"""
OAuth 2.0 support for the MCP endpoint.

Implements:
  - /.well-known/oauth-protected-resource  (RFC 9728 discovery)
  - /.well-known/oauth-authorization-server  (RFC 8414 metadata)
  - /oauth/register  (RFC 7591 Dynamic Client Registration)
  - /oauth/authorize   (authorization endpoint — a person approves with the ADMIN PIN, Kerry 10/23)
  - /oauth/token       (token endpoint — client_credentials + authorization_code)

Tokens AND authorization codes are self-contained HMAC-SHA256 signed
payloads — no shared state needed, works safely across multiple
Gunicorn workers.

Environment variables:
  MCP_CLIENT_ID      — OAuth client ID for the connector
  MCP_CLIENT_SECRET  — OAuth client secret for the connector
                       IMPORTANT: Use alphanumeric characters only (no dashes,
                       double-dashes, or special symbols). Railway's variable
                       parser may strip or mishandle values containing -- or
                       other special characters, preventing the secret from
                       reaching the process environment.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import urllib.parse
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, RedirectResponse

logger = logging.getLogger(__name__)

# Startup diagnostic: confirm whether MCP env vars are visible to this process
logger.info(
    "mcp_auth module loaded — MCP_CLIENT_ID present in os.environ: %s, "
    "MCP_CLIENT_SECRET present in os.environ: %s",
    "MCP_CLIENT_ID" in os.environ,
    "MCP_CLIENT_SECRET" in os.environ,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOKEN_LIFETIME = 86400          # 24 hours (was 1h — hourly re-auth pain)
REFRESH_TOKEN_LIFETIME = 30 * 86400  # 30 days
AUTH_CODE_LIFETIME = 120  # 2 minutes (generous for network round-trips)

def _client_id():
    return os.getenv("MCP_CLIENT_ID", "")

def _client_secret():
    return os.getenv("MCP_CLIENT_SECRET", "")

def _signing_key():
    """Derive signing key from the client secret (stable across workers)."""
    secret = _client_secret()
    if not secret:
        return b""
    return hashlib.sha256(("mcp-token-sign:" + secret).encode()).digest()

def _code_signing_key():
    """Separate signing key for authorization codes."""
    secret = _client_secret()
    if not secret:
        return b""
    return hashlib.sha256(("mcp-auth-code:" + secret).encode()).digest()


# ---------------------------------------------------------------------------
# Token helpers (stateless HMAC-SHA256)
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)

def _sign_payload(payload_dict: dict, key: bytes) -> str:
    """Create a signed payload string: base64(json).base64(hmac)."""
    payload_b64 = _b64url_encode(json.dumps(payload_dict).encode())
    sig = hmac.new(key, payload_b64.encode(), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"

def _verify_signed(token: str, key: bytes) -> dict | None:
    """Verify a signed payload. Returns payload dict or None."""
    if not key:
        return None
    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload_b64, sig_b64 = parts
    try:
        expected_sig = hmac.new(key, payload_b64.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def generate_token(client_id: str, lifetime: int = TOKEN_LIFETIME) -> str:
    """Create a signed access token."""
    return _sign_payload({
        "client_id": client_id,
        "exp": int(time.time()) + lifetime,
        "jti": secrets.token_hex(8),
    }, _signing_key())


def generate_refresh_token(client_id: str,
                           lifetime: int = REFRESH_TOKEN_LIFETIME) -> str:
    """Create a signed refresh token (type-tagged so it can't be used as an
    access token — verify_token rejects it)."""
    return _sign_payload({
        "type": "refresh",
        "client_id": client_id,
        "exp": int(time.time()) + lifetime,
        "jti": secrets.token_hex(8),
    }, _signing_key())


def verify_refresh_token(token: str) -> dict | None:
    """Verify a refresh token's signature, expiration, and type tag."""
    payload = _verify_signed(token, _signing_key())
    if not payload or payload.get("type") != "refresh":
        return None
    return payload

