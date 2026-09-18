import sys; sys.path.insert(0,'.')
from crawler.parsers.workday import fetch_jobs

companies = [
    ('accenture/AccentureCareers@wd103',          {'name':'Accenture','domain':'accenture.com','cin':''}),
    ('barclays/External_Career_Site_Barclays@wd3', {'name':'Barclays','domain':'barclays.com','cin':''}),
    ('crowdstrike/CrowdStrikeCareers@wd5',         {'name':'CrowdStrike','domain':'crowdstrike.com','cin':''}),
    ('workday/Workday@wd5',                        {'name':'Workday','domain':'workday.com','cin':''}),
]

for token, info in companies:
    jobs = fetch_jobs(token, info)
    print(f"{info['name']}: {len(jobs)} jobs")
    if jobs:
        print(f"  Sample: {jobs[0]['title']} | {jobs[0]['location']} | {jobs[0]['apply_url'][:70]}")
