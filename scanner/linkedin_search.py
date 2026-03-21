#!/usr/bin/env python3
"""LinkedIn Search via Serper.dev — full profile extraction + MongoDB save

Usage:
  python3 linkedin_search.py --save     # run all 20 searches, save to MongoDB
  python3 linkedin_search.py            # dry run, print JSON only
  python3 linkedin_search.py --query "site:linkedin.com/in/ ..."
"""

import sys, json, os, re, time
import urllib.request
from datetime import datetime

SERPER_KEY = os.environ.get('SERPER_API_KEY', '548fa122c80c78a7002829142ed528a023ef51de')
MONGO_URI  = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/job_hunter_db')

SEARCHES = [
    # --- CTO / VP Engineering ---
    {'q': 'site:linkedin.com/in/ "VP Engineering" OR "VP of Engineering" fintech saas Ukraine remote',          'segment': 'cto_vp_eng',      'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "CTO" fintech OR saas "Series B" OR "Series C" remote',                       'segment': 'cto_vp_eng',      'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "Head of Engineering" OR "Chief of Engineering" startup remote Europe',        'segment': 'cto_vp_eng',      'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "VP Engineering" "we are hiring" OR "join us" technology quality',            'segment': 'cto_vp_eng',      'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "CTO" OR "Chief Technology Officer" Ukraine Poland Israel fintech',           'segment': 'cto_vp_eng',      'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "VP of Engineering" quality "100" OR "200" OR "500" employees',               'segment': 'cto_vp_eng',      'collection': 'targets'},
    # --- CEO / Founder ---
    {'q': 'site:linkedin.com/in/ "CEO" OR "Founder" saas fintech technology Ukraine remote',                   'segment': 'ceo_founder',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "Co-Founder" CTO technology "quality engineering"',                           'segment': 'ceo_founder',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "CEO" startup "Series A" OR "Series B" technology Europe',                    'segment': 'ceo_founder',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "Founder" OR "CEO" "product quality" OR "quality assurance" technology',     'segment': 'ceo_founder',     'collection': 'targets'},
    # --- QA Directors ---
    {'q': 'site:linkedin.com/in/ "Head of QA" OR "QA Director" fintech saas remote',                          'segment': 'qa_director',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "Director of Quality" OR "Director of QA" technology Ukraine OR Poland',     'segment': 'qa_director',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "Head of QA" OR "QA Director" "open to work"',                               'segment': 'qa_director',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "QA Director" OR "Head of Quality Engineering" recently',                    'segment': 'qa_director',     'collection': 'targets'},
    # --- Executive Search Recruiters ---
    {'q': 'site:linkedin.com/in/ "executive recruiter" "engineering director" Europe OR Ukraine',              'segment': 'exec_recruiter',  'collection': 'agencies'},
    {'q': 'site:linkedin.com/in/ "executive search" technology "director level" OR "C-level" remote',         'segment': 'exec_recruiter',  'collection': 'agencies'},
    {'q': 'site:linkedin.com/in/ "headhunter" technology "QA" OR "quality" director Eastern Europe',          'segment': 'exec_recruiter',  'collection': 'agencies'},
    {'q': 'site:linkedin.com/in/ "technical recruiter" "director" OR "head" engineering',                     'segment': 'exec_recruiter',  'collection': 'agencies'},
    # --- VC / Investors ---
    {'q': 'site:linkedin.com/in/ "venture capital" OR "VC" portfolio technology Ukraine OR "Eastern Europe"', 'segment': 'vc_investor',     'collection': 'targets'},
    {'q': 'site:linkedin.com/in/ "investor" "board member" technology "quality" OR "engineering"',            'segment': 'vc_investor',     'collection': 'targets'},
]


def serper_search(query, num=10):
    payload = json.dumps({'q': query, 'num': num}).encode()
    req = urllib.request.Request(
        'https://google.serper.dev/search',
        data=payload,
        headers={'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f'  [ERROR] HTTP {e.code}: {e.read().decode()[:150]}', file=sys.stderr)
        return None
    except Exception as e:
        print(f'  [ERROR] {e}', file=sys.stderr)
        return None


def parse_item(item, segment, collection):
    url     = item.get('link', '')
    title   = item.get('title', '')
    snippet = item.get('snippet', '')
    date    = item.get('date', '')

    # Parse "Name - Title at Company | LinkedIn"
    name, role, company = '', '', ''
    clean = re.sub(r'\s*[-|]\s*LinkedIn.*$', '', title).strip()
    parts = re.split(r'\s+[-]\s+', clean, maxsplit=1)
    if parts:
        name = parts[0].strip()
    if len(parts) > 1:
        rc = parts[1]
        if ' at ' in rc:
            role, company = rc.split(' at ', 1)
        elif ' @ ' in rc:
            role, company = rc.split(' @ ', 1)
        elif ' · ' in rc:
            role = rc.split(' · ')[0]
        else:
            role = rc
        company = company.strip().rstrip('.')

    # Extract location and connections from snippet
    location, connections = '', ''
    loc_m = re.search(r'Location:\s*([^\n·|]+)', snippet)
    if loc_m:
        location = loc_m.group(1).strip()
    con_m = re.search(r'([\d,]+\+?)\s+connections', snippet)
    if con_m:
        connections = con_m.group(1)

    # Fallback: company from snippet
    if not company:
        m = re.search(r'\bat ([A-Z][^·\n|.]{2,40})', snippet)
        if m:
            company = m.group(1).strip()

    # Sitelinks give extra context (About, Experience, etc.)
    sitelinks = [s.get('title', '') for s in item.get('sitelinks', []) if s.get('title')]

    return {
        'name':            name,
        'title':           role.strip(),
        'company':         company.strip(),
        'location':        location,
        'connections':     connections,
        'linkedin_url':    url,
        'snippet':         snippet,
        'sitelinks':       sitelinks,
        'segment':         segment,
        'source':          'serper',
        'query_date':      date,
        'found_at':        datetime.now().isoformat(),
        'outreach_status': 'pending',
        'email':           None,
        'email_verified':  False,
        'signal_score':    0,
        'notes':           '',
        '_collection':     collection,
    }


def save_to_mongo(results):
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        db = client['job_hunter_db']
        saved, dupes = 0, 0
        for r in results:
            col_name = r.pop('_collection', 'targets')
            col = db[col_name]
            if not col.find_one({'linkedin_url': r['linkedin_url']}):
                col.insert_one(r)
                saved += 1
            else:
                dupes += 1
                r['_collection'] = col_name
        print(f'\n[mongo] Saved: {saved} new | Skipped dupes: {dupes}', file=sys.stderr)
        return saved
    except Exception as e:
        print(f'\n[mongo] ERROR: {e}', file=sys.stderr)
        return 0


if __name__ == '__main__':
    args  = sys.argv[1:]
    save  = '--save' in args or '-s' in args

    # Custom single query mode
    if '--query' in args:
        idx = args.index('--query')
        q = args[idx + 1]
        data = serper_search(q)
        results = [parse_item(i, 'custom', 'targets') for i in data.get('organic', [])] if data else []
        for r in results:
            r.pop('_collection', None)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        sys.exit(0)

    # Full run
    all_results   = []
    total_credits = 0
    segment_stats = {}

    print(f'[start] Running {len(SEARCHES)} searches...\n', file=sys.stderr)

    for s in SEARCHES:
        seg = s['segment']
        print(f'[{seg}] {s["q"][:88]}', file=sys.stderr)
        data = serper_search(s['q'])
        if not data:
            continue

        items   = data.get('organic', [])
        credits = data.get('credits', 1)
        total_credits += credits

        parsed = [parse_item(i, seg, s['collection']) for i in items]
        all_results.extend(parsed)
        segment_stats[seg] = segment_stats.get(seg, 0) + len(parsed)
        print(f'  -> {len(parsed)} results | credits used: {credits}', file=sys.stderr)
        time.sleep(0.4)

    print(f'\n[done] Total: {len(all_results)} profiles | Credits: {total_credits}/2500', file=sys.stderr)
    for seg, cnt in segment_stats.items():
        print(f'  {seg}: {cnt}', file=sys.stderr)

    if save:
        save_to_mongo(all_results)

    out = [{k: v for k, v in r.items() if k != '_collection'} for r in all_results]
    print(json.dumps(out, ensure_ascii=False, indent=2))
