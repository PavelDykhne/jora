---
name: vacancy-scanner
description: >
  Read vacancies found by the Docker job scanner from MongoDB and report matches.
  The Docker scanner does the actual web scraping every 30 min; this skill reads results.
  Triggers on: "scan vacancies", "check jobs", "find vacancies", "покажи вакансии",
  "проверь вакансии", "что нашёл сканер", "дневной отчёт по вакансиям".
metadata:
  openclaw:
    requires:
      bins: ["jora-vacancies"]
      env: []
---

# Vacancy Scanner Skill

## Architecture

**Do NOT scrape websites directly** — they block web-fetch. The Docker scanner handles scraping.

**Do NOT create your own scanner scripts** — do not write jora_scanner.py or any substitute.

**Do NOT invent or hardcode fake vacancy data** — only report real data from `jora-vacancies`.

**If `jora-vacancies` returns empty** — report: "Docker scanner has not found new matches yet. It runs every 30 minutes automatically." Do nothing else.

```
Docker scanner (Puppeteer, every 30 min)
  → MongoDB jobnotifications.viewedJobTitles { title, site, date }
    → jora-vacancies (CLI) → OpenClaw reads & reports
```

## Reading Vacancies

### Get vacancies from last 24 hours (default)
```bash
jora-vacancies
```

### Get vacancies from last N hours
```bash
jora-vacancies --hours 48
```

### Get all vacancies ever found
```bash
jora-vacancies --all
```

Output is a JSON array:
```json
[
  { "title": "head of qa", "site": "https://...", "date": "2026-03-02T08:00:00+00:00" },
  ...
]
```

If Docker stack is not running, returns: `{"error": "...", "hint": "Docker stack may not be running"}`

## Daily Report Flow

1. Run `jora-vacancies` to get last 24h results
2. If error → report that Docker scanner is likely not running
3. Group results by site
4. Format report (see template below)
5. Send to user

## Report Template

```
📋 Vacancy Scan — {date}
Docker scanner results for last 24h

✅ {N} new matches found:

{for each vacancy}
• {TITLE} — {site_name}
  🔗 {site_url}
  🕐 {time}

{if 0 found}
— No new matches in the last 24 hours.

────────────────────────
Total ever found: {jora-vacancies --all | count}
Scanner sources: {count from /home/oc/jora/scanner/config/sources.json, status=active}
```

## Source Health Check

After reading vacancies, optionally check scanner status:
```bash
cat /home/oc/jora/scanner/config/sources.json
```
Look at `stats.last_scan` and `stats.consecutive_failures` for each source.

## Notes

- Vacancy titles are stored lowercase (scanner normalises them)
- Site field is the source URL (job board), not the individual vacancy URL
- For individual vacancy links, user must visit the site directly
- Deduplication is done by the scanner: same title+site is never reported twice
