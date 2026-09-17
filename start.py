"""
MCA Job Portal — One-click startup script.
1. Seeds the company database
2. Runs the first crawl batch
3. Starts the FastAPI backend
"""

import sys
import os
import subprocess
import time
import webbrowser

ROOT = os.path.dirname(__file__)
sys.path.insert(0, ROOT)


def main():
    print("=" * 60)
    print("  MCA JOB PORTAL — LIVE CRAWLER STARTUP")
    print("=" * 60)

    # Step 1: Seed companies into DB
    print("\n[1/3] Seeding company database...")
    from crawler.seed_loader import load_seed_companies
    load_seed_companies()

    # Step 2: Run initial crawl batch
    print("\n[2/3] Running initial crawl batch (first 15 companies)...")
    from crawler.engine import run_crawl_batch
    run_crawl_batch(batch_size=15)

    # Step 3: Start FastAPI server
    print("\n[3/3] Starting API server on http://localhost:8000 ...")
    print("      Frontend running on http://localhost:5500")
    print("\n  Press Ctrl+C to stop.\n")
    print("=" * 60)

    time.sleep(1)
    webbrowser.open("http://localhost:5500")

    os.chdir(ROOT)
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "api.server:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])


if __name__ == "__main__":
    main()
