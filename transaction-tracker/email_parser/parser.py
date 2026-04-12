"""
Transaction email parser — uses Claude AI to extract structured purchase data
from email text/HTML.

Returns one row per line item so that multi-item orders become multiple records,
each with dedicated columns for filtering and sorting (item_name, chapter,
handicap, side_games, etc.).
"""

import html
import json
import logging
import os
import re
from html.parser import HTMLParser

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Safe HTML-to-text converter — immune to ReDoS on malformed input."""

    _SKIP_TAGS = frozenset({"style", "script"})

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces)


def _strip_html(raw_html: str) -> str:
    """Remove HTML tags and decode entities to plain text."""
    extractor = _HTMLTextExtractor()
    extractor.feed(raw_html)
    text = extractor.get_text()
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
  event line item with a distinct name in the Order Summary. Do NOT create \
  phantom items from section headers, form field labels, or repeated text. \
  If the order has one product line, return exactly one item. \
  IMPORTANT: Items with a $0.00 price ARE valid line items and MUST be \
  included (e.g. "SEASON CONTESTS" at $0.00 is a real item). Never merge \
  or skip a $0 item — each named line item in the Order Summary gets its \
  own entry in the "items" array.
- If a field is not present in the email, use null for that field.
- Dollar amounts should include the "$" sign (e.g. "$158.00").
- Dates should be in YYYY-MM-DD format.

FIELD-SPECIFIC GUIDANCE:
- "customer": The buyer / registrant name — the person who placed and paid for \
  the order. This is the name from "New order from:", the Shipping Address, or \
  the email header. Do NOT use the "Playing Partner Request" name here — that \
  is a DIFFERENT person and goes in "partner_request". Always use Title Case \
  (e.g. "Mike Jenkins", not "mike jenkins" or "MIKE JENKINS").
- "item_name": Use the FULL event/product name exactly as shown in the Order Summary, \
  including any series/event code prefix AND the venue/course name. \
  CRITICAL: Many events have a series code like "a9.1", "s18.2", "h5.3", "d3.1" \
  (letter + number + dot + number) at the beginning — you MUST include this code \
  as part of the item_name. For example: \
    "a9.1 STAR RANCH" → item_name = "a9.1 STAR RANCH" (NOT just "Star Ranch") \
    "s18.2 La CANTERA" → item_name = "s18.2 La CANTERA" (NOT just "La Cantera") \
    "Austin Kickoff SHADOWGLEN" → item_name = "Austin Kickoff SHADOWGLEN" \
    "Feb 22 - LaCANTERA" → item_name = "Feb 22 - LaCANTERA" \
  NEVER use just a course name (e.g. "Star Ranch", "La Cantera", "ShadowGlen") \
  as the item_name — that is always wrong. The item_name must include the full \
  event identifier as shown in the Order Summary. Look carefully at the Order \
  Summary section for the complete product/event title. \
  Exception: for membership items, normalise the item name to just "TGF MEMBERSHIP" \
  regardless of any city or tier suffix in the original (e.g. "TGF MEMBERSHIP CITY: \
  AUS | New Member..." → "TGF MEMBERSHIP"). \
  For standalone season contest purchases, use "SEASON CONTESTS" as the item name.
- "chapter": The TGF chapter for the item. ONLY four valid values: \
  "San Antonio", "Austin", "Houston", "DFW". \
  For EVENT items, infer from the course name (e.g. La Cantera/TPC San Antonio/The Quarry \
  = "San Antonio", Cowboys Golf Club/TPC Craig Ranch = "DFW", \
  Wolfdancer/Falconhead/Star Ranch = "Austin"). \
  For MEMBERSHIP items, extract from "CITY: AUS" or "CITY: SA" etc. \
  Normalise: AUS/ATX → "Austin", SA/SAT → "San Antonio", DAL/DFW → "DFW", HOU → "Houston". \
  IMPORTANT: Do NOT use the customer's shipping/billing address city as chapter. \
  The chapter must be inferred from the golf course or event location, not the customer address.
- "course": Use consistent canonical course names. Standard spellings: \
  "La Cantera", "TPC San Antonio", "The Quarry", "Cowboys Golf Club", \
  "TPC Craig Ranch", "Wolfdancer", "Falconhead", "Moody Gardens", \
  "Morris Williams", "Cedar Creek", "Kissing Tree", "Plum Creek", \
  "Landa Park", "Vaaler Creek", "Hancock Park", "ShadowGlen", "Star Ranch". \
  Always use these exact spellings regardless of how the email formats them \
  (e.g. "LaCANTERA" or "LaCantera" → "La Cantera", \
  "MORRIS WILLIAMS" → "Morris Williams", "CEDAR CREEK" → "Cedar Creek", \
  "SHADOWGLEN" → "ShadowGlen", "STAR RANCH" → "Star Ranch").
- "customer_email": The buyer's email address if present in the order.
- "customer_phone": The buyer's phone number if present in the order.
- "user_status": The player's status. Extract the label from "MEMBER STATUS:" \
  field. Common values: "MEMBER", "1st TIMER", "GUEST", "MANAGER". \
  Preserve as shown (e.g. "1st TIMER", "MEMBER"). Do NOT include the price.
- "side_games": CRITICAL — The email field labelled "GOLF or COMPETE?" contains \
  side-games information. Extract ONLY the side-games portion. Examples:
    "EVENT + NET Games Only | Add $30"   → side_games="NET"
    "EVENT + GROSS Games Only | Add $30" → side_games="GROSS"
    "EVENT + BOTH NET & GROSS Games"     → side_games="BOTH"
    "EVENT Only - No Additional Games"   → side_games="NONE"
    "EVENT Only (Inc. Team Game)"        → side_games="NONE"
    "1st TIMER - EVENT + GROSS Games"    → side_games="GROSS"
    "1st TIMER - EVENT + NET Games"      → side_games="NET"
  The side_games value must be normalised to exactly one of: "NET", "GROSS", \
  "BOTH", or "NONE". If the text says "No Additional Games" that is "NONE". \
  If the text says "EVENT Only" that is "NONE". \
  If the text contains "BOTH NET & GROSS" that is "BOTH".
- "handicap": The numeric handicap value only (for event registrations).
- "has_handicap": For MEMBERSHIP items only — "YES" or "NO" from the \
  "Do you have a Current Handicap?" field. For events, set to null.
- "returning_or_new": For MEMBERSHIP items — "New" or "Returning" from \
  the "RETURNING or NEW?" field. Extract just the keyword.
- "net_points_race": "YES" or "NO" from "Add NET Points Race?" field. \
  Can appear on MEMBERSHIP items or SEASON CONTESTS items. Normalise to YES/NO.
- "gross_points_race": "YES" or "NO" from "Add GROSS Points Race?" field. \
  Can appear on MEMBERSHIP items or SEASON CONTESTS items. Normalise to YES/NO.
- "city_match_play": "YES" or "NO" from "Add City MATCH PLAY?" field. \
  Can appear on MEMBERSHIP items or SEASON CONTESTS items. Normalise to YES/NO.
- "partner_request": If the player requested a specific playing partner, \
  extract the partner's name. Look for fields like "Playing Partner Request", \
  "Partner Request", "Who would you like to play with?", etc.
- "fellowship": Whether the player plans to attend the post-game \
  fellowship / gathering. Look for any field containing the word "Fellowship" \
  (e.g. "Fellowship After?", "Post-Game Fellowship", "POST-GAME FELLOWSHIP at \
  Course?", "Staying for fellowship?"). Normalise to "YES" or "NO".
- "guest_name": When an item has user_status "GUEST", extract the actual \
  guest player's name. Look for it in the "Special Instructions" section \
  (e.g. "Guest: Tanner Chalfant 6.2 GHIN: 12697695" → "Tanner Chalfant"), \
  or in the partner_request field of the MEMBER item in the same order \
  (e.g. "Tanner Chalfant guest"). Use Title Case. Strip any handicap, \
  GHIN numbers, or annotations — just the name.
- "notes": Any freeform notes, comments, special requests, or special \
  instructions from the player. Look for "Notes", "Comments", \
  "Special Requests", "Special Instructions", "Additional Info", etc. \
  If BOTH "Notes" and "Special Instructions" fields exist, combine them \
  with " - " between them. Preserve the text as-is.
- "date_of_birth": YYYY-MM-DD format. Often appears on membership orders.
- "transaction_fees": The processing/transaction fee amount charged on the \
  order (e.g. "$4.90"). This is an ORDER-level field, not per-item. \
  Look for "Transaction Fees", "Transaction Fee", "Processing Fee", \
  "Service Fee", etc. The email often shows it as "Transaction Fees 3.5%: $4.90" — \
  extract just the dollar amount (e.g. "$4.90").
- "coupon_code": If the order includes a coupon or discount line, extract the \
  coupon code. GoDaddy emails typically show it as "Coupon (tgf-referral-luke): -$25.00" — \
  extract just the code inside the parentheses (e.g. "tgf-referral-luke"). \
  If no coupon line exists, use null. This is an ORDER-level field, not per-item.
- "coupon_amount": The dollar amount of the coupon discount, stored as a POSITIVE \
  value with "$" sign (e.g. "$25.00"). The email shows it as a negative like "-$25.00" \
  but store the absolute value. If no coupon line exists, use null. \
  This is an ORDER-level field, not per-item.
- "tee_choice": The tee selection. Normalise to one of: "<50", "50-64", \
  "65+", or "Forward". If the email says "Front" tees, normalise to "Forward". \
  Discard any yardage information (e.g. "6300-6800y").
- "holes": For events that offer 9 or 18 holes, extract just the number: \
  "9" or "18". Look for "9 or 18 HOLES?" field. If not present, use null.
- "item_price": The PER-UNIT price ACTUALLY CHARGED for this item. \
  CRITICAL: Do NOT use the dollar amount from the "MEMBER STATUS" line \
  (e.g. "MEMBER = $88") — that is only the base membership rate and does NOT \
  include side game add-ons. Instead, determine item_price from these sources \
  in priority order: \
  1. The Subtotal line (e.g. "Subtotal: $148.00") — this is the item price before fees \
  2. The dollar amount next to the SKU code (e.g. "SKU: 26-s18-4-M-B $148.00") \
  3. Order Total minus Transaction Fees as a fallback \
  The "MEMBER = $88" line should ONLY be used for user_status extraction, never for price. \
  If the email shows "$57.00 x 2  $114.00", the item_price is "$57.00" \
  (the single-unit price), NOT the extended total.
- "quantity": The number of units purchased for this line item. Default 1. \
  Look for patterns like "$57.00 x 2", "× 2", "qty: 2", or a multiplier \
  next to the price. If the email shows "$57.00 x 2  $114.00", quantity is 2.
- "address": The street address from the Shipping Address section. The email \
  typically shows "Shipping Address" followed by the customer name in ALL CAPS, \
  then the street, city, state, and zip. For example: \
  "Shipping Address JOHN DOE 123 MAIN ST AUSTIN TX 78701" → \
  address="123 Main St", address_city="Austin", address_state="TX", \
  address_zip="78701". Extract the street portion only (not the name). \
  Use Title Case for the street address.
- "address2": Second address line (apt, suite, unit, etc.) if present.
- "address_city": City from the Shipping Address. Use Title Case.
- "address_state": State abbreviation from the Shipping Address (e.g. "TX").
- "address_zip": ZIP code from the Shipping Address (e.g. "78701").

Return this exact JSON structure:

{
  "merchant": "<store or company name>",
  "customer": "<customer / buyer name>",
  "customer_email": "<buyer email if present>",
  "customer_phone": "<buyer phone if present>",
  "order_id": "<order or confirmation number>",
  "order_date": "<YYYY-MM-DD>",
  "order_time": "<HH:MM:SS in 24-hour format, from the order/transaction timestamp if present, else null>",
  "total_amount": "<total charged including fees, e.g. $222.53>",
  "transaction_fees": "<processing fee amount, e.g. $7.53>",
  "coupon_code": "<coupon code if present, e.g. tgf-referral-luke, else null>",
  "coupon_amount": "<coupon discount as positive dollar amount, e.g. $25.00, else null>",
  "address": "<street address>",
  "address2": "<apt/suite/unit if present>",
  "address_city": "<city>",
  "address_state": "<state abbreviation>",
  "address_zip": "<zip code>",
  "items": [
    {
      "item_name": "<product or event name>",
      "item_price": "<PER-UNIT price, e.g. $57.00>",
      "quantity": "<integer — number of units purchased, default 1>",
      "chapter": "<city/chapter — Austin, San Antonio, Dallas, etc.>",
      "course": "<golf course name if mentioned>",
      "handicap": "<numeric handicap value if mentioned>",
      "has_handicap": "<YES or NO — membership only, null for events>",
      "side_games": "<NET, GROSS, BOTH, or NONE — see rules above>",
      "tee_choice": "<<50, 50-64, 65+, or Forward>",
      "user_status": "<MEMBER, 1st TIMER, GUEST, MANAGER, etc.>",
      "post_game": "<post-game fellowship selection if mentioned>",
      "partner_request": "<requested playing partner name if mentioned>",
      "fellowship": "<YES or NO — attending post-game fellowship>",
      "notes": "<freeform notes, comments, special requests, or special instructions>",
      "returning_or_new": "<New or Returning — membership only>",
      "shirt_size": "<shirt size if mentioned>",
      "guest_name": "<guest player name — see guidance below>",
      "date_of_birth": "<YYYY-MM-DD date of birth if mentioned>",
      "net_points_race": "<YES or NO — membership or season contests>",
      "gross_points_race": "<YES or NO — membership or season contests>",
      "city_match_play": "<YES or NO — membership or season contests>",
      "holes": "<9 or 18 if applicable, else null>"
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

# Roman numerals and suffixes that should stay uppercase
_UPPERCASE_SUFFIXES = {"ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
                       "jr", "sr"}


def _normalize_customer_name(name: str | None) -> str | None:
    """Normalise customer name to Title Case with special-case handling."""
    if not name:
        return name
    parts = name.strip().split()
    result = []
    for i, part in enumerate(parts):
        lower = part.lower().rstrip(".")
        # Roman numerals and suffixes → uppercase
        if lower in _UPPERCASE_SUFFIXES:
            result.append(part.upper().rstrip("."))
            continue
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
    "shadowglen": "ShadowGlen",
    "shadow glen": "ShadowGlen",
    "star ranch": "Star Ranch",
    "teravista": "Teravista",
    "canyon springs": "Canyon Springs",
    "silverhorn": "Silverhorn",
    "willow springs": "Willow Springs",
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
    "dal": "DFW",
    "dfw": "DFW",
    "dallas": "DFW",
    "fort worth": "DFW",
    "hou": "Houston",
    "houston": "Houston",
}

# Only these four chapters are valid
_VALID_CHAPTERS = {"San Antonio", "Austin", "Houston", "DFW"}


def _normalize_chapter(chapter: str | None) -> str | None:
    """Normalise chapter to one of the four valid TGF chapters.

    Returns None if the chapter cannot be mapped to a valid value.
    This prevents cities from shipping addresses (e.g. Elgin) from
    being stored as chapter.
    """
    if not chapter:
        return chapter
    lookup = chapter.strip().lower()
    mapped = _CHAPTER_MAP.get(lookup)
    if mapped:
        return mapped
    # Check if it's already a valid chapter name (case-insensitive)
    for valid in _VALID_CHAPTERS:
        if lookup == valid.lower():
            return valid
    # Not a valid chapter — discard it
    return None


# Course names that should NEVER be the entire item_name — they indicate
# the AI missed the event identifier / series code prefix.
_COURSE_ONLY_NAMES = {v.lower() for v in _COURSE_CANONICAL.values()}
# Also add common raw variants
_COURSE_ONLY_NAMES |= set(_COURSE_CANONICAL.keys())


_MEMBERSHIP_RE = re.compile(r"^TGF\s+MEMBERSHIP\b.*", re.IGNORECASE)


def _normalize_item_name(name: str | None) -> str | None:
    """Normalise item names — e.g. strip city/tier suffixes from memberships."""
    if not name:
        return name
    if _MEMBERSHIP_RE.match(name.strip()):
        return "TGF MEMBERSHIP"
    return name


_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_ACTIVE_MODEL = os.getenv("CLAUDE_MODEL", _DEFAULT_MODEL)
logger.info("Claude parser model: %s", _ACTIVE_MODEL)


def _call_ai(email_text: str) -> dict | None:
    """Send email text to Claude and return the parsed JSON dict."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set — cannot parse email with AI")
        return None

    model = os.getenv("CLAUDE_MODEL", _DEFAULT_MODEL)

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT + email_text,
                }
            ],
        )
    except anthropic.BadRequestError as e:
        logger.error("Anthropic API fatal error: %s", e.message)
        raise
    except anthropic.AuthenticationError as e:
        logger.error("Anthropic API auth error: %s", e.message)
        raise
    except anthropic.APIError:
        logger.exception("Anthropic API call failed")
        return None

    raw = message.content[0].text.strip()

    # Strip markdown fences if the model wrapped the JSON
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("AI returned invalid JSON: %.500s", raw)
        return None


