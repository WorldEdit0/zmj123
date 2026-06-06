"""Three-way blind judge: v1 (template) vs v1.1 (Seed Lite) vs v1.2 (Claude).

Uses Seed 2.0 Pro as judge to avoid v1.1 self-bias (v1.1 was Seed 2.0 Lite).
For each sample we shuffle the (v1, v1.1, v1.2) order into (A, B, C) so the
judge can't game position; we record the mapping per sample for decoding.

Judge scores each on three 1-5 axes (naturalness / faithfulness / clarity)
and picks one overall winner. Outputs:
  runs/eval_3way/per_sample.jsonl   one line per sample with verdict + mapping
  runs/eval_3way/summary.md         aggregate win/score tables

CLI:
    export ARK_API_KEY=...
    python -m mseditbench.edit_prompts.judge_3way \
        --tasks T1,T2,T3,T4,T5,T6,T7 \
        --max_workers 32 \
        --output_dir runs/eval_3way
"""

from __future__ import annotations
import argparse, json, os, random, threading, time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm import tqdm
from volcenginesdkarkruntime import Ark


JUDGE_SYSTEM = """You are a strict editor reviewing three candidate instructions for the SAME video edit task. Each instruction will be sent verbatim to a video editing model.

Score each candidate on three axes (1-5 integers):
  - naturalness: fluency and idiomatic English. 5 = native, no awkwardness;
    1 = many grammatical errors or unnatural phrasing.
  - faithfulness: how clearly it conveys the intended edit (subject, target,
    scope). 5 = unambiguous and complete; 1 = vague or missing key info.
  - clarity: conciseness and directness. 5 = nothing wasted, no fluff;
    1 = verbose, convoluted, or redundant.

Then pick the overall best — exactly one of "A", "B", or "C". No ties on the
overall winner.

Return strict JSON, no markdown:
{"A":{"naturalness":N,"faithfulness":N,"clarity":N},
 "B":{"naturalness":N,"faithfulness":N,"clarity":N},
 "C":{"naturalness":N,"faithfulness":N,"clarity":N},
 "winner":"A","reason":"one short sentence"}"""


_thread_local = threading.local()


def _client(api_key, base_url):
    c = getattr(_thread_local, "client", None)
    if c is None:
        c = Ark(base_url=base_url, api_key=api_key)
        _thread_local.client = c
    return c


def _safe_json(text: str) -> dict:
    s = (text or "").replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i, j = s.find("{"), s.rfind("}")
        if i >= 0 and j > i:
            return json.loads(s[i:j+1])
        raise


def load_three_versions(task: str) -> list[dict]:
    """Build [{sample_id, v1, v1.1, v1.2, task_id}, ...] joined on sample_id."""
    v1   = {s["sample_id"]: s for s in json.load(open(f"runs/edit_prompts_v1/{task}.json"))}
    v11  = {s["sample_id"]: s for s in json.load(open(f"runs/edit_prompts_v1.1/{task}.json"))}
    v12  = {s["sample_id"]: s for s in json.load(open(f"runs/edit_prompts_v1.2/{task}.json"))}

    common = sorted(set(v1) & set(v11) & set(v12))
    out = []
    for sid in common:
        out.append({
            "sample_id": sid,
            "task_id": task,
            "v1":   {"instruction": v1[sid]["edit"]["instruction"],
                     "target_phrase": v1[sid]["edit"]["target_phrase"]},
            "v1.1": {"instruction": v11[sid]["edit"]["instruction"],
                     "target_phrase": v11[sid]["edit"]["target_phrase"]},
            "v1.2": {"instruction": v12[sid]["edit"]["instruction"],
                     "target_phrase": v12[sid]["edit"]["target_phrase"]},
        })
    return out


