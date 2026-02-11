# Mac Setup Guide (No Coding Experience Needed)

This guide walks you through every click and keystroke to get the Transaction Email Tracker running on your Mac with Microsoft 365 email.

---

## Step 1: Open Terminal

Terminal is a built-in Mac app. You only need it for initial setup.

1. Press **Command + Space** (opens Spotlight search)
2. Type **Terminal**
3. Press **Enter**

A white or black window with text will appear. This is where you'll paste commands.

---

## Step 2: Install Python

Your Mac may already have Python. Let's check.

**Paste this into Terminal and press Enter:**

```
python3 --version
```

- If you see something like `Python 3.x.x` — you're good, skip to Step 3.
- If you see `command not found` or it asks you to install developer tools — follow the prompt to install, or continue below.

**If Python is not installed:**

1. Go to https://www.python.org/downloads/
2. Click the big yellow **"Download Python"** button
3. Open the downloaded `.pkg` file and follow the installer (just keep clicking Continue/Agree/Install)
4. When done, **close Terminal completely** (Command + Q) and reopen it
5. Run `python3 --version` again to confirm it works

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

**Paste these three commands one at a time, pressing Enter after each:**

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

Wait for it to finish (you'll see a bunch of text scrolling — that's normal).

---

## Step 5: Create Your Microsoft 365 App Password

The app needs a special password to read your email. Your regular password will NOT work.

1. Go to https://myaccount.microsoft.com/ and sign in
2. Click **"Security info"** in the left sidebar (or go directly to https://aka.ms/mysecurityinfo)
3. Click **"+ Add sign-in method"**
4. Choose **"App password"** from the dropdown
5. Give it a name like **"Transaction Tracker"**
6. Click **Next**
7. It will show you a password like `abcd efgh ijkl mnop` — **copy this immediately** (you won't see it again)

> **Can't find "App password"?** Your organization's admin may need to enable it. Ask your IT person: "Can you enable App Passwords for my Microsoft 365 account?"

> **Is IMAP enabled?** Ask your IT person to confirm: "Is IMAP access turned on for my mailbox in the Exchange admin center?" This is required for the app to connect.

---

## Step 6: Configure the App

**Paste this into Terminal:**

```
cp .env.example .env
```

Now open the settings file in TextEdit:

```
open -a TextEdit .env
```

A text file will open. Change these lines:

| Line | Change to |
|------|-----------|
| `EMAIL_ADDRESS=your-email@yourdomain.com` | Your actual email, e.g. `EMAIL_ADDRESS=john@thegolffellowship.com` |
| `EMAIL_PASSWORD=your-app-password` | The app password from Step 5, e.g. `EMAIL_PASSWORD=abcdefghijklmnop` |

Leave everything else as-is. **Save the file** (Command + S) and close TextEdit.

---

## Step 7: Start the App

**Paste this into Terminal:**

```
python3 app.py
```

You should see output like:

```
INFO: Scheduler started — checking inbox every 15 minutes
 * Running on http://0.0.0.0:5000
```

---

## Step 8: Open the Dashboard

1. Open **Safari** (or Chrome, any browser)
2. Go to **http://localhost:5000**
3. You'll see the transaction dashboard

Click the **"Check Now"** button to do an immediate scan of your inbox.

---

## Everyday Use

- **To start the app:** Open Terminal, then paste:
  ```
  cd ~/Desktop/Main/transaction-tracker && source venv/bin/activate && python3 app.py
  ```
- **To view the dashboard:** Open http://localhost:5000 in your browser
- **To stop the app:** Click on the Terminal window and press **Control + C**
- The app must be running for the dashboard to work. If you close Terminal or shut down your Mac, you'll need to start it again.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `command not found: python3` | Reinstall Python from https://www.python.org/downloads/ |
| `command not found: git` | Install Xcode tools: run `xcode-select --install` in Terminal |
| App starts but finds no emails | Click "Check Now" on the dashboard. If still nothing, verify your App Password and that IMAP is enabled. |
| `Login failed` or `Authentication failed` | Double-check your email address and app password in the `.env` file. Make sure there are no extra spaces. |
| `IMAP connection error` | Ask your IT admin to confirm IMAP is enabled for your Microsoft 365 account. |
| `Address already in use` | Another copy is already running. Close all Terminal windows and try again. |
| Page won't load in browser | Make sure Terminal is still running with the app. Don't close it. |
