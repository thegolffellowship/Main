"""
Transaction email parser — extracts purchase data (merchant, amount, date, items)
from email text/HTML using pattern matching.
"""

import re
import html
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Amount patterns — match monetary values like $12.34, USD 12.34, 12,345.67
# ---------------------------------------------------------------------------
AMOUNT_PATTERNS = [
    # $1,234.56 or $ 1,234.56
    r"\$\s?[\d,]+\.\d{2}",
    # USD 1,234.56
    r"USD\s?[\d,]+\.\d{2}",
    # "Total: $12.34" or "Amount: $12.34" (capture the number)
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

    # First pass: look for amounts near total-related keywords
    for keyword in TOTAL_KEYWORDS:
        idx = text_lower.find(keyword)
        if idx == -1:
            continue
        # Search within 80 chars after the keyword
        window = text[idx : idx + 80]
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


def _extract_items(text: str) -> list[str]:
    """Try to pull individual line items from the email body."""
    items = []

    # Pattern: "Product Name ... $XX.XX" or "1x Product Name $XX.XX"
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

    return items[:20]  # cap at 20 items


def _extract_order_id(text: str) -> str | None:
    """Try to find an order/confirmation number."""
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
        # Also try the HTML version
        html_body = email_data.get("html", "")
        if html_body:
            amount = _extract_amount(_strip_html(html_body))

    if not amount:
        return None

    merchant = _extract_merchant(from_addr, subject, body)
    items = _extract_items(body)
    order_id = _extract_order_id(body)

    email_date = email_data.get("date")
    if isinstance(email_date, datetime):
        date_str = email_date.strftime("%Y-%m-%d %H:%M")
    else:
        date_str = str(email_date) if email_date else ""

    return {
        "email_uid": email_data.get("uid", ""),
        "merchant": merchant,
        "amount": amount,
        "date": date_str,
        "subject": subject,
        "from": from_addr,
        "items": items,
        "order_id": order_id,
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
