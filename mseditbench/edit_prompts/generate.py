"""Per-video edit-prompt instantiation.

For each (video, task) pair, draws N concrete edit prompts from `banks.py`
and `tasks.py`. Output is a JSON list of EditPromptSample dicts ready for
the editor APIs and the metric layer.

CLI:
    python -m mseditbench.edit_prompts.generate \
        --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \
        --shots_dir runs/pilot_v2_10s/shots \
        --output_dir runs/edit_prompts_v2_10s \
        --tasks T1,T2,T3,T4,T5,T6,T7,T8 \
        --max_per_video 2 \
        --seed 0

Output: runs/edit_prompts/{T1,T2,...}.json - one prompt set per task.
"""

from __future__ import annotations
import argparse
import json
import os
import random
from pathlib import Path

from .tasks import ALL_TASKS
from . import banks


def _load_shots(shots_dir: str, video_id: str) -> list[dict]:
    p = Path(shots_dir) / f"{video_id}.shots.json"
    if not p.exists():
        return []
    return json.load(open(p)).get("consensus_shots") or []


def _mask_queries(nep: bool, scope: str, edit_type: str,
                  source=None, edited=None, reason: str | None = None) -> dict:
    spec = {
        "nep_applicable": nep,
        "edit_scope": scope,
        "edit_type": edit_type,
        "source_queries": list(source or []),
        "edited_queries": list(edited or []),
        "combine": "union" if nep else "none",
    }
    if reason:
        spec["reason"] = reason
    return spec


def _sample_t1(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    characters = item.get("characters", [])
    key_objects = item.get("key_objects", [])
    if characters:
        ch = rng.choice(characters)
        tgt = rng.choice(banks.T1_DYNAMIC_TARGETS)
        tpl = rng.choice(ALL_TASKS["T1"].instruction_templates[:3])
        instr = tpl.format(character_desc=ch["desc"], target_desc=tgt)
        out.append({
            "task_id": "T1",
            "instruction": instr,
            "target_phrase": tgt,
            "target_entity": ch["id"],
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": {"replace_kind": "dynamic", "old_entity": ch["desc"], "new_entity": tgt},
            "mask_queries": _mask_queries(True, "local", "dynamic_replace", [ch["desc"]], [tgt]),
        })
    if key_objects:
        old_object = rng.choice(key_objects)
        new_object = rng.choice(banks.T1_STATIC_REPLACEMENTS)
        instr = ALL_TASKS["T1"].instruction_templates[3].format(
            old_object=old_object, new_object=new_object
        )
        out.append({
            "task_id": "T1",
            "instruction": instr,
            "target_phrase": new_object,
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": {
                "replace_kind": "static",
                "op": "replace",
                "old_object": old_object,
                "new_object": new_object,
                "anchor": old_object,
            },
            "mask_queries": _mask_queries(True, "local", "static_replace", [old_object], [new_object]),
        })
    return out


