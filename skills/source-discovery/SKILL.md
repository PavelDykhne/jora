---
name: source-discovery
description: "Discovers and recommends new job vacancy sources — career websites, job boards, aggregators, and Telegram channels. Use when setting up a new job search, when the user asks to find more sources, or on a scheduled basis to expand the source list. Enriches each source with metadata (Enrichment Layer 1). Outputs validated sources for user approval before adding to the scanner config. Triggers on: 'find sources', 'add job boards', 'where to search', 'discover channels', or during initial job search setup."
---

# Source Discovery Skill

## Purpose

Finds, validates, and enriches new sources of job vacancies. Sources can be:
- **Web**: Career pages, job boards, aggregators (LinkedIn Jobs, Indeed, Glassdoor, etc.)
- **Telegram**: Public channels with job postings
- **[Future]**: Facebook groups, LinkedIn feeds, closed TG groups

## When to Use

- Initial setup of job search — build seed source list
- User requests: "find more sources", "add boards for QA roles"
- Scheduled weekly expansion run
- After keyword-expander produces new keywords

## Inputs Required

- `~/openclaw/workspace/jobs/keywords.json` — target keywords
- `~/openclaw/workspace/jobs/sources.json` — existing sources (if any)
- `~/openclaw/workspace/jobs/blacklist.json` — blacklisted sources

## Source Types and Discovery Methods

### Web Sources

#### Tier 1: Direct Career Pages (highest quality)
Search for career pages of target companies. Use the company longlist from:
`~/openclaw/workspace/jobs/company_targets.json` or ask user.

Pattern: `{company_name} careers page QA`

For each found page, record:
```json
{
  "id": "web_revolut_careers",
  "type": "web",
  "name": "Revolut Careers",
  "url": "https://revolut.com/careers/?query=quality",
  "jobTitleSelector": ".job-title-class",
  "antiBotCheck": false,
  "enrichment": {
    "source_type": "vendor",
    "company": "Revolut",
    "estimated_relevance": 5,
    "last_checked": null
  }
}
```

#### Tier 2: Aggregators and Job Boards
Known high-value aggregators for QA leadership roles:

| Source | URL Pattern | Notes |
|--------|------------|-------|
| LinkedIn Jobs | linkedin.com/jobs/search/?keywords=... | High volume, may need auth |
| Indeed | indeed.com/jobs?q=... | Good for global search |
| Glassdoor | glassdoor.com/Job/...-jobs-... | Salary data included |
| RemoteOK | remoteok.com/remote-qa-jobs | Remote-focused |
| WeWorkRemotely | weworkremotely.com/... | Remote-focused |
| BuiltIn | builtin.com/jobs | Tech-focused |
| AngelList/Wellfound | wellfound.com/jobs | Startups |
| InGameJob | ingamejob.com | Gaming-specific |
| Habr Career | career.habr.com | RU-speaking market |
| Djinni | djinni.co | UA market, remote |

For each, construct search URLs with keywords from keywords.json and validate.

#### Tier 3: Niche Boards
Search for: `"{keyword}" site:greenhouse.io OR site:lever.co OR site:workday.com`

### Telegram Sources

#### Discovery Methods

1. **Direct search**: Search Telegram for channels with names containing QA, Quality, Testing, Job, Vacancy, Career
2. **Known channels** (seed list for QA/Tech leadership):

| Channel | Type | Language |
|---------|------|----------|
| @qa_jobs | QA jobs | EN/RU |
| @remote_qa | Remote QA | EN |
| @devjobs | Dev & QA jobs | EN |
| @qa_vacancies | QA вакансии | RU |
| @job_qa | QA jobs | RU |
| @djinnijobs | Djinni jobs | UA/EN |
| @workintech | Tech jobs | EN |

3. **Web search for TG channels**: `"Head of QA" OR "QA Director" telegram channel jobs`

