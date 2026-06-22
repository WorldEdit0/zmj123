from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path
from statistics import mean, stdev
import sys

import numpy as np
from tqdm import tqdm

from api_vlm import ArkVlmJudge
from metric_units import build_vlm_units
from video_io import matched_pair_indices, per_shot_frames


RUN_ROOT = Path(__file__).resolve().parents[1]


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def format_template(template: str, **kwargs) -> str:
    return template.format(**kwargs)


def parse_tasks(value: str) -> list[str]:
    if value.lower() == "all":
        return [f"T{i}" for i in range(1, 10)]
    return [x.strip() for x in value.split(",") if x.strip()]


def discover_models(results_root: Path, models_arg: str | None) -> list[tuple[str, Path]]:
    if models_arg:
        return [(m.strip(), results_root / m.strip()) for m in models_arg.split(",") if m.strip()]
    children = [p for p in sorted(results_root.iterdir()) if p.is_dir()]
    if children:
        return [(p.name, p) for p in children]
    return [(results_root.name, results_root)]


def resolve_edited_video(model_root: Path, task_id: str, sample_id: str, k: int) -> Path | None:
    names = [
        f"{sample_id}_k{k}.mp4",
        f"{sample_id}.mp4",
    ]
    roots = [
        model_root / "videos" / task_id,
        model_root / task_id,
        model_root / "videos",
        model_root,
    ]
    for root in roots:
        for name in names:
            path = root / name
            if path.exists() and path.stat().st_size > 0:
                return path
    return None


def _mean_or_none(values: list[float | None]) -> float | None:
    xs = [float(v) for v in values if v is not None]
    return float(mean(xs)) if xs else None


def _std_or_none(values: list[float | None]) -> float | None:
    xs = [float(v) for v in values if v is not None]
    return float(stdev(xs)) if len(xs) >= 2 else None


def score_ee_unit(
    unit: dict,
    src_frames: dict[int, np.ndarray],
    edt_frames: dict[int, np.ndarray],
    judge: ArkVlmJudge,
    ee_template: str,
    frame_pairs_per_shot: int,
) -> dict:
    edit_request = (unit.get("instruction") or "").strip() or (unit.get("target_phrase") or "").strip()
    prompt = format_template(ee_template, edit_request=edit_request or "the requested edit")
    per_shot = {}
    for shot_id in [int(s) for s in unit.get("applicable_shots") or []]:
        if shot_id not in src_frames or shot_id not in edt_frames:
            continue
        sf = src_frames[shot_id]
        ef = edt_frames[shot_id]
        frame_scores = []
        for si, ei in matched_pair_indices(len(sf), len(ef), frame_pairs_per_shot):
            try:
                r = judge.rate_image_pair(sf[si], ef[ei], prompt)
                score = r["score"] if r["score"] is not None else 0.0
                frame_scores.append({
                    "source_idx": si,
                    "edit_idx": ei,
                    "ee": score,
                    "raw_response": r.get("raw_response"),
                })
            except Exception as exc:  # pragma: no cover - API dependent
                frame_scores.append({
                    "source_idx": si,
                    "edit_idx": ei,
                    "ee": 0.0,
                    "error": f"{type(exc).__name__}: {exc}",
                })
        if frame_scores:
            per_shot[str(shot_id)] = {
                "ee": float(mean([x["ee"] for x in frame_scores])),
                "frames": frame_scores,
            }
    return {
        "unit_id": unit.get("unit_id"),
        "edit_id": unit.get("edit_id"),
        "instruction": edit_request,
        "applicable_shots": unit.get("applicable_shots") or [],
        "ee": _mean_or_none([v["ee"] for v in per_shot.values()]),
        "per_shot": per_shot,
        "prompt": prompt,
    }


