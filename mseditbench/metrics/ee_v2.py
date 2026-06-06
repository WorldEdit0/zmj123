"""EE_v2 — DEPRECATED.  Use ``mseditbench.metrics.ee_v3.ee_v3`` for headline.

⚠️  This is the v2 metric (continuous CLIP-T uplift). Retained for ablation.

Why deprecated:
    CLIP image embedding is dominated by overall scene composition, so the
    CLIP-T uplift signal is weak even when humans clearly see a successful
    edit. Pro doesn't outperform Fast under this metric because Pro's larger
    re-renders don't translate into bigger CLIP-T deltas. v3 (VLM-as-Judge)
    captures visual quality and edit completeness directly.

Iteration history:
  v2.0  Directional CLIP × movement magnitude:
            EE = max(0, cos(img_diff, txt_diff)) × clip(||img_diff||/α, 0, 1)
        Smoke on 8 T1 Pro samples → mean 0.126. Failed: dir_sim is diluted by
        unchanged background in whole-frame CLIP embeddings; even good edits
        only align ~+0.15 to +0.30 with the requested text direction.

  v2.1  ★ Continuous CLIP-T uplift, no thresholding:
            For each shot k:
                delta_k = cos(CLIP_img(edit_k), CLIP_txt(tgt_text))
                        - cos(CLIP_img(src_k),  CLIP_txt(tgt_text))
                ee_k    = min(1, max(0, delta_k) / DELTA_MAX)
            EE = mean over applicable shots(ee_k)
        DELTA_MAX = 0.05 (empirical magnitude of a "well-edited" delta).

Why this is the right signal:
  - Directly answers "is the edit visually closer to the requested target than
    the source was?" — no proxy via text-difference directions.
  - Continuous in [0, 1]; no binary thresholds; no VLM dependence.
  - DELTA_MAX=0.05 means a 5-percentage-point CLIP-T uplift = full credit.
    This corresponds qualitatively to "the editor clearly applied the change".
  - Robust across task types: T1 large entity replace gives delta ~0.06-0.10;
    T2 attribute change gives ~0.02-0.05 -> ee = 0.4-1.0
    change gives ~0.005-0.02 → ee = 0.1-0.4.
  - No masking applied to image embeddings — whole-frame CLIP captures the
    overall semantic match. Masking the entity tends to corrupt CLIP because
    CLIP wasn't trained on black-padded inputs.

Properties:
  - Returns None when no applicable shots have both source and edit frames.
  - DELTA_MAX is the only tunable knob. Default 0.05 is calibrated on Seedance
    2.0 Pro/Fast on the v2_10s prompt set (see paper §4 calibration).
"""
from __future__ import annotations
import numpy as np
from . import backends as B


def ee_v2(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames:   dict[int, np.ndarray],
    applicable_shots: list[int],
    src_text: str,                # kept for signature compat; unused in v2.1
    tgt_text: str,
    clip_backend=None,
    per_shot_masks: dict[int, np.ndarray] | None = None,  # unused in v2.1 (whole frame)
    delta_max: float = 0.05,
) -> dict:
    """v2.1: continuous CLIP-T uplift.

    src_text and per_shot_masks kept in signature for backward compat but
    are intentionally unused in v2.1. The signal is purely
        delta_k = CLIP_T(edit_k, tgt_text) - CLIP_T(src_k, tgt_text)
    on whole frames.
    """
    if clip_backend is None:
        clip_backend = B.get_clip("mock")
    if not tgt_text:
        return {"ee": None, "per_shot": {}, "n_applicable": 0,
                "reason": "empty tgt_text"}

    try:
        t_tgt = clip_backend.embed_text(tgt_text)
    except NotImplementedError:
        return {"ee": None, "per_shot": {}, "n_applicable": 0,
                "reason": "clip backend lacks embed_text"}

    per_shot = {}
    for k in applicable_shots:
        if k not in per_shot_source_frames or k not in per_shot_edit_frames:
            continue
        sf = per_shot_source_frames[k]
        ef = per_shot_edit_frames[k]
        if len(sf) == 0 or len(ef) == 0:
            continue

        # Whole-frame CLIP image embeddings (mean-pooled over T frames)
        s_emb = clip_backend.embed_video(sf)
        e_emb = clip_backend.embed_video(ef)

        s_score = float(np.dot(s_emb, t_tgt))
        e_score = float(np.dot(e_emb, t_tgt))
        delta = e_score - s_score

        ee_k = float(np.clip(max(0.0, delta) / max(delta_max, 1e-6), 0.0, 1.0))
        per_shot[k] = {
            "ee": ee_k,
            "delta": delta,
            "s_score": s_score,
            "e_score": e_score,
        }

    if not per_shot:
        return {"ee": None, "per_shot": {}, "n_applicable": 0,
                "reason": "no applicable shots had frames"}

    ee_mean = float(np.mean([v["ee"] for v in per_shot.values()]))
    return {
        "ee": ee_mean,
        "per_shot": per_shot,
        "n_applicable": len(per_shot),
        "src_text": src_text,
        "tgt_text": tgt_text,
        "delta_max": delta_max,
    }
