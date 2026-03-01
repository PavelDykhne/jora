# JORA — Job Offer Radar Agent

AI-powered job search assistant for **Head of QA / QA Director** roles.

Scans career pages every 30 minutes, enriches vacancies with company data, detects duplicates, finds referrals and recruiters, generates tailored resumes and cover letters — all through a Telegram bot.

## Quick Start

```bash
git clone https://github.com/YOUR_USER/jora.git
cd jora/infrastructure
bash scripts/install.sh
```

The installer handles: Docker, Node.js, OpenClaw, credentials, skills, and service startup.

## Architecture

| Component | Role | Tech |
|-----------|------|------|
| **scanner** | Web scraping every 30 min | Node.js + Puppeteer |
| **enrichment** | Company data + dedup + scoring | Node.js + MongoDB |
| **OpenClaw skills** | Keywords, sources, docs, referrals, tracking | Claude AI |
| **MongoDB** | Shared storage | Docker |
| **Telegram Bot** | User interface | OpenClaw channel |

## OpenClaw Skills

| Skill | Trigger | Description |
|-------|---------|-------------|
| **keyword-expander** | `"Ищи вакансии Head of QA"` | Generates 25+ keyword variations |
| **source-discovery** | `"find sources"` | Discovers job boards and career pages |
| **source-validator** | `/sources`, `/add_source`, `/remove_source` | Manages source lifecycle: add/remove, health check, grey/blacklist |
| **sheet-importer** | `"импортируй из таблицы"` | Batch-imports companies from Google Sheets (1000 per run, ~3 API calls) |
| **sheet-scanner** | `"обработай 20 компаний"`, `"продолжи"` | Scans companies from Google Sheets for matching vacancies; auto-reads keywords from config, auto-resumes from last position |
| **doc-generator** | `/docs {id}` | Resume, cover letter, referrals, outreach |
| **job-coordinator** | `/status`, `/report` | Pipeline overview and weekly reports |
| **google-workspace** | `"запиши в таблицу"` | Read/write Google Sheets and Docs |

## Commands (Telegram)

| Command | Action |
|---------|--------|
| `Ищи вакансии "Head of QA"` | Expand keywords + discover sources |
| `Импортируй компании из таблицы {url}` | Batch-import up to 1000 companies from Google Sheets |
| `Обработай следующие 20 компаний` | Scan next N companies from sheet for vacancies |
| `Продолжи там где остановился` | Resume sheet scanning from last saved position |
| `/sources` | List all sources grouped by status |
| `/source N` | Detailed info on source N |
| `/add_source {url\|@channel}` | Add a web source or Telegram channel |
| `/remove_source N` | Remove a source (with confirmation) |
| `/docs {id}` | Generate resume + CL + referrals |
| `/referrals {id}` | Find referrals + recruiters |
| `/outreach {id}` | Generate outreach messages |
| `/status` | Pipeline overview |
| `/report` | Weekly summary |

## Rate Limit Optimisation

OpenClaw is configured to minimise Anthropic API calls:

| Setting | Value | Reason |
|---------|-------|--------|
| Default model | `claude-haiku-4-5` | Higher throughput, lower rate pressure |
| `doc-generator` model | `claude-sonnet-4-6` | Best quality for resume/CL generation |
| `thinkingDefault` | `off` | Disables extended thinking tokens on every call (saves 1k–8k tokens/response) |
| `maxConcurrent` | 1 | Single-user bot — no need for parallelism |
| `subagents.maxConcurrent` | 2 | Prevents burst of parallel LLM calls |
| `sheet-importer` | batch Python script | 1000 companies → ~3 LLM calls (vs ~2000) |

Config: `~/.openclaw/openclaw.json`

## Source Lifecycle

Sources are managed in `scanner/config/sources.json` (single source of truth).
`jobSites.json` and `tg_sources.json` are auto-generated from it.

| Status | Meaning |
|--------|---------|
| `active` | Scanned every 30 min |
| `pending` | Discovered, awaiting approval |
| `grey` | Temporarily inactive, re-checked weekly |
| `blacklisted` | Permanently excluded |

**Automation (OpenClaw cron):**

| Job | Schedule | Action |
|-----|----------|--------|
| `source-health-check` | Daily 18:00 | Reads scanner stats → moves stale sources to grey list |
| `grey-list-recheck` | Every Sunday 10:00 | Re-checks grey sources; blacklists after 180 days |

**Grey list criteria:** no relevant vacancy in 30+ days, or 3+ consecutive scan failures.

**New source trigger:** first scan runs in deep mode (180-day lookback) to backfill vacancies.

## Docs

- [Deploy Guide](DEPLOY.md) — step-by-step VPS deployment
- [Setup Guide](docs/SETUP_GUIDE.md) — architecture and concepts
- [Infrastructure](docs/INFRASTRUCTURE.md) — IaC, CI/CD, monitoring

## Monitoring

```bash
jora-api-stats             # API calls today
jora-api-stats --yesterday # yesterday
jora-api-stats --watch     # real-time stream
```

Shows LLM calls vs tool calls per message, peak RPM, rate limit errors, and model distribution.

## Cost

~€26-41/month (VPS €5.85 + Anthropic API $20-35)
