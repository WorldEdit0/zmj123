"""Side-Effect Score (SES).  RESEARCH_PLAN.md §4.4

SES = 1 - max(IDdrift, OffTarget).  Higher is better; clipped to [0,1].

IDdrift  = drop in mean CXS-ID for entities that should have been preserved.
OffTarget = average positive CLIP-T delta on shots in S_abs (shots that should
not have been touched).
"""

from __future__ import annotations
import numpy as np
from . import backends as B


def off_target(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames: dict[int, np.ndarray],
    absent_shots: list[int],
    target_phrase: str,
    clip_backend=None,
    tau_ot: float = 0.02,
) -> dict:
    """Returns {off_target_mean, per_shot_delta, n_absent}.

    Per shot: max(0, CLIP-T(edit) - CLIP-T(source) - tau_ot). Mean over absent
    shots. tau_ot is a small slack so we don't punish noise-level drifts.
    """
    # 中文注释：off_target 专门看“不应该出现目标编辑”的 absent_shots。
    # 如果编辑后这些 shot 和 target_phrase 的 CLIP-T 相似度明显上升，
    # 说明模型把编辑扩散到了不该改的地方。
    if clip_backend is None:
        clip_backend = B.get_clip("mock")
    deltas = {}
    for k in absent_shots:
        if k not in per_shot_source_frames or k not in per_shot_edit_frames:
            continue
        s = clip_backend.score_video_text(per_shot_source_frames[k].astype(np.uint8), target_phrase)
        e = clip_backend.score_video_text(per_shot_edit_frames[k].astype(np.uint8), target_phrase)
        # 中文注释：tau_ot 是容忍阈值，过滤掉 CLIP 噪声级别的小波动；
        # 只有超过阈值的正向增长才被当作非目标副作用。
        deltas[k] = float(max(0.0, (e - s) - tau_ot))
    if not deltas:
        # 中文注释：没有 absent shot 可评估时，不对 off-target 施加惩罚。
        return {"off_target_mean": 0.0, "per_shot_delta": {}, "n_absent": 0}
    return {
        # 中文注释：off_target_mean 越大，说明非目标区域越可能被错误编辑。
        "off_target_mean": float(np.mean(list(deltas.values()))),
        "per_shot_delta": deltas,
        "n_absent": len(deltas),
    }


def ses(
    id_drift: float | None,
    off_target_mean: float,
) -> dict:
    """SES = 1 - max(IDdrift, OffTarget). IDdrift may be None (no preserve set)."""
    # 中文注释：SES 取“身份漂移”和“非目标副作用”中更严重的那个作为惩罚。
    # 这样只要任一类副作用很大，安全性分数就会明显下降。
    components = []
    if id_drift is not None:
        # 中文注释：id_drift=None 表示该任务/样本无法评估身份保持，
        # 不是把身份漂移当作 0 分处理。
        components.append(max(0.0, float(id_drift)))
    components.append(max(0.0, float(off_target_mean)))
    worst = max(components) if components else 0.0
    return {
        # 中文注释：SES 越高越好，最终裁剪到 [0,1]，避免异常后端值越界。
        "ses": float(max(0.0, min(1.0, 1.0 - worst))),
        "id_drift": id_drift,
        "off_target": off_target_mean,
        "worst_component": worst,
    }
