# MCA Careers — India's Direct Corporate Job Portal

A job portal that fetches **real live job listings directly from Indian companies' own career pages** — no LinkedIn, no Naukri, no aggregators.

Powered by Ministry of Corporate Affairs (MCA) company registry data + public ATS APIs.

---

## What it does

- Crawls career pages of 127+ MCA-registered Indian companies
- Fetches jobs via public APIs: **Greenhouse, Lever, SmartRecruiters, Darwinbox, Workday**
- Auto-detects which ATS a company uses by fingerprinting their career page HTML
- Stores jobs in SQLite, refreshed daily via scheduler
- Serves live job data through a FastAPI backend
- Frontend: vanilla HTML/CSS/JS — no framework needed

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | HTML5 + CSS3 + Vanilla JS |
| Backend API | FastAPI + Uvicorn |
| Crawler | Python + Requests + Playwright |
| Scheduler | APScheduler |
| Database | SQLite (via built-in `sqlite3`) |

---

## Project Structure

```
mca-job-portal/
├── index.html          # Frontend UI
├── styles.css          # All styling
├── app.js              # Frontend logic (API-connected)
├── mca_data.js         # Mock data fallback
├── start.py            # One-click startup (seed + crawl + API server)
├── crawl.py            # Standalone crawler CLI
│
├── crawler/
│   ├── engine.py           # Main crawl orchestrator
│   ├── ats_detector.py     # ATS fingerprinting
│   ├── database.py         # SQLite layer
│   ├── seed_loader.py      # 127+ verified company seeds
│   ├── scheduler.py        # Daily refresh cron
│   └── parsers/
│       ├── greenhouse.py   # Greenhouse public API
│       ├── lever.py        # Lever public API
│       ├── workday.py      # Workday hidden JSON API
│       ├── darwinbox.py    # Darwinbox API + HTML
│       ├── taleo.py        # Taleo XML/JSON feed
│       ├── smartrecruiters.py  # SmartRecruiters API
│       └── generic.py      # Playwright fallback
│
├── api/
│   └── server.py       # FastAPI endpoints
│
└── data/               # SQLite databases (git-ignored)
    ├── companies.db
    └── jobs.db
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install scrapy playwright beautifulsoup4 lxml tldextract fake-useragent apscheduler fastapi uvicorn aiohttp
python -m playwright install chromium
```

### 2. One-click start
```bash
python start.py
```
This seeds the DB, runs the first crawl, and starts the API server.

### 3. Open the portal
- Frontend: http://localhost:5500 (run `python -m http.server 5500`)
- API docs: http://localhost:8000/docs

---

## Crawler CLI

```bash
# Crawl next 20 companies from queue
python crawl.py

# Crawl a specific batch size
python crawl.py --batch 50

# Crawl one specific company
python crawl.py --domain razorpay.com

# Run on a schedule (every 2 hours)
python crawl.py --schedule

# Re-seed company list
python crawl.py --seed
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/jobs` | Jobs with filters: `search`, `exp`, `ats`, `domain`, `limit`, `offset` |
| `GET /api/stats` | Total jobs, fresher count, ATS breakdown |
| `GET /api/companies` | Company directory with filters |
| `GET /api/companies/:domain/jobs` | Jobs for one company |
| `GET /api/crawler/status` | Queue status: pending/done/error counts |

---

## Verified ATS Companies (seed list)

| ATS | Companies | Jobs (approx) |
|---|---|---|
| Greenhouse | Razorpay, Groww, InMobi, Glance, Porter | ~140 |
| Lever | Paytm, CRED, Meesho, Fi, EpiFi, Nium, Porter | ~310 |
| SmartRecruiters | Freshworks, Swiggy, Unacademy, Cars24, NoBroker | ~245 |
| Darwinbox | BigBasket | — |
| Generic/Playwright | TCS, Infosys, Wipro, Flipkart, Zomato, PhonePe, 90+ more | — |

---

## Adding More Companies

Edit `crawler/seed_loader.py` and add entries to `SEED_COMPANIES`, then run:
```bash
python crawl.py --seed
python crawl.py --batch 50
```

The ATS detector will auto-discover the ATS for any company with `ats: "unknown"`.

---

## License

MIT
