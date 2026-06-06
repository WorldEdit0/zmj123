"""CSEP_v2 — DEPRECATED.  Use ``mseditbench.metrics.csep_v3.csep_v3`` for headline.

⚠️  This is the v2 metric (DINOv2 cross-shot consistency × CLIP-T-derived
    coverage). Retained for ablation.

Why deprecated:
    Inherits the v2 EE problems (coverage from CLIP-T uplift is a weak
    signal). v3 replaces both halves with VLM-as-Judge.

v2.1 design:
    coverage    = mean over applicable shots of EE_v2 per-shot                ∈ [0, 1]
    consistency = mean pairwise DINOv2 cosine sim between applicable
                  edit shots' mid-frame embeddings (masked when avail.)        ∈ [0, 1]

    CSEP = √(coverage × consistency)              # geometric mean

Why geometric mean (not product, not harmonic):
  - Product (cov × cons): too punishing — coverage of 0.4 and consistency of
    0.9 gives 0.36, far below either component.
  - Harmonic mean: even more punishing — drops to 0 if either component is 0.
  - Geometric mean √(cov × cons) is the natural compromise: it goes to 0 iff
    one component is 0, but stays close to the smaller of the two without
    being aggressive about it. cov=0.4, cons=0.9 → √0.36 = 0.60.

Why DINOv2 for consistency:
  - DINOv2 captures visual identity / texture / style well across viewpoints.
  - Far more reliable than CLIP-T deltas (which were used in v1 CSEP) for
    measuring whether the same edited entity appears across shots.
  - Mask-aware when available; falls back gracefully to whole-frame.

Returns None when fewer than 2 applicable shots (no pairs).
"""
from __future__ import annotations
import itertools
import numpy as np
from . import backends as B


def _cos(a: np.ndarray, b: np.ndarray, eps: float = 1e-8) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < eps or nb < eps:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def csep_v2(
    per_shot_edit_frames: dict[int, np.ndarray],
    applicable_shots: list[int],
    per_shot_ee_v2: dict[int, float],     # from ee_v2 output, used as coverage
    dino_backend=None,
    per_shot_masks: dict[int, np.ndarray] | None = None,
) -> dict:
    """Compute CSEP_v2 for one (video, edit) pair.

    Returns:
        {csep, coverage, consistency, n_applicable, pair_similarities}
        csep is None when fewer than 2 applicable shots had frames.
    """
    if dino_backend is None:
        dino_backend = B.get_dino("mock")

    edit_feat = {}
    for k in applicable_shots:
        if k not in per_shot_edit_frames:
            continue
        ef = per_shot_edit_frames[k]
        if len(ef) == 0:
            continue
        m = (per_shot_masks or {}).get(k)
        if m is not None:
            ef_masked = (ef.astype(np.float32) * m[None, ..., None]).astype(np.uint8)
        else:
            ef_masked = ef
        feats = dino_backend.embed_frames(ef_masked)        # [T, D] L2-norm
        v = feats.mean(0)
        v = v / (np.linalg.norm(v) + 1e-8)
        edit_feat[k] = v.astype(np.float32)

    if len(edit_feat) < 2:
        return {"csep": None, "coverage": None, "consistency": None,
                "n_applicable": len(edit_feat), "reason": "<2 applicable shots"}

    keys = sorted(edit_feat.keys())
    pair_sims = [_cos(edit_feat[a], edit_feat[b])
                 for a, b in itertools.combinations(keys, 2)]
    consistency = float(np.mean(pair_sims))
    consistency = max(0.0, min(1.0, consistency))   # clip neg / >1 numerical noise

    coverage_vals = [per_shot_ee_v2.get(k, 0.0) for k in keys]
    coverage = float(np.mean(coverage_vals))
    coverage = max(0.0, min(1.0, coverage))

    csep_val = float(np.sqrt(coverage * consistency))
    return {
        "csep": csep_val,
        "coverage": coverage,
        "consistency": consistency,
        "n_applicable": len(edit_feat),
        "pair_similarities": pair_sims,
    }
