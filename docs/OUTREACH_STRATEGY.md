# Outreach Strategy: скрытый рынок QA Director

_Дата: 2026-03-21_

## Контекст

70-85% позиций уровня Director никогда не публикуются. Стратегия — выйти напрямую на нанимающих менеджеров и executive search рекрутеров до появления вакансии.

**Два целевых сегмента:**
1. **Нанимающие менеджеры** — CTO, VP Engineering, CPTO в целевых компаниях
2. **Executive Search рекрутеры** — агентства и фрилансеры, закрывающие tech director роли

---

## Фаза A — Бесплатный путь (текущий приоритет)

### Инструменты
| Инструмент | Что даёт | Лимит | Цена |
|---|---|---|---|
| Google Custom Search API | LinkedIn профили рекрутеров и менеджеров | 100 запросов/день × 10 = 1000 профилей | $0 |
| Hunter.io free | Email по домену + имени | 25 поисков/мес | $0 |
| Snov.io free | Email верификация | 50 кредитов/мес | $0 |
| Email pattern guessing | firstname.lastname@company.com | Unlimited | $0 |

### Архитектура

```
Google CSE (site:linkedin.com/in/)
  → linkedin_search.py
    → MongoDB: targets, agencies
      → email_finder.py (Hunter.io + pattern)
        → contact-finder skill (OpenClaw)
          → outreach-manager skill (трекинг статусов)
```

### Настройка Google CSE (разово)

1. [programmablesearchengine.google.com](https://programmablesearchengine.google.com) → Add
2. Sites to search: `linkedin.com/in/*`
3. Search features → включить **Search the entire web**
4. Скопировать **Search Engine ID (cx)**
5. В Google Cloud Console → включить **Custom Search API** (тот же проект что Sheets)

### Поисковые запросы

**Рекрутеры executive search:**
```
site:linkedin.com/in/ "executive recruiter" "quality assurance" OR "QA" technology
site:linkedin.com/in/ "technical recruiter" "Head of QA" OR "QA Director"
site:linkedin.com/in/ "talent partner" "engineering" "director" remote
```

**Нанимающие менеджеры:**
```
site:linkedin.com/in/ "VP Engineering" "fintech" OR "saas" "Ukraine" OR "remote"
site:linkedin.com/in/ "CTO" "quality" "200-500 employees"
site:linkedin.com/in/ "VP of Engineering" "recently joined" OR "new role"
```

**Сигнальные запросы (QA Director ушёл/ищет):**
```
site:linkedin.com/in/ "Head of QA" OR "QA Director" "open to work"
site:linkedin.com/in/ "Director of Quality" "looking for new opportunities"
```

### Скрипты

```
scanner/linkedin_search.py   — CSE запрос → MongoDB targets/agencies
scanner/email_finder.py      — имя + домен → email через Hunter/pattern
```

### MongoDB коллекции

```json
// targets — нанимающие менеджеры
{
  "name": "John Smith",
  "title": "VP Engineering",
  "company": "Stripe",
  "linkedin": "linkedin.com/in/jsmith",
  "email": "j.smith@stripe.com",
  "email_verified": true,
  "source": "google_cse",
  "signal_score": 0,
  "outreach_status": "pending",
  "sent_at": null,
  "next_followup": null,
  "notes": ""
}

// agencies — executive search агентства и рекрутеры
{
  "name": "Anna Ivanova",
  "agency": "Ward Howell",
  "type": "exec_search",
  "linkedin": "linkedin.com/in/aivanova",
  "email": "a.ivanova@wardhowell.com",
  "specialization": "tech/QA",
  "relationship_status": "new",
  "last_contact": null,
  "notes": ""
}
```

### OpenClaw Skills (создать)

| Skill | Триггер | Что делает |
|---|---|---|
| `contact-finder` | `/find_recruiters`, `/find_managers` | Запрос в Google CSE → сохранить в MongoDB |
| `outreach-manager` | `/outreach`, `/followup`, `/pipeline` | Трекинг статусов, follow-up напоминания |

---

## Фаза B — Платный путь (после исчерпания бесплатного)

| Инструмент | Что добавляет | Цена |
|---|---|---|
| **Apollo.io Basic** | 270M контактов, email гарантирован, сигналы о найме | $49/мес |
| **Hunter.io Starter** | 500 email поисков/мес | $49/мес |

Apollo.io один перекрывает оба инструмента — при переходе на платный путь взять его.

---

## Сигналы для приоритизации компаний

Компании с высоким signal_score — первые в очереди outreach.

| Сигнал | Вес | Источник |
|---|---|---|
| QA Director обновил профиль / "open to work" | +40 | LinkedIn CSE |
| Новый CTO/VP Eng нанят 1-3 мес назад | +30 | LinkedIn CSE |
| Series B/C раунд | +25 | Crunchbase (Фаза B) |
| 3+ QA Engineer вакансий открыто | +25 | Scanner (уже есть) |
| 5+ QA нанято за 6 мес | +20 | LinkedIn CSE |
| Production инцидент / плохие отзывы | +15 | Google Alerts |

---

## Список целевых Executive Search агентств (стартовый)

### Глобальные tech-специализированные
- DHR International
- WilsonHCG
- Leathwaite (fintech/tech)
- Frazer Jones (QA/testing, UK)
- Executives Online (remote-first)
- Heidrick & Struggles

### CIS / Европа
- Ward Howell
- Antal International (Варшава, Прага, Москва)
- Odgers Berndtson (Европа)
- Michael Page Technology

### Задача: найти конкретных рекрутеров в каждом через Google CSE

---

## Приоритеты реализации

```
✅ Сейчас:     Настроить Google CSE (5 мин, вручную)
   Шаг 1:     linkedin_search.py + MongoDB targets/agencies
   Шаг 2:     email_finder.py (Hunter.io + pattern)
   Шаг 3:     contact-finder skill
   Шаг 4:     outreach-manager skill
   Фаза B:    Apollo.io — когда бесплатные лимиты станут узким местом
```

---

## Связь с roadmap.md

Этот документ — параллельный трек к `roadmap.md` (источники вакансий).
Оба трека работают на одну базу MongoDB, но разные коллекции:

| roadmap.md | OUTREACH_STRATEGY.md |
|---|---|
| `vacancies` коллекция | `targets`, `agencies` коллекции |
| scanner + enrichment | linkedin_search + email_finder |
| Найти вакансию | Найти человека до вакансии |
