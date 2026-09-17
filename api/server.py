"""
FastAPI server — MCA Careers live job API.
On startup: seeds DB, fetches live jobs from Greenhouse/Lever/SmartRecruiters.
Render-compatible: uses /tmp for SQLite (ephemeral is fine, refreshes on boot).
"""

import sys, os, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Point DB files to /tmp on cloud, or local data/ folder
DATA_DIR = "/tmp/mca_data" if os.path.exists("/tmp") else os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.environ["MCA_DATA_DIR"] = DATA_DIR

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI(title="MCA Careers API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

COMPANIES_DB = os.path.join(DATA_DIR, "companies.db")
JOBS_DB      = os.path.join(DATA_DIR, "jobs.db")

# ── Startup: seed + crawl in background thread ──────────────────────────────

def startup_crawl():
    """Runs in background on server start. Seeds DB and crawls API-based ATS."""
    try:
        print("[Startup] Initializing databases...")
        from crawler.database import init_databases
        init_databases()

        print("[Startup] Seeding companies...")
        from crawler.seed_loader import load_seed_companies
        load_seed_companies()

        print("[Startup] Crawling API-based companies (Greenhouse/Lever/SmartRecruiters)...")
        conn = sqlite3.connect(COMPANIES_DB)
        conn.row_factory = sqlite3.Row
        companies = conn.execute("""
            SELECT * FROM companies
            WHERE ats IN ('greenhouse','lever','smartrecruiters')
            AND status = 'pending'
            ORDER BY ats
        """).fetchall()
        conn.close()

        from crawler.engine import crawl_company
        from crawler.database import upsert_jobs, mark_company_crawled

        for comp in companies:
            c = dict(comp)
            print(f"  Crawling {c['brand']} ({c['ats']})...")
            jobs, error = crawl_company(c)
            upsert_jobs(jobs)
            mark_company_crawled(c['domain'], len(jobs), error)
            print(f"  → {len(jobs)} jobs")
            time.sleep(0.3)

        print("[Startup] Crawl complete.")
    except Exception as e:
        print(f"[Startup] Error: {e}")

@app.on_event("startup")
async def on_startup():
    # Run crawl in background so API responds immediately
    t = threading.Thread(target=startup_crawl, daemon=True)
    t.start()


# ── Helpers ──────────────────────────────────────────────────────────────────

def jobs_db():
    if not os.path.exists(JOBS_DB):
        return None
    conn = sqlite3.connect(JOBS_DB)
    conn.row_factory = sqlite3.Row
    return conn

def companies_db():
    if not os.path.exists(COMPANIES_DB):
        return None
    conn = sqlite3.connect(COMPANIES_DB)
    conn.row_factory = sqlite3.Row
    return conn


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def api_jobs(
    search: str = Query(""),
    exp:    str = Query(None),
    ats:    str = Query(None),
    domain: str = Query(None),
    limit:  int = Query(50,  ge=1, le=500),
    offset: int = Query(0,   ge=0),
):
    conn = jobs_db()
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
        f"SELECT * FROM jobs {where} ORDER BY posted_date DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()
    return {"total": total, "jobs": [dict(r) for r in rows], "limit": limit, "offset": offset}


@app.get("/api/stats")
def api_stats():
    jconn = jobs_db()
    cconn = companies_db()

    if not jconn:
        return {"total_jobs": 0, "fresher_jobs": 0, "experienced_jobs": 0,
                "total_companies": 0, "crawled_companies": 0, "ats_breakdown": {}}

    total_jobs       = jconn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    fresher_jobs     = jconn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND exp_level='entry_level'").fetchone()[0]
    experienced_jobs = jconn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND exp_level='experienced'").fetchone()[0]
    ats_rows         = jconn.execute("SELECT ats, COUNT(*) FROM jobs WHERE is_active=1 GROUP BY ats").fetchall()
    jconn.close()

    total_companies   = 0
    crawled_companies = 0
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
        "ats_breakdown":     dict(ats_rows),
    }


@app.get("/api/companies")
def api_companies(
    search: str = Query(""),
    roc:    str = Query(None),
    ats:    str = Query(None),
    limit:  int = Query(200, ge=1, le=1000),
    offset: int = Query(0,   ge=0),
):
    conn = companies_db()
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
    conn = companies_db()
    if not conn:
        return {"status": "initializing"}
    rows = conn.execute("SELECT status, COUNT(*) as cnt FROM companies GROUP BY status").fetchall()
    conn.close()
    status_map = {r[0]: r[1] for r in rows}
    return {**status_map, "total": sum(status_map.values())}


@app.get("/")
def root():
    return {"message": "MCA Careers API", "docs": "/docs", "jobs": "/api/jobs", "stats": "/api/stats"}
