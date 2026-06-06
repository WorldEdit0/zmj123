"""Per-shot entity tubes (Grounded-DINO + SAM-2-Video).

DEPRECATED (2026-05-24): superseded by SAM-3 in
`mseditbench.metrics.backends._make_sam3_mask`. The eval orchestrator
computes masks inline from the edit-frame anchor — see
`mseditbench.eval.run_eval.score_one`. Kept for historical reference.

Public API (still importable):
    from mseditbench.tracking import build_tubes_for_video
    from mseditbench.tracking.detector import get_detector
    from mseditbench.tracking.tracker import get_tracker
"""

from .run_video import build_tubes_for_video
from .detector import get_detector
from .tracker import get_tracker

__all__ = ["build_tubes_for_video", "get_detector", "get_tracker"]
