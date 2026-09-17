"""
FastAPI server — MCA Careers live job API.
On startup: seeds DB from company_career_sites.csv, crawls all API-based ATS companies.
Scheduled re-crawl every 6 hours to pick up new job postings automatically.
Render-compatible: uses /tmp for SQLite.
"""

import sys, os, threading, time, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

DATA_DIR = "/tmp/mca_data" if os.path.exists("/tmp") else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.environ["MCA_DATA_DIR"] = DATA_DIR

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MCA Careers API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

COMPANIES_DB = os.path.join(DATA_DIR, "companies.db")
JOBS_DB      = os.path.join(DATA_DIR, "jobs.db")


# ── Crawl cycle ──────────────────────────────────────────────────────────────

def _run_crawl_cycle():
    """Crawl all API-based companies. Called on startup + every 6 hours."""
    try:
        if not os.path.exists(COMPANIES_DB):
            print("[Crawler] DB not ready yet, skipping cycle")
            return

        conn = sqlite3.connect(COMPANIES_DB)
        conn.row_factory = sqlite3.Row
        # Crawl pending ones first, then re-crawl done ones (oldest first)
        companies = conn.execute("""
            SELECT * FROM companies
            WHERE ats IN ('greenhouse','lever','smartrecruiters','darwinbox')
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                last_crawled ASC
        """).fetchall()
        conn.close()

        from crawler.engine import crawl_company
        from crawler.database import upsert_jobs, mark_company_crawled

        total_jobs = 0
        print(f"[Crawler] Starting cycle — {len(companies)} companies to crawl")

        for comp in companies:
            c = dict(comp)
            try:
                jobs, error = crawl_company(c)
                upsert_jobs(jobs)
                mark_company_crawled(c['domain'], len(jobs), error)
                total_jobs += len(jobs)
                if jobs:
                    print(f"  ✓ {c['brand']}: {len(jobs)} jobs")
            except Exception as e:
                print(f"  ✗ {c.get('brand','?')}: {e}")
            time.sleep(0.3)

        print(f"[Crawler] Cycle complete — {total_jobs} total jobs from {len(companies)} companies")

    except Exception as e:
        print(f"[Crawler] Cycle error: {e}")


def startup_task():
    """Background thread: seed → crawl → schedule every 6 hours."""
    try:
        # Step 1: Init DB
        print("[Startup] Initializing databases...")
        from crawler.database import init_databases
        init_databases()

        # Step 2: Load all 238 companies from CSV
        print("[Startup] Seeding companies from company_career_sites.csv...")
        from crawler.seed_loader import load_seed_companies
        load_seed_companies()

        # Step 3: First crawl
        print("[Startup] Running first crawl cycle...")
        _run_crawl_cycle()

        # Step 4: Schedule every 6 hours
        print("[Startup] Scheduling crawl every 6 hours...")
        try:
            import schedule
            schedule.every(6).hours.do(_run_crawl_cycle)
            while True:
                schedule.run_pending()
                time.sleep(60)
        except ImportError:
            # If schedule not installed, just sleep and re-crawl manually
            while True:
                time.sleep(6 * 3600)
                print("[Scheduler] Running scheduled crawl cycle...")
                _run_crawl_cycle()

    except Exception as e:
        print(f"[Startup] Fatal error: {e}")


@app.on_event("startup")
async def on_startup():
    t = threading.Thread(target=startup_task, daemon=True)
    t.start()


# ── DB helpers ───────────────────────────────────────────────────────────────

def get_jobs_conn():
    if not os.path.exists(JOBS_DB):
        return None
    c = sqlite3.connect(JOBS_DB)
    c.row_factory = sqlite3.Row
    return c

def get_companies_conn():
    if not os.path.exists(COMPANIES_DB):
        return None
    c = sqlite3.connect(COMPANIES_DB)
    c.row_factory = sqlite3.Row
    return c


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "MCA Careers API v2", "docs": "/docs", "jobs": "/api/jobs", "stats": "/api/stats"}


