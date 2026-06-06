"""Run an EditPromptSample list through one editor baseline and save outputs.

CLI:
    python -m mseditbench.baselines.run_baseline \
        --prompts_json runs/edit_prompts_v2_10s/T1.json \
        --videos_dir data/source_videos_10s/videos \
        --output_dir runs/edits_aleph_mock/T1 \
        --baseline aleph_mock \
        --snapshot_config bench_config.json

Outputs:
    runs/edits_aleph_mock/T1/{sample_id}.mp4         edited videos
    runs/edits_aleph_mock/T1/{sample_id}.call.json   per-call request/response log
    runs/edits_aleph_mock/T1/run_manifest.json       per-run summary
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from tqdm import tqdm

from .aleph import AlephClient, AlephMock
from . import snapshot as S


BASELINE_REGISTRY = {
    "aleph":      lambda cfg: AlephClient(snapshot_model=cfg.models["aleph"].model),
    "aleph_mock": lambda cfg: AlephMock(),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts_json", required=True)
    ap.add_argument("--videos_dir", required=True,
                    help="Root directory containing source_video relative paths")
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--baseline", required=True, choices=list(BASELINE_REGISTRY.keys()))
    ap.add_argument("--snapshot_config", default="",
                    help="If empty, a stub config is used (mock-friendly)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.snapshot_config and Path(args.snapshot_config).exists():
        cfg = S.load(args.snapshot_config)
    else:
        cfg = S.BenchConfig(snapshot_id="ad-hoc", models={
            "aleph": S.ModelSnapshot(model="runwayml/aleph-mock", captured_at="2026-05-20"),
        })
    errors = S.validate(cfg)
    if errors:
        print("Snapshot config errors:")
        for e in errors:
            print(f"  - {e}")
        if not args.snapshot_config:
            print("(using ad-hoc config)")

    baseline = BASELINE_REGISTRY[args.baseline](cfg)
    os.makedirs(args.output_dir, exist_ok=True)

    prompts = json.load(open(args.prompts_json))
    if args.limit:
        prompts = prompts[: args.limit]

    manifest = {
        "snapshot_id": cfg.snapshot_id,
        "baseline": args.baseline,
        "snapshot_model": baseline.snapshot_model,
        "n_prompts": len(prompts),
        "results": [],
    }

    for sample in tqdm(prompts, desc=args.baseline):
        sid = sample["sample_id"]
        src_path = os.path.join(args.videos_dir, sample["source_video"])
        out_path = os.path.join(args.output_dir, f"{sid}.mp4")

        result = baseline.edit(
            source_video=src_path,
            instruction=sample["edit"]["instruction"],
            output_path=out_path,
        )

        with open(os.path.join(args.output_dir, f"{sid}.call.json"), "w") as f:
            json.dump({
                "sample_id": sid,
                "succeeded": result.succeeded,
                "edited_video_path": result.edited_video_path,
                "request": result.request,
                "response": result.response,
                "error": result.error_message,
            }, f, indent=2, default=str)

        manifest["results"].append({
            "sample_id": sid,
            "succeeded": result.succeeded,
            "output": result.edited_video_path,
            "error": result.error_message,
        })

    with open(os.path.join(args.output_dir, "run_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    n_ok = sum(1 for r in manifest["results"] if r["succeeded"])
    print(f"\n{n_ok}/{len(manifest['results'])} succeeded -> {args.output_dir}")


if __name__ == "__main__":
    main()
