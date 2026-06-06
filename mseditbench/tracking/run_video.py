"""Build per-shot entity tubes for one video.

Pipeline per shot:
    1. Pick anchor frame (mid-shot)
    2. Run open-vocab detector on anchor frame against `phrases` (key_objects + character descs)
    3. For each detected phrase, propagate a binary mask through the shot via tracker
    4. Encode masks as RLE-ish JSON-friendly dict; save bbox + RLE per frame

Output JSON: runs/.../tubes/{video_id}.tubes.json

Example:
    python -m mseditbench.tracking.run_video \
        --video data/source_videos_10s/videos/00000.mp4 \
        --shots_json runs/pilot_v2_10s/shots/00000.shots.json \
        --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \
        --output_json runs/tubes/00000.tubes.json \
        --detector mock --tracker mock
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .detector import get_detector
from .tracker import get_tracker


def _rle_encode(mask: np.ndarray) -> dict:
    """Tiny COCO-style RLE on flattened mask. Round-trippable, no compression."""
    flat = mask.flatten()
    if flat.size == 0:
        return {"size": [0, 0], "counts": []}
    diffs = np.diff(np.concatenate(([1 - flat[0]], flat)))
    starts = np.where(diffs != 0)[0]
    counts = np.diff(np.concatenate((starts, [flat.size]))).tolist()
    return {"size": list(mask.shape), "counts": counts, "first_value": int(flat[0])}


def _rle_decode(rle: dict) -> np.ndarray:
    h, w = rle["size"]
    flat = np.zeros(h * w, dtype=np.uint8)
    cur = rle.get("first_value", 0)
    pos = 0
    for c in rle["counts"]:
        flat[pos:pos + c] = cur
        pos += c
        cur = 1 - cur
    return flat.reshape(h, w)


def _bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return (0, 0, 0, 0)
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _load_phrases(source_item: dict) -> list[dict]:
    """Build phrase list: key_objects (label-only) + character descs.

    Returns list of {phrase, kind, ref_id} where kind in {object, character}.
    """
    out = []
    for ko in source_item.get("key_objects", []):
        out.append({"phrase": ko, "kind": "object", "ref_id": ko})
    for ch in source_item.get("characters", []):
        out.append({"phrase": ch["desc"], "kind": "character", "ref_id": ch["id"]})
    return out


def build_tubes_for_video(
    video_path: str,
    shots: list[dict],
    source_item: dict,
    detector_kind: str = "mock",
    tracker_kind: str = "mock",
    box_threshold: float = 0.30,
    text_threshold: float = 0.25,
) -> dict:
    detector = get_detector(detector_kind)
    tracker = get_tracker(tracker_kind)
    phrases = _load_phrases(source_item)

    cap = cv2.VideoCapture(video_path)
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    tubes = []
    for shot in shots:
        sid = int(shot["shot_id"])
        f0, f1 = int(shot["frame_start"]), int(shot["frame_end"])
        anchor_frame = (f0 + f1) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, anchor_frame)
        ok, anchor = cap.read()
        if not ok:
            continue
        anchor_rgb = cv2.cvtColor(anchor, cv2.COLOR_BGR2RGB)

        det = detector.detect(anchor_rgb, [p["phrase"] for p in phrases],
                              box_threshold=box_threshold, text_threshold=text_threshold)

        for d, p in zip(det, phrases):
            if d["score"] < box_threshold and detector_kind != "mock":
                continue
            masks_per_frame = tracker.propagate_shot(
                video_path, f0, f1, anchor_frame, d["bbox_xyxy"],
            )
            frames_out = []
            for fi, mask in sorted(masks_per_frame.items()):
                bb = _bbox_from_mask(mask)
                frames_out.append({
                    "frame": fi,
                    "bbox_xyxy": list(bb),
                    "mask_rle": _rle_encode(mask),
                    "score": float(d["score"]),
                    "visible": int(mask.sum()) > 16,
                })
            tubes.append({
                "video_id": Path(video_path).stem,
                "shot_id": sid,
                "entity_id": f"{p['ref_id']}",
                "label": p["phrase"],
                "kind": p["kind"],
                "anchor_frame": anchor_frame,
                "anchor_score": float(d["score"]),
                "frames": frames_out,
            })

    cap.release()

    return {
        "video_id": Path(video_path).stem,
        "video_path": video_path,
        "fps": fps,
        "total_frames": total_frames,
        "n_shots": len(shots),
        "n_tubes": len(tubes),
        "detector_backend": detector_kind,
        "tracker_backend": tracker_kind,
        "tubes": tubes,
    }


def main():
    ap = argparse.ArgumentParser(description="Build per-shot entity tubes for one video")
    ap.add_argument("--video", required=True)
    ap.add_argument("--shots_json", required=True)
    ap.add_argument("--source_json", required=True)
    ap.add_argument("--output_json", required=True)
    ap.add_argument("--detector", default="mock", choices=["mock", "groundingdino"])
    ap.add_argument("--tracker", default="mock", choices=["mock", "sam2"])
    ap.add_argument("--box_threshold", type=float, default=0.30)
    ap.add_argument("--text_threshold", type=float, default=0.25)
    args = ap.parse_args()

    shots_data = json.load(open(args.shots_json))
    shots = shots_data.get("consensus_shots") or []

    src = json.load(open(args.source_json))
    vid_id = Path(args.video).stem
    src_item = next((it for it in src if f"{int(it['global_index']):05d}" == vid_id), None)
    if src_item is None:
        print(f"[warn] no source item for {vid_id}; using empty phrases")
        src_item = {"characters": [], "key_objects": []}

    result = build_tubes_for_video(
        args.video, shots, src_item,
        detector_kind=args.detector, tracker_kind=args.tracker,
        box_threshold=args.box_threshold, text_threshold=args.text_threshold,
    )

    os.makedirs(os.path.dirname(args.output_json) or ".", exist_ok=True)
    with open(args.output_json, "w") as f:
        json.dump(result, f)
    print(f"Wrote {result['n_tubes']} tubes for {result['n_shots']} shots -> {args.output_json}")


if __name__ == "__main__":
    main()
