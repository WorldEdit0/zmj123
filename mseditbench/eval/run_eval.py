"""Eval orchestrator: score one (prompt sample, baseline output) pair.

Given:
    sample (EditPromptSample dict from edit_prompts/) — has source_video, shots, edit
    edited_video_path                              — output from a baseline
Compute:
    PSQ, EE_v3, NEP, CSEP_v3, USP, TAC

Outputs are saved as one EvalResult JSON per (sample, baseline) pair.

CLI:
    python -m mseditbench.eval.run_eval \
        --prompts_json runs/edit_prompts_v2_10s/T1.json \
        --baseline_dir runs/seedance_v2v_edit_v2_10s/videos/T1 \
        --videos_root data/source_videos_10s/videos \
        --output_dir runs/eval_seedance_v2v_v2_10s_v3/T1 \
        --baseline seedance_v2v \
        --backend_dino mock --backend_vlm mock --backend_shot none \
        --limit 5

The default mock backends produce deterministic [0,1] scores so the
orchestrator can be exercised without GPU. Swap in real backends with
--backend_dino v2s, --backend_vlm seed, etc when ready.
"""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

import numpy as np
from tqdm import tqdm

from mseditbench import metrics as M
from mseditbench.metrics import backends as B


def _maybe_per_shot_frames(video_path: str, shots: list[dict], stride: int, max_frames: int):
    # 中文注释：把一个视频按 prompt JSON 中的源视频 shot 边界切开，
    # 每个 shot 内按 stride 抽帧，最多 max_frames 帧。普通逐 shot 指标使用
    # 源 shot 边界对齐 source/edit；编辑后真实边界由 TAC 单独检测。
    return M.per_shot_frames(video_path, shots, stride=stride, max_frames=max_frames)


# SAM-3 minimum mask area (pixels). Below this, treat as a miss. For local
# NEP, miss shots are skipped instead of falling back to whole-frame scoring.
_MASK_MIN_PIXELS = 100


def _as_query_list(x) -> list[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x] if x else []
    return [str(v) for v in x if v]


def _legacy_mask_spec(sample: dict) -> dict:
    """Best-effort mask spec for older prompt JSONs without mask_queries."""
    edit = sample["edit"]
    task_id = edit["task_id"]

    if task_id in {"T3", "T5", "T6", "T7"}:
        return {
            "nep_applicable": False,
            "edit_scope": "global_or_structural",
            "edit_type": task_id,
            "source_queries": [],
            "edited_queries": [],
            "combine": "none",
            "reason": f"task {task_id} has no local edit-region mask policy",
        }

    target_entity = edit.get("target_entity")
    if target_entity:
        for c in sample.get("characters", []):
            if c.get("id") == target_entity:
                desc = c.get("desc")
                if desc:
                    return {
                        "nep_applicable": True,
                        "edit_scope": "local",
                        "edit_type": "legacy_entity",
                        "source_queries": [desc],
                        "edited_queries": [],
                        "combine": "union",
                    }

    if task_id == "T4":
        extra = edit.get("extra") or {}
        op = extra.get("op")
        old_object = extra.get("old_object")
        new_object = extra.get("new_object")
        if op == "add":
            source_queries, edited_queries = [], [new_object] if new_object else []
        elif op == "replace":
            source_queries = [old_object] if old_object else []
            edited_queries = [new_object] if new_object else []
        elif op in {"delete", "remove"}:
            source_queries, edited_queries = [old_object] if old_object else [], []
        else:
            source_queries, edited_queries = [], []
        return {
            "nep_applicable": True,
            "edit_scope": "local",
            "edit_type": f"legacy_object_{op}" if op else "legacy_object",
            "source_queries": source_queries,
            "edited_queries": edited_queries,
            "combine": "union",
        }

    return {
        "nep_applicable": True,
        "edit_scope": "local",
        "edit_type": "legacy_target_phrase",
        "source_queries": [],
        "edited_queries": [edit.get("target_phrase")] if edit.get("target_phrase") else [],
        "combine": "union",
    }


