"""
Generic Playwright-based scraper for custom career pages.
Used for TCS iON, SAP SuccessFactors, Instahyre, Keka, and any site 
that requires JS rendering.
"""

import re
import json
import asyncio
from datetime import datetime

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


async def fetch_jobs_async(career_url: str, company_info: dict) -> list[dict]:
    """
    Renders the career page using Playwright (headless Chromium),
    extracts job listings from the rendered HTML.
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[Generic] Playwright not available")
        return []

    jobs = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0"
        )
        page = await context.new_page()

        try:
            await page.goto(career_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)  # extra wait for JS rendering

            html = await page.content()
            page_url = page.url

            # Strategy 1: Look for JSON-LD structured data (job postings)
            json_ld_jobs = _extract_json_ld_jobs(html, company_info, page_url)
            if json_ld_jobs:
                jobs = json_ld_jobs
            else:
                # Strategy 2: Find job listing links and titles from rendered HTML
                jobs = await _extract_jobs_from_dom(page, company_info, page_url)

        except Exception as e:
            print(f"[Generic] Error scraping {career_url}: {e}")
        finally:
            await browser.close()

    print(f"[Generic] {career_url}: found {len(jobs)} jobs")
    return jobs


def fetch_jobs(token: str, company_info: dict) -> list[dict]:
    """Sync wrapper for the async scraper."""
    career_url = company_info.get("career_url") or f"https://{company_info.get('domain', '')}/careers"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(fetch_jobs_async(career_url, company_info))
    except Exception as e:
        print(f"[Generic] Async error: {e}")
        return []
    finally:
        loop.close()


def _extract_json_ld_jobs(html: str, company_info: dict, base_url: str) -> list[dict]:
    """Extract structured job postings from JSON-LD schema.org markup."""
    jobs = []
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE
    )
    for match in pattern.finditer(html):
        try:
            data = json.loads(match.group(1))
            # Handle both single object and array
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "JobPosting":
                    title = item.get("title", "")
                    description_html = item.get("description", "")
                    desc_text = re.sub(r'<[^>]+>', ' ', description_html).strip()[:1000]
                    location = ""
                    loc_obj = item.get("jobLocation", {})
                    if isinstance(loc_obj, dict):
                        addr = loc_obj.get("address", {})
                        if isinstance(addr, dict):
                            location = addr.get("addressLocality", "") or addr.get("addressRegion", "")
                    apply_url = item.get("url") or base_url

                    jobs.append({
                        "id": f"GN-{hash(title + apply_url) % 999999}",
                        "title": title,
                        "company_name": company_info.get("name", ""),
                        "company_domain": company_info.get("domain", ""),
                        "company_cin": company_info.get("cin", ""),
                        "location": location,
                        "department": item.get("occupationalCategory", ""),
                        "description": desc_text,
                        "description_html": description_html,
                        "apply_url": apply_url,
                        "ats": "Generic",
                        "ats_token": company_info.get("domain", ""),
                        "posted_date": _parse_date(item.get("datePosted", "")),
                        "exp_level": _infer_exp_level(title, desc_text),
                        "source": "jsonld",
                    })
        except Exception:
            continue
    return jobs


async def _extract_jobs_from_dom(page, company_info: dict, base_url: str) -> list[dict]:
    """Extract job links and titles directly from the rendered DOM."""
    jobs = []

    # Common job listing selectors across custom ATS pages
    selectors = [
        'a[href*="/job"]',
        'a[href*="/career"]',
        'a[href*="/opening"]',
        'a[href*="/vacancy"]',
        '.job-title a',
        '.job-listing a',
        '.career-item a',
        '[data-job-id] a',
        '.position a',
        '.opening a',
    ]

    found_links = set()
    for selector in selectors:
        try:
            elements = await page.query_selector_all(selector)
            for el in elements[:50]:  # cap per selector
                href = await el.get_attribute("href") or ""
                text = (await el.inner_text()).strip()
                if href and text and len(text) > 5 and href not in found_links:
                    found_links.add(href)
                    # Make absolute URL
                    if href.startswith("/"):
                        from urllib.parse import urljoin
                        href = urljoin(base_url, href)
                    elif not href.startswith("http"):
                        continue

                    jobs.append({
                        "id": f"GN-{hash(text + href) % 999999}",
                        "title": text,
                        "company_name": company_info.get("name", ""),
                        "company_domain": company_info.get("domain", ""),
                        "company_cin": company_info.get("cin", ""),
                        "location": "",
                        "department": "",
                        "description": "",
                        "description_html": "",
                        "apply_url": href,
                        "ats": "Generic",
                        "ats_token": company_info.get("domain", ""),
                        "posted_date": datetime.now().strftime("%Y-%m-%d"),
                        "exp_level": _infer_exp_level(text, ""),
                        "source": "dom_scrape",
                    })
        except Exception:
            continue

    return jobs


def _parse_date(date_str: str) -> str:
    try:
        if date_str:
            return date_str[:10]
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-%d")


def _infer_exp_level(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    if any(k in text for k in ['fresher', 'entry level', 'junior', 'trainee', 'intern', 'graduate', 'associate']):
        return 'entry_level'
    if any(k in text for k in ['senior', 'lead', 'principal', 'manager', 'director', 'head of', 'vp ']):
        return 'experienced'
    return 'mid_level'
