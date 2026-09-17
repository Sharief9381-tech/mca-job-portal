"""
Standalone crawler runner — run this separately to keep fetching jobs.
Usage:
  python crawl.py              # crawl next 20 companies
  python crawl.py --batch 50   # crawl next 50 companies
  python crawl.py --domain zomato.com   # crawl one specific domain
  python crawl.py --schedule   # run on a schedule (every 2 hours)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
from crawler.seed_loader import load_seed_companies
from crawler.engine import run_crawl_batch, crawl_company
from crawler.database import init_databases, upsert_jobs, mark_company_crawled


def main():
    parser = argparse.ArgumentParser(description="MCA Job Crawler")
    parser.add_argument("--batch",    type=int,  default=20,  help="Companies per batch (default: 20)")
    parser.add_argument("--domain",   type=str,  default=None, help="Crawl a single domain")
    parser.add_argument("--schedule", action="store_true",    help="Run on auto-schedule (every 2 hours)")
    parser.add_argument("--seed",     action="store_true",    help="Re-seed company list and exit")
    args = parser.parse_args()

    init_databases()

    if args.seed:
        load_seed_companies()
        return

    if args.domain:
        print(f"Crawling single domain: {args.domain}")
        company = {"domain": args.domain, "name": args.domain, "ats": "unknown", "ats_token": ""}
        jobs, error = crawl_company(company)
        upsert_jobs(jobs)
        mark_company_crawled(args.domain, len(jobs), error)
        print(f"Done: {len(jobs)} jobs found")
        if error:
            print(f"Error: {error}")
        for j in jobs[:10]:
            print(f"  [{j['exp_level']:12}] {j['title'][:55]:<55} → {j['apply_url'][:70]}")
        return

    if args.schedule:
        from crawler.scheduler import scheduler
        print("Starting scheduled crawler (every 2 hours, IST)...")
        run_crawl_batch(batch_size=args.batch)
        scheduler.start()
        return

    # Default: run one batch
    run_crawl_batch(batch_size=args.batch)


if __name__ == "__main__":
    main()
