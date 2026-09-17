"""
FastAPI server — serves live job data to the frontend.
Replaces the static mca_data.js mock with real DB-backed responses.

Run with: uvicorn api.server:app --reload --port 8000
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from crawler.database import init_databases, get_jobs, get_stats
import sqlite3

app = FastAPI(title="MCA Job Portal API", version="1.0.0")

# Allow the frontend (served on port 5500) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
COMPANIES_DB = os.path.join(BASE_DIR, "data", "companies.db")
JOBS_DB      = os.path.join(BASE_DIR, "data", "jobs.db")


@app.on_event("startup")
def startup():
    init_databases()


# ── Jobs endpoint ─────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def api_jobs(
    search:   str  = Query("",     description="Full-text search: title, company, skill, location"),
    exp:      str  = Query(None,   description="entry_level | mid_level | experienced"),
    ats:      str  = Query(None,   description="Filter by ATS: Greenhouse, Lever, Workday …"),
    domain:   str  = Query(None,   description="Filter by company domain"),
    limit:    int  = Query(50,     ge=1, le=500),
    offset:   int  = Query(0,      ge=0),
):
    return get_jobs(
        search=search,
        exp_level=exp,
        ats=ats,
        company_domain=domain,
        limit=limit,
        offset=offset,
    )


# ── Stats endpoint ────────────────────────────────────────────────────────────

@app.get("/api/stats")
def api_stats():
    return get_stats()


# ── Companies endpoint ────────────────────────────────────────────────────────

@app.get("/api/companies")
def api_companies(
    search: str = Query("", description="Search company name, brand, domain, CIN"),
    roc:    str = Query(None, description="Filter by ROC jurisdiction"),
    ats:    str = Query(None, description="Filter by ATS"),
    limit:  int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    if not os.path.exists(COMPANIES_DB):
        return {"total": 0, "companies": []}

    conn = sqlite3.connect(COMPANIES_DB)
    conn.row_factory = sqlite3.Row

    conditions = []
    params = []

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


# ── Single company jobs ───────────────────────────────────────────────────────

@app.get("/api/companies/{domain}/jobs")
def api_company_jobs(domain: str, limit: int = 100, offset: int = 0):
    return get_jobs(company_domain=domain, limit=limit, offset=offset)


# ── Crawler status ────────────────────────────────────────────────────────────

@app.get("/api/crawler/status")
def crawler_status():
    if not os.path.exists(COMPANIES_DB):
        return {"status": "not_initialized"}

    conn = sqlite3.connect(COMPANIES_DB)
    rows = conn.execute("""
        SELECT status, COUNT(*) as cnt FROM companies GROUP BY status
    """).fetchall()
    conn.close()

    status_map = {r[0]: r[1] for r in rows}
    return {
        "pending":  status_map.get("pending", 0),
        "queued":   status_map.get("queued", 0),
        "done":     status_map.get("done", 0),
        "error":    status_map.get("error", 0),
        "total":    sum(status_map.values()),
    }
