"""
MCA Job Crawler Engine
Orchestrates: company queue → ATS detection → parser dispatch → DB save
Supports concurrent crawling with rate limiting per domain.
"""

import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from crawler.database import (
    init_databases, get_pending_companies, upsert_jobs,
    mark_company_crawled, update_company_ats, get_stats
)
from crawler.ats_detector import detect_ats

# Import all parsers
from crawler.parsers import greenhouse, lever, workday, darwinbox, taleo, smartrecruiters, generic

# Concurrency settings
MAX_CONCURRENT = 5        # max parallel company crawls
RATE_LIMIT_DELAY = 1.0   # seconds between requests per domain
MAX_RETRIES = 2

# Map ATS name → parser module
ATS_PARSERS = {
    "greenhouse":      greenhouse,
    "lever":           lever,
    "workday":         workday,
    "darwinbox":       darwinbox,
    "taleo":           taleo,
    "smartrecruiters": smartrecruiters,
    "generic":         generic,
    # Aliases
    "tcs_ion":         generic,
    "successfactors":  generic,
    "keka":            generic,
    "zoho_recruit":    generic,
    "freshteam":       generic,
    "ashby":           generic,
    "instahyre":       generic,
    "recruitee":       generic,
    "naukri_rms":      generic,
}


def crawl_company(company: dict) -> tuple[list, str | None]:
    """
    Crawl a single company. Returns (jobs_list, error_message).
    Steps:
    1. If ATS unknown, run ATS detector first.
    2. Dispatch to correct parser.
    3. Return normalized jobs.
    """
    domain = company.get("domain", "")
    ats = company.get("ats", "unknown")
    ats_token = company.get("ats_token", "")
    career_url = company.get("career_url", "")

    print(f"\n[Engine] Crawling: {company.get('name')} ({domain}) | ATS: {ats}")

    # Step 1: Detect ATS if unknown
    if ats in ("unknown", None, ""):
        print(f"[Engine] Detecting ATS for {domain}...")
        detection = detect_ats(domain)
        if detection.get("error"):
            return [], f"ATS detection failed: {detection['error']}"

        ats = detection.get("ats") or "generic"
        ats_token = detection.get("ats_token") or domain
        career_url = detection.get("career_url") or career_url

        # Persist the detected ATS
        update_company_ats(domain, ats, ats_token, career_url)
        print(f"[Engine] Detected ATS: {ats} (token: {ats_token})")

    # Step 2: Dispatch to parser
    parser = ATS_PARSERS.get(ats)
    if not parser:
        return [], f"No parser for ATS: {ats}"

    # Use domain as token fallback
    token = ats_token or domain

    # Build company_info dict for parsers
    company_info = {
        "name": company.get("name") or company.get("brand") or domain,
        "brand": company.get("brand", ""),
        "domain": domain,
        "cin": company.get("cin", ""),
        "career_url": career_url,
    }

    # Step 3: Fetch jobs with retry
    jobs = []
    error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            jobs = parser.fetch_jobs(token, company_info)
            error = None
            break
        except Exception as e:
            error = str(e)
            print(f"[Engine] Attempt {attempt+1} failed for {domain}: {e}")
            time.sleep(2 ** attempt)  # exponential backoff

    return jobs, error


def run_crawl_batch(batch_size: int = 20):
    """
    Pull a batch of companies from the queue and crawl them.
    Saves jobs to DB and exports JSON for the frontend.
    """
    init_databases()

    companies = get_pending_companies(limit=batch_size)
    if not companies:
        print("[Engine] No companies pending crawl.")
        return

    print(f"\n[Engine] Starting crawl batch: {len(companies)} companies")
    print("=" * 60)

    total_jobs = 0
    for i, company in enumerate(companies, 1):
        print(f"\n[{i}/{len(companies)}] {company.get('name', 'Unknown')} ({company.get('domain', '')})")
        domain = company.get("domain", "")
        if not domain:
            print("  Skipping — no domain")
            continue

        try:
            jobs, error = crawl_company(company)
            upsert_jobs(jobs)
            mark_company_crawled(domain, len(jobs), error)
            total_jobs += len(jobs)

            # Rate limit between companies
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            print(f"  [Engine] Unhandled error for {domain}: {e}")
            mark_company_crawled(domain, 0, str(e))

    # Export updated JSON for frontend
    _export_for_frontend()

    stats = get_stats()
    print(f"\n{'='*60}")
    print(f"[Engine] Batch complete!")
    print(f"  Jobs found this run: {total_jobs}")
    print(f"  Total jobs in DB: {stats['total_jobs']}")
    print(f"  Fresher/Entry-Level: {stats['fresher_jobs']}")
    print(f"  Experienced: {stats['experienced_jobs']}")
    print(f"  Companies crawled: {stats['crawled_companies']}/{stats['total_companies']}")
    print("=" * 60)


def _export_for_frontend():
    """Export jobs.json and companies.json for the frontend to consume."""
    from crawler.database import export_jobs_json
    import sqlite3, json, os
    
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    portal_dir = os.path.dirname(os.path.dirname(__file__))

    # Export jobs
    jobs_json = os.path.join(portal_dir, "jobs_live.json")
    export_jobs_json(jobs_json)
    print(f"[Engine] Frontend data exported → jobs_live.json")


if __name__ == "__main__":
    import argparse
    parser_arg = argparse.ArgumentParser(description="MCA Job Crawler Engine")
    parser_arg.add_argument("--batch", type=int, default=20, help="Number of companies per batch")
    parser_arg.add_argument("--company", type=str, help="Crawl a single domain")
    args = parser_arg.parse_args()

    if args.company:
        init_databases()
        company = {"domain": args.company, "name": args.company, "ats": "unknown"}
        jobs, error = crawl_company(company)
        print(f"\nResults for {args.company}:")
        print(f"  Jobs found: {len(jobs)}")
        if error:
            print(f"  Error: {error}")
        for j in jobs[:5]:
            print(f"  - [{j['exp_level']}] {j['title']} | {j['location']} → {j['apply_url']}")
    else:
        run_crawl_batch(batch_size=args.batch)
