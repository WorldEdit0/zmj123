"""Per-shot face crop + ArcFace embedding extraction.

CLI:
    python -m mseditbench.identity.face_extract \
        --video data/source_videos_10s/videos/00000.mp4 \
        --shots_json runs/pilot_v2_10s/shots/00000.shots.json \
        --output_json runs/faces/00000.faces.json \
        --output_crops_dir runs/faces/00000_crops \
        --backend mock

Per shot we sample N keyframes and run face detection + 512-d ArcFace
embedding. Crops are saved to disk for later visualisation; embeddings are
saved as a parallel .npy.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import cv2
import numpy as np

from mseditbench.metrics.backends import get_face


def _sample_indices(f0: int, f1: int, n: int) -> list[int]:
    if f1 <= f0:
        return [f0]
    if n >= (f1 - f0 + 1):
        return list(range(f0, f1 + 1))
    return [int(round(f0 + (f1 - f0) * i / (n - 1))) for i in range(n)]


def extract_faces_for_video(
    video_path: str,
    shots: list[dict],
    output_crops_dir: str | None = None,
    n_keyframes_per_shot: int = 5,
    backend: str = "mock",
) -> dict:
    face = get_face(backend)
    cap = cv2.VideoCapture(video_path)
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vid = Path(video_path).stem

    if output_crops_dir:
        os.makedirs(output_crops_dir, exist_ok=True)

    records = []
    embeddings = []
    for shot in shots:
        sid = int(shot["shot_id"])
        f0 = int(shot["frame_start"])
        f1 = int(shot["frame_end"])
        for fi in _sample_indices(f0, f1, n_keyframes_per_shot):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, frame = cap.read()
            if not ok:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = face.detect_and_embed(rgb)
            for j, f in enumerate(faces):
                x0, y0, x1, y1 = f["bbox"]
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(rgb.shape[1], x1), min(rgb.shape[0], y1)
                if x1 - x0 < 16 or y1 - y0 < 16:
                    continue
                crop = rgb[y0:y1, x0:x1]
                crop_path = ""
                if output_crops_dir:
                    crop_path = os.path.join(output_crops_dir,
                                             f"shot{sid}_f{fi}_face{j}.jpg")
                    cv2.imwrite(crop_path, cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
                emb = np.asarray(f["embedding"], dtype=np.float32)
                emb = emb / (np.linalg.norm(emb) + 1e-8)
                idx = len(embeddings)
                embeddings.append(emb)
                records.append({
                    "embedding_idx": idx,
                    "shot_id": sid,
                    "frame": fi,
                    "bbox_xyxy": [int(x0), int(y0), int(x1), int(y1)],
                    "score": float(f["score"]),
                    "crop_path": crop_path,
                })
    cap.release()

    embeddings_np = np.stack(embeddings) if embeddings else np.zeros((0, 512), dtype=np.float32)
    return {
        "video_id": vid,
        "video_path": video_path,
        "fps": fps,
        "total_frames": total_frames,
        "backend": backend,
        "n_keyframes_per_shot": n_keyframes_per_shot,
        "n_records": len(records),
        "records": records,
        "embeddings_shape": list(embeddings_np.shape),
    }, embeddings_np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--shots_json", required=True)
    ap.add_argument("--output_json", required=True)
    ap.add_argument("--output_crops_dir", default="")
    ap.add_argument("--backend", default="mock", choices=["mock", "insightface"])
    ap.add_argument("--n_keyframes_per_shot", type=int, default=5)
    args = ap.parse_args()

    shots = json.load(open(args.shots_json)).get("consensus_shots") or []
    record, emb = extract_faces_for_video(
        args.video, shots,
        output_crops_dir=args.output_crops_dir or None,
        n_keyframes_per_shot=args.n_keyframes_per_shot,
        backend=args.backend,
    )
    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w") as f:
        json.dump(record, f)
    np.save(args.output_json.replace(".json", ".embeddings.npy"), emb)
    print(f"Wrote {record['n_records']} face records  ({emb.shape}) -> {args.output_json}")


if __name__ == "__main__":
    main()
