"""Per-Shot Quality (PSQ) and intra-shot temporal metrics. RESEARCH_PLAN.md §4.2

PSQ = mean over shots of 0.5 * (MUSIQ/100 + LAIONAes/10).

We provide the formula skeleton. Real MUSIQ / LAIONAes weights are heavy and
left to the runtime backend; the mock backend returns deterministic [0,1]
scores so unit tests still verify the aggregation logic.
"""

from __future__ import annotations
import numpy as np
import hashlib


def _mock_quality(frames: np.ndarray) -> tuple[float, float]:
    """Returns (musiq_in_0_100, laion_in_0_10)."""
    # 中文注释：mock 后端不做真实图像质量评估，只把帧内容哈希成稳定分数。
    # 这样单元测试可以验证 PSQ 的聚合逻辑，而不依赖 pyiqa 权重或 GPU。
    h = hashlib.md5(frames.tobytes()).digest()
    a = int.from_bytes(h[:4], "big") / 0xFFFFFFFF
    b = int.from_bytes(h[4:8], "big") / 0xFFFFFFFF
    return 50 + 30 * a, 5 + 3 * b


def psq(
    per_shot_frames: dict[int, np.ndarray],
    musiq_fn=_mock_quality,
) -> dict:
    """musiq_fn: frames -> (musiq, laionaes). Default: mock.

    Returns {psq, per_shot_psq}.
    """
    # 中文注释：PSQ 只看“编辑后视频本身”的视觉质量，不和源视频做对比。
    # 每个 shot 独立评分，再对所有 shot 求平均，避免长镜头天然占更大权重。
    per_shot = {}
    for k, fr in per_shot_frames.items():
        # 中文注释：真实后端返回 MUSIQ(0-100) 和 LAION-Aes(0-10)。
        # 这里先统一归一化到 [0,1]，再等权平均成单个 shot 质量分。
        m, a = musiq_fn(fr)
        per_shot[k] = 0.5 * (m / 100.0 + a / 10.0)
    if not per_shot:
        # 中文注释：没有可评分镜头时返回 None，而不是 0；
        # None 表示“缺失/不可评估”，0 表示“质量极差”，语义不同。
        return {"psq": None, "per_shot_psq": {}}
    return {
        # 中文注释：最终 PSQ 是 shot-level PSQ 的算术平均。
        "psq": float(np.mean(list(per_shot.values()))),
        "per_shot_psq": per_shot,
    }
