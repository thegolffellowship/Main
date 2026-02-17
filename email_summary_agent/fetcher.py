"""
IMAP email fetcher.

Connects to each configured email account via IMAP and retrieves
recent messages within the configured lookback window.
"""

import email
import email.header
import email.utils
import imaplib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text converter."""

    def __init__(self):
        super().__init__()
        self._pieces = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self._pieces.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._pieces.append(data)

    def get_text(self):
        return "".join(self._pieces).strip()


def html_to_text(html_str):
    """Convert HTML to plain text."""
    extractor = _HTMLTextExtractor()
    extractor.feed(html_str)
    return extractor.get_text()


def decode_header_value(raw):
    """Decode an RFC 2047 encoded header into a plain string."""
    if raw is None:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def extract_body(msg, max_chars=1000):
    """Extract a plain-text snippet from an email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
            elif ct == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = html_to_text(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            if msg.get_content_type() == "text/html":
                body = html_to_text(payload.decode(charset, errors="replace"))
            else:
                body = payload.decode(charset, errors="replace")

    # Collapse whitespace and truncate
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "..."
    return body


def parse_date(msg):
    """Parse the Date header into a datetime, falling back to now."""
    date_str = msg.get("Date")
    if date_str:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed
    return datetime.now(timezone.utc)


def fetch_emails(account, lookback_hours=24, max_emails=50):
    """
    Fetch recent emails from one IMAP account.

    Returns a list of dicts:
        {"from", "to", "subject", "date", "snippet", "account_label"}
    """
    results = []
    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    since_str = since.strftime("%d-%b-%Y")

    imap_class = imaplib.IMAP4_SSL if account.get("use_ssl", True) else imaplib.IMAP4
    try:
        conn = imap_class(account["imap_server"], account.get("imap_port", 993))
        conn.login(account["email"], account["password"])
        conn.select("INBOX", readonly=True)

        # Search for messages since the lookback window
        status, msg_ids = conn.search(None, f'(SINCE "{since_str}")')
        if status != "OK" or not msg_ids[0]:
            conn.logout()
            return results

        id_list = msg_ids[0].split()
        # Take the most recent N
        id_list = id_list[-max_emails:]

        for mid in id_list:
            status, data = conn.fetch(mid, "(RFC822)")
            if status != "OK":
                continue
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            msg_date = parse_date(msg)
            # Skip messages older than the lookback window (SINCE is date-only)
            if msg_date.replace(tzinfo=timezone.utc) < since.replace(tzinfo=timezone.utc):
                continue

            results.append({
                "from": decode_header_value(msg.get("From", "")),
                "to": decode_header_value(msg.get("To", "")),
                "subject": decode_header_value(msg.get("Subject", "(no subject)")),
                "date": msg_date.strftime("%Y-%m-%d %H:%M"),
                "snippet": extract_body(msg),
                "account_label": account.get("label", account["email"]),
            })

        conn.logout()
    except Exception as e:
        print(f"  Error fetching from {account.get('label', account['email'])}: {e}")

    return results


def fetch_all_accounts(config):
    """Fetch emails from every configured account and return a combined list."""
    all_emails = []
    lookback = config.get("lookback_hours", 24)
    max_per = config.get("max_emails_per_account", 50)

    for acct in config["accounts"]:
        label = acct.get("label", acct["email"])
        print(f"  Fetching from {label}...")
        emails = fetch_emails(acct, lookback_hours=lookback, max_emails=max_per)
        print(f"    Found {len(emails)} email(s)")
        all_emails.extend(emails)

    # Sort by date descending
    all_emails.sort(key=lambda e: e["date"], reverse=True)
    return all_emails
