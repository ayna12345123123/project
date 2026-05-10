# orgos-team — автономная AI-команда из 8 агентов

Минимальный, но работающий мульти-агентный генератор проектов на базе
**Canopy Wave** (модель `moonshotai/kimi-k2.6` по умолчанию). Принимает
описание идеи на любом языке и пишет полноценный код проекта в `output/<slug>/`.

> **Это MVP**, а не "автономная инженерная организация" из `ARCHITECTURE.md`.
> См. раздел [Что MVP делает / не делает](#что-mvp-делает--не-делает) ниже.

---

## Архитектура за 30 секунд

**Hub-and-spoke.** Все агенты общаются ТОЛЬКО через одного главного — `ChiefOrchestrator`.
Никакого прямого обращения "агент → агент" не существует физически: агенты не импортируют
друг друга, не имеют ссылок друг на друга, не передают друг другу сообщения. Каждый
переход роль → роль проходит через `Chief._route(...)` и логируется как событие
`chief.route` (видно в Web UI Run log и в CLI логах).

```
                       ┌───────────────────────┐
                       │   ChiefOrchestrator   │
                       │   (единственный hub)  │
                       └──┬──┬──┬──┬──┬────────┘
              ┌───────────┘  │  │  │  └────────┐
              ▼              ▼  ▼  ▼           ▼
         Product       Architect  │       Reviewer
                                  │       Security
                                  ▼
                  ┌─────────┬─────┴─────┬──────────┐
                  ▼         ▼           ▼          ▼
               Backend  Frontend     DevOps        QA
              (impl/fix)(impl/fix) (impl/fix)  (impl/fix)
```

Поток данных:

```
        idea (любой язык)
              │
              ▼  Chief.do_spec  → Product
        ┌───────────┐
        │  Product  │  пишет Spec → возвращает Chief'у
        └─────┬─────┘
              ▼  Chief.do_plan  → Architect
        ┌───────────┐
        │ Architect │  пишет Plan → возвращает Chief'у
        └─────┬─────┘
              ▼  Chief.do_implement  → 4 implementer'а параллельно
   ┌──────────┴──────────┐
   ▼          ▼          ▼          ▼
Backend   Frontend   DevOps     QA      → возвращают v1 файлы Chief'у
   └──────────┬──────────┘
              ▼  Chief.do_review  → Reviewer + Security параллельно
        ┌───────────┐
        │ Reviewer  │
        │ Security  │  → возвращают findings Chief'у
        └─────┬─────┘
              ▼  Chief.do_fix  → 4 fixer'а параллельно
   ┌──────────┴──────────┐
   ▼          ▼          ▼          ▼
Backend   Frontend   DevOps     QA      → возвращают v2 Chief'у
   └──────────┬──────────┘
              ▼  Chief пишет на диск + git init
```

**Важные инварианты** (тестируются в `tests/test_chief.py` и `tests/test_auto_execute.py`):
- ровно 5 типов inter-role transitions без auto-execute-tests
  (`idea→product`, `product→architect`, `architect→implementers`,
  `implementers→reviewers`, `reviewers→implementers`);
- +2 transitions с включённым auto-execute-tests
  (`implementers→test_runner` всегда, `test_runner→implementers` только если тесты упали);
- ни один файл агента не импортирует другого агента;
- весь стейт (`ChiefState`) принадлежит Chief'у — агенты не имеют разделяемой памяти.

8 агентов, 1 LangGraph state machine, ~14 LLM-вызовов на проект (+4 если включён auto-execute-tests fix-pass).

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

Два способа: **Web UI** или **CLI**. Делают одно и то же.

### Web UI (Streamlit) — рекомендуется

```bash
make ui
# или вручную:
streamlit run ui_app.py
```

Откроется на http://localhost:8501. Что внутри:

- **🎭 Demo mode** (чекбокс в sidebar) — запускает весь конвейер на детерминированном
  стабе вместо настоящего LLM. **Никаких сетевых вызовов, никакого ключа не нужно.**
  За ~3 секунды генерируется реальный, запускаемый демо-проект (Python CLI `hello`).
  Полезно для онбординга, скриншотов, скринкастов и быстрой итерации над самим UI.
- **🧪 Auto-execute tests** (чекбокс в sidebar, по умолчанию ВЫКЛ) — после fix-фазы
  материализует проект во временную директорию, создаёт изолированный venv,
  устанавливает `requirements.txt` + pytest, запускает тесты с timeout. Если тесты
  упали — собирает failures как `Finding`'и (severity=block, rule=TEST_FAIL) и
  запускает третий проход имплементеров, который правит конкретно эти места.
  Подробности в [Auto-execute tests](#auto-execute-tests).
- **Sidebar** — API ключ (можно переопределить .env), модель по умолчанию + per-role оверрайды, ползунки concurrency/temperature, выбор output dir.
- **Главное окно** — text-area для идеи + кнопки-примеры (`Telegram bot — expense tracker`, `FastAPI URL shortener`, `CLI markdown→PDF`, `Discord moderator bot`) которые подставляют готовый текст.
- **Прогресс** — лайв-стрим событий по 5 фазам (Spec / Plan / Implement / Review / Fix), с цветными статусами (`⬜ pending` / `🟡 running` / `✅ done`). Прогресс не блокирует UI: workflow крутится в background thread, а основной thread Streamlit поллит очередь событий.
- **Результат** — 5 вкладок:
  - **Files** — file-picker + подсветка синтаксиса для всех сгенерированных файлов
  - **Spec** — JSON-viewer
  - **Plan** — дерево файлов с владельцами + setup/run команды
  - **Findings** — список с цветовыми бейджами по severity (block/major/minor/nit)
  - **Run log** — полный stream событий от агентов
- **Download as .zip** — кнопка скачивает весь сгенерированный проект одним архивом.

### CLI

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
  --auto-execute-tests/--no-auto-execute-tests   запустить pytest после генерации (по умолчанию no)
  --verbose, -v     debug-логи
```

### Makefile-шорткаты

```bash
make install   # python -m venv + pip install -r requirements.txt
make ui        # streamlit run ui_app.py
make cli IDEA="ваша идея"   # python -m orgos "ваша идея"
make test      # pytest
make clean     # удалить .venv, кеши
```

---

## Конфигурация

`.env`:

| Переменная | Назначение |
|---|---|
| `CANOPYWAVE_API_KEY` | **Обязательно.** Ключ от Canopy Wave. |
| `CANOPYWAVE_BASE_URL` | По умолчанию `https://inference.canopywave.io/v1`. |
| `ORGOS_DEFAULT_MODEL` | Модель для всех агентов. По умолчанию `moonshotai/kimi-k2.6`. |
| `ORGOS_MODEL_<ROLE>` | Переопределение модели на конкретную роль (PRODUCT, ARCHITECT, BACKEND, FRONTEND, DEVOPS, QA, REVIEWER, SECURITY). |
| `ORGOS_MAX_CONCURRENCY` | Сколько LLM-вызовов параллельно (по умолчанию 4). |
| `ORGOS_TEMPERATURE` | Temperature для LLM (по умолчанию 0.2). |
| `ORGOS_OUTPUT_DIR` | Куда писать сгенерированные проекты (по умолчанию `output`). |

### Разные модели для разных ролей

Например, использовать тяжёлую модель только для архитектора и ревью:

```
ORGOS_DEFAULT_MODEL=qwen/qwen3-coder
ORGOS_MODEL_ARCHITECT=moonshotai/kimi-k2.6
ORGOS_MODEL_REVIEWER=moonshotai/kimi-k2.6
ORGOS_MODEL_SECURITY=moonshotai/kimi-k2.6
```

---

## Auto-execute tests

Опциональная фаза, которая запускает сгенерированные тесты в **изолированном
временном venv** и при провале даёт имплементерам ещё одну итерацию правок.
**По умолчанию выключена** — потому что это запуск AI-сгенерированного кода,
пусть и в песочнице.

### Что происходит при включении

```
... обычный pipeline (Spec→Plan→Implement→Review→Fix) ...
        ↓
    Chief.do_execute_tests:
        1. Создаём tempdir
        2. Материализуем все файлы из state.files_final (path-safe writer)
        3. python -m venv .venv      (timeout 90s)
        4. .venv/pip install pytest  (timeout 180s)
        5. .venv/pytest -p no:cacheprovider --color=no  (timeout 90s)
        6. Парсим pytest output, ищем "FAILED nodeid - msg" строки
        7. Записываем TestRunResult в state.test_run
        ↓
    Если ran=False (нет тестов в проекте) → пропускаем fix2.
    Если passed=True → пропускаем fix2.
    Если passed=False:
        ↓
    Chief.do_fix_from_tests:
        - Конвертируем TestFailure'ы в Finding(severity="block", rule="TEST_FAIL")
        - Запускаем имплементеров параллельно с этими findings'ами
        - Перезаписываем state.files_final
        ↓
    Конец pipeline. Финальный проект пишется на диск.
```

### Безопасность

- **Никогда не запускает код в вашем интерпретаторе.** Всегда новый venv в tempdir.
- **Path safety.** Любые попытки путей с `..`, абсолютные пути или escape из
  project_root → файл не пишется (та же логика что в `output.py`).
- **Bounded.** Три независимых таймаута (venv 90s, pip 180s, pytest 90s). Превышение
  → `TestRunResult.ran=False` с `skip_reason`, fix2 не запускается.
- **Output cap.** Только последние ~10 KB stdout+stderr попадают в `raw_output`.
- **Cleanup.** Tempdir удаляется в `finally`-блоке, даже при exception.

### Когда сработает хорошо

- Проекты на чистом Python с маленьким `requirements.txt` (FastAPI/aiogram/click и т.п.).
- QA-агент сгенерировал реальные тесты, а не "тест на то что 1+1==2".
- Простые юнит-тесты без mock'ов сложных внешних API.

### Когда не имеет смысла включать

- Не-Python проекты (Go, TS, Rust) — текущий runner только pytest.
- Проекты с тяжёлыми зависимостями (torch, transformers) — pip install не уложится в 180s.
- Тесты, которые требуют реального Postgres / Redis / etc. — мы не поднимаем сервисы.
- Если генерируемый код будет идти на code review человеком — там важнее чистый
  diff, а не "тесты прошли".

### CLI

```bash
python -m orgos "FastAPI URL shortener" --auto-execute-tests
```

### Web UI

Чекбокс **🧪 Auto-execute tests** в sidebar. Demo mode совместим (используется
`DemoTestRunner` без subprocess). После завершения появляется отдельный таб
**🧪 Tests** с количеством pass/fail, список failed test'ов и хвост pytest-output'а.

### Локальный запуск настоящего runner'а в тестах

Е2е-тест `test_real_runner_executes_tiny_passing_project` отмечен `@pytest.mark.skipif`
и не запускается в CI (медленный — 20-30s на venv + pip install). Запустить локально:

```bash
ORGOS_RUN_REAL_TEST_RUNNER=1 pytest tests/test_auto_execute.py -v
```

---

## Что MVP делает / не делает

### Делает

- Принимает идею на любом языке (русский, английский, и т.д.).
- 8 ролей агентов, каждая с собственным промтом в `prompts/<role>.md`.
- Параллельная имплементация по доменам (backend / frontend / devops / qa).
- Двухпроходный review-loop: Reviewer + Security находят дефекты, имплементеры фиксят.
- Опциональная третья итерация: запуск сгенерированных тестов в изолированном venv
  и автоматический фикс при провалах (см. раздел [Auto-execute tests](#auto-execute-tests)).
- Pydantic-схемы на каждом шаге — не парсим vibes, а валидируем JSON.
- Выходной проект всегда содержит README, тесты, .env.example (если нужно).
- Безопасная запись на диск: пути нормализуются, traversal заблокирован.

### Не делает (это другой уровень — см. `ARCHITECTURE.md`)

- Нет MCP-серверов как отдельных контейнеров — агенты не "ходят в FS/Git", они генерируют JSON.
- Нет gVisor-песочницы. Auto-execute tests изолирует через subprocess + venv + tempdir,
  но это не gVisor; не запускайте на полностью untrusted идеях.
- Нет долгосрочной памяти (Qdrant) и эмбеддингов кодовой базы.
- Нет ARCH.lock и arch-lint.
- Нет мульти-проектной памяти между запусками.
- Нет CI-pipeline'а внутри (его нужно настроить отдельно для сгенерированного проекта).
- ~~Нет UI / control plane — только CLI.~~ → Streamlit UI добавлен в PR #3.
- Максимум **3 итерации** имплементеров (v1 → review-fix → опционально test-fix → стоп);
  больше не делаем, чтобы не растить cost экспоненциально.

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
├── Makefile               # make install / make ui / make cli IDEA="…" / make test
├── README.md
├── requirements.txt
├── ui_app.py              # Streamlit web UI (опционально)
├── orgos/
│   ├── __init__.py
│   ├── __main__.py        # CLI вход
│   ├── config.py          # загрузка .env, role→model
│   ├── llm.py             # async-клиент Canopy Wave + retry + JSON-валидация
│   ├── schemas.py         # Pydantic-модели (Spec, Plan, GeneratedFile, Finding, TestRunResult, …)
│   ├── chief.py           # ChiefOrchestrator — единственный hub, через которого ходят все роли
│   ├── workflow.py        # LangGraph state machine (тонкая обёртка над Chief)
│   ├── output.py          # запись на диск + git
│   ├── test_runner.py     # изолированный pytest runner (venv + tempdir + timeouts)
│   ├── demo_client.py     # детерминированный LLM-стаб + DemoTestRunner для demo mode
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

## Web UI: внутренности (для тех кто хочет править)

`ui_app.py` — один файл Streamlit-приложения. Ключевые моменты:

- **Background thread + queue.Queue** для прогресса. Streamlit-главный поток не умеет async-await напрямую (любой долгий sync-вызов фризит UI). Поэтому:
  ```
  Click "Generate" → spawn threading.Thread(target=_worker_target, ...)
                  → worker запускает asyncio.new_event_loop() и run_until_complete(workflow)
                  → каждое progress-событие пишется в queue.Queue
                  → главный поток поллит queue, рендерит UI, делает st.rerun() каждые 0.5с
                  → когда worker кладёт ('done', state) — стопаем поллинг и рендерим results
  ```
- **st.session_state** хранит весь стейт между rerun'ами: `events`, `result`, `error`, `worker`, `event_queue`, `status` ∈ `{idle, running, done, error}`.
- **Sidebar overrides** перед запуском записываются в `os.environ` и затем `Config.load()` их подхватывает — никакого дублирующего конфиг-кода.
- **ZIP-download** строится на лету через `io.BytesIO()` + `zipfile.ZipFile`.
- **Подсветка синтаксиса** через `st.code(content, language=…)` где `language` определяется по расширению файла.

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
