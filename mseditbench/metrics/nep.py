"""Non-Edit Preservation (NEP).  RESEARCH_PLAN.md §4.4

Source-aligned per-shot DINO similarity over a mask-derived region. The
default is the *complement* of the edit mask. T8 background replacement uses
the foreground preserve mask itself. Per-shot, never cross-shot — that's the
whole point of this design:
cross-cut DINO is meaningless since the next shot is intentionally different.

If a caller has known non-comparable shots, pass shot_id in skip_shots so
they do not pull the average down.

For local edit tasks, pass require_masks=True so shots without a valid edit
region mask are skipped instead of falling back to whole-frame similarity.
"""

from __future__ import annotations
import numpy as np
from . import backends as B


def nep(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames: dict[int, np.ndarray],
    per_shot_edit_masks: dict[int, np.ndarray] | None = None,
    skip_shots: list[int] | None = None,
    dino_backend=None,
    require_masks: bool = False,
    mask_mode: str = "complement",
) -> dict:
    """Returns dict {nep, per_shot_nep, n_scored, n_skipped}.

    mask_mode:
        "complement" scores outside the mask, for ordinary local edits.
        "inside" scores inside the mask, for foreground-preservation tasks.
    """
    # 中文注释：NEP 衡量“没有被要求编辑的区域是否保留”。
    # 它按同一个 shot 内的 source/edit 对齐比较，不跨 shot 比较，
    # 因为多镜头视频中相邻 shot 本来就是不同画面。
    if dino_backend is None:
        dino_backend = B.get_dino("mock")
    skip_shots = set(skip_shots or [])

    per_shot, n_skipped = {}, 0
    n_mask_missing = 0
    for k, sf in per_shot_source_frames.items():
        if k in skip_shots or k not in per_shot_edit_frames:
            # 中文注释：显式跳过的镜头或缺失的编辑镜头不能和源镜头逐帧对齐，
            # 因此不把它们当作低分。
            n_skipped += 1
            continue
        ef = per_shot_edit_frames[k]
        m = (per_shot_edit_masks or {}).get(k)
        if require_masks and m is None:
            # 中文注释：局部编辑任务必须有“允许变化区域”mask，才能定义
            # mask 外的 NEP；缺 mask 时不要退回整帧相似度，否则会把编辑目标
            # 本身也算进 preservation。
            n_skipped += 1
            n_mask_missing += 1
            continue
        if m is not None:
            if mask_mode == "inside":
                region = m
            elif mask_mode == "complement":
                # 中文注释：默认情况下 mask 表示编辑目标区域；NEP 要评估
                # 非目标区域，所以取反 mask，只比较 mask 外的背景/未编辑区域。
                region = 1.0 - m
            else:
                raise ValueError(f"unknown NEP mask_mode: {mask_mode}")
            sf = (sf * region[..., None]).astype(np.uint8)
            ef = (ef * region[..., None]).astype(np.uint8)
        # 中文注释：每帧先提 DINO embedding，再对一个 shot 内所有帧求平均，
        # 得到该 shot 的语义/视觉表示，最后和源 shot 做 cosine similarity。
        es = dino_backend.embed_frames(sf).mean(axis=0)
        ee = dino_backend.embed_frames(ef).mean(axis=0)
        per_shot[k] = float(dino_backend.similarity(es, ee))

    if not per_shot:
        # 中文注释：没有任何可评分 shot 时，返回 None 作为“不可评估”。
        reason = None
        if require_masks and n_mask_missing:
            reason = "required edit-region masks were missing"
        return {
            "nep": None,
            "per_shot_nep": {},
            "n_scored": 0,
            "n_skipped": n_skipped,
            "n_mask_missing": n_mask_missing,
            "mask_mode": mask_mode,
            "reason": reason,
        }

    return {
        # 中文注释：最终 NEP 是所有可评分 shot 的保留相似度平均值。
        "nep": float(np.mean(list(per_shot.values()))),
        "per_shot_nep": per_shot,
        "n_scored": len(per_shot),
        "n_skipped": n_skipped,
        "n_mask_missing": n_mask_missing,
        "mask_mode": mask_mode,
    }
