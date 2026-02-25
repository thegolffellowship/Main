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
  "items" array. However, ONLY create an item if there is a real product or \
  event line item with a name and price. Do NOT create phantom items from \
  section headers, form field labels, or repeated text. If the order has one \
  product line, return exactly one item.
- If a field is not present in the email, use null for that field.
- Dollar amounts should include the "$" sign (e.g. "$158.00").
- Dates should be in YYYY-MM-DD format.

FIELD-SPECIFIC GUIDANCE:
- "customer": The buyer / registrant name. Always use Title Case \
  (e.g. "Mike Jenkins", not "mike jenkins" or "MIKE JENKINS").
- "item_name": Use the event/product name exactly as shown (e.g. "Feb 22 - LaCANTERA"). \
  Exception: for membership items, normalise the item name to just "TGF MEMBERSHIP" \
  regardless of any city or tier suffix in the original (e.g. "TGF MEMBERSHIP CITY: \
  AUS | New Member..." → "TGF MEMBERSHIP").
- "event_date": The date of the golf event, NOT the order date. Parse it from \
  the item name when present (e.g. "Feb 22 - LaCANTERA" → "2026-02-22"). Use \
  the current year (2026) if only month and day are given.
- "city": The city where the EVENT takes place. Infer it from the course name \
  or event context if not explicitly stated. For MEMBERSHIP items, leave city \
  null — the membership city/chapter goes in the "chapter" field instead. \
  Common Texas courses: \
  La Cantera/TPC San Antonio/The Quarry = San Antonio, \
  Cowboys Golf Club/TPC Craig Ranch = Dallas, \
  Wolfdancer/Falconhead = Austin, \
  Moody Gardens = Galveston, etc.
- "chapter": The TGF chapter the member is signing up for. Only applies to \
  MEMBERSHIP items. Extract from "CITY: AUS" or "CITY: SA" or "CITY: DAL" etc. \
  Normalise to full city names: AUS/ATX → "Austin", SA/SAT → "San Antonio", \
  DAL/DFW → "Dallas", HOU → "Houston", GAL → "Galveston". \
  For event items, set chapter to null.
- "course": Use consistent canonical course names. Standard spellings: \
  "La Cantera", "TPC San Antonio", "The Quarry", "Cowboys Golf Club", \
  "TPC Craig Ranch", "Wolfdancer", "Falconhead", "Moody Gardens", \
  "Morris Williams", "Cedar Creek", "Kissing Tree", "Plum Creek", \
  "Landa Park", "Vaaler Creek", "Hancock Park". \
  Always use these exact spellings regardless of how the email formats them \
  (e.g. "LaCANTERA" or "LaCantera" → "La Cantera", \
  "MORRIS WILLIAMS" → "Morris Williams", "CEDAR CREEK" → "Cedar Creek").
- "customer_email": The buyer's email address if present in the order.
- "customer_phone": The buyer's phone number if present in the order.
- "member_status": Extract only the status label (e.g. "MEMBER" or "NON-MEMBER"), \
  not the price.
- "side_games": CRITICAL — The email field labelled "GOLF or COMPETE?" often \
  contains BOTH the event type AND the side-games selection in one string. \
  You MUST split them apart. Examples of what the raw email may show:
    "EVENT + NET Games Only | Add $30"  → golf_or_compete="GOLF", side_games="NET"
    "EVENT + GROSS Games Only | Add $30" → golf_or_compete="GOLF", side_games="GROSS"
    "EVENT + BOTH NET & GROSS Games"     → golf_or_compete="GOLF", side_games="BOTH"
    "EVENT Only - No Additional Games"   → golf_or_compete="GOLF", side_games="NONE"
    "COMPETE + NET Games Only | Add $30" → golf_or_compete="COMPETE", side_games="NET"
  The side_games value must be normalised to exactly one of: "NET", "GROSS", \
  "BOTH", or "NONE". If the text says "No Additional Games" that is "NONE". \
  If the text contains "BOTH NET & GROSS" that is "BOTH". \
  Do NOT put the full "EVENT + NET Games Only | Add $30" string into \
  golf_or_compete — that string contains side-games data.
