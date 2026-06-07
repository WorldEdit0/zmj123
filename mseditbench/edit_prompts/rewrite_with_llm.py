"""LLM-rewrite edit prompts with Seed 2.0 Lite.

Take existing T*.json from a prompt dir, rewrite each `instruction` and
`target_phrase` to natural English while preserving every visual descriptor,
shot reference, and edit semantic. Write to a v1.1 dir.

Multi-threaded via ThreadPoolExecutor (per `run_rewrite_baseline_seed.py`
pattern). Resume-safe: existing rewritten samples in the output dir are
loaded and skipped.

CLI:
    export ARK_API_KEY=...
    python -m mseditbench.edit_prompts.rewrite_with_llm \
        --input_dir runs/edit_prompts_v1 \
        --output_dir runs/edit_prompts_v1.1 \
        --tasks T1,T2,T3,T4,T5,T6,T7 \
        --max_workers 32 \
        --model doubao-seed-2-0-lite-260215

Each output JSON has the same schema as input plus per-edit fields:
    instruction_original, target_phrase_original, llm_notes, llm_attempts,
    llm_status
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm
from volcenginesdkarkruntime import Ark


SYSTEM_PROMPT = """You are improving a video editing instruction. The instruction will be sent verbatim to a video editing model. Your job is to make it natural fluent English without changing what it asks for.

You will receive:
  - task_id: one of T1..T7 (kind of edit, see TASK_GUIDE below)
  - instruction: original (sometimes awkward) instruction
  - target_phrase: short noun phrase used downstream for CLIP-T matching
  - extra: any task-specific structured fields

TASK_GUIDE:
  T1 — replace either a dynamic entity or a static object across all shots
  T2 — change one character's attribute (color / material / clothing type / hairstyle / accessory)
  T3 — global visual style re-render only
  T4 — add or delete static/dynamic objects or entities, no replacement
  T5 — structural: reorder shots
  T6 — re-shoot a specific shot with a different framing or camera move
  T7 — global lighting re-render only

