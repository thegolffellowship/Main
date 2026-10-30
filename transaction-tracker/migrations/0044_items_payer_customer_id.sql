-- THE PAYER OF AN ORDER (Kerry 2026-10-30, verbatim: "Yes, build the payer
-- field with the migration" / "Seems like all transactions should go under a
-- customer_id, right? ... But there's definitely a parent payer element that
-- is assigned"). items.customer_id is who PLAYS the line; payer_customer_id
-- is who PAID the order: the order header's billing name, email and address.
-- Set once at import (email_parser/payer.py), never changed by a player edit
-- (Assign Guest, change customer, merges), read first by credit / WD credit /
-- transfer. Case: 3162, Peter Rundqvist's spot on Jeff Young's order
-- R293121452, whose $49 credit followed the player. RULE 3b schema, Kerry's
-- word above. Number: requested from Database (#2552).
-- Reversible: the column is ignored when NULL.
ALTER TABLE items ADD COLUMN payer_customer_id INTEGER REFERENCES customers(customer_id);
CREATE INDEX IF NOT EXISTS idx_items_order_id ON items (order_id);