- "golf_or_compete": Should contain ONLY the event-type portion: "GOLF" or \
  "COMPETE". If the raw value starts with "EVENT" treat that as "GOLF". \
  Never put side-games text here.
- "handicap": The numeric handicap value only (for event registrations).
- "has_handicap": For MEMBERSHIP items only — "YES" or "NO" from the \
  "Do you have a Current Handicap?" field. For events, set to null.
- "returning_or_new": For MEMBERSHIP items — "New" or "Returning" from \
  the "RETURNING or NEW?" field. Extract just the keyword.
- "net_points_race": For MEMBERSHIP items — "YES" or "NO" from \
  "Add NET Points Race?" field. Normalise to uppercase YES/NO.
- "gross_points_race": For MEMBERSHIP items — "YES" or "NO" from \
  "Add GROSS Points Race?" field. Normalise to uppercase YES/NO.
- "city_match_play": For MEMBERSHIP items — "YES" or "NO" from \
  "Add City MATCH PLAY?" field. Normalise to uppercase YES/NO.
- "date_of_birth": YYYY-MM-DD format. Often appears on membership orders.
- "transaction_fees": The processing/transaction fee amount charged on the \
  order (e.g. "$7.53"). This is an ORDER-level field, not per-item. \
  Look for "Transaction Fee", "Processing Fee", "Service Fee", etc.

Return this exact JSON structure:

{
  "merchant": "<store or company name>",
  "customer": "<customer / buyer name>",
  "customer_email": "<buyer email if present>",
  "customer_phone": "<buyer phone if present>",
  "order_id": "<order or confirmation number>",
  "order_date": "<YYYY-MM-DD>",
  "total_amount": "<total charged including fees, e.g. $222.53>",
  "transaction_fees": "<processing fee amount, e.g. $7.53>",
  "items": [
    {
      "item_name": "<product or event name>",
      "event_date": "<YYYY-MM-DD date of the event, parsed from item name>",
      "item_price": "<price for this item, e.g. $158.00>",
      "quantity": <integer, default 1>,
      "city": "<city where event takes place — null for memberships>",
      "chapter": "<TGF chapter — Austin, San Antonio, Dallas, etc. — null for events>",
      "course": "<golf course name if mentioned>",
      "handicap": "<numeric handicap value if mentioned>",
      "has_handicap": "<YES or NO — membership only, null for events>",
      "side_games": "<NET, GROSS, BOTH, or NONE — see rules above>",
      "tee_choice": "<tee choice if mentioned>",
      "member_status": "<MEMBER or NON-MEMBER>",
      "golf_or_compete": "<GOLF or COMPETE only — see rules above>",
      "post_game": "<post-game fellowship selection if mentioned>",
      "returning_or_new": "<New or Returning — membership only>",
      "shirt_size": "<shirt size if mentioned>",
      "guest_name": "<guest name if mentioned>",
      "date_of_birth": "<YYYY-MM-DD date of birth if mentioned>",
      "net_points_race": "<YES or NO — membership only>",
      "gross_points_race": "<YES or NO — membership only>",
      "city_match_play": "<YES or NO — membership only>"
    }
  ]
}

Here is the email text to parse:

