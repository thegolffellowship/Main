"""
Transaction email parser — extracts purchase data (merchant, amount, date, items,
customer) from email text/HTML using pattern matching.

Supports generic transaction emails as well as MySimpleStore / The Golf Fellowship
order notifications.
"""

import re
import html
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Amount patterns
# ---------------------------------------------------------------------------
AMOUNT_PATTERNS = [
    r"\$\s?[\d,]+\.\d{2}",
    r"USD\s?[\d,]+\.\d{2}",
    r"(?:total|amount|charged|paid|payment|price|cost|subtotal)[:\s]*\$\s?[\d,]+\.\d{2}",
]

# Keywords that indicate the amount near them is the *total*
TOTAL_KEYWORDS = [
    "order total",
    "grand total",
    "total charged",
    "total amount",
    "amount charged",
    "payment amount",
    "you paid",
    "amount due",
    "total:",
    "charged:",
    "amount:",
    "total paid",
]

# ---------------------------------------------------------------------------
# Merchant / sender mapping
# ---------------------------------------------------------------------------
SENDER_TO_MERCHANT = {
    "mysimplestore.com": "The Golf Fellowship",
    "amazon.com": "Amazon",
    "paypal.com": "PayPal",
    "venmo.com": "Venmo",
    "square.com": "Square",
    "stripe.com": "Stripe",
    "apple.com": "Apple",
    "google.com": "Google",
    "shopify.com": "Shopify",
    "ebay.com": "eBay",
    "walmart.com": "Walmart",
    "target.com": "Target",
    "bestbuy.com": "Best Buy",
    "uber.com": "Uber",
    "lyft.com": "Lyft",
    "doordash.com": "DoorDash",
    "grubhub.com": "Grubhub",
    "ubereats.com": "Uber Eats",
    "netflix.com": "Netflix",
    "spotify.com": "Spotify",
    "chase.com": "Chase",
    "bankofamerica.com": "Bank of America",
    "wellsfargo.com": "Wells Fargo",
    "citi.com": "Citi",
    "capitalone.com": "Capital One",
    "americanexpress.com": "American Express",
    "discover.com": "Discover",
}


