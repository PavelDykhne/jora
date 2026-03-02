---
name: sheet-scanner
description: >
  Sync companies from a Google Sheet with sources.json, then report vacancy matches from MongoDB.
  For each company: checks sources.json by URL, adds new source if missing, queries MongoDB for matches.
  Triggers on: "обработай N компаний", "обработай строки X-Y", "продолжи сканирование",
  "продолжи там где остановился", "continue scanning", "проверь компании из таблицы",
  "обработай следующие N компаний", "найди вакансии в таблице", "обработай таблицу",
  "добавь компании в сканер".
metadata:
  openclaw:
    requires:
      bins: ["jora-gapi", "jora-vacancies"]
      env: []
---

# Sheet Scanner Skill

## Purpose

Sync companies from a Google Sheet into the Docker scanner source database, then report any vacancy matches already found by the scanner.

**Flow for each company row:**
1. Read career URL from Google Sheet
2. Check if URL exists in `sources.json`
3. If missing → add new source with default settings
4. After all companies: query MongoDB for matches from those source URLs
5. Update sheet with results; report to user

---

## STRICT RULES — NO EXCEPTIONS

1. **Do NOT scrape company career pages directly** — the Docker scanner does this
2. **Do NOT create temporary scanner scripts** (no jora_scanner.py, no urllib fetching)
3. **Do NOT invent vacancy data** — all matches come from MongoDB via `jora-vacancies`
4. **Always regenerate jobSites.json** after adding new sources so the Docker scanner picks them up
5. **jobTitleSelector is required** — use `""` (empty string) for new sources; note to user that scanner needs a selector to extract job titles

---

## Step 0: Load Keywords (Never Ask the User)

```bash
python3 -c "
import json
cfg = json.load(open('/home/oc/jora/scanner/config/default.json'))
print(json.dumps(cfg['JOB_KEYWORDS']))
"
```

---

## Step 1: Read Google Sheet

**Sheet ID** — take from:
1. User's current message (URL or bare ID)
2. Fallback from MEMORY.md: `1AD8oUSjcbSsOaXGeckPKB7XqrDPudagbpgEoNORS2T4`

```bash
/home/oc/.local/bin/jora-gapi sheets read <SHEET_ID> "Sheet1!A:Z"
```

Parse response:
- Row 1 = header (detect column indices by name)
- Look for: "Company" / "Компания" → company name column
- Look for: "URL" / "Career" / "Site" / "Сайт" → career URL column
- Look for: "Added" / "Added to sources" / "Добавлен" → mark when newly added to sources.json
- Look for: "Scanned" / "Просканировано" → mark when Docker scanner has visited
- Look for: "Vacancies" / "Вакансии" → matched job titles

If user specifies rows (e.g. "обработай строки 52-71") — use those rows only.
Otherwise: process next N unprocessed rows (default batch = 20), determined by resume logic below.

---

## Step 2: Determine Resume Position

```bash
python3 -c "
import json, glob
files = glob.glob('/home/oc/.openclaw/workspace/jobs/scan_*.json')
all_rows = []
for f in files:
    all_rows.extend(json.load(open(f)))
scanned = [r['row'] for r in all_rows if r.get('scanned')]
print('Next row:', max(scanned)+1 if scanned else 2)
"
```

Start from next unprocessed row unless user specified explicit range.

---

## Step 3: Check Each Company in sources.json

Load the full source database:

```bash
python3 -c "
import json
sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
lookup = {}
for s in sources:
    url = s.get('url', '').rstrip('/').lower()
    if url:
        lookup[url] = s['name']
print(json.dumps(lookup))
"
```

For each company from the sheet:
- Normalize career URL: `url.rstrip('/').lower()`
- Check if normalized URL is in the lookup dict
- **Found** → record as "existing source", proceed to results query
- **Not found** → add new source (Step 3a)

### Step 3a: Add New Source

Construct the source object:

```json
{
  "name": "<Company Name from sheet>",
  "url": "<career URL from sheet>",
  "type": "web",
  "jobTitleSelector": "",
  "antiBotCheck": false,
  "status": "active",
  "priority": 5,
  "addedAt": "<current ISO timestamp>",
  "stats": {
    "total_found": 0,
    "last_scan": null,
    "consecutive_failures": 0
  }
}
```

Append to sources.json:

