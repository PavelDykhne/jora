---
name: keyword-expander
description: "Generates comprehensive keyword variations for job search from a seed role title. Use when the user provides a target job title (e.g., 'Head of QA') and needs a full list of synonyms, alternative titles, and related role names for job scanning. Outputs a validated keyword list in JSON format for job-scanner-tg-notification config. Triggers on: 'expand keywords', 'generate keywords', 'find synonyms for role', 'what titles to search for', or when setting up a new job search target."
---

# Keyword Expander Skill

## Purpose

Takes a seed role title (e.g., "Head of QA") and generates a comprehensive, deduplicated list of keyword variations that cover the same or very similar roles across different companies and naming conventions.

## When to Use

- User provides a target role (e.g., "Head of QA", "VP Engineering")
- User wants to set up or update job search keywords
- User asks "what titles should I search for?"
- Initial setup of the job hunter agent

## How It Works

### Step 1: Analyze the Seed Role

Break down the seed title into components:
- **Function**: QA, Quality Assurance, Quality Engineering, Testing, QE
- **Level**: Head, Director, VP, Senior Director, Global Head, Chief
- **Scope modifiers**: Global, Regional, Enterprise, Platform

### Step 2: Generate Variations

For each component, produce systematic combinations:

**Function synonyms** (for "QA"):
- Quality Assurance
- Quality Engineering  
- Quality
- QA
- QE
- Testing
- Test Engineering
- Software Quality
- SDET (only if IC roles included)

**Level synonyms** (for "Head of"):
- Head of
- Director of
- VP of / Vice President of
- Senior Director of
- Global Head of
- Associate VP of
- Group Head of

**Pattern templates**:
- `{Level} {Function}` → "Head of QA"
- `{Function} {Level-noun}` → "QA Director"
- `{Level} of {Function}` → "Director of Quality Assurance"
- `{Function} {Level-noun}, {Scope}` → "QA Director, Global"

### Step 3: Validate and Deduplicate

- Remove exact duplicates (case-insensitive)
- Remove titles that are clearly a different level (e.g., "QA Manager" if target is Director+)
- Remove titles that are clearly a different function (e.g., "Head of Engineering" too broad)
- Sort by relevance: exact match first, then close variations, then stretch

### Step 4: Categorize Output

```json
{
  "seed_role": "Head of QA",
  "generated_at": "2026-02-27T10:00:00Z",
  "keywords": {
    "exact_match": [
      "Head of QA",
      "Head of Quality Assurance",
      "Head of Quality Engineering"
    ],
    "close_variations": [
      "QA Director",
      "Director of QA",
      "Director of Quality Assurance",
      "Director of Quality Engineering",
      "Director of Quality",
      "Quality Engineering Director",
      "VP of QA",
      "VP of Quality Assurance",
      "VP Quality Engineering",
      "VP Quality",
      "Head of Testing",
      "Head of Test Engineering",
      "Head of Quality"
    ],
    "stretch_titles": [
      "Senior Director of QA",
      "Senior Director Quality Engineering",
      "Global Head of QA",
      "Global Head of Quality",
      "Global QA Director",
      "Associate VP Quality",
      "Group Head of Quality",
      "Chief Quality Officer"
    ],
    "exclude_patterns": [
      "QA Manager",
      "QA Lead",
      "Senior QA Engineer",
      "QA Analyst",
      "Test Manager"
    ]
  },
  "flat_list_for_scanner": [
    "Head of QA",
    "Head of Quality Assurance",
    "Head of Quality Engineering",
    "QA Director",
    "Director of QA",
    "Director of Quality Assurance",
    "Director of Quality Engineering",
    "Director of Quality",
    "Quality Engineering Director",
    "VP of QA",
    "VP of Quality Assurance",
    "VP Quality Engineering",
    "VP Quality",
    "Head of Testing",
    "Head of Test Engineering",
    "Head of Quality",
    "Senior Director of QA",
    "Senior Director Quality Engineering",
    "Global Head of QA",
    "Global Head of Quality",
    "Global QA Director",
    "Associate VP Quality",
    "Group Head of Quality",
    "Chief Quality Officer"
  ]
}
```

### Step 5: Update Scanner Config

After user approval, write the `flat_list_for_scanner` to `config/default.json` → `JOB_KEYWORDS` array for job-scanner-tg-notification.

Also save the full categorized output to `~/openclaw/workspace/jobs/keywords.json` for reference.

## Interaction Flow

```
User: "Ищи вакансии Head of QA"

Agent:
1. Генерирую ключевые слова...

📋 Ключевые слова для поиска "Head of QA":

🎯 Точное совпадение (3):
   Head of QA, Head of Quality Assurance, Head of Quality Engineering

🔄 Близкие вариации (13):
   QA Director, Director of QA, Director of Quality Assurance,
   Director of Quality Engineering, VP of QA, VP Quality Engineering,
   Head of Testing, Head of Quality, ...

🔭 Расширенные (8):
   Senior Director of QA, Global Head of QA, Global QA Director,
   Chief Quality Officer, ...

❌ Исключены (уровень ниже):
   QA Manager, QA Lead, Senior QA Engineer, ...

Всего: 24 ключевых слова

→ "Approve" — сохранить и обновить конфиг сканера
→ "Add: ..." — добавить свои варианты
→ "Remove: ..." — убрать лишние
```

## File Outputs

| File | Path | Purpose |
|------|------|---------|
| Full keyword data | `~/openclaw/workspace/jobs/keywords.json` | Reference with categories |
| Scanner config | `config/default.json` → `JOB_KEYWORDS` | For job-scanner-tg-notification |

## Notes

- Keywords are case-insensitive during scanning (job-scanner-tg handles this)
- The `exclude_patterns` list is informational — it helps the user understand what's NOT included
- User can always add custom keywords manually
- Re-running the skill with a different seed role REPLACES the list (with confirmation)
- Running with multiple seed roles MERGES the lists
