"""
Scheduler for the email summary agent.

Runs the fetch-summarize-send pipeline on a daily schedule using
a lightweight threading-based approach (no external dependencies).
"""

import threading
import time
from datetime import datetime, timedelta

from email_summary_agent.fetcher import fetch_all_accounts
from email_summary_agent.summarizer import build_summary
from email_summary_agent.sender import send_summary


def run_once(config):
    """Execute one fetch-summarize-send cycle."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting email summary run...")

    emails = fetch_all_accounts(config)
    print(f"  Total emails fetched: {len(emails)}")

    subject, plain, html = build_summary(emails)

    if config.get("dry_run"):
        print(f"\n  --- DRY RUN: Summary not sent ---")
        print(f"  Subject: {subject}")
        print(f"  Recipient: {config['summary_recipient']}")
        print(f"\n{plain}")
        return

    send_summary(
        config["smtp"],
        config["summary_recipient"],
        subject,
        plain,
        html,
    )
    print(f"  Done.")


def _seconds_until(hour, minute, tz_name=None):
    """Calculate seconds until the next occurrence of hour:minute in the given timezone."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name) if tz_name else None
    except ImportError:
        tz = None

    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_scheduled(config):
    """
    Run the agent on a daily schedule.

    Calculates the wait time until the next scheduled run and sleeps,
    then executes and repeats.
    """
    hour = config.get("schedule_hour", 8)
    minute = config.get("schedule_minute", 0)
    tz_name = config.get("timezone", "America/New_York")

    print(f"Email Summary Agent started.")
    print(f"  Schedule: daily at {hour:02d}:{minute:02d} ({tz_name})")
    print(f"  Accounts: {len(config['accounts'])}")
    print(f"  Recipient: {config['summary_recipient']}")
    print(f"  Lookback: {config.get('lookback_hours', 24)}h")

    while True:
        wait = _seconds_until(hour, minute, tz_name)
        next_run = datetime.now() + timedelta(seconds=wait)
        print(f"\n  Next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')} (in {wait/3600:.1f}h)")

        # Sleep in 60-second intervals so the process can be interrupted cleanly
        slept = 0
        while slept < wait:
            chunk = min(60, wait - slept)
            time.sleep(chunk)
            slept += chunk

        try:
            run_once(config)
        except Exception as e:
            print(f"  ERROR during run: {e}")
