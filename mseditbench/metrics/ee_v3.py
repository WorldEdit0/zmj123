"""EE_v3 — VLM-as-Judge Edit Effectiveness.

Iteration history:
  v2.0 / v2.1: CLIP-T directional / continuous uplift. Rejected because:
    - CLIP image embedding is dominated by overall scene composition,
      so signal is weak even when humans clearly see a successful edit
    - CLIP rewards "any movement in the right direction", not "the edit
      actually succeeded with high quality"
    - Stronger model (Pro) didn't outperform weaker (Fast) under CLIP-T
      because Pro does larger, more polished re-renders that don't translate
      into bigger CLIP-T deltas vs. Fast's small targeted nudges.

  v3 design — let a VLM judge: human-aligned signal.
    For each applicable shot k:
      1) sample N matched source/edit frame pairs at the same relative
         timestamps inside the shot. N = EE_V3_FRAME_PAIRS, default 3.
      2) ask the VLM to score each image pair on a 0-5 edit-success scale.
      3) normalise each score to [0,1] and average those frame-pair scores
         into the shot score ee_k.
    EE_v3 = mean over applicable shot scores.

Why this should work where CLIP-T failed:
  - VLM sees the images directly, reads the instruction in context, and
    judges with semantic reasoning — not surface text-image similarity.
  - VLM judges only whether the requested edit happened. Preservation,
    cross-shot consistency, and general visual quality are intentionally
    left to NEP/CSEP/PSQ so metric meanings stay disentangled.
  - Continuous score (0-5) avoids binary-threshold pathologies of v1.

VLM choice (default): Seed 2.0 Lite via Volcengine Ark (already wired in
backends._make_seed_vlm). Strong VLM, cheap, fast enough.

Calls per prompt: K × applicable_shots × EE_V3_FRAME_PAIRS. With local
Qwen3-VL, this controls runtime directly; smoke tests usually set
EE_V3_FRAME_PAIRS=1, while full evaluation can use the default 3.

Returns:
    {ee, per_shot, n_applicable, prompt}
    Returns None for ee if no applicable shots had frames.
"""
from __future__ import annotations
import os
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from . import backends as B


# Single-shot rating prompt. VLM-visible inputs are only:
# ORIGINAL image, EDITED image, and the requested edit text.
# Internal benchmark metadata stays outside the prompt for attribution/routing.
_EE_PROMPT_TEMPLATE = """You are a strict visual judge of edit effectiveness.

You are shown two corresponding images:
- ORIGINAL: the source image before editing.
- EDITED: the generated image after editing.

Your only job is to decide whether the requested edit is visible and correctly applied in EDITED compared with ORIGINAL.

Requested edit:
"{edit_request}"

Evaluation scope:
- This image pair is already selected from a shot where the requested edit should be evaluated.
- Judge only the visible evidence in this image pair for the requested edit.
- If the edited subject or object is only partially visible, evaluate whether the visible part reflects the requested edit.
- Do not require a full body, full object, or canonical view when the shot framing or occlusion only shows part of the edited target.
- If no relevant part of the edited target is visible in either image, treat the result as unverifiable and give a low ambiguity score instead of guessing.

Judging rules:
- Score only the requested edit above.
- Do not judge background preservation, identity preservation, temporal consistency, or overall image quality.
- Ignore unrelated changes unless they make it impossible to verify whether the requested edit happened.
- If another edit is also visible, ignore it and judge only the requested edit above.
- For global edits such as style, lighting, background, or camera/framing changes, judge only that requested visual axis.

Score 0-5:
0 = relevant visual evidence is visible but the requested edit is absent, opposite, or applied to the wrong target.
1 = the requested edit is barely visible, highly ambiguous, or the relevant visual evidence is not visible enough to verify.
2 = the requested edit is partially attempted but mostly incorrect or too weak.
3 = the requested edit is clearly present but incomplete, weak, or only partly correct.
4 = the requested edit is mostly correct and easy to verify, with minor misses.
5 = the requested edit is fully and unambiguously achieved.

Output ONLY one integer from 0 to 5. No explanation."""


def _build_prompt(instruction: str, target_phrase: str) -> str:
    # 中文注释：VLM 只看直接可理解的编辑要求，不看 task_id/shot_id/edit_type
    # 等 benchmark metadata。target_phrase 仅作为旧数据缺少 instruction 时的后备。
    # 模板要求 VLM 只输出 0-5 的整数，后端再归一化到 [0,1]。
    edit_request = (instruction or "").strip() or (target_phrase or "").strip()
    return _EE_PROMPT_TEMPLATE.format(
        edit_request=edit_request or "the requested edit",
    )