def judge_one(triple: dict, args) -> dict:
    rng = random.Random(triple["sample_id"])  # deterministic shuffle per sample
    versions = ["v1", "v1.1", "v1.2"]
    rng.shuffle(versions)
    label_to_version = dict(zip("ABC", versions))    # {"A":"v1.1", ...}
    version_to_label = {v: l for l, v in label_to_version.items()}

    user_msg_lines = [f"Task: {triple['task_id']} (video edit)"]
    for label in "ABC":
        v = label_to_version[label]
        user_msg_lines.append(f"\n[{label}] instruction: {triple[v]['instruction']}")
        user_msg_lines.append(f"[{label}] target_phrase: {triple[v]['target_phrase']}")
    user_msg = "\n".join(user_msg_lines)

    last_err = None
    for attempt in range(1, args.max_retries + 2):
        try:
            client = _client(args.api_key, args.base_url)
            resp = client.chat.completions.create(
                model=args.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
            )
            raw = resp.choices[0].message.content
            parsed = _safe_json(raw)
            winner_label = str(parsed.get("winner", "")).strip().upper()[:1]
            if winner_label not in "ABC":
                raise ValueError(f"bad winner {winner_label!r}; raw={raw[:200]}")
            return {
                "sample_id": triple["sample_id"],
                "task_id":   triple["task_id"],
                "label_to_version": label_to_version,
                "scores": {label_to_version[l]: parsed.get(l, {}) for l in "ABC"},
                "winner_label":   winner_label,
                "winner_version": label_to_version[winner_label],
                "reason": parsed.get("reason", ""),
                "status": "ok",
                "attempts": attempt,
            }
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            # 429 / rate-limit: long backoff
            if "429" in msg or "rate" in msg or "tpm" in msg or "toomanyrequest" in msg:
                time.sleep(15 + 5 * attempt + random.random() * 3)
            else:
                time.sleep(args.retry_sleep * (2 ** (attempt - 1)) + random.random())
    return {
        "sample_id": triple["sample_id"], "task_id": triple["task_id"],
        "status": "failed", "error": str(last_err)[:300],
        "label_to_version": label_to_version,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="T1,T2,T3,T4,T5,T6,T7")
    ap.add_argument("--output_dir", default="runs/eval_3way")
    ap.add_argument("--model", default="doubao-seed-2-0-pro-260215")
    ap.add_argument("--api_key", default=os.environ.get("ARK_API_KEY",
                    "bca56c77-9f9b-4568-a4bc-5311fb678e7c"))
    ap.add_argument("--base_url", default="https://ark.cn-beijing.volces.com/api/v3")
    ap.add_argument("--max_workers", type=int, default=8)
    ap.add_argument("--max_retries", type=int, default=4)
    ap.add_argument("--retry_sleep", type=float, default=2.0)
    ap.add_argument("--limit_per_task", type=int, default=0,
                    help="0 = all samples")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_sample_path = out_dir / "per_sample.jsonl"

    # gather triples
    all_triples = []
    for t in [x.strip() for x in args.tasks.split(",") if x.strip()]:
        triples = load_three_versions(t)
        if args.limit_per_task:
            triples = triples[: args.limit_per_task]
        all_triples.extend(triples)
    print(f"Judging {len(all_triples)} triples across "
          f"{args.tasks} with model {args.model}")

    write_lock = threading.Lock()
    f_out = open(per_sample_path, "w", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
        futures = [ex.submit(judge_one, t, args) for t in all_triples]
        results = []
        for fut in tqdm(as_completed(futures), total=len(futures), desc="judge"):
            try:
                r = fut.result()
            except Exception as e:
                print(f"[critical] {e}")
                continue
            with write_lock:
                f_out.write(json.dumps(r, ensure_ascii=False) + "\n")
                f_out.flush()
            results.append(r)
    f_out.close()

    # aggregate
    summary_lines = ["# 3-way blind judgment: v1 vs v1.1 vs v1.2", ""]
    summary_lines.append(f"Judge model: `{args.model}`")
    summary_lines.append(f"Total triples judged: {sum(1 for r in results if r.get('status') == 'ok')}")
    summary_lines.append("")

    by_task = defaultdict(list)
    for r in results:
        if r.get("status") == "ok":
            by_task[r["task_id"]].append(r)

    summary_lines.append("## Win counts (overall winner per sample)\n")
    summary_lines.append("| Task | n | v1 wins | v1.1 wins | v1.2 wins |")
    summary_lines.append("|---|---|---|---|---|")
    overall = Counter()
    for t in sorted(by_task):
        wins = Counter(r["winner_version"] for r in by_task[t])
        n = sum(wins.values())
        summary_lines.append(f"| {t} | {n} | {wins['v1']} | {wins['v1.1']} | {wins['v1.2']} |")
        overall.update(wins)
    summary_lines.append(f"| **all** | **{sum(overall.values())}** | "
                         f"**{overall['v1']}** | **{overall['v1.1']}** | **{overall['v1.2']}** |")
    summary_lines.append("")

    summary_lines.append("## Mean sub-scores (1-5 each)\n")
    summary_lines.append("| Task | metric | v1 | v1.1 | v1.2 |")
    summary_lines.append("|---|---|---|---|---|")
    for t in sorted(by_task) + ["all"]:
        rs = [r for r in results if r.get("status") == "ok"
              and (t == "all" or r["task_id"] == t)]
        if not rs:
            continue
        for axis in ("naturalness", "faithfulness", "clarity"):
            row = {"v1": [], "v1.1": [], "v1.2": []}
            for r in rs:
                for v in row:
                    sc = r["scores"].get(v, {})
                    if axis in sc:
                        try:    row[v].append(float(sc[axis]))
                        except: pass
            mean = {v: (sum(xs) / len(xs) if xs else 0.0) for v, xs in row.items()}
            summary_lines.append(f"| {t} | {axis} | {mean['v1']:.2f} | "
                                 f"{mean['v1.1']:.2f} | {mean['v1.2']:.2f} |")
        summary_lines.append("|  |  |  |  |  |")
    summary_lines.append("")

    summary_lines.append("## Sample reasons (5 per task)\n")
    for t in sorted(by_task):
        summary_lines.append(f"### {t}")
        for r in by_task[t][:5]:
            summary_lines.append(f"- `{r['sample_id']}` → **{r['winner_version']}** — {r['reason']}")
        summary_lines.append("")

    with open(out_dir / "summary.md", "w") as f:
        f.write("\n".join(summary_lines))

    print(f"\nWrote {per_sample_path}")
    print(f"Wrote {out_dir / 'summary.md'}")
    print(f"\nOverall winners: v1={overall['v1']}  v1.1={overall['v1.1']}  v1.2={overall['v1.2']}")


if __name__ == "__main__":
    main()
