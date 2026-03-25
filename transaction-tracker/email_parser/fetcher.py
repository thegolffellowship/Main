"""Microsoft Graph API email fetcher — reads inbox via OAuth and retrieves transaction-related emails."""

import logging
import os
import time
from datetime import datetime, timedelta

import msal
import requests

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Transient HTTP status codes worth retrying
_TRANSIENT_CODES = {429, 500, 502, 503, 504}
_RETRY_BACKOFFS = [2, 4, 8]  # seconds between retries


def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """HTTP request with retry on transient errors (429, 5xx).

    Respects Retry-After header on 429 responses.
    """
    for attempt in range(len(_RETRY_BACKOFFS) + 1):
        resp = requests.request(method, url, **kwargs)
        if resp.status_code not in _TRANSIENT_CODES:
            return resp
        if attempt < len(_RETRY_BACKOFFS):
            wait = _RETRY_BACKOFFS[attempt]
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = max(int(retry_after), 1)
                    except ValueError:
                        pass
            logger.warning(
                "Graph API %s %s returned %d — retry %d/%d in %ds",
                method.upper(), url, resp.status_code, attempt + 1, len(_RETRY_BACKOFFS), wait,
            )
            time.sleep(wait)
    # All retries exhausted — return last response (caller will raise_for_status)
    return resp

TRANSACTION_SUBJECTS = [
    "new order",
]


def _get_graph_token(tenant_id: str, client_id: str, client_secret: str) -> str | None:
    """Acquire an access token for Microsoft Graph using client credentials flow."""
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret,
    )

    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    if "access_token" in result:
        return result["access_token"]

    logger.error("Failed to acquire Graph token: %s", result.get("error_description", result))
    return None


def _is_transaction_email(subject: str, from_address: str) -> bool:
    """Only accept emails whose subject starts with 'New Order'."""
    subject_lower = (subject or "").lower().strip()

    for keyword in TRANSACTION_SUBJECTS:
        if subject_lower.startswith(keyword):
            return True

    return False


def fetch_transaction_emails(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    email_address: str,
    since_date: datetime | None = None,
) -> list[dict]:
    """
    Connect to Microsoft Graph API and return a list of raw email dicts
    that look like transaction/receipt emails.
    """
    if since_date is None:
        since_date = datetime.now() - timedelta(days=90)

    token = _get_graph_token(tenant_id, client_id, client_secret)
    if not token:
        raise RuntimeError("Could not acquire Graph API token — check AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET")
    logger.info("Graph API token acquired successfully for %s", email_address)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Format date for OData filter
    since_str = since_date.strftime("%Y-%m-%dT00:00:00Z")

    results = []
    # Graph API endpoint for reading a user's messages
    base_url = f"{GRAPH_BASE}/users/{email_address}/messages"
    params = {
        "$filter": f"receivedDateTime ge {since_str}",
        "$select": "id,subject,from,receivedDateTime,body,bodyPreview",
        "$top": "100",
        "$orderby": "receivedDateTime desc",
    }

    total_scanned = 0
    skipped_samples = []
    next_link = None

    first_page = True
    while first_page or next_link:
        if first_page:
            resp = _request_with_retry("get", base_url, headers=headers, params=params, timeout=30)
            first_page = False
        else:
            resp = _request_with_retry("get", next_link, headers=headers, timeout=30)

        logger.info("Graph API response status: %s  url: %s", resp.status_code, resp.url)
        resp.raise_for_status()
        data = resp.json()

        messages = data.get("value", [])
        logger.info("Page returned %d messages", len(messages))

        for msg in messages:
            total_scanned += 1
            from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
            subject = msg.get("subject", "")

            if not _is_transaction_email(subject, from_addr):
                # Log first few skipped emails so we can see what's being filtered out
                if len(skipped_samples) < 10:
                    skipped_samples.append(f"  from={from_addr}  subject={subject}")
                continue

            body = msg.get("body", {})
            body_content = body.get("content", "")
            content_type = body.get("contentType", "text")

            results.append({
                "uid": msg["id"],
                "subject": subject,
                "from": from_addr,
                "date": msg.get("receivedDateTime"),
                "text": body_content if content_type == "text" else "",
                "html": body_content if content_type == "html" else "",
            })

        # Follow pagination link if present
        next_link = data.get("@odata.nextLink")

    logger.info(
        "Fetched %d transaction emails out of %d total scanned since %s",
        len(results), total_scanned, since_date.date(),
    )
    if skipped_samples:
        logger.info("Sample skipped emails:\n%s", "\n".join(skipped_samples))

    return results


