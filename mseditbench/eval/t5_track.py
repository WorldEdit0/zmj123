"""T5 Structural Fidelity (TSF) - special-case eval track for T5 prompts.

T5 = Shot Reorder. Per-shot EE/NEP/CSEP cannot work because
they extract edit frames using *source* shot boundaries — when the edit
changes the shot structure, those boundaries are misaligned and the metrics
become noise.

Now that T5 contains reorder-only prompts, TSF no longer has an explicit
shot-count term. The score is the expected-order content alignment:

    TSF = content_alignment

content_alignment compares edited shot i with the source shot specified by
edit.extra.new_order[i] using DINOv2 cosine similarity. Missing edited shots
score 0 for their expected positions; extra edited shots are kept in the JSON
for audit but do not create a separate count bonus or penalty.

Output JSON per (sample, k) is written next to the standard eval results.
A single aggregate.json is emitted at the end.

CLI:
    python -m mseditbench.eval.t5_track \
        --prompts_json runs/edit_prompts_v2_10s/T5.json \
        --baseline_dir runs/seedance_v2v_edit_v2_10s/videos/T5 \
        --videos_root data/source_videos_10s/videos \
        --output_dir runs/eval_t5_track/seedance_v2v \
        --baseline seedance_v2v --num_samples 3
"""

from __future__ import annotations
import argparse
import json
import os
import re
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm

from mseditbench import metrics as M
from mseditbench.metrics import backends as B
from mseditbench.preprocess.omnishot_backend import predict_shots


# --- op classification ----------------------------------------------------

# 中文注释：T5 现在只保留 reorder。这里仍保留轻量分类，
# 主要用于过滤错误/旧 prompt，而不再根据操作类型推导 shot 数。
_OP_PATTERNS = [
    ("reorder", re.compile(r"\b(reorder|shot order|shot sequence|trade positions|trade places)\b", re.I)),
]


def classify_op(instruction: str, extra: dict | None = None) -> str:
    if (extra or {}).get("op") == "reorder":
        return "reorder"
    inst = instruction.strip()
    for name, pat in _OP_PATTERNS:
        if pat.search(inst):
            return name
    return "unknown"


def expected_order(sample: dict) -> list[int] | None:
    """Return the source shot_id sequence expected in the edited video."""
    edit = sample["edit"]
    extra = edit.get("extra") or {}
    order = extra.get("new_order")
    if isinstance(order, list) and order:
        try:
            return [int(x) for x in order]
        except (TypeError, ValueError):
            return None

    # Fallback for hand-written instructions that spell out "shot order 3, 1, 2".
    m = re.search(r"shot order\s*([0-9,\s]+)", edit.get("instruction", ""), re.I)
    if m:
        nums = [x for x in re.split(r"[\s,]+", m.group(1).strip()) if x]
        try:
            return [int(x) for x in nums]
        except ValueError:
            return None
    return None


# --- DINO shot embedding --------------------------------------------------

def _shot_anchor_embeddings(video_path: str, shots: list[dict],
                            dino_backend, target_size: int = 518) -> tuple[list[int], np.ndarray]:
    """Embed the middle frame of each shot. Returns (shot_ids, [n_shots, D])."""
    # 中文注释：T5 不使用源 shot 边界去切编辑后视频，因为结构编辑会改变边界。
    # 这里只取每个检测到的 shot 的中间帧作为该 shot 的内容锚点。
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        # 中文注释：视频打不开时返回空 embedding，调用方会把内容对齐记为 0。
        return [], np.zeros((0, 384), dtype=np.float32)
    shot_ids = []
    embs = []
    for sh in shots:
        mid = (int(sh["frame_start"]) + int(sh["frame_end"])) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
        ok, frame = cap.read()
        if not ok:
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # 中文注释：DINO embedding 表示该 shot 的视觉/语义内容，
        # 用于判断编辑后 shot 是否仍然来自原视频内容，而不是整体重生成。
        e = dino_backend.embed_frames(rgb[None, ...])  # [1, D]
        shot_ids.append(int(sh["shot_id"]))
        embs.append(e[0])
    cap.release()
    if not embs:
        return [], np.zeros((0, 384), dtype=np.float32)
    arr = np.stack(embs).astype(np.float32)
    # 中文注释：归一化后，矩阵乘法即可得到 cosine similarity。
    arr /= (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-8)
    return shot_ids, arr


