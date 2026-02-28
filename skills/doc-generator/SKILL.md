---
name: doc-generator
description: "Generates the full application package: adapted resume (PDF), cover letter (PDF), company dossier, referral contacts, and recruiter contacts. Also generates personalized outreach messages. Uses Enrichment Layer 3 (deep research) to customize everything. Triggers on: '/docs {id}', '/referrals {id}', '/outreach {id}', 'prepare documents for', 'generate resume for', 'cover letter for', 'find referrals for', or when user selects a vacancy for application."
---

# Doc Generator Skill

## Purpose

For a selected vacancy, produce the full application package:
1. **Company Dossier** — deep research brief
2. **Adapted Resume** — tailored from master template
3. **Cover Letter** — targeted to the role and company
4. **Referrals** — 3-5 people of the same grade in the company who can pass your resume internally
5. **Recruiters** — 3 most relevant recruiters hiring for this type of role
6. **Outreach messages** — personalized messages for referrals and recruiters

## Inputs

- `~/openclaw/workspace/jobs/master_resume.json` — structured master resume
- `~/openclaw/workspace/jobs/candidate_profile.json` — candidate preferences and angles
- Vacancy data from MongoDB (via enrichment-svc) or from notification context

## Triggers

| Command | Action |
|---------|--------|
| `/docs {id}` | Full package: dossier + resume + CL + referrals + recruiters |
| `/referrals {id}` | Referrals + recruiters only (without docs) |
| `/outreach {id}` | Generate outreach messages for found referrals and recruiters |

## Process

### Step 1: Deep Research (Enrichment Layer 3)

Research the company beyond the basic Layer 2 brief:

- Company product lines and recent launches
- Key people: CTO, VP Eng, current/former Head of QA
- Recent news and press releases (3 months)
- Tech stack and architecture challenges
- Culture signals from Glassdoor, LinkedIn, blog
- Competitors and market positioning
- Pain points and growth areas

Output: structured dossier saved to `applications/{vacancy_id}/dossier.md`

### Step 2: Resume Adaptation

From `master_resume.json`, create a targeted version:

1. **Select relevant experience**: Emphasize roles/achievements matching the vacancy
2. **Adjust language**: Mirror the job description's terminology
3. **Highlight domain fit**: If fintech → emphasize financial experience
4. **Tune keywords**: Include ATS-friendly terms from the JD
5. **Adjust summary**: Tailor professional summary to the specific role

Output: `applications/{vacancy_id}/resume.pdf`

### Step 3: Cover Letter

Generate a targeted cover letter using:

- Dossier insights (company challenges, growth areas)
- Resume highlights (most relevant achievements)
- Candidate profile (preferred angles, values)
- Recommended "approach angle" from Layer 3 research

Output: `applications/{vacancy_id}/cover_letter.pdf`

### Step 4: Referral Search

Find 3-5 potential referrals — people who can pass the resume to the hiring manager through the company's internal referral program.

#### Search strategy

```
1. Web search (LinkedIn-focused):
   "{company}" + ("Head of QA" OR "QA Director" OR "VP Engineering"
   OR "Director of Engineering" OR "Head of Testing"
   OR "Director of Platform" OR "VP Product")

2. Filter:
   - Current employee (not "Former")
   - Grade: Director / Head / VP / Senior Director (same or 1 level up)
   - Function: QA > Engineering > Platform > Product (prioritize closer)
   - NOT a direct competitor for the same role

3. Rank:
   - Closest by function (QA > Eng > Platform > Product)
   - Closest by grade (same > one above > one below)
   - Mutual connections / communities (if detectable)
   - Recent LinkedIn activity (active > dormant)
```

Output: `applications/{vacancy_id}/referrals.json`

```json
[
  {
    "name": "Anna Schmidt",
    "title": "Director of Engineering",
    "company": "Revolut",
    "linkedin_url": "https://linkedin.com/in/anna-schmidt",
    "relevance": "Closest by function, same grade",
    "recommendation": "Write first — most likely to respond",
    "rank": 1
  }
]
```

