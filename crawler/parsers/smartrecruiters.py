"""
SmartRecruiters ATS Parser
Public jobs API: GET https://api.smartrecruiters.com/v1/companies/{token}/postings
"""

import requests
import re
from datetime import datetime

API_BASE = "https://api.smartrecruiters.com/v1/companies"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MCAJobCrawler/1.0)"}


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    all_jobs = []
    offset = 0
    limit = 100
    while True:
        url = f"{API_BASE}/{token}/postings"
        try:
            resp = requests.get(url, headers=HEADERS, params={"limit": limit, "offset": offset}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[SmartRecruiters] Error: {e}")
            break

        postings = data.get("content", [])
        if not postings:
            break

        for job in postings:
            loc = job.get("location", {})
            location = f"{loc.get('city', '')} {loc.get('country', '')}".strip()
            title = job.get("name", "")
            job_id = job.get("id", "")
            apply_url = f"https://careers.smartrecruiters.com/{token}/{job_id}"
            desc = job.get("jobAd", {}).get("sections", {})
            desc_text = ""
            if desc:
                for section in desc.values():
                    if isinstance(section, dict):
                        desc_text += re.sub(r'<[^>]+>', ' ', section.get("text", "")).strip() + " "
            desc_text = desc_text[:1000]

            all_jobs.append({
                "id": f"SR-{job_id}",
                "title": title,
                "company_name": company_info.get("name", ""),
                "company_domain": company_info.get("domain", ""),
                "company_cin": company_info.get("cin", ""),
                "location": location,
                "department": job.get("department", {}).get("label", "") if isinstance(job.get("department"), dict) else "",
                "description": desc_text,
                "description_html": "",
                "apply_url": apply_url,
                "ats": "SmartRecruiters",
                "ats_token": token,
                "posted_date": (job.get("releasedDate") or datetime.now().strftime("%Y-%m-%d"))[:10],
                "exp_level": _infer_exp_level(title, desc_text),
                "source": "smartrecruiters_api",
            })

        total = data.get("totalFound", 0)
        offset += limit
        if offset >= total:
            break

    print(f"[SmartRecruiters] {token}: fetched {len(all_jobs)} jobs")
    return all_jobs


def _infer_exp_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    if any(k in text for k in ['fresher', 'entry level', 'junior', 'trainee', 'intern', 'graduate']):
        return 'entry_level'
    if any(k in text for k in ['senior', 'lead', 'principal', 'manager', 'director']):
        return 'experienced'
    return 'mid_level'