# ---------------------------------------------------------------------------
# Quantity expansion — split qty>1 items into separate rows
# ---------------------------------------------------------------------------


def _expand_quantity_rows(rows: list[dict]) -> list[dict]:
    """Expand rows with quantity > 1 into individual rows.

    For a qty=2 item purchased by "Victor Arias" with partner_request
    "Victor Arias III":
      - Row 0: Victor Arias (buyer), qty=1
      - Row 1: Victor Arias III (partner), qty=1

    For qty=3 with one partner name:
      - Row 0: buyer, Row 1: named partner, Row 2: "Guest of <buyer>"

    If no partner name is available, extra rows use "Guest of <buyer>".
    """
    expanded = []
    for row in rows:
        qty = row.get("quantity") or 1
        if qty <= 1:
            expanded.append(row)
            continue

        buyer = row.get("customer") or "Unknown"
        partner_name = (row.get("partner_request") or "").strip()

        # Buyer's own row — always first, quantity set to 1
        buyer_row = dict(row, quantity=1)
        expanded.append(buyer_row)

        # Additional rows for qty - 1 extra units
        for extra_i in range(1, qty):
            extra_row = dict(row, quantity=1)
            if extra_i == 1 and partner_name:
                # First extra unit goes to the named partner
                extra_row["customer"] = _normalize_customer_name(partner_name)
                extra_row["partner_request"] = None
                extra_row["notes"] = f"Purchased by {buyer}"
            else:
                # No partner name available — use placeholder
                extra_row["customer"] = f"Guest of {buyer}"
                extra_row["notes"] = f"Purchased by {buyer}"
            # Clear buyer-specific fields for the partner
            extra_row["customer_email"] = None
            extra_row["customer_phone"] = None
            extra_row["address"] = None
            extra_row["address2"] = None
            extra_row["city"] = None
            extra_row["state"] = None
            extra_row["zip"] = None
            expanded.append(extra_row)

    # Re-assign sequential item_index values
    for i, r in enumerate(expanded):
        r["item_index"] = i

    return expanded