```bash
python3 -c "
import json, sys
from datetime import datetime, timezone
sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
new = json.loads(sys.argv[1])
new['addedAt'] = datetime.now(timezone.utc).isoformat()
sources.append(new)
with open('/home/oc/jora/scanner/config/sources.json', 'w') as f:
    json.dump(sources, f, ensure_ascii=False, indent=2)
print('Added:', new['name'])
" '<NEW_SOURCE_JSON>'
```

---

## Step 4: Regenerate jobSites.json (if any new sources were added)

```bash
python3 -c "
import json
sources = json.load(open('/home/oc/jora/scanner/config/sources.json'))
EXCLUDE_FIELDS = {'stats', 'addedAt', 'greyListedAt', 'blacklistedAt', 'blacklistReason'}
web = [s for s in sources if s.get('type') == 'web' and s.get('status') == 'active']
web.sort(key=lambda s: s.get('priority', 5), reverse=True)
job_sites = [{k: v for k, v in s.items() if k not in EXCLUDE_FIELDS} for s in web]
with open('/home/oc/jora/scanner/config/jobSites.json', 'w') as f:
    json.dump(job_sites, f, ensure_ascii=False, indent=2)
print(f'jobSites.json updated: {len(job_sites)} active web sources')
"
```

---

## Step 5: Query MongoDB for Vacancy Matches

Get all recent matches (last 72h) from the Docker scanner:

```bash
jora-vacancies --hours 72
```

Then match results against processed companies by comparing the `site` field to career URLs
(normalize both sides: `rstrip('/').lower()`; match if one contains the other).

If `jora-vacancies` returns `[]` — Docker scanner has no matches yet for these sources.
Do NOT fabricate results. Report "no matches found yet" and move on.

---

## Step 6: Save Progress

```bash
python3 -c "
import json, os, sys
results = json.loads(sys.argv[1])
start_row = results[0]['row']
end_row = results[-1]['row']
outfile = f'/home/oc/.openclaw/workspace/jobs/scan_{start_row}_{end_row}.json'
existing = {}
if os.path.exists(outfile):
    for r in json.load(open(outfile)):
        existing[r['row']] = r
for r in results:
    existing[r['row']] = r
merged = sorted(existing.values(), key=lambda x: x['row'])
with open(outfile, 'w') as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print(f'Saved to {outfile}')
" '<RESULTS_JSON>'
```

Each result object:
```json
{
  "row": 52,
  "company": "Revolut",
  "url": "https://careers.revolut.com",
  "source_status": "added",
  "vacancies_found": ["Head of QA"],
  "scanned": true
}
```

`source_status` is either `"added"` (newly registered) or `"existing"` (was already in sources.json).

---

## Step 7: Update Google Sheet

Write results to corresponding columns (only if column exists in sheet):

```bash
# "Added to sources" column — write ✅ for newly added sources
/home/oc/.local/bin/jora-gapi sheets write <SHEET_ID> "Sheet1!<ADDED_COL><ROW>" '[["✅"]]'

# "Vacancies found" column — write matched titles (if any)
/home/oc/.local/bin/jora-gapi sheets write <SHEET_ID> "Sheet1!<VACANCIES_COL><ROW>" '[["Head of QA"]]'
```

---

## Step 8: Report to User

```
🔍 Sheet Scanner — строки {start}–{end}

📊 Обработано: {total} компаний

📥 Добавлено в базу источников: {new_count}
✅ Уже в базе: {existing_count}

🎯 Вакансии найдены ({match_count}):
• Revolut — "Head of QA"
  🔗 https://careers.revolut.com
  🕐 2026-03-02 08:15

📭 Совпадений не найдено: {no_match_count} компаний

ℹ️  {new_count} новых источников зарегистрировано.
   Docker сканер проверит их в следующем цикле (каждые 30 мин).

Следующая строка: {next_row}
→ "Следующие 20" — продолжить
```

If any new sources have empty `jobTitleSelector`, add:
> ⚠️  Новые источники добавлены с пустым jobTitleSelector. Без него сканер посетит сайт, но не сможет извлечь заголовки вакансий. Укажи CSS-селектор в sources.json для каждого нового сайта.

---

## Notes

- **`jobTitleSelector`**: CSS selector the Docker scanner uses to find job title elements. Without it, the scanner visits the URL but returns no results. Must be configured manually per site (e.g. `.job-title`, `h2.position-name`).
- **Batch size**: 20 rows by default unless user specifies
- **Docker scanner cycle**: every 30 min — new sources appear in results on the next cycle
- **MongoDB deduplication**: same title+site is never stored twice
