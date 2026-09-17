"""
Greenhouse ATS Parser
Public Job Board API — no auth required for GET requests.
Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
"""

import requests
from datetime import datetime

API_BASE = "https://boards-api.greenhouse.io/v1/boards"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MCAJobCrawler/1.0)"
}


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    """
    Fetches all live jobs for a Greenhouse board token.
    Returns list of normalized job dicts.
    """
    url = f"{API_BASE}/{token}/jobs?content=true"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[Greenhouse] Error fetching {token}: {e}")
        return []

    jobs = []
    for job in data.get("jobs", []):
        # Extract location
        locations = job.get("location", {})
        location_name = locations.get("name", "") if isinstance(locations, dict) else str(locations)

        # Parse description — Greenhouse gives HTML content
        description_html = ""
        description_text = ""
        if "content" in job:
            description_html = job["content"]
            # Strip HTML tags for plain text
            import re
            description_text = re.sub(r'<[^>]+>', ' ', description_html).strip()
            description_text = re.sub(r'\s+', ' ', description_text)[:1000]

        # Departments
        departments = [d.get("name", "") for d in job.get("departments", [])]

        # Posted date
        posted_at = job.get("updated_at") or job.get("absolute_url", "")
        try:
            posted_date = datetime.fromisoformat(
                posted_at.replace("Z", "+00:00")
            ).strftime("%Y-%m-%d") if posted_at else datetime.now().strftime("%Y-%m-%d")
        except Exception:
            posted_date = datetime.now().strftime("%Y-%m-%d")

        jobs.append({
            "id": f"GH-{job.get('id', '')}",
            "title": job.get("title", ""),
            "company_name": company_info.get("name", ""),
            "company_domain": company_info.get("domain", ""),
            "company_cin": company_info.get("cin", ""),
            "location": location_name,
            "department": ", ".join(departments),
            "description": description_text,
            "description_html": description_html,
            "apply_url": job.get("absolute_url", ""),
            "ats": "Greenhouse",
            "ats_token": token,
            "posted_date": posted_date,
            "exp_level": _infer_exp_level(job.get("title", ""), description_text),
            "source": "greenhouse_api",
        })

    print(f"[Greenhouse] {token}: fetched {len(jobs)} jobs")
    return jobs


def _infer_exp_level(title: str, description: str) -> str:
    """Infers experience level from job title and description keywords."""
    text = (title + " " + description).lower()
    fresher_kws = [
        'fresher', 'fresh graduate', 'entry level', 'entry-level', 'junior',
        'trainee', 'intern', 'graduate', '0-1', '0-2', '0 year', '1 year',
        'campus', 'batch 2025', 'batch 2026', 'associate'
    ]
    senior_kws = [
        'senior', 'lead', 'principal', 'staff', 'manager', 'director',
        'head of', 'vp ', 'vice president', '5+ year', '7+ year', '10+ year',
        'architect', 'expert', 'specialist'
    ]
    if any(k in text for k in fresher_kws):
        return 'entry_level'
    if any(k in text for k in senior_kws):
        return 'experienced'
    return 'mid_level'