def _get_mask_spec(sample: dict) -> dict:
    """Return structured source/edit mask queries for NEP.

    Prompt JSONs may now provide edit.mask_queries with separate queries for
    source frames and edited frames. NEP masks the union of those regions and
    normally evaluates the complement. T8 background replacement sets
    score_region="mask" so NEP evaluates the preserved foreground mask itself.
    This is essential for add/delete/replace: an anchor object is not
    necessarily the edited region.
    """
    spec = sample["edit"].get("mask_queries") or _legacy_mask_spec(sample)
    score_region = spec.get("score_region", "complement")
    if score_region == "mask":
        score_region = "inside"
    return {
        "nep_applicable": bool(spec.get("nep_applicable")),
        "edit_scope": spec.get("edit_scope"),
        "edit_type": spec.get("edit_type"),
        "source_queries": _as_query_list(spec.get("source_queries")),
        "edited_queries": _as_query_list(spec.get("edited_queries")),
        "combine": spec.get("combine", "union"),
        "score_region": score_region,
        "reason": spec.get("reason"),
    }


def _mask_one_frame(mask_backend, frame: np.ndarray, query: str) -> tuple[np.ndarray | None, bool]:
    m3 = mask_backend(frame[None, ...], query)  # [1,H,W]
    m = m3[0]
    hit = bool(m.sum() >= _MASK_MIN_PIXELS)
    return (m if hit else None), hit


