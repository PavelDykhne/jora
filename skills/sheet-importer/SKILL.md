---
name: sheet-importer
description: "Batch-imports company career pages from a Google Sheet into the job scanner. Designed for minimum API calls — processes all companies in one pass using a bash script, then analyzes results in a single LLM turn. Use when the user provides a Google Sheet with a list of companies or URLs to scan for vacancies. Triggers on: 'добавь компании из таблицы', 'импортируй из sheets', 'проверь компании из таблицы', 'добавь источники из google sheets', 'batch import', 'загрузи список компаний'."
---

# Sheet Importer Skill

## Architecture

```
Sheet read (1 bash) → Batch fetch script (1 bash) → Analyze (1 LLM turn per 100) → Write config → Approve
```

3–5 API calls total regardless of company count (up to 1000).
**State is persisted to disk** — job survives OpenClaw restarts.

## Queue File

```
/home/oc/.openclaw/workspace/jobs/import_queue.json
```

Statuses: `queued` → `fetching` → `pending_approval` → `done` / `cancelled`

Schema: `{id, created_at, updated_at, status, sheet_id, sheet_url, total_companies, processed, results_file}`

---

## Step 0: Create Job Entry

```bash
JOB_ID="import_$(date +%Y%m%d_%H%M%S)"
IMPORTS_DIR=/home/oc/.openclaw/workspace/jobs/imports/$JOB_ID
mkdir -p "$IMPORTS_DIR" /home/oc/.openclaw/workspace/jobs
# Append job to import_queue.json with status=queued
```

## Step 1: Read Sheet

```bash
DATA=$(/home/oc/.local/bin/jora-gapi sheets read <SHEET_ID> "Sheet1!A:Z")
```

Auto-detect column layout (company name + URL). Ask user once if ambiguous.

## Step 2: Batch Fetch (1 bash call)

```bash
python3 /home/oc/jora/scanner/batch_fetch.py '<JSON_ARRAY>' > "$IMPORTS_DIR/results.json"
```

JSON array format: `[{"name": "Revolut", "url": "https://revolut.com"}, ...]`

Script output per company: `{name, career_url, http_status, accessible, ats_platform, selector, anti_bot}`

After script finishes — update queue status to `pending_approval`.

## Step 3: Analyze Results

For each company:
- `accessible=true` + selector found → `ready`
- `accessible=true` + `selector=MANUAL_REVIEW_NEEDED` → add with flag
- `accessible=true` + `anti_bot=true` → `antiBotCheck: true`
- `accessible=false` → `unreachable`, skip

For >100 companies: process in chunks of 100 per LLM turn.

## Step 4: Present to User

```
📥 Импорт — {date} | {total} компаний

✅ Готово ({N}): Revolut (.opening a / Greenhouse), Wise ([class*="job-title"])
⚠️ Ручная проверка ({N}): AcmeCorp (MANUAL_REVIEW_NEEDED)
🤖 Антибот ({N}): BigCorp (antiBotCheck: true)
❌ Недоступны ({N}): OldStartup (HTTP 404)

→ "Approve all ready" | "Approve all" | "Skip unreachable"
```

## Step 5: Write Config & Confirm

Merge into sources.json and jobSites.json (deduplicate by URL):
```bash
python3 /home/oc/jora/scanner/regenerate.py
```

Mark job as `done` in queue. Confirm: `✅ Добавлено {N} источников.`

## Input Formats

- Sheet URL: `https://docs.google.com/spreadsheets/d/SHEET_ID/edit`
- Short ID: `1BxiMVs0XRA5...`
- With column hint: "таблица ID, компании в A, сайты в B"

Limits: max 1000 companies, 8s timeout per URL, ~3 min total.
