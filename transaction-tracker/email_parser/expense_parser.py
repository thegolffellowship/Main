"""
Expense & Financial Email Parser — classifies and extracts data from
Chase alerts, Venmo payments, expense receipts, and action-required emails.

Uses Claude Haiku for LLM-based extraction (same approach as transaction parser).
"""

import json
import logging
import os
import re
from datetime import datetime

import anthropic

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Known merchant context for receipt categorization
# ---------------------------------------------------------------------------

_KNOWN_MERCHANTS = {
    "make.com": {"category": "Automation Software", "entity": "TGF"},
    "railway": {"category": "Hosting", "entity": "TGF"},
    "anthropic": {"category": "AI Services", "entity": "TGF"},
    "manus ai": {"category": "AI Services", "entity": "TGF"},
    "manus": {"category": "AI Services", "entity": "TGF"},
    "godaddy": {"category": "Platform Fees", "entity": "TGF"},
    "horizon": {"category": "Design Services", "entity": "Horizon"},
    "adobe": {"category": "Design Software", "entity": "Horizon"},
    "figma": {"category": "Design Software", "entity": "Horizon"},
    "canva": {"category": "Design Software", "entity": "Horizon"},
}


def _call_llm(prompt: str, max_tokens: int = 1500) -> str | None:
    """Call Claude Haiku and return the text response."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping LLM call")
        return None
    model = os.getenv("CLAUDE_MODEL", _DEFAULT_MODEL)
    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return None


def _parse_json(text: str) -> dict | None:
    """Extract JSON from LLM response (handles markdown fences)."""
    if not text:
        return None
    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Email Classifier
# ---------------------------------------------------------------------------

def classify_email(subject: str, from_addr: str, body_text: str) -> dict:
    """Classify an email into a type using Claude Haiku.

    Returns: {"type": str, "confidence": int (0-100)}
    Types: godaddy_order, golf_genius_rsvp, chase_transaction_alert,
           venmo_payment, expense_receipt, action_required, unknown
    """
    # Fast-path: known patterns (no LLM needed)
    subject_lower = (subject or "").lower().strip()
    from_lower = (from_addr or "").lower()

    if subject_lower.startswith("new order"):
        return {"type": "godaddy_order", "confidence": 99}

    if "golfgenius.com" in from_lower or "golf genius" in from_lower:
        return {"type": "golf_genius_rsvp", "confidence": 99}

    if ("chase" in from_lower or "chase.com" in from_lower) and (
        "transaction" in subject_lower or "you made a" in subject_lower
        or "you sent" in subject_lower or "payment" in subject_lower
    ):
        return {"type": "chase_transaction_alert", "confidence": 95}

    if "venmo" in from_lower and (
        "you paid" in subject_lower or "you sent" in subject_lower
        or "paid you" in subject_lower or "completed" in subject_lower
    ):
        return {"type": "venmo_payment", "confidence": 95}

    # LLM classification for ambiguous emails
    body_preview = (body_text or "")[:1500]
    prompt = f"""Classify this email into exactly one of these types:
- godaddy_order: GoDaddy/MySimpleStore purchase notification
- golf_genius_rsvp: Golf Genius RSVP confirmation/cancellation
- chase_transaction_alert: Chase bank transaction alert or payment notification
- venmo_payment: Venmo payment sent or received
- expense_receipt: Receipt or invoice from a vendor (Make.com, Railway, Anthropic, etc.)
- action_required: Email that requires a response or action (contracts, inquiries, etc.)
- unknown: Marketing, spam, newsletters, or other non-actionable email

Email:
From: {from_addr}
Subject: {subject}
Body preview: {body_preview}

Return ONLY a JSON object: {{"type": "<type>", "confidence": <0-100>}}"""

    result = _parse_json(_call_llm(prompt, max_tokens=100))
    if result and "type" in result:
        return {
            "type": result["type"],
            "confidence": min(int(result.get("confidence", 50)), 100),
        }
    return {"type": "unknown", "confidence": 0}


# ---------------------------------------------------------------------------
# Chase Transaction Alert Parser
# ---------------------------------------------------------------------------

def parse_chase_alert(subject: str, from_addr: str, body_text: str,
                      merchant_context: dict | None = None) -> dict:
    """Extract transaction data from a Chase bank alert email."""
    body_preview = (body_text or "")[:2000]
    context_str = ""
    if merchant_context:
        context_str = f"\n\nPast categorization for this merchant:\n{json.dumps(merchant_context)}"

    prompt = f"""Extract transaction details from this Chase bank alert email.

