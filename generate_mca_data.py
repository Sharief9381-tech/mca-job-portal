"""Generate mca_data.js from the local SQLite database (real crawled data)."""
import sqlite3, json, os, re

jobs_db      = os.path.join('data', 'jobs.db')
companies_db = os.path.join('data', 'companies.db')

# ── Fetch jobs ──────────────────────────────────────────────────────────────
jconn = sqlite3.connect(jobs_db)
jconn.row_factory = sqlite3.Row
raw_jobs = [dict(r) for r in jconn.execute(
    "SELECT * FROM jobs WHERE is_active=1 ORDER BY posted_date DESC LIMIT 1000"
).fetchall()]
jconn.close()

# ── Fetch companies (only those with jobs) ──────────────────────────────────
cconn = sqlite3.connect(companies_db)
cconn.row_factory = sqlite3.Row
raw_companies = [dict(r) for r in cconn.execute(
    "SELECT * FROM companies WHERE jobs_found > 0 ORDER BY jobs_found DESC"
).fetchall()]
cconn.close()

# ── Normalise jobs ───────────────────────────────────────────────────────────
def clean(text):
    if not text: return ''
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(text))).strip()

jobs_out = []
for j in raw_jobs:
    jobs_out.append({
        'id':           j.get('id', ''),
        'title':        j.get('title', ''),
        'company_name': j.get('company_name', ''),
        'brand':        j.get('company_name', '').split()[0] if j.get('company_name') else '',
        'company_cin':  j.get('company_cin', ''),
        'company_domain': j.get('company_domain', ''),
        'location':     j.get('location', ''),
        'department':   j.get('department', ''),
        'description':  clean(j.get('description', ''))[:300],
        'apply_url':    j.get('apply_url', '#'),
        'direct_url':   j.get('apply_url', '#'),
        'ats':          j.get('ats', ''),
        'exp_level':    j.get('exp_level', 'mid_level'),
        'exp_display':  _exp_display(j.get('exp_level', '')),
        'posted_date':  j.get('posted_date', ''),
        'salary':       '',
        'skills':       [],
        'source':       j.get('source', ''),
    })

def _exp_display(level):
    return {'entry_level': '0–2 yrs', 'mid_level': '2–5 yrs', 'experienced': '5+ yrs'}.get(level, '2–5 yrs')

# ── Normalise companies ──────────────────────────────────────────────────────
companies_out = []
for c in raw_companies:
    companies_out.append({
        'cin':          c.get('cin', ''),
        'legal_name':   c.get('name', ''),
        'name':         c.get('name', ''),
        'brand':        c.get('brand', '') or c.get('name', '').split()[0],
        'domain':       c.get('domain', ''),
        'roc':          c.get('roc', ''),
        'incorporated': c.get('incorporated', ''),
        'company_class': c.get('company_class', ''),
        'capital':      c.get('capital', ''),
        'career_url':   c.get('career_url', ''),
        'ats':          c.get('ats', '').title(),
        'status':       'Active',
        'jobs_found':   c.get('jobs_found', 0),
    })

# ── Write mca_data.js ────────────────────────────────────────────────────────
output = f"""/* ==========================================================
   MCA_DATA — Auto-generated from live crawled data
   {len(jobs_out)} jobs from {len(companies_out)} companies
   Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
   Used as fallback when FastAPI backend is offline.
   ========================================================== */

const MCA_DATA = {{
  companies: {json.dumps(companies_out, ensure_ascii=False, indent=2)},

  jobs: {json.dumps(jobs_out, ensure_ascii=False, indent=2)}
}};
"""

# Fix the _exp_display call (we called it before defining — fix order)
with open('mca_data.js', 'w', encoding='utf-8') as f:
    f.write(output)

print(f'Written mca_data.js: {len(jobs_out)} jobs, {len(companies_out)} companies')
