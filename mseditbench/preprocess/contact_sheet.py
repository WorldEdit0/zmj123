"""
Generate a contact sheet image for each video: 3 keyframes per shot (start, mid, end)
arranged in a grid with shot labels overlaid. Used for human QA of shot detection.

Output: <output_dir>/<video_id>_contact.jpg
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm


def _extract_frame(video_path: str, frame_idx: int) -> np.ndarray:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return np.zeros((720, 1280, 3), dtype=np.uint8)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _resize_keep_aspect(img: np.ndarray, target_h: int) -> np.ndarray:
    h, w = img.shape[:2]
    target_w = int(w * target_h / h)
    return cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)


def _load_font(size: int = 28):
    """Try to find a usable TTF font; fall back to PIL default."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",                # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",       # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Ubuntu
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",                       # Windows
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_contact_sheet(
    video_path: str,
    shots: List[Dict],
    video_meta: Dict,
    expected_shots: int = None,
    thumb_height: int = 180,
    padding: int = 8,
) -> Image.Image:
    """3 keyframes per shot (start / mid / end) -> single image grid."""
    rows = []
    font_label = _load_font(20)
    font_header = _load_font(28)

    for shot in shots:
        f0, f1 = shot["frame_start"], shot["frame_end"]
        fm = (f0 + f1) // 2
        frames = []
        for tag, fi in [("start", f0), ("mid", fm), ("end", f1)]:
            frame = _extract_frame(video_path, fi)
            frame = _resize_keep_aspect(frame, thumb_height)
            pil = Image.fromarray(frame)
            draw = ImageDraw.Draw(pil)
            label = f"S{shot['shot_id']} {tag} f{fi} ({fi/video_meta['fps']:.2f}s)"
            # Black-bordered white text for readability over any background
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((6 + dx, 4 + dy), label, fill="black", font=font_label)
            draw.text((6, 4), label, fill="white", font=font_label)
            frames.append(np.array(pil))

        # Pad and concat horizontally
        max_w = max(f.shape[1] for f in frames)
        padded = []
        for f in frames:
            if f.shape[1] < max_w:
                pad = np.zeros((thumb_height, max_w - f.shape[1], 3), dtype=np.uint8)
                f = np.concatenate([f, pad], axis=1)
            padded.append(f)
        row_img = np.concatenate(padded, axis=1)
        rows.append(row_img)

    # Pad all rows to max width
    max_w = max(r.shape[1] for r in rows)
    padded_rows = []
    for r in rows:
        if r.shape[1] < max_w:
            pad = np.zeros((thumb_height, max_w - r.shape[1], 3), dtype=np.uint8)
            r = np.concatenate([r, pad], axis=1)
        padded_rows.append(r)

    # Vertical padding between rows
    sep = np.full((padding, max_w, 3), 32, dtype=np.uint8)
    stacked = padded_rows[0]
    for r in padded_rows[1:]:
        stacked = np.concatenate([stacked, sep, r], axis=0)

    # Header banner
    n_shots = len(shots)
    flag = "OK" if expected_shots == n_shots else f"MISMATCH expected={expected_shots}"
    header_text = (
        f"{Path(video_path).stem}  "
        f"actual_shots={n_shots}  "
        f"{flag}  "
        f"fps={video_meta['fps']:.2f}  "
        f"duration={video_meta['duration_sec']}s"
    )
    header_height = 50
    header = Image.new("RGB", (max_w, header_height), (20, 20, 20))
    draw = ImageDraw.Draw(header)
    color = "lime" if expected_shots == n_shots else "tomato"
    draw.text((10, 8), header_text, fill=color, font=font_header)
    header_arr = np.array(header)

    final = np.concatenate([header_arr, stacked], axis=0)
    return Image.fromarray(final)


def main():
    ap = argparse.ArgumentParser(description="Build per-video contact sheets from shots.json files")
    ap.add_argument("--shots_dir", required=True, help="Directory of {video_id}.shots.json files")
    ap.add_argument("--videos_dir", required=True, help="Directory of {video_id}.mp4 files")
    ap.add_argument("--output_dir", required=True, help="Where to write {video_id}_contact.jpg")
    ap.add_argument("--thumb_height", type=int, default=180)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    shots_files = sorted(Path(args.shots_dir).glob("*.shots.json"))
    print(f"Processing {len(shots_files)} shots.json files")

    for sf in tqdm(shots_files, desc="Contact sheets"):
        video_id = sf.stem.replace(".shots", "")
        video_path = os.path.join(args.videos_dir, f"{video_id}.mp4")
        if not os.path.exists(video_path):
            print(f"[skip] video not found: {video_path}")
            continue

        with open(sf, "r") as f:
            result = json.load(f)

        shots = result.get("consensus_shots")
        if not shots:
            print(f"[skip] no consensus shots for {video_id}")
            continue

        video_meta = {
            "fps": result["fps"],
            "duration_sec": result["duration_sec"],
        }
        expected = result.get("expected_shots")

        try:
            img = build_contact_sheet(
                video_path, shots, video_meta, expected_shots=expected,
                thumb_height=args.thumb_height
            )
            out_path = os.path.join(args.output_dir, f"{video_id}_contact.jpg")
            img.save(out_path, quality=85)
        except Exception as e:
            print(f"[ERROR] {video_id}: {e}")

    print(f"\nDone. Contact sheets in {args.output_dir}")


if __name__ == "__main__":
    main()
