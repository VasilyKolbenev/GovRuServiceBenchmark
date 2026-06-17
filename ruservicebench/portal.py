"""Единый портал: один самодостаточный out/index.html с вкладками под все аудитории.
Сворачивает дашборд + сравнение + детальный отчёт в одну страницу (inline-SVG, без сервера).
Переиспользует секции-рендеры из dashboard.py и compare.py — не дублирует логику."""
from __future__ import annotations
import html as _html
from datetime import datetime
from typing import Any
from .schemas import Task, RunResult
from .dashboard import (_CSS, _pct, _num, _exec_summary, _kpis, _svg_passk, _svg_bars,
                        _lights, _version_panel, _task_table, _cost_cards, _failure_panel,
                        _risk_panel, _FAIL_LABELS)
from .compare import _rows as _compare_rows, _svg_compare_bars

_PORTAL_CSS = """
.tabs{display:flex;flex-wrap:wrap;gap:4px;padding:9px 0;margin-bottom:8px;border-bottom:1px solid var(--border)}
.tab{padding:6px 12px;border-radius:8px;font-size:13px;color:var(--muted);background:none;border:1px solid transparent;cursor:pointer}
.tab:hover{background:var(--surface)}
.tab.active{background:var(--bg);border:1px solid var(--border);color:var(--text);font-weight:600}
.panel{display:none}
.panel.active{display:block}
.role{font-size:12px;color:var(--muted);margin:0 0 14px}
.dialog{background:var(--surface);border-radius:10px;padding:10px 14px;margin-bottom:12px;font-size:13px}
.dialog .t{font-weight:600;font-size:13px;margin-bottom:6px}
.turn{margin:3px 0}
.turn .who{color:var(--muted)}
.q{color:var(--info)}
@media print{.tab{display:none}.panel{display:block!important}.tabs{display:none}}
"""


def _esc(s: Any) -> str:
    return _html.escape(str(s))


def _tab_overview(summary, agent_name, curve, ci, pass1, passk, k_max, gap):
    return (f'{_exec_summary(summary, pass1, passk, k_max, gap)}'
            f'{_kpis(pass1, passk, k_max, summary["n_tasks"])}'
            f'<p class="sec">Надёжность по числу попыток pass^k (полоса — 95% ДИ)</p>'
            f'<div class="card">{_svg_passk(curve, ci)}</div>'
            f'<p class="sec" style="margin-top:20px">Цена ошибки</p>{_risk_panel()}')


def _tab_reliability(summary, k_max):
    return (f'<p class="sec">По типам задач: pass¹ против pass^{k_max}</p>'
            f'<div class="legend"><span><i style="background:var(--b1)"></i>pass¹</span>'
            f'<span><i style="background:var(--b2)"></i>pass^{k_max}</span></div>'
            f'<div class="card">{_svg_bars(summary["by_type"], k_max)}</div>'
            f'<p class="sec">Надёжность по доменам (pass^{k_max})</p>'
            f'<div class="lights">{_lights(summary["by_domain"], k_max)}</div>'
            f'<p class="sec" style="margin-top:20px">По задачам</p>{_task_table(summary["per_task"], k_max)}')


def _tab_compare(out_dir, agent_name, passk, k_max):
    agents, kc = _compare_rows(out_dir)
    if len(agents) < 2:
        return ('<p class="role">Пока подключён один агент. Прогоните другие версии '
                '(<code>--agent gov1</code> / <code>gov2</code>) — сравнение появится здесь автоматически.</p>'
                f'<p class="sec">Готовность по версиям</p>'
                f'<div class="vers">{_version_panel(agent_name, passk, k_max)}</div>')
    rows = "".join(
        f'<tr><td>{_esc(a["name"])}</td><td>{_pct(a["p1"])}</td><td><b>{_pct(a["pk"])}</b></td>'
        f'<td>−{a["gap"]} п.п.</td><td>{a["n_tasks"]}</td><td>{_num(a["tokens"])}</td></tr>' for a in agents)
    return (f'<div class="legend"><span><i style="background:var(--b1)"></i>pass¹</span>'
            f'<span><i style="background:var(--b2)"></i>pass^{kc}</span></div>'
            f'<div class="card">{_svg_compare_bars(agents)}</div>'
            f'<table><thead><tr><th>Агент</th><th>pass¹</th><th>pass^{kc}</th><th>разрыв</th>'
            f'<th>задач</th><th>ток./прогон</th></tr></thead><tbody>{rows}</tbody></table>')


def _tab_failures(summary, samples):
    fc = summary.get("failure_classes", {})
    head = f'<div class="card">{_failure_panel(fc)}</div>' if fc else '<p class="role">Провалов нет.</p>'
    if not samples:
        return head + ('<p class="role">Примеры диалогов появятся после прогона на реальной модели '
                       '(сохраняются по одному показательному прогону на задачу).</p>')
    blocks = []
    for tid, info in samples.items():
        cls = info.get("failure_class") or "—"
        turns = "".join(
            f'<div class="turn"><span class="who">[{_esc(t["role"])}]</span> '
            f'<span class="{"q" if t["role"] == "agent" else ""}">{_esc(t["text"])}</span></div>'
            for t in info.get("transcript", []))
        blocks.append(f'<div class="dialog"><div class="t">{_esc(tid)} · {_esc(_FAIL_LABELS.get(cls, cls))}'
                      f'</div>{turns or "<div class=turn>(нет реплик)</div>"}</div>')
    return head + '<p class="sec" style="margin-top:18px">Примеры провалов (диалоги)</p>' + "".join(blocks)


