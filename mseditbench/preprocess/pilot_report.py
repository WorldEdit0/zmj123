"""
Aggregate {video_id}.shots.json files into a pilot validation report.

Outputs:
  - pilot_report.md  : human-readable markdown
  - pilot_report.json: machine-readable with per-video records + summary
  - (optional) pilot_report.html with embedded contact sheet thumbnails

Key questions answered:
  1. Hit rate: how many videos have actual_shots == expected_shots?
  2. Off-by-one rate (close but not exact)?
  3. Are TransNetV2 and PySceneDetect agreeing? (= detection trustworthy?)
  4. Which categories / scene_ids fail most?
  5. Concrete recommended next action (scale up vs. fix prompt vs. tune threshold)
"""

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List


def load_source_metadata(source_json: str) -> Dict[str, Dict]:
    with open(source_json, "r") as f:
        items = json.load(f)
    return {f"{int(it['global_index']):05d}": it for it in items}


def load_shots_results(shots_dir: str) -> List[Dict]:
    out = []
    for sf in sorted(Path(shots_dir).glob("*.shots.json")):
        with open(sf, "r") as f:
            out.append(json.load(f))
    return out


def aggregate(results: List[Dict], sources: Dict[str, Dict]) -> Dict:
    n_total = len(results)
    if n_total == 0:
        return {"error": "no shots.json files found"}

    per_video = []
    n_exact = n_off_by_one = n_off_more = 0
    n_tn_ps_count_match = n_tn_ps_full_agree = 0
    n_tn_available = 0
    category_stats = defaultdict(lambda: {"total": 0, "exact": 0})
    expected_distribution = Counter()
    actual_distribution = Counter()
    diff_distribution = Counter()
    failed_videos = []

    for r in results:
        vid = r.get("video_id", "?")
        src = sources.get(vid, {})

        if "error" in r:
            per_video.append({
                "video_id": vid,
                "expected": src.get("expected_shots"),
                "actual": None,
                "match": False,
                "note": f"ERROR: {r['error']}",
            })
            failed_videos.append(vid)
            continue

        exp = r.get("expected_shots") or src.get("expected_shots")
        cons = r.get("consensus_n_shots")
        tn_n = (r.get("transnetv2") or {}).get("n_shots")
        ps_n = (r.get("pyscenedetect") or {}).get("n_shots")
        agree = r.get("agreement", {})

        if tn_n is not None:
            n_tn_available += 1
        if tn_n is not None and ps_n is not None and tn_n == ps_n:
            n_tn_ps_count_match += 1
        if agree.get("shot_count_match") and agree.get("boundaries_within_tolerance"):
            n_tn_ps_full_agree += 1

        actual_distribution[cons] += 1
        if exp is not None:
            expected_distribution[exp] += 1
            diff = (cons - exp) if cons is not None else None
            diff_distribution[diff] += 1
            match = (cons == exp)
            cat = src.get("category", "unknown")
            category_stats[cat]["total"] += 1
            if match:
                n_exact += 1
                category_stats[cat]["exact"] += 1
            elif diff is not None and abs(diff) == 1:
                n_off_by_one += 1
            else:
                n_off_more += 1
        else:
            match = None

        per_video.append({
            "video_id": vid,
            "scene_id": src.get("scene_id", ""),
            "category": src.get("category", ""),
            "expected": exp,
            "actual_consensus": cons,
            "actual_transnetv2": tn_n,
            "actual_pyscenedetect": ps_n,
            "boundaries_agree": agree.get("boundaries_within_tolerance"),
            "match": match,
            "note": "" if match else ("ERROR" if cons is None else f"diff={cons - exp if exp is not None else 'N/A'}"),
        })

    # Recommendations
    hit_rate = n_exact / n_total if n_total else 0
    recommendations = []
    if hit_rate >= 0.85:
        recommendations.append(
            f"✅ Hit rate {hit_rate:.0%} >= 85%. SAFE TO SCALE: extend prompt set to 150 videos."
        )
    elif hit_rate >= 0.70:
        recommendations.append(
            f"⚠️  Hit rate {hit_rate:.0%} in 70-85% range. CONDITIONAL: scale up, but inspect failing cases in contact sheets first."
        )
    else:
        recommendations.append(
            f"❌ Hit rate {hit_rate:.0%} < 70%. DO NOT SCALE YET. Tune prompts or thresholds first."
        )

    if n_off_by_one > n_off_more and n_off_by_one > 0:
        recommendations.append(
            f"Most misses are off-by-one ({n_off_by_one} vs {n_off_more} off-by-more). "
            "Likely Seedance over/under-cutting by one shot. Try stronger cut tags "
            "(`[Cut to wide shot:]`) or merge adjacent shot descriptions."
        )

    if n_tn_available > 0 and n_tn_ps_count_match / n_tn_available < 0.7:
        recommendations.append(
            f"TransNetV2 and PySceneDetect disagree on count for {n_tn_available - n_tn_ps_count_match}/{n_tn_available} videos. "
            "Detection is unreliable — manually verify a few contact sheets before trusting any numbers."
        )

    if not recommendations:
        recommendations.append("No major issues detected; proceed cautiously.")

    summary = {
        "n_total": n_total,
        "n_exact_match": n_exact,
        "n_off_by_one": n_off_by_one,
        "n_off_more": n_off_more,
        "hit_rate": round(hit_rate, 3),
        "off_by_one_rate": round(n_off_by_one / n_total, 3) if n_total else 0,
        "n_failed": len(failed_videos),
        "transnetv2_available_on": n_tn_available,
        "tn_ps_count_match_count": n_tn_ps_count_match,
        "tn_ps_full_agree_count": n_tn_ps_full_agree,
        "expected_shot_distribution": dict(expected_distribution),
        "actual_shot_distribution": dict(actual_distribution),
        "diff_distribution": {str(k): v for k, v in diff_distribution.items()},
        "category_stats": {
            k: {**v, "hit_rate": round(v["exact"] / v["total"], 3) if v["total"] else 0}
            for k, v in category_stats.items()
        },
        "failed_videos": failed_videos,
        "recommendations": recommendations,
    }

    return {"summary": summary, "per_video": per_video}


