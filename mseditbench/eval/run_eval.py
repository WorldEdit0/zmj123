"""Eval orchestrator: score one (prompt sample, baseline output) pair.

Given:
    sample (EditPromptSample dict from edit_prompts/) — has source_video, shots, edit
    edited_video_path                              — output from a baseline
Compute:
    PSQ, EE_v3, NEP, CSEP_v3, SES
    T5 is handled by mseditbench.eval.t5_track because structural edits
    change shot boundaries.

Outputs are saved as one EvalResult JSON per (sample, baseline) pair.

CLI:
    python -m mseditbench.eval.run_eval \
        --prompts_json runs/edit_prompts_v2_10s/T1.json \
        --baseline_dir runs/seedance_v2v_edit_v2_10s/videos/T1 \
        --videos_root data/source_videos_10s/videos \
        --output_dir runs/eval_seedance_v2v_v2_10s_v3/T1 \
        --baseline seedance_v2v \
        --backend_clip mock --backend_dino mock --backend_vlm mock \
        --limit 5

The default mock backends produce deterministic [0,1] scores so the
orchestrator can be exercised without GPU. Swap in real backends with
--backend_clip openai etc when ready.
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
    # 每个 shot 内按 stride 抽帧，最多 max_frames 帧。普通 T1/T2/T3/T4/T6/T7
    # 都用“源 shot 边界”对齐 source/edit；T5 结构编辑另走 t5_track.py。
    return M.per_shot_frames(video_path, shots, stride=stride, max_frames=max_frames)


# Tasks where the edit instruction itself changes the protagonist's identity.
# IDdrift is undefined / penalises intentional behaviour for these.
# T1 = Cross-Shot Character Replacement (the only task that intentionally
# replaces the person). T3 (style re-render) does NOT change identity even
# though heavy stylisation may drift the face embedding — we keep that signal.
_IDENTITY_CHANGING_TASKS = {"T1"}


# SAM-3 minimum mask area (pixels). Below this, treat as miss and fall through
# to whole-frame metrics — but log the miss so we know it happened.
_MASK_MIN_PIXELS = 100


def _get_mask_query(sample: dict) -> str | None:
    """Pick the phrase to query SAM-3 with for per-shot mask localisation.

    Why not just `target_phrase`?
      - For T1 char-replace, target_phrase describes the *post-edit* entity
        (e.g. "a female android with chrome cheekbones"). SAM-3 is run on the
        edit frames; if the editor failed, the android is not there → mask
        misses → silent fallthrough to whole-frame EE.
      - The right anchor is the *source* entity description, which exists in
        the source video regardless of edit success. The same mask is then
        applied to both source and edit frames.

    Returns None for tasks where masking doesn't make semantic sense:
      T3 global style    — change is everywhere
      T5 structural      — operates on shot ordering
      T6 cinematic       — re-frames whole shot
      T7 transition      — operates between shots
    """
    edit = sample["edit"]
    task_id = edit["task_id"]

    if task_id in {"T3", "T5", "T6", "T7"}:
        return None

    # T1 / T2: mask the SOURCE entity by its character desc (stable pre-edit)
    target_entity = edit.get("target_entity")
    if target_entity:
        for c in sample.get("characters", []):
            if c.get("id") == target_entity:
                desc = c.get("desc")
                if desc:
                    return desc

    # T4: mask the anchor object (existing in source, stable pre-edit)
    if task_id == "T4":
        anchor = (edit.get("extra") or {}).get("anchor")
        if anchor:
            return anchor

    # Fallback: whatever target_phrase the prompt declared
    return edit.get("target_phrase")


def _largest_face_embedding(frame: np.ndarray, face_backend) -> np.ndarray | None:
    """Detect faces in a single RGB frame; return the largest face's
    L2-normalised embedding, or None if no face detected. Internally converts
    RGB → BGR because InsightFace expects BGR."""
    bgr = frame[..., ::-1] if frame.shape[-1] == 3 else frame
    bgr = np.ascontiguousarray(bgr)
    try:
        faces = face_backend.detect_and_embed(bgr)
    except Exception as e:
        print(f"[face] detect failed: {type(e).__name__}: {e}")
        return None
    if not faces:
        return None
    def _area(f):
        x1, y1, x2, y2 = f["bbox"]
        return max(0, x2 - x1) * max(0, y2 - y1)
    f = max(faces, key=_area)
    e = f.get("embedding")
    if e is None:
        return None
    e = np.asarray(e, dtype=np.float32)
    n = np.linalg.norm(e) + 1e-8
    return e / n


def _get_v2_text_pair(sample: dict) -> tuple[str, str]:
    """For EE_v2 directional CLIP: pick the (source-anchor, target) text pair.

    The directional formula is cos(img_emb_diff, txt_emb_diff). Both halves of
    the text diff need to be present in the prompt JSON; we pick task-specific
    anchors so the diff vector points cleanly in the requested direction.

      T1 char-replace : characters[target_entity].desc → target_phrase
      T2 attribute    : characters[target_entity].desc → target_phrase
      T3 global style : "the original natural realistic scene" → target_phrase
                        (no source entity exists — use a generic anchor)
      T4 object       : extra.anchor (object class) → target_phrase
      T5 / T6 / T7    : not directional-friendly — return ("", "") and let
                        ee_v2 short-circuit to None
    """
    edit = sample["edit"]
    task_id = edit["task_id"]
    tgt = edit.get("target_phrase", "") or ""

    # Tasks where directional EE doesn't apply
    if task_id in {"T5", "T7"}:
        return "", ""

    if task_id == "T3":
        return "the original natural realistic scene", tgt

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

    # T4: anchor on the source object name
    if task_id == "T4":
        anchor = (edit.get("extra") or {}).get("anchor")
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
#   T4 object        : small object add/replace → ~0.02 typical
#   T6 cinematic     : framing change → ~0.03 typical
# T5 / T7: handled outside EE_v2 (shot-structural / transition).
_DELTA_MAX_PER_TASK = {
    "T1": 0.05,
    "T2": 0.02,
    "T3": 0.05,
    "T4": 0.02,
    "T6": 0.03,
}


def _compute_id_drift(
    per_shot_source_frames: dict[int, np.ndarray],
    per_shot_edit_frames: dict[int, np.ndarray],
    face_backend,
) -> float | None:
    """Per-shot largest-face cosine distance between source and edit, averaged.
    Returns None if face detection fails on every shot."""
    # 中文注释：ID drift 只取每个 shot 中间帧的最大人脸 embedding，
    # 用 1-cosine 表示身份变化幅度；越大说明身份越可能被非预期改坏。
    drifts = []
    for k, sf in per_shot_source_frames.items():
        if k not in per_shot_edit_frames:
            continue
        ef = per_shot_edit_frames[k]
        # Anchor = middle frame
        s_anchor = sf[len(sf) // 2]
        e_anchor = ef[len(ef) // 2]
        es = _largest_face_embedding(s_anchor, face_backend)
        ee = _largest_face_embedding(e_anchor, face_backend)
        if es is None or ee is None:
            continue
        cos = float(np.clip(np.dot(es, ee), -1.0, 1.0))
        drifts.append(max(0.0, 1.0 - cos))
    if not drifts:
        return None
    return float(np.mean(drifts))


def score_one(
    sample: dict,
    edited_video_path: str,
    videos_root: str,
    baseline_name: str,
    snapshot_id: str,
    clip_backend, dino_backend, face_backend, vlm_backends,
    stride: int = 4,
    max_frames_per_shot: int = 6,
    src_frames_cached: dict | None = None,  # avoid re-reading source per K
    mask_backend=None,                      # callable (frames, phrase) -> mask, or None
    psq_fn=None,                            # callable frames -> (musiq,laion), or None for default mock
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
    absent = [s["shot_id"] for s in shots if s["shot_id"] not in applicable]

    # 中文注释：source frames 对同一个 prompt 的 K 个输出完全相同，
    # 所以 main() 会缓存一次传进来，避免每个 k 都重复读源视频。
    if src_frames_cached is not None:
        src_frames = src_frames_cached
    else:
        src_frames = _maybe_per_shot_frames(src_path, shots, stride, max_frames_per_shot)
    edt_frames = _maybe_per_shot_frames(edited_video_path, shots, stride, max_frames_per_shot)

    # Per-shot 2D mask for entity-localised preservation.
    # Anchored on the *source* mid-frame using the source-entity desc — see
    # _get_mask_query() for rationale. In the current v3 pipeline this mask is
    # used by NEP to compare the non-edited complement region. EE_v3/CSEP_v3
    # are VLM full-frame image/frame-set judgments and do not consume masks.
    # Misses fall through to whole-frame NEP; we record mask_hits so reports can
    # audit the fallthrough rate.
    edit_masks = None
    mask_query = _get_mask_query(sample)
    mask_hits: dict[int, bool] = {}
    if mask_backend is not None and mask_query:
        edit_masks = {}
        for k, frames in src_frames.items():
            if applicable and k not in applicable:
                continue
            T = len(frames)
            if T == 0:
                mask_hits[k] = False
                continue
            anchor = frames[T // 2 : T // 2 + 1]    # [1,H,W,3] from SOURCE
            try:
                m3 = mask_backend(anchor, mask_query)   # [1,H,W]
                m = m3[0]
                # 中文注释：mask 太小通常表示 SAM3 没找到目标；
                # 此时不使用 mask，后续 NEP 退回整帧比较，并在 extra.mask_hits 中记录 miss。
                hit = bool(m.sum() >= _MASK_MIN_PIXELS)
                mask_hits[k] = hit
                if hit:
                    edit_masks[k] = m
            except Exception as e:
                print(f"[mask] sid={sample['sample_id']} shot={k}: {e}")
                mask_hits[k] = False
        if not edit_masks:
            edit_masks = None  # all misses → whole-frame fallthrough

    psq_kwargs = {} if psq_fn is None else {"musiq_fn": psq_fn}
    # 中文注释：PSQ 只看编辑后视频的视觉质量，不依赖 source。
    psq_r = M.psq(edt_frames, **psq_kwargs)

    # v1 EE / CSEP — DEPRECATED. Skipped to save VLM tokens. Set fields to None
    # in result dict for backward compat with merge_shards / aggregate.json.
    ee_r = {"ee": None, "per_shot_indicators": {}}
    csep_r = {"csep": None, "coverage": None, "consistency": None,
              "per_shot_e_tilde": {}}

    # 中文注释：NEP 比较 source/edit 在非编辑区域的 DINO 相似度。
    # 如果有 SAM mask，则只比较 mask 外；如果没有 mask 或 mask miss，则比较整帧。
    nep_r = M.nep(src_frames, edt_frames, dino_backend=dino_backend,
                  per_shot_edit_masks=edit_masks)

    # v2 (CLIP-T directional) — also DEPRECATED. Kept None.
    ee2_r = {"ee": None, "per_shot": {}, "n_applicable": 0}
    csep2_r = {"csep": None, "coverage": None, "consistency": None}

    # v3 EE / CSEP — VLM-as-judge headline metrics.
    # Skip for tasks where per-shot VLM rating doesn't make semantic sense.
    if task_id in {"T5", "T7"}:
        # 中文注释：T5 改变 shot 结构，T7 主要是转场操作；这两类不适合
        # 用“每个原始 shot 是否完成编辑”来定义 EE/CSEP，所以显式跳过。
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

    # 中文注释：OffTarget 看 absent shots 是否错误地朝 target_phrase 变化。
    off = M.off_target(src_frames, edt_frames, absent, target_phrase,
                       clip_backend=clip_backend)
    # IDdrift: only meaningful for tasks that *don't* intentionally change
    # the protagonist's identity. T1 intentionally replaces the character, so
    # it uses OffTarget-only SES. T3 keeps IDdrift because style transfer should
    # preserve identity even if the style is global.
    id_drift = None
    if face_backend is not None and task_id not in _IDENTITY_CHANGING_TASKS:
        id_drift = _compute_id_drift(src_frames, edt_frames, face_backend)
    ses_r = M.ses(id_drift=id_drift, off_target_mean=off["off_target_mean"])

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
        "ses": ses_r["ses"],
        "off_target": ses_r["off_target"],
        "id_drift": id_drift,
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
            "mask_query": mask_query,
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
    ap.add_argument("--backend_clip", default="mock", choices=["mock", "openai", "siglip"])
    ap.add_argument("--backend_dino", default="mock", choices=["mock", "v2s", "v2b"])
    ap.add_argument("--backend_face", default="mock", choices=["mock", "insightface"])
    ap.add_argument("--backend_vlm", default="mock", choices=["mock", "seed", "qwen3vl", "qwen"])
    ap.add_argument("--backend_mask", default="none", choices=["none", "sam3"],
                    help="If set, run SAM-3 per shot to localize the target region. "
                         "Current v3 uses the mask for NEP complement preservation; "
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

    clip = B.get_clip(args.backend_clip)
    dino = B.get_dino(args.backend_dino)
    face = B.get_face(args.backend_face) if args.backend_face != "mock" else None
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
                    clip, dino, face, vlms,
                    stride=args.stride, max_frames_per_shot=args.max_frames_per_shot,
                    src_frames_cached=src_cache,
                    mask_backend=mask_backend,
                    psq_fn=psq_fn,
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
            for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "ses"):
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
        for metric in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "ses"):
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
        for m in ("psq", "ee", "ee_v2", "ee_v3", "nep", "csep", "csep_v2", "csep_v3", "ses"):
            mn = agg.get(f"{m}_mean")
            sd = agg.get(f"{m}_std")
            mn_str = f"{mn:.3f}" if isinstance(mn, float) else "—"
            sd_str = f"±{sd:.3f}" if isinstance(sd, float) else ""
            print(f"  {m.upper():6} {mn_str} {sd_str}")


if __name__ == "__main__":
    main()
