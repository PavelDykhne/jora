---
name: sheet-importer
description: "Batch-imports company career pages from a Google Sheet into the job scanner. Designed for minimum API calls — processes all companies in one pass using a bash script, then analyzes results in a single LLM turn. Use when the user provides a Google Sheet with a list of companies or URLs to scan for vacancies. Triggers on: 'добавь компании из таблицы', 'импортируй из sheets', 'проверь компании из таблицы', 'добавь источники из google sheets', 'batch import', 'загрузи список компаний'."
---

# Sheet Importer Skill

## Purpose

Batch-import company career pages from a Google Sheet into the job scanner (`jobSites.json`).

**Key constraint**: process ALL companies with minimal LLM API calls.
- Do NOT spawn subagents per company
- Do NOT make separate tool calls per URL
- Use ONE bash/python script to process everything, then analyze results in one pass

## Batch Processing Architecture

```
Save job to queue → Sheet read (1 bash call) → Batch fetch script (1 bash call) → Save results → Analyze (1 LLM turn per 100) → Write config → User approval → Mark done
```

Total LLM API calls: 3–5 regardless of company count (up to 1000).

**State is persisted to disk at every step** so the job survives OpenClaw restarts.

---

## Queue File (persistent state)

All import jobs are stored at:
```
~/.openclaw/workspace/jobs/import_queue.json
```

Schema:
```json
[
  {
    "id": "import_20260301_143000",
    "created_at": "2026-03-01T14:30:00Z",
    "updated_at": "2026-03-01T14:35:00Z",
    "status": "pending_approval",
    "sheet_id": "1BxiMVs0XRA5...",
    "sheet_url": "https://docs.google.com/spreadsheets/d/...",
    "sheet_range": "Sheet1!A:Z",
    "total_companies": 42,
    "processed": 42,
    "results_file": "~/.openclaw/workspace/jobs/imports/import_20260301_143000/results.json"
  }
]
```

Statuses: `queued` → `fetching` → `pending_approval` → `done` / `cancelled`

### Queue helpers (run these as needed)

```bash
QUEUE=~/.openclaw/workspace/jobs/import_queue.json

# Read queue
cat "$QUEUE" 2>/dev/null || echo "[]"

# Update job status
python3 -c "
import json, sys
q = json.loads(open('$QUEUE').read())
for j in q:
    if j['id'] == sys.argv[1]:
        j['status'] = sys.argv[2]
        import datetime; j['updated_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
open('$QUEUE','w').write(json.dumps(q, ensure_ascii=False, indent=2))
" JOB_ID NEW_STATUS
```

---

## Step 0: Create Job Entry (BEFORE any processing)

**Do this first, before reading the sheet.** This ensures state is saved even if something fails.

```bash
QUEUE=~/.openclaw/workspace/jobs/import_queue.json
JOB_ID="import_$(date +%Y%m%d_%H%M%S)"
IMPORTS_DIR=~/.openclaw/workspace/jobs/imports/$JOB_ID
mkdir -p "$IMPORTS_DIR"
mkdir -p ~/.openclaw/workspace/jobs

# Create or update queue file
python3 -c "
import json, os, datetime
path = os.path.expanduser('$QUEUE')
q = json.loads(open(path).read()) if os.path.exists(path) else []
q.append({
    'id': '$JOB_ID',
    'created_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'updated_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'status': 'queued',
    'sheet_url': '$SHEET_URL',
    'sheet_id': '$SHEET_ID',
    'sheet_range': 'Sheet1!A:Z',
    'total_companies': 0,
    'processed': 0,
    'results_file': '$IMPORTS_DIR/results.json'
})
open(path,'w').write(json.dumps(q, ensure_ascii=False, indent=2))
"
```

---

## Step 1: Read the Sheet

```bash
DATA=$(/home/oc/.local/bin/jora-gapi sheets read <SHEET_ID> "Sheet1!A:Z")
```

