from __future__ import annotations

from collections import defaultdict
import re


def clean_text(text: str | None) -> str:
    return (text or "").strip(" \t\r\n.,;:")


def as_query_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(v) for v in value if v]


def shot_instruction_map(instruction: str, *, edit_only: bool = False) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in (instruction or "").splitlines():
        m = re.match(r"\s*Shot\s+(\d+)\s*:\s*(.*)", raw, flags=re.IGNORECASE)
        if not m:
            continue
        shot_id = int(m.group(1))
        rest = m.group(2).strip()
        role_m = re.match(r"^\[(EDIT|KEEP)\]\s*(.*)", rest, flags=re.IGNORECASE)
        role = role_m.group(1).upper() if role_m else None
        if edit_only and role != "EDIT":
            continue
        text = role_m.group(2).strip() if role_m else rest
        text = re.split(
            r"\.\s*(?:Apply this edit only|Do not inherit|If the same)",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        out[shot_id] = clean_text(text)
    return out


def vlm_instruction_for_applicable_shots(
    default_instruction: str,
    applicable_shots: list[int],
) -> str:
    edit_map = shot_instruction_map(default_instruction, edit_only=True)
    if not edit_map:
        return default_instruction
    selected = []
    for shot_id in applicable_shots:
        text = edit_map.get(int(shot_id))
        if text:
            selected.append(clean_text(text))
    if not selected:
        return default_instruction
    return " ".join(f"{text}." for text in selected)


def build_t9_metric_plan(sample: dict) -> dict | None:
    edit = sample.get("edit") or {}
    if edit.get("task_id") != "T9":
        return None

    extra = edit.get("extra") or {}
    mode = extra.get("mode")
    plan = {"mode": mode, "ee_units": []}
    all_shot_ids = [int(s["shot_id"]) for s in sample.get("shots") or []]

    if mode == "independent_per_shot":
        instruction_by_shot = shot_instruction_map(edit.get("instruction") or "")
        for row in extra.get("shot_edits") or []:
            shot_id = int(row["shot_id"])
            instruction = (
                instruction_by_shot.get(shot_id)
                or row.get("target_phrase")
                or edit.get("instruction")
                or ""
            )
            plan["ee_units"].append({
                "unit_id": f"shot-{shot_id}",
                "edit_id": f"shot-{shot_id}",
                "shot_id": shot_id,
                "source_task": row.get("source_task"),
                "edit_type": row.get("edit_type"),
                "instruction": instruction,
                "target_phrase": row.get("target_phrase") or edit.get("target_phrase") or "",
                "source_queries": as_query_list(
                    row.get("metric_source_queries", row.get("metric_source_query"))
                ),
                "edited_queries": as_query_list(
                    row.get("metric_edited_queries", row.get("metric_target_query"))
                ),
                "applicable_shots": [shot_id],
                "non_a_applicable_shots": [s for s in all_shot_ids if s != shot_id],
                "csep_applicable": False,
            })
        return plan

    if mode == "sequential_two_edit_prompt":
        components = {
            str(c.get("edit_id")): c
            for c in (extra.get("prompt_components") or [])
            if c.get("edit_id") is not None
        }
        object_edits = {
            str(c.get("edit_id")): c
            for c in (extra.get("object_edits") or [])
            if c.get("edit_id") is not None
        }
        targets_by_edit: dict[str, set[int]] = defaultdict(set)
        for impact in extra.get("metric_shot_impacts") or []:
            shot_id = int(impact.get("shot_id"))
            for target in impact.get("evaluation_targets") or []:
                edit_id = str(target.get("edit_id"))
                targets_by_edit[edit_id].add(shot_id)

        edit_ids = list(components.keys() or object_edits.keys())
        for edit_id in edit_ids:
            comp = components.get(edit_id) or {}
            obj = object_edits.get(edit_id) or {}
            shots_from_targets = sorted(targets_by_edit.get(edit_id, set()))
            fallback_shots = comp.get("applicable_shots") or obj.get("applicable_shots") or []
            applicable_shots = shots_from_targets or [int(s) for s in fallback_shots]
            instruction = comp.get("instruction_fragment") or edit.get("instruction") or ""
            plan["ee_units"].append({
                "unit_id": f"edit-{edit_id}",
                "edit_id": edit_id,
                "instruction": instruction,
                "target_phrase": comp.get("target_phrase") or obj.get("target_phrase") or "",
                "applicable_shots": applicable_shots,
                "csep_applicable": len(applicable_shots) >= 2,
            })
        return plan

    return plan


def build_vlm_units(sample: dict) -> tuple[list[dict], str | None]:
    edit = sample.get("edit") or {}
    task_id = edit.get("task_id")
    if task_id == "T5" or (edit.get("mask_queries") or {}).get("edit_type") == "transition_style":
        return [], f"task {task_id} not v3-applicable"

    t9_plan = build_t9_metric_plan(sample)
    if t9_plan is not None:
        return t9_plan.get("ee_units") or [], None

    shots = [int(s.get("shot_id", i + 1)) for i, s in enumerate(sample.get("shots") or [])]
    applicable = [int(s) for s in edit.get("applicable_shots", shots)]
    instruction = vlm_instruction_for_applicable_shots(edit.get("instruction") or "", applicable)
    return [{
        "unit_id": "prompt",
        "edit_id": "prompt",
        "instruction": instruction,
        "target_phrase": edit.get("target_phrase") or "",
        "applicable_shots": applicable,
        "csep_applicable": len(applicable) >= 2,
    }], None
