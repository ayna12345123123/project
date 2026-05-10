# orgos-team — автономная AI-команда из 8 агентов

Минимальный, но работающий мульти-агентный генератор проектов на базе
**Canopy Wave** (модель `moonshotai/kimi-k2-thinking` по умолчанию). Принимает
описание идеи на любом языке и пишет полноценный код проекта в `output/<slug>/`.

> **Это MVP**, а не "автономная инженерная организация" из `ARCHITECTURE.md`.
> См. раздел [Что MVP делает / не делает](#что-mvp-делает--не-делает) ниже.

---

## Архитектура за 30 секунд

```
        idea (любой язык)
              │
              ▼
        ┌───────────┐
        │  Product  │  пишет Spec
        └─────┬─────┘
              ▼
        ┌───────────┐
        │ Architect │  пишет Plan: список файлов + кто их пишет
        └─────┬─────┘
              ▼
   ┌──────────┴──────────┐
   ▼          ▼          ▼          ▼
Backend   Frontend   DevOps     QA       (4 параллельно — пишут v1)
   └──────────┬──────────┘
              ▼
        ┌───────────┐
        │ Reviewer  │  ┐
        │ Security  │  │ ← (2 параллельно)  → собирают findings
        └─────┬─────┘
              ▼
   ┌──────────┴──────────┐
   ▼          ▼          ▼          ▼
Backend   Frontend   DevOps     QA       (4 параллельно — пишут v2 с фиксами)
   └──────────┬──────────┘
              ▼
        write to disk + git init + initial commit
```

8 агентов, 1 LangGraph state machine, ~14 LLM-вызовов на проект.

---

## Установка

Требуется Python 3.11+.

```bash
cd tools/orgos-team

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Откройте .env и впишите ваш CANOPYWAVE_API_KEY
```

---

## Запуск

```bash
python -m orgos "Telegram-бот для учёта расходов на aiogram + Postgres"
```

Что происходит дальше:

1. В терминале появляется лог-стрим: `▶ spec.start`, `■ spec.done`, `▶ plan.start`, …
2. По окончании появляется проект в `output/<имя_проекта>/`.
3. Внутри проекта — `git init` + первый коммит (можно отключить: `--no-git-init`).
4. Метаданные (Spec, Plan, findings) лежат в `output/<имя>/.orgos/`.

Опции:

```bash
python -m orgos --help

  idea              описание проекта (любой язык)

  --env-file        путь к .env (по умолчанию ./.env)
  --output-dir      переопределить ORGOS_OUTPUT_DIR
  --git-init/--no-git-init   делать ли git init (по умолчанию yes)
  --verbose, -v     debug-логи
```

---

## Конфигурация

`.env`:

| Переменная | Назначение |
|---|---|
| `CANOPYWAVE_API_KEY` | **Обязательно.** Ключ от Canopy Wave. |
| `CANOPYWAVE_BASE_URL` | По умолчанию `https://inference.canopywave.io/v1`. |
| `ORGOS_DEFAULT_MODEL` | Модель для всех агентов. По умолчанию `moonshotai/kimi-k2-thinking`. |
| `ORGOS_MODEL_<ROLE>` | Переопределение модели на конкретную роль (PRODUCT, ARCHITECT, BACKEND, FRONTEND, DEVOPS, QA, REVIEWER, SECURITY). |
| `ORGOS_MAX_CONCURRENCY` | Сколько LLM-вызовов параллельно (по умолчанию 4). |
| `ORGOS_TEMPERATURE` | Temperature для LLM (по умолчанию 0.2). |
| `ORGOS_OUTPUT_DIR` | Куда писать сгенерированные проекты (по умолчанию `output`). |

### Разные модели для разных ролей

Например, использовать тяжёлую модель только для архитектора и ревью:

```
ORGOS_DEFAULT_MODEL=qwen/qwen3-coder
ORGOS_MODEL_ARCHITECT=moonshotai/kimi-k2-thinking
ORGOS_MODEL_REVIEWER=moonshotai/kimi-k2-thinking
ORGOS_MODEL_SECURITY=moonshotai/kimi-k2-thinking
```

---

## Что MVP делает / не делает

### Делает

- Принимает идею на любом языке (русский, английский, и т.д.).
- 8 ролей агентов, каждая с собственным промтом в `prompts/<role>.md`.
- Параллельная имплементация по доменам (backend / frontend / devops / qa).
- Двухпроходный review-loop: Reviewer + Security находят дефекты, имплементеры фиксят.
- Pydantic-схемы на каждом шаге — не парсим vibes, а валидируем JSON.
- Выходной проект всегда содержит README, тесты, .env.example (если нужно).
- Безопасная запись на диск: пути нормализуются, traversal заблокирован.

### Не делает (это другой уровень — см. `ARCHITECTURE.md`)

- Нет MCP-серверов как отдельных контейнеров — агенты не "ходят в FS/Git", они генерируют JSON.
- Нет gVisor-песочницы — сгенерированный код не выполняется автоматически.
- Нет долгосрочной памяти (Qdrant) и эмбеддингов кодовой базы.
- Нет ARCH.lock и arch-lint.
- Нет мульти-проектной памяти между запусками.
- Нет CI-pipeline'а внутри (его нужно настроить отдельно для сгенерированного проекта).
- Нет UI / control plane — только CLI.
- Нет автоматической итерации больше 2-х проходов (v1 → review → v2 → стоп).

### На каких задачах сработает хорошо

- Telegram/Discord боты (aiogram, discord.py)
- Простые FastAPI/Express backends с SQLite/Postgres
- CLI-утилиты на Python/Go/TS
- Скрипты-парсеры
- Лендинги на Next.js без сложной авторизации
- Микро-сервисы на 1-2 эндпоинта

### Где начнёт сыпаться

- Большие монорепо
- Сложная авторизация / биллинг / multi-tenant
- Проекты, где нужно ходить в существующий код
- Что-то, требующее реальной итерации тестирования (без MCP-песочницы)
- Production-grade SaaS уровня LinkForge — для этого нужна полная архитектура

---

## Структура

```
tools/orgos-team/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── orgos/
│   ├── __init__.py
│   ├── __main__.py        # CLI вход
│   ├── config.py          # загрузка .env, role→model
│   ├── llm.py             # async-клиент Canopy Wave + retry + JSON-валидация
│   ├── schemas.py         # Pydantic-модели (Spec, Plan, GeneratedFile, Finding, …)
│   ├── workflow.py        # LangGraph state machine
│   ├── output.py          # запись на диск + git
│   ├── ui.py              # rich CLI
│   └── agents/
│       ├── __init__.py
│       ├── product.py
│       ├── architect.py
│       ├── implementer.py # реализатор + фиксер (для всех 4 доменов)
│       ├── reviewer.py
│       └── security.py
└── prompts/
    ├── product.md
    ├── architect.md
    ├── backend.md
    ├── frontend.md
    ├── devops.md
    ├── qa.md
    ├── reviewer.md
    └── security.md
```

---

## Где оно может сломаться (известные ограничения)

- **Rate limits Canopy Wave.** Если уперётесь — снизьте `ORGOS_MAX_CONCURRENCY` до 2 или 1. Retry с экспоненциальным backoff уже встроен в `llm.py`.
- **JSON-парсинг.** Иногда модель возвращает JSON в markdown-fences. `llm.py` снимает их защитно. Если не помогло — увеличится `max_retries`.
- **Большие файлы.** Если имплементер пытается сгенерировать файл > ~16k токенов, ответ обрежется. Архитектор должен дробить — см. промт `architect.md`.
- **Кросс-файловые баги.** Reviewer находит часть, но не все. Generated-проект всё равно стоит прогнать через `python -m py_compile` / `tsc --noEmit` и тесты вручную.
- **`output/` в `.gitignore`.** Сгенерированные проекты не коммитятся в этот репо. Это намеренно: храните их отдельно.

---

## Расширение

Хотите добавить 9-го агента? Например, "Performance Engineer":

1. `prompts/performance.md` — системный промт.
2. `orgos/agents/performance.py` — функция `run_performance(client, spec, files)`.
3. Дописать ноду в `orgos/workflow.py` (например, `node_performance` параллельно с `node_review`).
4. Добавить `performance` в кортеж `ROLES` в `config.py`.

Изменить модель для конкретной роли — без правки кода, через `.env` (`ORGOS_MODEL_PERFORMANCE=...`).

---

## Лицензия

Тот же license что у родительского репо linkforge.
