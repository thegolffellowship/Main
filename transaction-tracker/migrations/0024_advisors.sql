-- ADVISORS (Kerry 2026-10-15 ~12:15 PM, rule 3b: "Yep B." — CoS #1905).
-- Outside advisors (the SA advisory board first: Jeff Young, Daniel South,
-- Mary Wade) open CONCEPTS and the PII-free member pages through a signed,
-- per-person magic link. One row per advisor; nothing here is a customer
-- record and no PII beyond the advisor's own name and email.
--   token_version  bumped to revoke this advisor's outstanding links only
--   revoked_at     set when Kerry revokes; a revoked advisor's link shows
--                  "this link is no longer active"
--   last_seen_at   the last request made on the advisor's link session
-- Pages opened are logged in agent_action_log (agent 'advisor:<id>'), not a
-- second table. Reversible: DROP TABLE advisors.
CREATE TABLE IF NOT EXISTS advisors (
    advisor_id     INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    email          TEXT,
    token_version  INTEGER NOT NULL DEFAULT 1,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by     TEXT,
    revoked_at     TIMESTAMP,
    last_seen_at   TIMESTAMP
);
