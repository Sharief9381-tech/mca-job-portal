"""
Seed Loader — loads companies from company_career_sites.csv into the DB.
Covers 238 Indian companies across all sectors.
"""
import sys, os, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from crawler.database import init_databases, bulk_insert_companies

# Map ATS names to our parser keys
ATS_MAP = {
    'GREENHOUSE':      'greenhouse',
    'LEVER':           'lever',
    'SMARTRECRUITERS': 'smartrecruiters',
    'DARWINBOX':       'darwinbox',
    'WORKDAY':         'workday',
    'TALEO':           'taleo',
    'SUCCESSFACTORS':  'successfactors',
    'CUSTOM':          'generic',
    'CUSTOM/ION':      'tcs_ion',
    'UNKNOWN':         'unknown',
}

def load_seed_companies():
    """Load all companies from company_career_sites.csv into the database."""
    init_databases()

    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'company_career_sites.csv')

    if not os.path.exists(csv_path):
        print(f"[Seed] CSV not found at {csv_path}, using hardcoded fallback.")
        _load_hardcoded_fallback()
        return

    companies = []
    seen = set()

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = (row.get('domain') or '').strip()
            if not domain or domain in seen:
                continue
            seen.add(domain)

            ats_raw = (row.get('ats') or 'UNKNOWN').strip().upper()
            ats     = ATS_MAP.get(ats_raw, 'generic')

            # Derive ATS token from career_url
            career_url = (row.get('career_url') or '').strip()
            ats_token  = _extract_token(career_url, ats, domain)

            companies.append({
                'cin':           (row.get('cin') or '').strip(),
                'name':          (row.get('name') or '').strip(),
                'brand':         (row.get('brand') or '').strip(),
                'domain':        domain,
                'roc':           '',
                'incorporated':  None,
                'company_class': '',
                'capital':       '',
                'career_url':    career_url,
                'ats':           ats,
                'ats_token':     ats_token,
            })

    bulk_insert_companies(companies)
    print(f"[Seed] Loaded {len(companies)} companies from CSV.")


def _extract_token(career_url: str, ats: str, domain: str) -> str:
    """Extract ATS board token from career URL."""
    import re
    try:
        if ats == 'greenhouse':
            m = re.search(r'greenhouse\.io/([a-zA-Z0-9_-]+)', career_url)
            return m.group(1) if m else domain
        elif ats == 'lever':
            m = re.search(r'lever\.co/([a-zA-Z0-9_-]+)', career_url)
            return m.group(1) if m else domain
        elif ats == 'smartrecruiters':
            m = re.search(r'smartrecruiters\.com/([a-zA-Z0-9_-]+)', career_url)
            return m.group(1) if m else domain
        elif ats == 'darwinbox':
            m = re.search(r'([a-zA-Z0-9_-]+)\.darwinbox', career_url)
            return m.group(1) if m else domain
        elif ats == 'workday':
            m = re.search(r'([a-zA-Z0-9_-]+)\.(?:wd\d+|myworkdayjobs)\.com/([a-zA-Z0-9_-]+)', career_url)
            return f"{m.group(1)}/{m.group(2)}" if m else domain
        elif ats == 'taleo':
            m = re.search(r'([a-zA-Z0-9_-]+)\.taleo\.net', career_url)
            return m.group(1) if m else domain
    except Exception:
        pass
    return domain