def score_csep_unit(
    unit: dict,
    ee_unit: dict,
    edt_frames: dict[int, np.ndarray],
    judge: ArkVlmJudge,
    csep_template: str,
) -> dict:
    applicable = [int(s) for s in unit.get("applicable_shots") or []]
    valid = [s for s in applicable if s in edt_frames and len(edt_frames[s])]
    if len(valid) < 2 or not unit.get("csep_applicable", len(valid) >= 2):
        return {
            "unit_id": unit.get("unit_id"),
            "edit_id": unit.get("edit_id"),
            "csep": None,
            "coverage": None,
            "consistency": None,
            "n_pairs": 0,
            "reason": "<2 applicable shots",
        }

    instruction = (unit.get("instruction") or "").strip() or (unit.get("target_phrase") or "").strip()
    prompt = format_template(csep_template, instruction=instruction or "the requested edit")
    pair_scores = {}
    for a, b in itertools.combinations(sorted(valid), 2):
        try:
            r = judge.rate_pair(edt_frames[a], edt_frames[b], prompt)
            score = r["score"] if r["score"] is not None else 0.0
            pair_scores[f"{a}-{b}"] = {
                "score": score,
                "raw_response": r.get("raw_response"),
                "n_images_a": r.get("n_images_a"),
                "n_images_b": r.get("n_images_b"),
            }
        except Exception as exc:  # pragma: no cover - API dependent
            pair_scores[f"{a}-{b}"] = {
                "score": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            }

    consistency = _mean_or_none([v["score"] for v in pair_scores.values()]) or 0.0
    per_shot_ee = {
        int(k): float(v.get("ee", 0.0))
        for k, v in (ee_unit.get("per_shot") or {}).items()
    }
    coverage = float(mean([per_shot_ee.get(s, 0.0) for s in valid])) if valid else 0.0
    csep = float(math.sqrt(max(0.0, coverage) * max(0.0, consistency)))
    return {
        "unit_id": unit.get("unit_id"),
        "edit_id": unit.get("edit_id"),
        "instruction": instruction,
        "applicable_shots": applicable,
        "csep": csep,
        "coverage": coverage,
        "consistency": consistency,
        "n_pairs": len(pair_scores),
        "pair_scores": pair_scores,
        "prompt": prompt,
    }


def evaluate_sample(
    sample: dict,
    source_video: Path,
    edited_video: Path,
    judge: ArkVlmJudge,
    ee_template: str,
    csep_template: str,
    stride: int,
    max_frames_per_shot: int,
    frame_pairs_per_shot: int,
) -> dict:
    shots = sample.get("shots") or []
    src_frames = per_shot_frames(source_video, shots, stride=stride, max_frames=max_frames_per_shot)
    edt_frames = per_shot_frames(edited_video, shots, stride=stride, max_frames=max_frames_per_shot)
    units, skip_reason = build_vlm_units(sample)
    if skip_reason:
        return {
            "sample_id": sample["sample_id"],
            "task_id": sample["edit"]["task_id"],
            "source_video": str(source_video),
            "edited_video": str(edited_video),
            "ee_v3": None,
            "csep_v3": None,
            "reason": skip_reason,
            "ee_units": [],
            "csep_units": [],
        }

    ee_units = [
        score_ee_unit(unit, src_frames, edt_frames, judge, ee_template, frame_pairs_per_shot)
        for unit in units
    ]
    ee_by_unit = {str(u.get("unit_id")): u for u in ee_units}
    csep_units = [
        score_csep_unit(unit, ee_by_unit.get(str(unit.get("unit_id")), {}), edt_frames, judge, csep_template)
        for unit in units
    ]
    return {
        "sample_id": sample["sample_id"],
        "task_id": sample["edit"]["task_id"],
        "source_video": str(source_video),
        "edited_video": str(edited_video),
        "ee_v3": _mean_or_none([u.get("ee") for u in ee_units]),
        "csep_v3": _mean_or_none([u.get("csep") for u in csep_units]),
        "ee_units": ee_units,
        "csep_units": csep_units,
    }