def write_markdown(report: Dict, contact_sheets_dir: str, output_md: str):
    s = report["summary"]
    pv = report["per_video"]
    lines = []

    lines.append("# MSEdit-Bench Pilot — Shot Detection Validation Report\n")
    lines.append(f"Total videos: **{s['n_total']}**\n")

    lines.append("## Summary\n")
    lines.append(f"- ✅ Exact match (actual == expected): **{s['n_exact_match']} / {s['n_total']}** ({s['hit_rate']:.0%})")
    lines.append(f"- ⚠️  Off-by-one: **{s['n_off_by_one']}** ({s['off_by_one_rate']:.0%})")
    lines.append(f"- ❌ Off by more / failed: **{s['n_off_more']}** + **{s['n_failed']} errors**")
    lines.append(f"- TransNetV2 ran on **{s['transnetv2_available_on']} / {s['n_total']}** videos")
    if s["transnetv2_available_on"]:
        lines.append(f"- TransNetV2 ↔ PySceneDetect count agreement: **{s['tn_ps_count_match_count']} / {s['transnetv2_available_on']}**")
        lines.append(f"- TransNetV2 ↔ PySceneDetect full agreement (count + boundaries within 0.25s): **{s['tn_ps_full_agree_count']} / {s['transnetv2_available_on']}**")
    lines.append("")

    lines.append("## Recommendations\n")
    for r in s["recommendations"]:
        lines.append(f"- {r}")
    lines.append("")

    lines.append("## Distributions\n")
    lines.append(f"Expected shots: `{s['expected_shot_distribution']}`")
    lines.append(f"Actual shots: `{s['actual_shot_distribution']}`")
    lines.append(f"Diff (actual − expected): `{s['diff_distribution']}`")
    lines.append("")

    lines.append("## Per-category hit rate\n")
    lines.append("| Category | Total | Exact | Hit rate |")
    lines.append("|---|---|---|---|")
    for cat, v in sorted(s["category_stats"].items(), key=lambda x: -x[1]["hit_rate"]):
        lines.append(f"| `{cat}` | {v['total']} | {v['exact']} | {v['hit_rate']:.0%} |")
    lines.append("")

    lines.append("## Per-video records\n")
    lines.append("| video_id | scene_id | category | expected | actual (consensus) | TN | PS | TN↔PS agree | match | note |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for v in pv:
        match_icon = "✅" if v["match"] else ("❌" if v["match"] is False else "—")
        lines.append(
            f"| `{v['video_id']}` | `{v.get('scene_id','')}` | `{v.get('category','')}` | "
            f"{v['expected']} | {v.get('actual_consensus')} | "
            f"{v.get('actual_transnetv2','-')} | {v.get('actual_pyscenedetect','-')} | "
            f"{'✓' if v.get('boundaries_agree') else '✗'} | {match_icon} | {v['note']} |"
        )
    lines.append("")

    if contact_sheets_dir:
        lines.append("## Contact sheets\n")
        for v in pv:
            cs_path = os.path.join(contact_sheets_dir, f"{v['video_id']}_contact.jpg")
            if os.path.exists(cs_path):
                rel = os.path.relpath(cs_path, os.path.dirname(output_md))
                lines.append(f"### {v['video_id']} ({v.get('scene_id','')})")
                lines.append(f"![{v['video_id']}]({rel})")
                lines.append("")

    with open(output_md, "w") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Aggregate shots.json into a pilot validation report")
    ap.add_argument("--shots_dir", required=True)
    ap.add_argument("--source_json", required=True, help="Path to source_prompts_multishot_v1.json")
    ap.add_argument("--contact_sheets_dir", default="", help="If given, embed contact sheets in the markdown")
    ap.add_argument("--output_md", default="pilot_report.md")
    ap.add_argument("--output_json", default="pilot_report.json")
    args = ap.parse_args()

    sources = load_source_metadata(args.source_json)
    results = load_shots_results(args.shots_dir)
    report = aggregate(results, sources)

    with open(args.output_json, "w") as f:
        json.dump(report, f, indent=2)
    write_markdown(report, args.contact_sheets_dir, args.output_md)

    s = report["summary"]
    print(f"\n=== Pilot Report Summary ===")
    print(f"  Total: {s['n_total']}")
    print(f"  Exact match: {s['n_exact_match']} ({s['hit_rate']:.0%})")
    print(f"  Off-by-one: {s['n_off_by_one']}")
    print(f"  Off by more / errors: {s['n_off_more'] + s['n_failed']}")
    print(f"\n  Recommendations:")
    for r in s["recommendations"]:
        print(f"    - {r}")
    print(f"\n  Markdown report: {args.output_md}")
    print(f"  JSON report: {args.output_json}")


if __name__ == "__main__":
    main()
