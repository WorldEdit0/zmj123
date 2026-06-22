"""CSEP_v3 — VLM-as-Judge Cross-Shot Edit Consistency.

For each pair of applicable shots (k1, k2), ask a VLM to rate how
consistent the edited entity / style / appearance is across the two shots.
Aggregate as:
    consistency = mean over pairs of pair_ratings
    coverage    = mean over applicable shots of EE_v3 per-shot rating
    CSEP_v3     = sqrt(coverage × consistency)

Returns None if fewer than 2 applicable shots (no pairs).

Important: CSEP_v3 deliberately does not compare against source frames. It
only checks whether edited shots agree with each other. The coverage term
from EE_v3 is what prevents "all shots are consistently unedited" from
receiving a high score.

Why VLM-pairwise instead of DINOv2-pairwise:
  - DINOv2 measures visual identity but doesn't know the EDIT context.
    Two shots could be very similar in DINO space because the editor failed
    to apply any change (preserving source) — DINO would call this consistent
    even though the edit didn't propagate.
  - A VLM can be asked the right question: "Are these two frames showing the
    same edited result for the instructed change?" — this is task-aware.
  - Pro tends to produce coherent multi-shot edits with consistent character
    appearance; Fast can drift more. VLM picks this up; DINO doesn't.
"""
from __future__ import annotations
import os
import itertools
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from . import backends as B


_CSEP_PROMPT_TEMPLATE = """You are a STRICT visual judge of multi-shot video edits. Be critical.

[FRAME-SET A] is from one shot of an EDITED video.
[FRAME-SET B] is from another shot of the SAME EDITED video.

The user's edit instruction was:
"{instruction}"

Rate how CONSISTENT the two shots are at showing the SAME edited result, on a 0-5 INTEGER scale considering:
  - same edited entity (same character / object appearance, not different ones)
  - same style / treatment (lighting, color grading, finish)
  - same level of edit applied (not one shot edited and the other not)

Evaluation scope:
- Both frame sets are already selected from shots where this same requested edit should be evaluated.
- Compare only the visible evidence relevant to the requested edit in each frame set.
- The edited target may be visible only in part. Judge whether the visible parts in both frame sets are consistent with the same requested edit.
- Do not require the same crop, pose, full body, full object, or viewpoint across shots.
- If one frame set has no relevant visible evidence for the requested edit, the consistency is unverifiable and should receive a low score.

Judge only the requested edit above. Ignore unrelated edits, unrelated scene changes,
and source preservation issues unless they make the requested edit impossible to compare.

STRICT SCALE — most multi-shot edits drift; reserve 5 for genuinely identical-feeling results:
  0 = totally inconsistent, with clearly different or missing edited results across the two frame sets
  1 = barely consistent or not enough relevant visible evidence to compare
  2 = noticeable inconsistency (different colors / proportions / details)
  3 = mostly consistent, minor drift
  4 = strongly consistent, only tiny variations
  5 = perfectly consistent — same edited result in both shots

Output ONLY a single integer 0-5. No explanation."""


def _build_prompt(instruction: str) -> str:
    # 中文注释：CSEP 的 prompt 不看 source，只比较两个 edited shot
    # 是否呈现同一个编辑结果，因此只需要原始编辑指令作为上下文。
    return _CSEP_PROMPT_TEMPLATE.format(instruction=(instruction or "").strip())


def csep_v3(
    per_shot_edit_frames: dict[int, np.ndarray],
    applicable_shots: list[int],
    per_shot_ee_v3: dict[int, float],     # from ee_v3 output
    instruction: str,
    vlm_backend=None,
    vlm_max_workers: int | None = None,
) -> dict:
    """Pairwise VLM consistency rating × EE_v3 coverage, geometric mean."""
    # 中文注释：CSEP_v3 由两部分组成：
    # 1) consistency：已编辑镜头之间看起来是否一致；
    # 2) coverage：这些镜头是否真的完成了编辑（来自 EE_v3 per-shot 分）。
    # 最终用几何平均，避免“没编辑但很一致”的结果拿高分。
    if vlm_backend is None:
        vlm_backend = B.get_vlm("mock")
    if vlm_max_workers is None:
        vlm_max_workers = int(os.environ.get("VLM_MAX_WORKERS", 8))
    if getattr(vlm_backend, "is_local_model", False):
        vlm_max_workers = 1

    # 中文注释：只保留 applicable 且存在编辑帧的 shot。
    valid_shots = [
        k for k in applicable_shots
        if k in per_shot_edit_frames and len(per_shot_edit_frames[k])
    ]
    if len(valid_shots) < 2:
        # 中文注释：少于两个 shot 没法定义“跨镜头一致性”。
        return {"csep": None, "coverage": None, "consistency": None,
                "n_applicable": len(valid_shots),
                "reason": "<2 applicable shots"}

    # 中文注释：对所有 applicable shot 做两两组合，逐对判断一致性。
    pairs = list(itertools.combinations(sorted(valid_shots), 2))
    prompt = _build_prompt(instruction)

    def _score_pair(pair):
        a, b = pair
        try:
            # 中文注释：这里的 A/B 都来自编辑后视频的不同 shot；
            # VLM 只判断二者是否显示同一个编辑结果。rate_pair 会在后端内部
            # 从每个 shot 的 frame set 中抽少量帧给 VLM 看。
            r = vlm_backend.rate_pair(
                per_shot_edit_frames[a],
                per_shot_edit_frames[b],
                prompt, max_score=5,
            )
        except Exception as e:
            return pair, None, f"error: {type(e).__name__}: {e}"
        return pair, r, None

    pair_scores = {}
    with ThreadPoolExecutor(max_workers=min(vlm_max_workers, max(1, len(pairs)))) as ex:
        for pair, r, err in ex.map(_score_pair, pairs):
            # 中文注释：pair VLM 调用失败时记 0 分，并保留 raw/error 用于诊断。
            pair_scores[pair] = {"score": r if r is not None else 0.0,
                                 "raw": r, "error": err}

    # 中文注释：consistency 是所有 shot pair 的一致性评分平均值。
    scores = [v["score"] for v in pair_scores.values()]
    consistency = float(np.mean(scores)) if scores else 0.0
    consistency = max(0.0, min(1.0, consistency))

    # 中文注释：coverage 复用 EE_v3 的逐镜头编辑有效性分数。
    # 如果某个 shot 没有 EE_v3 分数，按 0 处理，防止漏评提高分数。
    cov_vals = [per_shot_ee_v3.get(k, 0.0) for k in valid_shots]
    coverage = float(np.mean(cov_vals)) if cov_vals else 0.0
    coverage = max(0.0, min(1.0, coverage))

    # 中文注释：sqrt(coverage * consistency) 是几何平均形式；
    # 任一项低都会拉低最终 CSEP_v3。
    csep_val = float(np.sqrt(coverage * consistency))
    return {
        "csep": csep_val,
        "coverage": coverage,
        "consistency": consistency,
        "n_applicable": len(valid_shots),
        "n_pairs": len(pairs),
        "pair_scores": {f"{a}-{b}": v["score"] for (a,b), v in pair_scores.items()},
    }
