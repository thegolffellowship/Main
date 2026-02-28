"""
OAuth 2.0 Client Credentials support for the MCP endpoint.

Implements:
  - /.well-known/oauth-authorization-server  (RFC 8414 metadata)
  - /oauth/authorize   (authorization endpoint — auto-approves for known clients)
  - /oauth/token       (token endpoint — client_credentials + authorization_code)

Tokens are self-contained HMAC-SHA256 signed payloads (no external DB needed).
Works safely across multiple Gunicorn workers since verification is stateless.

Environment variables:
  MCP_CLIENT_ID      — OAuth client ID for the connector
  MCP_CLIENT_SECRET  — OAuth client secret for the connector
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, RedirectResponse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOKEN_LIFETIME = 3600  # 1 hour

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

def generate_token(client_id: str, lifetime: int = TOKEN_LIFETIME) -> str:
    """Create a signed access token."""
    payload = json.dumps({
        "client_id": client_id,
        "exp": int(time.time()) + lifetime,
        "jti": secrets.token_hex(8),
    }).encode()
    payload_b64 = _b64url_encode(payload)
    sig = hmac.new(_signing_key(), payload_b64.encode(), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{payload_b64}.{sig_b64}"

def verify_token(token: str) -> dict | None:
    """Verify a token's signature and expiration. Returns payload dict or None."""
    key = _signing_key()
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


# ---------------------------------------------------------------------------
# In-memory authorization code store (short-lived, per-worker)
# Codes expire in 60 seconds and are single-use.
# ---------------------------------------------------------------------------
_auth_codes: dict[str, dict] = {}

def _cleanup_codes():
    """Remove expired codes."""
    now = time.time()
    expired = [k for k, v in _auth_codes.items() if v["exp"] < now]
    for k in expired:
        del _auth_codes[k]


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _get_issuer(request: Request) -> str:
    """Build the issuer URL from the request."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{scheme}://{host}"


async def oauth_metadata(request: Request) -> JSONResponse:
    """RFC 8414 — OAuth 2.0 Authorization Server Metadata."""
    issuer = _get_issuer(request)
    return JSONResponse({
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/oauth/authorize",
        "token_endpoint": f"{issuer}/oauth/token",
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
        ],
        "grant_types_supported": [
            "authorization_code",
            "client_credentials",
        ],
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ["mcp"],
    })


async def oauth_authorize(request: Request) -> Response:
    """Authorization endpoint — auto-approves for valid client_id."""
    params = dict(request.query_params)
    client_id = params.get("client_id", "")
    redirect_uri = params.get("redirect_uri", "")
    state = params.get("state", "")
    response_type = params.get("response_type", "")
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "")

    if response_type != "code":
        return JSONResponse(
            {"error": "unsupported_response_type"},
            status_code=400,
        )

    expected_id = _client_id()
    if not expected_id or not secrets.compare_digest(client_id, expected_id):
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    if not redirect_uri:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "redirect_uri required"},
            status_code=400,
        )

    # Generate authorization code
    _cleanup_codes()
    code = secrets.token_urlsafe(32)
    _auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "exp": time.time() + 60,
    }

    # Redirect back with the code
    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={urllib.parse.quote(code)}"
    if state:
        location += f"&state={urllib.parse.quote(state)}"
    return RedirectResponse(url=location, status_code=302)


async def oauth_token(request: Request) -> JSONResponse:
    """Token endpoint — supports client_credentials and authorization_code."""
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
            pass

    client_id = data.get("client_id", "")
    client_secret = data.get("client_secret", "")

    expected_id = _client_id()
    expected_secret = _client_secret()

    if not expected_id or not expected_secret:
        return JSONResponse(
            {"error": "server_error", "error_description": "MCP OAuth not configured"},
            status_code=500,
        )

    # ── Client Credentials Grant ──
    if grant_type == "client_credentials":
        if not (secrets.compare_digest(client_id, expected_id) and
                secrets.compare_digest(client_secret, expected_secret)):
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        token = generate_token(client_id)
        return JSONResponse({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME,
            "scope": "mcp",
        })

    # ── Authorization Code Grant ──
    if grant_type == "authorization_code":
        code = data.get("code", "")
        redirect_uri = data.get("redirect_uri", "")
        code_verifier = data.get("code_verifier", "")

        _cleanup_codes()
        code_data = _auth_codes.pop(code, None)

        if not code_data:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired code"},
                status_code=400,
            )

        # Validate client
        if not secrets.compare_digest(code_data["client_id"], client_id or expected_id):
            return JSONResponse({"error": "invalid_client"}, status_code=401)

        # Validate redirect_uri if present
        if redirect_uri and redirect_uri != code_data["redirect_uri"]:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
                status_code=400,
            )

        # Validate PKCE code_verifier
        if code_data.get("code_challenge"):
            if not code_verifier:
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "code_verifier required"},
                    status_code=400,
                )
            # S256: BASE64URL(SHA256(code_verifier)) == code_challenge
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            computed = _b64url_encode(digest)
            if not secrets.compare_digest(computed, code_data["code_challenge"]):
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "code_verifier mismatch"},
                    status_code=400,
                )

        token = generate_token(code_data["client_id"])
        return JSONResponse({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": TOKEN_LIFETIME,
            "scope": "mcp",
        })

    return JSONResponse(
        {"error": "unsupported_grant_type"},
        status_code=400,
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

        # Skip auth if MCP_CLIENT_ID / MCP_CLIENT_SECRET not configured
        if not _client_id() or not _client_secret():
            await self.app(scope, receive, send)
            return

        # Extract bearer token from headers
        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode()

        if not auth_value.lower().startswith("bearer "):
            response = JSONResponse(
                {"error": "unauthorized", "error_description": "Bearer token required"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="mcp"'},
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
