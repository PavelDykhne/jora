# Roadmap: расширение источников сканера

_Дата: 2026-03-16_

## Фаза 0 — Активация готового (нулевые усилия)

**42 pending источника** уже сконфигурированы, просто не активированы.
Запустить `source-validator` в OpenClaw → включить рабочие.

- 39 корпоративных страниц (DataArt, Exness, Playrix, Wargaming, Tabby, Grid Dynamics, Nexters, Osome, Wheely, Kolesa, Tabby, BrainRocket...)
- 3 TG канала (Remote QA Jobs, QA Вакансии, Dev & QA Jobs)

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
Неделя 1:  Фаза 0 — активировать pending (42 источника)
Неделя 2:  Фаза 1 — hh.ru + Remotive + Himalayas + Relocate.me
Неделя 3:  Фаза 3 — новые TG каналы
Неделя 4+: Фаза 2 (ревив grey) + Фаза 4 (нестандартные)
```
