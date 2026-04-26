# Mac Setup Guide (No Coding Experience Needed)

> **OUTDATED — Local setup is no longer the recommended path.**
> The app runs live on Railway at `https://tgf-tracker.up.railway.app`. For most users,
> no local setup is needed at all.
>
> If you do need a local copy: this guide was written for the original IMAP email setup.
> The app now uses **Microsoft Graph API** with Azure AD — see `README.md` and `.env.example`
> for current credentials. **Step 6 (App Password) is fully outdated** — you need Azure AD
> app registration credentials (Tenant ID, Client ID, Client Secret) instead.
> Steps 1–5 and 7–9 are still valid for local Python setup.

This guide walks you through every click and keystroke to get the TGF Transaction Tracker running on your Mac. You'll have a live dashboard showing all your Golf Fellowship orders with the ability to filter by side games, handicap, city, and more.

**Time required:** About 20 minutes for initial setup.

---

## What You'll Need Before Starting

1. **Your Microsoft 365 email credentials** (the email where Golf Fellowship order notifications arrive)
2. **An Anthropic API key** (this is what powers the AI parsing — instructions below)
3. **A credit card** for the Anthropic account (usage is roughly $0.01-0.03 per email, so pennies)

---

## Step 1: Open Terminal

Terminal is a built-in Mac app. You only need it for initial setup.

1. Press **Command + Space** (opens Spotlight search)
2. Type **Terminal**
3. Press **Enter**

A window with text will appear. This is where you'll paste commands.

**Tip:** To paste into Terminal, use **Command + V** (same as everywhere else).

---

## Step 2: Install Python

Your Mac may already have Python. Let's check.

**Paste this into Terminal and press Enter:**

```
python3 --version
```

- If you see `Python 3.x.x` — skip to Step 3.
- If you see `command not found` or it asks to install developer tools — follow the prompt, or:

1. Go to https://www.python.org/downloads/
2. Click the big yellow **"Download Python"** button
3. Open the downloaded `.pkg` file and follow the installer
4. When done, **quit Terminal** (Command + Q) and reopen it
5. Run `python3 --version` again to confirm

---

## Step 3: Download the Project

**Paste this into Terminal and press Enter:**

```
cd ~/Desktop && git clone https://github.com/thegolffellowship/Main.git
```

This puts a folder called `Main` on your Desktop.

> If you see `git: command not found`, your Mac will pop up a dialog asking to install developer tools. Click **Install**, wait for it to finish, then try the command again.

---

## Step 4: Set Up the App

**Paste these commands one at a time, pressing Enter after each:**

```
cd ~/Desktop/Main/transaction-tracker
```

```
python3 -m venv venv
```

```
source venv/bin/activate
```

After the last command, you should see `(venv)` at the beginning of your Terminal line. That means it worked.

**Now install the required packages:**

```
pip install -r requirements.txt
```

Wait for it to finish (you'll see text scrolling — that's normal). It installs Flask, the AI SDK, email tools, and other dependencies.

---

## Step 5: Get Your Anthropic API Key

This is the key that lets the app use Claude AI to read and understand your order emails.

1. Go to https://console.anthropic.com/
2. Click **Sign Up** (or sign in if you already have an account)
3. Once logged in, go to https://console.anthropic.com/settings/keys
4. Click **Create Key**
5. Name it "TGF Tracker" and click **Create**
6. **Copy the key immediately** — it starts with `sk-ant-` and you won't see it again

Keep this key handy for the next step.

---

## Step 6: Create Your Microsoft 365 App Password

The app needs a special password to read your email. **Your regular password will NOT work.**