From: {from_addr}
Subject: {subject}
Body: {body_preview}{context_str}

Return a JSON object with:
- merchant: string (clean merchant name, remove card numbers/locations codes)
- amount: number (positive, no $ sign)
- account_last4: string (last 4 digits of card)
- account_name: string (e.g. "Rapid Rewards Performance Visa", "Southwest Performance Business")
- transaction_date: string (YYYY-MM-DD)
- transaction_type: string ("expense" or "transfer" — use "transfer" for payments to credit cards, bank transfers, etc.)
- confidence: integer (0-100, how confident you are in the extraction)

Return ONLY the JSON object."""

    result = _parse_json(_call_llm(prompt))
    if not result:
        return {"confidence": 0, "error": "LLM extraction failed"}

    # Clean up
    result.setdefault("confidence", 50)
    result.setdefault("transaction_type", "expense")
    if "amount" in result:
        result["amount"] = abs(float(result["amount"]))
    return result


# ---------------------------------------------------------------------------
# Venmo Payment Parser
# ---------------------------------------------------------------------------

def parse_venmo_payment(subject: str, from_addr: str, body_text: str) -> dict:
    """Extract payment data from a Venmo notification email."""
    body_preview = (body_text or "")[:2000]

    prompt = f"""Extract payment details from this Venmo notification email.

From: {from_addr}
Subject: {subject}
Body: {body_preview}

Return a JSON object with:
- recipient_name: string (who was paid, or who paid you)
- amount: number (positive, no $ sign)
- memo: string (the payment note/description)
- sent_from_account: string (Venmo username if visible, e.g. "@tgf-payments")
- transaction_date: string (YYYY-MM-DD)
- transaction_id: string (Venmo transaction ID if visible)
- transaction_type: string ("payout" if paying someone, "received" if receiving)
- confidence: integer (0-100)

Return ONLY the JSON object."""

    result = _parse_json(_call_llm(prompt))
    if not result:
        return {"confidence": 0, "error": "LLM extraction failed"}

    result.setdefault("confidence", 50)
    result.setdefault("transaction_type", "payout")
    if "amount" in result:
        result["amount"] = abs(float(result["amount"]))
    return result


# ---------------------------------------------------------------------------
# Expense Receipt Parser
# ---------------------------------------------------------------------------

def parse_expense_receipt(subject: str, from_addr: str, body_text: str,
                          merchant_context: dict | None = None) -> dict:
    """Extract data from an expense receipt or invoice email."""
    body_preview = (body_text or "")[:2000]

    known_list = "\n".join(
        f"  - {k}: category={v['category']}, entity={v['entity']}"
        for k, v in _KNOWN_MERCHANTS.items()
    )
    context_str = ""
    if merchant_context:
        context_str = f"\n\nPast categorization for this merchant:\n{json.dumps(merchant_context)}"

    prompt = f"""Extract receipt/invoice details from this email.

Known merchants and their categories:
{known_list}{context_str}

From: {from_addr}
Subject: {subject}
Body: {body_preview}

Return a JSON object with:
- merchant: string (clean merchant name)
- amount: number (positive, no $ sign)
- transaction_date: string (YYYY-MM-DD)
- description: string (what was purchased/billed)
- account_last4: string (last 4 of payment card if visible, else null)
- category: string (from known list above, or best guess)
- entity: string ("TGF", "Personal", or "Horizon" — from known list or infer)
- confidence: integer (0-100)

Return ONLY the JSON object."""

    result = _parse_json(_call_llm(prompt))
    if not result:
        return {"confidence": 0, "error": "LLM extraction failed"}

    result.setdefault("confidence", 50)

    # Auto-categorize from known merchants if not already set
    merchant_lower = (result.get("merchant") or "").lower()
    for key, meta in _KNOWN_MERCHANTS.items():
        if key in merchant_lower:
            if not result.get("category"):
                result["category"] = meta["category"]
            if not result.get("entity"):
                result["entity"] = meta["entity"]
            break

    if "amount" in result:
        result["amount"] = abs(float(result["amount"]))
    return result


# ---------------------------------------------------------------------------
# Action Required Detector
# ---------------------------------------------------------------------------

def parse_action_required(subject: str, from_addr: str, body_text: str) -> dict:
    """Extract action item from an email that requires a response."""
    body_preview = (body_text or "")[:2000]

    prompt = f"""Analyze this email and extract what action is needed.

From: {from_addr}
Subject: {subject}
Body: {body_preview}