def verify_token(token: str) -> dict | None:
    """Verify an access token's signature and expiration.

    Refresh tokens (type='refresh') are NOT valid access tokens."""
    payload = _verify_signed(token, _signing_key())
    if payload and payload.get("type") == "refresh":
        return None
    return payload


def _generate_auth_code(client_id: str, redirect_uri: str,
                        code_challenge: str, code_challenge_method: str) -> str:
    """Create a stateless signed authorization code (works across workers)."""
    return _sign_payload({
        "type": "auth_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "exp": int(time.time()) + AUTH_CODE_LIFETIME,
        "jti": secrets.token_hex(8),
    }, _code_signing_key())

def _verify_auth_code(code: str) -> dict | None:
    """Verify an authorization code's signature and expiration."""
    payload = _verify_signed(code, _code_signing_key())
    if payload and payload.get("type") != "auth_code":
        return None
    return payload


# ---------------------------------------------------------------------------
# CORS helper
# ---------------------------------------------------------------------------
_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _get_issuer(request: Request) -> str:
    """Build the issuer URL from the request."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{scheme}://{host}"


async def oauth_protected_resource(request: Request) -> JSONResponse:
    """RFC 9728 — Protected Resource Metadata.

    Claude.ai fetches this to discover which authorization server to use.
    Path-aware: serves for any sub-path (e.g. /mcp/mcp).
    """
    issuer = _get_issuer(request)
    logger.info("PRM requested from %s (path=%s)",
                request.client.host if request.client else "unknown",
                request.url.path)
    return JSONResponse({
        "resource": f"{issuer}/mcp/mcp",
        "authorization_servers": [issuer],
        "scopes_supported": ["mcp"],
        "bearer_methods_supported": ["header"],
    }, headers=_CORS_HEADERS)


async def oauth_metadata(request: Request) -> JSONResponse:
    """RFC 8414 — OAuth 2.0 Authorization Server Metadata."""
    issuer = _get_issuer(request)
    logger.info("OAuth metadata requested from %s", request.client.host if request.client else "unknown")
    return JSONResponse({
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "registration_endpoint": f"{issuer}/oauth/register",
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
            "none",
        ],
        "grant_types_supported": [
            "authorization_code",
            "client_credentials",
            "refresh_token",
        ],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp"],
    }, headers=_CORS_HEADERS)


# Kerry 10/23 (Tracker Build 4 security finding): the authorize step used to
# AUTO-APPROVE any request carrying the client id, and /oauth/register hands
# that id to anyone, so whoever knew the URL could add the Tracker as their own
# Claude connector. Now a person must type the ADMIN PIN on this page before a
# code is issued. Failed PINs are throttled.
_PIN_FAILS: list = []
_PIN_FAIL_WINDOW = 900
_PIN_FAIL_MAX = 8


def _pin_locked() -> bool:
    now = time.time()
    _PIN_FAILS[:] = [t for t in _PIN_FAILS if now - t < _PIN_FAIL_WINDOW]
    return len(_PIN_FAILS) >= _PIN_FAIL_MAX


def _approve_page(params: dict, error: str = "") -> Response:
    from html import escape
    keep = ("client_id", "redirect_uri", "state", "response_type",
            "code_challenge", "code_challenge_method", "scope")
    hidden = "".join(
        f'<input type="hidden" name="{k}" value="{escape(params.get(k, ""), quote=True)}">'
        for k in keep)
    err = f'<p style="color:#B91C1C">{escape(error)}</p>' if error else ""
    host = escape(urllib.parse.urlparse(params.get("redirect_uri", "")).netloc or "unknown")
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Approve connector - TGF Tracker</title></head>
<body style="font-family:Helvetica,Arial,sans-serif;background:#F8F8F8;color:#1B1B1B;margin:0">
<div style="max-width:420px;margin:48px auto;background:#fff;border:1px solid #E5E7EB;border-radius:10px;padding:24px">
<h2 style="margin:0 0 8px">Approve a connector</h2>
<p style="color:#4B5563">An app at <b>{host}</b> is asking for full access to the TGF Tracker.
Only approve this if you just added the Tracker connector yourself.</p>{err}
<form method="post" action="/oauth/authorize">{hidden}
<label>Admin PIN<br><input name="pin" type="password" inputmode="numeric" autocomplete="off"
 style="width:100%;padding:10px;margin:6px 0 14px;border:1px solid #E5E7EB;border-radius:8px;font-size:16px"></label>
<button type="submit" style="background:#E87C3E;color:#fff;border:0;border-radius:999px;padding:12px 22px;font-size:15px">Approve</button>
</form></div></body></html>"""
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-store"})


