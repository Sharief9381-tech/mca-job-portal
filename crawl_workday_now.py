"""Crawl the 4 confirmed Workday companies and regenerate mca_data.js"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from crawler.database import init_databases, upsert_jobs, mark_company_crawled, get_stats
from crawler.parsers.workday import fetch_jobs

init_databases()

companies = [
    ('accenture/AccentureCareers@wd103',
     {'name':'Accenture','brand':'Accenture','domain':'accenture.com','cin':'U72900MH2007PTC168455'}),
    ('barclays/External_Career_Site_Barclays@wd3',
     {'name':'Barclays','brand':'Barclays','domain':'barclays.com','cin':'U74140MH2007PTC174000'}),
    ('crowdstrike/CrowdStrikeCareers@wd5',
     {'name':'CrowdStrike','brand':'CrowdStrike','domain':'crowdstrike.com','cin':'U72900KA2020PTC131000'}),
    ('workday/Workday@wd5',
     {'name':'Workday','brand':'Workday','domain':'workday.com','cin':'U72900KA2012PTC062400'}),
]

total = 0
for token, info in companies:
    brand = info['brand']
    print(f'Crawling {brand}...')
    jobs = fetch_jobs(token, info)
    upsert_jobs(jobs)
    mark_company_crawled(info['domain'], len(jobs), None)
    total += len(jobs)
    print(f'  {brand}: {len(jobs)} jobs saved')

print(f'\nTotal new jobs: {total}')

# Print DB stats
stats = get_stats()
print(f"DB total: {stats['total_jobs']} jobs from {stats['crawled_companies']} companies")

# Regenerate mca_data.js
import sqlite3, json, re, os

def clean(t):
    if not t: return ''
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(t))).strip()[:300]

def exp_label(level):
    return {'entry_level':'0-2 yrs','mid_level':'2-5 yrs','experienced':'5+ yrs'}.get(level or '','2-5 yrs')

jobs_db = 'data/jobs.db'
companies_db = 'data/companies.db'

jconn = sqlite3.connect(jobs_db)
jconn.row_factory = sqlite3.Row
raw_jobs = [dict(r) for r in jconn.execute('SELECT * FROM jobs WHERE is_active=1 ORDER BY first_seen DESC, posted_date DESC LIMIT 1000').fetchall()]
jconn.close()

cconn = sqlite3.connect(companies_db)
cconn.row_factory = sqlite3.Row
raw_cos = [dict(r) for r in cconn.execute('SELECT * FROM companies WHERE jobs_found > 0 ORDER BY jobs_found DESC').fetchall()]
cconn.close()

jobs_out = [{
    'id': j.get('id',''), 'title': j.get('title',''),
    'company_name': j.get('company_name',''), 'brand': j.get('company_name',''),
    'company_cin': j.get('company_cin',''), 'company_domain': j.get('company_domain',''),
    'location': j.get('location',''), 'department': j.get('department',''),
    'description': clean(j.get('description','')),
    'apply_url': j.get('apply_url','#'), 'direct_url': j.get('apply_url','#'),
    'ats': j.get('ats',''), 'exp_level': j.get('exp_level','mid_level'),
    'exp_display': exp_label(j.get('exp_level','')),
    'posted_date': j.get('posted_date',''), 'first_seen': j.get('first_seen',''),
    'salary': '', 'skills': [],
} for j in raw_jobs]

cos_out = [{
    'cin': c.get('cin',''), 'legal_name': c.get('name',''), 'name': c.get('name',''),
    'brand': c.get('brand','') or c.get('name',''),
    'domain': c.get('domain',''), 'roc': c.get('roc',''),
    'incorporated': c.get('incorporated',''), 'company_class': c.get('company_class',''),
    'capital': c.get('capital',''), 'career_url': c.get('career_url',''),
    'ats': (c.get('ats','') or '').title(), 'status': 'Active',
    'jobs_found': c.get('jobs_found', 0),
} for c in raw_cos]

out = 'const MCA_DATA = {\n  companies: ' + json.dumps(cos_out, ensure_ascii=False, indent=2) + ',\n\n  jobs: ' + json.dumps(jobs_out, ensure_ascii=False, indent=2) + '\n};\n'
with open('mca_data.js', 'w', encoding='utf-8') as f:
    f.write(out)

print(f'mca_data.js updated: {len(jobs_out)} jobs, {len(cos_out)} companies')
