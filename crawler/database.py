"""
SQLite database layer for the MCA Job Crawler.
Two databases:
  - companies.db: company registry + crawl state
  - jobs.db: all scraped job postings
"""

import sqlite3
import json
import os
from datetime import datetime

DB_DIR = os.environ.get("MCA_DATA_DIR") or os.path.join(os.path.dirname(__file__), "..", "data")
COMPANIES_DB = os.path.join(DB_DIR, "companies.db")
JOBS_DB = os.path.join(DB_DIR, "jobs.db")


def init_databases():
    """Create tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)

    # Companies DB
    conn = sqlite3.connect(COMPANIES_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cin TEXT UNIQUE,
            name TEXT NOT NULL,
            brand TEXT,
            domain TEXT,
            roc TEXT,
            incorporated INTEGER,
            company_class TEXT,
            capital TEXT,
            career_url TEXT,
            ats TEXT,
            ats_token TEXT,
            status TEXT DEFAULT 'pending',
            last_crawled TEXT,
            crawl_error TEXT,
            jobs_found INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_ats ON companies(ats)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain)")
    conn.commit()
    conn.close()

    # Jobs DB
    conn = sqlite3.connect(JOBS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company_name TEXT,
            company_domain TEXT,
            company_cin TEXT,
            location TEXT,
            department TEXT,
            description TEXT,
            description_html TEXT,
            apply_url TEXT NOT NULL,
            ats TEXT,
            ats_token TEXT,
            exp_level TEXT,
            posted_date TEXT,
            source TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_domain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_exp ON jobs(exp_level)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_ats ON jobs(ats)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(id UNINDEXED, title, company_name, description, location, department, content=jobs, content_rowid=rowid)")
    conn.commit()
    conn.close()
    print("[DB] Databases initialized.")


def upsert_company(company: dict):
    conn = sqlite3.connect(COMPANIES_DB)
    conn.execute("""
        INSERT INTO companies (cin, name, brand, domain, roc, incorporated, company_class,
                               capital, career_url, ats, ats_token, status)
        VALUES (:cin, :name, :brand, :domain, :roc, :incorporated, :company_class,
                :capital, :career_url, :ats, :ats_token, :status)
        ON CONFLICT(cin) DO UPDATE SET
            name=excluded.name, brand=excluded.brand, domain=excluded.domain,
            career_url=excluded.career_url, ats=excluded.ats, ats_token=excluded.ats_token
    """, {
        "cin": company.get("cin", ""),
        "name": company.get("name") or company.get("legal_name") or "",
        "brand": company.get("brand", ""),
        "domain": company.get("domain", ""),
        "roc": company.get("roc", ""),
        "incorporated": company.get("incorporated"),
        "company_class": company.get("company_class", ""),
        "capital": company.get("capital", ""),
        "career_url": company.get("career_url", ""),
        "ats": company.get("ats", "unknown"),
        "ats_token": company.get("ats_token", ""),
        "status": company.get("status", "pending"),
    })
    conn.commit()
    conn.close()


def bulk_insert_companies(companies: list):
    conn = sqlite3.connect(COMPANIES_DB)
    for company in companies:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO companies (cin, name, brand, domain, roc,
                    incorporated, company_class, capital, career_url, ats, ats_token)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company.get("cin", ""),
                company.get("name") or company.get("legal_name") or "",
                company.get("brand", ""),
                company.get("domain", ""),
                company.get("roc", ""),
                company.get("incorporated"),
                company.get("company_class", ""),
                company.get("capital", ""),
                company.get("career_url", ""),
                company.get("ats", "unknown"),
                company.get("ats_token", ""),
            ))
        except Exception as e:
            print(f"[DB] Error inserting company {company.get('name')}: {e}")
    conn.commit()
    conn.close()
    print(f"[DB] Inserted {len(companies)} companies.")


def mark_company_crawled(domain: str, jobs_found: int, error: str = None):
    conn = sqlite3.connect(COMPANIES_DB)
    conn.execute("""
        UPDATE companies SET
            last_crawled = ?,
            jobs_found = ?,
            crawl_error = ?,
            status = ?
        WHERE domain = ?
    """, (
        datetime.now().isoformat(),
        jobs_found,
        error,
        "error" if error else "done",
        domain,
    ))
    conn.commit()
    conn.close()


def update_company_ats(domain: str, ats: str, ats_token: str, career_url: str):
    conn = sqlite3.connect(COMPANIES_DB)
    conn.execute("""
        UPDATE companies SET ats=?, ats_token=?, career_url=?, status='queued'
        WHERE domain=?
    """, (ats, ats_token, career_url, domain))
    conn.commit()
    conn.close()


def get_pending_companies(limit: int = 50) -> list:
    conn = sqlite3.connect(COMPANIES_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM companies
        WHERE status IN ('pending', 'queued')
           OR (status = 'done' AND last_crawled < datetime('now', '-1 day'))
        ORDER BY CASE status WHEN 'queued' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END, last_crawled ASC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_jobs(jobs: list):
    """Insert or update jobs. Marks jobs no longer returned as inactive."""
    if not jobs:
        return
    conn = sqlite3.connect(JOBS_DB)
    now = datetime.now().isoformat()
    inserted = 0
    updated = 0
    for job in jobs:
        existing = conn.execute("SELECT id FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if existing:
            conn.execute("""
                UPDATE jobs SET last_seen=?, is_active=1,
                    title=?, description=?, description_html=?,
                    location=?, apply_url=?, posted_date=?
                WHERE id=?
            """, (
                now, job.get("title"), job.get("description"),
                job.get("description_html"), job.get("location"),
                job.get("apply_url"), job.get("posted_date"), job["id"]
            ))
            updated += 1
        else:
            conn.execute("""
                INSERT INTO jobs (id, title, company_name, company_domain, company_cin,
                    location, department, description, description_html, apply_url,
                    ats, ats_token, exp_level, posted_date, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("id"), job.get("title"), job.get("company_name"),
                job.get("company_domain"), job.get("company_cin"),
                job.get("location"), job.get("department"),
                job.get("description"), job.get("description_html"),
                job.get("apply_url"), job.get("ats"), job.get("ats_token"),
                job.get("exp_level"), job.get("posted_date"), job.get("source"),
            ))
            inserted += 1
    conn.commit()
    conn.close()
    print(f"[DB] Jobs: {inserted} inserted, {updated} updated.")
    return inserted, updated


