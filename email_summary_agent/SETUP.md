# Email Summary Agent - Setup Guide

This agent checks your three email accounts every morning at 8 AM and sends you one email to **niester@mac.com** with a summary of everything that came in overnight.

Your accounts:
- **niester@mac.com** (iCloud)
- **kerry@thegolffellowship.com** (Microsoft 365)
- **admin@thegolffellowship.com** (Microsoft 365)

We'll set it up on **PythonAnywhere**, a free website that runs it for you 24/7. You don't need to leave a computer on.

---

## What You'll Need

- About 15 minutes
- A computer or tablet with a web browser

---

## Step 1: Create an App Password for Your iCloud Account

Apple doesn't let apps use your regular Apple ID password, so you need to create a special one-time "app password." This only takes a minute.

1. On your computer, go to **appleid.apple.com**
2. Sign in with the Apple ID that owns **niester@mac.com**
3. Click **Sign-In and Security**
4. Click **App-Specific Passwords**
5. Click the **+** button
6. Name it **Email Summary Agent** and click Create
7. Apple will show you a password that looks like `abcd-efgh-ijkl-mnop`
8. **Copy this password and save it somewhere safe** (a note on your phone is fine) - you'll need it in Step 3

---

## Step 2: Create App Passwords for Your Microsoft 365 Accounts

You need to do this for both **kerry@thegolffellowship.com** and **admin@thegolffellowship.com**.

**For each Microsoft 365 account:**

1. Go to **mysignins.microsoft.com/security-info**
2. Sign in with that Microsoft 365 account
3. Click **+ Add sign-in method**
4. Choose **App password** from the dropdown
5. Name it **Email Summary Agent** and click **Next**
6. Microsoft will show you a password
7. **Copy this password and save it** - you'll need it in Step 3

**Do this twice** - once for kerry@ and once for admin@.

> **Note:** If your Microsoft 365 admin has disabled app passwords, you may need to enable them in the Microsoft 365 admin center under Settings > Org settings > Security & privacy > Azure multi-factor authentication > Additional cloud-based MFA settings.

---

## Step 3: Sign Up for PythonAnywhere and Set Up the Agent

### 3a. Create a free account

1. Go to **www.pythonanywhere.com**
2. Click **Pricing & signup**
3. Click **Create a Beginner account** (the free one)
4. Pick a username and password, then create the account

### 3b. Open a console

1. After logging in, click **Dashboard** at the top
2. Under **New console**, click **Bash**
3. A black screen will appear - this is where you'll type commands

### 3c. Download the agent

Type this line into the console and press Enter:

```
git clone https://github.com/thegolffellowship/Main.git
```

Wait for it to finish (a few seconds).

### 3d. Create your config file

Type this and press Enter:

```
cp Main/email_agent_config.example.json Main/email_agent_config.json
```

### 3e. Add your app passwords

Type this and press Enter:

```
nano Main/email_agent_config.json
```

A text editor will open. The file already has your three email accounts set up. **You only need to replace the passwords.**

You'll see these lines that need changing:

**Line 6** - Replace `PASTE-YOUR-ICLOUD-APP-PASSWORD-HERE` with the iCloud app password from Step 1

**Line 14** - Replace `PASTE-YOUR-MICROSOFT-365-APP-PASSWORD-HERE` with the app password for **kerry@thegolffellowship.com** from Step 2

**Line 22** - Replace `PASTE-YOUR-MICROSOFT-365-APP-PASSWORD-HERE` with the app password for **admin@thegolffellowship.com** from Step 2

**Line 34** - Replace `PASTE-YOUR-ICLOUD-APP-PASSWORD-HERE` with the **same** iCloud app password from Step 1 (this is used to send the summary)

Use your arrow keys to move around. Just delete the placeholder text and type in the password.

**When you're done:**
1. Press **Ctrl + O** (the letter O, not zero) then press **Enter** to save
2. Press **Ctrl + X** to exit the editor

### 3f. Test it (dry run - won't send anything)

Type this and press Enter:

```
cd Main && python3 -m email_summary_agent --dry-run
```

You should see it connect to each of your three accounts and print a summary of recent emails. If you see errors, the most common cause is a typo in the app password - go back to step 3e and double-check.

### 3g. Send yourself a real test summary

```
python3 -m email_summary_agent --now
```

Check your **niester@mac.com** inbox - you should have a nicely formatted summary email.

---

## Step 4: Schedule It for Every Morning at 8 AM

1. Click the **PythonAnywhere** logo at the top left to go back to the dashboard
2. Click the **Tasks** tab
3. Set the time to **08:00**
4. In the command box, type:

```
cd ~/Main && python3 -m email_summary_agent --now
```

5. Click **Create**

**You're done!** Every morning at 8 AM, you'll receive a summary email at niester@mac.com covering all three of your accounts.

---

## Changing the Time Zone

The schedule runs in UTC by default on PythonAnywhere. If you're on the US East Coast, 8 AM Eastern = **13:00 UTC**, so set the task time to **13:00** instead of 08:00.

Common conversions for 8 AM:
- **Eastern Time** = set task to **13:00**
- **Central Time** = set task to **14:00**
- **Mountain Time** = set task to **15:00**
- **Pacific Time** = set task to **16:00**

---

## Troubleshooting

**"Login failed" for iCloud:**
Make sure you're using the app-specific password from appleid.apple.com (Step 1), not your regular Apple ID password.

**"Login failed" for Microsoft 365:**
Make sure app passwords are enabled for your Microsoft 365 organization. If you're the admin, check the Microsoft 365 admin center.

**No emails in the summary:**
The agent only looks at emails from the last 24 hours. If it's been a quiet day, try sending yourself a test email first, wait a minute, then run the test again.

**Want to change where the summary gets sent:**
On PythonAnywhere, go to Dashboard > Files > Main > email_agent_config.json. Change the `summary_recipient` value to a different email address.

**Want to stop the daily summary:**
Go to PythonAnywhere > Tasks tab > delete the scheduled task.

---

## Quick Reference

| What | Where |
|------|-------|
| Agent checks | niester@mac.com, kerry@thegolffellowship.com, admin@thegolffellowship.com |
| Summary sent to | niester@mac.com |
| Runs at | 8:00 AM daily |
| Hosted on | PythonAnywhere (free) |
| To edit settings | PythonAnywhere > Files > Main/email_agent_config.json |
| To stop | PythonAnywhere > Tasks > delete the task |
