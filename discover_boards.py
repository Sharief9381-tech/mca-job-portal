"""
Auto-discover Indian companies on Greenhouse, Lever, SmartRecruiters.
These ATS platforms have public directories of all their client companies.
We find all boards, filter for India-relevant ones, and add them to our DB.
"""

import requests, re, json, time, csv, warnings
warnings.filterwarnings('ignore')

H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

INDIA_KEYWORDS = [
    'india', 'indian', 'bengaluru', 'bangalore', 'mumbai', 'delhi', 'hyderabad',
    'pune', 'chennai', 'kolkata', 'noida', 'gurugram', 'gurgaon', 'ahmedabad',
    ' ltd', 'private limited', 'pvt', 'limited'
]


# ── Greenhouse: discover all boards ──────────────────────────────────────────

def discover_greenhouse_boards():
    """
    Greenhouse exposes a public sitemap / directory.
    We probe known Indian company slugs systematically.
    """
    print("\n[Greenhouse] Discovering boards...")

    # Known Indian company slug patterns to try
    indian_slugs = [
        # Fintech
        'razorpaysoftwareprivatelimited', 'groww', 'cred', 'bharatpe', 'cashfree',
        'juspay', 'slice', 'niyo', 'open-financial', 'freo', 'kuvera', 'smallcase',
        'upstox', 'zerodha', 'mswipe', 'lendingkart', 'indifi', 'neogrowth',
        'ftcash', 'instamojo', 'razorpay',
        # Tech/SaaS
        'inmobi', 'glance', 'freshworks', 'zoho', 'chargebee', 'clevertap',
        'moengage', 'webengage', 'exotel', 'knowlarity', 'kaleyra', 'ozonetel',
        'browserstack', 'lambdatest', 'postman', 'hasura', 'appsmith', 'tooljet',
        'setu', 'decentro', 'hyperface', 'zeta', 'perfios', 'signzy',
        'sprinklr', 'capillarytech', 'netcore', 'emailvision',
        # Logistics
        'porter', 'shadowfax', 'dunzo', 'ninjacart', 'kirana-club',
        # Health
        'pristyncare', 'healthifyme', 'mfine', 'practo', 'curefit', 'cultfit',
        'apollo247', 'tata-1mg', 'netmeds', 'pharmeasy',
        # Edtech
        'unacademy', 'vedantu', 'toppr', 'simplilearn', 'upgrad', 'scaler',
        'classplus', 'teachmint', 'physics-wallah', 'doubtnut',
        # Ecommerce/D2C
        'nykaa', 'myntra', 'purplle', 'mamaearth', 'boat', 'lenskart',
        'pepperfry', 'urbanladder', 'homelane', 'livspace',
        'licious', 'freshotome', 'country-delight', 'milkbasket',
        # B2B
        'moglix', 'zetwerk', 'ofbusiness', 'udaan', 'industrybuying',
        'storeking', 'solv', 'zetwork',
        # HR Tech
        'darwinbox', 'keka', 'greythr', 'beehyv', 'kredily',
        # Auto
        'cars24', 'cardekho', 'spinny', 'droom', 'olacabs', 'rapido',
        # Real estate
        'nobroker', 'housing', 'magicbricks', 'squareyards',
        # Media
        'sharechat', 'josh', 'moj', 'roposo', 'stage',
        # Gaming
        'mpl', 'dream11', 'gameskraft', 'winzo', 'nazara',
        # Others
        'khatabook', 'vyapar', 'okcredit', 'myoperator', 'leadsquared',
        'freshteam', 'greythr', 'zimyo',
        # MNCs with India presence
        'airbnb', 'atlassian', 'stripe', 'twilio', 'dropbox', 'hubspot',
        'zendesk', 'mongodb', 'databricks', 'elastic', 'nutanix', 'datadog',
        'hashicorp', 'okta', 'pagerduty', 'crowdstrike', 'gitlab',
        'rubrik', 'cohesity', 'druva', 'clumio', 'lacework',
        'samsara', 'toast', 'benchling', 'lattice', 'rippling',
        'gusto', 'deel', 'remote', 'oyster', 'papaya-global',
        'gong', 'outreach', 'salesloft', 'chorus', 'clari',
        'amplitude', 'mixpanel', 'heap', 'fullstory', 'contentsquare',
        'braze', 'klaviyo', 'iterable', 'sailthru', 'sendgrid-jobs',
        'figma', 'miro', 'notion', 'airtable', 'coda',
        'linear', 'shortcut', 'productboard', 'aha', 'roadmunk',
    ]

    found = []
    for slug in indian_slugs:
        try:
            r = requests.get(
                f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
                headers=H, timeout=5
            )
            if r.status_code == 200:
                jobs = r.json().get('jobs', [])
                if jobs:
                    # Check if any jobs mention India
                    india_jobs = [j for j in jobs if 'india' in str(j).lower() or
                                  any(city in str(j).lower() for city in ['bengaluru', 'mumbai', 'delhi', 'hyderabad', 'pune', 'chennai'])]
                    found.append({
                        'slug': slug,
                        'total_jobs': len(jobs),
                        'india_jobs': len(india_jobs),
                        'has_india': len(india_jobs) > 0 or len(jobs) > 0
                    })
                    print(f"  GH FOUND: {slug} → {len(jobs)} jobs ({len(india_jobs)} India)")
            time.sleep(0.1)
        except Exception:
            pass

    print(f"[Greenhouse] Found {len(found)} active boards")
    return found


