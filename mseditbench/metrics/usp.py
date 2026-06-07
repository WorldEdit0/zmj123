"""Unedited Shot Preservation (USP).

USP replaces the old SES headline metric.

Definition:
    USP = mean_k DINOv2(source_shot_k, edited_shot_k)

where k ranges only over source shots that are not listed in
``edit.applicable_shots``. The raw DINO cosine is clipped to [0, 1]. It is a
pure content-preservation score:

- no face / ArcFace identity drift term
- no CLIP text off-target term
- no spatial mask term

If a prompt edits every shot, USP is undefined and returns ``None`` rather
than pretending that preservation is either perfect or failed.
"""

from __future__ import annotations

import numpy as np

from . import backends as B


def usp(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames: dict[int, np.ndarray],
    unedited_shots: list[int],
    dino_backend=None,
) -> dict:
    """Return DINOv2 similarity on shots that should not be edited.

    Returns:
        {
          "usp": float | None,
          "per_shot_usp": {shot_id: score},
          "n_scored": int,
          "n_unedited": int,
          "n_missing": int,
          "reason": str | None,
        }
    """
    if dino_backend is None:
        dino_backend = B.get_dino("mock")

    per_shot: dict[int, float] = {}
    n_missing = 0
    for shot_id in unedited_shots:
        if shot_id not in per_shot_source_frames or shot_id not in per_shot_edit_frames:
            n_missing += 1
            continue
        sf = per_shot_source_frames[shot_id]
        ef = per_shot_edit_frames[shot_id]
        if len(sf) == 0 or len(ef) == 0:
            n_missing += 1
            continue

        src_emb = dino_backend.embed_frames(sf).mean(axis=0)
        edt_emb = dino_backend.embed_frames(ef).mean(axis=0)
        sim = float(dino_backend.similarity(src_emb, edt_emb))
        per_shot[int(shot_id)] = max(0.0, min(1.0, sim))

    if not unedited_shots:
        return {
            "usp": None,
            "per_shot_usp": {},
            "n_scored": 0,
            "n_unedited": 0,
            "n_missing": 0,
            "reason": "no unedited shots for this prompt",
        }
    if not per_shot:
        return {
            "usp": None,
            "per_shot_usp": {},
            "n_scored": 0,
            "n_unedited": len(unedited_shots),
            "n_missing": n_missing,
            "reason": "unedited shots were missing or unreadable",
        }

    return {
        "usp": float(np.mean(list(per_shot.values()))),
        "per_shot_usp": per_shot,
        "n_scored": len(per_shot),
        "n_unedited": len(unedited_shots),
        "n_missing": n_missing,
        "reason": None,
    }