async def oauth_authorize(request: Request) -> Response:
    """Authorization endpoint: GET shows the approve page, POST checks the
    ADMIN PIN and only then issues a code."""
    if request.method == "POST":
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}
    else:
        params = dict(request.query_params)
    client_id = params.get("client_id", "")
    redirect_uri = params.get("redirect_uri", "")
    state = params.get("state", "")
    response_type = params.get("response_type", "")
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "")
    scope = params.get("scope", "")

    logger.info(
        "OAuth authorize (%s): client_id=%s redirect_uri=%s response_type=%s "
        "code_challenge_method=%s scope=%s",
        request.method, client_id, redirect_uri, response_type, code_challenge_method, scope,
    )

    if response_type != "code":
        logger.warning("OAuth authorize: unsupported response_type=%s", response_type)
        return JSONResponse(
            {"error": "unsupported_response_type"},
            status_code=400,
        )

    expected_id = _client_id()
    if not expected_id or not secrets.compare_digest(client_id, expected_id):
        logger.warning("OAuth authorize: invalid client_id=%s", client_id)
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    if not redirect_uri:
        logger.warning("OAuth authorize: missing redirect_uri")
        return JSONResponse(
            {"error": "invalid_request", "error_description": "redirect_uri required"},
            status_code=400,
        )

    if request.method != "POST":
        return _approve_page(params)
    if _pin_locked():
        logger.warning("OAuth authorize: PIN attempts locked")
        return _approve_page(params, "Too many wrong PINs. Try again in 15 minutes.")
    admin_pin = os.getenv("ADMIN_PIN", "")
    if not admin_pin or not secrets.compare_digest(params.get("pin", ""), admin_pin):
        _PIN_FAILS.append(time.time())
        logger.warning("OAuth authorize: wrong PIN")
        return _approve_page(params, "That PIN is not right.")

    # Generate stateless signed authorization code
    code = _generate_auth_code(client_id, redirect_uri, code_challenge, code_challenge_method)

    # Redirect back with the code
    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={urllib.parse.quote(code)}"
    if state:
        location += f"&state={urllib.parse.quote(state)}"

    logger.info("OAuth authorize: PIN approved, issuing code, redirecting to %s", redirect_uri)
    return RedirectResponse(url=location, status_code=302)


async def oauth_register(request: Request) -> Response:
    """RFC 7591 — Dynamic Client Registration.

    Claude.ai calls this to self-register as an OAuth client.
    Returns the configured MCP_CLIENT_ID so the rest of the flow
    (authorize → token) works with the same credentials.
    """
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_CORS_HEADERS)

    try:
        data = await request.json()
    except Exception:
        data = {}

    logger.info("OAuth register: client_name=%s redirect_uris=%s",
                data.get("client_name"), data.get("redirect_uris"))

    cid = _client_id()
    if not cid:
        logger.error("OAuth register: MCP_CLIENT_ID not configured")
        return JSONResponse(
            {"error": "server_error", "error_description": "MCP OAuth not configured"},
            status_code=500,
            headers=_CORS_HEADERS,
        )

    # Return the configured client_id.  For PKCE public clients the
    # secret is not required — token_endpoint_auth_method=none.
    response_data = {
        "client_id": cid,
        "client_name": data.get("client_name", "MCP Client"),
        "redirect_uris": data.get("redirect_uris", []),
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": "mcp",
    }
    logger.info("OAuth register: registered client_id=%s", cid)
    return JSONResponse(response_data, status_code=201, headers=_CORS_HEADERS)


