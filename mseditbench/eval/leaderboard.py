"""Aggregate eval results across (task, baseline) into a leaderboard CSV.

CLI:
    python -m mseditbench.eval.leaderboard \
        --eval_root runs/eval_aleph_mock \
        --output_csv runs/eval_aleph_mock/leaderboard.csv

Walks <eval_root>/<task>/aggregate.json files written by run_eval.py and
emits one CSV row per (task, baseline) tuple.
"""

from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

LEADERBOARD_COLUMNS = [
    "snapshot_id", "task_id", "baseline", "n",
    "psq_mean", "ee_v3_mean", "nep_mean", "csep_v3_mean", "usp_mean", "tac_mean",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval_root", required=True)
    ap.add_argument("--output_csv", required=True)
    args = ap.parse_args()

    rows = []
    for agg_path in sorted(Path(args.eval_root).rglob("aggregate.json")):
        d = json.load(open(agg_path))
        rows.append({k: d.get(k) for k in LEADERBOARD_COLUMNS})

    with open(args.output_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEADERBOARD_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} leaderboard rows -> {args.output_csv}")


if __name__ == "__main__":
    main()
