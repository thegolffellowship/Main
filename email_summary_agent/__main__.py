"""
CLI entry point for the email summary agent.

Usage:
    python -m email_summary_agent              Run on daily schedule (default: 8:00 AM)
    python -m email_summary_agent --now        Run once immediately and exit
    python -m email_summary_agent --dry-run    Run once, print summary, don't send email
    python -m email_summary_agent --config /path/to/config.json
"""

import argparse
import sys

from email_summary_agent.config import load_config
from email_summary_agent.scheduler import run_once, run_scheduled


def main():
    parser = argparse.ArgumentParser(
        description="Email Summary Agent - Daily email digest from all your accounts"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration JSON file (default: email_agent_config.json)",
        default=None,
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run once immediately and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and summarize but don't send the email (prints to console)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.dry_run:
        config["dry_run"] = True
        run_once(config)
    elif args.now:
        run_once(config)
    else:
        try:
            run_scheduled(config)
        except KeyboardInterrupt:
            print("\nAgent stopped.")
            sys.exit(0)


if __name__ == "__main__":
    main()
