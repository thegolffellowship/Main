# Customer Merge Repair Playbook

When a customer's profile disappears and their transactions show up under someone else,
a bad merge has absorbed their `customer_emails` row into another customer's record.
This playbook describes how to diagnose and write a boot-time repair function.

## What a bad merge looks like

- Search for "Massey" or "Chalfant" returns no results (or GUEST status with wrong history)
- Transactions for that person appear under a different customer's profile
- The absorbed customer's email is listed in `customer_emails` under the wrong `customer_id`

## Known cases

| Absorbed player   | Absorbed into    | Repair function                    |
|-------------------|------------------|------------------------------------|
| Tanner Chalfant   | Bryan McCrary    | `_repair_chalfant_attribution()`   |
| William Massey    | Colby Johnson    | `_repair_massey_attribution()`     |

Both functions live in `email_parser/database.py` and are called from `init_db()`.

---

## Diagnosis checklist

1. **Find the absorbed player's email** — look at the transactions visible under the wrong
   customer's profile. The `customer_email` column on those `items` rows is the absorbed
   player's email.

2. **Confirm via `customer_emails`** — the absorbed email is linked to the wrong
   `customer_id`:
   ```sql
   SELECT * FROM customer_emails WHERE LOWER(email) = LOWER('absorbed@example.com');
   ```

3. **Know the order IDs** — identify which specific `items.order_id` values belong to
   the absorbed player. You'll need these for the repair function.

4. **Check `items.customer_email`** — the identity-heal migration (`_heal_items_identity_fields`)
   runs on every boot and overwrites `items.customer_email` with the canonical email for
   that row's `customer_id`. This means by the time your repair runs, `items.customer_email`
   on the absorbed player's rows may already show the absorber's email, not the absorbed
   player's email. **Don't rely solely on email matching — target order IDs directly.**

---

## Repair function structure

Copy this skeleton. Call it `_repair_<name>_attribution(conn)` and add it to `init_db()`.

```python
def _repair_<name>_attribution(conn: sqlite3.Connection) -> None:
    _PLAYER_EMAIL  = 'player@example.com'
    _PLAYER_NAME   = 'First Last'
    _PLAYER_PHONE  = '(555) 000-0000'
    _ABSORBER_EMAIL = 'absorber@example.com'
    # Known order IDs that belong to the absorbed player
    _PLAYER_ORDERS = ('RXXXXXXXXX', 'RYYYYYYYYY')

    # 1. Find the absorber's customer_id (look up by email, not hardcoded ID)
    absorber_row = conn.execute(
        "SELECT customer_id FROM customer_emails WHERE LOWER(email) = LOWER(?) LIMIT 1",
        (_ABSORBER_EMAIL,),
    ).fetchone()
    if not absorber_row:
        logger.warning("<Name> repair: could not find absorber — skipping")
        return
    absorber_cid = absorber_row["customer_id"]

    # 2. Remove absorbed player's email from absorber's customer_emails
    conn.execute(
        "DELETE FROM customer_emails WHERE customer_id = ? AND LOWER(email) = LOWER(?)",
        (absorber_cid, _PLAYER_EMAIL),
    )

    # 3. Find or create the absorbed player's own customer record
    player_row = conn.execute(
        "SELECT customer_id FROM customer_emails WHERE LOWER(email) = LOWER(?) LIMIT 1",
        (_PLAYER_EMAIL,),
    ).fetchone()
    if player_row:
        player_cid = player_row["customer_id"]
    else:
        cur = conn.execute(
            """INSERT INTO customers
                   (first_name, last_name, phone, chapter, account_status, acquisition_source)
               VALUES (?, ?, ?, 'Austin', 'active', 'repair')""",
            ('First', 'Last', _PLAYER_PHONE),
        )
        player_cid = cur.lastrowid
        logger.info("<Name> repair: created customer record cid=%d", player_cid)

    # 4. Ensure the player's email is on their own record
    #    Use (customer_id, email) — do NOT include a 'source' column; it doesn't exist.
    conn.execute(
        "INSERT OR IGNORE INTO customer_emails (customer_id, email, is_primary) VALUES (?, ?, 1)",
        (player_cid, _PLAYER_EMAIL),
    )
    conn.execute(
        "UPDATE customer_emails SET is_primary = 1 WHERE customer_id = ? AND LOWER(email) = LOWER(?)",
        (player_cid, _PLAYER_EMAIL),
    )

    # 5. Re-attribute items by email
    #    Note: identity-heal may have already overwritten customer_email, so don't rely on this alone.
    r_email = conn.execute(
        """UPDATE items SET customer = ?, customer_id = ?, customer_email = ?
           WHERE LOWER(customer_email) = LOWER(?) AND (customer_id != ? OR customer_id IS NULL)""",
        (_PLAYER_NAME, player_cid, _PLAYER_EMAIL, _PLAYER_EMAIL, player_cid),
    ).rowcount

    # 6. Re-attribute items by name
    r_name = conn.execute(
        """UPDATE items SET customer = ?, customer_id = ?, customer_email = ?
           WHERE LOWER(customer) IN ('first last', 'nick last')
             AND (customer_id != ? OR customer_id IS NULL)""",
        (_PLAYER_NAME, player_cid, _PLAYER_EMAIL, player_cid),
    ).rowcount

    # 7. Re-attribute by known order IDs (most reliable — immune to identity-heal overwriting)
    placeholders = ','.join('?' * len(_PLAYER_ORDERS))
    r_orders = conn.execute(
        f"""UPDATE items SET customer = ?, customer_id = ?, customer_email = ?
            WHERE order_id IN ({placeholders})
              AND (customer_id != ? OR customer_id IS NULL)""",
        (_PLAYER_NAME, player_cid, _PLAYER_EMAIL, *_PLAYER_ORDERS, player_cid),
    ).rowcount

    logger.info(
        "<Name> repair: re-attributed %d item(s) to cid=%d (by-email=%d, by-name=%d, by-order=%d)",
        r_email + r_name + r_orders, player_cid, r_email, r_name, r_orders,
    )

    conn.commit()  # Must be last — any exception before this rolls back everything
```

