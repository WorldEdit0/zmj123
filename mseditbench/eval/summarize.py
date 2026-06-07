"""Summarize MSEdit-Bench aggregate.json files.

Reads standard run_eval aggregates from one eval root, writes a CSV + Markdown
table, and prints a compact final score.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


METRICS = [
    "psq_mean",
    "ee_v3_mean",
    "nep_mean",
    "csep_v3_mean",
    "usp_mean",
    "tac_mean",
]

# 中文注释：task_score 是这些 headline 指标的简单平均。
# 如果某个指标为 None，会在 _task_score 中被跳过，而不是按 0 处理。
DEFAULT_PRIMARY = ["psq_mean", "ee_v3_mean", "nep_mean", "csep_v3_mean", "usp_mean", "tac_mean"]


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4f}"
    if v is None:
        return ""
    return str(v)


def _task_score(row: dict) -> float | None:
    # 中文注释：task_score 是为了快速看一个任务的单数总分；
    # 正式分析仍建议同时查看每个 metric 的列，因为它们含义不同。
    task = row.get("task_id")
    keys = DEFAULT_PRIMARY
    vals = [row.get(k) for k in keys if isinstance(row.get(k), (int, float))]
    if not vals:
        return None
    return float(mean(vals))


def _read_rows(eval_root: Path) -> list[dict]:
    rows = []
    for agg_path in sorted(eval_root.rglob("aggregate.json")):
        # 中文注释：summarize 只认任务级 aggregate.json，
        # 不读取单个 {sid}_k*.eval.json。
        data = json.load(open(agg_path))
        task_id = data.get("task_id") or agg_path.parent.name
        row = {
            "task_id": task_id,
            "baseline": data.get("baseline"),
            "snapshot_id": data.get("snapshot_id"),
            "n_prompts": data.get("n_prompts"),
            "k_samples": data.get("k_samples"),
            "aggregate_path": str(agg_path),
        }
        for metric in METRICS:
            row[metric] = data.get(metric)
        row["task_score"] = _task_score(row)
        rows.append(row)
    rows.sort(key=lambda r: str(r.get("task_id") or ""))
    return rows


def _write_csv(rows: list[dict], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "task_id", "baseline", "snapshot_id", "n_prompts", "k_samples",
        *METRICS, "task_score", "aggregate_path",
    ]
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(rows: list[dict], output_md: Path) -> None:
    output_md.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "task_id", "n_prompts", "k_samples", "psq_mean", "ee_v3_mean",
        "nep_mean", "csep_v3_mean", "usp_mean", "tac_mean",
        "task_score",
    ]
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_fmt(row.get(c)) for c in cols) + " |")
    scores = [r["task_score"] for r in rows if isinstance(r.get("task_score"), float)]
    lines.append("")
    lines.append(f"Overall score: {_fmt(float(mean(scores)) if scores else None)}")
    output_md.write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval_root", required=True)
    ap.add_argument("--output_csv", default=None)
    ap.add_argument("--output_md", default=None)
    args = ap.parse_args()

    eval_root = Path(args.eval_root)
    rows = _read_rows(eval_root)
    if not rows:
        print(f"No aggregate.json files found under {eval_root}")
        return

    output_csv = Path(args.output_csv) if args.output_csv else eval_root / "summary.csv"
    output_md = Path(args.output_md) if args.output_md else eval_root / "summary.md"
    _write_csv(rows, output_csv)
    _write_md(rows, output_md)

    print(f"Wrote {len(rows)} task rows")
    print(f"CSV: {output_csv}")
    print(f"Markdown: {output_md}")
    print("")
    print("task   n   K   PSQ    EE_v3  NEP    CSEP   USP    TAC    task_score")
    for row in rows:
        print(
            f"{str(row.get('task_id')):5s} "
            f"{_fmt(row.get('n_prompts')):3s} "
            f"{_fmt(row.get('k_samples')):3s} "
            f"{_fmt(row.get('psq_mean')):6s} "
            f"{_fmt(row.get('ee_v3_mean')):6s} "
            f"{_fmt(row.get('nep_mean')):6s} "
            f"{_fmt(row.get('csep_v3_mean')):6s} "
            f"{_fmt(row.get('usp_mean')):6s} "
            f"{_fmt(row.get('tac_mean')):6s} "
            f"{_fmt(row.get('task_score')):6s}"
        )
    scores = [r["task_score"] for r in rows if isinstance(r.get("task_score"), float)]
    print("")
    print(f"Overall score: {_fmt(float(mean(scores)) if scores else None)}")


if __name__ == "__main__":
    main()
