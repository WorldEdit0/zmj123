"""
Shot boundary detection.

Backends in priority order (consensus = first available):
    1. OmniShotCut  (UVA CV Lab, arXiv:2604.24762; transformer SBD model)
    2. TransNetV2   (legacy primary)
    3. PySceneDetect (cross-check)

Agreement check uses TransNetV2 vs PySceneDetect (when OmniShotCut not used,
or as a diagnostic when it is). All three results are recorded in the JSON
so the user can compare per-video.

Output JSON schema (canonical = frame index; time is derived for human reading):

{
  "video_id": "00000",
  "video_path": "...",
  "fps": 24.0,
  "total_frames": 360,
  "duration_sec": 15.0,
  "width": 1920,
  "height": 1080,
  "expected_shots": 4,                       // from source JSON (optional)
  "omnishotcut": {                           // new primary
      "n_shots": 3, "backend": "omnishotcut",
      "shots": [{"shot_id": 1, "frame_start": 0, "frame_end": 188, ...}, ...]
  },
  "transnetv2": { "n_shots": 4, "shots": [...] },
  "pyscenedetect": { "n_shots": 4, "shots": [...] },
  "agreement": { "shot_count_match": ..., "boundaries_within_tolerance": ... },
  "consensus_shots": [...]  // = omnishotcut.shots (preferred), else TN, else PS
}
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

import cv2
import numpy as np
from tqdm import tqdm


# ----------------------------------------------------------------------------
# OmniShotCut wrapper (preferred backend; arXiv:2604.24762)
# ----------------------------------------------------------------------------
def _try_import_omnishotcut():
    """Returns (predict_fn, "omnishotcut") or (None, None) if not loadable."""
    try:
        try:
            from .omnishot_backend import predict_shots as _ps  # package-relative
        except (ImportError, ValueError):
            # Direct script run (`python shot_detect.py`); use absolute import
            import os, sys
            here = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(os.path.dirname(here))
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
            from mseditbench.preprocess.omnishot_backend import predict_shots as _ps
        return (lambda video_path: _ps(video_path)), "omnishotcut"
    except Exception as e:
        print(f"[omnishotcut] import failed: {e}")
        return None, None


# ----------------------------------------------------------------------------
# TransNetV2 wrapper (graceful fallback if not installed)
# ----------------------------------------------------------------------------
def _try_import_transnetv2():
    """Try several common pip distributions of TransNetV2; return a callable
    `predict_video(path) -> np.ndarray of per-frame transition probabilities`
    or None if no package is installed.
    """
    # Option A: transnetv2-pytorch by jramapuram (pip install transnetv2-pytorch)
    try:
        from transnetv2_pytorch import TransNetV2 as _TN  # type: ignore
        import torch

        _model = _TN()
        _model.eval()
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        _model.to(_device)

        def _predict(video_path: str) -> np.ndarray:
            # transnetv2_pytorch provides .predict_video which returns
            # single_frame_predictions
            with torch.no_grad():
                _, single_frame_preds, _ = _model.predict_video(video_path)
            return np.asarray(single_frame_preds).flatten()

        return _predict, "transnetv2_pytorch"
    except ImportError:
        pass

    # Option B: official tensorflow port (pip install transnetv2)
    try:
        from transnetv2 import TransNetV2 as _TN  # type: ignore
        _model = _TN()

        def _predict(video_path: str) -> np.ndarray:
            _, single_frame_preds, _ = _model.predict_video(video_path)
            return np.asarray(single_frame_preds).flatten()

        return _predict, "transnetv2(tf)"
    except ImportError:
        pass

    return None, None


# ----------------------------------------------------------------------------
# PySceneDetect wrapper
# ----------------------------------------------------------------------------
def _detect_pyscenedetect(video_path: str, threshold: float = 27.0) -> List[Dict]:
    """Returns list of {frame_start, frame_end} dicts."""
    from scenedetect import detect, ContentDetector

    scenes = detect(video_path, ContentDetector(threshold=threshold))
    if not scenes:
        # No cut detected -> single shot covering whole video
        cap = cv2.VideoCapture(video_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return [{"frame_start": 0, "frame_end": total - 1}]

    shots = []
    for s, e in scenes:
        shots.append(
            {
                "frame_start": int(s.get_frames()),
                "frame_end": int(e.get_frames()) - 1,
            }
        )
    return shots


# ----------------------------------------------------------------------------
# TransNetV2 → shots conversion
# ----------------------------------------------------------------------------
def _probs_to_shots(probs: np.ndarray, threshold: float = 0.5) -> List[Dict]:
    """Convert per-frame transition probabilities to shot boundary list."""
    cuts = np.where(probs > threshold)[0]
    # Merge adjacent cut frames (TransNetV2 sometimes fires on 2-3 consecutive frames)
    if len(cuts) > 0:
        merged = [int(cuts[0])]
        for c in cuts[1:]:
            if c - merged[-1] > 3:
                merged.append(int(c))
        cuts = merged
    else:
        cuts = []

    n_frames = len(probs)
    if len(cuts) == 0:
        return [{"frame_start": 0, "frame_end": n_frames - 1}]

    shots = []
    prev = 0
    for c in cuts:
        shots.append({"frame_start": prev, "frame_end": int(c) - 1})
        prev = int(c)
    shots.append({"frame_start": prev, "frame_end": n_frames - 1})
    return shots


# ----------------------------------------------------------------------------
# Common helpers
# ----------------------------------------------------------------------------
def _enrich_shots(shots: List[Dict], fps: float) -> List[Dict]:
    out = []
    for i, s in enumerate(shots, start=1):
        f0, f1 = s["frame_start"], s["frame_end"]
        out.append(
            {
                "shot_id": i,
                "frame_start": f0,
                "frame_end": f1,
                "duration_frames": f1 - f0 + 1,
                "t_start": round(f0 / fps, 3),
                "t_end": round((f1 + 1) / fps, 3),
                "duration_sec": round((f1 - f0 + 1) / fps, 3),
            }
        )
    return out


def _video_metadata(video_path: str) -> Dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Cannot open video: {video_path}")
    meta = {
        "fps": float(cap.get(cv2.CAP_PROP_FPS)),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    meta["duration_sec"] = round(meta["total_frames"] / max(meta["fps"], 1e-6), 3)
    cap.release()
    return meta


def _compare_agreement(
    tn_shots: Optional[List[Dict]],
    ps_shots: Optional[List[Dict]],
    fps: float,
    tol_sec: float = 0.25,
) -> Dict:
    if tn_shots is None or ps_shots is None:
        return {
            "shot_count_match": False,
            "boundaries_within_tolerance": False,
            "tolerance_sec": tol_sec,
            "note": "one detector unavailable",
        }
    if len(tn_shots) != len(ps_shots):
        return {
            "shot_count_match": False,
            "boundaries_within_tolerance": False,
            "tolerance_sec": tol_sec,
        }
    tol_frames = tol_sec * fps
    ok = True
    for a, b in zip(tn_shots, ps_shots):
        if abs(a["frame_start"] - b["frame_start"]) > tol_frames:
            ok = False
            break
    return {
        "shot_count_match": True,
        "boundaries_within_tolerance": ok,
        "tolerance_sec": tol_sec,
    }


# ----------------------------------------------------------------------------
# Main API
# ----------------------------------------------------------------------------
def detect_shots(
    video_path: str,
    expected_shots: Optional[int] = None,
    pyscenedetect_threshold: float = 27.0,
    transnet_threshold: float = 0.5,
    skip_transnetv2: bool = False,
    skip_omnishotcut: bool = False,
) -> Dict:
    """Detect shots in a single video. Returns the full result dict (see module docstring)."""
    meta = _video_metadata(video_path)
    video_id = Path(video_path).stem

    # OmniShotCut (preferred)
    os_block, os_shots = None, None
    if not skip_omnishotcut:
        os_predict, os_backend = _try_import_omnishotcut()
        if os_predict is not None:
            try:
                os_shots = os_predict(video_path)  # already [{frame_start, frame_end}, ...]
                os_block = {
                    "n_shots": len(os_shots),
                    "backend": os_backend,
                    "shots": _enrich_shots(os_shots, meta["fps"]),
                }
            except Exception as e:
                os_block = {"n_shots": None, "error": str(e), "backend": "omnishotcut"}

    # TransNetV2
    tn_shots, tn_block = None, None
    if not skip_transnetv2:
        tn_predict, tn_backend = _try_import_transnetv2()
        if tn_predict is not None:
            try:
                probs = tn_predict(video_path)
                tn_shots = _probs_to_shots(probs, threshold=transnet_threshold)
                tn_block = {
                    "n_shots": len(tn_shots),
                    "backend": tn_backend,
                    "threshold": transnet_threshold,
                    "shots": _enrich_shots(tn_shots, meta["fps"]),
                }
            except Exception as e:
                tn_block = {"n_shots": None, "error": str(e), "backend": tn_backend}

    # PySceneDetect
    try:
        ps_shots = _detect_pyscenedetect(video_path, threshold=pyscenedetect_threshold)
        ps_block = {
            "n_shots": len(ps_shots),
            "threshold": pyscenedetect_threshold,
            "shots": _enrich_shots(ps_shots, meta["fps"]),
        }
    except Exception as e:
        ps_shots, ps_block = None, {"n_shots": None, "error": str(e)}

    # Agreement: TN vs PS as a diagnostic of borderline cases.
    agreement = _compare_agreement(tn_shots, ps_shots, meta["fps"])

    # Consensus = OmniShotCut > TransNetV2 > PySceneDetect.
    consensus = None
    consensus_backend = None
    if os_block and os_block.get("shots"):
        consensus = os_block["shots"]
        consensus_backend = "omnishotcut"
    elif tn_block and tn_block.get("shots"):
        consensus = tn_block["shots"]
        consensus_backend = tn_block.get("backend", "transnetv2")
    elif ps_block and ps_block.get("shots"):
        consensus = ps_block["shots"]
        consensus_backend = "pyscenedetect"

    return {
        "video_id": video_id,
        "video_path": video_path,
        **meta,
        "expected_shots": expected_shots,
        "omnishotcut": os_block,
        "transnetv2": tn_block,
        "pyscenedetect": ps_block,
        "agreement": agreement,
        "consensus_shots": consensus,
        "consensus_n_shots": len(consensus) if consensus else None,
        "consensus_backend": consensus_backend,
        "matches_expected": (
            consensus is not None and expected_shots is not None
            and len(consensus) == expected_shots
        ),
    }


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def _load_expected_shots(source_json_path: str) -> Dict[str, int]:
    """Build {video_name (without ext): expected_shots} from source_prompts JSON."""
    if not source_json_path or not os.path.exists(source_json_path):
        return {}
    with open(source_json_path, "r") as f:
        items = json.load(f)
    mapping = {}
    for it in items:
        gi = int(it["global_index"])
        name = f"{gi:05d}"
        mapping[name] = it.get("expected_shots", None)
    return mapping


def main():
    ap = argparse.ArgumentParser(description="Detect shot boundaries (OmniShotCut primary + TransNetV2 + PySceneDetect)")
    ap.add_argument("--video", type=str, help="Single video path")
    ap.add_argument("--videos_dir", type=str, help="Directory of mp4 videos")
    ap.add_argument("--output_dir", type=str, required=True,
                    help="Where to write {video_id}.shots.json (one per video)")
    ap.add_argument("--source_json", type=str, default="",
                    help="Path to source_prompts_multishot_v1.json (to look up expected_shots)")
    ap.add_argument("--pyscenedetect_threshold", type=float, default=27.0)
    ap.add_argument("--transnet_threshold", type=float, default=0.5)
    ap.add_argument("--skip_omnishotcut", action="store_true",
                    help="Disable OmniShotCut, fall back to TN/PS only")
    ap.add_argument("--skip_transnetv2", action="store_true",
                    help="Disable TransNetV2 (saves a few seconds when OmniShot is enough)")
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Collect videos
    if args.video:
        videos = [args.video]
    elif args.videos_dir:
        videos = sorted(
            str(p) for p in Path(args.videos_dir).glob("*.mp4")
        )
    else:
        sys.exit("Must provide either --video or --videos_dir")

    if not videos:
        sys.exit(f"No videos found.")

    expected = _load_expected_shots(args.source_json)
    if expected:
        print(f"Loaded {len(expected)} expected_shots entries from {args.source_json}")

    print(f"Processing {len(videos)} videos -> {args.output_dir}")

    for video_path in tqdm(videos, desc="Detecting shots"):
        video_id = Path(video_path).stem
        exp = expected.get(video_id, None)
        try:
            result = detect_shots(
                video_path,
                expected_shots=exp,
                pyscenedetect_threshold=args.pyscenedetect_threshold,
                transnet_threshold=args.transnet_threshold,
                skip_omnishotcut=args.skip_omnishotcut,
                skip_transnetv2=args.skip_transnetv2,
            )
        except Exception as e:
            print(f"\n[ERROR] {video_id}: {e}")
            result = {"video_id": video_id, "video_path": video_path, "error": str(e)}

        out_path = os.path.join(args.output_dir, f"{video_id}.shots.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

    print(f"\nDone. Outputs in {args.output_dir}")
    print(f"Next: python contact_sheet.py --shots_dir {args.output_dir} --videos_dir <videos>")
    print(f"      python pilot_report.py --shots_dir {args.output_dir} --source_json <source.json>")


if __name__ == "__main__":
    main()