Rules:
  1. Preserve every visual descriptor (colors, materials, named clothing,
     hair, accessories, objects, named places). Do not invent details.
  2. Preserve all numerical shot references exactly (e.g. "shot 3", "from
     shot 2 onward").
  3. Fix awkward duplication: e.g. "bright pink hair hair color" should
     become "bright pink hair color"; "slow slow dolly-in" -> "slow dolly-in".
  4. Output one or two fluent sentences. Stay under 60 words total.
  5. Do NOT add constraints or hedges (no "preserve X", "do not change",
     "must keep", "carefully", etc).
  6. Rewrite target_phrase too if it has obvious redundancy or awkwardness;
     otherwise keep it nearly identical. target_phrase must remain a noun
     phrase suitable for CLIP image-text matching (no verbs, no commands).

Return strict JSON only, no markdown, no commentary:
{
  "rewritten_instruction": "...",
  "rewritten_target_phrase": "...",
  "notes": ""
}"""


_thread_local = threading.local()


def _get_client(api_key: str, base_url: str) -> Ark:
    c = getattr(_thread_local, "client", None)
    if c is None:
        c = Ark(base_url=base_url, api_key=api_key)
        _thread_local.client = c
    return c


def _build_user_message(edit: dict) -> str:
    extra = edit.get("extra", {}) or {}
    extra_keys = ["op", "object_kind", "replace_kind", "old_object", "new_object",
                  "old_entity", "new_entity", "anchor", "style", "lighting",
                  "target_framing", "camera_move", "new_order"]
    extra_compact = {k: extra.get(k) for k in extra_keys if extra.get(k) is not None}
    payload = {
        "task_id": edit.get("task_id"),
        "instruction": edit.get("instruction"),
        "target_phrase": edit.get("target_phrase"),
        "extra": extra_compact,
        "applicable_shots": edit.get("applicable_shots"),
    }
    return "Rewrite this:\n" + json.dumps(payload, ensure_ascii=False)


def _strip_json_md(text: str) -> str:
    return (text or "").replace("```json", "").replace("```", "").strip()


def _safe_parse(text: str) -> dict:
    s = _strip_json_md(text)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            return json.loads(s[i : j + 1])
        raise


def rewrite_one(sample: dict, args) -> dict:
    out = json.loads(json.dumps(sample))  # deep copy
    edit = out["edit"]
    edit["instruction_original"] = edit["instruction"]
    edit["target_phrase_original"] = edit["target_phrase"]

    last_err = None
    for attempt in range(1, args.max_retries + 2):
        try:
            client = _get_client(args.api_key, args.base_url)
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_message(edit)},
                ],
                temperature=args.temperature,
            )
            raw = resp.choices[0].message.content
            parsed = _safe_parse(raw)
            new_instr = str(parsed.get("rewritten_instruction", "")).strip()
            new_tgt = str(parsed.get("rewritten_target_phrase", "")).strip()
            if not new_instr:
                raise ValueError(f"empty rewritten_instruction; raw={raw[:200]}")
            edit["instruction"] = new_instr
            if new_tgt:
                edit["target_phrase"] = new_tgt
            edit["llm_notes"] = str(parsed.get("notes", "")).strip()
            edit["llm_attempts"] = attempt
            edit["llm_status"] = "succeeded"
            edit["llm_model"] = args.model
            return out
        except Exception as e:
            last_err = e
            if attempt <= args.max_retries:
                time.sleep(args.retry_sleep * (2 ** (attempt - 1)) + random.random())

    edit["llm_status"] = "failed"
    edit["llm_attempts"] = args.max_retries + 1
    edit["llm_error"] = str(last_err)[:500]
    return out


def load_done_ids(out_path: Path) -> set:
    if not out_path.exists():
        return set()
    try:
        data = json.load(open(out_path))
    except Exception:
        return set()
    return {s["sample_id"] for s in data
            if s.get("edit", {}).get("llm_status") == "succeeded"}


def process_task(task_id: str, args):
    in_path = Path(args.input_dir) / f"{task_id}.json"
    out_path = Path(args.output_dir) / f"{task_id}.json"
    if not in_path.exists():
        print(f"[skip] {in_path} not found")
        return
    samples = json.load(open(in_path))

    done_ids = load_done_ids(out_path) if args.resume else set()
    todo = [s for s in samples if s["sample_id"] not in done_ids]
    print(f"{task_id}: {len(samples)} total, {len(done_ids)} resumed, {len(todo)} to rewrite")

    # load any existing rewritten outputs for resume
    existing = []
    if args.resume and out_path.exists():
        existing = [s for s in json.load(open(out_path))
                    if s.get("edit", {}).get("llm_status") == "succeeded"]

    results_by_id = {s["sample_id"]: s for s in existing}
    write_lock = threading.Lock()

    def _write_partial():
        ordered = [results_by_id[s["sample_id"]] for s in samples
                   if s["sample_id"] in results_by_id]
        with open(out_path, "w") as f:
            json.dump(ordered, f, indent=2, ensure_ascii=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futures = {ex.submit(rewrite_one, s, args): s["sample_id"] for s in todo}
        last_flush = time.time()
        for fut in tqdm(as_completed(futures), total=len(futures), desc=task_id):
            try:
                r = fut.result()
            except Exception as e:
                sid = futures[fut]
                print(f"[critical] {sid}: {e}")
                continue
            with write_lock:
                results_by_id[r["sample_id"]] = r
                # periodic flush every 30s so a crash doesn't wipe everything
                if time.time() - last_flush > 30:
                    _write_partial()
                    last_flush = time.time()

    _write_partial()
    n_ok = sum(1 for s in results_by_id.values()
               if s.get("edit", {}).get("llm_status") == "succeeded")
    print(f"{task_id}: wrote {len(results_by_id)} samples, {n_ok} ok -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_dir", required=True)
    ap.add_argument("--output_dir", required=True)
    ap.add_argument("--tasks", default="T1,T2,T3,T4,T5,T6,T7")
    ap.add_argument("--model", default="doubao-seed-2-0-lite-260215")
    ap.add_argument("--api_key", default=os.environ.get("ARK_API_KEY",
                    "bca56c77-9f9b-4568-a4bc-5311fb678e7c"))
    ap.add_argument("--base_url", default="https://ark.cn-beijing.volces.com/api/v3")
    ap.add_argument("--max_workers", type=int, default=32)
    ap.add_argument("--max_retries", type=int, default=2)
    ap.add_argument("--retry_sleep", type=float, default=2.0)
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no_resume", dest="resume", action="store_false")
    args = ap.parse_args()

    if not args.api_key:
        raise SystemExit("Set ARK_API_KEY env var or pass --api_key")

    os.makedirs(args.output_dir, exist_ok=True)
    for task_id in [t.strip() for t in args.tasks.split(",") if t.strip()]:
        process_task(task_id, args)


if __name__ == "__main__":
    main()
