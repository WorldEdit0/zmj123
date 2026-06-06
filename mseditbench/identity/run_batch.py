"""Batch character DB extraction across all videos.

CLI:
    python -m mseditbench.identity.run_batch \
        --videos_dir data/source_videos_10s/videos \
        --shots_dir runs/pilot_v2_10s/shots \
        --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \
        --output_dir runs/identity_v2_10s \
        --backend mock --threshold 0.45
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import numpy as np
from tqdm import tqdm

from .face_extract import extract_faces_for_video
from .face_cluster import cluster_to_character_db


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos_dir", required=True)
    ap.add_argument("--shots_dir", required=True)
    ap.add_argument("--source_json", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--backend", default="mock", choices=["mock", "insightface"])
    ap.add_argument("--n_keyframes_per_shot", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=0.45)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    src_items = json.load(open(args.source_json))
    src_lookup = {f"{int(it['global_index']):05d}": it for it in src_items}

    videos = sorted(Path(args.videos_dir).glob("*.mp4"))
    summary = {"total_videos": 0, "total_faces": 0, "total_characters": 0,
               "per_video": {}}

    for vp in tqdm(videos, desc="Identity"):
        vid = vp.stem
        shots_path = Path(args.shots_dir) / f"{vid}.shots.json"
        if not shots_path.exists():
            continue
        shots = json.load(open(shots_path)).get("consensus_shots") or []
        try:
            faces, emb = extract_faces_for_video(
                str(vp), shots,
                output_crops_dir=str(Path(args.output_dir) / f"{vid}_crops"),
                n_keyframes_per_shot=args.n_keyframes_per_shot,
                backend=args.backend,
            )
            with open(Path(args.output_dir) / f"{vid}.faces.json", "w") as f:
                json.dump(faces, f)
            np.save(Path(args.output_dir) / f"{vid}.faces.embeddings.npy", emb)

            src_chars = src_lookup.get(vid, {}).get("characters", [])
            db = cluster_to_character_db(faces, emb, src_chars, threshold=args.threshold)
            with open(Path(args.output_dir) / f"{vid}.character_db.json", "w") as f:
                json.dump(db, f, indent=2)

            summary["total_videos"] += 1
            summary["total_faces"] += int(faces["n_records"])
            summary["total_characters"] += int(db["n_clusters"])
            summary["per_video"][vid] = {"n_faces": faces["n_records"],
                                         "n_characters": db["n_clusters"]}
        except Exception as e:
            print(f"[ERROR] {vid}: {e}")

    with open(Path(args.output_dir) / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n{summary['total_videos']} videos, {summary['total_faces']} faces, "
          f"{summary['total_characters']} characters -> {args.output_dir}")


if __name__ == "__main__":
    main()
