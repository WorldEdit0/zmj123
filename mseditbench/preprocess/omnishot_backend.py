"""OmniShotCut backend for shot boundary detection.

OmniShotCut is a transformer-based SBD model (UVA CV Lab, arXiv:2604.24762)
that handles transitions (dissolve / fade / wipe) in addition to hard cuts.

We use 'clean_shot' mode (filters out transitions, keeps only general-cut
boundaries) since our Seedance multi-shot videos are pure hard cuts.

The OmniShotCut repo lives outside our package; we add it to sys.path on
first use. Model + ckpt are loaded once and cached as module globals.

Layout assumptions (paths can be overridden via env vars):
    OMNISHOTCUT_REPO=OmniShotCut
    OMNISHOTCUT_CKPT=mseditbench/ckpt/omnishotcut/OmniShotCut_ckpt.pth
"""

from __future__ import annotations
import os
import sys
import warnings
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
OMNISHOT_REPO = os.environ.get("OMNISHOTCUT_REPO", str(_REPO_ROOT / "OmniShotCut"))
OMNISHOT_CKPT = os.environ.get(
    "OMNISHOTCUT_CKPT",
    str(_REPO_ROOT / "mseditbench" / "ckpt" / "omnishotcut" / "OmniShotCut_ckpt.pth"),
)

# Module-level cache
_MODEL = None
_MODEL_ARGS = None
_SINGLE_INFER = None
_INTRA_MAP = None


def _ensure_loaded():
    """Load OmniShotCut model + helpers exactly once."""
    global _MODEL, _MODEL_ARGS, _SINGLE_INFER, _INTRA_MAP
    if _MODEL is not None:
        return

    if OMNISHOT_REPO not in sys.path:
        sys.path.insert(0, OMNISHOT_REPO)

    import torch
    import torch.serialization
    import argparse as _argparse

    # OmniShotCut checkpoints stash an argparse.Namespace; allow it.
    torch.serialization.add_safe_globals([_argparse.Namespace])

    # Suppress harmless torchvision deprecation warnings on backbone build.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        from omnishotcut.engine import load_model, single_video_inference
        from omnishotcut.label_correspondence import unique_intra_label_mapping

        if not os.path.exists(OMNISHOT_CKPT):
            raise FileNotFoundError(f"OmniShotCut ckpt missing: {OMNISHOT_CKPT}")

        model, args = load_model(OMNISHOT_CKPT, device="auto")

    _MODEL = model
    _MODEL_ARGS = args
    _SINGLE_INFER = single_video_inference
    _INTRA_MAP = unique_intra_label_mapping


def predict_shots(video_path: str, clean_shot: bool = True,
                  num_context_frames: int = 20) -> list[dict]:
    """Run OmniShotCut on one video, return [{frame_start, frame_end}, ...].

    `num_context_frames=20` matches OmniShotCut's official inference default
    overlap window. `clean_shot=True` filters out predicted transitions
    (dissolve/fade/wipe), keeping only general (hard-cut) shot ranges. For
    Seedance multi-shot videos we only have hard cuts, so default True is
    correct.
    """
    _ensure_loaded()

    pred_ranges, intra_labels, inter_labels, _video_np, _fps = _SINGLE_INFER(
        video_path, _MODEL, _MODEL_ARGS, num_context_frames,
    )

    if clean_shot:
        general_idx = _INTRA_MAP["general"]
        keep = [i for i, lab in enumerate(intra_labels) if lab == general_idx]
        pred_ranges = [pred_ranges[i] for i in keep]

    # OmniShotCut returns half-open ranges: shot k ends at pred_ranges[k][1] (exclusive),
    # next shot starts there. Convert to our inclusive-end schema.
    shots = []
    for start, end in pred_ranges:
        s, e = int(start), int(end)
        if e <= s:
            continue
        shots.append({"frame_start": s, "frame_end": e - 1})
    return shots