def content_alignment(
    src_ids: list[int],
    src_embeds: np.ndarray,
    edit_embeds: np.ndarray,
    order: list[int],
) -> float:
    """Mean cosine sim between edited shots and their expected source shots."""
    # 中文注释：T5 只剩 reorder，所以内容对齐必须按 expected_order
    # 做位置对应，而不是让每个 edited shot 自由匹配任意 source shot。
    if not order or len(src_embeds) == 0 or len(edit_embeds) == 0:
        return 0.0
    src_by_id = {sid: emb for sid, emb in zip(src_ids, src_embeds)}
    scores = []
    for pos, sid in enumerate(order):
        if pos >= len(edit_embeds) or sid not in src_by_id:
            scores.append(0.0)
            continue
        scores.append(float(np.dot(edit_embeds[pos], src_by_id[sid])))
    if not scores:
        return 0.0
    return float(np.clip(np.mean(scores), 0.0, 1.0))


# --- main -----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts_json", required=True)
    ap.add_argument("--baseline_dir", required=True,
                    help="Dir with {sample_id}_k{0,1,2}.mp4 edit videos")
    ap.add_argument("--videos_root", required=True,
                    help="Source videos root dir")
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--snapshot_id", default="t5_track")
    ap.add_argument("--num_samples", type=int, default=3)
    ap.add_argument("--backend_dino", default="v2s",
                    choices=["mock", "v2s", "v2b"])
    ap.add_argument("--num_shards", type=int, default=1)
    ap.add_argument("--shard_id", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    all_prompts = json.load(open(args.prompts_json))
    all_prompts = [p for p in all_prompts if p["edit"]["task_id"] == "T5"]
    valid_sample_ids = {p["sample_id"] for p in all_prompts}
    prompts = all_prompts
    if args.num_shards > 1:
        # 中文注释：分片运行时，每个进程只处理 prompts 的一个交错子集。
        prompts = prompts[args.shard_id::args.num_shards]
    # 中文注释：该脚本只处理 T5；即使传入混合 prompt 文件，也会过滤掉其他任务。
    print(f"Loaded {len(prompts)} T5 prompts (shard {args.shard_id}/{args.num_shards})")

    dino = B.get_dino(args.backend_dino)

    per_sample_aggs = []
    op_breakdown = {"reorder": [], "unknown": []}
    for sample in tqdm(prompts, desc=f"t5 shard {args.shard_id}"):
        sid = sample["sample_id"]
        src_path = os.path.join(args.videos_root, sample["source_video"])
        src_shots = sample["shots"]
        src_count = len(src_shots)
        # 中文注释：从结构字段读取 expected_order；TSF 不再使用 shot-count 分。
        op = classify_op(sample["edit"]["instruction"], sample["edit"].get("extra") or {})
        order = expected_order(sample)

        # source DINO embedding (cached across K)
        # 中文注释：源视频的 shot embedding 对同一个 prompt 的 K 个样本相同，
        # 所以只算一次，避免重复跑 DINO。
        src_ids, src_embs = _shot_anchor_embeddings(src_path, src_shots, dino)

        per_k = []
        for k in range(args.num_samples):
            ev = os.path.join(args.baseline_dir, f"{sid}_k{k}.mp4")
            if not os.path.exists(ev):
                # 中文注释：允许某些 K 样本缺失；缺失样本不参与该 prompt 聚合。
                continue
            try:
                # 中文注释：编辑后视频重新做 shot detection，
                # 这是 T5 track 区别于普通逐镜头评估的关键。
                edit_shots = predict_shots(ev, clean_shot=True)
            except Exception as e:
                print(f"[t5] {sid}_k{k} shot_detect failed: {e}")
                continue
            edit_count = len(edit_shots)

            _, edit_embs = _shot_anchor_embeddings(ev, edit_shots, dino)
            ca = content_alignment(src_ids, src_embs, edit_embs, order or [])
            # 中文注释：T5 reorder-only 后，TSF 就是 expected-order 内容对齐。
            tsf = ca

            row = {
                "sample_id": sid, "k": k, "op": op,
                "source_shot_count": src_count,
                "expected_order": order,
                "edit_shot_count": edit_count,
                "content_alignment": ca,
                "tsf": tsf,
            }
            with open(os.path.join(args.output_dir, f"{sid}_k{k}.t5.json"), "w") as f:
                json.dump(row, f, indent=2)
            per_k.append(row)

        if not per_k:
            # 中文注释：该 prompt 没有任何成功评分的 K 样本时，不写 prompt 聚合。
            continue
        # 中文注释：先对同一 prompt 的 K 个输出求均值/标准差，
        # 再在最终 aggregate 中对 prompt 求均值，保证每条 prompt 权重相同。
        agg = {
            "sample_id": sid, "op": op, "k_count": len(per_k),
            "tsf_mean": float(np.mean([r["tsf"] for r in per_k])),
            "tsf_std": float(np.std([r["tsf"] for r in per_k], ddof=1))
                if len(per_k) >= 2 else None,
            "content_alignment_mean": float(np.mean([r["content_alignment"] for r in per_k])),
        }
        with open(os.path.join(args.output_dir, f"{sid}.t5.agg.json"), "w") as f:
            json.dump(agg, f, indent=2)
        per_sample_aggs.append(agg)
        op_breakdown[op].append(agg["tsf_mean"])

    if args.num_shards > 1 and args.shard_id != 0:
        # 中文注释：多分片时非 0 分片只写自己的 per-sample 文件；
        # 最终跨分片 aggregate 由 shard 0 重新扫描磁盘完成。
        return  # only shard 0 aggregates

    # Re-read from disk so cross-shard aggregation works
    # 中文注释：重新从 output_dir 读取所有 .t5.agg.json，
    # 这样单进程和多分片运行都能走同一套最终聚合逻辑。
    per_sample_aggs = []
    op_breakdown = {"reorder": [], "unknown": []}
    for f in sorted(Path(args.output_dir).glob("*.t5.agg.json")):
        a = json.load(open(f))
        if a.get("sample_id") not in valid_sample_ids:
            continue
        per_sample_aggs.append(a)
        op_breakdown.setdefault(a["op"], []).append(a["tsf_mean"])

    if not per_sample_aggs:
        print("no t5 results to aggregate")
        return

    tsfs = [a["tsf_mean"] for a in per_sample_aggs]
    cas = [a["content_alignment_mean"] for a in per_sample_aggs]
    # 中文注释：最终 aggregate 按 prompt-level mean 聚合，
    # 同时保留 by_op，方便检查是否有旧 prompt 混入 unknown。
    out = {
        "baseline": args.baseline,
        "snapshot_id": args.snapshot_id,
        "task_id": "T5",
        "n_prompts": len(per_sample_aggs),
        "k_samples": args.num_samples,
        "tsf_mean": float(np.mean(tsfs)),
        "tsf_std": float(np.std(tsfs, ddof=1)) if len(tsfs) >= 2 else None,
        "content_alignment_mean": float(np.mean(cas)),
        "by_op": {op: {
            "n": len(vals),
            "tsf_mean": float(np.mean(vals)) if vals else None,
            "tsf_std": float(np.std(vals, ddof=1)) if len(vals) >= 2 else None,
        } for op, vals in op_breakdown.items() if vals},
    }
    with open(os.path.join(args.output_dir, "aggregate.json"), "w") as f:
        json.dump(out, f, indent=2)

    print(f"\n{args.baseline} T5 track: n_prompts={out['n_prompts']} K={args.num_samples}")
    print(f"  TSF                  {out['tsf_mean']:.3f} "
          f"±{out['tsf_std']:.3f}" if out['tsf_std'] else "")
    print(f"  content_alignment    {out['content_alignment_mean']:.3f}")
    print("  Per-op breakdown:")
    for op, stats in out["by_op"].items():
        sd = f"±{stats['tsf_std']:.3f}" if stats['tsf_std'] else ""
        print(f"    {op:8s} n={stats['n']:3d}  TSF={stats['tsf_mean']:.3f} {sd}")


if __name__ == "__main__":
    main()