# ── Lever: discover all boards ────────────────────────────────────────────────

def discover_lever_boards():
    """Probe known Indian company Lever slugs."""
    print("\n[Lever] Discovering boards...")

    slugs = [
        'paytm', 'cred', 'meesho', 'porter', 'epifi', 'fi', 'nium',
        'oyo', 'oyorooms', 'zomato', 'swiggy', 'ola', 'rapido',
        'cars24', 'cardekho', 'spinny', 'ninjacart', 'udaan',
        'pristyncare', 'healthifyme', 'practo', 'curefit',
        'unacademy', 'vedantu', 'upgrad', 'scaler',
        'bharatpe', 'cashfree', 'juspay', 'razorpay',
        'moglix', 'zetwerk', 'ofbusiness',
        'sharechat', 'mpl', 'dream11',
        'lenskart', 'nykaa', 'mamaearth',
        'delhivery', 'shiprocket', 'shadowfax',
        'khatabook', 'zoho', 'browserstack',
        'nobroker', 'housing', 'magicbricks',
        'freshworks', 'chargebee', 'clevertap',
        'inmobi', 'glance', 'moengage',
        # MNCs
        'airbnb', 'stripe', 'twilio', 'atlassian', 'dropbox',
        'hubspot', 'zendesk', 'mongodb', 'elastic', 'okta',
        'gitlab', 'figma', 'notion', 'airtable', 'miro',
        'gong', 'braze', 'amplitude', 'lattice', 'rippling',
        'gusto', 'deel', 'remote-com', 'oyster-hr',
    ]

    found = []
    for slug in slugs:
        try:
            r = requests.get(
                f'https://api.lever.co/v0/postings/{slug}?mode=json',
                headers=H, timeout=5
            )
            if r.status_code == 200:
                jobs = r.json() if isinstance(r.json(), list) else []
                if jobs:
                    found.append({'slug': slug, 'total_jobs': len(jobs)})
                    print(f"  LV FOUND: {slug} → {len(jobs)} jobs")
            time.sleep(0.1)
        except Exception:
            pass

    print(f"[Lever] Found {len(found)} active boards")
    return found


# ── SmartRecruiters: discover boards ─────────────────────────────────────────

def discover_smartrecruiters_boards():
    """Probe SmartRecruiters company identifiers."""
    print("\n[SmartRecruiters] Discovering boards...")

    tokens = [
        'Freshworks', 'Unacademy', 'Swiggy', 'Cars24', 'NoBroker',
        'Meesho', 'CRED', 'Paytm', 'PhonePe', 'Zomato',
        'Flipkart', 'Myntra', 'Nykaa', 'Lenskart', 'Mamaearth',
        'BigBasket', 'Zepto', 'Blinkit', 'Dunzo', 'Porter',
        'Delhivery', 'Shiprocket', 'Shadowfax', 'XpressBees',
        'Practo', 'HealthifyMe', 'CureFit', 'PristynCare',
        'Udaan', 'Moglix', 'OfBusiness', 'Zetwerk',
        'Razorpay', 'Groww', 'Zerodha', 'Upstox',
        'BharatPe', 'Cashfree', 'Juspay',
        'BrowserStack', 'LambdaTest', 'Postman',
        'MoEngage', 'CleverTap', 'WebEngage',
        'Darwinbox', 'Keka', 'GreytHR',
        'Classplus', 'Vedantu', 'Scaler', 'UpGrad',
        'ShareChat', 'MPL', 'Dream11',
        # MNCs
        'Airbnb', 'Stripe', 'Atlassian', 'HubSpot',
        'MongoDB', 'Elastic', 'Databricks', 'Okta',
        'GitLab', 'Figma', 'Notion', 'Miro',
        'Gong', 'Braze', 'Amplitude', 'Lattice',
        'Deel', 'Remote', 'Rippling',
        'IndiGo', 'AkasaAir', 'OYO',
        'Apollo247', 'Narayana', 'MaxHealthcare',
        'Cognizant', 'Capgemini', 'Accenture',
        'IBM', 'Oracle', 'SAP', 'Cisco',
    ]

    found = []
    for token in tokens:
        try:
            r = requests.get(
                f'https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=10',
                headers=H, timeout=5
            )
            if r.status_code == 200:
                count = r.json().get('totalFound', 0)
                if count > 0:
                    found.append({'token': token, 'total_jobs': count})
                    print(f"  SR FOUND: {token} → {count} jobs")
            time.sleep(0.15)
        except Exception:
            pass

    print(f"[SmartRecruiters] Found {len(found)} active boards")
    return found


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    gh_boards = discover_greenhouse_boards()
    lv_boards = discover_lever_boards()
    sr_boards = discover_smartrecruiters_boards()

    # Save results
    with open('discovered_boards.json', 'w') as f:
        json.dump({
            'greenhouse': gh_boards,
            'lever': lv_boards,
            'smartrecruiters': sr_boards,
        }, f, indent=2)

    total = len(gh_boards) + len(lv_boards) + len(sr_boards)
    print(f"\n{'='*50}")
    print(f"Total new boards discovered: {total}")
    print(f"  Greenhouse: {len(gh_boards)}")
    print(f"  Lever: {len(lv_boards)}")
    print(f"  SmartRecruiters: {len(sr_boards)}")
    print(f"Results saved to discovered_boards.json")
    print(f"{'='*50}")
