# Railway API Setup — what the Tracker needs, and how to get it

**For:** Kerry. **Raised:** 2026-09-03 — *"Biggest thing I think is to get
all the necessary APIs setup thru Railway that you need."*

Everything here is a Railway environment variable on the Tracker
service. **Each feature is already coded to sit idle until its variable
exists**, so nothing breaks while a slot is empty and nothing needs a
deploy when one is filled — set the variable, restart, done.

**Important distinction:** Claude can read Meta and HubSpot *in a
session* through connectors. The Tracker running on Railway cannot use
those — it needs its own tokens. Reading data here does not mean the app
can.

---

## 0. Files.ReadWrite.All on the existing Azure app — NIGHTLY BACKUPS

**Not a new variable. One permission on an app registration you already
have.** Unblocks the nightly off-site database backup (v2.296.0), which
is built and idle until this is granted.

Azure Portal → App registrations → the app already used for TGF mail →
**API permissions** → Add a permission → Microsoft Graph → **Application
permissions** → `Files.ReadWrite.All` → Add → **Grant admin consent**.

`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` and
`EMAIL_ADDRESS` are already on Railway, so nothing else changes.

Then run `scoring-backup-run` and `scoring-backup-verify`. Until verify
passes once, we do not have backups.

---

## Already set (no action)

| Variable | Powers |
|---|---|
| `HUBSPOT_TOKEN` | The lead poll. Contacts read only. |
| `BREVO_API_KEY` | Nightly member-status / chapter / last-played sync. |
| `LEAD_CHECK_INTERVAL_MINUTES` | Lead poll cadence, currently 15. |

---

## 1. `META_ACCESS_TOKEN` — campaign stats (do this first)

**Unblocks:** the META panel on the Lead Center's 📊 Stats view — live
spend, impressions, reach, frequency, link clicks, CTR, CPM, and true
CPL / CPP / CPMem. Also the **historical campaign backfill** (§5).
Until it lands, spend is a number typed in by hand.

**Type:** System User token, Meta Business Suite → Business Settings →
Users → System Users → Add → assign the ad account → Generate token.

**Permissions:** `ads_read`. (`ads_management` only if we ever want the
Tracker to change campaigns — it does not today. Don't grant it.)

**Ad account:** `act_2353186181735308`.

**Set it to a long-lived / non-expiring System User token.** A 60-day
user token means this quietly stops working in November and the panel
goes stale without saying so.

---

## 2. `META_PAGE_TOKEN` — direct lead rows

**Unblocks:** pulling lead-form submissions straight from Meta instead
of through HubSpot. This is the decommission's other half.

**Type:** Page access token for the TGF Facebook Page
(`119648338214501`), issued to the same System User.

**Permissions:** `leads_retrieval`, plus `pages_show_list` and
`pages_read_engagement` to mint the page token.

**Prerequisite:** the Page must have accepted Meta's Lead Ads Terms of
Service. It has — lead campaigns are running — but confirm at
facebook.com/legal/leadgen/tos if the token errors.

---

## 3. `META_APP_SECRET` + `META_WEBHOOK_VERIFY_TOKEN` — real-time leads

**Unblocks:** leads arriving in **seconds** instead of on a 15-minute
poll. The 48-hour clock starts sooner on every single lead.

- `META_APP_SECRET` — from the Meta app's Basic Settings. Used to verify
  that an incoming webhook really came from Meta. **Without it we would
  be trusting anything that POSTs to our URL, so this is not optional.**
- `META_WEBHOOK_VERIFY_TOKEN` — a random string you invent. Paste the
  same value into Meta's webhook subscription screen; it is only used
  for the initial handshake.

Subscribe the app to the `leadgen` field on the TGF Page. The Tracker
will expose the callback URL once the ingest is built.

---

## 4. `HUBSPOT_EXPORT_TOKEN` — the archive (before anything is switched off)

**Unblocks:** extracting every bit of data out of HubSpot. **The current
token cannot do this** — it reads contacts and nothing else, so notes,
calls, tasks, meetings, and email history are all invisible to it today.

**Type:** HubSpot → Settings → Integrations → Private Apps → new app.

**Scopes:**

| Scope | Why |
|---|---|
| `crm.objects.contacts.read` | the 1,453 contacts + property history |
| `crm.objects.companies.read` | 130 companies |
| `crm.objects.notes.read` (or Engagements read) | **the 15 hand-written notes** |
| `crm.objects.tasks.read` | 118 tasks |
| `crm.objects.calls.read` | 24 calls, back to 2023 |
| `crm.objects.meetings.read` | 22 meetings |
| `sales-email-read` | 469 logged emails — **HubSpot gates email bodies behind this specific scope** |
| `crm.objects.owners.read` | turns note author ids into names. **Without it every imported note loses who wrote it.** |
| `crm.lists.read` | 3 lists |
| `crm.schemas.contacts.read` | custom property definitions (the survey fields) |

Read-only throughout. The export never writes to HubSpot.

---

## 5. What each unlocks, in order of value

1. **`HUBSPOT_EXPORT_TOKEN`** — the only irreplaceable data in the
   project. Nothing else should start before this one works.
2. **`META_ACCESS_TOKEN`** — turns the stats view live, and unlocks the
   historical campaign backfill (34 campaigns, ~$2,898 of spend since
   April 2025, all still retrievable from Meta today).
3. **`META_PAGE_TOKEN`** — the ingest replacement.
4. **`META_APP_SECRET` + verify token** — real-time delivery.

Numbers 2, 3 and 4 all come from the same Meta System User, so they are
one sitting in Business Settings, not four.
