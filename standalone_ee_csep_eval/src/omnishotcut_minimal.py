from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import warnings


RUN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = RUN_ROOT / "third_party" / "OmniShotCut"
DEFAULT_CKPT = RUN_ROOT / "checkpoints" / "OmniShotCut_ckpt.pth"

_MODEL = None
_MODEL_ARGS = None
_SINGLE_INFER = None
_INTRA_MAP = None


def _ensure_loaded(repo: Path, ckpt: Path) -> None:
    global _MODEL, _MODEL_ARGS, _SINGLE_INFER, _INTRA_MAP
    if _MODEL is not None:
        return
    if not repo.exists():
        raise FileNotFoundError(f"OmniShotCut repo missing: {repo}")
    if not ckpt.exists():
        raise FileNotFoundError(f"OmniShotCut checkpoint missing: {ckpt}")
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    import argparse as _argparse
    import torch

    torch.serialization.add_safe_globals([_argparse.Namespace])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        from omnishotcut.engine import load_model, single_video_inference
        from omnishotcut.label_correspondence import unique_intra_label_mapping

        model, model_args = load_model(str(ckpt), device="auto")

    _MODEL = model
    _MODEL_ARGS = model_args
    _SINGLE_INFER = single_video_inference
    _INTRA_MAP = unique_intra_label_mapping


def predict_shots(
    video_path: str | Path,
    *,
    repo: str | Path = DEFAULT_REPO,
    ckpt: str | Path = DEFAULT_CKPT,
    clean_shot: bool = True,
    num_context_frames: int = 20,
) -> list[dict]:
    """Return [{frame_start, frame_end}, ...] using OmniShotCut.

    num_context_frames=20 and clean_shot=True match the parameters used by the
    main benchmark pipeline.
    """
    _ensure_loaded(Path(repo), Path(ckpt))
    pred_ranges, intra_labels, _inter_labels, _video_np, _fps = _SINGLE_INFER(
        str(video_path),
        _MODEL,
        _MODEL_ARGS,
        int(num_context_frames),
    )
    if clean_shot:
        general_idx = _INTRA_MAP["general"]
        keep = [i for i, lab in enumerate(intra_labels) if lab == general_idx]
        pred_ranges = [pred_ranges[i] for i in keep]

    shots = []
    for start, end in pred_ranges:
        start_i, end_i = int(start), int(end)
        if end_i <= start_i:
            continue
        shots.append({"frame_start": start_i, "frame_end": end_i - 1})
    return shots


def main() -> None:
    ap = argparse.ArgumentParser(description="Minimal standalone OmniShotCut wrapper.")
    ap.add_argument("--video", required=True)
    ap.add_argument("--output_json", required=True)
    ap.add_argument("--repo", default=os.environ.get("OMNISHOTCUT_REPO", str(DEFAULT_REPO)))
    ap.add_argument("--ckpt", default=os.environ.get("OMNISHOTCUT_CKPT", str(DEFAULT_CKPT)))
    ap.add_argument("--num_context_frames", type=int, default=20)
    ap.add_argument("--include_transitions", action="store_true")
    args = ap.parse_args()

    shots = predict_shots(
        args.video,
        repo=args.repo,
        ckpt=args.ckpt,
        clean_shot=not args.include_transitions,
        num_context_frames=args.num_context_frames,
    )
    out = {"video": args.video, "shots": shots}
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {len(shots)} shots: {output}")


if __name__ == "__main__":
    main()
