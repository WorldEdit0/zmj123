"""Cross-Shot Edit Propagation (CSEP) — DEPRECATED v1.

⚠️  This is the legacy v1 metric. Use ``mseditbench.metrics.csep_v3.csep_v3``
    for paper-quality evaluation. Retained only for ablation.

Why deprecated:
    Inherits all v1 EE pathologies (CLIP-T per-shot delta + harmonic-mean
    aggregation drops to 0 when one component is 0). Replaced by csep_v3
    which uses VLM-as-Judge pairwise consistency × EE_v3 coverage with a
    geometric-mean combination.

Original v1 design (kept as-is below): continuous EE per applicable shot,
then harmonic mean of coverage and consistency. Skipped (returns None)
when |applicable_shots| < 2.
"""

from __future__ import annotations
import numpy as np
from . import backends as B


def _ee_continuous(
    src_frames: np.ndarray,
    edit_frames: np.ndarray,
    target_phrase: str,
    clip_backend,
    tau_csep: float,
    src_mask: np.ndarray | None = None,
    edit_mask: np.ndarray | None = None,
) -> float:
    """Returns ẽ_k in [0, 1]. Mask is multiplicative on RGB if given."""
    s = src_frames.copy()
    e = edit_frames.copy()
    if src_mask is not None:
        s = s * src_mask[..., None]
    if edit_mask is not None:
        e = e * edit_mask[..., None]
    s_score = clip_backend.score_video_text(s.astype(np.uint8), target_phrase)
    e_score = clip_backend.score_video_text(e.astype(np.uint8), target_phrase)
    delta = (e_score - s_score) / tau_csep
    return float(np.clip(delta, 0.0, 1.0))


def csep(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames: dict[int, np.ndarray],
    applicable_shots: list[int],
    target_phrase: str,
    clip_backend=None,
    tau_csep: float = 0.05,
    per_shot_source_masks: dict[int, np.ndarray] | None = None,
    per_shot_edit_masks: dict[int, np.ndarray] | None = None,
    eps: float = 1e-6,
) -> dict:
    """Compute CSEP for one (video, edit) pair.

    Returns dict {csep, coverage, consistency, per_shot_e_tilde, n_applicable}.
    csep is None when fewer than 2 applicable shots exist.
    """
    if clip_backend is None:
        clip_backend = B.get_clip("mock")

    e_tilde = {}
    for k in applicable_shots:
        if k not in per_shot_source_frames or k not in per_shot_edit_frames:
            continue
        sm = (per_shot_source_masks or {}).get(k)
        em = (per_shot_edit_masks or {}).get(k)
        e_tilde[k] = _ee_continuous(
            per_shot_source_frames[k], per_shot_edit_frames[k],
            target_phrase, clip_backend, tau_csep,
            src_mask=sm, edit_mask=em,
        )

    if len(e_tilde) == 0:
        return {"csep": None, "coverage": None, "consistency": None,
                "per_shot_e_tilde": {}, "n_applicable": 0}

    vals = np.array(list(e_tilde.values()))
    coverage = float(vals.mean())
    if len(vals) >= 2:
        consistency = 1 - float(vals.std()) / (float(vals.mean()) + eps)
        consistency = max(0.0, min(1.0, consistency))
        if coverage + consistency < eps:
            csep_val = 0.0
        else:
            csep_val = 2 * coverage * consistency / (coverage + consistency)
    else:
        consistency = None
        csep_val = None

    return {
        "csep": csep_val,
        "coverage": coverage,
        "consistency": consistency,
        "per_shot_e_tilde": e_tilde,
        "n_applicable": len(e_tilde),
    }
