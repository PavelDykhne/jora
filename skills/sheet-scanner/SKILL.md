---
name: sheet-scanner
description: >
  Scan companies from a Google Sheet for relevant job vacancies.
  Reads keywords automatically from scanner config — never asks the user for them.
  Tracks progress in local JSON files and resumes from where it left off.
  Triggers on: "обработай N компаний", "обработай строки X-Y", "продолжи сканирование",
  "продолжи там где остановился", "continue scanning", "проверь компании из таблицы",
  "обработай следующие N компаний", "найди вакансии в таблице".
---

# Sheet Scanner Skill

## Purpose

Scan companies from a Google Sheet for job vacancies matching the user's target keywords.
Saves progress after every batch so work survives restarts.

---

## CRITICAL: Always Read These Automatically (Never Ask the User)

### Keywords — always load from:
```bash
python3 -c "
import json
cfg = json.load(open('/home/oc/jora/scanner/config/default.json'))
print(json.dumps(cfg['JOB_KEYWORDS']))
"
```

### Scan progress — always check before starting:
```bash
ls /home/oc/.openclaw/workspace/jobs/scan_*.json 2>/dev/null
```

Read all scan files, merge into one dict keyed by row number to know which rows are done.

### Google Sheet ID — take from:
1. User's current message (if they provided a URL)
2. Or the most recently used sheet ID found in scan files:
```bash
python3 -c "
import json, glob, os
files = sorted(glob.glob(os.path.expanduser('/home/oc/.openclaw/workspace/jobs/scan_*.json')))
if files:
    d = json.load(open(files[-1]))
    # sheet_id is stored in scan file metadata if present
    print(d[0].get('sheet_id', '') if d else '')
"
```

---

## Step 1: Determine Starting Row

1. Load all scan files and find the **highest row marked `scanned: true`**
2. Next row to process = highest_scanned_row + 1
3. If user specified "начни с строки N" or "обработай строки X–Y" — use that

```bash
python3 -c "
import json, glob, os
files = glob.glob(os.path.expanduser('/home/oc/.openclaw/workspace/jobs/scan_*.json'))
all_rows = []
for f in files:
    all_rows.extend(json.load(open(f)))
scanned = [r['row'] for r in all_rows if r.get('scanned')]
print('Last scanned row:', max(scanned) if scanned else 0)
print('Total scanned:', len(scanned))
"
```

---

## Step 2: Read Companies from Sheet

```bash
DATA=$(/home/oc/.local/bin/jora-gapi sheets read <SHEET_ID> "Sheet1!A:Z")
```

Parse to get: row number, company name, URL.
Detect columns automatically (look for "company"/"компания" and "url"/"site"/"сайт" headers).

Select the next N rows starting from the determined start row.

---

## Step 3: Batch-Scan Career Pages (1 bash call)

Write and execute a Python script that processes all N companies at once:

```python
#!/usr/bin/env python3
"""
Batch career page scanner.
Fetches each company URL and checks for keyword matches.
"""
import json, sys, time, re, urllib.request, urllib.error

def fetch(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobBot/1.0)'
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(65536).decode('utf-8', errors='ignore'), r.url
    except urllib.error.HTTPError as e:
        return e.code, '', url
    except Exception:
        return 0, '', url

def find_career_url(base_url):
    """Try base URL and common career page paths."""
    CAREER_PATHS = [
        '', '/careers', '/jobs', '/en/jobs', '/en/careers',
        '/about/jobs', '/work-with-us', '/join-us', '/vacancy',
        '/vacancies', '/hiring', '/team/jobs', '/company/careers',
    ]
    if not base_url.startswith('http'):
        base_url = 'https://' + base_url
    base = base_url.rstrip('/')
    for path in CAREER_PATHS:
        status, html, final_url = fetch(base + path)
        if status == 200:
            return final_url, html
    return base_url, ''

def check_keywords(html, keywords):
    """Return list of keywords found in page HTML."""
    html_lower = html.lower()
    found = []
    for kw in keywords:
        if kw.lower() in html_lower:
            found.append(kw)
    return found

def extract_job_titles(html, keywords):
    """Extract job listing titles that match keywords."""
    found_jobs = []
    # Look for job title patterns in HTML
    patterns = [
        r'<(?:a|h[1-4]|span|div|li)[^>]*>([^<]{5,120})</(?:a|h[1-4]|span|div|li)>',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for title in matches:
            title = title.strip()
            if any(kw.lower() in title.lower() for kw in keywords):
                if title not in found_jobs and len(title) < 120:
                    found_jobs.append(title)
    return found_jobs[:10]  # max 10 per company


data = json.loads(sys.argv[1])
companies = data['companies']
keywords = data['keywords']
results = []

for company in companies:
    name = company.get('company', '')
    url = company.get('url', '').strip()
    row = company.get('row', 0)

    if not url:
        results.append({'row': row, 'company': name, 'url': url,
                        'found_jobs': [], 'scanned': True,
                        'error': 'no_url'})
        continue

    career_url, html = find_career_url(url)
    matched_keywords = check_keywords(html, keywords) if html else []
    found_jobs = extract_job_titles(html, keywords) if html else []

    results.append({
        'row': row,
        'company': name,
        'url': career_url,
        'original_url': url,
        'found_jobs': found_jobs,
        'matched_keywords': matched_keywords,
        'scanned': True,
        'http_status': 200 if html else 0,
    })

    time.sleep(0.2)

print(json.dumps(results, ensure_ascii=False, indent=2))
```

