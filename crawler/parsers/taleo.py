"""
Taleo ATS Parser
Oracle Taleo exposes an XML job feed at: https://{tenant}.taleo.net/careersection/jobboard/joblist.ftl?lang=en
Also has a REST-like JSON API on some instances.
"""

import requests
import re
import json
from datetime import datetime
try:
    import xml.etree.ElementTree as ET
except ImportError:
    ET = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MCAJobCrawler/1.0)",
    "Accept": "application/json, text/xml, */*",
}


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    """
    token: Taleo tenant slug e.g. 'sunpharma'
    """
    jobs = []

    # Try Taleo JSON API endpoint (newer instances)
    json_url = f"https://{token}.taleo.net/careersection/rest/jobboard/job/list"
    try:
        resp = requests.get(
            json_url,
            params={"lang": "en", "start": 0, "end": 100},
            headers=HEADERS,
            timeout=15
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                raw_jobs = (
                    data.get("jobs") or
                    data.get("jobList") or
                    data.get("requisitions") or []
                )
                if raw_jobs:
                    for job in raw_jobs:
                        jobs.append(_normalize_taleo_job(job, token, company_info))
                    print(f"[Taleo] {token}: fetched {len(jobs)} jobs via JSON API")
                    return jobs
            except Exception:
                pass
    except Exception:
        pass

    # Try Taleo XML job feed
    xml_url = f"https://{token}.taleo.net/careersection/jobboard/joblist.ftl?lang=en&radiusType=K&searchExpanded=true"
    try:
        resp = requests.get(xml_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200 and ET:
            jobs = _parse_taleo_html(resp.text, token, company_info)
    except Exception as e:
        print(f"[Taleo] Error fetching {token}: {e}")

    print(f"[Taleo] {token}: fetched {len(jobs)} jobs")
    return jobs


def _normalize_taleo_job(job: dict, token: str, company_info: dict) -> dict:
    title = (
        job.get("jobTitle") or job.get("title") or
        job.get("requisitionTitle") or ""
    )
    location = (
        job.get("jobLocation") or job.get("location") or
        job.get("city") or ""
    )
    if isinstance(location, dict):
        location = location.get("location") or location.get("name") or ""

    department = job.get("department") or job.get("jobFamily") or ""
    description = job.get("jobDescription") or job.get("description") or ""
    job_id = job.get("requisitionId") or job.get("jobId") or job.get("id") or ""

    desc_text = re.sub(r'<[^>]+>', ' ', str(description)).strip()
    desc_text = re.sub(r'\s+', ' ', desc_text)[:1000]

    apply_url = (
        job.get("applyUrl") or job.get("apply_url") or
        f"https://{token}.taleo.net/careersection/1/jobdetail.ftl?job={job_id}&lang=en"
    )

    return {
        "id": f"TL-{job_id}",
        "title": title,
        "company_name": company_info.get("name", ""),
        "company_domain": company_info.get("domain", ""),
        "company_cin": company_info.get("cin", ""),
        "location": str(location),
        "department": str(department),
        "description": desc_text,
        "description_html": str(description),
        "apply_url": apply_url,
        "ats": "Taleo",
        "ats_token": token,
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "exp_level": _infer_exp_level(title, desc_text),
        "source": "taleo_api",
    }


def _parse_taleo_html(html: str, token: str, company_info: dict) -> list[dict]:
    """Parse job titles and links from Taleo HTML listing page."""
    jobs = []
    # Find job rows in Taleo's HTML table
    rows = re.findall(
        r'jobdetail\.ftl\?job=(\d+)[^"]*"[^>]*>([^<]+)</a>',
        html, re.IGNORECASE
    )
    for job_id, title in rows:
        apply_url = f"https://{token}.taleo.net/careersection/1/jobdetail.ftl?job={job_id}&lang=en"
        jobs.append({
            "id": f"TL-{job_id}",
            "title": title.strip(),
            "company_name": company_info.get("name", ""),
            "company_domain": company_info.get("domain", ""),
            "company_cin": company_info.get("cin", ""),
            "location": "",
            "department": "",
            "description": "",
            "description_html": "",
            "apply_url": apply_url,
            "ats": "Taleo",
            "ats_token": token,
            "posted_date": datetime.now().strftime("%Y-%m-%d"),
            "exp_level": _infer_exp_level(title, ""),
            "source": "taleo_html",
        })
    return jobs


def _infer_exp_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    if any(k in text for k in ['fresher', 'entry level', 'junior', 'trainee', 'intern', 'graduate']):
        return 'entry_level'
    if any(k in text for k in ['senior', 'lead', 'principal', 'manager', 'director', 'head of']):
        return 'experienced'
    return 'mid_level'
