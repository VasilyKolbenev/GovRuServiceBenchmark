# Инструкция по использованию

## Установка

Требования: **Python 3.10+**. Ядро и dry-run работают на стандартной библиотеке, без установки.

Для реальных прогонов (LLM):

```bash
cp .env.example .env            # заполнить LLM_API_KEY
pip install -r requirements.txt # openai SDK
```

## Быстрый старт

```bash
python run_eval.py --dry-run                          # проверка пайплайна (без ключей и сети)
python run_eval.py --agent reference --runs 10 --k 5  # реальный прогон на фронтир-модели
```

Затем откройте **`out/index.html`** в браузере — это единый портал со всеми вкладками.
Печать (Ctrl+P → «Сохранить как PDF») разворачивает всё в один документ для рассылки.

## Флаги CLI

| Флаг | Значение |
|---|---|
| `--agent` | `demo` \| `reference` \| `gov1` \| `gov2` |
| `--runs N` | прогонов на задачу (n); для pass^k нужно n>k |
| `--k K` | макс. k для кривой pass^k (K ≤ N) |
| `--task <подстрока>` | только задачи, чей id содержит подстроку |
| `--limit N` | первые N задач |
| `--tasks <путь>` | файл задач (по умолчанию `tasks/seed_tasks.json`) |
| `--out <папка>` | каталог результатов (по умолчанию `out`) |
| `--dry-run` | DemoAgent + FakeLLM, без сети/ключей |

## Дешёвая итерация (экономия токенов)

```bash
python run_eval.py --agent reference --task jkh --runs 3   # только ЖКХ, 3 прогона
python run_eval.py --agent reference --limit 3             # первые 3 задачи
```

## Выходные файлы

| Файл | Кому |
|---|---|
| `out/index.html` | **людям** — единый портал (обзор, надёжность, сравнение, провалы, стоимость, задачи, методология) |
| `out/report.md` | markdown — для git-дифф и CI |
| `out/summary.json`, `out/runs.csv`, `out/agents/*.json` | машинно — для дашбордов/выгрузок |

## Переключение провайдера и модели

В `.env`: `LLM_PROVIDER` (`fake`/`openai`/`anthropic`), `LLM_MODEL`. Судью можно вынести на
отдельную модель (чтобы не оценивал «сам себя») через `LLM_JUDGE_PROVIDER`/`LLM_JUDGE_MODEL`/`LLM_JUDGE_API_KEY`.

## Тесты

```bash
python -m unittest discover -s tests -t .
```
