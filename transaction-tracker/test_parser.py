"""
Test the AI-based transaction email parser.

Uses unittest.mock to patch the Anthropic API call so tests run without
an API key.  Validates that the parser correctly transforms AI output into
flat item rows ready for database storage.

Run: python test_parser.py
"""

import json
from unittest.mock import patch, MagicMock

from email_parser.parser import parse_email

# Simulated email data matching a Golf Fellowship order with one item
SAMPLE_EMAIL = {
    "uid": "test-001",
    "subject": "New Order #R854482675",
    "from": "The Golf Fellowship <noreply@mysimplestore.com>",
    "date": None,
    "text": """The Golf Fellowship
New order from: Kenneth Carter

(210) 378-8073 | rzrback31@gmail.com

VIEW ORDER
Order: R854482675  |  Date: 02-10-2026
Shipping Address

KENNETH CARTER
1035 CR 4516
CASTROVILLEC TX 78009
(210) 378-8073

Billing Address

Same as the shipping address

Shipping Method

Ships Free

Order Summary

Feb 22 - LaCANTERA

GOLF or COMPETE?: EVENT Only - No Additional Games
MEMBER STATUS: MEMBER = $158
POST-GAME FELLOWSHIP?: YES
TEE CHOICE (See details for selection): <50 | 6300-6800y
SKU: 26-s18-2-M
$158.00
Subtotal:\t$158.00
Shipping (Ships Free):\t$0.00
Transaction Fees 3.5%:\t$5.53
Order Total:

$163.53

Selected payment method:
Credit/Debit Card - GoDaddy Payments""",
    "html": "",
}

# What we expect Claude to return for the above email
MOCK_AI_RESPONSE = {
    "merchant": "The Golf Fellowship",
    "customer": "Kenneth Carter",
    "order_id": "R854482675",
    "order_date": "2026-02-10",
    "total_amount": "$163.53",
    "items": [
        {
            "item_name": "Feb 22 - LaCANTERA",
            "item_price": "$158.00",
            "quantity": 1,
            "chapter": None,
            "course": "LaCANTERA",
            "handicap": None,
            "side_games": None,
            "tee_choice": "<50 | 6300-6800y",
            "user_status": "MEMBER = $158",
            "side_games_raw": "EVENT Only - No Additional Games",
            "post_game": "YES",
            "returning_or_new": None,
            "shirt_size": None,
            "guest_name": None,
            "date_of_birth": None,
            "net_points_race": None,
            "gross_points_race": None,
            "city_match_play": None,
        }
    ],
}

# Simulated multi-item email
MULTI_ITEM_EMAIL = {
    "uid": "test-002",
    "subject": "New Order #R999999999",
    "from": "The Golf Fellowship <noreply@mysimplestore.com>",
    "date": None,
    "text": "Multi item order body (mocked)",
    "html": "",
}

MOCK_MULTI_ITEM_RESPONSE = {
    "merchant": "The Golf Fellowship",
    "customer": "John Doe",
    "order_id": "R999999999",
    "order_date": "2026-03-15",
    "total_amount": "$350.00",
    "items": [
        {
            "item_name": "Mar 15 - TPC San Antonio",
            "item_price": "$175.00",
            "quantity": 1,
            "chapter": "San Antonio",
            "course": "TPC San Antonio",
            "handicap": "12",
            "side_games": "NET Points Race, City Match Play",
            "tee_choice": "<50 | 6300-6800y",
            "user_status": "MEMBER = $175",
            "side_games_raw": "COMPETE",
            "post_game": "YES",
            "returning_or_new": "Returning",
            "shirt_size": None,
            "guest_name": None,
            "date_of_birth": None,
            "net_points_race": "YES",
            "gross_points_race": None,
            "city_match_play": "YES",
        },
        {
            "item_name": "TGF Membership 2026",
            "item_price": "$175.00",
            "quantity": 1,
            "chapter": None,
            "course": None,
            "handicap": None,
            "side_games": None,
            "tee_choice": None,
            "user_status": None,
            "side_games_raw": None,
            "post_game": None,
            "returning_or_new": None,
            "shirt_size": "XL",
            "guest_name": None,
            "date_of_birth": None,
            "net_points_race": None,
            "gross_points_race": None,
            "city_match_play": None,
        },
    ],
}


