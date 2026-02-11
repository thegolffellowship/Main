"""IMAP email fetcher — connects to inbox and retrieves transaction-related emails."""

import logging
from datetime import datetime, timedelta
from imap_tools import MailBox, AND

logger = logging.getLogger(__name__)

# Senders commonly associated with purchase/transaction receipts
TRANSACTION_SENDERS = [
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


def connect(host: str, port: int, email: str, password: str) -> MailBox:
    """Open an IMAP connection and authenticate."""
    mailbox = MailBox(host, port)
    mailbox.login(email, password)
    return mailbox


def _is_transaction_email(msg) -> bool:
    """Heuristic check: does the email look like a transaction/receipt?"""
    subject_lower = (msg.subject or "").lower()
    from_lower = (msg.from_ or "").lower()

    # Check sender domain
    for domain in TRANSACTION_SENDERS:
        if domain in from_lower:
            return True

    # Check subject keywords
    for keyword in TRANSACTION_SUBJECTS:
        if keyword in subject_lower:
            return True

    return False


def fetch_transaction_emails(
    host: str,
    port: int,
    email_address: str,
    password: str,
    since_date: datetime | None = None,
    folder: str = "INBOX",
) -> list[dict]:
    """
    Connect to the mailbox and return a list of raw email dicts
    that look like transaction/receipt emails.
    """
    if since_date is None:
        since_date = datetime.now() - timedelta(days=90)

    results = []

    try:
        with MailBox(host, int(port)).login(email_address, password, folder) as mailbox:
            criteria = AND(date_gte=since_date.date())
            for msg in mailbox.fetch(criteria, mark_seen=False):
                if not _is_transaction_email(msg):
                    continue

                results.append(
                    {
                        "uid": msg.uid,
                        "subject": msg.subject,
                        "from": msg.from_,
                        "date": msg.date,
                        "text": msg.text or "",
                        "html": msg.html or "",
                    }
                )

        logger.info("Fetched %d transaction emails since %s", len(results), since_date.date())
    except Exception:
        logger.exception("Failed to fetch emails")

    return results
