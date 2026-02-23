"""
Transaction email parser — uses Claude AI to extract structured purchase data
from email text/HTML.

Returns one row per line item so that multi-item orders become multiple records,
each with dedicated columns for filtering and sorting (item_name, city,
handicap, side_games, etc.).
"""

import html
import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(raw_html: str) -> str:
    """Remove HTML tags and decode entities to plain text."""
    text = re.sub(r"<style[^>]*>.*?</style>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# AI extraction prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
You are a transaction email parser for The Golf Fellowship (TGF). Given the \
raw text of a transaction or order confirmation email, extract structured data \
and return it as JSON.

IMPORTANT RULES:
- Return ONLY valid JSON — no markdown, no explanation, no extra text.
- The top-level value must be a JSON object with the keys described below.
- An order may contain MULTIPLE items. Return each item separately in the \
  "items" array.
- If a field is not present in the email, use null for that field.
- Dollar amounts should include the "$" sign (e.g. "$158.00").
- Dates should be in YYYY-MM-DD format.

FIELD-SPECIFIC GUIDANCE:
- "item_name": Use the event/product name exactly as shown (e.g. "Feb 22 - LaCANTERA").
- "event_date": The date of the golf event, NOT the order date. Parse it from \
  the item name when present (e.g. "Feb 22 - LaCANTERA" → "2026-02-22"). Use \
  the current year (2026) if only month and day are given.
- "city": The city where the event takes place. Infer it from the course name \
  or event context if not explicitly stated. Common Texas courses: \
  LaCantera/TPC San Antonio/The Quarry = San Antonio, \
  Cowboys Golf Club/TPC Craig Ranch = Dallas, \
  Wolfdancer/Falconhead = Austin, \
  Moody Gardens = Galveston, etc.
- "customer_email": The buyer's email address if present in the order.
- "customer_phone": The buyer's phone number if present in the order.
- "member_status": Extract only the status label (e.g. "MEMBER" or "NON-MEMBER"), \
  not the price.
- "side_games": Combine all side-game selections into a comma-separated string.
- "handicap": The numeric handicap value only.

Return this exact JSON structure:

{
  "merchant": "<store or company name>",
  "customer": "<customer / buyer name>",
  "customer_email": "<buyer email if present>",
  "customer_phone": "<buyer phone if present>",
  "order_id": "<order or confirmation number>",
  "order_date": "<YYYY-MM-DD>",
  "total_amount": "<total charged including fees, e.g. $163.53>",
  "items": [
    {
      "item_name": "<product or event name>",
      "event_date": "<YYYY-MM-DD date of the event, parsed from item name>",
      "item_price": "<price for this item, e.g. $158.00>",
      "quantity": <integer, default 1>,
      "city": "<city where event takes place — infer from course if needed>",
      "course": "<golf course name if mentioned>",
      "handicap": "<numeric handicap value if mentioned>",
      "side_games": "<all side game selections, comma-separated>",
      "tee_choice": "<tee choice if mentioned>",
      "member_status": "<MEMBER or NON-MEMBER>",
      "golf_or_compete": "<event type selection if mentioned>",
      "post_game": "<post-game fellowship selection if mentioned>",
      "returning_or_new": "<returning or new member if mentioned>",
      "shirt_size": "<shirt size if mentioned>",
      "guest_name": "<guest name if mentioned>",
      "date_of_birth": "<date of birth if mentioned>",
      "net_points_race": "<net points race selection if mentioned>",
      "gross_points_race": "<gross points race selection if mentioned>",
      "city_match_play": "<city match play selection if mentioned>"
    }
  ]
}

Here is the email text to parse:

"""


def _call_ai(email_text: str) -> dict | None:
    """Send email text to Claude and return the parsed JSON dict."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set — cannot parse email with AI")
        return None

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT + email_text,
                }
            ],
        )
        raw = message.content[0].text.strip()

        # Strip markdown fences if the model wrapped the JSON
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        return json.loads(raw)

    except json.JSONDecodeError:
        logger.exception("AI returned invalid JSON")
        return None
    except anthropic.BadRequestError as e:
        # Re-raise billing / auth errors so the caller can stop the batch
        logger.error("Anthropic API fatal error: %s", e.message)
        raise
    except anthropic.AuthenticationError as e:
        logger.error("Anthropic API auth error: %s", e.message)
        raise
    except anthropic.APIError:
        logger.exception("Anthropic API call failed")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_email(email_data: dict) -> list[dict]:
    """
    Parse a single email dict (from fetcher) using Claude AI.

    Returns a *list* of flat dicts — one per line item — ready for DB insert.
    Returns an empty list if parsing fails or no items are found.
    """
    body = email_data.get("text", "")
    if not body and email_data.get("html"):
        body = _strip_html(email_data["html"])
    if not body:
        return []

    parsed = _call_ai(body)
    if not parsed:
        return []

    items = parsed.get("items") or []
    if not items:
        return []

    email_uid = email_data.get("uid", "")
    subject = email_data.get("subject", "")
    from_addr = email_data.get("from", "")

    rows = []
    for idx, item in enumerate(items):
        rows.append({
            "email_uid": email_uid,
            "item_index": idx,
            "merchant": parsed.get("merchant") or "Unknown",
            "customer": parsed.get("customer"),
            "customer_email": parsed.get("customer_email"),
            "customer_phone": parsed.get("customer_phone"),
            "order_id": parsed.get("order_id"),
            "order_date": parsed.get("order_date") or "",
            "total_amount": parsed.get("total_amount") or "",
            "item_name": item.get("item_name") or "",
            "event_date": item.get("event_date"),
            "item_price": item.get("item_price") or "",
            "quantity": item.get("quantity") or 1,
            "city": item.get("city"),
            "course": item.get("course"),
            "handicap": item.get("handicap"),
            "side_games": item.get("side_games"),
            "tee_choice": item.get("tee_choice"),
            "member_status": item.get("member_status"),
            "golf_or_compete": item.get("golf_or_compete"),
            "post_game": item.get("post_game"),
            "returning_or_new": item.get("returning_or_new"),
            "shirt_size": item.get("shirt_size"),
            "guest_name": item.get("guest_name"),
            "date_of_birth": item.get("date_of_birth"),
            "net_points_race": item.get("net_points_race"),
            "gross_points_race": item.get("gross_points_race"),
            "city_match_play": item.get("city_match_play"),
            "subject": subject,
            "from_addr": from_addr,
        })

    return rows


def parse_emails(email_list: list[dict]) -> list[dict]:
    """Parse a batch of emails and return flat item rows for DB storage."""
    all_rows = []
    for email_data in email_list:
        try:
            rows = parse_email(email_data)
            all_rows.extend(rows)
        except (anthropic.BadRequestError, anthropic.AuthenticationError) as e:
            logger.error(
                "Stopping batch — Anthropic API returned a fatal error: %s", e.message,
            )
            break
        except Exception:
            logger.exception("Failed to parse email uid=%s", email_data.get("uid"))
    logger.info("Parsed %d item rows from %d emails", len(all_rows), len(email_list))
    return all_rows