def _make_mock_response(data: dict):
    """Create a mock Anthropic message response."""
    mock_msg = MagicMock()
    mock_block = MagicMock()
    mock_block.text = json.dumps(data)
    mock_msg.content = [mock_block]
    return mock_msg


def test_single_item():
    """Test parsing a single-item Golf Fellowship order."""
    print("=== Test: Single Item Order ===")

    with patch("email_parser.parser.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(MOCK_AI_RESPONSE)

        # Need ANTHROPIC_API_KEY to be set
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            rows = parse_email(SAMPLE_EMAIL)

    errors = []

    if len(rows) != 1:
        errors.append(f"Expected 1 row, got {len(rows)}")
    else:
        row = rows[0]
        checks = {
            "merchant": "The Golf Fellowship",
            "customer": "Kenneth Carter",
            "order_id": "R854482675",
            "order_date": "2026-02-10",
            "total_amount": "$163.53",
            "item_name": "Feb 22 - LaCANTERA",
            "item_price": "$158.00",
            "side_games_raw": "EVENT Only - No Additional Games",
            "user_status": "MEMBER = $158",
            "post_game": "YES",
            "tee_choice": "<50 | 6300-6800y",
            "email_uid": "test-001",
            "item_index": 0,
        }
        for key, expected in checks.items():
            actual = row.get(key)
            if actual != expected:
                errors.append(f"{key}: expected '{expected}', got '{actual}'")

        print(f"  Merchant:   {row['merchant']}")
        print(f"  Customer:   {row['customer']}")
        print(f"  Item:       {row['item_name']}")
        print(f"  Price:      {row['item_price']}")
        print(f"  Status:     {row.get('user_status', '')}")
        print(f"  Tee:        {row['tee_choice']}")
        print(f"  Order ID:   {row['order_id']}")

    if errors:
        print("\n  FAILURES:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("\n  ALL CHECKS PASSED")
    print()
    return len(errors) == 0


def test_multi_item():
    """Test parsing a multi-item order."""
    print("=== Test: Multi-Item Order ===")

    with patch("email_parser.parser.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(MOCK_MULTI_ITEM_RESPONSE)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            rows = parse_email(MULTI_ITEM_EMAIL)

    errors = []

    if len(rows) != 2:
        errors.append(f"Expected 2 rows, got {len(rows)}")
    else:
        # First item — event registration
        r0 = rows[0]
        if r0["item_name"] != "Mar 15 - TPC San Antonio":
            errors.append(f"item[0].item_name: expected 'Mar 15 - TPC San Antonio', got '{r0['item_name']}'")
        if r0["side_games"] != "NET Points Race, City Match Play":
            errors.append(f"item[0].side_games: expected 'NET Points Race, City Match Play', got '{r0['side_games']}'")
        if r0["chapter"] != "San Antonio":
            errors.append(f"item[0].chapter: expected 'San Antonio', got '{r0['chapter']}'")
        if r0["item_index"] != 0:
            errors.append(f"item[0].item_index: expected 0, got {r0['item_index']}")

        # Second item — membership
        r1 = rows[1]
        if r1["item_name"] != "TGF Membership 2026":
            errors.append(f"item[1].item_name: expected 'TGF Membership 2026', got '{r1['item_name']}'")
        if r1["shirt_size"] != "XL":
            errors.append(f"item[1].shirt_size: expected 'XL', got '{r1['shirt_size']}'")
        if r1["item_index"] != 1:
            errors.append(f"item[1].item_index: expected 1, got {r1['item_index']}")

        # Both should share order-level fields
        if r0["order_id"] != r1["order_id"]:
            errors.append("order_id mismatch between items")
        if r0["customer"] != "John Doe":
            errors.append(f"customer: expected 'John Doe', got '{r0['customer']}'")

        print(f"  Item 0: {r0['item_name']} — {r0['item_price']} — sides: {r0['side_games']}")
        print(f"  Item 1: {r1['item_name']} — {r1['item_price']} — shirt: {r1['shirt_size']}")

    if errors:
        print("\n  FAILURES:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("\n  ALL CHECKS PASSED")
    print()
    return len(errors) == 0


def test_contest_option_lines():
    """The printed contest add-on lines override the LLM (2026-09-09:
    Campos / Cheshire / Lourigan lost 'Add CITY Match Play?: YES';
    Miller's 'Add FALL Points Race?: YES' came back as NET)."""
    print("=== Test: Contest option lines are read from the form ===")
    from email_parser.parser import contest_flags_from_body
    errors = []
    body = ("TGF MEMBERSHIP CITY: SAN ANTONIO RETURNING or NEW?: RETURNING "
            "Add CITY Match Play?: YES Do you have a Current Handicap? YES SKU: MEM-R-S")
    f = contest_flags_from_body(body.upper())
    if f != {"city_match_play": "YES"}:
        errors.append(f"match play line: {f}")
    body2 = "TGF MEMBERSHIP RETURNING or NEW?: RETURNING Add FALL Points Race?: YES SKU: MEM-R-S"
    f2 = contest_flags_from_body(body2.upper())
    if f2 != {"fall_net_points_race": "YES", "net_points_race": "NO"}:
        errors.append(f"fall line clears NET: {f2}")
    body3 = ("Add NET Points Race?: YES Add GROSS Points Race?: YES "
             "Add CITY Match Play?: NO")
    f3 = contest_flags_from_body(body3.upper())
    if f3 != {"net_points_race": "YES", "gross_points_race": "YES", "city_match_play": "NO"}:
        errors.append(f"three lines: {f3}")
    f4 = contest_flags_from_body("RETURNING or NEW?: NEW ($25 Off Promo) Add FALL Points Race?: YES Add FALL Match Play?: YES".upper())
    if f4 != {"fall_net_points_race": "YES", "city_match_play": "YES", "net_points_race": "NO"}:
        errors.append(f"2025 FALL Match Play line (Bartz): {f4}")
    if contest_flags_from_body("EVENT ONLY - NO ADDITIONAL GAMES") != {}:
        errors.append("no lines → empty (LLM value kept)")
    # End to end: the LLM omits the flag, the form line supplies it.
    email = dict(SAMPLE_EMAIL)
    email["text"] = (SAMPLE_EMAIL["text"] + "\nTGF MEMBERSHIP\nRETURNING or NEW?: RETURNING\n"
                     "Add CITY Match Play?: YES\nSKU: MEM-R-S\n$125.00")
    ai = {"merchant": "The Golf Fellowship", "customer": "Rolando Campos",
          "order_id": "R745590832", "order_date": "2026-05-13", "total_amount": "$129.38",
          "items": [{"item_name": "TGF MEMBERSHIP", "item_price": "$125.00", "quantity": 1,
                     "returning_or_new": "Returning", "city_match_play": None}]}
    with patch("email_parser.parser.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_response(ai)
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            rows = parse_email(email)
    if not rows or rows[0].get("city_match_play") != "YES":
        errors.append(f"end to end: {rows and rows[0].get('city_match_play')}")
    if errors:
        print("\n  FAILURES:")
        for e in errors:
            print(f"    - {e}")
    else:
        print("\n  ALL CHECKS PASSED")
    print()
    return not errors


def main():
    results = [test_single_item(), test_multi_item(), test_contest_option_lines()]
    print("=" * 40)
    if all(results):
        print("ALL TESTS PASSED")
    else:
        print(f"SOME TESTS FAILED ({results.count(False)} of {len(results)})")


if __name__ == "__main__":
    main()
