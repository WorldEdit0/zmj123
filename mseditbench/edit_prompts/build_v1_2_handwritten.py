"""Build v1.2 from hand-written task modules.

Reads:
    runs/edit_prompts_v1/T{N}.json     (for structural fields)
    handwritten_t{N}.HAND_T{N}         (for instruction + target_phrase)
Writes:
    runs/edit_prompts_v1.2/T{N}.json
"""

import json, os
from pathlib import Path

from .handwritten_t1 import HAND_T1
from .handwritten_t2 import HAND_T2
from .handwritten_t3 import HAND_T3
from .handwritten_t4 import HAND_T4
from .handwritten_t5 import HAND_T5
from .handwritten_t6 import HAND_T6
from .handwritten_t7 import HAND_T7

ALL_HAND = {"T1": HAND_T1, "T2": HAND_T2, "T3": HAND_T3, "T4": HAND_T4,
            "T5": HAND_T5, "T6": HAND_T6, "T7": HAND_T7}

IN_DIR = Path("runs/edit_prompts_v1")
OUT_DIR = Path("runs/edit_prompts_v1.2")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    missing = 0
    for task in "T1 T2 T3 T4 T5 T6 T7".split():
        samples = json.load(open(IN_DIR / f"{task}.json"))
        hand = ALL_HAND[task]
        out = []
        for s in samples:
            sid = s["sample_id"]
            new = json.loads(json.dumps(s))
            if sid in hand:
                instr, tgt = hand[sid]
                new["edit"]["instruction_v1"] = s["edit"]["instruction"]
                new["edit"]["target_phrase_v1"] = s["edit"]["target_phrase"]
                new["edit"]["instruction"] = instr
                new["edit"]["target_phrase"] = tgt
                new["edit"]["author"] = "claude-handwritten-v1.2"
            else:
                missing += 1
                print(f"  MISSING handwritten for {sid}")
            out.append(new)
        with open(OUT_DIR / f"{task}.json", "w") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        ok = sum(1 for s in out if s["edit"].get("author") == "claude-handwritten-v1.2")
        print(f"{task}: {ok}/{len(out)} hand-written -> {OUT_DIR / (task + '.json')}")
        total += ok
    print(f"\nTotal hand-written: {total}")
    if missing:
        print(f"MISSING: {missing}")


if __name__ == "__main__":
    main()
