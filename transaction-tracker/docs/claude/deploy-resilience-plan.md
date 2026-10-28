# Deploy resilience plan: PROPOSAL, not ruled (2026-10-21)

Kerry, verbatim (10/21, after Railway's all-day build outage): "I need options
for pushing new code. Railway is falling very short. I need to diversify from
just having one builder like Railway I believe." Then: "Yes, write it up and
send it to the Front Desk, but I want to discuss it at length with CA."

Status: for discussion between Kerry and CA (platform-claude). Nothing is built,
bought or changed. Rule 3b applies to scope and cost. Nothing touches production
before 10/31 without Kerry's "Deploy".

## What happened on 10/21

Railway had a major outage: "Dashboard and API unavailable, builds paused" in
every region, from about 00:28 UTC. The running app stayed up the whole time;
members saw nothing wrong. What stopped was every new release: v2.577.1 to
v2.578.0 sat on main for more than eight hours. Our API token also stopped
working, so we couldn't even see the deploy state. The risk shows up in two
places:

- **Build/deploy path (hit today):** we can't ship fixes. On an event night
  that would mean a broken screen stays broken.
- **Hosting (not hit today, bigger):** if Railway's runtime or volume fails,
  the Tracker is down. The database lives on that one volume, and Litestream
  already copies it off-site to Cloudflare R2 every 10 seconds.

## Today's setup (from the repo)

- `railway.toml`: builder nixpacks; start `sh scripts/start.sh`; restart
  always.
- `scripts/start.sh`: gunicorn plus `litestream replicate` beside it. The
  Litestream binary is pinned and cached on the volume
  (`scripts/install_litestream.py`). See `docs/claude/replication.md`.
- Headless Chromium (Playwright) for the print pack and scorecards.
- One SQLite database file (plus the GG archive file) on the Railway volume
  `/data`.
- APScheduler inside the web process: about 30 jobs, some every minute,
  several of which send member email.
- Every link, QR code and email uses `tgf-tracker.up.railway.app`, a Railway
  address.

## The plan, in order

### 1. We build the image ourselves (GitHub Actions to GHCR). Cost: $0.

- Add a `Dockerfile` that reproduces the nixpacks build: Python, the
  requirements, Playwright plus Chromium, and the pinned Litestream. Today we
  have no Dockerfile; nixpacks builds it implicitly.
- A GitHub Actions workflow builds that image on every push to main, runs the
  fast test set, and pushes it to GitHub Container Registry tagged with the
  commit and version.
- Railway switches from "build from repo" to "deploy this image". A Railway
  builder outage no longer blocks a release.
- Limit: today Railway also paused deploys, not only builds. Step 1 alone
  would not have shipped today; it is the foundation for step 2. It also
  gives one tested image that runs anywhere.
- Risk: the first Dockerfile must match today's build exactly. Prove it with
  a side-by-side run (rehearsal copy, `TGF_REHEARSAL=1`) before Railway uses
  it, and switch outside an event window.

### 2. Domain first: app.thegolffellowship.com (ruled 10/17). Cost: $0.

- Without our own address we cannot fail over: `*.up.railway.app` can only
  ever point at Railway.
- Kerry adds one CNAME at GoDaddy once Railway's dashboard shows the target.
  The code sweep moves every link, QR code and email to an `APP_BASE_URL`
  setting. The old address forwards permanently, because printed cart signs
  and old emails carry it.
- Optional and worth discussing: move DNS to Cloudflare, which we already use
  for backups. That gives near-instant switches and an edge cache for the
  public pages. The Microsoft 365 records (MX, autodiscover, SPF/DKIM) must
  be copied exactly; CFO #1999.

### 3. A cold standby on a second host (Fly.io or Render). Cost: about $5-15/month.

- The same GHCR image is deployed on the second host, stopped, with
  `SCHEDULER_DISABLED=1` and no outbound mail.
- **Failover by checklist, never automatic:**
  1. Confirm Railway is down. Stop the Railway service if it can still be
     reached, so two copies never write or send.
  2. Restore the newest R2 replica onto the standby's volume. This is the
     restore drill we already passed (`scoring-rehearsal:restore|replica`),
     so data loss is at most about 10 seconds.
  3. Start the standby with the scheduler ON and replication pointed at a new
     R2 path, so the old lineage stays intact.
  4. Point `app.thegolffellowship.com` at the standby.
  5. Post WINDOW-style notices on the mailbox.

  Target: about 15 minutes. Failing back is the same steps in reverse.
- **Marcus:** "Only one copy may ever run the jobs. Two schedulers means
  every member email twice and payouts recorded twice. The standby stays dark
  until someone decides Railway is down."
- **Priya:** "Drill it once on a quiet weekday before we count on it, and
  never during an event window."
- Fly vs Render: both run a container with a volume. Fly bills a stopped
  machine at about storage cost only; Render keeps a paid instance. CA and
  Kerry pick; Sarah reviews the recurring cost.

### 4. Long term: the Platform (already the plan, Convergence v0.3 Part 3)

- The Supabase Postgres move takes the database off the app host. After that,
  the app host is interchangeable: Vercel for the screens, and a small
  always-on worker for the jobs and PDFs. The worker is still Kerry's open
  decision (c).
- With the database off the host, failover is "start the image elsewhere and
  point DNS". No restore step.

## Questions for Kerry and CA

1. Do steps 1 to 3 in that order, starting after the outage clears and
   outside event windows? Or wait for the Postgres move?
2. Fly.io or Render for the standby (about $5-15/month)?
3. DNS: stay at GoDaddy, or move to Cloudflare?
4. Who may declare a failover: Kerry only, or also CA / Front Desk with
   Kerry told?
5. How often to rehearse the failover: once, or each quarter?
