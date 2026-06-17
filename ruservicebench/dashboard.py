"""Executive-дашборд: самодостаточный HTML с inline-SVG (без зависимостей и без сети).
Тот же summary, что и markdown-отчёт; акцент — надёжность pass^k для руководства.
Open в браузере двойным кликом; PDF-одностраничник = печать (Ctrl+P) благодаря @media print."""
from __future__ import annotations
from datetime import datetime
from typing import Any

_CSS = """
:root{--bg:#fff;--surface:#f6f7f9;--text:#1a1a1a;--muted:#6b7280;--border:#e5e7eb;
--ok:#0f6e56;--okbg:#e1f5ee;--warn:#854f0b;--warnbg:#faeeda;--bad:#a32d2d;--badbg:#fcebeb;
--info:#185fa5;--infobg:#e6f1fb;--line:#d85a30;--b1:#378add;--b2:#d85a30}
@media(prefers-color-scheme:dark){:root{--bg:#16181c;--surface:#1f2228;--text:#e8e8e8;--muted:#9aa0aa;
--border:#2c2f36;--okbg:#0f3a30;--warnbg:#3a2c0a;--badbg:#3a1414;--infobg:#0c2c4a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);line-height:1.5;
font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif}
.wrap{max-width:840px;margin:0 auto;padding:28px 24px}
h1{font-size:22px;font-weight:600;margin:0 0 2px}
.sub{color:var(--muted);font-size:13px;margin:0 0 20px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.kpi{background:var(--surface);border-radius:10px;padding:14px 16px}
.kpi .l{font-size:12px;color:var(--muted)}
.kpi .v{font-size:26px;font-weight:600;margin-top:4px}
.kpi.bad{background:var(--badbg)}.kpi.bad .v{color:var(--bad)}
.sec{font-size:13px;color:var(--muted);margin:0 0 8px}
.card{background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:24px}
.chart{width:100%;height:auto}
.grid{stroke:var(--border);stroke-width:1}
.ax{fill:var(--muted);font-size:11px}
.val{fill:var(--text);font-size:11px;font-weight:600}
.line{fill:none;stroke:var(--line);stroke-width:2.5}
.area{fill:var(--line);opacity:.10}
.dot{fill:var(--line)}
.b1{fill:var(--b1)}.b2{fill:var(--b2)}
.lights{display:flex;flex-wrap:wrap;gap:10px}
.light{flex:1;min-width:120px;border-radius:10px;padding:12px 14px;border:1px solid var(--border)}
.light .n{font-weight:600;font-size:14px}
.light .p{font-size:13px;margin-top:4px}
.ok{background:var(--okbg)}.ok .p{color:var(--ok)}
.warn{background:var(--warnbg)}.warn .p{color:var(--warn)}
.bad{background:var(--badbg)}.bad .p{color:var(--bad)}
.vers{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.vcard{background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:14px}
.vcard.hi{border:2px solid var(--info)}
.vcard .t{font-weight:600;font-size:14px}
.vcard .d{font-size:12px;color:var(--muted);margin:4px 0 10px}
.badge{font-size:12px;padding:3px 10px;border-radius:8px;background:var(--surface);color:var(--muted);display:inline-block}
.badge.hi{background:var(--infobg);color:var(--info)}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--border)}
th{color:var(--muted);font-weight:500}
.tag{font-size:12px;padding:2px 8px;border-radius:6px}
.legend{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-bottom:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px}
.note{font-size:12px;color:var(--muted);border-left:3px solid var(--border);padding:6px 12px;margin-top:16px}
.summary{border-left:4px solid var(--border);background:var(--surface);border-radius:0 10px 10px 0;padding:12px 16px;margin-bottom:20px;font-size:14px}
.summary.ok{border-color:var(--ok)}
.summary.warn{border-color:var(--warn)}
.summary.bad{border-color:var(--bad)}
.ciband{fill:var(--line);opacity:.15}
.frow{display:flex;align-items:center;gap:10px;margin-bottom:8px;font-size:13px}
.fl{flex:0 0 230px}
.fn{flex:0 0 32px;text-align:right;color:var(--muted)}
.fbar{flex:1;height:10px;background:var(--surface);border-radius:5px;overflow:hidden}
.fbar span{display:block;height:100%;background:var(--line)}
.risk{background:var(--surface);border-radius:12px;padding:14px 18px;margin-bottom:24px}
.risk .rt{font-weight:600;font-size:14px;margin-bottom:6px}
.risk ul{margin:0;padding-left:18px;font-size:13px}
.risk li{margin:4px 0}
@media(max-width:680px){.kpis,.vers{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:#fff}.wrap{max-width:none;padding:0}.card,.kpi,.light{break-inside:avoid}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def _pct(v: float) -> str:
    return f"{round(v * 100)}%"


def _status(v: float) -> str:
    """Класс светофора по значению надёжности: зелёный/жёлтый/красный."""
    return "ok" if v >= 0.8 else "warn" if v >= 0.4 else "bad"


def _kpis(pass1: float, passk: float, k_max: int, n_tasks: int) -> str:
    gap = max(0, round((pass1 - passk) * 100))
    return (
        '<div class="kpis">'
        f'<div class="kpi"><div class="l">pass¹ — обычный «успех»</div><div class="v">{_pct(pass1)}</div></div>'
        f'<div class="kpi bad"><div class="l">pass^{k_max} — надёжность</div><div class="v">{_pct(passk)}</div></div>'
        f'<div class="kpi"><div class="l">разрыв надёжности</div><div class="v">−{gap} п.п.</div></div>'
        f'<div class="kpi"><div class="l">покрытие</div><div class="v">{n_tasks}×{k_max}</div></div>'
        '</div>')


def _num(n: int) -> str:
    return f"{n:,}".replace(",", " ")


_FAIL_LABELS = {
    "wrong_outcome": "не довёл задачу до нужного состояния",
    "no_action": "не предпринял действий",
    "tool_error": "ошибки при вызове инструментов",
    "judge_fail": "не достиг цели (по оценке судьи)",
    "exception": "сбои выполнения",
    "unknown": "прочее",
}


def _verdict_label(passk: float) -> tuple[str, str]:
    if passk >= 0.8:
        return "надёжен", "ok"
    if passk >= 0.5:
        return "умеренно надёжен", "warn"
    return "ненадёжен", "bad"


def _exec_summary(summary: dict[str, Any], pass1: float, passk: float, k_max: int, gap: int) -> str:
    """Авто-вывод человеческим языком: одна-две фразы для руководства."""
    word, cls = _verdict_label(passk)
    fc = summary.get("failure_classes", {})
    top = max(fc.items(), key=lambda kv: kv[1])[0] if fc else ""
    tail = f" Главная причина провалов — {_FAIL_LABELS.get(top, top)}." if top else ""
    return (f'<div class="summary {cls}"><b>Вывод:</b> агент <b>{word}</b>. '
            f'Обычный успех (pass¹) — {_pct(pass1)}, но повторяемость во всех {k_max} попытках '
            f'(pass^{k_max}) — лишь {_pct(passk)} (разрыв −{gap} п.п.).{tail}</div>')


def _cost_cards(cost: dict[str, Any]) -> str:
    return ('<div class="kpis">'
            f'<div class="kpi"><div class="l">LLM-вызовов</div><div class="v">{_num(cost.get("llm_calls", 0))}</div></div>'
            f'<div class="kpi"><div class="l">токенов всего</div><div class="v">{_num(cost.get("tokens", 0))}</div></div>'
            f'<div class="kpi"><div class="l">ср. токенов/прогон</div><div class="v">{_num(cost.get("avg_tokens_per_run", 0))}</div></div>'
            f'<div class="kpi"><div class="l">ср. задержка</div><div class="v">{cost.get("avg_latency_s", 0)} с</div></div>'
            '</div>')


def _failure_panel(fc: dict[str, int]) -> str:
    if not fc:
        return '<p style="font-size:13px;color:var(--muted);margin:0">Провалов нет.</p>'
    total = sum(fc.values()) or 1
    rows = []
    for cls, n in sorted(fc.items(), key=lambda kv: -kv[1]):
        width = round(n / total * 100)
        rows.append(f'<div class="frow"><span class="fl">{_FAIL_LABELS.get(cls, cls)}</span>'
                    f'<span class="fbar"><span style="width:{width}%"></span></span>'
                    f'<span class="fn">{n}</span></div>')
    return "".join(rows)


def _risk_panel() -> str:
    return ('<div class="risk"><div class="rt">Почему надёжность критична для госуслуг</div><ul>'
            '<li>Ненадёжное действие — это неоплаченная квитанция, незаписанный ребёнок, неполученная '
            'справка: поток жалоб и повторных обращений.</li>'
            '<li>Средний успех маскирует «иногда срабатывает». Для госуслуги важно, чтобы услуга '
            'проходила <b>каждый раз</b>, иначе доверие к сервису падает.</li>'
            '<li>pass^k измеряет именно повторяемость — поэтому планка приёмки 2.0 строится на нём, '
            'а не на среднем успехе.</li></ul></div>')


def _svg_passk(curve: dict[int, float], ci: dict[int, list[float]]) -> str:
    """Линейный SVG-график кривой pass^k с полосой 95% доверительного интервала."""
    ks = sorted(curve)
    w, h, pad = 640, 220, 38
    x0, x1, y0, y1 = pad + 14, w - pad, 16, h - pad
    span = max(1, len(ks) - 1)
    xs = [x0 + (x1 - x0) * (i / span) for i in range(len(ks))]

    def py(v: float) -> float:
        return y1 - (y1 - y0) * v

    grid = []
    for g in (0, 25, 50, 75, 100):
        y = py(g / 100)
        grid.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="grid"/>')
        grid.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" class="ax" text-anchor="end">{g}%</text>')
    bounds = [ci.get(k, [curve[k], curve[k]]) for k in ks]
    top = " ".join(f"{x:.1f},{py(b[1]):.1f}" for x, b in zip(xs, bounds))
    bot = " ".join(f"{x:.1f},{py(b[0]):.1f}" for x, b in zip(reversed(xs), reversed(bounds)))
    band = f'<polygon points="{top} {bot}" class="ciband"/>'
    poly = " ".join(f"{x:.1f},{py(curve[k]):.1f}" for x, k in zip(xs, ks))
    marks = []
    for x, k in zip(xs, ks):
        y = py(curve[k])
        marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="dot"/>')
        marks.append(f'<text x="{x:.1f}" y="{y - 10:.1f}" class="val" text-anchor="middle">{_pct(curve[k])}</text>')
        marks.append(f'<text x="{x:.1f}" y="{y1 + 18:.1f}" class="ax" text-anchor="middle">k={k}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" '
            f'aria-label="Кривая надёжности pass^k с доверительным интервалом">'
            + band + f'<polyline points="{poly}" class="line"/>' + "".join(grid) + "".join(marks) + "</svg>")


def _svg_bars(buckets: dict[str, Any], k_max: int) -> str:
    """Сгруппированные SVG-столбики pass¹ vs pass^k_max по категориям (типы задач)."""
    items = list(buckets.items())
    if not items:
        return ""
    w, h, pad = 640, 210, 40
    x0, x1, y1, top = pad, w - pad, h - pad, 16
    group = (x1 - x0) / len(items)
    bw = min(48.0, group / 3)
    parts = []
    for g in (0, 50, 100):
        y = y1 - (y1 - top) * g / 100
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" class="ax" text-anchor="end">{g}%</text>')
    for i, (label, v) in enumerate(items):
        cx = x0 + group * (i + 0.5)
        pairs = ((v.get("pass^1", 0.0), "b1", cx - bw - 2), (v.get(f"pass^{k_max}", 0.0), "b2", cx + 2))
        for val, cls, bx in pairs:
            by = y1 - (y1 - top) * val
            parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{y1 - by:.1f}" rx="3" class="{cls}"/>')
            parts.append(f'<text x="{bx + bw / 2:.1f}" y="{by - 6:.1f}" class="val" text-anchor="middle">{_pct(val)}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{y1 + 18:.1f}" class="ax" text-anchor="middle">{label}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="pass по типам задач">'
            + "".join(parts) + "</svg>")


def _lights(by_domain: dict[str, Any], k_max: int) -> str:
    out = []
    for dom, v in by_domain.items():
        pk = v.get(f"pass^{k_max}", 0.0)
        out.append(f'<div class="light {_status(pk)}"><div class="n">{dom}</div>'
                   f'<div class="p">pass^{k_max} {_pct(pk)}</div></div>')
    return "".join(out)


def _version_panel(agent_name: str, passk: float, k_max: int) -> str:
    """Панель «готовность по версиям»: подсвечивает текущего агента, остальные — заглушки/планка."""
    name = agent_name.lower()
    cards = [("gov1", "GovTech 1.0", "baseline · классификаторы"),
             ("reference", "Референс · GPT-5.5", "агентный baseline"),
             ("gov2", "GovTech 2.0", "A2A · приёмочная планка")]
    out = []
    for key, title, desc in cards:
        hi = key in name
        if hi:
            badge = f'<span class="badge hi">pass^{k_max} {_pct(passk)}</span>'
        elif key == "gov2":
            badge = '<span class="badge">цель: pass^k выше</span>'
        else:
            badge = '<span class="badge">будет измерено</span>'
        cls = "vcard hi" if hi else "vcard"
        out.append(f'<div class="{cls}"><div class="t">{title}</div><div class="d">{desc}</div>{badge}</div>')
    return "".join(out)


def _task_table(per_task: dict[str, Any], k_max: int) -> str:
    rows = []
    for tid, v in per_task.items():
        pk = v.get(f"pass^{k_max}", 0.0)
        rows.append(f'<tr><td>{tid}</td><td>{v["successes"]}/{v["runs"]}</td>'
                    f'<td>{_pct(v.get("pass^1", 0.0))}</td>'
                    f'<td><span class="tag {_status(pk)}">{_pct(pk)}</span></td></tr>')
    return ('<table><thead><tr><th>Задача</th><th>Успехов</th><th>pass¹</th>'
            f'<th>pass^{k_max}</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>')


def write_html(summary: dict[str, Any], agent_name: str, path: str) -> None:
    """Собирает executive-дашборд (HTML+inline-SVG) из summary и пишет в path."""
    k_max = summary["k_max"]
    curve = {int(k): v for k, v in summary["passk_curve"].items()}
    ci = {int(k): v for k, v in summary.get("passk_ci", {}).items()}
    pass1 = curve.get(1, 0.0)
    passk = curve.get(k_max, 0.0)
    gap = max(0, round((pass1 - passk) * 100))
    n_tasks = summary["n_tasks"]
    runs_pt = summary.get("runs_per_task", "?")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    body = (
        f'<h1>RuServiceBench — отчёт для руководства</h1>'
        f'<p class="sub">Агент: {agent_name} · задач: {n_tasks} · прогонов на задачу: n={runs_pt} · '
        f'кривая до k={k_max} · {ts}</p>'
        f'{_exec_summary(summary, pass1, passk, k_max, gap)}'
        f'{_kpis(pass1, passk, k_max, n_tasks)}'
        f'<p class="sec">Надёжность по числу попыток pass^k (полоса — 95% доверит. интервал)</p>'
        f'<div class="card">{_svg_passk(curve, ci)}</div>'
        f'<p class="sec">По типам задач: обычный успех (pass¹) против надёжности (pass^{k_max})</p>'
        f'<div class="legend"><span><i style="background:var(--b1)"></i>pass¹</span>'
        f'<span><i style="background:var(--b2)"></i>pass^{k_max}</span></div>'
        f'<div class="card">{_svg_bars(summary["by_type"], k_max)}</div>'
        f'<p class="sec">Надёжность по доменам (pass^{k_max})</p>'
        f'<div class="lights">{_lights(summary["by_domain"], k_max)}</div>'
        f'<p class="sec" style="margin-top:24px">Почему агент сыпется</p>'
        f'<div class="card">{_failure_panel(summary.get("failure_classes", {}))}</div>'
        f'<p class="sec">Стоимость и скорость</p>'
        f'{_cost_cards(summary.get("cost", {}))}'
        f'<p class="sec" style="margin-top:24px">Готовность по версиям</p>'
        f'<div class="vers">{_version_panel(agent_name, passk, k_max)}</div>'
        f'<p class="sec" style="margin-top:24px">Цена ошибки</p>'
        f'{_risk_panel()}'
        f'<p class="sec">По задачам</p>'
        f'{_task_table(summary["per_task"], k_max)}'
        '<p class="note">Граница: офлайн-харнесс доказывает корректность, оркестрацию и проактивность '
        'на сценариях. Боевой A/B в проде — отдельный трек прод-телеметрии.</p>')

    html = (f'<!DOCTYPE html>\n<html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>RuServiceBench — {agent_name}</title><style>{_CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>\n')
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