### Register it in `init_db()`

Find the block near the end of `init_db()` where `_repair_chalfant_attribution` is called
and add an identical try/except block immediately after:

```python
try:
    _repair_<name>_attribution(conn)
except Exception as e:
    logger.warning("<Name> attribution repair failed: %s", e)
```

---

## Critical gotchas (every one of these burned us)

### 1. `customer_emails` has no `source` column
The live DB's `customer_emails` table only has `(customer_id, email, is_primary, label)`.
Writing `INSERT INTO customer_emails (..., source) VALUES (...)` crashes the repair and
rolls back the entire transaction. Use only the columns that exist.

### 2. `action_items` has no `customer` column
`action_items` schema: `id, email_uid, subject, from_name, from_email, summary, urgency,
category, email_date, status, completed_at, completed_by, resolution_notes, confidence,
created_at, customer_id`. There is no `customer` text column. Only update `customer_id`.

### 3. `NULL != x` is falsy in SQLite
`WHERE customer_id != ?` silently skips rows where `customer_id IS NULL`.
Always write `WHERE (customer_id != ? OR customer_id IS NULL)`.

### 4. The identity-heal overwrites `items.customer_email` before your repair runs
`_heal_items_identity_fields` runs at every boot and sets `items.customer_email` to the
canonical email for that row's `customer_id`. If the absorbed player's items are sitting
under the absorber's `customer_id`, their `items.customer_email` gets overwritten to
the absorber's email. By the time your repair runs, email matching finds 0 rows.
**Always include an order_id-based step** as the primary mechanism.

### 5. `conn.commit()` must be the very last line
All steps share one implicit transaction. An exception at step N rolls back steps 1–N.
If `conn.commit()` never runs, every INSERT and UPDATE is silently discarded on the
next boot restart. Make sure every step uses the correct column names before adding
a new repair — one bad column name undoes everything.

### 6. Look up `customer_id` by email, don't hardcode it
The Chalfant repair uses hardcoded CIDs (325 and 46) which is fragile. Look up the
absorber's `customer_id` via `customer_emails` at runtime so the repair survives
any future re-numbering.

### 7. The repair runs twice per boot
Railway's gunicorn starts two workers, both calling `init_db()`. Make every UPDATE
idempotent (`customer_id != player_cid` guard prevents re-running). The second worker
should always log `re-attributed 0 item(s)`.

---

## Verifying it worked

After the next Railway deploy, the boot log should show:

```
<Name> repair: re-attributed N item(s) to cid=NNN (by-email=X, by-name=Y, by-order=Z)
```

Second boot (idempotent check):
```
<Name> repair: re-attributed 0 item(s) to cid=NNN (by-email=0, by-name=0, by-order=0)
```

Then check the Customers page — the player should appear with correct transaction count
and MEMBER status (if they have a membership).
