# Furever Home — Nightly Cron Setup Guide

## Architecture

```
GitHub Actions (free, runs on GitHub's servers at 1am PST)
    │
    ▼  python cron/petfinder_sync.py
Petfinder API v2  ──────────────────────────────┐
    │  GET /v2/animals                           │
    │  Bay Area locations, dogs + cats           │
    ▼                                            │
Transform data                                  │
(breed, age, size, gender, photo, story...)     │
    │                                            │
    ▼                                            │
Google Sheets API  ──────────────────────────────┘
    │  Write all rows to Sheet1
    │
    ▼
index.html fetches via gviz endpoint
    → Users see live, up-to-date pets
```

---

## One-Time Setup (do this once)

### Step 1 — Get Petfinder API Key (5 minutes)

1. Go to **https://www.petfinder.com/developers/**
2. Click **Get an API Key**
3. Sign up / log in with your email
4. You'll receive an **API Key** and **Secret** — save both

> Note: If the form says keys are paused, check back in a few days.
> As of 2025 keys are still being issued.

---

### Step 2 — Create Google Service Account (10 minutes)

This lets the Python script write to your Google Sheet.

1. Go to **https://console.cloud.google.com/**
2. Create a new project (e.g. "Furever Home")
3. Enable **Google Sheets API**:
   - APIs & Services → Library → search "Google Sheets API" → Enable
4. Create a Service Account:
   - APIs & Services → Credentials → Create Credentials → Service Account
   - Name: `furever-sync`
   - Click Create and Continue → Done
5. Click the service account → Keys tab → Add Key → JSON
6. Download the JSON file — save it as `cron/service_account.json`
   - **NEVER commit this file to GitHub** (it's in .gitignore)
7. Share your Google Sheet with the service account email:
   - Open the JSON file — find `"client_email"`
   - Copy that email (looks like `furever-sync@project.iam.gserviceaccount.com`)
   - Open your Google Sheet → Share → paste that email → Editor access

---

### Step 3 — Push to GitHub and add Secrets

1. Create a free GitHub account at **github.com** (no age limit)
2. Create a new repository (e.g. `furever-home`)
3. Push your project:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/furever-home.git
   git push -u origin main
   ```
4. In GitHub repo → **Settings** → **Secrets and variables** → **Actions**
5. Add these secrets (click "New repository secret" for each):

   | Secret Name | Value |
   |---|---|
   | `PETFINDER_API_KEY` | Your Petfinder API key |
   | `PETFINDER_SECRET` | Your Petfinder secret |
   | `GOOGLE_CREDENTIALS_JSON` | Paste the entire contents of service_account.json |
   | `SHEET_ID` | `1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80` |

---

### Step 4 — Test it manually right now

Once secrets are set:
1. Go to your GitHub repo → **Actions** tab
2. Click **Furever Home — Nightly Pet Sync**
3. Click **Run workflow** → **Run workflow**
4. Watch it run live — takes about 30–60 seconds
5. Check your Google Sheet — it should be filled with real pets!

---

## Local Testing (before GitHub)

### Dry run (no sheet writes, just tests the API):
```powershell
$env:PETFINDER_API_KEY = "your_key_here"
$env:PETFINDER_SECRET  = "your_secret_here"
python cron/petfinder_sync.py --dry-run
```

### Full local run (writes to sheet):
```powershell
$env:PETFINDER_API_KEY       = "your_key_here"
$env:PETFINDER_SECRET        = "your_secret_here"
# service_account.json must exist in cron/ folder
python cron/petfinder_sync.py
```

---

## Cron Schedule

The workflow runs at `0 9 * * *` (UTC) = **1:00 AM Pacific Time** every night.

To change the time, edit `.github/workflows/nightly_sync.yml`:
```yaml
cron: "0 9 * * *"   # 1am PST / 9am UTC
cron: "0 14 * * *"  # 6am PST / 2pm UTC  
cron: "0 8 * * *"   # 12am PST / 8am UTC
```

---

## What Gets Synced

Every night the script:
1. Fetches all adoptable dogs and cats within 10 miles of 5 Bay Area cities
2. Deduplicates pets that appear in multiple location searches
3. Maps Petfinder fields → your sheet columns
4. Clears the sheet and rewrites with fresh data
5. Pets marked `available=no` are automatically hidden from the website

## Efficiency

| Metric | Value |
|---|---|
| Runtime | ~30–60 seconds |
| API calls | ~10 (5 locations × 2 species) |
| Petfinder rate limit | 50 req/sec — well within limits |
| GitHub Actions cost | Free (2,000 min/month free tier) |
| Sheet writes | 1 clear + 1 batch write (very efficient) |