Run with:
```bash
python3 /tmp/jora_sheet_scan.py '{
  "companies": [{"row": 52, "company": "Acme", "url": "https://acme.com"}, ...],
  "keywords": ["Head of QA", "QA Director", ...]
}'
```

---

## Step 4: Save Progress

After the script runs, save results to a progress file:

```bash
# File naming: scan_ROW_START_ROW_END.json
OUTFILE=/home/oc/.openclaw/workspace/jobs/scan_${START_ROW}_${END_ROW}.json
# Merge with existing file for same range if it exists, otherwise create new
python3 -c "
import json, os, sys
results = json.loads(sys.argv[1])
outfile = os.path.expanduser('$OUTFILE')
# Load existing if file exists, merge by row number
existing = {}
if os.path.exists(outfile):
    for r in json.load(open(outfile)):
        existing[r['row']] = r
for r in results:
    existing[r['row']] = r
merged = sorted(existing.values(), key=lambda x: x['row'])
open(outfile, 'w').write(json.dumps(merged, ensure_ascii=False, indent=2))
print(f'Saved {len(results)} results to $OUTFILE')
" '<RESULTS_JSON>'
```

---

## Step 5: Update Google Sheet

Mark each processed company in the sheet. Use column mapping:
- If there's a "Scanned" / "Статус" column → write ✅ or "Scanned"
- If there's a "Vacancies" / "Вакансии" column → write found job titles (comma-separated)
- If no status column → append ✅ to the company name cell

```bash
# Write status to the Scanned column (detect column from header row)
/home/oc/.local/bin/jora-gapi sheets write <SHEET_ID> "Sheet1!<STATUS_COL><ROW>" '[["✅"]]'

# If vacancies found, also write them
/home/oc/.local/bin/jora-gapi sheets write <SHEET_ID> "Sheet1!<JOBS_COL><ROW>" '[["Head of QA — open"]]'
```

---

## Step 6: Report to User

After processing all N companies:

```
🔍 Сканирование компаний — строки {start}–{end}

✅ Обработано: {total} компаний

🎯 Найдены совпадения ({match_count}):
1. Revolut (строка 52)
   → "Head of QA" — careers.revolut.com/jobs/12345
2. Wise (строка 58)
   → "QA Director" — wise.jobs/opening/qa-director

📭 Вакансий не найдено: {empty_count} компаний
❌ Недоступны: {error_count} (сайт не ответил)

Следующая необработанная строка: {next_row}
→ "Следующие 20" — продолжить с строки {next_row}
→ "Детали 1" — подробнее по Revolut
→ "/docs [id]" — подготовить документы
```

---

## State after completion

- Progress file updated: `/home/oc/.openclaw/workspace/jobs/scan_{start}_{end}.json`
- Google Sheet updated with ✅ markers
- Ready to resume from `next_row` on the next request

---

## Resume Logic (if OpenClaw restarted mid-scan)

On any trigger phrase ("продолжи", "continue", "следующие N"):
1. Read ALL scan files → find max scanned row
2. Read sheet starting from max_row + 1
3. Proceed with Step 3 — no need to re-scan already-scanned rows

Never ask the user "where did you stop?" — compute it from the scan files.
