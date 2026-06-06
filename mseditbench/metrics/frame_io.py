"""Frame extraction helpers — read per-shot frame arrays from a video file.

Used by the metrics layer when given a `consensus_shots` list to pull RGB
frames into the {shot_id: [T,H,W,3]} dicts the metrics expect.
"""

from __future__ import annotations
import numpy as np
import cv2


def read_frames(video_path: str, frame_start: int, frame_end: int,
                stride: int = 1, max_frames: int | None = 8) -> np.ndarray:
    """Returns [T, H, W, 3] uint8 RGB. T capped at max_frames if set."""
    # 中文注释：stride 控制原始视频帧的抽样间隔；max_frames 控制每个 shot
    # 最多交给指标多少帧。先按 stride 生成候选帧，再等间隔压到 max_frames。
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)
    target = list(range(frame_start, frame_end + 1, stride))
    if max_frames is not None and len(target) > max_frames:
        idx = np.linspace(0, len(target) - 1, max_frames).astype(int)
        target = [target[i] for i in idx]

    frames = []
    cur = frame_start
    target_set = set(target)
    while cur <= frame_end:
        ok, frame = cap.read()
        if not ok:
            break
        if cur in target_set:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        cur += 1
    cap.release()
    if not frames:
        raise ValueError(f"No frames read from {video_path} [{frame_start}, {frame_end}]")
    return np.stack(frames)


def per_shot_frames(video_path: str, shots: list[dict],
                    stride: int = 1, max_frames: int | None = 8) -> dict[int, np.ndarray]:
    """Convenience: shots = [{shot_id, frame_start, frame_end}, ...]."""
    # 中文注释：返回结构统一为 shot_id -> RGB frame array，所有指标都吃这个格式。
    out = {}
    for s in shots:
        out[int(s["shot_id"])] = read_frames(
            video_path, int(s["frame_start"]), int(s["frame_end"]),
            stride=stride, max_frames=max_frames,
        )
    return out
