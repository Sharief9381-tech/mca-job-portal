"""
ATS Detector — fingerprints which Applicant Tracking System a company domain uses.
Checks HTTP headers, HTML content, and known URL patterns.
"""

import re
import requests
from urllib.parse import urljoin

TIMEOUT = 10
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
}

# ATS fingerprint rules: (pattern_in_html_or_headers, ats_name, career_url_template)
ATS_SIGNATURES = [
    # Greenhouse
    (r'boards\.greenhouse\.io|greenhouse\.io/embed', 'greenhouse', None),
    # Lever
    (r'jobs\.lever\.co', 'lever', None),
    # Workday
    (r'myworkdayjobs\.com|wd\d+\.myworkdayjobs', 'workday', None),
    # Darwinbox
    (r'darwinbox\.com|darwin\.box', 'darwinbox', None),
    # Taleo
    (r'taleo\.net|tbe\.taleo\.net', 'taleo', None),
    # SAP SuccessFactors
    (r'successfactors\.com|sapsf\.com', 'successfactors', None),
    # SmartRecruiters
    (r'smartrecruiters\.com', 'smartrecruiters', None),
    # Ashby
    (r'ashbyhq\.com|jobs\.ashbyhq', 'ashby', None),
    # Keka
    (r'keka\.com|kekaats\.com', 'keka', None),
    # iSmartRecruit / Zoho Recruit
    (r'zohorecruit\.com|zoho\.com/recruit', 'zoho_recruit', None),
    # Freshteam
    (r'freshteam\.com|freshworks\.com/hrms', 'freshteam', None),
    # Naukri RMS (company internal ATS)
    (r'naukri\.com/mnj', 'naukri_rms', None),
    # TCS iON
    (r'tcsion\.com|nextstep\.tcs\.com', 'tcs_ion', None),
    # Instahyre
    (r'instahyre\.com', 'instahyre', None),
    # Recruitee
    (r'recruitee\.com', 'recruitee', None),
]

# Known career URL patterns to probe per domain
CAREER_URL_PATHS = [
    '/careers', '/jobs', '/career', '/join-us', '/join', '/work-with-us',
    '/about/careers', '/company/careers', '/en/careers', '/openings',
    '/opportunities', '/hiring', '/vacancies', '/current-openings',
]


def detect_ats(domain: str) -> dict:
    """
    Given a company domain (e.g. 'zomato.com'), returns:
    {
        'domain': str,
        'career_url': str | None,
        'ats': str | None,   # 'greenhouse', 'lever', 'workday', etc.
        'ats_token': str | None,  # board slug / tenant ID
        'error': str | None
    }
    """
    result = {
        'domain': domain,
        'career_url': None,
        'ats': None,
        'ats_token': None,
        'error': None,
    }

    # Step 1: Probe candidate career URLs
    career_url = _find_career_url(domain)
    if not career_url:
        result['error'] = 'No career page found'
        return result

    result['career_url'] = career_url

    # Step 2: Fetch the page and fingerprint ATS
    try:
        resp = requests.get(career_url, headers=HEADERS, timeout=TIMEOUT,
                            allow_redirects=True)
        html = resp.text
        final_url = resp.url

        # Check the final redirected URL too (e.g. domain redirects to Lever)
        combined = html + final_url + str(resp.headers)

        for pattern, ats_name, _ in ATS_SIGNATURES:
            if re.search(pattern, combined, re.IGNORECASE):
                result['ats'] = ats_name
                result['ats_token'] = _extract_token(combined, final_url, ats_name)
                result['career_url'] = final_url
                return result

        # Step 3: Check for embedded iframes or script src pointing to ATS
        iframe_match = re.search(
            r'<iframe[^>]+src=["\']([^"\']*(?:greenhouse|lever|workday|darwinbox|taleo)[^"\']*)["\']',
            html, re.IGNORECASE
        )
        if iframe_match:
            embedded_url = iframe_match.group(1)
            for pattern, ats_name, _ in ATS_SIGNATURES:
                if re.search(pattern, embedded_url, re.IGNORECASE):
                    result['ats'] = ats_name
                    result['ats_token'] = _extract_token(embedded_url, embedded_url, ats_name)
                    return result

        # No ATS detected — mark as custom/generic
        result['ats'] = 'generic'

    except requests.exceptions.SSLError:
        # Retry without SSL verification for old Indian company sites
        try:
            resp = requests.get(career_url, headers=HEADERS, timeout=TIMEOUT,
                                allow_redirects=True, verify=False)
            result['ats'] = 'generic'
            result['career_url'] = resp.url
        except Exception as e:
            result['error'] = str(e)
    except Exception as e:
        result['error'] = str(e)

    return result


def _find_career_url(domain: str) -> str | None:
    """Probes common career page paths to find a working one."""
    base_urls = [f'https://{domain}', f'https://www.{domain}']
    for base in base_urls:
        for path in CAREER_URL_PATHS:
            url = base + path
            try:
                resp = requests.head(url, headers=HEADERS, timeout=6,
                                     allow_redirects=True)
                if resp.status_code in (200, 301, 302, 303):
                    return url
            except Exception:
                continue
    return None


def _extract_token(text: str, url: str, ats: str) -> str | None:
    """Extracts the board token / tenant slug for a given ATS."""
    try:
        if ats == 'greenhouse':
            m = re.search(r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', text)
            if m:
                return m.group(1)
            m = re.search(r'boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_-]+)', text)
            if m:
                return m.group(1)

        elif ats == 'lever':
            m = re.search(r'jobs\.lever\.co/([a-zA-Z0-9_-]+)', text)
            if m:
                return m.group(1)

        elif ats == 'workday':
            # Pattern: {tenant}.myworkdayjobs.com/{site}
            m = re.search(r'([a-zA-Z0-9_-]+)\.myworkdayjobs\.com/([a-zA-Z0-9_-]+)', text)
            if m:
                return f'{m.group(1)}/{m.group(2)}'

        elif ats == 'darwinbox':
            m = re.search(r'([a-zA-Z0-9_-]+)\.darwinbox\.com', text)
            if m:
                return m.group(1)

        elif ats == 'taleo':
            m = re.search(r'([a-zA-Z0-9_-]+)\.taleo\.net', text)
            if m:
                return m.group(1)

        elif ats == 'successfactors':
            m = re.search(r'([a-zA-Z0-9_-]+)\.successfactors\.com', text)
            if m:
                return m.group(1)

        elif ats == 'smartrecruiters':
            m = re.search(r'smartrecruiters\.com/([a-zA-Z0-9_-]+)', text)
            if m:
                return m.group(1)

        elif ats == 'ashby':
            m = re.search(r'jobs\.ashbyhq\.com/([a-zA-Z0-9_-]+)', text)
            if m:
                return m.group(1)

    except Exception:
        pass
    return None