1. Go to https://myaccount.microsoft.com/ and sign in
2. Click **"Security info"** in the left sidebar (or go directly to https://aka.ms/mysecurityinfo)
3. Click **"+ Add sign-in method"**
4. Choose **"App password"** from the dropdown
5. Give it a name like **"Transaction Tracker"**
6. Click **Next**
7. It will show you a password like `abcd efgh ijkl mnop` — **copy this immediately** (you won't see it again)

> **Can't find "App password"?** Your organization's admin may need to enable it. Ask your IT person: *"Can you enable App Passwords for my Microsoft 365 account?"*

> **Is IMAP enabled?** Ask your IT person to confirm: *"Is IMAP access turned on for my mailbox in the Exchange admin center?"* This is required for the app to read emails.

---

## Step 7: Configure the App

**Paste this into Terminal:**

```
cp .env.example .env
```

Now open the settings file in TextEdit:

```
open -a TextEdit .env
```

A text file will open. Change these lines (leave everything else as-is):

| Find this line | Change it to |
|---|---|
| `EMAIL_ADDRESS=your-email@yourdomain.com` | Your actual email, e.g. `EMAIL_ADDRESS=john@thegolffellowship.com` |
| `EMAIL_PASSWORD=your-app-password` | The App Password from Step 6 (remove any spaces), e.g. `EMAIL_PASSWORD=abcdefghijklmnop` |
| `ANTHROPIC_API_KEY=your-anthropic-api-key` | The API key from Step 5, e.g. `ANTHROPIC_API_KEY=sk-ant-api03-xxxxx` |
| `DAILY_REPORT_TO=your-email@yourdomain.com` | Your email to receive the daily report, e.g. `DAILY_REPORT_TO=john@thegolffellowship.com` |

**Optional — Connector API Key** (only needed if you want external systems to push data in):

| Find this line | Change it to |
|---|---|
| `CONNECTOR_API_KEY=your-connector-api-key` | Any random secret string, or generate one (see below) |

To generate a secure connector key, paste this into Terminal:
```
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy the output and paste it as `CONNECTOR_API_KEY`.

**Save the file** (Command + S) and close TextEdit.

---

## Step 8: Start the App

**Paste this into Terminal:**

```
python3 app.py
```

You should see output like:

```
INFO: Database initialized
INFO: Scheduler started — checking inbox every 15 minutes
INFO: Daily report scheduled for 07:00
 * Running on http://0.0.0.0:5000
```

---

## Step 9: Open the Dashboard

1. Open **Safari** (or Chrome, any browser)
2. Go to **http://localhost:5000**
3. You'll see the TGF Transaction Tracker dashboard

Click the **"Check Now"** button to do an immediate scan of your inbox. The first scan may take a minute since each email gets sent to AI for parsing.

---

## What You'll See

The dashboard shows a table with these columns (each one is sortable and filterable):

- **Date** — order date
- **Customer** — who placed the order
- **Item** — event name (e.g., "Feb 22 - LaCANTERA")
- **Price** — price for this specific item
- **Chapter** — TGF chapter (Austin, San Antonio, Dallas, Houston, Galveston)
- **Course** — golf course name
- **Handicap** — player's handicap
- **Side Games** — selected side games (NET Points Race, City Match Play, etc.)
- **Tee** — tee choice
- **Status** — user status (MEMBER, 1st TIMER, GUEST, MANAGER)
- **Holes** — 9 or 18
- **Order ID** — order confirmation number

Use the **search box** to find anything. Use the **column filter** dropdown to search within just one column (e.g., only Side Games). Click **Export CSV** to download as a spreadsheet.

---

## Make It Run Automatically (So You Never Have to Think About It)

Right now the app only runs when Terminal is open. Here's how to make it start whenever you turn on your Mac and keep running in the background.

### Create an Auto-Start Service

**Step 1: Paste this entire block into Terminal as one command:**

```
cat > ~/Library/LaunchAgents/com.tgf.tracker.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tgf.tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>VENV_PATH/bin/gunicorn</string>
        <string>app:app</string>
        <string>--bind</string>
        <string>0.0.0.0:5000</string>
        <string>--workers</string>
        <string>2</string>
        <string>--timeout</string>
        <string>120</string>
    </array>
    <key>WorkingDirectory</key>
    <string>WORK_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/tgf-tracker.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/tgf-tracker-error.log</string>
</dict>
</plist>
PLIST
```

**Step 2: Fill in your paths (paste these two commands):**

```
cd ~/Desktop/Main/transaction-tracker && source venv/bin/activate
```

```
sed -i '' "s|VENV_PATH|$(pwd)/venv|g; s|WORK_DIR|$(pwd)|g" ~/Library/LaunchAgents/com.tgf.tracker.plist
```

**Step 3: Activate it:**

```
launchctl load ~/Library/LaunchAgents/com.tgf.tracker.plist
```

**That's it!** The app will now:

- Start automatically when you log in to your Mac
- Restart itself if it crashes
- Check your inbox every 15 minutes
- Send you a daily report at 7 AM
- Be available at http://localhost:5000 at all times

### Controlling the Auto-Start Service

Open Terminal and use these commands:

| What you want to do | Command |
|---|---|
| Stop the app | `launchctl stop com.tgf.tracker` |
| Start the app | `launchctl start com.tgf.tracker` |
| Disable auto-start | `launchctl unload ~/Library/LaunchAgents/com.tgf.tracker.plist` |
| Re-enable auto-start | `launchctl load ~/Library/LaunchAgents/com.tgf.tracker.plist` |
| View logs | `cat /tmp/tgf-tracker.log` |
| View error logs | `cat /tmp/tgf-tracker-error.log` |

---

## Sharing the Dashboard with Your TGF Managers

### Same Wi-Fi / Office Network

If you and your managers are on the same network:

1. Find your Mac's IP: **System Settings > Wi-Fi > Details > IP Address** (looks like `192.168.1.42`)
2. Managers open their browser and go to `http://192.168.1.42:5000`

### From Anywhere (Public URL)

For a link that works from any internet connection, deploy to a cloud service:

**Railway (easiest — free tier available):**
1. Go to https://railway.app and sign up with GitHub
2. Click **New Project** > **Deploy from GitHub Repo**
3. Select this repo, set the root directory to `transaction-tracker`
4. Add your environment variables in the Railway dashboard (copy them from your `.env` file)
5. Railway gives you a public URL like `https://tgf-tracker.up.railway.app`

Share that URL with your managers — they can bookmark it and check orders anytime.

---

## Everyday Use Cheat Sheet

| What you want to do | How |
|---|---|
| View the dashboard | Open http://localhost:5000 in your browser |
| Force an inbox check | Click **Check Now** on the dashboard |
| Send the daily report now | Click **Send Report** on the dashboard |
| Search for a player | Type their name in the search box |
| Filter by side games only | Select "Side Games" from the column filter dropdown, then type |
| Sort by side games | Click the **Side Games** column header |
| Export all data | Click **Export CSV** |
| Stop the app | `launchctl stop com.tgf.tracker` |
| Restart after changes | `launchctl stop com.tgf.tracker && launchctl start com.tgf.tracker` |

---

## Updating After Code Changes

If the code gets updated:

```
cd ~/Desktop/Main/transaction-tracker
git pull
source venv/bin/activate
pip install -r requirements.txt
launchctl stop com.tgf.tracker
launchctl start com.tgf.tracker
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `command not found: python3` | Reinstall Python from https://www.python.org/downloads/ |
| `command not found: git` | Install Xcode tools: run `xcode-select --install` in Terminal |
| `ModuleNotFoundError` | Activate the venv: `cd ~/Desktop/Main/transaction-tracker && source venv/bin/activate` |
| App starts but finds no emails | Click **Check Now**. Verify your App Password and that IMAP is enabled. |
| `Login failed` or `Authentication failed` | Double-check email + App Password in `.env`. No extra spaces. |
| `IMAP connection error` | Ask your admin to confirm IMAP is enabled in Exchange admin center. |
| `ANTHROPIC_API_KEY not configured` | Add your key to `.env`. Get one at https://console.anthropic.com/settings/keys |
| AI parses 0 items | Check your API key is valid and has credits at https://console.anthropic.com/settings/billing |
| Daily report not arriving | Check `DAILY_REPORT_TO` in `.env`. View logs: `cat /tmp/tgf-tracker-error.log` |
| `Address already in use` | Another copy is running. Run `launchctl stop com.tgf.tracker` then try again. |
| Dashboard won't load | Make sure the app is running. Check: `launchctl list | grep tgf` |
| Connector returns 401 | The `X-API-Key` header must exactly match `CONNECTOR_API_KEY` in `.env` |