def get_jobs(
    search: str = "",
    exp_level: str = None,
    ats: str = None,
    company_domain: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    conn = sqlite3.connect(JOBS_DB)
    conn.row_factory = sqlite3.Row

    conditions = ["is_active = 1"]
    params = []

    if search:
        conditions.append("(title LIKE ? OR company_name LIKE ? OR description LIKE ? OR location LIKE ?)")
        term = f"%{search}%"
        params += [term, term, term, term]
    if exp_level:
        conditions.append("exp_level = ?")
        params.append(exp_level)
    if ats:
        conditions.append("ats = ?")
        params.append(ats)
    if company_domain:
        conditions.append("company_domain = ?")
        params.append(company_domain)

    where = "WHERE " + " AND ".join(conditions)

    total = conn.execute(f"SELECT COUNT(*) FROM jobs {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM jobs {where} ORDER BY posted_date DESC, first_seen DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()

    return {
        "total": total,
        "jobs": [dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
    }


def get_stats() -> dict:
    jobs_conn = sqlite3.connect(JOBS_DB)
    companies_conn = sqlite3.connect(COMPANIES_DB)

    total_jobs = jobs_conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    fresher_jobs = jobs_conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND exp_level='entry_level'").fetchone()[0]
    experienced_jobs = jobs_conn.execute("SELECT COUNT(*) FROM jobs WHERE is_active=1 AND exp_level='experienced'").fetchone()[0]
    ats_counts = jobs_conn.execute("SELECT ats, COUNT(*) as cnt FROM jobs WHERE is_active=1 GROUP BY ats").fetchall()

    total_companies = companies_conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    crawled_companies = companies_conn.execute("SELECT COUNT(*) FROM companies WHERE status='done'").fetchone()[0]

    jobs_conn.close()
    companies_conn.close()

    return {
        "total_jobs": total_jobs,
        "fresher_jobs": fresher_jobs,
        "experienced_jobs": experienced_jobs,
        "total_companies": total_companies,
        "crawled_companies": crawled_companies,
        "ats_breakdown": dict(ats_counts),
    }


def export_jobs_json(output_path: str):
    """Export all active jobs as JSON for the frontend."""
    conn = sqlite3.connect(JOBS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM jobs WHERE is_active=1 ORDER BY posted_date DESC"
    ).fetchall()
    conn.close()

    import json
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=2)
    print(f"[DB] Exported {len(rows)} jobs to {output_path}")