### Step 5: Recruiter Search

Find 3 most relevant recruiters at the target company.

#### Search strategy

```
1. Web search:
   "{company}" + ("Technical Recruiter" OR "Engineering Recruiter"
   OR "Talent Acquisition" OR "Recruiting Lead"
   OR "Talent Partner" OR "TA Manager")

2. Filter:
   - Current employee
   - Hires for: Engineering / QA / Tech Leadership

3. Rank:
   - Specialization: Engineering Recruiter > General Recruiter
   - Level: Senior > Mid > Junior
   - Activity: Recent hiring posts > no recent activity
   - Scope: Leadership hiring > IC hiring
```

Output: `applications/{vacancy_id}/recruiters.json`

```json
[
  {
    "name": "James Wilson",
    "title": "Senior Technical Recruiter",
    "company": "Revolut",
    "linkedin_url": "https://linkedin.com/in/james-wilson",
    "relevance": "Hires Engineering Leadership, recent posts",
    "recommendation": "Primary contact for this role",
    "rank": 1
  }
]
```

### Step 6: Send Package to User

```
📦 {Company}: {Role}

📋 Досье: {key points summary}
📄 Резюме: акцент на {main angle}
✉️ CL: угол — {approach angle}

👥 Рефералы (3):
1. ⭐ {name} — {title} 💡 {recommendation}
2. {name} — {title}
3. {name} — {title}

🎯 Рекрутеры (3):
1. ⭐ {name} — {title} 💡 {recommendation}
2. {name} — {title}
3. {name} — {title}

📎 файлы прикреплены

→ "Approve" — сохранить всё
→ "Edit resume: {instructions}" — скорректировать
→ "Edit CL: {instructions}" — скорректировать
→ /outreach {id} — сгенерировать сообщения
→ "Regenerate" — пересоздать все
```

### Step 7: Outreach Messages (on /outreach command)

Generate personalized LinkedIn messages for each referral and recruiter:

#### Referral message template logic:
- Open with specific compliment about their work / role at the company
- Mention the target role naturally
- Brief value proposition (1-2 sentences from resume highlights)
- Soft ask: "Would you be open to passing along my profile?"
- Keep under 300 characters for LinkedIn connection request, or ~500 for InMail

#### Recruiter message template logic:
- Reference the specific role or hiring area
- 2-sentence value proposition matched to the role
- Direct ask: offer to share CV
- Keep concise and professional

```
✉️ Outreach: {Company} — {Role}

📨 Реферал #{1} ({name}):
───────────────────────
{personalized message}
───────────────────────

📨 Реферал #{2} ({name}):
───────────────────────
{personalized message}
───────────────────────

📨 Рекрутер #{1} ({name}):
───────────────────────
{personalized message}
───────────────────────

→ "Approve" / "Edit referral 1: ..." / "Edit recruiter 1: ..."
```

## File Structure

```
~/openclaw/workspace/jobs/applications/
└── {vacancy_id}/
    ├── dossier.md
    ├── resume.pdf
    ├── cover_letter.pdf
    ├── resume_source.md        # markdown source before PDF
    ├── cover_letter_source.md  # markdown source before PDF
    ├── referrals.json          # found referral contacts
    ├── recruiters.json         # found recruiter contacts
    ├── outreach_messages.md    # generated outreach messages
    └── metadata.json           # generation params, timestamps
```

## Notes

- In POC: uses web search for Layer 3 research, referral and recruiter search
- PDF generation via pandoc or wkhtmltopdf
- Master resume format follows the existing `Pavel_Dykhne_Resume.md` structure
- All documents require user approval before they are marked as "ready"
- Referral search quality depends on public LinkedIn data availability
- Outreach messages are always generated as drafts — user reviews and sends manually
- The skill respects privacy: it only uses publicly available professional information
