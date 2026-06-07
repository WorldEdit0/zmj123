"""Deprecated SES shim.

The old SES used ArcFace ID drift and CLIP-T off-target deltas. It is no
longer a headline metric. Use ``mseditbench.metrics.usp.usp`` instead.
"""

from __future__ import annotations


def ses(*args, **kwargs):
    raise RuntimeError("SES has been removed. Use M.usp(...) instead.")


def off_target(*args, **kwargs):
    raise RuntimeError("CLIP-T off_target has been removed with SES.")
