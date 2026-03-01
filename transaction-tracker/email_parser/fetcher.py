"""Microsoft Graph API email fetcher — reads inbox via OAuth and retrieves transaction-related emails."""

import logging
import os
from datetime import datetime, timedelta

import msal
import requests

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Senders commonly associated with purchase/transaction receipts
TRANSACTION_SENDERS = [
    "mysimplestore.com",
    "amazon.com",
    "paypal.com",
    "venmo.com",
    "square.com",
    "squareup.com",
    "stripe.com",
    "apple.com",
    "google.com",
    "shopify.com",
    "ebay.com",
    "walmart.com",
    "target.com",
    "bestbuy.com",
    "uber.com",
    "lyft.com",
    "doordash.com",
    "grubhub.com",
    "ubereats.com",
    "netflix.com",
    "spotify.com",
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "citi.com",
    "capitalone.com",
    "americanexpress.com",
    "discover.com",
    # Golf / tee-time / event platforms
    "golfnow.com",
    "teeoff.com",
    "foreup.com",
    "chronogolf.com",
    "golfgenius.com",
    "clubessential.com",
    "lightspeedhq.com",
    "clover.com",
    "toasttab.com",
    "eventbrite.com",
    "golfchannel.com",
    # General business / payments
    "intuit.com",
    "quickbooks.com",
    "freshbooks.com",
    "waveapps.com",
    "zelle.com",
    "cashapp.com",
    "notify.thegolffellowship.com",
    "thegolffellowship.com",
    "noreply",
    "no-reply",
]

TRANSACTION_SUBJECTS = [
    "new order",
    "receipt",
    "order confirmation",
    "payment",
    "transaction",
    "purchase",
    "invoice",
    "billing",
    "charged",
    "your order",
    "order shipped",
    "payment received",
    "payment sent",
    "autopay",
    "statement",
    # Golf / event related
    "tee time",
    "booking",
    "reservation",
    "registration",
    "membership",
    "renewal",
    "dues",
    "entry fee",
    "round of golf",
    "golf event",
    "tournament",
    "confirmation",
    "thank you for your",
    "your booking",
    "event registration",
    "subscription",
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
    """Heuristic check: does the email look like a transaction/receipt?"""
    subject_lower = (subject or "").lower()
    from_lower = (from_address or "").lower()

    for domain in TRANSACTION_SENDERS:
        if domain in from_lower:
            return True

    for keyword in TRANSACTION_SUBJECTS:
        if keyword in subject_lower:
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
            resp = requests.get(base_url, headers=headers, params=params, timeout=30)
            first_page = False
        else:
            resp = requests.get(next_link, headers=headers, timeout=30)

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
        resp = requests.get(url, headers=headers, params=params, timeout=30)
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
    """Send an email via Microsoft Graph API (requires Mail.Send permission)."""
    token = _get_graph_token(tenant_id, client_id, client_secret)
    if not token:
        return False

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
            "toRecipients": [
                {"emailAddress": {"address": to_address}}
            ],
        },
        "saveToSentItems": "false",
    }

    url = f"{GRAPH_BASE}/users/{from_address}/sendMail"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        logger.info("Email sent via Graph API to %s", to_address)
        return True
    except requests.exceptions.HTTPError as e:
        logger.exception("Graph API send mail error: %s", e.response.text if e.response else e)
    except Exception:
        logger.exception("Failed to send email via Graph API")

    return False
