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

## Data Sources

- `sources.json` — source stats
- MongoDB `vacancies` — vacancy data
- MongoDB `applications` — application tracking
- `~/openclaw/workspace/jobs/applications/` — generated docs
