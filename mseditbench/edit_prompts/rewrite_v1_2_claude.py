"""v1.2 — Claude-authored edit prompts.

Reads v1's edit JSON to inherit (sample_id, target_entity, applicable_shots,
extra) and re-authors `instruction` + `target_phrase` per task with
hand-written sentence patterns chosen for each (video, edit) pair.

Differences from v1 (template-fill) and v1.1 (LLM rewrite):
  - short referring expression: "the woman in the red knit sweater"
    instead of dumping the full character desc inline
  - varied sentence pattern per (task, sample_idx % N) — no mechanical repetition
  - scope expressed naturally ("in every shot she appears") instead of
    bracketed shot lists
  - no two-stage stitching that produces "hair hair color" or "slow slow"
"""

from __future__ import annotations
import json, os, re
from pathlib import Path


def short_ref(desc: str, plural: bool = False) -> str:
    """'young woman with long brown hair, wearing a red knit sweater' →
    'the woman in the red knit sweater'."""
    d = desc.lower()
    if "barber" in d: head = "the barber"
    elif "mechanic" in d: head = "the mechanic"
    elif "hiker" in d: head = "the hiker"
    elif "doctor" in d: head = "the doctor"
    elif "teacher" in d: head = "the teacher"
    elif "waiter" in d: head = "the waiter"
    elif "retriever" in d or "golden retriever" in d: head = "the dog"
    elif "girl" in d and "young woman" not in d: head = "the girl"
    elif "boy" in d: head = "the boy"
    elif "elderly woman" in d: head = "the elderly woman"
    elif "older woman" in d: head = "the older woman"
    elif "older man" in d: head = "the older man"
    elif "young woman" in d: head = "the young woman"
    elif "young man" in d: head = "the young man"
    elif "muscular man" in d: head = "the muscular man"
    elif "athletic woman" in d: head = "the athletic woman"
    elif "tired woman" in d: head = "the woman"
    elif "concerned" in d and "woman" in d: head = "the woman"
    elif "woman" in d: head = "the woman"
    elif "man" in d: head = "the man"
    else: head = "the person"

    for kw in ("wearing a ", "wearing an ", "in a "):
        if kw in d:
            tail = d.split(kw, 1)[1]
            cl = tail.split(",", 1)[0].split(" and ", 1)[0]
            cl = re.sub(r"\b(over|with|on)\b.*$", "", cl).strip()
            return f"{head} in the {cl}"

    if "beard" in d:    return f"{head} with the beard"
    if "glasses" in d:  return f"{head} with glasses"
    if "ponytail" in d: return f"{head} with the ponytail"
    if "pigtails" in d: return f"{head} with pigtails"
    return head


def t1_instr(char_desc: str, target_desc: str, idx: int) -> str:
    sub = short_ref(char_desc)
    patterns = [
        f"Replace {sub} with {target_desc}, in every shot they appear.",
        f"Throughout the video, swap {sub} for {target_desc}.",
        f"Make {sub} into {target_desc}; keep their actions and positions identical across all shots.",
        f"Recast {sub} as {target_desc} for the entire scene.",
    ]
    return patterns[idx % len(patterns)]


def t2_instr(char_desc: str, attr: str, new_val: str, idx: int) -> str:
    sub = short_ref(char_desc)
    if attr == "hair color":
        return [f"Change {sub}'s hair color to {new_val.replace(' hair','')}, throughout the video.",
                f"{sub.capitalize()} now has {new_val.replace(' hair','').strip()} hair, in every shot.",
                f"Recolor {sub}'s hair to {new_val.replace(' hair','').strip()} across all shots."][idx % 3]
    if attr == "jacket color":
        return [f"Re-dress {sub} in {new_val} instead, in every shot.",
                f"Swap {sub}'s jacket for {new_val}, throughout the video.",
                f"{sub.capitalize()} now wears {new_val} for the entire video."][idx % 3]
    if attr == "shirt color":
        return [f"Change {sub}'s shirt to {new_val}, throughout the video.",
                f"Dress {sub} in {new_val} for every shot.",
                f"Replace {sub}'s shirt with {new_val} in all shots."][idx % 3]
    if attr == "glasses":
        return [f"Add {new_val} to {sub}, in every shot.",
                f"{sub.capitalize()} now wears {new_val}, throughout the video.",
                f"Place {new_val} on {sub} for the entire scene."][idx % 3]
    if attr == "hat":
        return [f"Put {new_val} on {sub}, in every shot.",
                f"{sub.capitalize()} now wears {new_val}, throughout the video.",
                f"Add {new_val} to {sub} across all shots."][idx % 3]
    return f"Change {sub}'s {attr} to {new_val}, throughout the video."


