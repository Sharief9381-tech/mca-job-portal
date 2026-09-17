"""
Darwinbox ATS Parser
Darwinbox career pages are JS-rendered but follow a predictable pattern.
Most Indian companies using Darwinbox have subdomain: {company}.darwinbox.com/ms/candidate/careers
"""

import requests
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0",
    "Accept": "application/json, text/html",
    "X-Requested-With": "XMLHttpRequest",
}


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    """
    token: darwinbox subdomain slug e.g. 'paytm'
    Tries the Darwinbox public careers JSON endpoint.
    Falls back to HTML scraping if needed.
    """
    # Darwinbox careers API endpoint pattern
    api_url = f"https://{token}.darwinbox.com/ms/candidate/careers/listCareers"
    html_url = f"https://{token}.darwinbox.com/ms/candidate/careers"

    jobs = []

    # Try JSON API first
    try:
        resp = requests.post(
            api_url,
            json={"searchText": "", "department": "", "location": "", "page": 1},
            headers=HEADERS,
            timeout=15
        )
        if resp.status_code == 200:
            try:
                data = resp.json()
                raw_jobs = data.get("data", data.get("jobs", data.get("careers", [])))
                if isinstance(raw_jobs, list) and raw_jobs:
                    for job in raw_jobs:
                        jobs.append(_normalize_darwinbox_job(job, token, company_info))
                    print(f"[Darwinbox] {token}: fetched {len(jobs)} jobs via API")
                    return jobs
            except Exception:
                pass
    except Exception:
        pass

    # Fallback: scrape HTML career listing page
    try:
        resp = requests.get(html_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            jobs = _parse_darwinbox_html(resp.text, token, company_info)
            print(f"[Darwinbox] {token}: fetched {len(jobs)} jobs via HTML")
    except Exception as e:
        print(f"[Darwinbox] Error fetching {token}: {e}")

    return jobs


def _normalize_darwinbox_job(job: dict, token: str, company_info: dict) -> dict:
    title = job.get("job_title") or job.get("title") or job.get("name") or ""
    location = job.get("location") or job.get("city") or ""
    department = job.get("department") or job.get("function") or ""
    description = job.get("job_description") or job.get("description") or ""
    job_id = job.get("id") or job.get("job_id") or ""

    desc_text = re.sub(r'<[^>]+>', ' ', str(description)).strip()
    desc_text = re.sub(r'\s+', ' ', desc_text)[:1000]

    apply_url = (
        job.get("apply_url") or
        job.get("apply_link") or
        f"https://{token}.darwinbox.com/ms/candidate/careers/{job_id}"
    )

    return {
        "id": f"DB-{job_id}",
        "title": title,
        "company_name": company_info.get("name", ""),
        "company_domain": company_info.get("domain", ""),
        "company_cin": company_info.get("cin", ""),
        "location": location,
        "department": department,
        "description": desc_text,
        "description_html": str(description),
        "apply_url": apply_url,
        "ats": "Darwinbox",
        "ats_token": token,
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "exp_level": _infer_exp_level(title, desc_text),
        "source": "darwinbox_api",
    }


def _parse_darwinbox_html(html: str, token: str, company_info: dict) -> list[dict]:
    """Parse job listings from Darwinbox HTML career page."""
    jobs = []
    # Darwinbox embeds job data as JSON in script tags
    json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html, re.DOTALL)
    if json_match:
        try:
            import json
            state = json.loads(json_match.group(1))
            raw_jobs = state.get("careers", {}).get("jobs", [])
            for job in raw_jobs:
                jobs.append(_normalize_darwinbox_job(job, token, company_info))
        except Exception:
            pass

    return jobs


def _infer_exp_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    fresher_kws = [
        'fresher', 'entry level', 'entry-level', 'junior', 'trainee',
        'intern', 'graduate', '0-1', '0-2', 'campus', 'associate'
    ]
    senior_kws = [
        'senior', 'lead', 'principal', 'staff', 'manager', 'director',
        'head of', 'vp ', '5+ year', '7+ year', 'architect'
    ]
    if any(k in text for k in fresher_kws):
        return 'entry_level'
    if any(k in text for k in senior_kws):
        return 'experienced'
    return 'mid_level'