Return a JSON object with:
- subject: string (email subject, cleaned up)
- from_name: string (sender's name)
- from_email: string (sender's email)
- summary: string (1-2 sentence summary of what action is needed)
- urgency: string ("high", "medium", or "low")
- category: string ("contract", "payment", "member_inquiry", "course_correspondence", or "other")
- email_date: string (YYYY-MM-DD, from email date if visible)
- confidence: integer (0-100, how confident this actually requires action)

Return ONLY the JSON object."""

    result = _parse_json(_call_llm(prompt))
    if not result:
        return {"confidence": 0, "error": "LLM extraction failed"}

    result.setdefault("confidence", 50)
    result.setdefault("urgency", "medium")
    result.setdefault("category", "other")
    return result


# ---------------------------------------------------------------------------
# Event & Customer Matching (for Venmo)
# ---------------------------------------------------------------------------

def match_event_from_memo(memo: str, conn) -> str | None:
    """Try to match a Venmo memo to a TGF event name."""
    if not memo:
        return None
    memo_upper = memo.strip().upper()

    # Direct match against event names
    events = conn.execute("SELECT item_name FROM events").fetchall()
    for ev in events:
        if ev["item_name"].upper() in memo_upper:
            return ev["item_name"]

    # Try partial match (e.g. "MORRIS WILLIAMS" in event name)
    for ev in events:
        # Extract course name from event
        parts = ev["item_name"].split()
        if len(parts) >= 2:
            # Try matching last 2+ words of event name
            course_part = " ".join(parts[1:]).upper()  # Skip "s9.1" prefix
            if len(course_part) >= 4 and course_part in memo_upper:
                return ev["item_name"]

    return None


def match_customer_from_name(name: str, conn) -> int | None:
    """Try to match a name to a customer_id."""
    if not name:
        return None
    name_clean = name.strip()

    # Exact match
    row = conn.execute(
        """SELECT customer_id FROM customers
           WHERE (first_name || ' ' || last_name) = ? COLLATE NOCASE
              OR (last_name || ', ' || first_name) = ? COLLATE NOCASE
           LIMIT 1""",
        (name_clean, name_clean),
    ).fetchone()
    if row:
        return row["customer_id"]

    # Alias match
    row = conn.execute(
        """SELECT c.customer_id FROM customer_aliases ca
           JOIN customers c ON (c.first_name || ' ' || c.last_name) = ca.customer_name
           WHERE ca.alias_value = ? COLLATE NOCASE AND ca.alias_type = 'name'
           LIMIT 1""",
        (name_clean,),
    ).fetchone()
    if row:
        return row["customer_id"]

    return None


def match_event_from_customer(customer_id: int, conn) -> str | None:
    """Find most recent event for a customer from their registrations.

    Used as a fallback for Venmo payments when memo-based matching fails
    but the customer was identified by name.
    """
    if not customer_id:
        return None
    row = conn.execute(
        """SELECT i.item_name FROM items i
           JOIN events e ON e.item_name = i.item_name
           WHERE i.customer_id = ? AND i.transaction_status = 'active'
           ORDER BY e.event_date DESC LIMIT 1""",
        (customer_id,),
    ).fetchone()
    return row["item_name"] if row else None


# ---------------------------------------------------------------------------
# Merchant Learning Context
# ---------------------------------------------------------------------------

def get_merchant_context(merchant_name: str, conn) -> dict | None:
    """Return past categorization history for a merchant.

    Looks at both extraction_corrections and approved expense_transactions
    to build context for the AI prompt.
    """
    if not merchant_name:
        return None

    merchant_upper = merchant_name.strip().upper()

    # Check corrections first (highest signal)
    corrections = conn.execute(
        """SELECT field_corrected, corrected_value, COUNT(*) as times
           FROM extraction_corrections
           WHERE UPPER(merchant) = ?
           GROUP BY field_corrected, corrected_value
           ORDER BY times DESC""",
        (merchant_upper,),
    ).fetchall()

    if corrections:
        return {
            "merchant": merchant_name,
            "corrections": [dict(c) for c in corrections],
            "source": "corrections",
        }

    # Check approved transactions for this merchant
    approved = conn.execute(
        """SELECT category, entity, event_name, COUNT(*) as times
           FROM expense_transactions
           WHERE UPPER(merchant) LIKE ?
             AND review_status = 'approved'
           GROUP BY category, entity, event_name
           ORDER BY times DESC
           LIMIT 5""",
        (f"%{merchant_upper}%",),
    ).fetchall()

    if approved:
        return {
            "merchant": merchant_name,
            "past_categorizations": [dict(a) for a in approved],
            "source": "approved_history",
        }

    return None