def t2_target(attr: str, new_val: str) -> str:
    if attr == "hair color":  return f"a person with {new_val.replace(' hair','').strip()} hair"
    if attr == "jacket color":return f"a person wearing {new_val}"
    if attr == "shirt color": return f"a person wearing {new_val}"
    if attr == "glasses":     return f"a person wearing {new_val}"
    if attr == "hat":         return f"a person wearing {new_val}"
    return f"a person with {new_val} {attr}"


def t3_instr(style: str, idx: int) -> str:
    patterns = [
        f"Re-render the entire video in the visual style of {style}.",
        f"Restyle every shot as {style}.",
        f"Apply a {style} look to the whole video, preserving the action and shot order.",
        f"Make the entire video read as {style}.",
    ]
    return patterns[idx % len(patterns)]


def t3_target(style: str) -> str:
    return f"a {style} look"


def t4_instr(op, old_obj, new_obj, anchor, idx) -> str:
    if op == "replace":
        return [f"Replace the {old_obj} with {new_obj}, wherever it appears.",
                f"Throughout the video, swap the {old_obj} for {new_obj}.",
                f"Where the {old_obj} would be, show {new_obj} instead."][idx % 3]
    if op == "add":
        return [f"Add {new_obj} beside the {anchor}, in every shot the {anchor} is visible.",
                f"Place {new_obj} next to the {anchor}, throughout the video.",
                f"Insert {new_obj} alongside the {anchor} in all shots where it appears."][idx % 3]
    if op == "remove":
        return [f"Remove the {old_obj} from every shot.",
                f"Erase the {old_obj} entirely from the video.",
                f"The {old_obj} should not appear in any shot."][idx % 3]
    return ""


def t4_target(op, old_obj, new_obj) -> str:
    if op == "remove": return f"a scene without the {old_obj}"
    return new_obj


def t5_instr(extra: dict, idx: int) -> str:
    order = extra.get("new_order") or []
    order_text = ", ".join(str(x) for x in order)
    return [f"Reorder the video to shot order {order_text}.",
            f"Change the shot sequence to {order_text}, preserving each shot's content.",
            f"Make the edited video play in this shot order: {order_text}."][idx % 3]


def t5_target(extra: dict) -> str:
    order = extra.get("new_order") or []
    return "shots reordered to " + ", ".join(str(x) for x in order)


def _a_an(noun: str) -> str:
    return "an" if noun and noun[0].lower() in "aeiou" else "a"


def t6_instr(extra: dict, idx: int) -> str:
    sid = extra.get("target_shot_id")
    framing = extra.get("target_framing", "")
    cam = extra.get("camera_move", "")
    art_f = _a_an(framing)
    art_c = _a_an(cam)
    patterns = [
        f"Re-shoot shot {sid} as {art_f} {framing} with {art_c} {cam}.",
        f"Shot {sid} should be filmed as {art_f} {framing}; apply {art_c} {cam}.",
        f"Re-frame shot {sid} as {art_f} {framing} and add {art_c} {cam}.",
        f"Reshoot shot {sid} with {framing} framing and {art_c} {cam}.",
    ]
    return patterns[idx % len(patterns)]


def t6_target(extra: dict) -> str:
    f = extra.get("target_framing", "")
    art = _a_an(f)
    if f.endswith(" shot") or f == "extreme close-up":
        return f"{art} {f}" if not f.endswith(" shot") else f"{art} {f}"
    return f"{art} {f} shot"


def t7_instr(extra: dict, idx: int) -> str:
    tr = extra.get("transition_style", "")
    art = _a_an(tr)
    patterns = [
        f"Replace every hard cut with {art} {tr}.",
        f"Use {tr} transitions instead of cuts between every shot.",
        f"Connect the shots with {tr} transitions rather than hard cuts.",
        f"Smooth the cuts into {tr} transitions throughout the video.",
    ]
    return patterns[idx % len(patterns)]


def t7_target(extra: dict) -> str:
    tr = extra.get("transition_style", "")
    art = _a_an(tr)
    return f"{art} {tr} transition"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

SRC_JSON = "seedance_api_example/source_prompts_multishot_v1.json"
IN_DIR = Path("runs/edit_prompts_v1")
OUT_DIR = Path("runs/edit_prompts_v1.2")
OUT_DIR.mkdir(parents=True, exist_ok=True)

src_items = json.load(open(SRC_JSON))
src_lookup = {f"{int(it['global_index']):05d}": it for it in src_items}


