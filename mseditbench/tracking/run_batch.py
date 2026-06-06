"""Batch wrapper: run tube building for all videos in a directory.

    python -m mseditbench.tracking.run_batch \
        --videos_dir data/source_videos_10s/videos \
        --shots_dir runs/pilot_v2_10s/shots \
        --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \
        --output_dir runs/tubes_v2_10s \
        --detector mock --tracker mock
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

from tqdm import tqdm

from .run_video import build_tubes_for_video


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos_dir", required=True)
    ap.add_argument("--shots_dir", required=True)
    ap.add_argument("--source_json", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--detector", default="mock", choices=["mock", "groundingdino"])
    ap.add_argument("--tracker", default="mock", choices=["mock", "sam2"])
    ap.add_argument("--box_threshold", type=float, default=0.30)
    ap.add_argument("--text_threshold", type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    src_items = json.load(open(args.source_json))
    src_lookup = {f"{int(it['global_index']):05d}": it for it in src_items}

    videos = sorted(Path(args.videos_dir).glob("*.mp4"))
    print(f"Processing {len(videos)} videos -> {args.output_dir}")

    summary = {"total": 0, "skipped_no_shots": 0, "tubes_per_video": {}}
    for vp in tqdm(videos):
        vid = vp.stem
        shots_path = Path(args.shots_dir) / f"{vid}.shots.json"
        if not shots_path.exists():
            summary["skipped_no_shots"] += 1
            continue
        shots = json.load(open(shots_path)).get("consensus_shots") or []
        src_item = src_lookup.get(vid, {"characters": [], "key_objects": []})

        try:
            r = build_tubes_for_video(
                str(vp), shots, src_item,
                detector_kind=args.detector, tracker_kind=args.tracker,
                box_threshold=args.box_threshold, text_threshold=args.text_threshold,
            )
        except Exception as e:
            print(f"[ERROR] {vid}: {e}")
            continue

        out_p = Path(args.output_dir) / f"{vid}.tubes.json"
        with open(out_p, "w") as f:
            json.dump(r, f)
        summary["tubes_per_video"][vid] = r["n_tubes"]
        summary["total"] += r["n_tubes"]

    with open(Path(args.output_dir) / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nTotal tubes: {summary['total']}")
    print(f"Summary: {Path(args.output_dir) / 'summary.json'}")


if __name__ == "__main__":
    main()