async def oauth_token(request: Request) -> Response:
    """Token endpoint — supports client_credentials and authorization_code."""
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_CORS_HEADERS)

    content_type = request.headers.get("content-type", "")

    # Parse form body or JSON
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        data = dict(form)
    elif "application/json" in content_type:
        data = await request.json()
    else:
        # Try form anyway (common for OAuth)
        try:
            form = await request.form()
            data = dict(form)
        except Exception:
            data = {}

    grant_type = data.get("grant_type", "")

    # Check for HTTP Basic auth as well
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode()
            basic_id, basic_secret = decoded.split(":", 1)
            data.setdefault("client_id", basic_id)
            data.setdefault("client_secret", basic_secret)
        except Exception:
            logger.warning("OAuth token: malformed Basic auth header")

    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")

    logger.info(
        "OAuth token: grant_type=%s client_id=%s has_secret=%s content_type=%s",
        grant_type, client_id, bool(client_secret), content_type,
    )

    expected_id = _client_id()
    expected_secret = _client_secret()

    if not expected_id or not expected_secret:
        logger.error("OAuth token: MCP_CLIENT_ID or MCP_CLIENT_SECRET not configured")
        return JSONResponse(
            {"error": "server_error", "error_description": "MCP OAuth not configured"},
            status_code=500,
            headers=_CORS_HEADERS,
        )

    # ── Client Credentials Grant ──
    if grant_type == "client_credentials":
        if not (secrets.compare_digest(client_id, expected_id) and
                secrets.compare_digest(client_secret, expected_secret)):
            logger.warning("OAuth token: client_credentials invalid credentials")
            return JSONResponse({"error": "invalid_client"}, status_code=401, headers=_CORS_HEADERS)

        token = generate_token(client_id)
        logger.info("OAuth token: client_credentials grant succeeded")
        return JSONResponse({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME,
            "refresh_token": generate_refresh_token(client_id),
            "scope": "mcp",
        }, headers=_CORS_HEADERS)

    # ── Authorization Code Grant ──
    if grant_type == "authorization_code":
        code = data.get("code", "")
        redirect_uri = data.get("redirect_uri", "")
        code_verifier = data.get("code_verifier", "")

        logger.info(
            "OAuth token: auth_code exchange — has_code=%s has_redirect_uri=%s "
            "has_code_verifier=%s",
            bool(code), bool(redirect_uri), bool(code_verifier),
        )

        # Verify the stateless signed auth code
        code_data = _verify_auth_code(code)

        if not code_data:
            logger.warning("OAuth token: invalid or expired authorization code")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired code"},
                status_code=400,
                headers=_CORS_HEADERS,
            )

        logger.info("OAuth token: code verified — code_client=%s code_redirect=%s",
                     code_data.get("client_id"), code_data.get("redirect_uri"))

        # Validate client — accept if client_id matches OR if not provided (PKCE public client)
        if client_id and not secrets.compare_digest(code_data["client_id"], client_id):
            logger.warning("OAuth token: client_id mismatch (code=%s, request=%s)",
                           code_data["client_id"], client_id)
            return JSONResponse({"error": "invalid_client"}, status_code=401, headers=_CORS_HEADERS)

        # Validate redirect_uri if present
        if redirect_uri and redirect_uri != code_data["redirect_uri"]:
            logger.warning("OAuth token: redirect_uri mismatch (code=%s, request=%s)",
                           code_data["redirect_uri"], redirect_uri)
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
                status_code=400,
                headers=_CORS_HEADERS,
            )

        # Validate PKCE code_verifier
        if code_data.get("code_challenge"):
            if not code_verifier:
                logger.warning("OAuth token: code_verifier required but missing")
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "code_verifier required"},
                    status_code=400,
                    headers=_CORS_HEADERS,
                )
            # S256: BASE64URL(SHA256(code_verifier)) == code_challenge
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            computed = _b64url_encode(digest)
            if not secrets.compare_digest(computed, code_data["code_challenge"]):
                logger.warning("OAuth token: PKCE code_verifier mismatch")
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "code_verifier mismatch"},
                    status_code=400,
                    headers=_CORS_HEADERS,
                )
            logger.info("OAuth token: PKCE verification passed")

        token = generate_token(code_data["client_id"])
        logger.info("OAuth token: authorization_code grant succeeded for client=%s",
                     code_data["client_id"])
        return JSONResponse({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME,
            "refresh_token": generate_refresh_token(code_data["client_id"]),
            "scope": "mcp",
        }, headers=_CORS_HEADERS)

    # ── Refresh Token Grant ──
    if grant_type == "refresh_token":
        refresh = data.get("refresh_token", "")
        payload = verify_refresh_token(refresh)
        if not payload:
            logger.warning("OAuth token: invalid or expired refresh token")
            return JSONResponse(
                {"error": "invalid_grant",
                 "error_description": "Invalid or expired refresh token"},
                status_code=400,
                headers=_CORS_HEADERS,
            )
        if client_id and not secrets.compare_digest(payload["client_id"], client_id):
            logger.warning("OAuth token: refresh client_id mismatch")
            return JSONResponse({"error": "invalid_client"}, status_code=401,
                                headers=_CORS_HEADERS)
        logger.info("OAuth token: refresh_token grant succeeded for client=%s",
                     payload["client_id"])
        return JSONResponse({
            "access_token": generate_token(payload["client_id"]),
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME,
            "refresh_token": generate_refresh_token(payload["client_id"]),
            "scope": "mcp",
        }, headers=_CORS_HEADERS)

    logger.warning("OAuth token: unsupported grant_type=%s", grant_type)
    return JSONResponse(
        {"error": "unsupported_grant_type"},
        status_code=400,
        headers=_CORS_HEADERS,
    )