def _tab_cost(summary):
    c = summary.get("cost", {})
    return (f'{_cost_cards(c)}'
            '<p class="role" style="margin-top:14px">Токены и задержка суммируются по всем LLM-вызовам '
            'прогона: агент + симулятор пользователя + судья.</p>')


def _tab_tasks(tasks):
    if not tasks:
        return '<p class="role">Каталог задач недоступен.</p>'
    rows = []
    for t in tasks:
        check = "; ".join(a.path for a in t.expected) if t.expected else (t.rubric[:80] or "—")
        rows.append(f'<tr><td>{_esc(t.id)}</td><td>{_esc("+".join(t.domains))}</td>'
                    f'<td>{_esc(t.type.value)}</td><td>{_esc(t.reward_mode.value)}</td>'
                    f'<td>{_esc(t.user_goal)}</td><td>{_esc(check)}</td></tr>')
    return ('<p class="role">Каталог сценариев, на которых меряется агент. Правится в '
            '<code>tasks/seed_tasks.json</code> (валидируется на загрузке).</p>'
            '<table><thead><tr><th>id</th><th>домены</th><th>тип</th><th>оценка</th>'
            f'<th>цель пользователя</th><th>что проверяем</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _tab_methodology(k_max):
    return (
        '<p class="sec">Что это</p>'
        '<p class="role">Офлайн-стенд надёжности агентов госуслуг (RU): ЖКХ/ЕИРЦ, кружки, МФЦ. '
        'Меряем не «получилось ли», а «получается ли каждый раз».</p>'
        f'<p class="sec">pass^k</p><p class="role">pass¹ — обычный успех; pass^{k_max} — доля задач, '
        f'решённых во ВСЕХ {k_max} попытках (повторяемость). Разрыв pass¹→pass^{k_max} = нестабильность. '
        'Рядом — 95% доверительный интервал (отделяет результат от шума).</p>'
        '<p class="sec">Режимы оценки</p><p class="role">STATE — сверка финального состояния песочницы; '
        'JUDGE — LLM-судья по цели/рубрике (для проактивности и диалоговых задач).</p>'
        '<p class="sec">Честная граница</p><p class="role">Стенд доказывает корректность, оркестрацию и '
        'проактивность на сценариях в мок-песочнице. Боевой A/B в проде — отдельный трек, не часть стенда.</p>'
        '<p class="sec">Статус версий</p><p class="role">GovTech 1.0 — baseline (нужен endpoint); '
        'Reference (GPT-5.5) — агентный baseline; GovTech 2.0 — приёмочный контур (когда запустится).</p>')


def write_portal(summary: dict[str, Any], agent_name: str, out_dir: str,
                 tasks: list[Task] | None = None,
                 samples: dict[str, Any] | None = None) -> str:
    """Собирает единый портал out/index.html со всеми вкладками. Возвращает путь к файлу."""
    import os
    k_max = summary["k_max"]
    curve = {int(k): v for k, v in summary["passk_curve"].items()}
    ci = {int(k): v for k, v in summary.get("passk_ci", {}).items()}
    pass1, passk = curve.get(1, 0.0), curve.get(k_max, 0.0)
    gap = max(0, round((pass1 - passk) * 100))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    panels = [
        ("overview", "Обзор", "для руководства", _tab_overview(summary, agent_name, curve, ci, pass1, passk, k_max, gap)),
        ("reliability", "Надёжность", "продукт, технари", _tab_reliability(summary, k_max)),
        ("compare", "Сравнение версий", "руководство, продукт", _tab_compare(out_dir, agent_name, passk, k_max)),
        ("failures", "Провалы", "технари, предметники", _tab_failures(summary, samples)),
        ("cost", "Стоимость", "эксплуатация, финансы", _tab_cost(summary)),
        ("tasks", "Задачи", "предметники", _tab_tasks(tasks or [])),
        ("methodology", "Методология", "все", _tab_methodology(k_max)),
    ]
    nav = "".join(f'<button class="tab{" active" if i == 0 else ""}" data-tab="{pid}">{title}</button>'
                  for i, (pid, title, _role, _body) in enumerate(panels))
    body = "".join(
        f'<div class="panel{" active" if i == 0 else ""}" data-panel="{pid}">'
        f'<p class="role">Вкладка для: {role}</p>{content}</div>'
        for i, (pid, _title, role, content) in enumerate(panels))

    js = ("<script>document.querySelectorAll('.tab').forEach(function(t){t.addEventListener('click',function(){"
          "document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('active')});"
          "document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active')});"
          "t.classList.add('active');"
          "document.querySelector('[data-panel=\"'+t.dataset.tab+'\"]').classList.add('active');});});</script>")

    page = (f'<!DOCTYPE html>\n<html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>RuServiceBench — единый отчёт ({_esc(agent_name)})</title>'
            f'<style>{_CSS}{_PORTAL_CSS}</style></head><body><div class="wrap">'
            f'<h1>RuServiceBench — единый отчёт</h1>'
            f'<p class="sub">Агент: {_esc(agent_name)} · задач: {summary["n_tasks"]} · '
            f'прогонов: n={summary.get("runs_per_task", "?")} · кривая до k={k_max} · {ts}</p>'
            f'<div class="tabs">{nav}</div>{body}{js}</div></body></html>\n')

    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path
