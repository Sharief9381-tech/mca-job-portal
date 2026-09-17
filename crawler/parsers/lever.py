"""
Lever ATS Parser
Public Postings API — no auth required.
Endpoint: GET https://api.lever.co/v0/postings/{company}?mode=json
"""

import requests
import re
from datetime import datetime

API_BASE = "https://api.lever.co/v0/postings"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MCAJobCrawler/1.0)"
}


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    """
    Fetches all live jobs for a Lever company slug.
    Returns list of normalized job dicts.
    """
    url = f"{API_BASE}/{token}?mode=json&limit=250"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        postings = resp.json()
    except Exception as e:
        print(f"[Lever] Error fetching {token}: {e}")
        return []

    if not isinstance(postings, list):
        postings = postings.get("postings", [])

    jobs = []
    for posting in postings:
        # Location
        location = posting.get("workplaceType", "")
        categories = posting.get("categories", {})
        if isinstance(categories, dict):
            location = categories.get("location", location)
            department = categories.get("department", "")
            team = categories.get("team", "")
        else:
            department = ""
            team = ""

        # Description — Lever gives plain text lists
        description_text = ""
        description_html = ""
        description_obj = posting.get("description", "")
        if isinstance(description_obj, str):
            description_html = description_obj
            description_text = re.sub(r'<[^>]+>', ' ', description_obj).strip()
            description_text = re.sub(r'\s+', ' ', description_text)[:1000]

        # Additional sections (lists, requirements)
        additional = posting.get("additional", "") or ""
        if additional:
            clean_add = re.sub(r'<[^>]+>', ' ', additional).strip()
            description_text = (description_text + " " + clean_add)[:1000]

        # Posted date — Lever gives Unix ms timestamp
        created_at = posting.get("createdAt", 0)
        try:
            posted_date = datetime.fromtimestamp(
                created_at / 1000
            ).strftime("%Y-%m-%d") if created_at else datetime.now().strftime("%Y-%m-%d")
        except Exception:
            posted_date = datetime.now().strftime("%Y-%m-%d")

        jobs.append({
            "id": f"LV-{posting.get('id', '')}",
            "title": posting.get("text", ""),
            "company_name": company_info.get("name", ""),
            "company_domain": company_info.get("domain", ""),
            "company_cin": company_info.get("cin", ""),
            "location": location,
            "department": department,
            "team": team,
            "description": description_text,
            "description_html": description_html,
            "apply_url": posting.get("applyUrl") or posting.get("hostedUrl", ""),
            "ats": "Lever",
            "ats_token": token,
            "posted_date": posted_date,
            "exp_level": _infer_exp_level(posting.get("text", ""), description_text),
            "source": "lever_api",
        })

    print(f"[Lever] {token}: fetched {len(jobs)} jobs")
    return jobs


def _infer_exp_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    fresher_kws = [
        'fresher', 'fresh graduate', 'entry level', 'entry-level', 'junior',
        'trainee', 'intern', 'graduate', '0-1', '0-2', '0 year', '1 year',
        'campus', 'associate', 'new grad'
    ]
    senior_kws = [
        'senior', 'lead', 'principal', 'staff', 'manager', 'director',
        'head of', 'vp ', 'vice president', '5+ year', '7+ year', '10+ year',
        'architect', 'expert'
    ]
    if any(k in text for k in fresher_kws):
        return 'entry_level'
    if any(k in text for k in senior_kws):
        return 'experienced'
    return 'mid_level'
