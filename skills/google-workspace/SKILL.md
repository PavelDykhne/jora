---
name: google-workspace
description: "Read and write Google Sheets, create and export Google Docs via service account. Use when the user wants to: read data from a spreadsheet, write rows to a sheet, generate a Google Doc from a template, export a Doc as PDF/DOCX. Triggers on: 'запиши в таблицу', 'прочитай таблицу', 'создай документ', 'добавь в sheets', 'сгенерируй doc', 'экспортируй в pdf', 'google sheets', 'google docs', or when job-coordinator needs to log vacancies/reports to a spreadsheet."
---

# Google Workspace Skill

## Tool

`/home/oc/.local/bin/jora-gapi` — Google Sheets & Docs via service account

Service account: `jora-gog@jora-gog.iam.gserviceaccount.com`
Key file: `/home/oc/jora-gog-49c5cb47caec.json`

**Important:** Before using any Sheet or Doc, it must be shared with the service account email:
`jora-gog@jora-gog.iam.gserviceaccount.com` (role: Editor)

## Google Sheets

### Read data
```bash
/home/oc/.local/bin/jora-gapi sheets read <SHEET_ID> "Sheet1!A1:Z100"
# Returns JSON array of rows: [["val1","val2"],["val3","val4"]]
```

### Write data (overwrites range)
```bash
/home/oc/.local/bin/jora-gapi sheets write <SHEET_ID> "Sheet1!A1" '[["Header1","Header2"],["val1","val2"]]'
```

### Append rows (adds to end)
```bash
/home/oc/.local/bin/jora-gapi sheets append <SHEET_ID> "Sheet1!A:Z" '[["new row","value2","value3"]]'
```

### Clear range
```bash
/home/oc/.local/bin/jora-gapi sheets clear <SHEET_ID> "Sheet1!A2:Z"
```

### Get SHEET_ID from URL
URL: `https://docs.google.com/spreadsheets/d/SHEET_ID/edit`

## Google Docs

### Create new document
```bash
/home/oc/.local/bin/jora-gapi docs create "Document Title"
# Returns: {"doc_id": "...", "title": "...", "url": "https://docs.google.com/..."}
```

### Read document text
```bash
/home/oc/.local/bin/jora-gapi docs read <DOC_ID>
```

### Export document
```bash
/home/oc/.local/bin/jora-gapi docs export <DOC_ID> txt   # plain text
/home/oc/.local/bin/jora-gapi docs export <DOC_ID> pdf   # PDF (binary to stdout)
/home/oc/.local/bin/jora-gapi docs export <DOC_ID> docx  # Word
/home/oc/.local/bin/jora-gapi docs export <DOC_ID> html  # HTML
```

### Get DOC_ID from URL
URL: `https://docs.google.com/document/d/DOC_ID/edit`

## Job Search Integration

### Log vacancy to tracker sheet
When a new relevant vacancy is found, append to job tracker:
```bash
/home/oc/.local/bin/jora-gapi sheets append <TRACKER_SHEET_ID> "Vacancies!A:F" \
  '[["2026-03-01","Company Name","Head of QA","source_url","new",""]]'
```
Columns: Date | Company | Role | URL | Status | Notes

### Weekly report → Sheets
```bash
/home/oc/.local/bin/jora-gapi sheets append <TRACKER_SHEET_ID> "Reports!A:E" \
  '[["2026-03-01","42","5","3","1"]]'
```
Columns: Week | Scanned | New | Applied | Interviews

### Generate cover letter Doc from template
1. Read template: `jora-gapi docs read <TEMPLATE_DOC_ID>`
2. Substitute placeholders: `{{COMPANY}}`, `{{ROLE}}`, `{{DATE}}`
3. Create new doc: `jora-gapi docs create "Cover Letter — CompanyName"`
4. Write filled content via Docs API (use write tool or bash)

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `403 forbidden` | Sheet/Doc not shared | Share with `jora-gog@jora-gog.iam.gserviceaccount.com` |
| `404 not found` | Wrong ID | Check URL, extract ID correctly |
| `invalid range` | Wrong range format | Use `Sheet1!A1:Z100` format |

## Setup Check
```bash
# Verify tool works
/home/oc/.local/bin/jora-gapi 2>&1

# Test with a shared sheet (replace with real ID)
/home/oc/.local/bin/jora-gapi sheets read <SHEET_ID> "A1:A1"
```
