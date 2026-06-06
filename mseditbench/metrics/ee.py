"""Edit Effectiveness (EE) — DEPRECATED v1.

⚠️  This is the legacy v1 metric. Use ``mseditbench.metrics.ee_v3.ee_v3``
    for paper-quality evaluation. This file is retained only for ablation /
    reproducibility of historical numbers.

Why deprecated:
    Binary thresholding (CLIP-T delta > tau) + 3-VLM unanimous voting collapses
    real edit signals to 0 in many cases (compositional target phrases dilute
    CLIP-T uplift; correlated VLM votes amplify single-judge errors). Strong
    editors like Seedance Pro scored ≤ 0.10 mean across tasks, which was a
    measurement artefact, not a model shortcoming.

v3 replaces both v1 and v2 (continuous CLIP-T uplift, also deprecated). v3
uses a VLM-as-Judge that directly rates the edit on a 0-5 scale.

Original v1 design (kept as-is below): per-shot binary indicator that
mask-conditional CLIP-T delta exceeds tau AND 3-VLM unanimous agrees.
"""

from __future__ import annotations
import os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from . import backends as B


def ee(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames: dict[int, np.ndarray],
    applicable_shots: list[int],
    target_phrase: str,
    instruction: str,
    clip_backend=None,
    vlm_backends: list | None = None,
    tau_ee: float = 0.05,
    per_shot_source_masks: dict[int, np.ndarray] | None = None,
    per_shot_edit_masks: dict[int, np.ndarray] | None = None,
    vlm_max_workers: int | None = None,
) -> dict:
    """All VLM calls (3 VLMs × N applicable shots) are issued in parallel via
    a ThreadPoolExecutor. Default max_workers = $VLM_MAX_WORKERS env var or 16.
    """
    if vlm_max_workers is None:
        vlm_max_workers = int(os.environ.get("VLM_MAX_WORKERS", 16))
    if clip_backend is None:
        clip_backend = B.get_clip("mock")
    if vlm_backends is None:
        vlm_backends = [B.get_vlm("mock") for _ in range(3)]
    assert len(vlm_backends) == 3, "EE requires exactly 3 VLM backends"

    deltas = {}
    valid_shots = []
    for k in applicable_shots:
        if k not in per_shot_source_frames or k not in per_shot_edit_frames:
            continue
        valid_shots.append(k)
        sm = (per_shot_source_masks or {}).get(k)
        em = (per_shot_edit_masks or {}).get(k)
        sf = per_shot_source_frames[k].copy()
        ef = per_shot_edit_frames[k].copy()
        if sm is not None: sf = sf * sm[..., None]
        if em is not None: ef = ef * em[..., None]

        s_score = clip_backend.score_video_text(sf.astype(np.uint8), target_phrase)
        e_score = clip_backend.score_video_text(ef.astype(np.uint8), target_phrase)
        deltas[k] = float(e_score - s_score)

    def _call(k_v_idx):
        k, vidx = k_v_idx
        return k, vidx, vlm_backends[vidx].yes_no(per_shot_edit_frames[k], instruction)

    tasks = [(k, vi) for k in valid_shots for vi in range(3)]
    vlm_votes_raw = {}
    if tasks:
        with ThreadPoolExecutor(max_workers=min(vlm_max_workers, len(tasks))) as ex:
            for fut in ex.map(_call, tasks):
                k, vi, ans = fut
                vlm_votes_raw[(k, vi)] = ans

    indicators, vlm_votes = {}, {}
    for k in valid_shots:
        votes = [vlm_votes_raw.get((k, vi), False) for vi in range(3)]
        vlm_votes[k] = votes
        unanimous = all(votes)
        indicators[k] = 1 if (deltas[k] > tau_ee and unanimous) else 0

    if not indicators:
        return {"ee": None, "per_shot_indicators": {}, "per_shot_clip_delta": {}, "per_shot_vlm": {}}

    return {
        "ee": float(np.mean(list(indicators.values()))),
        "per_shot_indicators": indicators,
        "per_shot_clip_delta": deltas,
        "per_shot_vlm": vlm_votes,
    }