def fetch_email_by_id(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    email_address: str,
    message_id: str,
) -> dict | None:
    """Fetch a single email by Graph message ID. Returns raw email dict or None."""
    token = _get_graph_token(tenant_id, client_id, client_secret)
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = f"{GRAPH_BASE}/users/{email_address}/messages/{message_id}"
    params = {"$select": "id,subject,from,receivedDateTime,body"}

    try:
        resp = _request_with_retry("get", url, headers=headers, params=params, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        msg = resp.json()
        from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        subject = msg.get("subject", "")
        body = msg.get("body", {})
        body_content = body.get("content", "")
        content_type = body.get("contentType", "text")
        return {
            "uid": msg["id"],
            "subject": subject,
            "from": from_addr,
            "date": msg.get("receivedDateTime"),
            "text": body_content if content_type == "text" else "",
            "html": body_content if content_type == "html" else "",
        }
    except Exception:
        logger.exception("Failed to fetch email %s", message_id)
        return None


def send_mail_graph(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    from_address: str,
    to_address: str,
    subject: str,
    html_body: str,
) -> bool:
    """Send an email via Microsoft Graph API (requires Mail.Send permission).

    ``to_address`` may be a single email or a comma-separated list of emails.
    """
    token = _get_graph_token(tenant_id, client_id, client_secret)
    if not token:
        return False

    # Support comma-separated recipient list
    addresses = [a.strip() for a in to_address.split(",") if a.strip()]
    to_recipients = [{"emailAddress": {"address": addr}} for addr in addresses]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": html_body,
            },
            "toRecipients": to_recipients,
        },
        "saveToSentItems": "false",
    }

    url = f"{GRAPH_BASE}/users/{from_address}/sendMail"

    try:
        resp = _request_with_retry("post", url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        logger.info("Email sent via Graph API to %s", to_address)
        return True
    except requests.exceptions.HTTPError as e:
        logger.exception("Graph API send mail error: %s", e.response.text if e.response else e)
    except Exception:
        logger.exception("Failed to send email via Graph API")

    return False


def render_msg_template(template_text: str, variables: dict) -> str:
    """Render a message template by substituting {variable} placeholders.

    Only replaces known variable names to avoid KeyError on user-typed braces.
    """
    if not template_text:
        return template_text or ""
    result = template_text
    for key, value in variables.items():
        result = result.replace("{" + key + "}", str(value or ""))
    return result


def send_bulk_emails(
    recipients: list[dict],
    subject_template: str,
    body_template: str,
    event_vars: dict,
    delay_ms: int = 300,
) -> dict:
    """Send emails to a list of recipients with template variable substitution.

    Each recipient dict must have: player_name, email
    event_vars provides: event_name, event_date, course, chapter

    Returns: {"sent": N, "failed": N, "errors": [...]}
    """
    tenant_id = os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    from_address = os.getenv("EMAIL_ADDRESS")

    if not all([tenant_id, client_id, client_secret, from_address]):
        return {"sent": 0, "failed": len(recipients),
                "errors": [{"recipient": "all", "error": "Email credentials not configured"}]}

    sent = 0
    failed = 0
    errors = []

    for i, recip in enumerate(recipients):
        variables = {**event_vars, "player_name": recip["player_name"]}
        rendered_subject = render_msg_template(subject_template, variables)
        rendered_body = render_msg_template(body_template, variables)

        ok = send_mail_graph(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            from_address=from_address,
            to_address=recip["email"],
            subject=rendered_subject,
            html_body=rendered_body,
        )

        if ok:
            sent += 1
        else:
            failed += 1
            errors.append({"recipient": recip["email"], "error": "Graph API send failed"})

        # Throttle between sends (skip delay after last)
        if delay_ms > 0 and i < len(recipients) - 1:
            time.sleep(delay_ms / 1000.0)

    return {"sent": sent, "failed": failed, "errors": errors}