def write_task_aggregate(out_dir: Path, model: str, task_id: str, rows: list[dict]) -> dict:
    agg = {
        "model": model,
        "task_id": task_id,
        "n_prompts": len(rows),
        "ee_v3_mean": _mean_or_none([r.get("ee_v3") for r in rows]),
        "ee_v3_std": _std_or_none([r.get("ee_v3") for r in rows]),
        "csep_v3_mean": _mean_or_none([r.get("csep_v3") for r in rows]),
        "csep_v3_std": _std_or_none([r.get("csep_v3") for r in rows]),
    }
    (out_dir / "aggregate.json").write_text(json.dumps(agg, indent=2), encoding="utf-8")
    return agg


def write_summary(output_root: Path, aggregates: list[dict]) -> None:
    csv_path = output_root / "summary.csv"
    md_path = output_root / "summary.md"
    fields = ["model", "task_id", "n_prompts", "ee_v3_mean", "csep_v3_mean"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in aggregates:
            w.writerow({k: row.get(k) for k in fields})

    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in aggregates:
        vals = []
        for key in fields:
            value = row.get(key)
            vals.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(vals) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Standalone EE_v3/CSEP_v3 API-VLM evaluator.")
    ap.add_argument("--prompts_dir", default=str(RUN_ROOT / "prompts"))
    ap.add_argument("--source_videos_dir", default=str(RUN_ROOT / "source_videos"))
    ap.add_argument("--results_root", default=str(RUN_ROOT / "video_results"))
    ap.add_argument("--output_dir", default=str(RUN_ROOT / "outputs"))
    ap.add_argument("--tasks", default="all", help="all or comma-separated list, e.g. T1,T2,T9")
    ap.add_argument("--models", default=None, help="comma-separated model directory names under results_root")
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--max_frames_per_shot", type=int, default=6)
    ap.add_argument("--ee_frame_pairs_per_shot", type=int, default=3)
    args = ap.parse_args()

    prompts_dir = Path(args.prompts_dir)
    source_root = Path(args.source_videos_dir)
    results_root = Path(args.results_root)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    ee_template = load_template(RUN_ROOT / "vlm_prompts" / "ee_v3.txt")
    csep_template = load_template(RUN_ROOT / "vlm_prompts" / "csep_v3.txt")
    judge = ArkVlmJudge()

    aggregates = []
    for model, model_root in discover_models(results_root, args.models):
        for task_id in parse_tasks(args.tasks):
            prompt_path = prompts_dir / f"{task_id}.json"
            if not prompt_path.exists():
                print(f"[skip] prompt missing: {prompt_path}", file=sys.stderr)
                continue
            samples = json.loads(prompt_path.read_text(encoding="utf-8"))
            if args.limit is not None:
                samples = samples[: args.limit]
            task_out = output_root / model / task_id
            task_out.mkdir(parents=True, exist_ok=True)
            rows = []
            for sample in tqdm(samples, desc=f"{model}/{task_id}"):
                edited_video = resolve_edited_video(model_root, task_id, sample["sample_id"], args.k)
                source_video = source_root / sample["source_video"]
                if edited_video is None:
                    print(f"[missing edit] {model}/{task_id}/{sample['sample_id']}", file=sys.stderr)
                    continue
                if not source_video.exists():
                    print(f"[missing source] {source_video}", file=sys.stderr)
                    continue
                result = evaluate_sample(
                    sample,
                    source_video,
                    edited_video,
                    judge,
                    ee_template,
                    csep_template,
                    args.stride,
                    args.max_frames_per_shot,
                    args.ee_frame_pairs_per_shot,
                )
                (task_out / f"{sample['sample_id']}_k{args.k}.eval.json").write_text(
                    json.dumps(result, indent=2),
                    encoding="utf-8",
                )
                rows.append(result)
            if rows:
                aggregates.append(write_task_aggregate(task_out, model, task_id, rows))

    write_summary(output_root, aggregates)
    print(f"Wrote summary: {output_root / 'summary.md'}")


if __name__ == "__main__":
    main()
