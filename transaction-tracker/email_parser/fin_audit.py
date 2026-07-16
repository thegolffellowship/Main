"""Read-only financial / customer_id / FK integrity audit (charter:
docs/claude/financial-audit-charter.md, Deliverable 1).

Every function here is pure SELECT/PRAGMA — this module must never write.
Reached in-session via the probe_golf_genius bridge:
    extract="scoring-fin-audit:<section>"
Sections: tables | customer | fks | ledger | money | dupes | summary

The audit introspects the LIVE schema (PRAGMA table_info / sqlite_master)
rather than trusting code-side CREATE TABLE text, so it also catches drift
between the deployed DB and the repo.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .database import managed_connection

# Tables that are pure machine bookkeeping — no person or money reference is
# expected, so they're excluded from the "missing customer_id" complaint list
# (they still appear in the inventory + declared-FK checks).
NON_PERSON_TABLES = {
    "processed_emails", "expense_seen_emails", "app_settings", "chapters",
    "courses", "course_aliases", "event_aliases", "roles", "statuses",
    "acct_keyword_rules", "acct_tags", "acct_categories", "acct_entities",
    "acct_accounts", "bank_accounts", "coo_agents", "system_alert_state",
    "payout_templates", "payout_template_versions", "event_type_template_map",
    "platform_dialogue", "member_analytics", "sqlite_sequence",
    "period_closings", "gg_portal_registry",
}

# Columns whose content is a person NAME (display/snapshot). If one of these
# is populated while customer_id is NULL, the row is a name-only reference.
PERSON_NAME_COLS = (
    "customer", "customer_name", "player_name", "golfer_name", "player",
    "recipient_name", "from_name", "manager_name", "buyer_name", "winner_name",
)

# Conventional FK map for *_id columns that were ALTER-added without a
# declared REFERENCES clause. Declared clauses (parsed from sqlite_master)
# always win; these fill the gaps.
CONVENTIONAL_FK = {
    "customer_id": ("customers", "customer_id"),
    "manager_customer_id": ("customers", "customer_id"),
    "set_by": ("customers", "customer_id"),
    "event_id": ("events", "id"),
    "events_id": ("events", "id"),
    "item_id": ("items", "id"),
    "matched_item_id": ("items", "id"),
    "source_item_id": ("items", "id"),
    "parent_item_id": ("items", "id"),
    "transferred_from_id": ("items", "id"),
    "transferred_to_id": ("items", "id"),
    "acct_transaction_id": ("acct_transactions", "id"),
    "merged_into_id": ("acct_transactions", "id"),
    "surviving_txn_id": ("acct_transactions", "id"),
    "merged_txn_id": ("acct_transactions", "id"),
    "txn_a_id": ("acct_transactions", "id"),
    "txn_b_id": ("acct_transactions", "id"),
    "bank_deposit_id": ("bank_deposits", "id"),
    "chapter_id": ("chapters", "chapter_id"),
    "course_id": ("courses", "id"),
    "status_id": ("statuses", "id"),
    "template_id": ("payout_templates", "id"),
    "payout_template_version_id": ("payout_template_versions", "id"),
    "current_version_id": ("payout_template_versions", "id"),
    "rsvp_id": ("rsvps", "id"),
    "granted_by": ("customers", "customer_id"),
    "role_id": ("roles", "role_id"),
    "entity_id": ("acct_entities", "id"),
    "category_id": ("acct_categories", "id"),
    "tag_id": ("acct_tags", "id"),
    "transaction_id": ("acct_transactions", "id"),
    "account_id": ("acct_accounts", "id"),
    "tee_id": ("course_tees", "tee_id"),
    "related_item_id": ("items", "id"),
    "rescheduled_to_event_id": ("events", "id"),
}
# Fix conventional targets whose PK is table-named, and per-table overrides
CONVENTIONAL_FK["course_id"] = ("courses", "course_id")
CONVENTIONAL_FK["status_id"] = ("statuses", "status_id")
TABLE_FK_OVERRIDE = {
    # Live data proves bank_deposits.account_id points at acct_accounts
    # (ids 3=TGF Checking, 7=Venmo), NOT the vestigial bank_accounts table.
    ("bank_deposits", "account_id"): ("acct_accounts", "id"),
    ("message_log", "template_id"): ("message_templates", "id"),
}

# A row is DEAD only when reversed or merged. 'reconciled' is a LIVE status
# (matched to a bank deposit) — never count links to reconciled rows as
# dangling evidence.
DEAD = "('reversed','merged')"
LIVE = "COALESCE(status,'active') NOT IN ('reversed','merged')"
# Columns that hold EXTERNAL identifiers (Golf Genius, Platform) — no local
# FK target exists by design, so they're not flagged as unmapped.
EXTERNAL_ID_COLS = {"platform_user_id", "round_id", "gg_round_id",
                    "gg_event_id", "gg_aggregate_id", "gg_profile_id",
                    "gg_league_round_id", "gg_tournament_id"}

# Money-bearing columns, first match wins, used to sum the dollars sitting on
# gap rows so findings rank by financial exposure, not just row count.
AMOUNT_COLS = (
    "amount", "total_amount", "item_price", "price_paid", "refund_amount",
    "amount_owed", "total_purse", "total_collected",
)

# tgf_payouts / expense_transactions special-cased in money section.
# FOREIGN KEY branch FIRST — otherwise the inline branch consumes the word
# "FOREIGN" as a column name and the real column never gets mapped.
_REF_RE = re.compile(
    r'(?:FOREIGN\s+KEY\s*\(\s*"?(\w+)"?\s*\)\s*REFERENCES\s+"?(\w+)"?\s*\(\s*"?(\w+)"?\s*\))'
    r'|(?:"?(\w+)"?\s+[A-Za-z0-9_() ]*?REFERENCES\s+"?(\w+)"?\s*\(\s*"?(\w+)"?\s*\))',
    re.IGNORECASE,
)


def _tables(conn):
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return {r["name"]: (r["sql"] or "") for r in rows}


def _cols(conn, table):
    return [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _pk_cols(conn, table):
    return {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')
            if r["pk"]}


def _count(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def _one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else {}


def _declared_fks(create_sql):
    """Parse REFERENCES clauses out of a CREATE TABLE statement."""
    fks = []
    for m in _REF_RE.finditer(create_sql or ""):
        if m.group(1):
            fks.append((m.group(1), m.group(2), m.group(3)))
        else:
            fks.append((m.group(4), m.group(5), m.group(6)))
    return fks


def _amount_col(cols):
    for c in AMOUNT_COLS:
        if c in cols:
            return c
    return None


# ────────────────────────────────────────────────────────────────────
# Section: tables — whole-DB inventory
# ────────────────────────────────────────────────────────────────────
def audit_tables(conn):
    out = []
    for table, sql in _tables(conn).items():
        cols = _cols(conn, table)
        n = _count(conn, f'SELECT COUNT(*) FROM "{table}"')
        person_cols = [c for c in cols if c in PERSON_NAME_COLS]
        pks = _pk_cols(conn, table)
        id_cols = [c for c in cols
                   if (c.endswith("_id") or c == "set_by") and c not in pks]
        declared = {c for c, _, _ in _declared_fks(sql)}
        unmapped = [c for c in id_cols
                    if c not in declared and c not in CONVENTIONAL_FK
                    and (table, c) not in TABLE_FK_OVERRIDE
                    and c not in EXTERNAL_ID_COLS
                    and c != "id" and not c.startswith("email")
                    and c not in ("order_id", "email_uid", "reconciled_batch_id",
                                  "source_ref", "league_id")]
        out.append({
            "table": table,
            "rows": n,
            "has_customer_id": "customer_id" in cols,
            "person_name_cols": person_cols,
            "needs_customer_id": (
                "customer_id" not in cols and bool(person_cols)
                and table not in NON_PERSON_TABLES),
            "unmapped_id_cols": unmapped,
        })
    return {"tables": out, "table_count": len(out)}


# ────────────────────────────────────────────────────────────────────
# Section: customer — lens A, customer_id coverage per table
# ────────────────────────────────────────────────────────────────────
def audit_customer_lens(conn):
    report = []
    for table, _sql in _tables(conn).items():
        cols = _cols(conn, table)
        person_cols = [c for c in cols if c in PERSON_NAME_COLS]
        if "customer_id" not in cols:
            if person_cols and table not in NON_PERSON_TABLES:
                n = _count(conn, f'SELECT COUNT(*) FROM "{table}"')
                report.append({
                    "table": table, "rows": n,
                    "MISSING_customer_id_column": True,
                    "person_name_cols": person_cols,
                })
            continue
        n = _count(conn, f'SELECT COUNT(*) FROM "{table}"')
        if n == 0:
            continue
        nulls = _count(
            conn, f'SELECT COUNT(*) FROM "{table}" WHERE customer_id IS NULL')
        orphans = _count(
            conn,
            f'SELECT COUNT(*) FROM "{table}" t WHERE t.customer_id IS NOT NULL '
            'AND NOT EXISTS (SELECT 1 FROM customers c '
            'WHERE c.customer_id = t.customer_id)')
        name_only = 0
        if person_cols:
            pred = " OR ".join(
                f'(t."{c}" IS NOT NULL AND TRIM(t."{c}") != \'\')'
                for c in person_cols)
            name_only = _count(
                conn,
                f'SELECT COUNT(*) FROM "{table}" t '
                f'WHERE t.customer_id IS NULL AND ({pred})')
        entry = {
            "table": table, "rows": n,
            "null_customer_id": nulls,
            "coverage_pct": round(100.0 * (n - nulls) / n, 1),
            "orphan_customer_id": orphans,
            "name_only_rows": name_only,
        }
        amt = _amount_col(cols)
        if amt and nulls:
            entry["dollars_on_null_rows"] = round(_one(
                conn,
                f'SELECT COALESCE(SUM(ABS("{amt}")),0) AS s FROM "{table}" '
                'WHERE customer_id IS NULL').get("s", 0), 2)
        report.append(entry)
    report.sort(key=lambda e: (
        -(e.get("dollars_on_null_rows", 0) or 0),
        -(e.get("null_customer_id", 0) or e.get("rows", 0))))
    return {"customer_id_lens": report}


# ────────────────────────────────────────────────────────────────────
# Section: fks — lens C, dangling references
# ────────────────────────────────────────────────────────────────────
def audit_fks(conn):
    tables = _tables(conn)
    findings, checked = [], 0
    for table, sql in tables.items():
        cols = _cols(conn, table)
        pks = _pk_cols(conn, table)
        fkmap = {}
        for col, rt, rc in _declared_fks(sql):
            if col in cols:
                fkmap[col] = (rt, rc)
        for col in cols:
            if col in fkmap or col in pks:
                continue
            if (table, col) in TABLE_FK_OVERRIDE:
                fkmap[col] = TABLE_FK_OVERRIDE[(table, col)]
            elif col in CONVENTIONAL_FK:
                fkmap[col] = CONVENTIONAL_FK[col]
        for col, (rt, rc) in fkmap.items():
            if rt not in tables or rc not in _cols(conn, rt):
                findings.append({"table": table, "column": col,
                                 "ref": f"{rt}({rc})",
                                 "error": "referenced table/column missing"})
                continue
            checked += 1
            dangling = _count(
                conn,
                f'SELECT COUNT(*) FROM "{table}" t WHERE t."{col}" IS NOT NULL '
                f'AND NOT EXISTS (SELECT 1 FROM "{rt}" r '
                f'WHERE r."{rc}" = t."{col}")')
            if dangling:
                nulls = _count(
                    conn,
                    f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" IS NULL')
                sample = [r[0] for r in conn.execute(
                    f'SELECT DISTINCT t."{col}" FROM "{table}" t '
                    f'WHERE t."{col}" IS NOT NULL AND NOT EXISTS '
                    f'(SELECT 1 FROM "{rt}" r WHERE r."{rc}" = t."{col}") '
                    'LIMIT 10')]
                findings.append({
                    "table": table, "column": col, "ref": f"{rt}({rc})",
                    "dangling": dangling, "nulls_for_context": nulls,
                    "sample_dangling_values": sample,
                })
    findings.sort(key=lambda f: -(f.get("dangling") or 0))
    return {"fk_checks_run": checked, "dangling_fk_findings": findings}


# ────────────────────────────────────────────────────────────────────
# Section: ledger — acct_transactions deep dive (lens B core)
# ────────────────────────────────────────────────────────────────────
def audit_ledger(conn):
    cols = _cols(conn, "acct_transactions")
    out = {"columns_present": cols}
    amt = "amount" if "amount" in cols else "total_amount"

    out["by_status"] = [dict(r) for r in conn.execute(
        f"SELECT COALESCE(status,'(null)') AS status, COUNT(*) AS n, "
        f"ROUND(SUM({amt}),2) AS total FROM acct_transactions GROUP BY 1")]

    out["active_by_entry_type_category"] = [dict(r) for r in conn.execute(
        f"""SELECT COALESCE(entry_type,'(legacy-null)') AS entry_type,
                   COALESCE(category,'(null)') AS category,
                   COUNT(*) AS n, ROUND(SUM({amt}),2) AS total,
                   SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS cid_null,
                   ROUND(SUM(CASE WHEN customer_id IS NULL THEN ABS({amt})
                             ELSE 0 END),2) AS dollars_cid_null
            FROM acct_transactions
            WHERE COALESCE(status,'active') NOT IN ('reversed','merged')
            GROUP BY 1,2 ORDER BY dollars_cid_null DESC""")]

    out["active_by_source"] = [dict(r) for r in conn.execute(
        f"""SELECT COALESCE(source,'(null)') AS source, COUNT(*) AS n,
                   ROUND(SUM({amt}),2) AS total,
                   SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS cid_null
            FROM acct_transactions
            WHERE COALESCE(status,'active') NOT IN ('reversed','merged')
            GROUP BY 1 ORDER BY n DESC""")]

    # source_ref families: exp-promoted-N, venmo-bd-N, godaddy-order-X …
    fam = defaultdict(lambda: [0, 0.0, 0, 0.0])
    for r in conn.execute(
            f"SELECT source_ref, {amt} AS a, customer_id FROM acct_transactions "
            "WHERE COALESCE(status,'active') NOT IN ('reversed','merged')"):
        ref = r["source_ref"] or "(none)"
        family = re.sub(r"[-_]?\d+$", "", ref) or "(none)"
        f = fam[family]
        f[0] += 1
        f[1] += r["a"] or 0
        if r["customer_id"] is None:
            f[2] += 1
            f[3] += abs(r["a"] or 0)
    out["active_by_source_ref_family"] = sorted(
        ({"family": k, "n": v[0], "total": round(v[1], 2),
          "cid_null": v[2], "dollars_cid_null": round(v[3], 2)}
         for k, v in fam.items()),
        key=lambda e: -e["dollars_cid_null"])

    # Name-only: customer text present, customer_id NULL
    if "customer" in cols:
        out["name_only_rows"] = _one(conn, f"""
            SELECT COUNT(*) AS n, ROUND(SUM(ABS({amt})),2) AS dollars
            FROM acct_transactions
            WHERE COALESCE(status,'active') NOT IN ('reversed','merged') AND customer_id IS NULL
              AND customer IS NOT NULL AND TRIM(customer) != ''""")

    # Floating money: attributed to no customer, no item, no event
    ev_pred = ("(event_name IS NULL OR TRIM(event_name)='')"
               if "event_name" in cols else "1=1")
    item_pred = "item_id IS NULL" if "item_id" in cols else "1=1"
    out["floating_money"] = [dict(r) for r in conn.execute(f"""
        SELECT COALESCE(entry_type,'(legacy-null)') AS entry_type,
               COUNT(*) AS n, ROUND(SUM(ABS({amt})),2) AS dollars
        FROM acct_transactions
        WHERE COALESCE(status,'active') NOT IN ('reversed','merged')
          AND customer_id IS NULL AND {item_pred} AND {ev_pred}
        GROUP BY 1 ORDER BY dollars DESC""")]

    # Event linkage is by NAME string only (no event_id column on the ledger)
    out["has_event_id_column"] = "event_id" in cols
    if "event_name" in cols:
        out["event_name_not_in_events"] = _one(conn, """
            SELECT COUNT(*) AS n FROM acct_transactions t
            WHERE COALESCE(t.status,'active') NOT IN ('reversed','merged')
              AND t.event_name IS NOT NULL AND TRIM(t.event_name) != ''
              AND NOT EXISTS (SELECT 1 FROM events e
                              WHERE e.item_name = t.event_name)""")

    # Legacy accounting rows (entry_type NULL) — the parallel-truth pool
    out["legacy_rows_no_entry_type"] = _one(conn, f"""
        SELECT COUNT(*) AS n, ROUND(SUM({amt}),2) AS total
        FROM acct_transactions
        WHERE COALESCE(status,'active') NOT IN ('reversed','merged') AND entry_type IS NULL""")
    return out


# ────────────────────────────────────────────────────────────────────
# Section: money — the satellite financial tables (lens B)
# ────────────────────────────────────────────────────────────────────
def audit_money(conn):
    out = {}
    tables = _tables(conn)

    # tgf_payouts: computed vs actual-paid variance
    if "tgf_payouts" in tables:
        out["tgf_payouts"] = _one(conn, """
            SELECT COUNT(*) AS rows_total,
                   SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS cid_null,
                   SUM(CASE WHEN paid_at IS NOT NULL THEN 1 ELSE 0 END) AS paid_rows,
                   SUM(CASE WHEN paid_at IS NOT NULL
                            AND acct_transaction_id IS NULL THEN 1 ELSE 0 END)
                       AS paid_but_unlinked_to_ledger,
                   SUM(CASE WHEN acct_transaction_id IS NOT NULL THEN 1 ELSE 0 END)
                       AS linked_rows,
                   ROUND(SUM(amount),2) AS computed_total
            FROM tgf_payouts""")
        # One Venmo payment often covers SEVERAL payout rows (a lump per
        # golfer per event day), so variance is judged per linked ledger
        # row: sum of computed payouts sharing that acct_transaction_id
        # vs the actual paid amount.
        var = [dict(r) for r in conn.execute("""
            SELECT p.acct_transaction_id,
                   COUNT(*) AS payout_rows,
                   MIN(p.customer_id) AS customer_id,
                   ROUND(SUM(p.amount),2) AS computed_sum,
                   ROUND(ABS(a.total_amount),2) AS actual_paid,
                   ROUND(ABS(a.total_amount) - SUM(p.amount),2) AS variance
            FROM tgf_payouts p
            JOIN acct_transactions a ON a.id = p.acct_transaction_id
            GROUP BY p.acct_transaction_id
            HAVING ABS(ABS(a.total_amount) - SUM(p.amount)) > 0.01
            ORDER BY ABS(ABS(a.total_amount) - SUM(p.amount)) DESC
            LIMIT 25""")]
        out["tgf_payouts"]["variance_lumps_computed_vs_actual"] = len(var)
        out["tgf_payouts"]["variance_total_abs"] = round(
            sum(abs(v["variance"] or 0) for v in var), 2)
        out["tgf_payouts"]["variance_examples"] = var
        out["tgf_payouts"]["linked_to_nonactive_ledger_row"] = _count(conn, """
            SELECT COUNT(*) FROM tgf_payouts p
            JOIN acct_transactions a ON a.id = p.acct_transaction_id
            WHERE COALESCE(a.status,'active') IN ('reversed','merged')""")

    # expense_transactions: staging → promotion integrity
    if "expense_transactions" in tables:
        out["expense_transactions"] = {
            "by_review_status": [dict(r) for r in conn.execute("""
                SELECT review_status, transaction_type, COUNT(*) AS n,
                       ROUND(SUM(amount),2) AS total,
                       SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END)
                           AS cid_null
                FROM expense_transactions GROUP BY 1,2 ORDER BY n DESC""")],
            "approved_not_promoted": _one(conn, """
                SELECT COUNT(*) AS n, ROUND(SUM(amount),2) AS total
                FROM expense_transactions
                WHERE review_status='approved' AND acct_transaction_id IS NULL"""),
            "promoted_to_nonactive_ledger_row": _count(conn, """
                SELECT COUNT(*) FROM expense_transactions e
                JOIN acct_transactions a ON a.id = e.acct_transaction_id
                WHERE COALESCE(a.status,'active') IN ('reversed','merged')"""),
            "promoted_rows_ledger_cid_null": _one(conn, """
                SELECT COUNT(*) AS n, ROUND(SUM(ABS(a.total_amount)),2) AS dollars
                FROM expense_transactions e
                JOIN acct_transactions a ON a.id = e.acct_transaction_id
                WHERE COALESCE(a.status,'active') NOT IN ('reversed','merged')
                  AND a.customer_id IS NULL"""),
            "exp_cid_set_but_ledger_cid_null": _count(conn, """
                SELECT COUNT(*) FROM expense_transactions e
                JOIN acct_transactions a ON a.id = e.acct_transaction_id
                WHERE e.customer_id IS NOT NULL AND a.customer_id IS NULL
                  AND COALESCE(a.status,'active') NOT IN ('reversed','merged')"""),
        }

    # acct_allocations: per-player money without ledger/customer anchors
    if "acct_allocations" in tables:
        acols = _cols(conn, "acct_allocations")
        out["acct_allocations"] = _one(conn, f"""
            SELECT COUNT(*) AS rows_total,
                   SUM(CASE WHEN item_id IS NULL THEN 1 ELSE 0 END) AS item_null,
                   {'SUM(CASE WHEN acct_transaction_id IS NULL THEN 1 ELSE 0 END)'
                    if 'acct_transaction_id' in acols else 'NULL'}
                       AS ledger_link_null,
                   {'SUM(CASE WHEN event_id IS NULL THEN 1 ELSE 0 END)'
                    if 'event_id' in acols else 'NULL'} AS event_id_null,
                   ROUND(SUM(total_collected),2) AS total_collected
            FROM acct_allocations""")
        out["acct_allocations"]["has_customer_id_column"] = "customer_id" in acols

    # godaddy_order_splits: split sums vs parent order entry
    if "godaddy_order_splits" in tables:
        out["godaddy_order_splits"] = _one(conn, """
            SELECT COUNT(*) AS rows_total,
                   SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS cid_null
            FROM godaddy_order_splits""")
        mism = [dict(r) for r in conn.execute("""
            SELECT s.transaction_id, ROUND(SUM(s.amount),2) AS split_sum,
                   ROUND(a.net_deposit,2) AS parent_net_deposit,
                   ROUND(a.total_amount,2) AS parent_amount
            FROM godaddy_order_splits s
            JOIN acct_transactions a ON a.id = s.transaction_id
            WHERE COALESCE(a.status,'active') NOT IN ('reversed','merged')
            GROUP BY s.transaction_id
            HAVING ABS(split_sum - parent_net_deposit) > 0.02
            LIMIT 15""")]
        out["godaddy_order_splits"]["splits_vs_parent_mismatch"] = len(mism)
        out["godaddy_order_splits"]["mismatch_examples"] = mism[:10]
        out["godaddy_order_splits"]["splits_on_nonactive_parent"] = _count(conn, """
            SELECT COUNT(*) FROM godaddy_order_splits s
            JOIN acct_transactions a ON a.id = s.transaction_id
            WHERE COALESCE(a.status,'active') IN ('reversed','merged')""")

    # bank reconciliation chain
    if "bank_deposits" in tables:
        out["bank_deposits_by_status"] = [dict(r) for r in conn.execute("""
            SELECT COALESCE(status,'(null)') AS status, COUNT(*) AS n,
                   ROUND(SUM(amount),2) AS total
            FROM bank_deposits GROUP BY 1""")]
    if "reconciliation_matches" in tables:
        out["reconciliation_matches"] = {
            "rows": _count(conn, "SELECT COUNT(*) FROM reconciliation_matches"),
            "match_to_nonactive_txn": _count(conn, """
                SELECT COUNT(*) FROM reconciliation_matches m
                JOIN acct_transactions a ON a.id = m.acct_transaction_id
                WHERE COALESCE(a.status,'active') IN ('reversed','merged')"""),
        }

    # items: paid rows floating outside the ledger. item_price is stored as
    # dollar-formatted TEXT ('$182.00') on the live DB — strip and CAST.
    if "items" in tables:
        cast = ("CAST(REPLACE(REPLACE(COALESCE(item_price,'0'),'$',''),"
                "',','') AS REAL)")
        out["items_money"] = _one(conn, f"""
            SELECT COUNT(*) AS paid_rows,
                   SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) AS cid_null,
                   ROUND(SUM({cast}),2) AS total
            FROM items
            WHERE {cast} != 0
              AND COALESCE(transaction_status,'') NOT IN ('rsvp_only')""")
        out["items_money_column_typing"] = [dict(r) for r in conn.execute(
            """SELECT typeof(item_price) AS storage_type, COUNT(*) AS n
               FROM items GROUP BY 1 ORDER BY n DESC""")]
        out["items_not_in_ledger"] = _one(conn, f"""
            SELECT COUNT(*) AS n,
                   ROUND(SUM(CAST(REPLACE(REPLACE(COALESCE(i.item_price,'0'),
                             '$',''),',','') AS REAL)),2) AS dollars
            FROM items i
            WHERE CAST(REPLACE(REPLACE(COALESCE(i.item_price,'0'),'$',''),
                       ',','') AS REAL) != 0
              AND i.merchant = 'The Golf Fellowship'
              AND COALESCE(i.transaction_status,'') NOT IN
                  ('rsvp_only','transferred')
              AND NOT EXISTS (SELECT 1 FROM acct_transactions a
                              WHERE a.item_id = i.id
                                AND COALESCE(a.status,'active') NOT IN ('reversed','merged'))
              AND NOT EXISTS (SELECT 1 FROM godaddy_order_splits s
                              WHERE s.item_id = i.id)
              AND NOT EXISTS (
                  SELECT 1 FROM acct_transactions a2
                  WHERE a2.order_id = i.order_id
                    AND i.order_id IS NOT NULL
                    AND COALESCE(a2.status,'active') NOT IN ('reversed','merged'))""")

    # customer_memberships money
    if "customer_memberships" in tables:
        out["customer_memberships"] = _one(conn, """
            SELECT COUNT(*) AS rows_total,
                   SUM(CASE WHEN price_paid IS NULL THEN 1 ELSE 0 END)
                       AS price_null,
                   SUM(CASE WHEN source_item_id IS NULL THEN 1 ELSE 0 END)
                       AS source_item_null
            FROM customer_memberships""")

    # contractor_payouts
    if "contractor_payouts" in tables:
        out["contractor_payouts"] = _one(conn, """
            SELECT COUNT(*) AS rows_total,
                   ROUND(SUM(amount_owed),2) AS owed,
                   ROUND(SUM(amount_paid),2) AS paid,
                   SUM(CASE WHEN event_id IS NULL THEN 1 ELSE 0 END)
                       AS event_id_null
            FROM contractor_payouts""") if "event_id" in _cols(
                conn, "contractor_payouts") else _one(conn, """
            SELECT COUNT(*) AS rows_total,
                   ROUND(SUM(amount_owed),2) AS owed,
                   ROUND(SUM(amount_paid),2) AS paid
            FROM contractor_payouts""")
    return out


# ────────────────────────────────────────────────────────────────────
# Section: dupes — double-count risk across the multiple writers
# ────────────────────────────────────────────────────────────────────
def audit_dupes(conn):
    out = {}
    amt = "total_amount"

    # Same (date, |amount|, customer_id) active in >1 source_ref family.
    # Transfer legs (source_ref ...-in / ...-out) are double-entry pairs by
    # design — exclude them so they don't read as duplicates.
    fam_expr = ("CASE WHEN source_ref IS NULL THEN '(none)' "
                "ELSE rtrim(source_ref,'0123456789') END")
    xfer_excl = ("(source_ref IS NULL OR (source_ref NOT LIKE '%-in' "
                 "AND source_ref NOT LIKE '%-out' "
                 "AND source_ref NOT LIKE 'xfer%'))")
    rows = [dict(r) for r in conn.execute(f"""
        SELECT date, ROUND(ABS({amt}),2) AS aamt,
               COALESCE(customer_id,-1) AS cid,
               COUNT(*) AS n,
               COUNT(DISTINCT {fam_expr}) AS families,
               GROUP_CONCAT(DISTINCT {fam_expr}) AS family_list
        FROM acct_transactions
        WHERE COALESCE(status,'active') NOT IN ('reversed','merged')
          AND ABS({amt}) > 0.01 AND {xfer_excl}
        GROUP BY 1,2,3
        HAVING COUNT(*) > 1 AND families > 1
        ORDER BY aamt DESC LIMIT 40""")]
    out["cross_writer_same_day_amount_customer"] = {
        "groups": len(rows), "examples": rows[:20]}

    # exp-promoted row still active although a venmo-bd twin exists
    out["exp_promoted_with_active_venmo_bd_twin"] = _count(conn, """
        SELECT COUNT(*) FROM acct_transactions e
        WHERE e.source_ref LIKE 'exp-promoted-%'
          AND COALESCE(e.status,'active') NOT IN ('reversed','merged')
          AND EXISTS (
              SELECT 1 FROM acct_transactions v
              WHERE v.source_ref LIKE 'venmo-bd-%'
                AND COALESCE(v.status,'active') NOT IN ('reversed','merged')
                AND v.date = e.date
                AND ABS(ABS(v.total_amount) - ABS(e.total_amount)) < 0.01)""")

    # Duplicate Detective history
    tables = _tables(conn)
    if "duplicate_merge_audit" in tables:
        out["duplicate_merge_audit"] = _one(conn, """
            SELECT COUNT(*) AS merges,
                   SUM(CASE WHEN reversed_at IS NOT NULL THEN 1 ELSE 0 END)
                       AS reversed
            FROM duplicate_merge_audit""")
    if "duplicate_dismissed_pairs" in tables:
        out["dismissed_pairs"] = _count(
            conn, "SELECT COUNT(*) FROM duplicate_dismissed_pairs")

    # Live detector, if importable (read-only scan)
    try:
        from . import database as db
        cands = db.find_duplicate_candidates()
        if isinstance(cands, dict):
            cands = cands.get("pairs") or cands.get("candidates") or []
        bands = defaultdict(int)
        for c in cands:
            conf = (c.get("confidence") or c.get("confidence_score") or 0
                    ) if isinstance(c, dict) else 0
            bands["high>=0.90" if conf >= 0.90 else
                  "med>=0.70" if conf >= 0.70 else "low<0.70"] += 1
        out["live_duplicate_candidates"] = {
            "total": len(cands), "by_confidence": dict(bands)}
    except Exception as exc:  # detector shape may drift — report, don't die
        out["live_duplicate_candidates"] = {"error": str(exc)}
    return out


SECTIONS = {
    "tables": audit_tables,
    "customer": audit_customer_lens,
    "fks": audit_fks,
    "ledger": audit_ledger,
    "money": audit_money,
    "dupes": audit_dupes,
}


def run(section: str = "summary") -> dict:
    """Entry point for the bridge. section = one section name, 'summary'
    (= everything), or comma-separated names."""
    section = (section or "summary").strip().lower()
    names = (list(SECTIONS) if section in ("summary", "all", "")
             else [s.strip() for s in section.split(",") if s.strip()])
    result = {"read_only": True, "sections": names}
    with managed_connection() as conn:
        for name in names:
            fn = SECTIONS.get(name)
            if not fn:
                result[name] = {"error": f"unknown section {name!r}; "
                                         f"valid: {sorted(SECTIONS)}"}
                continue
            try:
                result[name] = fn(conn)
            except Exception as exc:
                result[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return result