"""


_SIDE_GAMES_PATTERNS = [
    (re.compile(r"BOTH\s*NET\s*[&+]\s*GROSS", re.IGNORECASE), "BOTH"),
    (re.compile(r"NET\s*[&+]\s*GROSS", re.IGNORECASE), "BOTH"),
    (re.compile(r"\bNET\b.*Games?\b", re.IGNORECASE), "NET"),
    (re.compile(r"\bGROSS\b.*Games?\b", re.IGNORECASE), "GROSS"),
    (re.compile(r"\bBOTH\b", re.IGNORECASE), "BOTH"),
    (re.compile(r"No\s+Additional\s+Games", re.IGNORECASE), "NONE"),
    (re.compile(r"EVENT\s+Only", re.IGNORECASE), "NONE"),
]

_SIDE_GAMES_KEYWORDS = re.compile(
    r"NET Games|GROSS Games|BOTH NET|No Additional Games|EVENT Only|EVENT \+",
    re.IGNORECASE,
)


def _normalize_side_games(value: str | None) -> str | None:
    """Normalize a side-games value to NET / GROSS / BOTH / NONE."""
    if not value:
        return value
    upper = value.strip().upper()
    # Already clean
    if upper in ("NET", "GROSS", "BOTH", "NONE"):
        return upper
    # Try pattern matching on the raw string
    for pattern, label in _SIDE_GAMES_PATTERNS:
        if pattern.search(value):
            return label
    return value  # leave as-is if we can't parse it


_TEE_PATTERNS = [
    (re.compile(r"\bforward\b|\bfront\b", re.IGNORECASE), "Forward"),
    (re.compile(r"\b65\s*\+", re.IGNORECASE), "65+"),
    (re.compile(r"\b50\s*[-–]\s*64\b", re.IGNORECASE), "50-64"),
    (re.compile(r"(?:^|(?<=\s))<\s*50\b|\bunder\s*50\b", re.IGNORECASE), "<50"),
]


def _normalize_tee_choice(value: str | None) -> str | None:
    """Normalize a tee-choice value to <50 / 50-64 / 65+ / Forward."""
    if not value:
        return value
    cleaned = value.strip()
    # Already canonical
    if cleaned in ("<50", "50-64", "65+", "Forward"):
        return cleaned
    for pattern, label in _TEE_PATTERNS:
        if pattern.search(cleaned):
            return label
    return cleaned  # leave as-is if we can't parse it


def _fixup_side_games_field(item: dict) -> dict:
    """
    Detect when side-games data has landed in golf_or_compete and move it.

    Also normalises both fields to their canonical values.
    """
    goc = item.get("golf_or_compete") or ""
    sg = item.get("side_games") or ""

    # If golf_or_compete contains side-games text, split it out
    if _SIDE_GAMES_KEYWORDS.search(goc):
        # Extract side games
        if not sg:
            sg = _normalize_side_games(goc)
        # Determine the event type from the prefix
        if re.match(r"(?:COMPETE|COMPETITION)", goc, re.IGNORECASE):
            goc = "COMPETE"
        else:
            goc = "GOLF"
        item["golf_or_compete"] = goc
        item["side_games"] = sg

    # Always normalise side_games if it has a value
    if item.get("side_games"):
        item["side_games"] = _normalize_side_games(item["side_games"])

    return item


# ---------------------------------------------------------------------------
# Customer name normalisation
# ---------------------------------------------------------------------------

# Small words that should stay lowercase in title case (unless first/last)
_TITLE_CASE_SMALL = {"and", "or", "the", "of", "in", "at", "to", "for", "a", "an"}

# Common name prefixes that need special casing
_NAME_PREFIX_MAP = {
    "mc": lambda rest: "Mc" + rest.capitalize(),
    "mac": lambda rest: "Mac" + rest.capitalize(),
    "o'": lambda rest: "O'" + rest.capitalize(),
}


def _normalize_customer_name(name: str | None) -> str | None:
    """Normalise customer name to Title Case with special-case handling."""
    if not name:
        return name
    parts = name.strip().split()
    result = []
    for i, part in enumerate(parts):
        lower = part.lower()
        # Handle Mc/Mac/O' prefixes
        handled = False
        for prefix, formatter in _NAME_PREFIX_MAP.items():
            if lower.startswith(prefix) and len(lower) > len(prefix):
                result.append(formatter(lower[len(prefix):]))
                handled = True
                break
        if not handled:
            result.append(part.capitalize())
    return " ".join(result) if result else name


# ---------------------------------------------------------------------------
# Course name canonicalisation
# ---------------------------------------------------------------------------

_COURSE_CANONICAL = {
    "lacantera": "La Cantera",
    "la cantera": "La Cantera",
    "lacantera golf": "La Cantera",
    "tpc san antonio": "TPC San Antonio",
    "the quarry": "The Quarry",
    "cowboys golf club": "Cowboys Golf Club",
    "tpc craig ranch": "TPC Craig Ranch",
    "wolfdancer": "Wolfdancer",
    "falconhead": "Falconhead",
    "moody gardens": "Moody Gardens",
    "morris williams": "Morris Williams",
    "cedar creek": "Cedar Creek",
    "kissing tree": "Kissing Tree",
    "plum creek": "Plum Creek",
    "landa park": "Landa Park",
    "vaaler creek": "Vaaler Creek",
    "hancock park": "Hancock Park",
}


def _normalize_course_name(course: str | None) -> str | None:
    """Map course name to its canonical spelling."""
    if not course:
        return course
    lookup = course.strip().lower()
    # Direct match
    if lookup in _COURSE_CANONICAL:
        return _COURSE_CANONICAL[lookup]
    # Substring match (e.g. "LaCANTERA Resort" still matches "lacantera")
    for key, canonical in _COURSE_CANONICAL.items():
        if key in lookup:
            return canonical
    # No match — return title-cased original
    return course.strip().title()


# ---------------------------------------------------------------------------
# Item name normalisation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Chapter normalisation (membership city/chapter abbreviations)
# ---------------------------------------------------------------------------

_CHAPTER_MAP = {
    "aus": "Austin",
    "atx": "Austin",
    "austin": "Austin",
    "sa": "San Antonio",
    "sat": "San Antonio",
    "san antonio": "San Antonio",
    "dal": "Dallas",
    "dfw": "Dallas",
    "dallas": "Dallas",
    "hou": "Houston",
    "houston": "Houston",
    "gal": "Galveston",
    "galveston": "Galveston",
}


def _normalize_chapter(chapter: str | None) -> str | None:
    """Normalise chapter abbreviations to full city names."""
    if not chapter:
        return chapter
    lookup = chapter.strip().lower()
    return _CHAPTER_MAP.get(lookup, chapter.strip().title())


_MEMBERSHIP_RE = re.compile(r"^TGF\s+MEMBERSHIP\b.*", re.IGNORECASE)


def _normalize_item_name(name: str | None) -> str | None:
    """Normalise item names — e.g. strip city/tier suffixes from memberships."""
    if not name:
        return name
    if _MEMBERSHIP_RE.match(name.strip()):
        return "TGF MEMBERSHIP"
    return name


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

    # Filter out phantom items — must have at least an item_name
    items = [it for it in items if it.get("item_name")]

    if not items:
        return []

    email_uid = email_data.get("uid", "")
    subject = email_data.get("subject", "")
    from_addr = email_data.get("from", "")

    # Normalise order-level customer name once
    customer = _normalize_customer_name(parsed.get("customer"))

    rows = []
    for idx, item in enumerate(items):
        # Fix side-games / golf_or_compete misplacement before storing
        item = _fixup_side_games_field(item)

        rows.append({
            "email_uid": email_uid,
            "item_index": idx,
            "merchant": parsed.get("merchant") or "Unknown",
            "customer": customer,
            "customer_email": parsed.get("customer_email"),
            "customer_phone": parsed.get("customer_phone"),
            "order_id": parsed.get("order_id"),
            "order_date": parsed.get("order_date") or "",
            "total_amount": parsed.get("total_amount") or "",
            "transaction_fees": parsed.get("transaction_fees"),
            "item_name": _normalize_item_name(item.get("item_name")) or "",
            "event_date": item.get("event_date"),
            "item_price": item.get("item_price") or "",
            "quantity": item.get("quantity") or 1,
            "city": item.get("city"),
            "chapter": _normalize_chapter(item.get("chapter")),
            "course": _normalize_course_name(item.get("course")),
            "handicap": item.get("handicap"),
            "has_handicap": item.get("has_handicap"),
            "side_games": item.get("side_games"),
            "tee_choice": _normalize_tee_choice(item.get("tee_choice")),
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
