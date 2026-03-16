# Roadmap: расширение источников сканера

_Дата: 2026-03-16_

## ✅ Фаза 0 — Активация готового (ВЫПОЛНЕНО 2026-03-16)

Все 42 pending источника провалидированы вручную (HTTP-запросы + анализ HTML). Коммит `c71e8b8`.

**Результат:**
- Web источников: **30 → 56** (+26 активировано)
- TG каналов: **12 → 15** (+3: @remote_qa_jobs, @qa_vacancies, @devjobs)
- Inactive (убрано): conundrum.ai (фейк), Nexters (rebrand→GDEV), AlgoBrains (DNS dead), @djinnijobs и @workintech (неверные каналы)
- Grey: Tapclap, Waxbill, Altoros, Brask, Secreate, Gaviti, HomeBuddy, Grid Dynamics (не нанимают / не парсятся)

**Из новых 26 веб-источников подтверждены листинги:**
Wheely (40), Strikerz (36), Adapty (20), Velvetech (18), Osome (18), Mayflower/SPA, DataArt/SPA, Exness/SPA, Playrix/SPA, Wargaming/SPA и др.
Текущих совпадений по ключевым словам Head of QA / QA Director: **0** (рынок пуст)

**Замечание по валидации:** при массовой проверке источников эффективнее собирать HTML батчем через Python/requests, затем отправлять в Claude API одним запросом — вместо последовательных tool calls на каждый источник.

## Фаза 1 — Крупные агрегаторы СНГ/Европы

| Источник | Тип | Сложность | Почему важен |
|---|---|---|---|
| **hh.ru** | Web API | Низкая | Крупнейший рынок СНГ, публичный API |
| **dou.ua** | Web | Низкая | Украинский рынок, хорошо парсится |
| **Relocate.me** | Web | Низкая | Релокейшн-вакансии, tech-focus |
| **Remotive.io** | JSON API | Низкая | Открытый JSON endpoint, remote-only, глобально |
| **Himalayas.app** | JSON feed | Низкая | Растущий remote job board, JSON sitemap |
| **Jobgether.com** | Web | Средняя | Remote-first, Европа |

## Фаза 2 — Ревив серых источников

41 grey с `failures=0, listings=0` — большинство никогда не давали результат по селектору
или требуют puppeteer. Проверить выборочно:

- **SOFTSWISS, SDG, AIBY, SoftTeco, Inktech, Glera** — игровые/tech CIS, есть команды QA
- **Wellfound** — возможно сломан селектор (0 listings, 0 failures)
- **BuiltIn** — возможно нужен другой URL/селектор
- **Revolut** — периодически открывает Head of QA, держать на мониторинге

## Фаза 3 — Telegram расширение

Уже активно: 12 каналов + 3 pending. Добавить направленные каналы:

**QA / Leadership:**
- `@qa_jobs_remote` — QA вакансии удалённо
- `@it_management_jobs` — IT менеджмент вакансии
- `@cto_jobs` — CTO/Tech Lead вакансии (часть релевантна)
- `@hh_remote` — hh.ru remote вакансии
- `@tproger_jobs` — Tproger jobs feed

**Международные:**
- `@remotejobs_global`
- `@tech_jobs_eng`

Все каналы нужно валидировать через `source-validator` перед добавлением.

## Фаза 4 — Нестандартные источники

| Источник | Тип | Примечание |
|---|---|---|
| **Google Alerts RSS** | RSS | Алерт "Head of QA" → RSS → парсить |
| **Ministry of Testing Jobs** | Web | QA-специфичный job board |
| **Workable public listings** | Web | Многие стартапы используют Workable |
| **Greenhouse board API** | API | Агрегация по company slug — нужен список компаний |
| **LinkedIn (Proxycurl API)** | Paid API | $0.01/профиль, доступ к закрытым вакансиям |

## Приоритизация

```
✅ Неделя 1:  Фаза 0 — выполнено 2026-03-16 (56 web + 15 TG активно)
   Неделя 2:  Фаза 1 — hh.ru + Remotive + Himalayas + Relocate.me
   Неделя 3:  Фаза 3 — новые TG каналы
   Неделя 4+: Фаза 2 (ревив grey) + Фаза 4 (нестандартные)
```