Parse the JSON array to determine:
- Which column has company names (look for "Company", "Компания", or first text column)
- Which column has URLs (look for "URL", "Site", "Website", "Сайт", or column with http:// values)
- Skip header row if present

If user didn't specify columns, auto-detect from first row.

---

## Step 2: Batch-Fetch All Career Pages (1 bash call)

Write and run a Python script that processes ALL companies at once.
Cap at 1000 companies per run. If more — process first 1000 and warn user.

```python
#!/usr/bin/env python3
"""Batch career page finder. Processes all companies in one run."""

import json, sys, time, re
import urllib.request, urllib.error
from html.parser import HTMLParser

CAREER_PATHS = [
    '/careers', '/jobs', '/en/jobs', '/en/careers',
    '/about/jobs', '/work-with-us', '/join-us',
    '/vacancy', '/vacancies', '/hiring', '/team/jobs',
    '/careers/open-positions', '/company/careers',
]

SELECTOR_PATTERNS = [
    ('[data-automation-id="jobTitle"]', 'Workday'),
    ('.opening a', 'Greenhouse'),
    ('.posting-title h5', 'Lever'),
    ('.jss-job-title', 'BambooHR'),
    ('[class*="job-title"]', 'generic'),
    ('[class*="position-title"]', 'generic'),
    ('h2 a[href*="job"]', 'generic'),
    ('h3 a[href*="job"]', 'generic'),
    ('[class*="vacancy"] a', 'generic'),
    ('[class*="career"] h2', 'generic'),
    ('[class*="career"] h3', 'generic'),
]

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


def fetch(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobBot/1.0)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(32768).decode('utf-8', errors='ignore'), r.url
    except urllib.error.HTTPError as e:
        return e.code, '', url
    except Exception:
        return 0, '', url


def find_career_url(base_url):
    """Try base URL and common career paths, return first working one."""
    # First try base URL itself (might already be a careers page)
    status, html, final_url = fetch(base_url)
    if status == 200 and any(kw in html.lower() for kw in ['job', 'career', 'vacancy', 'position', 'вакансия']):
        return final_url, status, html

    # Try common career paths
    origin = base_url.rstrip('/')
    if '://' not in origin:
        origin = 'https://' + origin

    for path in CAREER_PATHS:
        url = origin + path
        status, html, final_url = fetch(url)
        if status == 200:
            return final_url, status, html

    return base_url, 0, ''


def detect_ats(url, html):
    """Detect ATS platform from URL or page content."""
    url_lower = url.lower()
    for domain, (selector, platform) in ATS_DOMAINS.items():
        if domain in url_lower:
            return selector, platform

    html_lower = html.lower()
    for kw, platform in [('greenhouse', 'Greenhouse'), ('lever.co', 'Lever'),
                          ('workday', 'Workday'), ('bamboohr', 'BambooHR'),
                          ('smartrecruiters', 'SmartRecruiters')]:
        if kw in html_lower:
            for domain, (selector, _) in ATS_DOMAINS.items():
                if kw in domain:
                    return selector, platform

    return None, None


def guess_selector(html):
    """Heuristic: find the most likely CSS selector for job titles."""
    # Look for known ATS-style patterns in HTML
    patterns = [
        (r'class="[^"]*job[_-]title[^"]*"', '[class*="job-title"]'),
        (r'class="[^"]*position[_-]title[^"]*"', '[class*="position-title"]'),
        (r'class="[^"]*vacancy[^"]*"', '[class*="vacancy"]'),
        (r'data-automation-id="jobTitle"', '[data-automation-id="jobTitle"]'),
        (r'class="[^"]*opening[^"]*"', '.opening a'),
        (r'class="[^"]*posting[^"]*"', '.posting-title'),
    ]
    for pattern, selector in patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return selector
    return 'MANUAL_REVIEW_NEEDED'


def extract_sample_titles(html, selector_hint):
    """Extract a few job title examples from HTML (rough heuristic)."""
    titles = []
    # Look for text inside likely job listing elements
    pattern = r'<(?:a|h[23]|span|div)[^>]*(?:job|career|position|vacancy)[^>]*>([^<]{5,80})</(?:a|h[23]|span|div)>'
    matches = re.findall(pattern, html, re.IGNORECASE)
    for m in matches[:5]:
        t = m.strip()
        if t and not t.startswith('<'):
            titles.append(t)
    return titles[:3]


# ── Main ──────────────────────────────────────────────────────────────────────

companies = json.loads(sys.argv[1])[:1000]
results = []
total = len(companies)

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

    selector = 'MANUAL_REVIEW_NEEDED'
    ats_platform = None
    sample_titles = []

    if accessible and html:
        ats_selector, ats_platform = detect_ats(career_url, html)
        if ats_selector:
            selector = ats_selector
        else:
            selector = guess_selector(html)
        sample_titles = extract_sample_titles(html, selector)

    needs_anti_bot = accessible and html and any(kw in html.lower() for kw in [
        'cloudflare', 'captcha', 'cf-browser-verification', 'just a moment'
    ])

    results.append({
        'name': name,
        'original_url': company.get('url', ''),
        'career_url': career_url,
        'http_status': status,
        'accessible': accessible,
        'ats_platform': ats_platform,
        'selector': selector,
        'anti_bot': needs_anti_bot,
        'sample_titles': sample_titles,
    })

    time.sleep(0.15)  # be polite, ~6-7 req/sec

print(json.dumps(results, ensure_ascii=False, indent=2))
```

Save as `/tmp/jora_batch_fetch.py` and run:
```bash
python3 /tmp/jora_batch_fetch.py '<JSON_ARRAY_OF_COMPANIES>'
```

Where JSON array format: `[{"name": "Revolut", "url": "https://revolut.com"}, ...]`

**Immediately after the script finishes — save results and update queue status:**

```bash
# Save results to disk
python3 /tmp/jora_batch_fetch.py '<JSON>' > "$IMPORTS_DIR/results.json"

# Update queue: fetching → pending_approval
python3 -c "
import json, os, datetime
path = os.path.expanduser('~/.openclaw/workspace/jobs/import_queue.json')
q = json.loads(open(path).read())
for j in q:
    if j['id'] == '$JOB_ID':
        j['status'] = 'pending_approval'
        j['processed'] = len(json.loads(open('$IMPORTS_DIR/results.json').read()))
        j['updated_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
open(path,'w').write(json.dumps(q, ensure_ascii=False, indent=2))
print('Queue updated')
"
```

From this point on, **results are safe on disk**. If OpenClaw restarts, the job-coordinator will
detect status `pending_approval` and restore the context automatically.

---

## Step 3: Analyze Results (1 LLM turn per ≤100 companies)

Process the JSON output from the script. For each company, decide:

1. **accessible: true + selector found** → add to sources, mark `ready`
2. **accessible: true + selector = MANUAL_REVIEW_NEEDED** → add with flag, set `antiBotCheck: false`
3. **accessible: true + anti_bot: true** → add with `antiBotCheck: true` (will use Puppeteer)
4. **accessible: false (status 0 or 4xx/5xx)** → mark as `unreachable`, skip

For batches >100, process in chunks of 100 per LLM turn without asking user between chunks.

### Generate sources.json entries

For each accessible company, create an entry:
```json
{
  "name": "<company name>",
  "url": "<career_url>",
  "jobTitleSelector": "<selector or MANUAL_REVIEW_NEEDED>",
  "antiBotCheck": <true if anti_bot else false>
}
```

---

## Step 4: Write to Scanner Config

Append new sources to existing `jobSites.json`:
```bash
# Read existing
EXISTING=$(cat /home/oc/jora/scanner/config/jobSites.json)

# Merge and write new JSON (merge existing + new entries, deduplicate by url)
python3 -c "
import json, sys
existing = json.loads(open('/home/oc/jora/scanner/config/jobSites.json').read())
new_entries = json.loads(sys.argv[1])
seen = {e['url'] for e in existing}
merged = existing + [e for e in new_entries if e['url'] not in seen]
print(json.dumps(merged, ensure_ascii=False, indent=2))
" '<NEW_ENTRIES_JSON>' > /home/oc/jora/scanner/config/jobSites.json
```

Also update `~/openclaw/workspace/jobs/sources.json` with full metadata.

---

## Step 5: Present Batch Results to User

```
📥 Импорт из Google Sheets — {date}
Обработано: {total} компаний за {N} секунд

✅ Готово к сканированию ({ready_count}):
1. Revolut → revolut.com/careers (.opening a / Greenhouse)
2. Wise → wise.com/careers ([class*="job-title"])
...

⚠️ Требует ручной проверки селектора ({manual_count}):
8. AcmeCorp → acmecorp.com/jobs (MANUAL_REVIEW_NEEDED)
...

🤖 Нужен браузер / антибот ({antibot_count}):
12. BigCorpCareers → bigcorp.com/careers (antiBotCheck: true)
...

❌ Недоступны ({unreachable_count}):
15. OldStartup → oldstartup.io (HTTP 404)
...

→ "Approve all ready" — добавить {ready_count} источников
→ "Approve all" — добавить все включая manual review
→ "Skip unreachable" — пропустить недоступные
→ "Restart scanner" — перезапустить сканер после добавления
```

---

## After Approval

1. Confirm which sources to add (user choice)
2. Write final `jobSites.json`
3. Restart scanner:
```bash
cd /home/oc/jora/infrastructure && docker compose restart job-scanner
```
4. Mark job as done in queue:
```bash
python3 -c "
import json, os, datetime
path = os.path.expanduser('~/.openclaw/workspace/jobs/import_queue.json')
q = json.loads(open(path).read())
for j in q:
    if j['id'] == '$JOB_ID':
        j['status'] = 'done'
        j['updated_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
open(path,'w').write(json.dumps(q, ensure_ascii=False, indent=2))
"
```
5. Confirm: "✅ Добавлено {N} источников. Следующее сканирование через ~30 мин."

---

## Input Formats Supported

The skill accepts Google Sheet in any of these formats:
- Sheet URL: `https://docs.google.com/spreadsheets/d/SHEET_ID/edit`
- Short ID: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`
- With sheet name hint: "таблица ID, компании в колонке A, сайты в колонке B"

Auto-detects column layout. If ambiguous, asks user once to clarify before processing.

## Limits

- Max 1000 companies per batch run
- If sheet has >1000 rows: process first 1000, warn user, offer to continue
- Timeout per company: 8 seconds (skip if no response)
- Total script runtime: ~3 min for 1000 companies (0.15s × 1000 + network)
