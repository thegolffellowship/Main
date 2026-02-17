# Email Summary Agent - Setup Guide

This agent checks all your email accounts every morning at 8 AM and sends you one email with a summary of everything that came in overnight.

We'll set it up on **PythonAnywhere**, a free website that runs it for you 24/7. You don't need to leave a computer on.

---

## What You'll Need Before Starting

- About 15-20 minutes
- Your iPhone (to look up which email accounts you have)
- A computer or tablet with a web browser (to set things up on PythonAnywhere)

---

## Step 1: Find Out Which Email Accounts Are on Your iPhone

On your iPhone:

1. Open **Settings**
2. Scroll down and tap **Mail**
3. Tap **Accounts**
4. You'll see a list like "iCloud", "Gmail", "Outlook", etc.
5. **Write down each email address** - you'll need them in Step 4

---

## Step 2: Create App Passwords for Each Email Account

For security, email providers don't let apps use your normal password. Instead, you create a special "app password" for each account. This is a one-time thing.

**Do this for each email account on your iPhone:**

### If you have a Gmail account (anything @gmail.com):

1. On your computer, go to **myaccount.google.com**
2. Click **Security** on the left side
3. Make sure **2-Step Verification** is turned ON (if it's not, turn it on first)
4. Go back to the Security page and search for **App Passwords**
5. For the app name, type **Email Summary Agent** and click **Create**
6. Google will show you a 16-letter password like `abcd efgh ijkl mnop`
7. **Copy this password and save it somewhere** - you'll need it in Step 4

### If you have an iCloud account (anything @icloud.com, @me.com, or @mac.com):

1. On your computer, go to **appleid.apple.com**
2. Sign in with your Apple ID
3. Go to **Sign-In and Security**
4. Click **App-Specific Passwords**
5. Click the **+** button, name it **Email Summary Agent**
6. Apple will show you a password like `abcd-efgh-ijkl-mnop`
7. **Copy this password and save it somewhere** - you'll need it in Step 4

### If you have an Outlook/Hotmail account (@outlook.com, @hotmail.com, @live.com):

1. On your computer, go to **account.microsoft.com**
2. Sign in and go to **Security**
3. Click **Advanced security options**
4. Scroll to **App passwords** and click **Create a new app password**
5. Microsoft will show you a password
6. **Copy this password and save it somewhere** - you'll need it in Step 4

### If you have a Yahoo account (@yahoo.com):

1. On your computer, go to **login.yahoo.com**
2. Go to **Account Security**
3. Click **Generate app password**
4. Select **Other App**, name it **Email Summary Agent**
5. Yahoo will show you a password
6. **Copy this password and save it somewhere** - you'll need it in Step 4

---

## Step 3: Sign Up for PythonAnywhere (Free)

1. Go to **www.pythonanywhere.com** in your browser
2. Click **Pricing & signup**
3. Click **Create a Beginner account** (the free one)
4. Fill in a username, email, and password, then create the account
5. Confirm your email if they ask you to

---

## Step 4: Upload the Agent and Set Up Your Config

### 4a. Open a console

1. After logging in to PythonAnywhere, click the **Dashboard** link at the top
2. Under **New console**, click **Bash**
3. A black screen with a command line will appear - this is where you'll type commands

### 4b. Download the agent code

Type this into the console and press Enter:

```
git clone https://github.com/thegolffellowship/Main.git
```

Wait for it to finish.

### 4c. Create your personal config file

Type this and press Enter:

```
cp Main/email_agent_config.example.json Main/email_agent_config.json
```

### 4d. Edit the config file with your email accounts

Type this and press Enter:

```
nano Main/email_agent_config.json
```

A text editor will open. You need to replace the placeholder values with your real information.

**Here's what to change:**

For each email account on your iPhone, you need a block that looks like this. Delete the example accounts and replace them with yours.

**For a Gmail account**, the block looks like:
```json
{
    "label": "My Gmail",
    "email": "yourname@gmail.com",
    "password": "the-app-password-from-step-2",
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "use_ssl": true
}
```

**For an iCloud account**, the block looks like:
```json
{
    "label": "My iCloud",
    "email": "yourname@icloud.com",
    "password": "the-app-password-from-step-2",
    "imap_server": "imap.mail.me.com",
    "imap_port": 993,
    "use_ssl": true
}
```

**For an Outlook/Hotmail account**, the block looks like:
```json
{
    "label": "My Outlook",
    "email": "yourname@outlook.com",
    "password": "the-app-password-from-step-2",
    "imap_server": "outlook.office365.com",
    "imap_port": 993,
    "use_ssl": true
}
```

**For a Yahoo account**, the block looks like:
```json
{
    "label": "My Yahoo",
    "email": "yourname@yahoo.com",
    "password": "the-app-password-from-step-2",
    "imap_server": "imap.mail.yahoo.com",
    "imap_port": 993,
    "use_ssl": true
}
```

**Important:** If you have more than one account, put a comma between each block. If it's the last account, no comma after it.

**Also change these two sections:**

`"summary_recipient"` - Change this to the email address where you want to RECEIVE your daily summary (probably your main email).

`"smtp"` section - This is the account that SENDS the summary. Use one of your Gmail accounts if you have one:
```json
"smtp": {
    "server": "smtp.gmail.com",
    "port": 587,
    "email": "yourname@gmail.com",
    "password": "the-same-app-password-for-this-gmail",
    "use_tls": true
}
```

**Also change the timezone** if you're not on the US East Coast. Common options:
- `America/New_York` - Eastern Time
- `America/Chicago` - Central Time
- `America/Denver` - Mountain Time
- `America/Los_Angeles` - Pacific Time

**When you're done editing:**
1. Press **Ctrl + O** (that's the letter O) then press **Enter** to save
2. Press **Ctrl + X** to exit the editor

### 4e. Test it

Type this and press Enter:

```
cd Main && python3 -m email_summary_agent --dry-run
```

You should see it connect to each account and print a summary. If you see errors, double-check your email addresses and app passwords in the config file.

If the dry run looks good, try sending a real one:

```
python3 -m email_summary_agent --now
```

Check the email address you put in `summary_recipient` - you should have a summary email.

---

## Step 5: Schedule It to Run Every Morning

1. Go back to PythonAnywhere (click the PythonAnywhere logo at the top left)
2. Click the **Tasks** tab at the top of the page
3. Under **Scheduled tasks**, you'll see a section to create a new task
4. Set the time to **08:00** (or whatever time you want your summary)
5. In the command box, type:

```
cd ~/Main && python3 -m email_summary_agent --now
```

6. Click **Create**

**That's it!** Every morning at 8 AM, PythonAnywhere will run the agent, and you'll get a summary email on your phone.

---

## Troubleshooting

**"Login failed" error for Gmail:**
Make sure 2-Step Verification is turned on in your Google account BEFORE creating the app password. The app password won't work without it.

**"Login failed" error for iCloud:**
Make sure you're using an app-specific password from appleid.apple.com, not your regular Apple ID password.

**No emails showing up:**
The agent only looks at emails from the last 24 hours by default. If your inbox has been quiet, try sending yourself a test email first.

**Wrong time zone:**
Edit the config file and change the `timezone` value. Re-run the test to verify.

**Need to change settings later:**
Go to PythonAnywhere > Dashboard > Files > navigate to `Main/email_agent_config.json` and edit it there.

---

## Notes

- **Free PythonAnywhere accounts** allow one scheduled task per day, which is exactly what we need
- Your passwords are stored only in your PythonAnywhere account - they're never uploaded to GitHub
- To stop the daily summary, just delete the scheduled task in PythonAnywhere