@app.get("/api/jobs")
def api_jobs(
    search: str = Query(""),
    exp:    str = Query(None),
    ats:    str = Query(None),
    domain: str = Query(None),
    limit:  int = Query(50,  ge=1, le=500),
    offset: int = Query(0,   ge=0),
):
    conn = get_jobs_conn()
    if not conn:
        return {"total": 0, "jobs": [], "limit": limit, "offset": offset}

    conditions = ["is_active = 1"]
    params = []

    if search:
        conditions.append("(title LIKE ? OR company_name LIKE ? OR description LIKE ? OR location LIKE ?)")
        t = f"%{search}%"
        params += [t, t, t, t]
    if exp:
        conditions.append("exp_level = ?")
        params.append(exp)
    if ats:
        conditions.append("LOWER(ats) = LOWER(?)")
        params.append(ats)
    if domain:
        conditions.append("company_domain = ?")
        params.append(domain)

    where = "WHERE " + " AND ".join(conditions)
    total = conn.execute(f"SELECT COUNT(*) FROM jobs {where}", params).fetchone()[0]
    rows  = conn.execute(
        f"SELECT * FROM jobs {where} ORDER BY posted_date DESC, first_seen DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()
    return {"total": total, "jobs": [dict(r) for r in rows], "limit": limit, "offset": offset}


@app.get("/api/stats")
def api_stats():
    jconn = get_jobs_conn()
    cconn = get_companies_conn()

    if not jconn:
        return {"total_jobs": 0, "fresher_jobs": 0, "experienced_jobs": 0,
                "total_companies": 0, "crawled_companies": 0, "ats_breakdown": {},
                "status": "initializing — crawl in progress"}

    total_jobs       = jconn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    fresher_jobs     = jconn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND exp_level='entry_level'").fetchone()[0]
    experienced_jobs = jconn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND exp_level='experienced'").fetchone()[0]
    ats_rows         = jconn.execute("SELECT ats, COUNT(*) as c FROM jobs WHERE is_active=1 GROUP BY ats").fetchall()
    jconn.close()

    total_companies = crawled_companies = 0
    if cconn:
        total_companies   = cconn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        crawled_companies = cconn.execute("SELECT COUNT(*) FROM companies WHERE status='done'").fetchone()[0]
        cconn.close()

    return {
        "total_jobs":        total_jobs,
        "fresher_jobs":      fresher_jobs,
        "experienced_jobs":  experienced_jobs,
        "total_companies":   total_companies,
        "crawled_companies": crawled_companies,
        "ats_breakdown":     {r[0]: r[1] for r in ats_rows},
    }


@app.get("/api/companies")
def api_companies(
    search: str = Query(""),
    roc:    str = Query(None),
    ats:    str = Query(None),
    limit:  int = Query(500, ge=1, le=1000),
    offset: int = Query(0,   ge=0),
):
    conn = get_companies_conn()
    if not conn:
        return {"total": 0, "companies": []}

    conditions, params = [], []
    if search:
        conditions.append("(name LIKE ? OR brand LIKE ? OR domain LIKE ? OR cin LIKE ?)")
        t = f"%{search}%"
        params += [t, t, t, t]
    if roc:
        conditions.append("roc = ?")
        params.append(roc)
    if ats:
        conditions.append("LOWER(ats) = LOWER(?)")
        params.append(ats)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    total = conn.execute(f"SELECT COUNT(*) FROM companies {where}", params).fetchone()[0]
    rows  = conn.execute(
        f"SELECT * FROM companies {where} ORDER BY jobs_found DESC, name ASC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()
    return {"total": total, "companies": [dict(r) for r in rows]}


@app.get("/api/companies/{domain}/jobs")
def api_company_jobs(domain: str, limit: int = 100, offset: int = 0):
    return api_jobs(domain=domain, limit=limit, offset=offset)


@app.get("/api/crawler/status")
def crawler_status():
    conn = get_companies_conn()
    if not conn:
        return {"status": "initializing"}
    rows = conn.execute("SELECT status, COUNT(*) FROM companies GROUP BY status").fetchall()
    conn.close()
    d = {r[0]: r[1] for r in rows}
    return {**d, "total": sum(d.values())}
