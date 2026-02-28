# 🦞 OpenClaw Job Offer Radar Agent

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

## Commands (Telegram)

| Command | Action |
|---------|--------|
| `Ищи вакансии "Head of QA"` | Expand keywords + discover sources |
| `/add_source {url}` | Add a job source |
| `/sources` | List all sources |
| `/docs {id}` | Generate resume + CL + referrals |
| `/referrals {id}` | Find referrals + recruiters |
| `/outreach {id}` | Generate outreach messages |
| `/status` | Pipeline overview |
| `/report` | Weekly summary |

## Docs

- [Setup Guide](docs/SETUP_GUIDE.md) — full deployment walkthrough
- [Infrastructure](docs/INFRASTRUCTURE.md) — IaC, CI/CD, monitoring

## Cost

~€26-41/month (VPS €5.85 + Anthropic API $20-35)
