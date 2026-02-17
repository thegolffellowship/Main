"""
Configuration loader for email summary agent.

Reads account credentials and agent settings from a JSON config file.
Supports multiple IMAP email accounts and one SMTP delivery account.
"""

import json
import os
import sys

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "email_agent_config.json"
)


def load_config(path=None):
    """Load and validate the agent configuration file."""
    path = path or DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        print(f"Config file not found: {path}")
        print("Copy email_agent_config.example.json to email_agent_config.json and fill in your details.")
        sys.exit(1)

    with open(path, "r") as f:
        cfg = json.load(f)

    # Validate required top-level keys
    for key in ("accounts", "summary_recipient", "smtp"):
        if key not in cfg:
            raise ValueError(f"Missing required config key: '{key}'")

    # Validate each account
    for i, acct in enumerate(cfg["accounts"]):
        for field in ("email", "password", "imap_server"):
            if field not in acct:
                raise ValueError(f"Account #{i} missing required field: '{field}'")
        acct.setdefault("imap_port", 993)
        acct.setdefault("use_ssl", True)
        acct.setdefault("label", acct["email"])

    # Validate SMTP
    smtp = cfg["smtp"]
    for field in ("server", "port", "email", "password"):
        if field not in smtp:
            raise ValueError(f"SMTP config missing required field: '{field}'")
    smtp.setdefault("use_tls", True)

    # Defaults
    cfg.setdefault("schedule_hour", 8)
    cfg.setdefault("schedule_minute", 0)
    cfg.setdefault("timezone", "America/New_York")
    cfg.setdefault("lookback_hours", 24)
    cfg.setdefault("max_emails_per_account", 50)

    return cfg
