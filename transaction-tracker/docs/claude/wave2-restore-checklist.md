# Wave 2: putting the keys back after the Railway incident (checklist, 10/22)

Context: on 10/21 Railway disclosed that customer environment variables may
have been read (#2212). That night Kerry did wave 1 (#2213):
- deleted the "Transaction Tracker" Microsoft client secret;
- deleted the R2 token "tgf-tracker-replica";
- deleted the TGF-Transaction-Tracker Anthropic key and four unused keys.

Wave 2 creates new keys and puts them into Railway. Kerry does every click;
Tracker Build 4 walks him through it and runs the checks. Order per CoS #2221,
Health #2216, Database #2224 and CFO #2218.

**When:** only when Railway builds and deploys work for our plan, and outside
an event window. The windows run from first tee on Tue 10/27 to that night's
close-out digest, and the same again Sat 10/31. Check the mailbox for WINDOW
OPEN before saving variables: saving one restarts the app.

**Golden rule:** copy each new value the moment it is shown. Paste it straight
into Railway, never into email, chat or a document. Each site shows it only
once.

## Step 0: Railway itself (2 min)
1. Sign in at railway.com. If Railway asks you to reconnect GitHub, accept;
   leave its GitHub app installed.
2. Open the Tracker service (project with service "Main"):
   - **Settings > Source**: the repository is thegolffellowship/Main, branch
     main, and automatic deploys are on.
   - **Variables**: keep this tab open. Every value below goes here.

## Step 1: Microsoft secret (first: mail, intake and the OneDrive backup)
1. Go to entra.microsoft.com > Applications > App registrations >
   **Transaction Tracker** > Certificates & secrets > **New client secret**.
   Description "Tracker 2026-10", expiry 24 months, then **Add**.
2. Copy the **Value** column, not the "Secret ID". The Value is the long one
   shown only now.
3. In Railway > Variables, set **AZURE_CLIENT_SECRET** to it. If a variable
   **RSVP_AZURE_CLIENT_SECRET** also exists, set it to the same value (one app
   serves both mailboxes). Leave AZURE_CLIENT_ID and AZURE_TENANT_ID as they
   are.

## Step 2: Cloudflare R2 token (first: the off-site backup)
1. Go to dash.cloudflare.com > Storage & databases > R2 Object Storage >
   **Manage API Tokens** > **Create Account API token**.
   - Name: tgf-tracker-replica-2026-10.
   - Permission: **Object Read & Write**.
   - Apply to specific bucket: **tgf-tracker-replica** only.
   - TTL: forever. Then **Create**.
2. Copy the **Access Key ID** and the **Secret Access Key**.
3. In Railway, set **LITESTREAM_ACCESS_KEY_ID** and
   **LITESTREAM_SECRET_ACCESS_KEY**. Leave the other LITESTREAM_* variables
   (endpoint and bucket) as they are.

## Step 3: Anthropic key (AI parsing, Insider writer)
1. Go to platform.claude.com > Settings > API keys > **Create key**.
   Name: TGF-Tracker-2026-10, workspace Default.
2. In Railway, set **ANTHROPIC_API_KEY**.
3. Optional: Settings > Limits, set a monthly spend limit.

## Step 4: our own secrets (sign-in and links)
Make each new value up yourself: 6-digit PINs, and SECRET_KEY as a long
random string (Tracker Build can generate one on request). Then set:
- **ADMIN_PIN** (also **TGF_ADMIN_PIN** if it exists), **AUSTIN_MANAGER_PIN**,
  **SA_MANAGER_PIN**, **VIEWONLY_PIN**, **MANAGER_PIN** if present. Tell
  Robert and the SA manager their new PINs in person or by text.
- **SECRET_KEY.** WARNING: this voids every signed link already sent:
  - invitation and RSVP buttons;
  - handicap and payout asks;
  - roster opt-in/out;
  - advisor links;
  - every login session.

  Printed QR codes carry it too. None are printed for 10/27 yet, but any
  already printed for 10/31 would need reprinting.
- **CONNECTOR_API_KEY**: any new long random string.
- **MCP_CLIENT_SECRET**: a new long random string. WARNING: this is the Claude
  connector's own login. After the redeploy, re-authorize the "TGF Transaction
  Tracker" connector in claude.ai Settings > Connectors with the new secret.
  Until then every Claude lane loses Tracker access, this one included. Do
  this step LAST, after the checks below have passed.

## Step 5: the other providers (can be the same day or later)
- **BREVO_API_KEY**: Brevo > Settings > SMTP & API > API keys > generate.
- **HUBSPOT_TOKEN / HUBSPOT_PRIVATE_APP_TOKEN / HUBSPOT_EXPORT_TOKEN**:
  HubSpot > Settings > Integrations > Private Apps > the Tracker's app >
  rotate token. Set whichever of these Railway has.
- **META_ACCESS_TOKEN / META_PAGE_TOKEN / META_APP_SECRET**: only those that
  exist in Railway.
- **GOLF_GENIUS_PASSWORD**: change it at Golf Genius, then set it here.
- **TWOMANTOUR_COOKIE**: sign in to the Two Man Tour site again, if still
  used.

## Step 6: deploy
Saving variables stages a redeploy; Railway asks you to **Deploy**. Confirm it
and wait for the deployment to show Active (about 3-5 minutes).

## Step 7: checks (Tracker Build runs these through the connector; read-only)
1. `get_live_version`: the version matches main (v2.578.0 or later).
2. Microsoft: `scoring-health` shows inbox_check succeeding again, with no
   "Could not acquire Graph API token".
3. Off-site backup: `scoring-health` REPLICATION shows a new generation.
   `scoring-backup-status`: a files-backup run. The same day, the restore
   check `scoring-rehearsal:restore|replica` (Health and Database read it
   back).
4. AI: the next order email parses, or the Insider dry run
   `scoring-brevo-draft:dry` writes.
5. **Catch-up, missed payments:** POST `/api/accounting/check-expense-inbox`
   with `days_back` = days since 10/21 plus 1, run once as admin. The steady
   lookback is only 48 h.
6. **Catch-up, missed orders** (CFO #2218):
   `scoring-import-orders:2026-10-21|<today>`, preview first, then `|apply`
   on Kerry's OK. Before the 11/1 sales-tax review. If the secret is not in
   by Tue 10/27, this is required.
7. Kerry closes Tracker alerts #4399, #4400 and #4407.
8. Then step 4's MCP_CLIENT_SECRET, and the connector re-authorized.

## If something fails
- An "InvalidAccessKeyId" or "SignatureDoesNotMatch" in replication means a
  wrong or old R2 value: re-copy from Cloudflare (or make another token).
- A Graph "invalid_client" means the Secret ID was pasted instead of the
  Value: make a new secret and copy the Value.
- Stop after the same step fails twice, and report (lane guardrail).