def char_desc_for(item, ent_id):
    for c in item.get("characters", []):
        if c["id"] == ent_id:
            return c["desc"]
    return None


def rewrite_t1(samples):
    out = []
    for i, s in enumerate(samples):
        item = src_lookup[s["video_id"]]
        edit = s["edit"]
        char_desc = char_desc_for(item, edit["target_entity"])
        target = edit["target_phrase"]
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t1_instr(char_desc, target, i)
        new_edit["target_phrase"] = target  # already clean for T1
        out.append({**s, "edit": new_edit})
    return out


def _t2_extract(instr_v1: str, char_desc: str, target_phrase_v1: str):
    """Recover (attribute, new_val) from v1 — generate.py used:
       'a person with {new_value} {attribute_kind}'"""
    parts = target_phrase_v1.replace("a person with ", "").rsplit(" ", 2)
    if len(parts) >= 2 and parts[-1] in ("color", "glasses", "hat"):
        if parts[-1] == "color":
            attr = " ".join(parts[-2:])  # "hair color" or "jacket color" or "shirt color"
            new_val = " ".join(parts[:-2])
        else:
            attr = parts[-1]
            new_val = " ".join(parts[:-1])
    else:
        attr = "attribute"
        new_val = target_phrase_v1.replace("a person with ", "")
    return attr, new_val


def rewrite_t2(samples):
    out = []
    for i, s in enumerate(samples):
        item = src_lookup[s["video_id"]]
        edit = s["edit"]
        char_desc = char_desc_for(item, edit["target_entity"])
        attr, new_val = _t2_extract(edit["instruction"], char_desc, edit["target_phrase"])
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t2_instr(char_desc, attr, new_val, i)
        new_edit["target_phrase"] = t2_target(attr, new_val)
        out.append({**s, "edit": new_edit})
    return out


def rewrite_t3(samples):
    out = []
    for i, s in enumerate(samples):
        edit = s["edit"]
        style = edit["target_phrase"].replace(" look", "")
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t3_instr(style, i)
        new_edit["target_phrase"] = t3_target(style)
        out.append({**s, "edit": new_edit})
    return out


def rewrite_t4(samples):
    out = []
    for i, s in enumerate(samples):
        edit = s["edit"]
        ex = edit.get("extra", {})
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t4_instr(ex.get("op"), ex.get("old_object"),
                                            ex.get("new_object"), ex.get("anchor"), i)
        new_edit["target_phrase"] = t4_target(ex.get("op"), ex.get("old_object"),
                                               ex.get("new_object"))
        out.append({**s, "edit": new_edit})
    return out


def rewrite_t5(samples):
    out = []
    for i, s in enumerate(samples):
        edit = s["edit"]
        ex = edit.get("extra", {})
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t5_instr(ex, i)
        new_edit["target_phrase"] = t5_target(ex)
        out.append({**s, "edit": new_edit})
    return out


def rewrite_t6(samples):
    out = []
    for i, s in enumerate(samples):
        edit = s["edit"]
        ex = edit.get("extra", {})
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t6_instr(ex, i)
        new_edit["target_phrase"] = t6_target(ex)
        out.append({**s, "edit": new_edit})
    return out


def rewrite_t7(samples):
    out = []
    for i, s in enumerate(samples):
        edit = s["edit"]
        ex = edit.get("extra", {})
        new_edit = dict(edit)
        new_edit["instruction_v1"] = edit["instruction"]
        new_edit["target_phrase_v1"] = edit["target_phrase"]
        new_edit["instruction"] = t7_instr(ex, i)
        new_edit["target_phrase"] = t7_target(ex)
        out.append({**s, "edit": new_edit})
    return out


REWRITERS = {"T1": rewrite_t1, "T2": rewrite_t2, "T3": rewrite_t3, "T4": rewrite_t4,
             "T5": rewrite_t5, "T6": rewrite_t6, "T7": rewrite_t7}


def main():
    total = 0
    for task in "T1 T2 T3 T4 T5 T6 T7".split():
        in_path = IN_DIR / f"{task}.json"
        samples = json.load(open(in_path))
        rewritten = REWRITERS[task](samples)
        out_path = OUT_DIR / f"{task}.json"
        with open(out_path, "w") as f:
            json.dump(rewritten, f, indent=2, ensure_ascii=False)
        print(f"{task}: {len(rewritten)} prompts -> {out_path}")
        total += len(rewritten)
    print(f"\nTotal: {total} v1.2 prompts (Claude-authored)")


if __name__ == "__main__":
    main()
