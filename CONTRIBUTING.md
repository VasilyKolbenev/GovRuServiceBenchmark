# Как дополнять стенд

## Добавить задачу (для предметников — без глубокого кода)

Правьте [`tasks/seed_tasks.json`](tasks/seed_tasks.json). Поля задачи:

| Поле | Назначение |
|---|---|
| `id`, `title` | идентификатор и название |
| `domains` | список доменов: `jkh` / `edu` / `mfc` |
| `type` | `single` / `multi` (мультидомен) / `proactive` |
| `reward_mode` | `state` (сверка состояния) / `judge` (оценка по рубрике) |
| `user_goal`, `user_values` | цель пользователя и данные, раскрываемые по запросу |
| `initial_state` | стартовое состояние песочницы (перекрывает дефолт) |
| `expected` | проверки по dotted-путям (для `state`) |
| `rubric` | критерий (для `judge`) |
| `demo_solution` | шаги для dry-run DemoAgent |

Задачи **валидируются на загрузке** — при ошибке будет понятное сообщение (пустой `expected`,
путь вне доменов, неизвестный домен и т.п.).

Проверка: `python run_eval.py --dry-run --task <ваш_id>`.

## Добавить инструмент или домен

[`ruservicebench/environments.py`](ruservicebench/environments.py): состояние в `DEFAULT`,
методы-инструменты и их описание в `tool_specs()`. Сверяйте сигнатуры с реальными
MCP-инструментами ЦАМ (см. [docs/INTEGRATION_CAM.md](docs/INTEGRATION_CAM.md)).

## Тесты

Новый код — с тестами в [`tests/`](tests) (stdlib `unittest`, без зависимостей).
Перед PR:

```bash
python -m unittest discover -s tests -t .
python run_eval.py --dry-run
```

## Стиль

- Ядро харнесса — на стандартной библиотеке (dry-run работает без установки). Новые
  зависимости — только в `requirements.txt` и только при реальной необходимости.
- Контент задач и промпты — на русском. Вендор LLM не хардкодить (переключается через `.env`).
