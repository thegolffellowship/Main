"""
Test the transaction email parser against a real MySimpleStore order email.
Run: python test_parser.py
"""

from email_parser.parser import parse_email

# Simulated email data matching the forwarded Golf Fellowship order
SAMPLE_EMAIL = {
    "uid": "test-001",
    "subject": "New Order #R854482675",
    "from": "The Golf Fellowship <noreply@mysimplestore.com>",
    "date": None,  # we'll test date extraction from body
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


def main():
    result = parse_email(SAMPLE_EMAIL)

    if result is None:
        print("FAIL: parse_email returned None")
        return

    print("=== Parsed Transaction ===")
    print(f"  Merchant:  {result['merchant']}")
    print(f"  Customer:  {result['customer']}")
    print(f"  Amount:    {result['amount']}")
    print(f"  Date:      {result['date']}")
    print(f"  Order ID:  {result['order_id']}")
    print(f"  Items:     {result['items']}")
    print(f"  Subject:   {result['subject']}")
    print(f"  From:      {result['from']}")
    print()

    # Assertions
    errors = []

    if result["merchant"] != "The Golf Fellowship":
        errors.append(f"merchant: expected 'The Golf Fellowship', got '{result['merchant']}'")

    if result["customer"] != "Kenneth Carter":
        errors.append(f"customer: expected 'Kenneth Carter', got '{result['customer']}'")

    if result["amount"] != "$163.53":
        errors.append(f"amount: expected '$163.53', got '{result['amount']}'")

    if result["date"] != "2026-02-10":
        errors.append(f"date: expected '2026-02-10', got '{result['date']}'")

    if result["order_id"] != "R854482675":
        errors.append(f"order_id: expected 'R854482675', got '{result['order_id']}'")

    if not result["items"]:
        errors.append("items: expected at least one item, got empty list")
    else:
        # The first item should reference LaCANTERA
        if "LaCANTERA" not in result["items"][0]:
            errors.append(f"items[0]: expected to contain 'LaCANTERA', got '{result['items'][0]}'")

    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
