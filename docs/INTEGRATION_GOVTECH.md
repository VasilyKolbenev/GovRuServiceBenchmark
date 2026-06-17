# Подключение к продукту GovTech

## Принцип

«Агент под тестом» — **сменный слот**. Один и тот же набор задач гоняется через
`reference` / `gov1` / `gov2`; вкладка «Сравнение версий» в портале показывает версии на
одних сценариях. Это и есть **приёмочный гейт GovTech 2.0**: «2.0 готова, когда обходит 1.0 и
закрывает разрыв надёжности pass^k».

## GovTech 1.0 (baseline)

Реализовать `Gov1Adapter.run` в [`ruservicebench/agents.py`](../ruservicebench/agents.py):

- вести диалог с `GOV1_ENDPOINT` (например, `POST {session, msg}`), собрать `transcript`;
- оценка в **JUDGE**-режиме (GovTech 1.0 обычно не вызывает наши инструменты, состояние песочницы
  не меняет).

Нужно: `GOV1_ENDPOINT` + `GOV1_TOKEN` (staging) в `.env`.

## GovTech 2.0 (A2A)

`Gov2Adapter.run`: слать `Task {intent, context, session_id}` на `GOV2_A2A_ENDPOINT`,
обрабатывать `TaskResult`.

**Критично:** инструменты GovTech 2.0 в тестовом контуре должны быть **перенаправлены на нашу
мок-песочницу** (или staging-копии ведомств), а не на боевые API — иначе нельзя задать
`initial_state` и проверить `final_state` (см. [пояснительную записку](EXPLANATORY_NOTE.md), §4).

## Выравнивание инструментов

`tool_specs()` в [`environments.py`](../ruservicebench/environments.py) свести с реальными
MCP-инструментами GovTech (имена и параметры), чтобы агент 2.0 вызывал их без переходников.

## Запуск

```bash
python run_eval.py --agent gov1 --runs 10
python run_eval.py --agent gov2 --runs 10
```

Результаты накапливаются — вкладка «Сравнение версий» обновляется автоматически.
