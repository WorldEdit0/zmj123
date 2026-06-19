"""Temporal Anchor Consistency (TAC).

TAC measures whether edited video shot boundaries preserve the expected time
anchors of the source sequence.

The metric first detects shots in the edited video, normally with OmniShotCut.
If the edited shot count differs from the expected shot count, TAC is 0. If
the counts match, each edited shot is compared with its expected start/end
time. The expected source timeline comes from benchmark shot metadata by
default; source-side detector output can be enabled explicitly for diagnostics
with ``detect_source_shots=True``. Per-shot score is:

    max(0, 1 - mean(|Δstart|, |Δend|) / expected_duration)

Final TAC is the mean of per-shot scores. T5 reorder prompts can pass
``expected_order``; in that case the expected timeline is built by laying out
source shot durations in the requested order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np


def _video_fps(video_path: str) -> float:
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    cap.release()
    return fps if fps > 0 else 24.0


def _duration_sec(shot: dict, fps: float) -> float:
    if shot.get("duration_sec"):
        return float(shot["duration_sec"])
    return (int(shot["frame_end"]) - int(shot["frame_start"]) + 1) / max(fps, 1e-6)


def _anchors_from_shots(shots: list[dict], fps: float) -> list[tuple[float, float]]:
    anchors = []
    for sh in shots:
        if "t_start" in sh and "t_end" in sh:
            anchors.append((float(sh["t_start"]), float(sh["t_end"])))
        else:
            anchors.append((
                int(sh["frame_start"]) / max(fps, 1e-6),
                (int(sh["frame_end"]) + 1) / max(fps, 1e-6),
            ))
    return anchors


def _with_reference_shot_ids(
    detected_shots: list[dict],
    reference_shots: list[dict],
) -> list[dict]:
    """Attach stable shot IDs to detector output for T5 reorder mapping."""
    tagged = []
    for i, sh in enumerate(detected_shots):
        item = dict(sh)
        if "shot_id" not in item:
            if i < len(reference_shots) and "shot_id" in reference_shots[i]:
                item["shot_id"] = int(reference_shots[i]["shot_id"])
            else:
                item["shot_id"] = i + 1
        tagged.append(item)
    return tagged


def _expected_anchors(
    source_shots: list[dict],
    source_fps: float,
    expected_order: list[int] | None = None,
) -> list[tuple[float, float]]:
    by_id = {int(sh.get("shot_id", i + 1)): sh for i, sh in enumerate(source_shots)}
    order = expected_order or [int(sh.get("shot_id", i + 1)) for i, sh in enumerate(source_shots)]

    anchors = []
    t = 0.0
    for sid in order:
        sh = by_id.get(int(sid))
        if sh is None:
            continue
        dur = max(_duration_sec(sh, source_fps), 1e-6)
        anchors.append((t, t + dur))
        t += dur
    return anchors


def temporal_anchor_consistency(
    source_shots: list[dict],
    edited_video_path: str | None = None,
    *,
    source_video_path: str | None = None,
    edited_shots: list[dict] | None = None,
    source_fps: float | None = None,
    edited_fps: float | None = None,
    expected_order: list[int] | None = None,
    detect_shots_fn: Callable[[str], list[dict]] | None = None,
    detect_source_shots: bool | None = None,
) -> dict:
    """Compute temporal-anchor consistency.

    ``edited_shots`` can be supplied directly for tests. Production callers
    pass ``edited_video_path`` and let ``detect_shots_fn`` default to
    OmniShotCut for edited-video boundaries. Source shot metadata is treated
    as the benchmark reference unless ``detect_source_shots`` is set to true.
    """
    if source_fps is None:
        source_fps = _video_fps(source_video_path) if source_video_path else 24.0

    if detect_source_shots is None:
        detect_source_shots = False

    needs_detector = (detect_source_shots and source_video_path) or edited_shots is None
    if needs_detector and detect_shots_fn is None:
        from mseditbench.preprocess.omnishot_backend import predict_shots
        detect_shots_fn = predict_shots

    source_from_detection = False
    source_for_expected = source_shots
    if detect_source_shots and source_video_path:
        detected_source = detect_shots_fn(source_video_path) if detect_shots_fn else []
        source_for_expected = _with_reference_shot_ids(detected_source, source_shots)
        source_from_detection = True

    expected = _expected_anchors(source_for_expected, source_fps, expected_order)
    if not expected:
        return {
            "tac": None,
            "shot_count_match": False,
            "expected_count": 0,
            "edited_count": 0,
            "per_shot_tac": {},
            "mean_anchor_error_sec": None,
            "source_count_from_detection": source_from_detection,
            "edited_count_from_detection": False,
            "source_shots": source_for_expected,
            "edited_shots": [],
            "reason": "no expected source shots",
        }

    edited_from_detection = False
    if edited_shots is None:
        if not edited_video_path:
            return {
                "tac": None,
                "shot_count_match": False,
                "expected_count": len(expected),
                "edited_count": None,
                "per_shot_tac": {},
                "mean_anchor_error_sec": None,
                "source_count_from_detection": source_from_detection,
                "edited_count_from_detection": False,
                "source_shots": source_for_expected,
                "edited_shots": [],
                "reason": "edited video path missing",
            }
        edited_shots = detect_shots_fn(edited_video_path)
        edited_from_detection = True

    if edited_fps is None:
        edited_fps = _video_fps(edited_video_path) if edited_video_path else source_fps

    edited = _anchors_from_shots(edited_shots, edited_fps)
    if len(edited) != len(expected):
        return {
            "tac": 0.0,
            "shot_count_match": False,
            "expected_count": len(expected),
            "edited_count": len(edited),
            "per_shot_tac": {},
            "mean_anchor_error_sec": None,
            "source_count_from_detection": source_from_detection,
            "edited_count_from_detection": edited_from_detection,
            "source_shots": source_for_expected,
            "edited_shots": edited_shots,
            "reason": "edited shot count differs from expected count",
        }

    per_shot: dict[int, float] = {}
    errors = []
    for i, ((s0, s1), (e0, e1)) in enumerate(zip(expected, edited), start=1):
        edge_error = (abs(e0 - s0) + abs(e1 - s1)) / 2.0
        expected_duration = max(s1 - s0, 1e-6)
        score = max(0.0, 1.0 - edge_error / expected_duration)
        per_shot[i] = float(score)
        errors.append(edge_error)

    return {
        "tac": float(np.mean(list(per_shot.values()))),
        "shot_count_match": True,
        "expected_count": len(expected),
        "edited_count": len(edited),
        "per_shot_tac": per_shot,
        "mean_anchor_error_sec": float(np.mean(errors)) if errors else None,
        "source_count_from_detection": source_from_detection,
        "edited_count_from_detection": edited_from_detection,
        "source_shots": source_for_expected,
        "edited_shots": edited_shots,
        "reason": None,
    }
