"""A money REQUEST is not a transaction (Kerry 2026-09-22).

Straiton's $22 Venmo request for reimbursement was classified as a
payment and booked as $22 of income on Forest Creek — no money had
moved (a request email carries no transaction id). Three layers keep
the class safe now:

1. classify_email fast-paths request subjects to `p2p_request`
   (no LLM call), which check_expense_inbox marks seen and skips.
2. parse_p2p_payment tags a request that slips past classification
   with transaction_type "request" (request wording + no id).
3. check_expense_inbox skips saving a "request"-tagged extraction.

This file guards layers 1 and 2.
"""

import email_parser.expense_parser as ep


def _classify(subject, from_addr):
    return ep.classify_email(subject, from_addr, "body")


def test_venmo_outgoing_request_is_not_a_payment():
    r = _classify("You requested $22.00 from Robert Straiton",
                  "Venmo <venmo@venmo.com>")
    assert r["type"] == "p2p_request"


def test_venmo_incoming_request_is_not_a_payment():
    r = _classify("Robert Straiton requests $22.00",
                  "Venmo <venmo@venmo.com>")
    assert r["type"] == "p2p_request"


def test_venmo_request_reminder_is_not_a_payment():
    r = _classify("Reminder: you requested $22.00 from Robert Straiton",
                  "Venmo <venmo@venmo.com>")
    assert r["type"] == "p2p_request"


def test_paypal_money_request_is_not_a_payment():
    r = _classify("Kerry sent you a money request",
                  "service@paypal.com")
    assert r["type"] == "p2p_request"


def test_zelle_money_request_is_not_a_payment():
    # Zelle requests arrive through the bank, not Zelle itself.
    r = _classify("You have a Zelle money request",
                  "alerts@frostbank.com")
    assert r["type"] == "p2p_request"


def test_real_venmo_payment_still_classifies_as_payment():
    r = _classify("Robert Straiton paid you $22.00",
                  "Venmo <venmo@venmo.com>")
    assert r["type"] == "venmo_payment"


def test_parser_tags_request_that_slips_past_classification(monkeypatch):
    # Layer 2: the LLM route can still hand parse_p2p_payment a request
    # email. Request wording + no transaction id = no money moved.
    monkeypatch.setattr(ep, "_call_llm", lambda prompt: (
        '{"recipient_name": "Robert Straiton", "amount": 22.0,'
        ' "memo": "Forest creek reimbursement",'
        ' "sent_from_account": "@tgf-payments",'
        ' "transaction_date": "", "transaction_id": "",'
        ' "transaction_type": "received", "confidence": 75}'))
    out = ep.parse_p2p_payment("You requested $22.00 from Robert Straiton",
                               "venmo@venmo.com", "body")
    assert out["transaction_type"] == "request"


def test_parser_keeps_real_payment_with_id(monkeypatch):
    # A real payment carries a transaction id and keeps its type even
    # if the word "request" appears somewhere in the subject.
    monkeypatch.setattr(ep, "_call_llm", lambda prompt: (
        '{"recipient_name": "Robert Straiton", "amount": 22.0,'
        ' "memo": "guest fee", "sent_from_account": "Robert Straiton",'
        ' "transaction_date": "2026-09-14",'
        ' "transaction_id": "4686000000000000000",'
        ' "transaction_type": "received", "confidence": 95}'))
    out = ep.parse_p2p_payment("Robert Straiton paid your request",
                               "venmo@venmo.com", "body")
    assert out["transaction_type"] == "received"