def _promote_guest_customers(rows: list[dict]) -> list[dict]:
    """Swap customer on GUEST items in multi-item orders to the actual guest.

    When a buyer purchases two separate line items — one for themselves
    (MEMBER) and one for a guest (GUEST) — both items get the buyer's
    name as customer. This function detects GUEST items where a
    ``guest_name`` is available and promotes the guest to customer,
    adding a "Purchased by <buyer>" note.

    Detection: item has user_status containing "GUEST" AND a non-empty
    ``guest_name`` field, AND the current customer differs from the
    guest_name (meaning the buyer's name is on the row, not the guest's).
    """
    for row in rows:
        status = (row.get("user_status") or "").upper()
        if "GUEST" not in status:
            continue
        guest = (row.get("guest_name") or "").strip()
        if not guest:
            continue
        buyer = (row.get("customer") or "").strip()
        # Only swap if the customer is still the buyer (not already the guest)
        guest_norm = _normalize_customer_name(guest)
        if not guest_norm or guest_norm.lower() == buyer.lower():
            continue
        row["customer"] = guest_norm
        row["notes"] = f"Purchased by {buyer}"
        # Clear buyer-specific fields — guest has different contact info
        row["customer_email"] = None
        row["customer_phone"] = None
        row["address"] = None
        row["address2"] = None
        row["city"] = None
        row["state"] = None
        row["zip"] = None
    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _validate_parsed_items(rows: list[dict]) -> list[dict]:
    """Check parsed items for suspicious patterns and attach warnings.

    Returns the same rows with a ``_parse_warnings`` list added to any
    row that has a potential issue.  Callers can persist these warnings
    for admin review.
    """
    warnings: list[dict] = []
    for row in rows:
        item_name = (row.get("item_name") or "").strip()
        if not item_name:
            continue

        row_warnings = []

        # 1. item_name is JUST a course name (e.g. "Star Ranch" instead of "a9.1 STAR RANCH")
        if item_name.lower() in _COURSE_ONLY_NAMES:
            row_warnings.append({
                "code": "COURSE_NAME_ONLY",
                "message": (
                    f"Item name \"{item_name}\" is just a course name — the event "
                    f"identifier (e.g. series code like 'a9.1') was likely missed "
                    f"during parsing. Check the original email Order Summary."
                ),
            })
            logger.warning(
                "Parse validation: item_name '%s' is just a course name "
                "(order_id=%s, customer=%s) — event code likely missing",
                item_name, row.get("order_id"), row.get("customer"),
            )

        # 2. item_name is very short and looks like it might be truncated
        # (real event names are usually 10+ chars, e.g. "a9.1 Star Ranch")
        elif len(item_name) < 6 and not _MEMBERSHIP_RE.match(item_name):
            row_warnings.append({
                "code": "ITEM_NAME_TOO_SHORT",
                "message": f"Item name \"{item_name}\" is suspiciously short — may be truncated.",
            })

        # 3. GUEST item in a multi-item order with no identifiable guest name
        #    Only warn when the same buyer has another item in this batch (same email_uid)
        #    AND there's no guest_name or partner_request to identify the guest.
        status = (row.get("user_status") or "").upper()
        if "GUEST" in status and not (row.get("guest_name") or "").strip():
            email_uid = row.get("email_uid", "")
            customer = (row.get("customer") or "").strip().lower()
            has_peer = email_uid and not email_uid.startswith("manual-") and any(
                r.get("email_uid") == email_uid and r is not row
                and (r.get("customer") or "").strip().lower() == customer
                for r in rows
            )
            no_partner = not (row.get("partner_request") or "").strip()
            if has_peer and no_partner:
                row_warnings.append({
                    "code": "GUEST_NAME_MISSING",
                    "message": (
                        f"GUEST registration for \"{row.get('customer', '')}\" has no guest name. "
                        f"The customer may be the buyer, not the actual guest. "
                        f"Please confirm or update the guest player's name."
                    ),
                })
                logger.warning(
                    "Parse validation: GUEST item missing guest_name "
                    "(item_name=%s, customer=%s, order_id=%s)",
                    item_name, row.get("customer"), row.get("order_id"),
                )

        # 4. Side games selected but item_price may equal base rate only
        #    (parser grabbed "MEMBER = $88" instead of Subtotal $148)
        side_games = (row.get("side_games") or "").strip().upper()
        if side_games in ("NET", "GROSS", "BOTH"):
            raw_price = (row.get("item_price") or "").replace("$", "").replace(",", "").strip()
            try:
                price = float(raw_price)
            except (ValueError, TypeError):
                price = 0
            if price > 0:
                # Known base rates that never include side game add-ons
                # These are the standard member/1st-timer rates WITHOUT games
                _BASE_RATES_NO_GAMES = {73, 88, 102}
                if price in _BASE_RATES_NO_GAMES:
                    row_warnings.append({
                        "code": "price_games_mismatch",
                        "message": (
                            f"Player selected {side_games} games but item_price=${price:.2f} "
                            f"matches a base rate with no add-ons. Expected higher amount if "
                            f"games were added. Likely parsed from 'MEMBER = ${price:.0f}' "
                            f"instead of the Subtotal line. Order: {row.get('order_id', '?')}"
                        ),
                    })
                    logger.warning(
                        "Parse validation: price_games_mismatch — %s games but price=$%.2f "
                        "(order_id=%s, customer=%s)",
                        side_games, price, row.get("order_id"), row.get("customer"),
                    )

        if row_warnings:
            row["_parse_warnings"] = row_warnings
            warnings.extend(row_warnings)

    return rows