For each TG channel, record:
```json
{
  "id": "tg_qa_jobs",
  "type": "telegram_public",
  "name": "QA Jobs",
  "url": "https://t.me/qa_jobs",
  "telegram_channel_id": "@qa_jobs",
  "enrichment": {
    "source_type": "aggregator",
    "subscribers": null,
    "avg_posts_per_week": null,
    "relevant_posts_sample": 0,
    "language": "en",
    "last_checked": null
  }
}
```

## Enrichment Layer 1: Source Metadata

For each discovered source, collect:

| Field | Web | Telegram | How |
|-------|-----|----------|-----|
| `source_type` | vendor / aggregator | aggregator | Classify based on URL pattern |
| `estimated_relevance` | 1-5 | 1-5 | Based on keyword match in recent posts |
| `company` | Company name (if vendor) | null | From URL/page |
| `subscribers` | N/A | Number | TG API or estimate |
| `avg_posts_per_week` | N/A | Frequency | Sample recent posts |
| `last_post_date` | N/A | Date | Most recent post |
| `language` | Detect | Detect | Content analysis |
| `needs_auth` | bool | bool (closed group) | Check access |
| `anti_bot` | bool | N/A | Test with simple fetch |

## Validation Rules

Before recommending a source:

1. **Not blacklisted**: Check against `blacklist.json`
2. **Not duplicate**: Check URL/channel against existing `sources.json`
3. **Accessible**: Can be fetched (web) or is public (TG)
4. **Relevant**: At least some content matches target keywords
5. **Active**: Has recent posts/listings (< 30 days for aggregators)

## Output Format

### To User (TG notification)

```
📡 Source Discovery — {date}

✅ Рекомендую добавить ({count}):
1. 🌐 [Web] Revolut Careers (5/5)
   Vendor career page, QA positions found
2. 📱 [TG] @qa_jobs (4/5)
   12k подписчиков, 6 релевантных постов за месяц
3. 🌐 [Web] RemoteOK - QA (3/5)
   Агрегатор, 15 remote QA позиций

❌ Отклонены автоматически ({count}):
4. 📱 [TG] @qa_trainee — 0 senior ролей
5. 🌐 [Web] example.com/jobs — сайт не отвечает

→ "Approve all" / "Approve 1,2" / "Blacklist 4"
```

### To File System

After user approval, update:

1. **`~/openclaw/workspace/jobs/sources.json`** — full source list with metadata
2. **`scanner-config/jobSites.json`** — web sources in job-scanner-tg format:
```json
[
  {
    "name": "Revolut Careers",
    "url": "https://revolut.com/careers/?query=quality",
    "jobTitleSelector": ".job-title",
    "antiBotCheck": false
  }
]
```
3. **`scanner-config/tg_sources.json`** — Telegram sources (for future TG userbot integration; in POC these are monitored manually or via enrichment-svc)

## CSS Selector Discovery

For web sources, the skill needs to determine the correct CSS selector for job titles.

### Strategy
1. Fetch the page
2. Look for common job listing patterns:
   - `h2 a`, `h3 a` within list containers
   - Elements with classes containing: `job`, `title`, `position`, `role`, `vacancy`
   - `[data-job-title]`, `[data-position]` attributes
3. Validate: selector returns multiple elements with text that looks like job titles
4. If unclear, mark as `"jobTitleSelector": "MANUAL_REVIEW_NEEDED"`

### Common Selectors by Platform

| Platform | Typical Selector |
|----------|-----------------|
| Greenhouse | `.opening a` |
| Lever | `.posting-title h5` |
| Workday | `[data-automation-id="jobTitle"]` |
| BambooHR | `.jss-job-title` |
| Custom | Needs manual discovery |

## Scheduling

| Event | Action |
|-------|--------|
| Initial setup | Full discovery run |
| Weekly (Sunday) | Search for new sources, validate existing |
| User command | On-demand discovery |
| After keyword update | Re-run with new keywords |

## Notes

- In POC: web sources + public TG channels only
- CSS selectors may need manual validation for custom career pages
- The skill does NOT scan for vacancies — that's job-scanner-tg's job
- Source approval is always required before adding to scanner config