# ---------------------------------------------------------------------------
# MCP Auth Middleware
# ---------------------------------------------------------------------------

class MCPAuthMiddleware:
    """ASGI middleware that requires a valid Bearer token on MCP requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # SECURITY: fail CLOSED if MCP_CLIENT_ID / MCP_CLIENT_SECRET are not
        # configured. This used to skip auth entirely (fail open), which meant
        # a deploy that forgot the env vars exposed every MCP write tool
        # (update/delete transactions, delete events, ...) to anonymous
        # callers. An unconfigured server now refuses MCP traffic instead.
        if not _client_id() or not _client_secret():
            logger.error(
                "MCP request rejected: MCP_CLIENT_ID/MCP_CLIENT_SECRET not "
                "configured — set both env vars to enable the MCP endpoint"
            )
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = JSONResponse(
                {
                    "error": "mcp_not_configured",
                    "error_description": "MCP OAuth is not configured on this server.",
                },
                status_code=503,
            )
            await response(scope, receive, send)
            return

        # Extract bearer token from headers
        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode()

        if not auth_value.lower().startswith("bearer "):
            # Build the resource_metadata URL from request headers
            host = None
            scheme = b"https"
            for h_name, h_value in scope.get("headers", []):
                if h_name == b"host":
                    host = h_value.decode()
                elif h_name == b"x-forwarded-proto":
                    scheme = h_value
            if host:
                prm_url = f"{scheme.decode() if isinstance(scheme, bytes) else scheme}://{host}/.well-known/oauth-protected-resource"
            else:
                prm_url = "/.well-known/oauth-protected-resource"
            response = JSONResponse(
                {"error": "unauthorized", "error_description": "Bearer token required"},
                status_code=401,
                headers={
                    "WWW-Authenticate": f'Bearer realm="mcp", resource_metadata="{prm_url}"',
                },
            )
            await response(scope, receive, send)
            return

        token = auth_value[7:]
        payload = verify_token(token)
        if not payload:
            response = JSONResponse(
                {"error": "invalid_token", "error_description": "Token expired or invalid"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="mcp", error="invalid_token"'},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
