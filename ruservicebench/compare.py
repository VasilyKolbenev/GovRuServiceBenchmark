"""Сравнительный отчёт по нескольким агентам (GovTech 1.0 / Референс / GovTech 2.0).
Каждый прогон сохраняет свою сводку в out/agents/<name>.json; отчёт читает их все
и рендерит out/compare.md + out/compare.html (надёжность pass^k по версиям)."""
from __future__ import annotations
import glob
import json
import os
from typing import Any
from .dashboard import _CSS, _pct, _num


def _safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name)


def save_agent_summary(summary: dict[str, Any], agent_name: str, out_dir: str) -> None:
    """Сохраняет сводку агента для последующего сравнения (накапливается между прогонами)."""
    d = os.path.join(out_dir, "agents")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, _safe_name(agent_name) + ".json"), "w", encoding="utf-8") as f:
        json.dump({"agent": agent_name, "summary": summary}, f, ensure_ascii=False, indent=2)


def _load(out_dir: str) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(glob.glob(os.path.join(out_dir, "agents", "*.json"))):
        with open(path, encoding="utf-8") as f:
            rows.append(json.load(f))
    return rows


def _rows(out_dir: str) -> tuple[list[dict[str, Any]], int]:
    raw = _load(out_dir)
    if not raw:
        return [], 0
    k_common = min(int(r["summary"]["k_max"]) for r in raw)
    agents = []
    for r in raw:
        s = r["summary"]
        curve = {int(k): v for k, v in s["passk_curve"].items()}
        p1, pk = curve.get(1, 0.0), curve.get(k_common, 0.0)
        agents.append({"name": r["agent"], "p1": p1, "pk": pk,
                       "gap": max(0, round((p1 - pk) * 100)), "n_tasks": s.get("n_tasks", 0),
                       "runs": s.get("runs_per_task", "?"),
                       "tokens": s.get("cost", {}).get("avg_tokens_per_run", 0)})
    agents.sort(key=lambda a: a["pk"], reverse=True)
    return agents, k_common


def _svg_compare_bars(agents: list[dict[str, Any]]) -> str:
    w, h, pad = 640, 240, 44
    x0, x1, y1, top = pad, w - pad, h - pad, 16
    group = (x1 - x0) / max(1, len(agents))
    bw = min(40.0, group / 3)
    parts = []
    for g in (0, 50, 100):
        y = y1 - (y1 - top) * g / 100
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" class="ax" text-anchor="end">{g}%</text>')
    for i, a in enumerate(agents):
        cx = x0 + group * (i + 0.5)
        for val, cls, bx in ((a["p1"], "b1", cx - bw - 2), (a["pk"], "b2", cx + 2)):
            by = y1 - (y1 - top) * val
            parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{y1 - by:.1f}" rx="3" class="{cls}"/>')
            parts.append(f'<text x="{bx + bw / 2:.1f}" y="{by - 6:.1f}" class="val" text-anchor="middle">{_pct(val)}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{y1 + 18:.1f}" class="ax" text-anchor="middle">{a["name"][:20]}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" role="img" aria-label="Сравнение pass по агентам">'
            + "".join(parts) + "</svg>")


def write_comparison(out_dir: str) -> str | None:
    """Рендерит сравнение всех накопленных агентов. Возвращает путь к HTML или None, если нет данных."""
    agents, k = _rows(out_dir)
    if not agents:
        return None

    md = [f"# RuServiceBench — сравнение агентов (pass^{k})\n",
          f"| Агент | pass¹ | pass^{k} | разрыв | задач | ср. токенов/прогон |",
          "|---|---|---|---|---|---|"]
    for a in agents:
        md.append(f"| {a['name']} | {_pct(a['p1'])} | {_pct(a['pk'])} | −{a['gap']} п.п. | "
                  f"{a['n_tasks']} | {_num(a['tokens'])} |")
    with open(os.path.join(out_dir, "compare.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    table_rows = "".join(
        f'<tr><td>{a["name"]}</td><td>{_pct(a["p1"])}</td><td><b>{_pct(a["pk"])}</b></td>'
        f'<td>−{a["gap"]} п.п.</td><td>{a["n_tasks"]}</td><td>{_num(a["tokens"])}</td></tr>' for a in agents)
    body = (
        f'<h1>RuServiceBench — сравнение агентов</h1>'
        f'<p class="sub">Надёжность pass^{k} по версиям · агентов: {len(agents)}</p>'
        f'<div class="legend"><span><i style="background:var(--b1)"></i>pass¹</span>'
        f'<span><i style="background:var(--b2)"></i>pass^{k}</span></div>'
        f'<div class="card">{_svg_compare_bars(agents)}</div>'
        f'<table><thead><tr><th>Агент</th><th>pass¹</th><th>pass^{k}</th><th>разрыв</th>'
        f'<th>задач</th><th>ток./прогон</th></tr></thead><tbody>{table_rows}</tbody></table>'
        '<p class="note">Цель GovTech 2.0 — обойти 1.0 и закрыть разрыв по надёжности pass^k, '
        'а не только по среднему успеху. Сравнение накапливается между прогонами разных агентов.</p>')
    html = (f'<!DOCTYPE html>\n<html lang="ru"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>RuServiceBench — сравнение</title><style>{_CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>\n')
    path = os.path.join(out_dir, "compare.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
