#!/usr/bin/env python3
"""
LinkedIn Search via Serper.dev (Google Search API)
Usage:
  python3 linkedin_search.py recruiters    -- executive search рекрутеры
  python3 linkedin_search.py managers      -- нанимающие менеджеры (CTO/VP Eng)
  python3 linkedin_search.py open          -- QA Directors в поиске работы
  python3 linkedin_search.py --save        -- сохранить в MongoDB
  python3 linkedin_search.py --query "site:linkedin.com/in/ ..."
"""

import sys, json, os, re, time
import urllib.request, urllib.parse
from datetime import datetime

SERPER_KEY = os.environ.get('SERPER_API_KEY', '548fa122c80c78a7002829142ed528a023ef51de')
MONGO_URI  = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/job_hunter_db')

QUERIES = {
    'recruiters': [
        'site:linkedin.com/in/ "executive recruiter" "quality assurance" OR "QA" technology',
        'site:linkedin.com/in/ "technical recruiter" "Head of QA" OR "QA Director"',
        'site:linkedin.com/in/ "talent partner" engineering director remote',
        'site:linkedin.com/in/ "executive search" "testing" OR "QA" technology director',
    ],
    'managers': [
        'site:linkedin.com/in/ "VP Engineering" fintech OR saas Ukraine OR remote',
        'site:linkedin.com/in/ "VP of Engineering" quality hire',
        'site:linkedin.com/in/ "CTO" "quality assurance" startup remote',
        'site:linkedin.com/in/ "Head of Engineering" QA director hire',
    ],
    'open': [
        'site:linkedin.com/in/ "Head of QA" OR "QA Director" "open to work"',
        'site:linkedin.com/in/ "Director of Quality" "looking for" opportunities',
    ],
}

def serper_search(query, num=10):
    url = 'https://google.serper.dev/search'
    payload = json.dumps({'q': query, 'num': num}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        'X-API-KEY': SERPER_KEY,
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f'[ERROR] HTTP {e.code}: {e.read().decode()[:200]}', file=sys.stderr)
        return None
    except Exception as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        return None

def parse_item(item, mode):
    url   = item.get('link', '')
    title = item.get('title', '')
    snip  = item.get('snippet', '')

    # "Name - Title at Company | LinkedIn"
    name, role, company = '', '', ''
    parts = re.split(r' [-–|] ', title)
    if parts:
        name = parts[0].strip()
    if len(parts) > 1:
        rc = parts[1]
        if ' at ' in rc:
            role, company = rc.split(' at ', 1)
        elif ' @ ' in rc:
            role, company = rc.split(' @ ', 1)
        else:
            role = rc
    # strip " | LinkedIn" suffix
    company = re.sub(r'\s*\|\s*LinkedIn.*$', '', company).strip()
    role    = re.sub(r'\s*\|\s*LinkedIn.*$', '', role).strip()

    col = 'agencies' if mode == 'recruiters' else 'targets'

    return {
        'name':            name,
        'title':           role,
        'company':         company,
        'linkedin':        url,
        'snippet':         snip,
        'source':          'serper_cse',
        'segment':         mode,
        'found_at':        datetime.utcnow().isoformat(),
        'outreach_status': 'pending',
        'email':           None,
        'email_verified':  False,
        'signal_score':    0,
        'notes':           '',
        '_collection':     col,
    }

def search_all(mode):
    results = []
    for q in QUERIES.get(mode, []):
        print(f'[search] {q[:90]}', file=sys.stderr)
        data = serper_search(q)
        if not data:
            continue
        items = data.get('organic', [])
        for item in items:
            results.append(parse_item(item, mode))
        credits = data.get('credits', '?')
        print(f'  → {len(items)} results | credits used: {credits}', file=sys.stderr)
        time.sleep(0.3)
    return results

def save_to_mongo(results):
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URI)
        db = client.get_default_database()
        saved = 0
        for r in results:
            col_name = r.pop('_collection', 'targets')
            col = db[col_name]
            if not col.find_one({'linkedin': r['linkedin']}):
                col.insert_one(r)
                saved += 1
            else:
                r['_collection'] = col_name  # restore
        print(f'[mongo] Saved {saved} new / {len(results)} total', file=sys.stderr)
    except Exception as e:
        print(f'[mongo] Error: {e}', file=sys.stderr)

if __name__ == '__main__':
    args = sys.argv[1:]
    save = '--save' in args
    args = [a for a in args if a != '--save']

    custom_query = None
    if '--query' in args:
        idx = args.index('--query')
        custom_query = args[idx + 1]
        mode = 'custom'
    else:
        mode = args[0] if args else 'recruiters'

    if custom_query:
        data = serper_search(custom_query)
        results = [parse_item(i, mode) for i in data.get('organic', [])] if data else []
    else:
        results = search_all(mode)

    if save:
        save_to_mongo(results)

    # Print clean summary
    for r in results:
        r.pop('_collection', None)
    print(json.dumps(results, ensure_ascii=False, indent=2))
