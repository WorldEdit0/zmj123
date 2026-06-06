"""Cross-Shot Identity (CXS-ID) with anti-copy-paste floor. RESEARCH_PLAN.md §4.3

For each entity that appears in >=2 shots, compute mean cosine sim across
shot pairs (a), then multiply by ACP-floor (b) which suppresses scores
when within-shot frame variance is too low (i.e. the model emitted a static
copy of one frame).

phi_e: ArcFace for faces, DINOv2 patch embedding for non-face entities.
"""

from __future__ import annotations
import numpy as np
import itertools
from . import backends as B


def cxs_id_one_entity(
    per_shot_embeddings: dict[int, np.ndarray],
    tau_acp: float = 0.05,
) -> dict:
    """per_shot_embeddings[k]: [T_k, D] frame-level embeddings (already L2-normed).

    Returns {cxs_id, raw_pairwise, acp_factor, intra_std, n_pairs}.
    """
    # 中文注释：CXS-ID 衡量同一实体在多个 shot 中的身份一致性。
    # 输入已经是每个 shot 内的帧级 embedding，这里只负责聚合和惩罚静态复制。
    shots = sorted(per_shot_embeddings.keys())
    if len(shots) < 2:
        # 中文注释：少于两个 shot 无法计算“跨镜头”身份一致性。
        return {"cxs_id": None, "raw_pairwise": None, "acp_factor": None,
                "intra_std": None, "n_pairs": 0}

    # 中文注释：先把每个 shot 的帧级 embedding 平均成一个 shot-level 身份向量。
    means = {k: per_shot_embeddings[k].mean(axis=0) for k in shots}
    means = {k: m / (np.linalg.norm(m) + 1e-8) for k, m in means.items()}

    # 中文注释：raw_pairwise 是所有 shot pair 的 cosine similarity 平均值。
    sims = []
    for i, j in itertools.combinations(shots, 2):
        sims.append(float(np.dot(means[i], means[j])))
    raw = float(np.mean(sims))

    # 中文注释：ACP floor 用 shot 内帧 embedding 方差检测静态复制。
    # 如果一个 shot 内几乎没有变化，可能是模型复制了同一帧，
    # 即便跨镜头 identity 很像，也不应拿满分。
    intra_stds = []
    for k in shots:
        emb = per_shot_embeddings[k]
        if emb.shape[0] < 2:
            continue
        intra_stds.append(float(emb.std(axis=0).mean()))
    intra_std = float(np.mean(intra_stds)) if intra_stds else 0.0
    acp = float(min(1.0, intra_std / tau_acp)) if tau_acp > 0 else 1.0

    return {
        # 中文注释：最终 CXS-ID = 跨镜头身份相似度 × 反复制粘贴因子。
        "cxs_id": raw * acp,
        "raw_pairwise": raw,
        "acp_factor": acp,
        "intra_std": intra_std,
        "n_pairs": len(sims),
    }


def cxs_id(
    entities: list[dict],
    tau_acp: float = 0.05,
) -> dict:
    """entities: [{entity_id, per_shot_embeddings}, ...]
    Returns {cxs_id_mean, per_entity}. Entities with <2 shots are skipped.
    """
    # 中文注释：对每个实体单独计算 CXS-ID，再对可评分实体求平均。
    # 只出现在一个 shot 的实体会被跳过，因为没有跨镜头一致性可言。
    per_entity = {}
    for ent in entities:
        r = cxs_id_one_entity(ent["per_shot_embeddings"], tau_acp=tau_acp)
        per_entity[ent["entity_id"]] = r

    scored = [r["cxs_id"] for r in per_entity.values() if r["cxs_id"] is not None]
    return {
        "cxs_id_mean": float(np.mean(scored)) if scored else None,
        "n_entities_scored": len(scored),
        "per_entity": per_entity,
    }
