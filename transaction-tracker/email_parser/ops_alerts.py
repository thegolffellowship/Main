"""Operational alerting.

When the app's Claude/Anthropic calls start failing for a reason the owner
must act on — the org is out of API credit, or the API key was revoked /
rotated — surface it in their inbox instead of letting it show up as a
surprise bank charge or a silent gap in the dashboard.

Design notes:

* Throttled to one email per ``ALERT_THROTTLE_HOURS``. The expense
  classifier runs every ~5 minutes, so without a throttle a dead key would
  generate an email storm.
* The throttle marker is persisted in the SQLite DB, which lives on the
  Railway persistent volume, so a redeploy crash-loop also can't spam.
* The throttle is only stamped *after* a successful send — if the alert
  email itself fails, the next cycle retries rather than going silent for
  hours.
* ``maybe_alert_anthropic_billing`` never raises: alerting must not break
  the caller's own error-handling path.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

ALERT_THROTTLE_HOURS = 6
_ALERT_KEY = "anthropic_billing"


def _is_billing_failure(exc: BaseException) -> bool:
    """True only for failures the owner can fix by adding credit or fixing
    the key — out of API credit, or an invalid/revoked/forbidden key.

    Deliberately excludes generic BadRequestError (bad prompt, token
    overflow) and RateLimitError (transient, not a "send money" situation).
    """
    try:
        import anthropic
    except Exception:
        anthropic = None

    msg = (getattr(exc, "message", None) or str(exc) or "").lower()
    if "credit balance is too low" in msg:
        return True
    if anthropic is not None and isinstance(
        exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)
    ):
        return True
    return False


def _recently_alerted(conn) -> bool:
    """Read-only throttle check. Does not stamp — see _record_alert_sent."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS system_alert_state ("
        "alert_key TEXT PRIMARY KEY, last_sent_epoch REAL)"
    )
    row = conn.execute(
        "SELECT last_sent_epoch FROM system_alert_state WHERE alert_key = ?",
        (_ALERT_KEY,),
    ).fetchone()
    if not row or not row[0]:
        return False
    return (time.time() - float(row[0])) < ALERT_THROTTLE_HOURS * 3600


def _record_alert_sent(conn) -> None:
    """Stamp the throttle. Called only after a successful send."""
    conn.execute(
        "INSERT INTO system_alert_state (alert_key, last_sent_epoch) "
        "VALUES (?, ?) ON CONFLICT(alert_key) DO UPDATE SET "
        "last_sent_epoch = excluded.last_sent_epoch",
        (_ALERT_KEY, time.time()),
    )


def maybe_alert_anthropic_billing(exc: BaseException) -> None:
    """Call from any 'Claude call failed' except handler.

    No-op unless ``exc`` is a billing/auth failure and the throttle window
    has elapsed. Never raises.
    """
    try:
        if not _is_billing_failure(exc):
            return

        from email_parser.database import _connect
        from email_parser.fetcher import send_mail_graph

        with _connect() as conn:
            if _recently_alerted(conn):
                logger.info("Anthropic billing alert suppressed (throttled)")
                return

        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_id = os.getenv("AZURE_CLIENT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        from_address = os.getenv("EMAIL_ADDRESS")
        to_address = (
            os.getenv("ANTHROPIC_ALERT_EMAIL_TO")
            or os.getenv("COO_EMAIL_TO")
            or from_address
        )
        if not all([tenant_id, client_id, client_secret, from_address, to_address]):
            logger.warning(
                "Anthropic billing failure detected but email creds not "
                "configured — cannot send alert. Error: %s", exc,
            )
            return

        detail = (getattr(exc, "message", None) or str(exc) or "")[:500]
        subject = "TGF ALERT: Claude/Anthropic budget exhausted — action needed"
        html_body = f"""<p>Hi Kerry,</p>
<p><strong>The transaction tracker's Claude API calls are failing.</strong></p>
<p>Incoming GoDaddy orders and expense emails are <strong>not lost</strong> —
they stay queued in the inbox and will be processed automatically once Claude
is working again — but the dashboard will not show new activity until then.</p>
<p><strong>What to do:</strong> open
<a href="https://console.anthropic.com/settings/billing">console.anthropic.com
&rarr; Billing</a> and add credit. If you recently rotated the API key, update
<code>ANTHROPIC_API_KEY</code> in the Railway environment instead.</p>
<p style="font-size:0.85rem;color:#6b7280;">Technical detail: {detail}</p>
<p style="font-size:0.8rem;color:#9ca3af;">You'll get at most one of these
every {ALERT_THROTTLE_HOURS} hours while the problem persists. &mdash; TGF System</p>"""

        ok = send_mail_graph(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            from_address=from_address,
            to_address=to_address,
            subject=subject,
            html_body=html_body,
        )
        if ok:
            with _connect() as conn:
                _record_alert_sent(conn)
            logger.warning(
                "Anthropic billing-failure alert emailed to %s", to_address
            )
        else:
            logger.error(
                "Anthropic billing-failure detected but alert email send "
                "FAILED — will retry next cycle"
            )
    except Exception:
        logger.exception("maybe_alert_anthropic_billing crashed (non-fatal)")
