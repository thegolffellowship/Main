# Round 2: the rest of the keys (Railway incident, 10/23)

**Why now.** Railway's 10/23 email (alert #4426) says our workspace "Kerry
Niester's Projects" held variables matching the pattern the attackers hunted.
Railway can't say whether ours were decrypted. The attack ended
10/22 03:32 UTC. Round 1 (#2213, #2231) already replaced:
- the Microsoft secret, the R2 token and the Anthropic key;
- the PINs and SECRET_KEY.

**Rules:**
- Kerry does every click and pastes every value straight into Railway, never
  into chat.
- Nothing is deployed until Kerry types "Deploy".
- Make all variable changes first, then deploy once.
- No deploy during an event window: Tue 10/27 from first tee to that night's
  close-out digest, and Sat 10/31.
- Best slot: today (Fri 10/23) or over the weekend.

## Part A: new values (stage them in Railway; don't deploy yet)

For each provider: create the new value, delete the old one, set it in
Railway > Variables.

1. **Brevo** (TGF Insider, nightly member-status sync)
   1. Brevo > top-right menu > **SMTP & API** > **API keys** tab >
      **Generate a new API key**. Name it `tgf-tracker-2026-10`, then copy
      it.
   2. In Railway, set **BREVO_API_KEY**.
   3. Back in Brevo, delete the old key (the one not named
      tgf-tracker-2026-10).
   4. Until redeploy: the nightly Brevo sync and the Insider draft fail.
   5. Afterwards: Tracker Build reads `brevo_status`, then sees the next
      brevo_sync succeed.
2. **HubSpot** (lead polling)
   1. HubSpot > Settings (gear) > **Integrations > Private Apps** > the
      Tracker's app > **Auth** tab > **Rotate** the access token, then copy
      the new one.
   2. In Railway, set whichever exists: **HUBSPOT_TOKEN**,
      **HUBSPOT_PRIVATE_APP_TOKEN**, **HUBSPOT_EXPORT_TOKEN** (the export
      token may be a second private app; rotate it the same way).
   3. Rotating expires the old token, after a short grace window.
   4. Until redeploy: the 45-minute lead poll fails.
   5. Afterwards: the next lead_poll succeeds.
3. **Meta** (campaign stats): only the META_* variables that exist in
   Railway.
   1. **META_ACCESS_TOKEN / META_PAGE_TOKEN**: in business.facebook.com,
      under Business settings > **System users**, generate a new token for
      the same system user and assets. Then remove the old token there.
   2. **META_APP_SECRET**: in developers.facebook.com > the app > Settings >
      Basic > **App secret**, click **Reset**.
   3. **META_WEBHOOK_VERIFY_TOKEN**: any new random string. If a Meta
      webhook is configured, set the same string in the app's Webhooks
      settings.
   4. Until redeploy: meta_insights fails.
   5. Afterwards: the next meta_insights run succeeds.
4. **Golf Genius** (historical reads and RSVPs)
   1. Change the password at golfgenius.com.
   2. In Railway, set **GOLF_GENIUS_PASSWORD**. Set **GOLF_GENIUS_EMAIL**
      only if the login email changes.
   3. Until redeploy: Golf Genius logins from the Tracker fail. Most of
      that is off since the untether.
   4. Afterwards: one read-only Golf Genius RSVP/archive read.
5. **Two Man Tour** (TWOMANTOUR_COOKIE, the sibling-brand flight board)
   1. Sign out of the Two Man Tour / unknowngolf site everywhere, which
      expires the old session, then sign in again.
   2. Copy the session cookie per the twomantour doc, or delete the variable
      if the board is no longer used.
   3. Afterwards: /twomantour loads.
6. **Anything else in Railway Variables that is a secret.** Scan the list
   for names containing KEY, TOKEN, SECRET, PASSWORD, COOKIE or PIN.
   - Already done: AZURE_CLIENT_SECRET, LITESTREAM_ACCESS_KEY_ID and
     LITESTREAM_SECRET_ACCESS_KEY, ANTHROPIC_API_KEY, ADMIN_PIN,
     AUSTIN_MANAGER_PIN, SA_MANAGER_PIN, SECRET_KEY.
   - Not secrets (identifiers): AZURE_CLIENT_ID, AZURE_TENANT_ID,
     MCP_CLIENT_ID, EMAIL_ADDRESS, DATABASE_PATH, LITESTREAM endpoint and
     bucket.
   - Anything else (a Stripe or Twilio key, for example): tell Tracker
     Build the NAME only.
7. **LAST: the Claude connector.**
   - **MCP_CLIENT_SECRET**: a new long random string, letters and digits
     only (no dashes; mcp_auth.py says Railway mangles them).
     **CONNECTOR_API_KEY** doesn't exist, so skip it.
   - After the redeploy, every Claude lane loses Tracker access until Kerry
     re-authorizes. claude.ai > Settings > Connectors > "TGF Transaction
     Tracker" > Disconnect, then Connect.
   - This session loses access too, so it runs all its checks BEFORE this
     step. Recommended order:
     1. Stage values 1-6 and deploy.
     2. Tracker Build checks.
     3. Then MCP_CLIENT_SECRET.
     4. A second deploy.
     5. Re-authorize the connector.
   - See the security finding below; it should ship in this same deploy.

## Part B: deploy and check (read-only)

**Deploy** (Kerry types "Deploy" here, then clicks Deploy in Railway). Wait
for Active.

Then Tracker Build checks:
- **Version:** `get_live_version` shows the new deployment id.
- **Mail and intake:** inbox_check, expense_inbox_check and rsvp_inbox_check
  OK.
- **Brevo:** `brevo_status` OK, then the next brevo_sync.
- **HubSpot:** the next lead_poll OK.
- **Meta:** the next meta_insights OK.
- **Golf Genius:** one read OK.
- **AI:** the next order parse, or the Insider dry run.
- **Replication:** lag 0 s in `scoring-health`.
- **OneDrive backup:** the last run OK.

## Part C: log review (Kerry, read-only; anything since 10/20)

- **GitHub:**
  - github.com/settings/security-log: sign-ins and token use.
  - Settings > Applications: keep Railway and Claude, remove anything you
    don't recognize.
  - Developer settings > Personal access tokens: delete any you don't
    recognize.
  - Repo thegolffellowship/Main > Settings: deploy keys, webhooks,
    collaborators. Tracker Build checked collaborators 10/22: only you.
- **Container registry (Docker Hub, GHCR):** none. Railway builds from
  GitHub with nixpacks, so there are no registry credentials to rotate.
- **Railway:** the workspace Audit Log. Railway staff "Faraz Patankar"
  bucket revocations are expected.
- **Microsoft:** entra.microsoft.com > Applications > Enterprise
  applications > Transaction Tracker > Sign-in logs (service principal
  sign-ins). Look for any IP or time that isn't Railway's.
- **Anthropic:** platform.claude.com > Usage, by key, 10/20 to 10/22. Also
  Members.
- **Cloudflare R2:** Account > Audit Log, plus R2 bucket metrics, for reads
  you don't expect.
- **Brevo:** Campaigns (anything you didn't send), Contacts > recent exports,
  Security > login history.
- **HubSpot:** Settings > Account > Audit logs (logins, exports).

## Security finding (Tracker Build, 10/23): the Claude connector has no real lock

`mcp_auth.py`'s login flow gives the connector's client id to anyone who asks
(`/oauth/register`). Its authorize step then **auto-approves** any request
with that id, and the code exchange needs no secret (PKCE). So anyone who knows
the Tracker's URL could add it as their own Claude connector and get the same
read/write tools as our lanes.

Rotating MCP_CLIENT_SECRET does **not** close this: the secret isn't part of
that flow. Nothing in the action log looks foreign, but reads aren't all
logged.

**Fix BUILT as v2.579.1 (branch claude/evlb-batch1-k7q2m9), needs Kerry's "Deploy":** the authorize step shows a
sign-in page that asks for the ADMIN PIN before it issues a code. Only Kerry
can approve a new connector, and existing lanes keep working until their
tokens are re-issued. Build it before the round-2 deploy so both ship
together.