def _load_hardcoded_fallback():
    """Minimal fallback when CSV is not available (e.g. first Render boot)."""
    companies = [
        {"cin":"U72200KA2013PTC097332","name":"RAZORPAY SOFTWARE PRIVATE LIMITED","brand":"Razorpay","domain":"razorpay.com","roc":"ROC Bangalore","incorporated":2013,"company_class":"Private","capital":"₹3,000 Cr+","career_url":"https://boards.greenhouse.io/razorpaysoftwareprivatelimited","ats":"greenhouse","ats_token":"razorpaysoftwareprivatelimited"},
        {"cin":"U72200MH2007PTC173821","name":"ONE97 COMMUNICATIONS LIMITED","brand":"Paytm","domain":"paytm.com","roc":"ROC Noida","incorporated":2007,"company_class":"Public","capital":"₹7,000 Cr+","career_url":"https://jobs.lever.co/paytm","ats":"lever","ats_token":"paytm"},
        {"cin":"U74999KA2018PTC118991","name":"DREAMPLUG TECHNOLOGIES PRIVATE LIMITED","brand":"CRED","domain":"cred.club","roc":"ROC Bangalore","incorporated":2018,"company_class":"Private","capital":"₹800 Cr+","career_url":"https://jobs.lever.co/cred","ats":"lever","ats_token":"cred"},
        {"cin":"U72900KA2019PTC134567","name":"MEESHO SUPPLY CHAIN PRIVATE LIMITED","brand":"Meesho","domain":"meesho.com","roc":"ROC Bangalore","incorporated":2015,"company_class":"Private","capital":"₹2,000 Cr+","career_url":"https://jobs.lever.co/meesho","ats":"lever","ats_token":"meesho"},
        {"cin":"U72900TN2010PLC075256","name":"FRESHWORKS INC INDIA PRIVATE LIMITED","brand":"Freshworks","domain":"freshworks.com","roc":"ROC Chennai","incorporated":2010,"company_class":"Private","capital":"₹5,000 Cr+","career_url":"https://careers.smartrecruiters.com/Freshworks","ats":"smartrecruiters","ats_token":"Freshworks"},
        {"cin":"U72900KA2019PTC125488","name":"SWIGGY BUNDL TECHNOLOGIES PRIVATE LIMITED","brand":"Swiggy","domain":"swiggy.com","roc":"ROC Bangalore","incorporated":2014,"company_class":"Private","capital":"₹5,000 Cr+","career_url":"https://careers.smartrecruiters.com/Swiggy","ats":"smartrecruiters","ats_token":"Swiggy"},
        {"cin":"U74999KA2015PTC082455","name":"GROWW INVEST TECH PRIVATE LIMITED","brand":"Groww","domain":"groww.in","roc":"ROC Bangalore","incorporated":2016,"company_class":"Private","capital":"₹500 Cr+","career_url":"https://boards.greenhouse.io/groww","ats":"greenhouse","ats_token":"groww"},
        {"cin":"U72900KA2011PTC058998","name":"INMOBI PRIVATE LIMITED","brand":"InMobi","domain":"inmobi.com","roc":"ROC Bangalore","incorporated":2007,"company_class":"Private","capital":"₹1,000 Cr+","career_url":"https://boards.greenhouse.io/inmobi","ats":"greenhouse","ats_token":"inmobi"},
        {"cin":"U63030KA2014PTC077962","name":"PORTER LOGISTICS PRIVATE LIMITED","brand":"Porter","domain":"porter.in","roc":"ROC Bangalore","incorporated":2014,"company_class":"Private","capital":"₹500 Cr+","career_url":"https://boards.greenhouse.io/porter","ats":"greenhouse","ats_token":"porter"},
        {"cin":"U72900KA2011PTC058999","name":"GLANCE DIGITAL EXPERIENCE PVT LTD","brand":"Glance","domain":"glance.com","roc":"ROC Bangalore","incorporated":2019,"company_class":"Private","capital":"₹500 Cr+","career_url":"https://boards.greenhouse.io/glance","ats":"greenhouse","ats_token":"glance"},
        {"cin":"U65990KA2019PTC124778","name":"EPIFI TECHNOLOGIES PRIVATE LIMITED","brand":"Fi Money","domain":"fi.money","roc":"ROC Bangalore","incorporated":2019,"company_class":"Private","capital":"₹500 Cr+","career_url":"https://jobs.lever.co/epifi","ats":"lever","ats_token":"epifi"},
        {"cin":"U72900KA2018PTC109577","name":"KARNA LEARNING PRIVATE LIMITED","brand":"Unacademy","domain":"unacademy.com","roc":"ROC Bangalore","incorporated":2015,"company_class":"Private","capital":"₹2,000 Cr+","career_url":"https://careers.smartrecruiters.com/Unacademy","ats":"smartrecruiters","ats_token":"Unacademy"},
        {"cin":"U74999DL2015PTC281154","name":"CARS24 SERVICES PRIVATE LIMITED","brand":"Cars24","domain":"cars24.com","roc":"ROC Delhi","incorporated":2015,"company_class":"Private","capital":"₹5,000 Cr+","career_url":"https://careers.smartrecruiters.com/Cars24","ats":"smartrecruiters","ats_token":"Cars24"},
        {"cin":"U72900MH2013PTC246588","name":"NOBROKER TECHNOLOGIES SOLUTIONS PVT LTD","brand":"NoBroker","domain":"nobroker.com","roc":"ROC Bangalore","incorporated":2013,"company_class":"Private","capital":"₹1,000 Cr+","career_url":"https://careers.smartrecruiters.com/NoBroker","ats":"smartrecruiters","ats_token":"NoBroker"},
    ]
    bulk_insert_companies(companies)
    print(f"[Seed] Loaded {len(companies)} hardcoded companies.")


if __name__ == "__main__":
    load_seed_companies()
    print("Seed complete.")
