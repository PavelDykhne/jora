#!/usr/bin/env python3
"""
Email Finder — finds emails for contacts in MongoDB targets/agencies collections.

Methods (in priority order):
  1. Hunter.io API  — name + domain (25 free/month)
  2. Pattern guess  — firstname.lastname@domain, f.lastname@domain, flastname@domain
  3. Serper search  — "John Smith" "stripe.com" email contact

Usage:
  python3 email_finder.py --collection targets   # process targets
  python3 email_finder.py --collection agencies  # process agencies
  python3 email_finder.py --all                  # both collections
  python3 email_finder.py --limit 25             # max records to process (default: 25)
  python3 email_finder.py --dry-run              # print without saving
"""

import sys, json, os, re, time
import urllib.request, urllib.parse
from datetime import datetime

HUNTER_KEY  = os.environ.get('HUNTER_API_KEY', '')   # set your key here
SERPER_KEY  = os.environ.get('SERPER_API_KEY', '548fa122c80c78a7002829142ed528a023ef51de')
MONGO_URI   = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/job_hunter_db')

# Common company domain guesses by company name patterns
KNOWN_DOMAINS = {
    'google': 'google.com', 'meta': 'meta.com', 'facebook': 'meta.com',
    'apple': 'apple.com', 'microsoft': 'microsoft.com', 'amazon': 'amazon.com',
    'stripe': 'stripe.com', 'revolut': 'revolut.com', 'wise': 'wise.com',
    'airbnb': 'airbnb.com', 'uber': 'uber.com', 'netflix': 'netflix.com',
    'spotify': 'spotify.com', 'gitlab': 'gitlab.com', 'github': 'github.com',
    'atlassian': 'atlassian.com', 'datadog': 'datadoghq.com',
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def split_name(full_name):
    """Split 'John Smith' → ('John', 'Smith')"""
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return full_name, ''


def guess_domain(company_name):
    """Try to derive domain from company name."""
    if not company_name:
        return ''
    # Check known domains
    lower = company_name.lower().strip()
    for key, domain in KNOWN_DOMAINS.items():
        if key in lower:
            return domain
    # Simple guess: remove common suffixes, lowercase, add .com
    clean = re.sub(r'\b(inc|llc|ltd|gmbh|corp|co|s\.a|pvt|oy|ab)\b', '', lower, flags=re.I)
    clean = re.sub(r'[^a-z0-9]', '', clean).strip()
    return f'{clean}.com' if clean else ''


def generate_patterns(first, last, domain):
    """Generate common email patterns."""
    if not first or not last or not domain:
        return []
    f, l = first.lower(), last.lower()
    return [
        f'{f}.{l}@{domain}',
        f'{f}{l}@{domain}',
        f'{f[0]}.{l}@{domain}',
        f'{f[0]}{l}@{domain}',
        f'{f}@{domain}',
        f'{l}@{domain}',
        f'{f}_{l}@{domain}',
    ]


# ── Hunter.io ─────────────────────────────────────────────────────────────────

def hunter_find(first, last, domain):
    """Find email via Hunter.io Email Finder API."""
    if not HUNTER_KEY or not domain:
        return None
    params = urllib.parse.urlencode({
        'first_name': first,
        'last_name':  last,
        'domain':     domain,
        'api_key':    HUNTER_KEY,
    })
    url = f'https://api.hunter.io/v2/email-finder?{params}'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        d = data.get('data', {})
        email = d.get('email')
        score = d.get('score', 0)
        if email and score >= 50:
            return {'email': email, 'score': score, 'method': 'hunter'}
    except Exception as e:
        print(f'  [hunter] error: {e}', file=sys.stderr)
    return None


def hunter_domain_search(domain, limit=5):
    """Get known emails at a domain via Hunter Domain Search."""
    if not HUNTER_KEY or not domain:
        return []
    params = urllib.parse.urlencode({'domain': domain, 'limit': limit, 'api_key': HUNTER_KEY})
    url = f'https://api.hunter.io/v2/domain-search?{params}'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        emails = data.get('data', {}).get('emails', [])
        pattern = data.get('data', {}).get('pattern', '')
        return {'emails': emails, 'pattern': pattern}
    except Exception as e:
        print(f'  [hunter-domain] error: {e}', file=sys.stderr)
    return {'emails': [], 'pattern': ''}


# ── Serper email search ───────────────────────────────────────────────────────

def serper_email_search(name, company):
    """Try to find email via Google search."""
    q = f'"{name}" "{company}" email contact'
    payload = json.dumps({'q': q, 'num': 5}).encode()
    req = urllib.request.Request(
        'https://google.serper.dev/search',
        data=payload,
        headers={'X-API-KEY': SERPER_KEY, 'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        for item in data.get('organic', []):
            snippet = item.get('snippet', '') + item.get('title', '')
            # Extract email pattern from snippet
            m = re.search(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}', snippet)
            if m:
                return {'email': m.group(0), 'score': 30, 'method': 'serper_search'}
    except Exception as e:
        print(f'  [serper-email] error: {e}', file=sys.stderr)
    return None


# ── Main finder ──────────────────────────────────────────────────────────────

def find_email(contact):
    name    = contact.get('name', '')
    company = contact.get('company', '') or ''
    snippet = contact.get('snippet', '') or ''

    first, last = split_name(name)
    if not first:
        return None

    # Try to get domain
    domain = guess_domain(company)

    # Also check snippet for domain hints
    if not domain:
        m = re.search(r'[\w.-]+\.(com|io|co|org|net|ai|app)', snippet)
        if m:
            domain = m.group(0)

    result = {'first': first, 'last': last, 'domain': domain, 'company': company}

    # 1. Hunter.io
    if HUNTER_KEY and domain:
        found = hunter_find(first, last, domain)
        if found:
            result.update(found)
            return result

    # 2. Serper email search (costs 1 credit)
    if name and company:
        found = serper_email_search(name, company)
        if found:
            result.update(found)
            return result

    # 3. Pattern guesses (no verification — mark as unverified)
    if domain:
        patterns = generate_patterns(first, last, domain)
        result['email']          = patterns[0] if patterns else None
        result['email_patterns'] = patterns
        result['score']          = 10
        result['method']         = 'pattern_guess'
        result['email_verified'] = False
        return result

    return None


# ── MongoDB ───────────────────────────────────────────────────────────────────

def get_mongo_db():
    from pymongo import MongoClient
    client = MongoClient(MONGO_URI)
    return client['job_hunter_db']


def process_collection(col_name, limit, dry_run):
    db  = get_mongo_db()
    col = db[col_name]
    # Only process contacts without email yet
    contacts = list(col.find({'email': None, 'name': {'$ne': ''}}).limit(limit))
    print(f'\n[{col_name}] Processing {len(contacts)} contacts...', file=sys.stderr)

    found_count = 0
    for c in contacts:
        name = c.get('name', '—')
        print(f'  {name} @ {c.get("company","?")}', file=sys.stderr)
        result = find_email(c)
        if result and result.get('email'):
            print(f'    -> {result["email"]} [{result.get("method","?")} score:{result.get("score",0)}]', file=sys.stderr)
            found_count += 1
            if not dry_run:
                col.update_one({'_id': c['_id']}, {'$set': {
                    'email':          result['email'],
                    'email_verified': result.get('email_verified', False),
                    'email_score':    result.get('score', 0),
                    'email_method':   result.get('method', ''),
                    'email_patterns': result.get('email_patterns', []),
                    'email_domain':   result.get('domain', ''),
                    'email_found_at': datetime.now().isoformat(),
                }})
        else:
            print(f'    -> not found', file=sys.stderr)
        time.sleep(0.3)

    print(f'\n[{col_name}] Found emails: {found_count}/{len(contacts)}', file=sys.stderr)
    return found_count


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    args    = sys.argv[1:]
    dry_run = '--dry-run' in args
    do_all  = '--all' in args

    limit = 25
    if '--limit' in args:
        limit = int(args[args.index('--limit') + 1])

    collection = 'targets'
    if '--collection' in args:
        collection = args[args.index('--collection') + 1]

    if not HUNTER_KEY:
        print('[warn] HUNTER_API_KEY not set — using Serper + pattern guess only', file=sys.stderr)

    if dry_run:
        print('[mode] DRY RUN — no MongoDB writes', file=sys.stderr)

    if do_all:
        t = process_collection('targets',  limit, dry_run)
        a = process_collection('agencies', limit, dry_run)
        print(f'\n[total] Emails found: {t + a}')
    else:
        found = process_collection(collection, limit, dry_run)
        print(f'\n[total] Emails found: {found}')
