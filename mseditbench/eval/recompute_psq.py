"""Re-compute PSQ on an already-eval'd output_dir using a real backend.

Why a separate script: PSQ is independent of source frames / target phrase /
VLM votes — it only depends on edit-video frames and the chosen image-quality
model. So we can fix the (previously mock) PSQ in place without re-doing the
expensive DINO / VLM / shot-detection passes.

Reads every {sid}_k{k}.eval.json in --output_dir, recomputes psq from the
edit video pointed to by `edited_video_path`, rewrites the eval json, then
re-aggregates {sid}.agg.json and aggregate.json.

CLI:
    python -m mseditbench.eval.recompute_psq \
        --output_dir runs/eval_seedance_v2v/T1 \
        --backend_psq pyiqa
"""

from __future__ import annotations
import argparse
import glob
import json
import os
from pathlib import Path

from tqdm import tqdm

from mseditbench import metrics as M
from mseditbench.metrics import backends as B


def _aggregate_per_prompt(eval_jsons: list[dict]) -> dict:
    sid = eval_jsons[0]["sample_id"]
    task_id = eval_jsons[0]["task_id"]
    agg = {"sample_id": sid, "task_id": task_id, "k_count": len(eval_jsons)}
    for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
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


def _aggregate_task(per_sample_aggs: list[dict], baseline: str, snapshot_id: str, k_samples: int) -> dict:
    if not per_sample_aggs:
        return {}
    agg = {
        "baseline": baseline,
        "snapshot_id": snapshot_id,
        "task_id": per_sample_aggs[0]["task_id"],
        "n_prompts": len(per_sample_aggs),
        "k_samples": k_samples,
    }
    for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
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
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--backend_psq", default="pyiqa", choices=["mock", "pyiqa"])
    ap.add_argument("--prompts_json", required=True,
                    help="Edit prompts JSON (for shot boundaries — needed to read per-shot frames)")
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--max_frames_per_shot", type=int, default=6)
    ap.add_argument("--num_shards", type=int, default=1)
    ap.add_argument("--shard_id", type=int, default=0)
    args = ap.parse_args()

    out = Path(args.output_dir)
    eval_files = sorted(out.glob("*.eval.json"))
    if not eval_files:
        print(f"No *.eval.json in {out}")
        return

    # Sample → list of shots, for frame extraction
    prompts = json.load(open(args.prompts_json))
    shots_by_sid = {s["sample_id"]: s["shots"] for s in prompts}

    # Shard for multi-GPU parallel
    if args.num_shards > 1:
        eval_files = eval_files[args.shard_id::args.num_shards]

    psq_fn = B.get_psq(args.backend_psq)
    print(f"Loaded {args.backend_psq} PSQ backend; processing {len(eval_files)} files")

    n_updated = 0
    for ef in tqdm(eval_files, desc=f"psq shard {args.shard_id}"):
        d = json.load(open(ef))
        sid = d["sample_id"]
        edited = d.get("edited_video_path")
        if not edited or not os.path.exists(edited):
            continue
        shots = shots_by_sid.get(sid)
        if not shots:
            continue
        try:
            edt_frames = M.per_shot_frames(edited, shots,
                                           stride=args.stride,
                                           max_frames=args.max_frames_per_shot)
            psq_r = M.psq(edt_frames, musiq_fn=psq_fn)
        except Exception as e:
            print(f"[ERR] {ef.name}: {e}")
            continue
        d["psq"] = psq_r["psq"]
        with open(ef, "w") as f:
            json.dump(d, f, indent=2)
        n_updated += 1

    print(f"Updated PSQ in {n_updated}/{len(eval_files)} eval files")

    # Re-aggregate (only when running shard_id 0 as a final step would be nicer,
    # but sharding the recompute means we must re-aggregate after all shards).
    # We always re-aggregate from whatever's on disk now — idempotent.
    if args.num_shards > 1 and args.shard_id != 0:
        return

    # Group {sid}_k{k}.eval.json into per-sid lists
    by_sid = {}
    for ef in sorted(out.glob("*.eval.json")):
        d = json.load(open(ef))
        by_sid.setdefault(d["sample_id"], []).append(d)

    per_sample_aggs = []
    for sid, rs in by_sid.items():
        ag = _aggregate_per_prompt(rs)
        with open(out / f"{sid}.agg.json", "w") as f:
            json.dump(ag, f, indent=2)
        per_sample_aggs.append(ag)

    # Task-level
    if per_sample_aggs:
        # Pull baseline / snapshot / K from any existing aggregate
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
        for m in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
            mn = ag.get(f"{m}_mean"); sd = ag.get(f"{m}_std")
            mn_s = f"{mn:.3f}" if isinstance(mn, float) else "—"
            sd_s = f"±{sd:.3f}" if isinstance(sd, float) else ""
            print(f"  {m.upper():6} {mn_s} {sd_s}")


if __name__ == "__main__":
    main()
