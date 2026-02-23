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
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Format date for OData filter
    since_str = since_date.strftime("%Y-%m-%dT00:00:00Z")

    results = []
    # Graph API endpoint for reading a user's messages
    url = (
        f"{GRAPH_BASE}/users/{email_address}/messages"
        f"?$filter=receivedDateTime ge {since_str}"
        f"&$select=id,subject,from,receivedDateTime,body,bodyPreview"
        f"&$top=100"
        f"&$orderby=receivedDateTime desc"
    )

    try:
        while url:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for msg in data.get("value", []):
                from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
                subject = msg.get("subject", "")

                if not _is_transaction_email(subject, from_addr):
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
            url = data.get("@odata.nextLink")

        logger.info("Fetched %d transaction emails since %s", len(results), since_date.date())
    except requests.exceptions.HTTPError as e:
        logger.exception("Graph API HTTP error: %s", e.response.text if e.response else e)
    except Exception:
        logger.exception("Failed to fetch emails via Graph API")

    return results


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
