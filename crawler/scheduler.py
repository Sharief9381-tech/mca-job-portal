"""
Daily job refresh scheduler using APScheduler.
Runs the crawler engine on a schedule and keeps jobs_live.json fresh.
"""

import sys
import os
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from crawler.engine import run_crawl_batch
from crawler.seed_loader import load_seed_companies

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("MCAScheduler")

scheduler = BlockingScheduler(timezone="Asia/Kolkata")

# Crawl 50 companies every 2 hours throughout the day
@scheduler.scheduled_job(CronTrigger(hour="*/2", minute=0))
def crawl_batch_job():
    log.info("Scheduled crawl batch starting...")
    try:
        run_crawl_batch(batch_size=50)
    except Exception as e:
        log.error(f"Crawl batch failed: {e}")

# Re-seed new companies daily at midnight
@scheduler.scheduled_job(CronTrigger(hour=0, minute=30))
def reseed_job():
    log.info("Reseeding company queue...")
    try:
        load_seed_companies()
    except Exception as e:
        log.error(f"Reseed failed: {e}")


if __name__ == "__main__":
    log.info("Starting MCA Job Crawler Scheduler (IST timezone)")
    log.info("Schedule: crawl 50 companies every 2 hours, reseed daily at 00:30")
    
    # Run one batch immediately on startup
    log.info("Running initial batch...")
    run_crawl_batch(batch_size=30)
    
    log.info("Scheduler running. Press Ctrl+C to stop.")
    scheduler.start()
