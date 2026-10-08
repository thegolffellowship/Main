# Off-site replication (Litestream -> Cloudflare R2)

Hard gate (a) of CA #731: continuous off-site replication. Built 2026-10-02
(Health lane; CA #834 chose R2, Kerry set the keys, CoS go #1161).

**What runs.** `scripts/start.sh` (the Railway start command, `railway.toml`
and `Procfile`) starts `litestream replicate` BESIDE the app, then `exec`s
gunicorn exactly as before. Replication can never stop the app: a missing
binary, bad config or unreachable bucket only stops replication, and the
digest says so. Litestream restarts itself 30 s after any exit.

**What it replicates.** Both SQLite files, every 10 s, into one bucket
(`tgf-tracker-replica`): `transactions.db` and `transactions_gg_archive.db`,
each under its own folder. Snapshots every 6 h / 24 h, a week of point-in-time
restore. Config: `litestream.yml` (secret-free; `${VAR}` expands from the
environment).

**Railway variables (Kerry sets them; never post a value):**
`LITESTREAM_ACCESS_KEY_ID`, `LITESTREAM_SECRET_ACCESS_KEY` (read natively by
Litestream), `LITESTREAM_R2_ENDPOINT`, `LITESTREAM_R2_BUCKET`. If any of the
four is missing, startup is identical to before and the digest says
"REPLICATION not configured".

**The binary.** Pinned (v0.3.13, sha256 in `scripts/install_litestream.py`),
fetched ONCE in the background into `<volume>/bin/litestream`, so the build
system is untouched and a deploy never re-downloads it. `LITESTREAM_NO_FETCH=1`
turns the download off.

**What the digest shows** (`email_parser/replication.py`, `health.py`): a
REPLICATION line (streaming, lag, generations, latest write) and findings:
not configured = info (not filed); no binary / process not running / lag over
300 s = HIGH; unreadable replica or no generation yet = MEDIUM.

**The drill (gate (a) passes only on this).** `scoring-rehearsal:restore|replica`
restores the main database from R2 into the rehearsal folder (never the live
file), checks integrity and counts against live, scrubs, and installs it as
the scratch copy, exactly like the OneDrive drill. Recorded as app setting
`rehearsal_drill_replica` (`scoring-rehearsal:status` -> `last_replica_drill`).
The GG archive file is replicated but not part of the inline drill (its restore
is a 400 MB download); restore it by hand with `litestream restore` if ever
needed.

**Real restore** (disaster): `litestream restore -config litestream.yml -o <new path> <db path>`
with the four variables and `DATABASE_PATH` / `GG_ARCHIVE_PATH` set; add
`-timestamp <RFC3339>` for a point in time.

Guard: `test_replication.py` (real litestream binary + file replica when
`LITESTREAM_BIN` is set; the start script's fallbacks, the digest findings
and the drill end to end). R2 itself can only be proven on production.


## Status read cost (v2.525.23)
`replication.status()` runs `litestream generations` for the main file and the GG archive file; each lists the R2 bucket, so the cost grows with the replica's history (11.6 s then 16.4 s through the health bridge on 10/7-10/8). The two run in parallel, the result is cached for 900 s, and only the scheduled digest (`build_health_report(record_size=True)`) passes `fresh=True`. `running` is re-checked on every call. If the listing ever passes ~10 s even in parallel, shorten the retention in `litestream.yml` rather than raising the timeout.