def ee_v3(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames:   dict[int, np.ndarray],
    applicable_shots: list[int],
    instruction: str,
    target_phrase: str,
    vlm_backend=None,
    vlm_max_workers: int | None = None,
    frame_pairs_per_shot: int | None = None,
) -> dict:
    """Matched-frame VLM rating; mean over frames, then over applicable shots."""
    # 中文注释：EE_v3 是当前 headline 的编辑有效性指标。
    # 它不依赖 CLIP-T 的文本图像相似度增量，而是让 VLM 直接比较
    # source frames 和 edited frames，判断指令是否被成功执行。
    if vlm_backend is None:
        vlm_backend = B.get_vlm("mock")
    if vlm_max_workers is None:
        vlm_max_workers = int(os.environ.get("VLM_MAX_WORKERS", 8))
    if frame_pairs_per_shot is None:
        frame_pairs_per_shot = int(os.environ.get("EE_V3_FRAME_PAIRS", 3))
    if getattr(vlm_backend, "is_local_model", False):
        # Local VLM generation is GPU-bound and model objects are generally not
        # thread-safe; keep calls serial even if VLM_MAX_WORKERS is high.
        vlm_max_workers = 1

    prompt = _build_prompt(instruction, target_phrase)

    # 中文注释：只评估 applicable_shots，并且要求 source/edit 两边都有帧。
    # 缺帧的 shot 不能可靠比较，直接排除。
    valid_shots = [
        k for k in applicable_shots
        if k in per_shot_source_frames and k in per_shot_edit_frames
        and len(per_shot_source_frames[k]) and len(per_shot_edit_frames[k])
    ]
    if not valid_shots:
        # 中文注释：没有有效 shot 时返回 None，表示该样本不可评估 EE。
        return {"ee": None, "per_shot": {}, "n_applicable": 0,
                "reason": "no applicable shots had frames"}

    def _pair_indices(n_src: int, n_edit: int) -> list[tuple[int, int]]:
        # 中文注释：source/edit 每个 shot 内可能抽到的帧数不同；
        # 这里只在共同长度 n 内按等间距取点，保证比较的是同一相对时间位置。
        n = min(n_src, n_edit)
        if n <= 0:
            return []
        m = min(max(1, frame_pairs_per_shot), n)
        if m == 1:
            # 中文注释：单帧 smoke / 快速评测时取 shot 中间位置，
            # 比取第 0 帧更能代表该 shot 的主体内容。
            mid = (n - 1) // 2
            return [(int(mid), int(mid))]
        idx = np.linspace(0, n - 1, m).round().astype(int)
        return [(int(i), int(i)) for i in idx]

    def _score_shot(k):
        # 中文注释：每个 shot 内按相同相对时间点抽取 source/edit 帧对，
        # 逐对让 VLM 评分，再对这些帧对取平均，得到该 shot 的 EE。
        sf = per_shot_source_frames[k]
        ef = per_shot_edit_frames[k]
        frame_rows = []
        try:
            for si, ei in _pair_indices(len(sf), len(ef)):
                r = vlm_backend.rate_image_pair(sf[si], ef[ei], prompt, max_score=5)
                frame_rows.append({
                    # 中文注释：source_idx/edit_idx 是该 shot 内被抽中的帧序号；
                    # ee 是归一化后的帧对分数，raw 保留后端原始解析结果。
                    "source_idx": si,
                    "edit_idx": ei,
                    "ee": r if r is not None else 0.0,
                    "raw": r,
                })
        except Exception as e:
            return k, None, [], f"error: {type(e).__name__}: {e}"
        if not frame_rows:
            return k, None, [], "no matched frames"
        shot_score = float(np.mean([x["ee"] for x in frame_rows]))
        return k, shot_score, frame_rows, None

    per_shot = {}
    with ThreadPoolExecutor(max_workers=min(vlm_max_workers, max(1, len(valid_shots)))) as ex:
        for k, r, frame_rows, err in ex.map(_score_shot, valid_shots):
            # 中文注释：VLM 调用失败时该 shot 记 0 分，同时保留 per-frame/raw/error 方便排查。
            per_shot[k] = {
                "ee": r if r is not None else 0.0,
                "raw": r,
                "frames": frame_rows,
                "error": err,
            }

    scores = [v["ee"] for v in per_shot.values()]
    ee_mean = float(np.mean(scores)) if scores else None
    return {
        # 中文注释：最终 EE_v3 是所有 applicable shot 的 VLM 分数平均值。
        "ee": ee_mean,
        "per_shot": per_shot,
        "n_applicable": len(per_shot),
        "frame_pairs_per_shot": frame_pairs_per_shot,
        "prompt_template": "v3-ee-edit-only-image-pair-rating",
    }
