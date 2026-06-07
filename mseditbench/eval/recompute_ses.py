"""Re-compute SES on existing eval results by adding the IDdrift signal.

Why a separate script: when SES was first computed, `run_eval.py:97` hard-coded
`id_drift=None`, so SES was effectively `1 - OffTarget`. After we wired
IDdrift (face detection + cosine drift) on 2026-05-25, the existing eval
JSONs still hold the broken SES. This script:

  1. Reads every {sid}_k{k}.eval.json in --output_dir
  2. Skips entries whose edit type intentionally changes the actor set
  3. For all others, computes IDdrift (largest face per shot, source vs edit,
     mean cosine distance) using InsightFace
  4. Updates `id_drift`, recomputes `ses = 1 - max(IDdrift, off_target)`
  5. Re-aggregates {sid}.agg.json and aggregate.json

CSV / DINO / CLIP / VLM / SAM-3 / pyiqa results are untouched.

CLI:
    python -m mseditbench.eval.recompute_ses \
        --output_dir runs/eval_seedance_v2v_v2_10s_v3/T2 \
        --prompts_json runs/edit_prompts_v2_10s/T2.json \
        --videos_root data/source_videos_10s/videos
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import numpy as np
from tqdm import tqdm

from mseditbench import metrics as M
from mseditbench.metrics import backends as B
from mseditbench.eval.run_eval import (
    _compute_id_drift, _is_identity_changing_edit,
)


RUN_EVAL_METRICS = ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "ses")


def _aggregate_per_prompt(eval_jsons: list[dict]) -> dict:
    sid = eval_jsons[0]["sample_id"]
    task_id = eval_jsons[0]["task_id"]
    agg = {"sample_id": sid, "task_id": task_id, "k_count": len(eval_jsons)}
    for metric in RUN_EVAL_METRICS:
        xs = [r[metric] for r in eval_jsons if r.get(metric) is not None]
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
    return agg


def _aggregate_task(per_sample_aggs, baseline, snapshot_id, k_samples):
    if not per_sample_aggs:
        return {}
    agg = {
        "baseline": baseline,
        "snapshot_id": snapshot_id,
        "task_id": per_sample_aggs[0]["task_id"],
        "n_prompts": len(per_sample_aggs),
        "k_samples": k_samples,
    }
    for metric in RUN_EVAL_METRICS:
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
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output_dir", required=True,
                    help="Per-task eval output dir (contains *_k*.eval.json)")
    ap.add_argument("--prompts_json", required=True)
    ap.add_argument("--videos_root", required=True)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--max_frames_per_shot", type=int, default=6)
    ap.add_argument("--num_shards", type=int, default=1)
    ap.add_argument("--shard_id", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.output_dir)
    eval_files = sorted(out.glob("*.eval.json"))
    if not eval_files:
        print(f"no *.eval.json in {out}")
        return

    prompts = json.load(open(args.prompts_json))
    by_sid = {p["sample_id"]: p for p in prompts}

    if args.num_shards > 1:
        eval_files = eval_files[args.shard_id::args.num_shards]

    fb = B.get_face("insightface")
    print(f"Loaded InsightFace; processing {len(eval_files)} eval files")

    n_updated = 0
    n_skipped_ic = 0   # identity-changing prompt -> leave SES alone
    n_skipped_no_face = 0
    for ef in tqdm(eval_files, desc=f"ses shard {args.shard_id}"):
        d = json.load(open(ef))
        sid = d["sample_id"]
        sample = by_sid.get(sid)
        if not sample:
            continue
        if _is_identity_changing_edit(sample):
            n_skipped_ic += 1
            continue
        src_path = os.path.join(args.videos_root, sample["source_video"])
        edited = d.get("edited_video_path")
        if not edited or not os.path.exists(edited) or not os.path.exists(src_path):
            continue
        try:
            src_frames = M.per_shot_frames(src_path, sample["shots"],
                                           stride=args.stride,
                                           max_frames=args.max_frames_per_shot)
            edt_frames = M.per_shot_frames(edited, sample["shots"],
                                           stride=args.stride,
                                           max_frames=args.max_frames_per_shot)
        except Exception as e:
            print(f"[err] {ef.name}: {e}")
            continue

        id_drift = _compute_id_drift(src_frames, edt_frames, fb)
        if id_drift is None:
            n_skipped_no_face += 1
            # Leave the file as-is (id_drift stays None, ses stays = 1-OffTarget)
            continue

        # Recompute SES. ses() takes the max of (id_drift, off_target_mean).
        off_target = float(d.get("off_target") or 0.0)
        new_ses = M.ses(id_drift=id_drift, off_target_mean=off_target)
        d["id_drift"] = id_drift
        d["ses"] = new_ses["ses"]
        with open(ef, "w") as f:
            json.dump(d, f, indent=2)
        n_updated += 1

    print(f"Updated SES in {n_updated}/{len(eval_files)} files "
          f"(skipped: {n_skipped_ic} identity-changing, "
          f"{n_skipped_no_face} no-face)")

    # Re-aggregate (idempotent — always re-derive from .eval.json on disk)
    if args.num_shards > 1 and args.shard_id != 0:
        return

    by_sid_evals = {}
    for ef in sorted(out.glob("*.eval.json")):
        d = json.load(open(ef))
        by_sid_evals.setdefault(d["sample_id"], []).append(d)

    per_sample_aggs = []
    for sid, rs in by_sid_evals.items():
        ag = _aggregate_per_prompt(rs)
        with open(out / f"{sid}.agg.json", "w") as f:
            json.dump(ag, f, indent=2)
        per_sample_aggs.append(ag)

    if per_sample_aggs:
        existing = list(out.glob("aggregate*.json"))
        baseline = snapshot_id = None
        k_samples = per_sample_aggs[0].get("k_count")
        if existing:
            try:
                first = json.load(open(existing[0]))
                baseline = first.get("baseline")
                snapshot_id = first.get("snapshot_id")
                k_samples = first.get("k_samples", k_samples)
            except Exception:
                pass
        ag = _aggregate_task(per_sample_aggs, baseline, snapshot_id, k_samples)
        with open(out / "aggregate.json", "w") as f:
            json.dump(ag, f, indent=2)
        print(f"\nRe-aggregated → {out / 'aggregate.json'}")
        for m in RUN_EVAL_METRICS:
            mn = ag.get(f"{m}_mean")
            sd = ag.get(f"{m}_std")
            mn_s = f"{mn:.3f}" if isinstance(mn, float) else "—"
            sd_s = f"±{sd:.3f}" if isinstance(sd, float) else ""
            print(f"  {m.upper():6} {mn_s} {sd_s}")


if __name__ == "__main__":
    main()
