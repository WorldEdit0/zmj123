from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np


def video_info(video_path: str | Path) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 24.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return {"fps": fps, "frame_count": frame_count}


def _sample_indices(start: int, end: int, stride: int, max_frames: int) -> list[int]:
    start = max(0, int(start))
    end = max(start, int(end))
    stride = max(1, int(stride))
    idx = list(range(start, end + 1, stride))
    if not idx:
        idx = [start]
    if max_frames > 0 and len(idx) > max_frames:
        pick = np.linspace(0, len(idx) - 1, max_frames).round().astype(int)
        idx = [idx[int(i)] for i in pick]
    return idx


def read_frames_at(video_path: str | Path, indices: list[int]) -> np.ndarray:
    if not indices:
        return np.empty((0, 0, 0, 3), dtype=np.uint8)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    frames = []
    for frame_idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
        ok, frame_bgr = cap.read()
        if not ok:
            continue
        frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    cap.release()
    if not frames:
        return np.empty((0, 0, 0, 3), dtype=np.uint8)
    return np.stack(frames, axis=0)


def per_shot_frames(
    video_path: str | Path,
    shots: list[dict],
    *,
    stride: int = 4,
    max_frames: int = 6,
) -> dict[int, np.ndarray]:
    out: dict[int, np.ndarray] = {}
    for i, shot in enumerate(shots, start=1):
        shot_id = int(shot.get("shot_id", i))
        idx = _sample_indices(shot["frame_start"], shot["frame_end"], stride, max_frames)
        out[shot_id] = read_frames_at(video_path, idx)
    return out


def matched_pair_indices(n_src: int, n_edit: int, pairs_per_shot: int) -> list[tuple[int, int]]:
    n = min(int(n_src), int(n_edit))
    if n <= 0:
        return []
    m = min(max(1, int(pairs_per_shot)), n)
    if m == 1:
        mid = (n - 1) // 2
        return [(mid, mid)]
    idx = np.linspace(0, n - 1, m).round().astype(int)
    return [(int(i), int(i)) for i in idx]


def sample_frame_set(frames: np.ndarray, k: int) -> list[np.ndarray]:
    if len(frames) == 0:
        return []
    n = min(max(1, int(k)), len(frames))
    idx = np.linspace(0, len(frames) - 1, n).round().astype(int)
    return [frames[int(i)] for i in idx]


def encode_jpeg_data_url(frame_rgb: np.ndarray, *, max_side: int = 384, quality: int = 80) -> str:
    arr = np.asarray(frame_rgb)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    h, w = arr.shape[:2]
    scale = min(1.0, float(max_side) / max(h, w))
    if scale < 1.0:
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)))
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    b64 = base64.b64encode(buf).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"
