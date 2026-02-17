# Email Summary Agent - Setup Guide

A Python agent that fetches emails from all your configured email accounts (matching the ones on your iPhone) and sends you a single summary digest every morning at 8 AM.

## Requirements

- Python 3.9+ (uses only standard library modules - no pip install needed)

## Quick Start

### 1. Create your config file

```bash
cp email_agent_config.example.json email_agent_config.json
```

Edit `email_agent_config.json` with your actual email credentials.

### 2. Set up App Passwords

**You must use app-specific passwords** (not your regular passwords) for each email provider:

| Provider | How to get an App Password |
|----------|---------------------------|
| **Gmail** | Google Account > Security > 2-Step Verification > App Passwords |
| **iCloud** | appleid.apple.com > Sign-In and Security > App-Specific Passwords |
| **Outlook** | account.microsoft.com > Security > App Passwords |
| **Yahoo** | login.yahoo.com > Account Security > Generate App Password |

### 3. Add all your iPhone email accounts

Add an entry to the `"accounts"` array in the config for each email address on your iPhone. Common IMAP servers:

| Provider | IMAP Server | Port |
|----------|------------|------|
| Gmail | `imap.gmail.com` | 993 |
| iCloud | `imap.mail.me.com` | 993 |
| Outlook/Hotmail | `outlook.office365.com` | 993 |
| Yahoo | `imap.mail.yahoo.com` | 993 |
| AOL | `imap.aol.com` | 993 |

### 4. Test with a dry run

```bash
python -m email_summary_agent --dry-run
```

This fetches your emails and prints the summary to the console without sending anything.

### 5. Run once immediately

```bash
python -m email_summary_agent --now
```

### 6. Start the daily scheduler

```bash
python -m email_summary_agent
```

This keeps running and sends a summary every day at the configured time (default: 8:00 AM).

## Running in the Background

### Option A: Using nohup (simple)

```bash
nohup python -m email_summary_agent > email_agent.log 2>&1 &
```

### Option B: Using a systemd service (Linux)

Create `/etc/systemd/system/email-summary-agent.service`:

```ini
[Unit]
Description=Email Summary Agent
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/Main
ExecStart=/usr/bin/python3 -m email_summary_agent
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl enable email-summary-agent
sudo systemctl start email-summary-agent
```

### Option C: Using cron (alternative to built-in scheduler)

Instead of running the agent's built-in scheduler, use cron to trigger it:

```bash
crontab -e
```

Add:

```
0 8 * * * cd /path/to/Main && python3 -m email_summary_agent --now >> email_agent.log 2>&1
```

### Option D: Using launchd (macOS)

Create `~/Library/LaunchAgents/com.golfellowship.emailagent.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.golfellowship.emailagent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-m</string>
        <string>email_summary_agent</string>
        <string>--now</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/Main</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/email-agent.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/email-agent.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.golfellowship.emailagent.plist
```

## Configuration Reference

| Key | Default | Description |
|-----|---------|-------------|
| `accounts` | (required) | Array of IMAP email accounts to fetch from |
| `summary_recipient` | (required) | Email address to receive the daily summary |
| `smtp` | (required) | SMTP server config for sending the summary |
| `schedule_hour` | `8` | Hour of day to send summary (0-23) |
| `schedule_minute` | `0` | Minute of hour to send summary (0-59) |
| `timezone` | `America/New_York` | Timezone for scheduling |
| `lookback_hours` | `24` | How far back to look for emails |
| `max_emails_per_account` | `50` | Max emails to fetch per account per run |

## Security Notes

- **Never commit `email_agent_config.json`** - it contains your passwords
- The example config (`email_agent_config.example.json`) is safe to commit
- Always use app-specific passwords, never your main account password
- The config file should already be in `.gitignore`
