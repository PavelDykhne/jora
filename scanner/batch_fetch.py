#!/usr/bin/env python3
Batch career page finder. Usage: python3 batch_fetch.py <JSON_ARRAY>

import json, sys, time, re
import urllib.request, urllib.error

CAREER_PATHS = ['/careers', '/jobs', '/en/jobs', '/en/careers', '/about/jobs',
    '/work-with-us', '/join-us', '/vacancy', '/vacancies', '/hiring',
    '/careers/open-positions', '/company/careers']

ATS_DOMAINS = {
    'greenhouse.io': ('.opening a', 'Greenhouse'),
    'lever.co': ('.posting-title h5', 'Lever'),
    'workday.com': ('[data-automation-id="jobTitle"]', 'Workday'),
    'bamboohr.com': ('.jss-job-title', 'BambooHR'),
    'smartrecruiters.com': ('[data-qa="job-item-title"]', 'SmartRecruiters'),
    'ashbyhq.com': ('h3', 'Ashby'),
    'jobs.lever.co': ('.posting-title h5', 'Lever'),
    'boards.greenhouse.io': ('.opening a', 'Greenhouse'),
}

SELECTOR_PATTERNS = [
    (r'class="[^"]*job[_-]title[^"]*"', '[class*="job-title"]'),
    (r'class="[^"]*position[_-]title[^"]*"', '[class*="position-title"]'),
    (r'class="[^"]*vacancy[^"]*"', '[class*="vacancy"]'),
    (r'data-automation-id="jobTitle"', '[data-automation-id="jobTitle"]'),
    (r'class="[^"]*opening[^"]*"', '.opening a'),
    (r'class="[^"]*posting[^"]*"', '.posting-title'),
]

def fetch(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(32768).decode('utf-8', errors='ignore'), r.url
    except urllib.error.HTTPError as e:
        return e.code, '', url
    except Exception:
        return 0, '', url

def find_career_url(base_url):
    status, html, final_url = fetch(base_url)
    if status == 200 and any(kw in html.lower() for kw in ['job', 'career', 'vacancy']):
        return final_url, status, html
    origin = base_url.rstrip('/')
    if '://' not in origin:
        origin = 'https://' + origin
    for path in CAREER_PATHS:
        status, html, final_url = fetch(origin + path)
        if status == 200:
            return final_url, status, html
    return base_url, 0, ''

def detect_ats(url, html):
    for domain, (selector, platform) in ATS_DOMAINS.items():
        if domain in url.lower():
            return selector, platform
    for kw, platform in [('greenhouse', 'Greenhouse'), ('lever.co', 'Lever'),
                          ('workday', 'Workday'), ('bamboohr', 'BambooHR')]:
        if kw in html.lower():
            for domain, (selector, _) in ATS_DOMAINS.items():
                if kw in domain:
                    return selector, platform
    return None, None

def guess_selector(html):
    for pattern, selector in SELECTOR_PATTERNS:
        if re.search(pattern, html, re.IGNORECASE):
            return selector
    return 'MANUAL_REVIEW_NEEDED'

companies = json.loads(sys.argv[1])[:1000]
results = []

for i, company in enumerate(companies):
    name = company.get('name', f'Company_{i+1}')
    base_url = company.get('url', '').strip()
    if not base_url:
        results.append({'name': name, 'url': '', 'accessible': False, 'error': 'no_url'})
        continue
    if not base_url.startswith('http'):
        base_url = 'https://' + base_url
    career_url, status, html = find_career_url(base_url)
    accessible = status == 200
    selector, ats = 'MANUAL_REVIEW_NEEDED', None
    if accessible and html:
        selector, ats = detect_ats(career_url, html)
        if not selector:
            selector = guess_selector(html)
    anti_bot = accessible and html and any(kw in html.lower() for kw in
        ['cloudflare', 'captcha', 'cf-browser-verification', 'just a moment'])
    results.append({'name': name, 'original_url': company.get('url', ''),
        'career_url': career_url, 'http_status': status, 'accessible': accessible,
        'ats_platform': ats, 'selector': selector, 'anti_bot': anti_bot})
    time.sleep(0.15)

print(json.dumps(results, ensure_ascii=False, indent=2))