def parse_email(email_data: dict) -> list[dict]:
    """
    Parse a single email dict (from fetcher) using Claude AI.

    Returns a *list* of flat dicts — one per line item — ready for DB insert.
    Returns an empty list if parsing fails or no items are found.
    """
    subject = email_data.get("subject", "")
    body = email_data.get("text", "")
    if not body and email_data.get("html"):
        body = _strip_html(email_data["html"])
    if not body:
        logger.warning("Empty email body for subject=%s uid=%s", subject, email_data.get("uid", ""))
        return []

    parsed = _call_ai(body)
    if not parsed:
        logger.warning("AI returned no result for subject=%s uid=%s (body length=%d)",
                        subject, email_data.get("uid", ""), len(body))
        return []

    items = parsed.get("items") or []
    if not items:
        logger.warning("AI returned 0 items for subject=%s uid=%s (body length=%d)",
                        subject, email_data.get("uid", ""), len(body))
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
            "order_time": parsed.get("order_time"),
            "total_amount": parsed.get("total_amount") or "",
            "transaction_fees": parsed.get("transaction_fees"),
            "coupon_code": parsed.get("coupon_code"),
            "coupon_amount": parsed.get("coupon_amount"),
            "item_name": _normalize_item_name(item.get("item_name")) or "",
            "item_price": item.get("item_price") or "",
            "quantity": item.get("quantity") or 1,
            "chapter": _normalize_chapter(item.get("chapter")),
            "course": _normalize_course_name(item.get("course")),
            "handicap": item.get("handicap"),
            "has_handicap": item.get("has_handicap"),
            "side_games": item.get("side_games"),
            "tee_choice": _normalize_tee_choice(item.get("tee_choice")),
            "user_status": item.get("user_status"),
            "post_game": item.get("post_game"),
            "partner_request": item.get("partner_request"),
            "fellowship": item.get("fellowship"),
            "notes": item.get("notes"),
            "holes": item.get("holes"),
            "address": parsed.get("address"),
            "address2": parsed.get("address2"),
            "transaction_status": "active",
            "city": parsed.get("address_city"),
            "state": parsed.get("address_state"),
            "zip": parsed.get("address_zip"),
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

    # Expand any items with quantity > 1 into separate per-player rows
    rows = _expand_quantity_rows(rows)

    # Promote guest_name to customer on GUEST line items
    rows = _promote_guest_customers(rows)

    # Validate parsed items and attach warnings for suspicious patterns
    rows = _validate_parsed_items(rows)

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
