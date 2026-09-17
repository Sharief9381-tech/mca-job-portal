"""
Workday ATS Parser
Uses Workday's internal CXS (Candidate Experience) JSON search API.
Endpoint: POST https://{tenant}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
No auth required — same API the career page frontend calls.
"""

import requests
import re
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MCAJobCrawler/1.0)",
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    """
    token format: "{tenant}/{site}"  e.g. "swiggy/Swiggy-Careers"
    """
    parts = token.split("/", 1)
    if len(parts) < 2:
        print(f"[Workday] Invalid token format: {token}")
        return []

    tenant, site = parts[0], parts[1]
    base_url = f"https://{tenant}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"

    all_jobs = []
    offset = 0
    limit = 20  # Workday's default page size

    while True:
        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": ""
        }
        try:
            resp = requests.post(base_url, json=payload, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Workday] Error fetching {token} offset={offset}: {e}")
            break

        job_postings = data.get("jobPostings", [])
        if not job_postings:
            break

        for job in job_postings:
            # Build the apply URL
            ext_path = job.get("externalPath", "")
            apply_url = f"https://{tenant}.myworkdayjobs.com/{site}{ext_path}" if ext_path else ""

            # Location
            location_parts = []
            if job.get("locationsText"):
                location_parts.append(job["locationsText"])

            posted_on = job.get("postedOn", "")
            try:
                # Workday gives "Posted X Days Ago" or ISO date
                if "Posted" in posted_on:
                    posted_date = datetime.now().strftime("%Y-%m-%d")
                else:
                    posted_date = posted_on[:10] if posted_on else datetime.now().strftime("%Y-%m-%d")
            except Exception:
                posted_date = datetime.now().strftime("%Y-%m-%d")

            title = job.get("title", "")
            description = job.get("jobDescription", {})
            if isinstance(description, dict):
                desc_html = description.get("jobDescription", "")
            else:
                desc_html = str(description)

            desc_text = re.sub(r'<[^>]+>', ' ', desc_html).strip()
            desc_text = re.sub(r'\s+', ' ', desc_text)[:1000]

            all_jobs.append({
                "id": f"WD-{job.get('bulletFields', [''])[0] if job.get('bulletFields') else job.get('title', '')}",
                "title": title,
                "company_name": company_info.get("name", ""),
                "company_domain": company_info.get("domain", ""),
                "company_cin": company_info.get("cin", ""),
                "location": ", ".join(location_parts),
                "department": "",
                "description": desc_text,
                "description_html": desc_html,
                "apply_url": apply_url,
                "ats": "Workday",
                "ats_token": token,
                "posted_date": posted_date,
                "exp_level": _infer_exp_level(title, desc_text),
                "source": "workday_api",
            })

        total = data.get("total", 0)
        offset += limit
        if offset >= total or len(all_jobs) >= total:
            break

    print(f"[Workday] {token}: fetched {len(all_jobs)} jobs")
    return all_jobs


def _infer_exp_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    fresher_kws = [
        'fresher', 'entry level', 'entry-level', 'junior', 'trainee',
        'intern', 'graduate', '0-1', '0-2', 'campus', 'associate', 'new grad'
    ]
    senior_kws = [
        'senior', 'lead', 'principal', 'staff', 'manager', 'director',
        'head of', 'vp ', '5+ year', '7+ year', 'architect', 'expert'
    ]
    if any(k in text for k in fresher_kws):
        return 'entry_level'
    if any(k in text for k in senior_kws):
        return 'experienced'
    return 'mid_level'