def _build_nep_masks(
    sample: dict,
    src_frames: dict[int, np.ndarray],
    edt_frames: dict[int, np.ndarray],
    applicable: list[int],
    mask_backend,
    mask_spec: dict,
) -> tuple[dict[int, np.ndarray] | None, dict]:
    """Build union edit-region masks from source-side and edit-side queries."""
    mask_hits: dict[str, dict] = {}
    if mask_backend is None or not mask_spec.get("nep_applicable"):
        return None, mask_hits

    source_queries = mask_spec.get("source_queries") or []
    edited_queries = mask_spec.get("edited_queries") or []
    if not source_queries and not edited_queries:
        return None, mask_hits

    edit_masks: dict[int, np.ndarray] = {}
    for k, src in src_frames.items():
        if applicable and k not in applicable:
            continue
        shot_hits = {"source": {}, "edited": {}, "used": False}
        masks = []

        if len(src):
            frame = src[len(src) // 2]
            for query in source_queries:
                try:
                    m, hit = _mask_one_frame(mask_backend, frame, query)
                    shot_hits["source"][query] = hit
                    if m is not None:
                        masks.append(m)
                except Exception as e:
                    print(f"[mask] sid={sample['sample_id']} shot={k} source {query!r}: {e}")
                    shot_hits["source"][query] = False

        edt = edt_frames.get(k)
        if edt is not None and len(edt):
            frame = edt[len(edt) // 2]
            for query in edited_queries:
                try:
                    m, hit = _mask_one_frame(mask_backend, frame, query)
                    shot_hits["edited"][query] = hit
                    if m is not None:
                        masks.append(m)
                except Exception as e:
                    print(f"[mask] sid={sample['sample_id']} shot={k} edited {query!r}: {e}")
                    shot_hits["edited"][query] = False

        if masks:
            edit_masks[k] = np.maximum.reduce(masks).astype(np.uint8)
            shot_hits["used"] = True
        mask_hits[str(k)] = shot_hits

    return (edit_masks or None), mask_hits


def _get_v2_text_pair(sample: dict) -> tuple[str, str]:
    """For EE_v2 directional CLIP: pick the (source-anchor, target) text pair.

    The directional formula is cos(img_emb_diff, txt_emb_diff). Both halves of
    the text diff need to be present in the prompt JSON; we pick task-specific
    anchors so the diff vector points cleanly in the requested direction.

      T1 char-replace : characters[target_entity].desc → target_phrase
      T2 attribute    : characters[target_entity].desc → target_phrase
      T3 global style : "the original natural realistic scene" -> target_phrase
                        (no source entity exists, use a generic anchor)
      T7 global light : "the original natural realistic lighting" -> target_phrase
      T8 background   : "the original background" -> target_phrase
      T4 object       : extra.anchor (object class) -> target_phrase
      T5 / T6         : not directional-friendly, return ("", "") and let
                        ee_v2 short-circuit to None
    """
    edit = sample["edit"]
    task_id = edit["task_id"]
    tgt = edit.get("target_phrase", "") or ""

    # Tasks where directional EE doesn't apply
    if task_id in {"T5"}:
        return "", ""

    if task_id == "T3":
        return "the original natural realistic scene", tgt

    if task_id == "T7":
        return "the original natural realistic lighting", tgt

    if task_id == "T8":
        return "the original background", tgt

    if task_id == "T6":
        # T6 = cinematic re-shoot of one shot. target_phrase is e.g. "an
        # over-the-shoulder shot from behind the espresso machine". A generic
        # anchor for "the original framing" is the cleanest direction.
        return "the original camera framing of the scene", tgt

    # T1 / T2: anchor on the source character description
    target_entity = edit.get("target_entity")
    if target_entity:
        for c in sample.get("characters", []):
            if c.get("id") == target_entity:
                desc = c.get("desc")
                if desc:
                    return desc, tgt

    # T1 static replace / T4 object edits: anchor on the source object name
    if task_id in {"T1", "T4"}:
        extra = edit.get("extra") or {}
        old_object = extra.get("old_object")
        if old_object:
            return old_object, tgt
        anchor = extra.get("anchor")
        if anchor:
            return anchor, tgt

    # Last-resort fallback: generic source anchor
    return "the original scene", tgt


# Per-task EE_v2 DELTA_MAX (CLIP-T uplift normalisation constant). Empirical:
# the typical magnitude of a successful edit's delta on this task type, so
# that median good-edit per-shot delta normalises near 0.5-1.0.
#   T1 char-replace  : large entity swap → ~0.05 typical for a strong edit
#   T2 attribute     : subtle apron/hair change → ~0.02 typical
#   T3 style         : whole-frame re-render → ~0.05 typical
#   T4 object        : small object/entity add/delete → ~0.02 typical
#   T6 cinematic     : framing change → ~0.03 typical
#   T7 lighting      : whole-frame relighting -> ~0.04 typical
#   T8 background    : whole-background replacement -> ~0.05 typical
# T5: handled outside EE_v2 (shot-structural).
_DELTA_MAX_PER_TASK = {
    "T1": 0.05,
    "T2": 0.02,
    "T3": 0.05,
    "T4": 0.02,
    "T6": 0.03,
    "T7": 0.04,
    "T8": 0.05,
}


def score_one(
    sample: dict,
    edited_video_path: str,
    videos_root: str,
    baseline_name: str,
    snapshot_id: str,
    dino_backend, vlm_backends,
    stride: int = 4,
    max_frames_per_shot: int = 6,
    src_frames_cached: dict | None = None,  # avoid re-reading source per K
    mask_backend=None,                      # callable (frames, phrase) -> mask, or None
    psq_fn=None,                            # callable frames -> (musiq,laion), or None for default mock
    shot_backend: str = "none",             # "omnishotcut" computes TAC; "none" leaves TAC=None
) -> dict:
    # 中文注释：score_one 是最核心的单个视频样本评分函数。
    # 输入是一条 prompt sample 和某个 baseline 生成的一个视频文件，
    # 输出是一行 eval JSON，包含所有可用指标及调试信息。
    src_path = os.path.join(videos_root, sample["source_video"])
    shots = sample["shots"]
    edit = sample["edit"]
    task_id = edit["task_id"]
    target_phrase = edit["target_phrase"]
    instruction = edit["instruction"]
    applicable = edit.get("applicable_shots", [s["shot_id"] for s in shots])
    unedited = [s["shot_id"] for s in shots if s["shot_id"] not in applicable]

    # 中文注释：source frames 对同一个 prompt 的 K 个输出完全相同，
    # 所以 main() 会缓存一次传进来，避免每个 k 都重复读源视频。
    if src_frames_cached is not None:
        src_frames = src_frames_cached
    else:
        src_frames = _maybe_per_shot_frames(src_path, shots, stride, max_frames_per_shot)
    edt_frames = _maybe_per_shot_frames(edited_video_path, shots, stride, max_frames_per_shot)

    # Per-shot 2D masks for local NEP. Prompt JSON declares source-side and
    # edit-side queries separately; their union is the allowed edit region.
    # EE_v3/CSEP_v3 are VLM full-frame judgments and do not consume masks.
    mask_spec = _get_mask_spec(sample)
    edit_masks, mask_hits = _build_nep_masks(
        sample, src_frames, edt_frames, applicable, mask_backend, mask_spec
    )

    psq_kwargs = {} if psq_fn is None else {"musiq_fn": psq_fn}
    # 中文注释：PSQ 只看编辑后视频的视觉质量，不依赖 source。
    psq_r = M.psq(edt_frames, **psq_kwargs)

    # v1 EE / CSEP — DEPRECATED. Skipped to save VLM tokens. Set fields to None
    # in result dict for backward compat with merge_shards / aggregate.json.
    ee_r = {"ee": None, "per_shot_indicators": {}}
    csep_r = {"csep": None, "coverage": None, "consistency": None,
              "per_shot_e_tilde": {}}

    # 中文注释：NEP 比较 source/edit 的保留区域 DINO 相似度。
    # 普通局部任务用 edit mask 的 complement；T8 背景替换用 foreground
    # preserve mask 内部区域。缺 mask 的 shot 会被 nep(require_masks=True)
    # 跳过，避免回退到整帧相似度。
    if mask_spec.get("nep_applicable"):
        nep_r = M.nep(
            src_frames,
            edt_frames,
            dino_backend=dino_backend,
            per_shot_edit_masks=edit_masks,
            require_masks=True,
            mask_mode=mask_spec.get("score_region", "complement"),
        )
    else:
        nep_r = {
            "nep": None,
            "per_shot_nep": {},
            "n_scored": 0,
            "n_skipped": 0,
            "n_mask_missing": 0,
            "reason": mask_spec.get("reason") or "NEP not applicable for this task",
        }

    # v2 (CLIP-T directional) — also DEPRECATED. Kept None.
    ee2_r = {"ee": None, "per_shot": {}, "n_applicable": 0}
    csep2_r = {"csep": None, "coverage": None, "consistency": None}

    # v3 EE / CSEP — VLM-as-judge headline metrics.
    # Skip for tasks where per-shot VLM rating doesn't make semantic sense.
    if task_id in {"T5"} or mask_spec.get("edit_type") == "transition_style":
        # 中文注释：T5 改变 shot 结构，不适合用“每个原始 shot 是否完成编辑”
        # 来定义 EE/CSEP，所以显式跳过。历史 T7 transition JSON 也跳过；
        # 当前 T7 是全局光照任务，继续走普通 per-shot VLM 判断。
        ee3_r = {"ee": None, "per_shot": {}, "n_applicable": 0,
                 "reason": f"task {task_id} not v3-applicable"}
        csep3_r = {"csep": None, "coverage": None, "consistency": None,
                   "n_applicable": 0}
    else:
        # Pick a single VLM backend (use first; ensemble averaging happens
        # internally via temperature if backend supports it). In future, swap
        # for a 3-VLM ensemble across families.
        vlm = vlm_backends[0] if vlm_backends else None
        # 中文注释：EE_v3 先算每个 applicable shot 的编辑有效性；
        # run_eval 会把逐帧对分数放到 extra.ee_v3_frame_scores 里方便排查。
        ee3_r = M.ee_v3(
            src_frames, edt_frames, applicable, instruction, target_phrase,
            vlm_backend=vlm,
        )
        per_shot_ee3 = {k: v["ee"] for k, v in (ee3_r.get("per_shot") or {}).items()}
        # 中文注释：CSEP_v3 使用 EE_v3 的 per-shot 分数作为 coverage，
        # 再额外判断 edited shots 之间是否一致。
        csep3_r = M.csep_v3(
            edt_frames, applicable, per_shot_ee3, instruction,
            vlm_backend=vlm,
        )

    # USP replaces the old SES. It measures DINOv2 content preservation only
    # on source shots that are not edited by the prompt; no face ID and no CLIP.
    usp_r = M.usp(src_frames, edt_frames, unedited, dino_backend=dino_backend)

    # TAC compares expected source shot time anchors with edited-video shot
    # boundaries detected by OmniShotCut. T5 reorder uses the requested order
    # to build the expected output timeline.
    if task_id == "T5":
        order = (edit.get("extra") or {}).get("new_order")
        expected_order = [int(x) for x in order] if isinstance(order, list) else None
    else:
        expected_order = None
    if shot_backend == "omnishotcut":
        try:
            tac_r = M.temporal_anchor_consistency(
                shots,
                edited_video_path,
                source_video_path=src_path,
                expected_order=expected_order,
            )
        except Exception as e:
            tac_r = {
                "tac": None,
                "shot_count_match": False,
                "expected_count": len(shots),
                "edited_count": None,
                "per_shot_tac": {},
                "mean_anchor_error_sec": None,
                "reason": f"shot detection failed: {type(e).__name__}: {e}",
            }
    else:
        tac_r = {
            "tac": None,
            "shot_count_match": False,
            "expected_count": len(shots),
            "edited_count": None,
            "per_shot_tac": {},
            "mean_anchor_error_sec": None,
            "reason": "shot backend disabled",
        }
    legacy_mask_query = "; ".join(
        (mask_spec.get("source_queries") or []) + (mask_spec.get("edited_queries") or [])
    ) or None

    return {
        "sample_id": sample["sample_id"],
        "video_id": sample["video_id"],
        "task_id": task_id,
        "baseline": baseline_name,
        "snapshot_id": snapshot_id,
        "edited_video_path": edited_video_path,
        "psq": psq_r["psq"],
        "ee": ee_r["ee"],                      # v1 (kept for ablation)
        "ee_v2": ee2_r["ee"],                  # v2 (deprecated)
        "ee_v3": ee3_r.get("ee"),              # ★ v3 headline (VLM-judge)
        "nep": nep_r["nep"],
        "csep": csep_r["csep"],                # v1
        "csep_coverage": csep_r["coverage"],
        "csep_consistency": csep_r["consistency"],
        "csep_v2": csep2_r["csep"],            # v2 (deprecated)
        "csep_v2_coverage": csep2_r["coverage"],
        "csep_v2_consistency": csep2_r["consistency"],
        "csep_v3": csep3_r.get("csep"),        # ★ v3 headline (VLM-judge)
        "csep_v3_coverage": csep3_r.get("coverage"),
        "csep_v3_consistency": csep3_r.get("consistency"),
        "usp": usp_r["usp"],
        "tac": tac_r["tac"],
        "extra": {
            "ee_indicators": ee_r["per_shot_indicators"],
            "csep_per_shot": csep_r["per_shot_e_tilde"],
            "ee_v2_per_shot": ee2_r.get("per_shot") or {},
            "ee_v2_src_text": ee2_r.get("src_text"),
            "ee_v2_tgt_text": ee2_r.get("tgt_text"),
            "csep_v2_pair_similarities": csep2_r.get("pair_similarities") or [],
            "ee_v3_per_shot": {str(k): v.get("ee") for k, v in (ee3_r.get("per_shot") or {}).items()},
            "ee_v3_frame_scores": {
                str(k): v.get("frames") or []
                for k, v in (ee3_r.get("per_shot") or {}).items()
            },
            "csep_v3_pair_scores": csep3_r.get("pair_scores") or {},
            "nep_per_shot": nep_r["per_shot_nep"],
            "nep_n_scored": nep_r.get("n_scored"),
            "nep_n_skipped": nep_r.get("n_skipped"),
            "nep_n_mask_missing": nep_r.get("n_mask_missing"),
            "nep_mask_mode": nep_r.get("mask_mode") or mask_spec.get("score_region"),
            "nep_reason": nep_r.get("reason"),
            "usp_per_shot": usp_r["per_shot_usp"],
            "usp_n_scored": usp_r.get("n_scored"),
            "usp_n_unedited": usp_r.get("n_unedited"),
            "usp_n_missing": usp_r.get("n_missing"),
            "usp_reason": usp_r.get("reason"),
            "tac_per_shot": tac_r.get("per_shot_tac") or {},
            "tac_shot_count_match": tac_r.get("shot_count_match"),
            "tac_expected_count": tac_r.get("expected_count"),
            "tac_edited_count": tac_r.get("edited_count"),
            "tac_mean_anchor_error_sec": tac_r.get("mean_anchor_error_sec"),
            "tac_reason": tac_r.get("reason"),
            "mask_queries": mask_spec,
            "mask_query": legacy_mask_query,
            "mask_hits": mask_hits,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts_json", required=True)
    ap.add_argument("--baseline_dir", required=True)
    ap.add_argument("--videos_root", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--snapshot_id", default="ad-hoc")
    ap.add_argument("--backend_dino", default="mock", choices=["mock", "v2s", "v2b"])
    ap.add_argument("--backend_vlm", default="mock", choices=["mock", "seed", "qwen3vl", "qwen"])
    ap.add_argument("--backend_shot", default="none", choices=["none", "omnishotcut"],
                    help="Shot detector for TAC. Production uses omnishotcut; none leaves TAC unset.")
    ap.add_argument("--backend_mask", default="none", choices=["none", "sam3"],
                    help="If set, run SAM-3 per shot on edit.mask_queries to localize "
                         "the mask region for NEP. Ordinary local edits score the "
                         "mask complement; T8 background replacement scores the "
                         "foreground preserve mask itself. "
                         "EE_v3/CSEP_v3 remain VLM full-frame judgments. Default off.")
    ap.add_argument("--backend_psq", default="mock", choices=["mock", "pyiqa"],
                    help="MUSIQ + LAION-Aes via pyiqa, or deterministic hash mock.")
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--max_frames_per_shot", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--num_samples", type=int, default=1,
                    help="K-sample protocol. If 1, prefer {sid}.mp4 but also accept {sid}_k0.mp4. "
                         "If >1, look for {sid}_k0.mp4 ... {sid}_k{K-1}.mp4. "
                         "Score each available k, then aggregate to mean/std per metric.")
    ap.add_argument("--num_shards", type=int, default=1,
                    help="Total number of parallel shards (one process per shard).")
    ap.add_argument("--shard_id", type=int, default=0,
                    help="Which shard this process is. prompts = prompts[shard_id::num_shards].")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    prompts = json.load(open(args.prompts_json))
    # Shard FIRST, then limit. So --limit means N per shard, not total.
    if args.num_shards > 1:
        prompts = prompts[args.shard_id :: args.num_shards]
    if args.limit:
        prompts = prompts[: args.limit]

    dino = B.get_dino(args.backend_dino)
    vlms = [B.get_vlm(args.backend_vlm)]
    mask_backend = B.get_mask(args.backend_mask)
    psq_fn = B.get_psq(args.backend_psq)

    # Per-sample results: list of dicts. With K>1, each prompt produces K rows
    # plus an aggregated row.
    results = []                 # all per-(sid,k) rows
    per_sample_aggs = []         # one per prompt: aggregated across K
    for sample in tqdm(prompts, desc="eval"):
        sid = sample["sample_id"]
        # Discover available K samples
        candidates = []
        if args.num_samples == 1:
            # 中文注释：兼容两种单输出命名：
            # 旧 baseline 可能写 {sid}.mp4；当前 K-sample baseline 常写 {sid}_k0.mp4。
            for name in (f"{sid}.mp4", f"{sid}_k0.mp4"):
                p = os.path.join(args.baseline_dir, name)
                if os.path.exists(p):
                    candidates.append((0, p))
                    break
        else:
            for k in range(args.num_samples):
                p = os.path.join(args.baseline_dir, f"{sid}_k{k}.mp4")
                if os.path.exists(p):
                    candidates.append((k, p))
        if not candidates:
            continue

        sample_rs = []
        # Read source frames ONCE per prompt, share across all K samples
        src_path = os.path.join(args.videos_root, sample["source_video"])
        try:
            src_cache = _maybe_per_shot_frames(
                src_path, sample["shots"], args.stride, args.max_frames_per_shot
            )
        except Exception as e:
            print(f"[ERROR] {sid} can't read source {src_path}: {e}")
            continue

        for k, ev in candidates:
            try:
                r = score_one(
                    sample, ev, args.videos_root, args.baseline, args.snapshot_id,
                    dino, vlms,
                    stride=args.stride, max_frames_per_shot=args.max_frames_per_shot,
                    src_frames_cached=src_cache,
                    mask_backend=mask_backend,
                    psq_fn=psq_fn,
                    shot_backend=args.backend_shot,
                )
                r["k"] = k
            except Exception as e:
                print(f"[ERROR] {sid}_k{k}: {e}")
                continue
            with open(os.path.join(args.output_dir, f"{sid}_k{k}.eval.json"), "w") as f:
                json.dump(r, f, indent=2)
            results.append(r)
            sample_rs.append(r)

        # per-sample aggregation across K
        if len(sample_rs) >= 1:
            # 中文注释：先在同一个 prompt 内对 K 个生成样本求平均。
            # 这一步生成 {sid}.agg.json，代表“这个 prompt 的模型表现”。
            agg_p = {"sample_id": sid, "task_id": sample_rs[0]["task_id"], "k_count": len(sample_rs)}
            for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
                xs = [r[metric] for r in sample_rs if r.get(metric) is not None]
                # 中文注释：None 表示该指标对该样本不可评估/被任务规则跳过，
                # 聚合时会被排除；不要把 None 当作 0。
                agg_p[f"{metric}_mean"] = sum(xs) / len(xs) if xs else None
                if len(xs) >= 2:
                    mu = sum(xs) / len(xs)
                    var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
                    agg_p[f"{metric}_std"] = var ** 0.5
                else:
                    agg_p[f"{metric}_std"] = None
            with open(os.path.join(args.output_dir, f"{sid}.agg.json"), "w") as f:
                json.dump(agg_p, f, indent=2)
            per_sample_aggs.append(agg_p)

    # Task-level aggregation: take per-sample MEANS (so each prompt counts equally
    # regardless of how many K it had), then mean+std across prompts.
    if per_sample_aggs:
        # 中文注释：任务级 aggregate 再对 prompt-level mean 求平均。
        # 这样每个 prompt 权重相同，不会因为某条 prompt 有更多可用 K 样本而权重大。
        agg = {"baseline": args.baseline, "snapshot_id": args.snapshot_id,
               "task_id": per_sample_aggs[0]["task_id"], "n_prompts": len(per_sample_aggs),
               "k_samples": args.num_samples}
        for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
            # collect per-prompt mean (across K)
            xs = [a[f"{metric}_mean"] for a in per_sample_aggs if a.get(f"{metric}_mean") is not None]
            if xs:
                mu = sum(xs) / len(xs)
                agg[f"{metric}_mean"] = mu
                if len(xs) >= 2:
                    var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
                    agg[f"{metric}_std"] = var ** 0.5
                else:
                    agg[f"{metric}_std"] = None
            else:
                agg[f"{metric}_mean"] = None
                agg[f"{metric}_std"] = None
        agg_name = "aggregate.json" if args.num_shards == 1 else f"aggregate_s{args.shard_id}_of_{args.num_shards}.json"
        with open(os.path.join(args.output_dir, agg_name), "w") as f:
            json.dump(agg, f, indent=2)
        print(f"\n{args.baseline} {agg['task_id']} shard {args.shard_id}/{args.num_shards}: "
              f"n_prompts={len(per_sample_aggs)} K={args.num_samples}")
        for m in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "usp", "tac"):
            mn = agg.get(f"{m}_mean")
            sd = agg.get(f"{m}_std")
            mn_str = f"{mn:.3f}" if isinstance(mn, float) else "—"
            sd_str = f"±{sd:.3f}" if isinstance(sd, float) else ""
            print(f"  {m.upper():6} {mn_str} {sd_str}")


if __name__ == "__main__":
    main()