def _sample_t2(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    for ch in item.get("characters", []):
        attrs = rng.sample(banks.T2_ATTRIBUTES, k=min(n, len(banks.T2_ATTRIBUTES)))
        for kind, olds, news in attrs:
            new_value = rng.choice(news)
            old_value = rng.choice(olds)
            attribute_label = kind.replace("_", " ")
            tpl = rng.choice(ALL_TASKS["T2"].instruction_templates)
            instr = tpl.format(character_desc=ch["desc"], attribute_kind=attribute_label,
                               new_value=new_value, old_value=old_value)
            target_phrase = ALL_TASKS["T2"].target_phrase_template.format(
                new_value=new_value, attribute_kind=attribute_label)
            out.append({
                "task_id": "T2", "instruction": instr, "target_phrase": target_phrase,
                "target_entity": ch["id"],
                "applicable_shots": [s["shot_id"] for s in shots],
                "extra": {"attribute_category": kind, "old_value": old_value, "new_value": new_value},
                "mask_queries": _mask_queries(
                    True, "local", "attribute_edit",
                    [] if old_value.startswith("original") else [old_value],
                    [new_value],
                ),
            })
    return out


def _sample_t3(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    styles = rng.sample(banks.T3_STYLES, k=min(n, len(banks.T3_STYLES)))
    for st in styles:
        tpl = rng.choice(ALL_TASKS["T3"].instruction_templates)
        out.append({
            "task_id": "T3",
            "instruction": tpl.format(style=st),
            "target_phrase": ALL_TASKS["T3"].target_phrase_template.format(style=st),
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": {"render_axis": "style", "style": st},
            "mask_queries": _mask_queries(
                False, "global", "style_transfer",
                reason="Whole-frame style edits can legitimately affect the entire frame.",
            ),
        })
    return out


def _t4_op_matches(op: str, conds: dict, key_objects: list[str]) -> tuple[str | None, str | None]:
    """Return (matched_target_obj, matched_anchor_obj) or (None, ...) if op
    can't be applied to this video. Tells the caller which key_object played
    each role."""
    lk = [k.lower() for k in key_objects]
    match_any = conds.get("match_any") or []
    anchor_any = conds.get("anchor_any") or []

    matched_target = None
    if match_any:
        for kw in match_any:
            for orig, low in zip(key_objects, lk):
                if kw.lower() in low:
                    matched_target = orig
                    break
            if matched_target:
                break

    matched_anchor = None
    if anchor_any:
        for kw in anchor_any:
            for orig, low in zip(key_objects, lk):
                if kw.lower() in low:
                    matched_anchor = orig
                    break
            if matched_anchor:
                break

    if op == "add" and matched_anchor is None:     return None, None
    if op == "delete" and matched_target is None:  return None, None
    return matched_target, matched_anchor


def _sample_t4(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    obj_keywords = item.get("key_objects", [])
    characters = item.get("characters", [])
    if not obj_keywords and not characters:
        return out

    # Pre-filter: keep only ops that can fire on this video.
    applicable = []
    for op, new_obj, conds in banks.T4_OPS:
        object_kind = conds.get("object_kind", "static")
        if object_kind == "dynamic" and op == "delete" and characters:
            ch = rng.choice(characters)
            applicable.append((op, new_obj, conds, ch["desc"], ch["desc"]))
            continue
        target, anchor = _t4_op_matches(op, conds, obj_keywords)
        if op == "add" and anchor is None:     continue
        if op == "delete" and target is None:  continue
        applicable.append((op, new_obj, conds, target, anchor))

    if not applicable:
        return out

    chosen = rng.sample(applicable, k=min(n, len(applicable)))
    for op, new_obj, conds, old_object, anchor_obj in chosen:
        object_kind = conds.get("object_kind", "static")
        if op == "add":
            instr = ALL_TASKS["T4"].instruction_templates[0].format(new_object=new_obj, anchor=anchor_obj)
            target_phrase = new_obj
            source_queries, edited_queries = [], [new_obj]
        else:  # delete
            instr = ALL_TASKS["T4"].instruction_templates[1].format(old_object=old_object)
            target_phrase = f"a scene without {old_object}"
            source_queries, edited_queries = [old_object], []
        prompt = {
            "task_id": "T4", "instruction": instr, "target_phrase": target_phrase,
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": {
                "op": op,
                "object_kind": object_kind,
                "old_object": old_object,
                "new_object": new_obj,
                "anchor": anchor_obj or old_object,
            },
            "mask_queries": _mask_queries(
                True, "local", f"{object_kind}_{op}",
                source_queries, edited_queries,
            ),
        }
        if object_kind == "dynamic" and op == "delete":
            for ch in characters:
                if ch.get("desc") == old_object:
                    prompt["target_entity"] = ch.get("id")
                    break
        out.append(prompt)
    return out


def _sample_t5(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    if len(shots) < 2: return out
    ids = [s["shot_id"] for s in shots]
    seen = set()
    attempts = 0
    while len(out) < n and attempts < max(10, n * 20):
        attempts += 1
        order = ids[:]
        rng.shuffle(order)
        if order == ids:
            continue
        key = tuple(order)
        if key in seen:
            continue
        seen.add(key)
        new_order = ", ".join(str(x) for x in order)
        tpl = rng.choice(ALL_TASKS["T5"].instruction_templates)
        instr = tpl.format(new_order=new_order)
        target_phrase = ALL_TASKS["T5"].target_phrase_template.format(new_order=new_order)
        extra = {"op": "reorder", "new_order": order}
        out.append({
            "task_id": "T5", "instruction": instr, "target_phrase": target_phrase,
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": extra,
        })
    return out


def _sample_t6(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    if not shots: return out
    for _ in range(n):
        sid = rng.choice([s["shot_id"] for s in shots])
        framing = rng.choice(banks.T6_FRAMINGS)
        cam = rng.choice(banks.T6_CAMERA_MOVES)
        tpl_idx = rng.randrange(3)
        if tpl_idx == 0:
            instr = ALL_TASKS["T6"].instruction_templates[0].format(target_shot_id=sid, target_framing=framing)
        elif tpl_idx == 1:
            instr = ALL_TASKS["T6"].instruction_templates[1].format(target_shot_id=sid, camera_move=cam)
        else:
            instr = ALL_TASKS["T6"].instruction_templates[2].format(target_shot_id=sid, target_framing=framing, camera_move=cam)
        out.append({
            "task_id": "T6", "instruction": instr,
            "target_phrase": ALL_TASKS["T6"].target_phrase_template.format(target_framing=framing),
            "applicable_shots": [sid],
            "extra": {"target_shot_id": sid, "target_framing": framing, "camera_move": cam},
        })
    return out


def _sample_t7(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    lightings = rng.sample(banks.T7_LIGHTING, k=min(n, len(banks.T7_LIGHTING)))
    for lighting in lightings:
        instr = ALL_TASKS["T7"].instruction_templates[0].format(lighting=lighting)
        out.append({
            "task_id": "T7", "instruction": instr,
            "target_phrase": ALL_TASKS["T7"].target_phrase_template.format(lighting=lighting),
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": {"render_axis": "lighting", "lighting": lighting},
            "mask_queries": _mask_queries(
                False, "global", "lighting_edit",
                reason="Whole-frame lighting edits can legitimately affect the entire frame.",
            ),
        })
    return out


def _sample_t8(item: dict, shots: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    preserve_queries = [
        c["desc"] for c in item.get("characters", [])
    ] + list(item.get("key_objects", []))
    if not preserve_queries:
        return out
    backgrounds = rng.sample(banks.T8_BACKGROUNDS, k=min(n, len(banks.T8_BACKGROUNDS)))
    preserve_foreground = ", ".join(preserve_queries[:4])
    old_background = item.get("scene", "original background")
    for bg in backgrounds:
        instr = ALL_TASKS["T8"].instruction_templates[0].format(
            old_background=old_background,
            new_background=bg,
            preserve_foreground=preserve_foreground,
        )
        out.append({
            "task_id": "T8",
            "instruction": instr,
            "target_phrase": ALL_TASKS["T8"].target_phrase_template.format(new_background=bg),
            "applicable_shots": [s["shot_id"] for s in shots],
            "extra": {
                "render_axis": "background",
                "old_background": old_background,
                "new_background": bg,
                "preserve_queries": preserve_queries,
            },
            "mask_queries": _mask_queries(
                True, "global_background", "background_replace",
                preserve_queries, preserve_queries,
                reason="T8 replaces the background; NEP scores DINOv2 preservation inside the foreground preserve mask.",
            ) | {"score_region": "mask"},
        })
    return out


SAMPLERS = {
    "T1": _sample_t1, "T2": _sample_t2, "T3": _sample_t3, "T4": _sample_t4,
    "T5": _sample_t5, "T6": _sample_t6, "T7": _sample_t7, "T8": _sample_t8,
}


def generate_for_task(
    source_items: list[dict],
    shots_dir: str,
    task_id: str,
    max_per_video: int,
    seed: int = 0,
) -> list[dict]:
    rng = random.Random(seed)
    sampler = SAMPLERS[task_id]
    out = []
    for item in source_items:
        vid = f"{int(item['global_index']):05d}"
        shots = _load_shots(shots_dir, vid)
        if not shots:
            continue
        edits = sampler(item, shots, rng, max_per_video)
        for e in edits:
            sample_id = f"{vid}_{task_id}_{len(out):04d}"
            out.append({
                "sample_id": sample_id,
                "video_id": vid,
                "source_video": f"{vid}.mp4",
                "shots": shots,
                "characters": item.get("characters", []),
                "key_objects": item.get("key_objects", []),
                "edit": e,
            })
    return out


def main():
    ap = argparse.ArgumentParser(description="Generate per-video T1-T8 edit prompts")
    ap.add_argument("--source_json", required=True)
    ap.add_argument("--shots_dir", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--tasks", default="T1,T2,T3,T4,T5,T6,T7,T8")
    ap.add_argument("--max_per_video", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    items = json.load(open(args.source_json))

    summary = {}
    for task_id in args.tasks.split(","):
        task_id = task_id.strip()
        if task_id not in SAMPLERS:
            print(f"[skip] unknown task {task_id!r}")
            continue
        prompts = generate_for_task(items, args.shots_dir, task_id, args.max_per_video, args.seed)
        out_path = os.path.join(args.output_dir, f"{task_id}.json")
        with open(out_path, "w") as f:
            json.dump(prompts, f, indent=2)
        print(f"{task_id}: {len(prompts)} prompts -> {out_path}")
        summary[task_id] = len(prompts)

    with open(os.path.join(args.output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nTotal: {sum(summary.values())} prompts across {len(summary)} tasks")


if __name__ == "__main__":
    main()
