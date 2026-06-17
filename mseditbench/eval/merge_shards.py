"""Merge per-shard aggregate files and per-sample .agg.json files into a
final aggregate.json.

After running run_eval.py with --num_shards N (one process per GPU), each
shard writes:
    aggregate_s{shard_id}_of_{N}.json   (shard's own task-level aggregate)
    {sample_id}.agg.json                (per-prompt aggregate, no conflict)
    {sample_id}_k{0,1,2}.eval.json      (per-K-sample raw scores)

This script collects ALL .agg.json files in the output dir and produces a
single aggregate.json equivalent to a single-shard run.

CLI:
    python -m mseditbench.eval.merge_shards --output_dir runs/eval_X/T1

中文说明：
    正式多 GPU 评测时，每个 shard 只负责一部分 prompts。每个 prompt
    都会生成一个 {sample_id}.agg.json。最终任务分数不能简单平均各 shard
    的 aggregate，因为每个 shard 可能 prompt 数不同；这里重新读取所有
    prompt-level agg，再按 prompt 等权汇总，保证和单进程跑全任务一致。
"""

from __future__ import annotations
import argparse
import glob
import json
import os
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output_dir", required=True)
    args = ap.parse_args()

    out = Path(args.output_dir)
    per_sample_aggs = []
    for f in sorted(out.glob("*.agg.json")):
        # 中文注释：这是 prompt-level 聚合，已经在 run_eval.py 中把 K 个输出平均过。
        per_sample_aggs.append(json.load(open(f)))

    if not per_sample_aggs:
        print(f"No *.agg.json files in {out}; nothing to merge.")
        return

    # The shard aggregate files have baseline / snapshot_id / task_id we need
    # 中文注释：shard aggregate 只用来拿元信息；真正分数重新从所有 prompt agg 计算。
    shard_aggs = sorted(out.glob("aggregate_s*_of_*.json"))
    if shard_aggs:
        first = json.load(open(shard_aggs[0]))
        baseline = first.get("baseline")
        snapshot_id = first.get("snapshot_id")
        k_samples = first.get("k_samples")
        metrics = first.get("metrics")
    else:
        baseline = snapshot_id = None
        k_samples = per_sample_aggs[0].get("k_count")
        metrics = None

    task_id = per_sample_aggs[0].get("task_id")

    agg = {
        "baseline": baseline,
        "snapshot_id": snapshot_id,
        "task_id": task_id,
        "n_prompts": len(per_sample_aggs),
        "k_samples": k_samples,
    }
    if metrics is not None:
        agg["metrics"] = metrics
    for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
        # 中文注释：None 表示指标不可评估/被任务规则跳过，合并时跳过 None。
        xs = [a[f"{metric}_mean"] for a in per_sample_aggs
              if a.get(f"{metric}_mean") is not None]
        if xs:
            mu = sum(xs) / len(xs)
            agg[f"{metric}_mean"] = mu
            if len(xs) >= 2:
                var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
                agg[f"{metric}_std"] = var ** 0.5
            else:
                agg[f"{metric}_std"] = None
        else:
            agg[f"{metric}_mean"] = None
            agg[f"{metric}_std"] = None

    with open(out / "aggregate.json", "w") as f:
        json.dump(agg, f, indent=2)

    print(f"Merged {len(per_sample_aggs)} per-prompt aggs from {len(shard_aggs)} shards "
          f"→ {out / 'aggregate.json'}")
    print(f"  baseline={baseline} task={task_id} n_prompts={agg['n_prompts']} K={k_samples}")
    for m in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
        mn = agg.get(f"{m}_mean"); sd = agg.get(f"{m}_std")
        mn_s = f"{mn:.3f}" if isinstance(mn, float) else "—"
        sd_s = f"±{sd:.3f}" if isinstance(sd, float) else ""
        print(f"  {m.upper():6} {mn_s} {sd_s}")


if __name__ == "__main__":
    main()
