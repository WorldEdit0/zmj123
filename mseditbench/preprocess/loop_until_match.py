"""Loop-retry Seedance source generation until shot count matches expected.

For each video_id in --mismatch_ids:
    while attempt < max_retries:
        - call Seedance API (text-only multi-shot)
        - download (delete stale local file first)
        - run TransNetV2 + PySceneDetect shot detection
        - if actual == expected: write success CSV, break
        - else: continue

When successful, writes a single-row CSV named `zz_loopmatch_<vid>.csv` to
`--success_csv_dir`. The `zz_` prefix sorts after `all_seedance_*` and
`retry_seedance_*` so it overrides earlier URLs in the edit pipeline.

Usage:
    python -m mseditbench.preprocess.loop_until_match \\
        --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \\
        --mismatch_ids 00000 \\
        --videos_dir data/source_videos_10s/videos \\
        --success_csv_dir data/source_videos_10s/success_csv \\
        --max_retries 15

Note: Seedance has no seed parameter — outputs vary across calls. For a
caption that biases strongly toward the wrong shot count (e.g. 00000 has
been over-cutting to 4 instead of 3), even 15 retries may not converge.
If a video fails all retries, consider modifying its caption (merge
adjacent shots) or accepting `expected_shots = actual` in the source JSON.
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from volcenginesdkarkruntime import Ark

from .shot_detect import detect_shots


def build_multishot_prompt(caption: str) -> tuple[str, int]:
    """Same logic as infer_v2_mutilshot_source.py: '[wide] action.' →
    'Shot 1: [wide] action.' concatenated."""
    pattern = r"\[(.*?)\]\s*([^\[]*)"
    matches = re.findall(pattern, caption, flags=re.DOTALL)
    lines = []
    for i, (tag, action) in enumerate(matches, 1):
        action = " ".join(action.split())
        lines.append(f"Shot {i}: [{tag}] {action}")
    return "".join(lines), len(lines)


def call_seedance(client: Ark, item: dict, model: str) -> tuple[str, str]:
    """Returns (task_id, video_url) on success; raises on failure."""
    prompt, _ = build_multishot_prompt(item["caption"])
    create = client.content_generation.tasks.create(
        model=model,
        content=[{"type": "text", "text": prompt}],
        ratio=item.get("ratio", "16:9"),
        duration=int(item.get("duration_sec", 15)),
        watermark=False,
        resolution=item.get("resolution", "720p"),
        generate_audio=False,
    )
    task_id = create.id
    while True:
        r = client.content_generation.tasks.get(task_id=task_id)
        if r.status == "succeeded":
            return task_id, r.content.video_url
        if r.status == "failed":
            raise RuntimeError(f"task failed: {getattr(r, 'error', '?')}")
        time.sleep(3)


def download(url: str, save_path: str) -> None:
    """Delete any pre-existing file (avoid the download_videos.py:32-34 footgun),
    then stream-download the URL to save_path."""
    if os.path.exists(save_path):
        os.remove(save_path)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def write_success_csv(csv_path: str, video_name: str, video_url: str) -> None:
    """One-row CSV in the same schema as download_videos success records,
    so the edit pipeline can read it without code changes."""
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["video_name", "video_url"])
        w.writeheader()
        w.writerow({"video_name": video_name, "video_url": video_url})


def loop_one_video(
    item: dict,
    vid: str,
    videos_dir: str,
    success_csv_dir: str,
    client: Ark,
    model: str,
    max_retries: int,
) -> tuple[bool, int, int]:
    """Returns (success, attempts_used, last_actual_shots)."""
    expected = int(item["expected_shots"])
    video_name = f"{vid}.mp4"
    save_path = os.path.join(videos_dir, video_name)
    last_actual = -1

    for attempt in range(1, max_retries + 1):
        print(f"  [{vid}] attempt {attempt}/{max_retries}: calling Seedance...", flush=True)
        try:
            task_id, url = call_seedance(client, item, model)
        except Exception as e:
            print(f"    API failed: {e}", flush=True)
            continue

        try:
            download(url, save_path)
        except Exception as e:
            print(f"    download failed: {e}", flush=True)
            continue

        try:
            r = detect_shots(save_path, expected_shots=expected)
        except Exception as e:
            print(f"    shot detect failed: {e}", flush=True)
            continue

        actual = r.get("consensus_n_shots")
        tn = (r.get("transnetv2") or {}).get("n_shots")
        ps = (r.get("pyscenedetect") or {}).get("n_shots")
        last_actual = actual or -1
        match = (actual == expected)
        flag = "✓ MATCH" if match else f"✗ off-by-{actual - expected:+d}"
        print(f"    expected={expected}  actual={actual}  TN={tn}  PS={ps}  {flag}", flush=True)

        if match:
            csv_path = os.path.join(success_csv_dir, f"zz_loopmatch_{vid}.csv")
            write_success_csv(csv_path, video_name, url)
            print(f"    wrote {csv_path}", flush=True)
            return True, attempt, actual

    return False, max_retries, last_actual


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source_json", required=True,
                    help="Path to source_prompts_multishot_v1.json")
    ap.add_argument("--mismatch_ids", nargs="+", required=True,
                    help="Video IDs to retry, e.g. 00000 00008")
    ap.add_argument("--videos_dir", required=True,
                    help="Where to save the regenerated mp4 files")
    ap.add_argument("--success_csv_dir", required=True,
                    help="Where to write zz_loopmatch_<vid>.csv "
                         "(edit pipeline reads this dir)")
    ap.add_argument("--max_retries", type=int, default=15)
    ap.add_argument("--model", default="doubao-seedance-2-0-260128")
    ap.add_argument("--api_key",
                    default=os.environ.get("ARK_API_KEY",
                                           "2fc23b6f-d9c0-4c30-901f-7f5cd60a3500"))
    ap.add_argument("--base_url", default="https://ark.cn-beijing.volces.com/api/v3")
    args = ap.parse_args()

    src = json.load(open(args.source_json))
    src_lookup = {f"{int(it['global_index']):05d}": it for it in src}

    os.makedirs(args.videos_dir, exist_ok=True)
    os.makedirs(args.success_csv_dir, exist_ok=True)

    client = Ark(base_url=args.base_url, api_key=args.api_key)

    print(f"Looping {len(args.mismatch_ids)} video(s) up to {args.max_retries} retries each.")
    print(f"  videos_dir:      {args.videos_dir}")
    print(f"  success_csv_dir: {args.success_csv_dir}")
    print(f"  model:           {args.model}")
    print()

    summary = []
    for vid in args.mismatch_ids:
        item = src_lookup.get(vid)
        if not item:
            print(f"[skip] no source item for {vid!r}")
            summary.append((vid, False, 0, "no source"))
            continue
        print(f"=== {vid}  scene={item.get('scene_id')}  expected_shots={item['expected_shots']} ===", flush=True)
        ok, attempts, last_actual = loop_one_video(
            item, vid, args.videos_dir, args.success_csv_dir,
            client, args.model, args.max_retries,
        )
        summary.append((vid, ok, attempts, last_actual))
        print()

    print("=== Summary ===")
    n_ok = 0
    for vid, ok, attempts, last_actual in summary:
        if ok:
            print(f"  ✓ {vid}  matched on attempt {attempts}")
            n_ok += 1
        else:
            print(f"  ✗ {vid}  gave up after {attempts} attempts (last actual={last_actual})")
    print(f"\n{n_ok}/{len(summary)} reached 100%-match.")
    if n_ok < len(summary):
        print("\nNext steps for unmatched IDs:")
        print("  - increase --max_retries")
        print("  - OR modify the caption in source_prompts_multishot_v1.json")
        print("    (most common fix: merge adjacent shots when over-cutting,"
              " add stronger contrast when under-cutting)")
        print("  - OR update the JSON's expected_shots to match what Seedance reliably produces")


if __name__ == "__main__":
    main()
