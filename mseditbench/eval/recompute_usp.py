"""Re-compute USP/TAC on existing eval result directories.

USP replaces the old SES metric. It is DINOv2 similarity on source shots that
the prompt did not ask to edit. This script updates existing ``*.eval.json``
files in place, then re-aggregates prompt-level and task-level JSONs.

Optionally pass ``--backend_shot omnishotcut`` to recompute TAC as well.
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


RUN_EVAL_METRICS = ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac")


def _aggregate_per_prompt(eval_jsons: list[dict]) -> dict:
    sid = eval_jsons[0]["sample_id"]
    task_id = eval_jsons[0]["task_id"]
    agg = {"sample_id": sid, "task_id": task_id, "k_count": len(eval_jsons)}
    for metric in RUN_EVAL_METRICS:
        xs = [r[metric] for r in eval_jsons if r.get(metric) is not None]
        if xs:
            mu = sum(xs) / len(xs)
            agg[f"{metric}_mean"] = mu
            agg[f"{metric}_std"] = (
                float(np.std(xs, ddof=1)) if len(xs) >= 2 else None
            )
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
            agg[f"{metric}_std"] = (
                float(np.std(xs, ddof=1)) if len(xs) >= 2 else None
            )
        else:
            agg[f"{metric}_mean"] = None
            agg[f"{metric}_std"] = None
    return agg


def _expected_order_for_tac(sample: dict) -> list[int] | None:
    edit = sample.get("edit") or {}
    if edit.get("task_id") != "T5":
        return None
    order = (edit.get("extra") or {}).get("new_order")
    if not isinstance(order, list):
        return None
    try:
        return [int(x) for x in order]
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output_dir", required=True,
                    help="Per-task eval output dir containing *_k*.eval.json")
    ap.add_argument("--prompts_json", required=True)
    ap.add_argument("--videos_root", required=True)
    ap.add_argument("--backend_dino", default="v2s", choices=["mock", "v2s", "v2b"])
    ap.add_argument("--backend_shot", default="none", choices=["none", "omnishotcut"])
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

    dino = B.get_dino(args.backend_dino)
    print(f"Loaded DINO backend {args.backend_dino}; processing {len(eval_files)} eval files")

    n_updated = 0
    for ef in tqdm(eval_files, desc=f"usp shard {args.shard_id}"):
        d = json.load(open(ef))
        sample = by_sid.get(d["sample_id"])
        if not sample:
            continue
        src_path = os.path.join(args.videos_root, sample["source_video"])
        edited = d.get("edited_video_path")
        if not edited or not os.path.exists(edited) or not os.path.exists(src_path):
            continue
        try:
            src_frames = M.per_shot_frames(
                src_path, sample["shots"],
                stride=args.stride,
                max_frames=args.max_frames_per_shot,
            )
            edt_frames = M.per_shot_frames(
                edited, sample["shots"],
                stride=args.stride,
                max_frames=args.max_frames_per_shot,
            )
        except Exception as e:
            print(f"[err] {ef.name}: {e}")
            continue

        applicable = sample["edit"].get("applicable_shots", [s["shot_id"] for s in sample["shots"]])
        unedited = [s["shot_id"] for s in sample["shots"] if s["shot_id"] not in applicable]
        usp_r = M.usp(src_frames, edt_frames, unedited, dino_backend=dino)
        d["usp"] = usp_r["usp"]
        extra = d.setdefault("extra", {})
        extra["usp_per_shot"] = usp_r["per_shot_usp"]
        extra["usp_n_scored"] = usp_r.get("n_scored")
        extra["usp_n_unedited"] = usp_r.get("n_unedited")
        extra["usp_n_missing"] = usp_r.get("n_missing")
        extra["usp_reason"] = usp_r.get("reason")

        if args.backend_shot == "omnishotcut":
            try:
                tac_r = M.temporal_anchor_consistency(
                    sample["shots"],
                    edited,
                    source_video_path=src_path,
                    expected_order=_expected_order_for_tac(sample),
                )
            except Exception as e:
                tac_r = {"tac": None, "reason": f"shot detection failed: {type(e).__name__}: {e}"}
            d["tac"] = tac_r.get("tac")
            extra["tac_per_shot"] = tac_r.get("per_shot_tac") or {}
            extra["tac_shot_count_match"] = tac_r.get("shot_count_match")
            extra["tac_expected_count"] = tac_r.get("expected_count")
            extra["tac_edited_count"] = tac_r.get("edited_count")
            extra["tac_mean_anchor_error_sec"] = tac_r.get("mean_anchor_error_sec")
            extra["tac_reason"] = tac_r.get("reason")

        d.pop("ses", None)
        d.pop("off_target", None)
        d.pop("id_drift", None)
        with open(ef, "w") as f:
            json.dump(d, f, indent=2)
        n_updated += 1

    print(f"Updated USP in {n_updated}/{len(eval_files)} files")

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
        print(f"\nRe-aggregated -> {out / 'aggregate.json'}")
        for m in RUN_EVAL_METRICS:
            mn = ag.get(f"{m}_mean")
            sd = ag.get(f"{m}_std")
            mn_s = f"{mn:.3f}" if isinstance(mn, float) else "-"
            sd_s = f"±{sd:.3f}" if isinstance(sd, float) else ""
            print(f"  {m.upper():6} {mn_s} {sd_s}")


if __name__ == "__main__":
    main()