def _strip_html(raw_html: str) -> str:
    """Remove HTML tags and decode entities to plain text."""
    text = re.sub(r"<style[^>]*>.*?</style>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_amount(text: str) -> str | None:
    """
    Try to find the *total* transaction amount in the email body.
    Prioritizes amounts near 'total' keywords, falls back to the largest amount.
    """
    text_lower = text.lower()

    # First pass: look for amounts near total-related keywords.
    # Use a generous 200-char window to handle cases where the amount
    # is on the next line (e.g. MySimpleStore "Order Total:\n\n$163.53").
    for keyword in TOTAL_KEYWORDS:
        idx = text_lower.find(keyword)
        if idx == -1:
            continue
        window = text[idx : idx + 200]
        match = re.search(r"\$\s?[\d,]+\.\d{2}", window)
        if match:
            return _normalize_amount(match.group())

    # Second pass: collect all dollar amounts and return the largest
    all_amounts = re.findall(r"\$\s?[\d,]+\.\d{2}", text)
    if all_amounts:
        parsed = []
        for raw in all_amounts:
            val = _normalize_amount(raw)
            if val:
                try:
                    parsed.append((float(val.replace("$", "").replace(",", "")), val))
                except ValueError:
                    continue
        if parsed:
            parsed.sort(key=lambda x: x[0], reverse=True)
            return parsed[0][1]

    return None


def _normalize_amount(raw: str) -> str:
    """Clean up an amount string to a canonical $X,XXX.XX form."""
    raw = raw.strip()
    raw = re.sub(r"[^\d.,\$]", "", raw)
    if not raw.startswith("$"):
        raw = "$" + raw
    return raw


def _extract_merchant(from_addr: str, subject: str, body: str) -> str:
    """Determine the merchant name from sender, subject, or body."""
    from_lower = (from_addr or "").lower()

    # Check sender domain against known merchants
    for domain, name in SENDER_TO_MERCHANT.items():
        if domain in from_lower:
            return name

    # Try to extract from subject line patterns like "Your [Merchant] order"
    subject_patterns = [
        r"your\s+(.+?)\s+order",
        r"order\s+(?:from|at|with)\s+(.+?)[\s\-]",
        r"receipt\s+from\s+(.+?)[\s\-]",
        r"payment\s+to\s+(.+?)[\s\-]",
        r"(.+?)\s+receipt",
        r"(.+?)\s+order\s+confirmation",
    ]
    for pattern in subject_patterns:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            merchant = match.group(1).strip()
            if 2 < len(merchant) < 40:
                return merchant

    # Fall back to the sender display name
    name_match = re.match(r"^([^<@]+)", from_addr)
    if name_match:
        name = name_match.group(1).strip().strip('"')
        if name:
            return name

    return "Unknown"


def _extract_customer(text: str) -> str | None:
    """
    Try to extract the customer name from the email body.
    Handles MySimpleStore format ("New order from: Name") and
    shipping address blocks ("FIRSTNAME LASTNAME" in all caps).
    """
    # MySimpleStore: "New order from: Kenneth Carter"
    match = re.search(r"[Nn]ew order from:\s*(.+?)(?:\n|$)", text)
    if match:
        name = match.group(1).strip()
        if name:
            return name

    # Shipping Address block — look for an all-caps name after "Shipping Address"
    match = re.search(
        r"[Ss]hipping\s+[Aa]ddress\s*\n+\s*([A-Z][A-Z\s]+[A-Z])\s*\n",
        text,
    )
    if match:
        name = match.group(1).strip()
        # Title-case it: "KENNETH CARTER" → "Kenneth Carter"
        if name and len(name) > 2:
            return name.title()

    return None


# ---------------------------------------------------------------------------
# Item extraction
# ---------------------------------------------------------------------------

# Detail-line labels found in MySimpleStore / Golf Fellowship order emails.
# Matched case-insensitively against the beginning of each line; the value
# after the colon is captured.
_DETAIL_LABELS = [
    "GOLF or COMPETE",
    "MEMBER STATUS",
    "TEE CHOICE",
    "POST-GAME",
    "POST GAME",
    "HANDICAP",
    "SHIRT SIZE",
    "GUEST NAME",
    "GUEST",
]

# Lines starting with these tokens are never item titles.
_SKIP_LINE_RE = re.compile(
    r"^(Rs=|SKU:|Qty:)",
    re.IGNORECASE,
)


def _extract_items(text: str) -> list:
    """
    Extract line items from the email body.

    For MySimpleStore / Golf Fellowship emails, returns a list of dicts::

        {"name": "Feb 22 - LaCANTERA", "price": "$158.00",
         "details": {"GOLF or COMPETE": "COMPETE",
                     "MEMBER STATUS": "Non-Member", ...}}

    For other merchants, returns a list of plain strings (backward-compatible).
    """
    items: list = []

    # ----- MySimpleStore / Golf Fellowship format -----
    mysimplestore_match = re.search(
        r"Order Summary\b(.*?)(?:Subtotal|Sub total)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if mysimplestore_match:
        block = mysimplestore_match.group(1)
        # Split on price tokens so each chunk = description before a price
        product_chunks = re.split(r"(\$[\d,]+\.\d{2})", block)
        i = 0
        while i < len(product_chunks) - 1:
            desc = product_chunks[i].strip()
            price = product_chunks[i + 1].strip() if i + 1 < len(product_chunks) else ""
            if desc and price:
                lines = [ln.strip() for ln in desc.splitlines() if ln.strip()]

                # Separate title lines from detail lines
                title_lines: list[str] = []
                details: dict[str, str] = {}

                for line in lines:
                    if _SKIP_LINE_RE.match(line):
                        continue

                    # Check if this line is a known detail label
                    matched_label = False
                    for label in _DETAIL_LABELS:
                        if line.upper().startswith(label.upper()):
                            val = line.split(":", 1)[-1].strip() if ":" in line else ""
                            details[label] = val
                            matched_label = True
                            break

                    if not matched_label and len(line) > 2:
                        title_lines.append(line)

                if title_lines:
                    items.append({
                        "name": title_lines[0],
                        "price": price,
                        "details": details,
                    })
            i += 2
        if items:
            return items[:20]

    # ----- Generic patterns (other merchants) -----
    item_patterns = [
        r"(\d+)\s*x\s+(.+?)\s+\$[\d,]+\.\d{2}",
        r"^[\s•\-\*]+(.+?)\s+\$[\d,]+\.\d{2}",
    ]
    for pattern in item_patterns:
        matches = re.findall(pattern, text, re.MULTILINE)
        for match in matches:
            if isinstance(match, tuple):
                item = match[-1].strip()
            else:
                item = match.strip()
            if 2 < len(item) < 100:
                items.append(item)

    return items[:20]


def _extract_order_id(subject: str, text: str) -> str | None:
    """Try to find an order/confirmation number from subject line and body."""
    # Subject: "New Order #R854482675"
    match = re.search(r"[Oo]rder\s*#\s*([A-Za-z0-9\-]{4,30})", subject)
    if match:
        return match.group(1).strip()

    # Body: "Order: R854482675" (MySimpleStore format)
    match = re.search(r"[Oo]rder:\s*([A-Za-z0-9\-]{4,30})", text)
    if match:
        return match.group(1).strip()

    # Generic body patterns
    patterns = [
        r"order\s*(?:#|number|no\.?)[:\s]*([A-Z0-9\-]{4,30})",
        r"confirmation\s*(?:#|number|no\.?)[:\s]*([A-Z0-9\-]{4,30})",
        r"transaction\s*(?:#|id|number)[:\s]*([A-Z0-9\-]{4,30})",
        r"reference\s*(?:#|number|no\.?)[:\s]*([A-Z0-9\-]{4,30})",
        r"#\s*([A-Z0-9\-]{6,30})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_date(text: str, email_date: datetime | None) -> str:
    """
    Try to extract the order date from the email body.
    Falls back to the email's sent date.
    """
    # MySimpleStore: "Date: 02-10-2026"
    match = re.search(r"Date:\s*(\d{2}-\d{2}-\d{4})", text)
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%m-%d-%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # ISO-style dates in body
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)

    if isinstance(email_date, datetime):
        return email_date.strftime("%Y-%m-%d %H:%M")

    return str(email_date) if email_date else ""


def parse_email(email_data: dict) -> dict | None:
    """
    Parse a single email dict (from fetcher) and return structured transaction data.

    Returns None if no transaction amount could be extracted.
    """
    body = email_data.get("text", "")
    if not body and email_data.get("html"):
        body = _strip_html(email_data["html"])

    if not body:
        return None

    subject = email_data.get("subject", "")
    from_addr = email_data.get("from", "")

    amount = _extract_amount(body)
    if not amount:
        html_body = email_data.get("html", "")
        if html_body:
            amount = _extract_amount(_strip_html(html_body))

    if not amount:
        return None

    merchant = _extract_merchant(from_addr, subject, body)
    items = _extract_items(body)
    order_id = _extract_order_id(subject, body)
    customer = _extract_customer(body)
    date_str = _extract_date(body, email_data.get("date"))

    return {
        "email_uid": email_data.get("uid", ""),
        "merchant": merchant,
        "amount": amount,
        "date": date_str,
        "subject": subject,
        "from": from_addr,
        "items": items,
        "order_id": order_id,
        "customer": customer,
    }


def parse_emails(email_list: list[dict]) -> list[dict]:
    """Parse a batch of emails and return successfully parsed transactions."""
    transactions = []
    for email_data in email_list:
        try:
            result = parse_email(email_data)
            if result:
                transactions.append(result)
        except Exception:
            logger.exception("Failed to parse email uid=%s", email_data.get("uid"))
    logger.info("Parsed %d transactions from %d emails", len(transactions), len(email_list))
    return transactions
