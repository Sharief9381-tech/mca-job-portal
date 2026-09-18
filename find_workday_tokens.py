"""Find correct Workday tenant/site for major companies."""
import requests, re, warnings, json, time
warnings.filterwarnings('ignore')

H_HTML = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
H_JSON = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Content-Type': 'application/json'}

# Companies to probe: (brand, career_url)
COMPANIES = [
    ('Accenture',   'https://www.accenture.com/in-en/careers/jobsearch'),
    ('Cognizant',   'https://careers.cognizant.com/global/en'),
    ('Capgemini',   'https://www.capgemini.com/in-en/careers/'),
    ('HCL Tech',    'https://www.hcltech.com/careers'),
    ('Wipro',       'https://careers.wipro.com'),
    ('Infosys',     'https://career.infosys.com/joblist'),
    ('TCS',         'https://www.tcs.com/careers'),
    ('Tech Mahindra','https://careers.techmahindra.com'),
    ('Mphasis',     'https://careers.mphasis.com'),
    ('Dell',        'https://jobs.dell.com/search-jobs/India'),
    ('HP',          'https://jobs.hp.com/en-us/search?location=India'),
    ('Adobe',       'https://www.adobe.com/careers.html'),
    ('Qualcomm',    'https://www.qualcomm.com/company/careers'),
    ('Nvidia',      'https://www.nvidia.com/en-in/about-nvidia/careers/'),
    ('Salesforce',  'https://www.salesforce.com/in/company/careers/'),
    ('PayPal',      'https://www.paypal.com/us/webapps/mpp/jobs'),
    ('Goldman Sachs','https://www.goldmansachs.com/careers/'),
    ('JP Morgan',   'https://careers.jpmorgan.com/us/en/home'),
    ('Morgan Stanley','https://www.morganstanley.com/people-opportunities/students-graduates'),
    ('Deutsche Bank','https://careers.db.com/india/'),
    ('Barclays',    'https://search.jobs.barclays/india'),
    ('Wells Fargo', 'https://www.wellsfargojobs.com/en/jobs/?location=India'),
    ('Fidelity',    'https://jobs.fidelity.com/search-jobs/india'),
    ('IDFC First',  'https://www.idfcfirstbank.com/careers'),
    ('IndiGo',      'https://careers.goindigo.in'),
    ('Air India',   'https://www.airindia.com/in/en/footer/careers.html'),
    ('Taj Hotels',  'https://careers.ihcltata.com'),
    ('Blue Dart',   'https://www.bluedart.com/web/guest/careersoverview'),
    ('Godrej Properties','https://www.godrejproperties.com/careers'),
    ('Lodha Group', 'https://www.lodhagroup.com/careers'),
    ('Hindalco',    'https://www.hindalco.com/careers'),
    ('Vedanta',     'https://www.vedantalimited.com/eng/careers.aspx'),
    ('HUL',         'https://careers.unilever.com/india'),
    ('Nestle',      'https://www.nestle.in/jobs'),
    ('P&G',         'https://www.pg.com/en_IN/careers/'),
    ('Colgate',     'https://www.colgate.com/en-in/careers'),
    ('Mondelez',    'https://careers.mondelezinternational.com/india'),
    ('PepsiCo',     'https://www.pepsicojobs.com/main/india'),
    ('J&J',         'https://jobs.jnj.com/jobs?location=India'),
    ('Pfizer',      'https://www.pfizer.co.in/content/about-pfizer/careers'),
    ('AstraZeneca', 'https://careers.astrazeneca.com/india'),
    ('GSK',         'https://www.gsk.com/en-gb/careers/'),
    ('Biocon',      'https://www.biocon.com/careers/'),
    ('Maruti Suzuki','https://www.marutisuzuki.com/corporate/careers'),
    ('Bajaj Auto',  'https://www.bajajauto.com/careers'),
    ('Sony India',  'https://www.sony.co.in/en/careers'),
    ('Star India',  'https://www.hotstar.com/in/about/careers'),
    ('DHL',         'https://careers.dhl.com/site/global/home/index.page'),
    ('FedEx',       'https://careers.fedex.com/fedex'),
    ('Aditya Birla Fashion', 'https://www.abfrl.com/careers/'),
    ('Snowflake',   'https://careers.snowflake.com'),
    ('CrowdStrike', 'https://careers.crowdstrike.com/india'),
    ('ServiceNow',  'https://careers.servicenow.com'),
    ('Workday',     'https://www.workday.com/en-us/company/careers/open-positions.html'),
]

WD_PAT = re.compile(r'([a-zA-Z0-9_-]+)\.(?:wd\d+|myworkdayjobs)\.com/([a-zA-Z0-9_/-]+)', re.I)

results = {}
for brand, url in COMPANIES:
    try:
        r = requests.get(url, headers=H_HTML, timeout=10, verify=False, allow_redirects=True)
        m = WD_PAT.search(r.text + r.url)
        if m:
            tenant_raw = m.group(1)
            site_raw   = m.group(2).split('?')[0].rstrip('/').split('/')[0]
            # tenant is the subdomain before .wdXX.myworkdayjobs.com
            # but sometimes it's encoded differently - try both
            wd_num = re.search(r'\.(wd\d+)\.myworkdayjobs', r.text + r.url, re.I)
            wd     = wd_num.group(1) if wd_num else 'wd3'

            # Try the CXS API
            for tenant in [tenant_raw, brand.lower().replace(' ',''), brand.lower().replace(' ','-')]:
                for site in [site_raw, brand.replace(' ','')+'Careers', brand.replace(' ','')+'-Careers']:
                    api_url = f'https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs'
                    try:
                        resp = requests.post(api_url, json={'appliedFacets':{},'limit':1,'offset':0,'searchText':''}, headers=H_JSON, timeout=6)
                        if resp.status_code == 200:
                            total = resp.json().get('total', 0)
                            if total > 0:
                                token = f'{tenant}/{site}'
                                results[brand] = {'token': token, 'total': total, 'wd': wd}
                                print(f'FOUND: {brand} -> {token} ({total} jobs)')
                                break
                    except: pass
                if brand in results: break
        else:
            print(f'NO WD:  {brand} ({r.url[:60]})')
    except Exception as e:
        print(f'ERR:    {brand}: {str(e)[:60]}')
    time.sleep(0.3)

print(f'\n=== Found {len(results)} Workday companies ===')
with open('workday_tokens.json', 'w') as f:
    json.dump(results, f, indent=2)
for brand, info in results.items():
    print(f"  {brand}: {info['token']} ({info['total']} jobs)")
