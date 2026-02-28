---
name: job-coordinator
description: "Orchestrates the job search pipeline: tracks application statuses, sends follow-up reminders, generates weekly and monthly reports. Use when the user asks about application status, needs a report, wants to track a follow-up, or on a scheduled basis for weekly digests. Triggers on: 'status', 'report', 'follow up', 'weekly', 'how is my search going', 'track', or scheduled weekly/monthly."
---

# Job Coordinator Skill

## Purpose

Central orchestrator that:
- Tracks all vacancy and application statuses
- Sends follow-up reminders
- Generates periodic reports
- Provides a single view of the job search pipeline

## Application States

```
found → notified → shortlisted → docs_ready → applied → 
  → interview → offer / rejected
```

## Commands

| Command | Action |
|---------|--------|
| `/status` | Show pipeline overview |
| `/status {id}` | Show specific application |
| `/followup {id}` | Mark for follow-up |
| `/applied {id}` | Mark as applied |
| `/interview {id} {date}` | Schedule interview |
| `/rejected {id}` | Mark as rejected |
| `/report` | Generate weekly report |

## Weekly Report (Sunday 19:00)

```
📊 Weekly Report — {date_range}

📡 Источники: {active} активных | {grey} в сером списке
🔍 Просканировано: {total} вакансий | Новых: {new}
⭐ Shortlisted: {shortlisted} | ⚠️ Дубликатов: {dupes}
📨 Откликов: {applied} | 🎤 Собеседований: {interviews}

⏰ Follow-up нужен:
   • {company} — {days} дней без ответа
   
🎯 Ближайшие собеседования:
   • {company} — {date}

📈 Тренд: {trend}% вакансий vs прошлая неделя
```

## Follow-up Logic

| Days after apply | Action |
|------------------|--------|
| 7 | Reminder: "Consider follow-up" |
| 14 | Reminder: "No response — send follow-up?" |
| 30 | Mark as "likely rejected" |

## Pending Import Check (on every /status and on first message after restart)

Check for unfinished sheet imports and notify the user if any are pending:

```bash
python3 -c "
import json, os
path = os.path.expanduser('~/.openclaw/workspace/jobs/import_queue.json')
if not os.path.exists(path):
    exit(0)
q = json.loads(open(path).read())
pending = [j for j in q if j['status'] == 'pending_approval']
if pending:
    print(json.dumps(pending, ensure_ascii=False))
"
```

If any jobs have `status = pending_approval`:

1. Read results from `results_file` path stored in the job entry
2. Notify the user:

```
⏸️ Незавершённый импорт

Найден импорт из Google Sheets от {created_at}:
  📋 Таблица: {sheet_url}
  🏢 Компаний обработано: {processed}
  ⏳ Ждёт одобрения

→ "Продолжить" — показать результаты для одобрения
→ "Отменить" — удалить задачу
```

3. If user says "Продолжить" — re-run Step 3 (Analyze) from the saved `results.json` file.
   Do NOT re-fetch URLs — results are already saved.
4. If user says "Отменить":
```bash
python3 -c "
import json, os, datetime
path = os.path.expanduser('~/.openclaw/workspace/jobs/import_queue.json')
q = json.loads(open(path).read())
for j in q:
    if j['id'] == 'JOB_ID':
        j['status'] = 'cancelled'
        j['updated_at'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
open(path,'w').write(json.dumps(q, ensure_ascii=False, indent=2))
"
```

## Data Sources

- `sources.json` — source stats
- MongoDB `vacancies` — vacancy data
- MongoDB `applications` — application tracking
- `~/openclaw/workspace/jobs/applications/` — generated docs
- `~/.openclaw/workspace/jobs/import_queue.json` — pending sheet imports
