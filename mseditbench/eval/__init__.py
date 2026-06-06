"""End-to-end eval orchestrator.

    from mseditbench.eval.run_eval import score_one

CLI:
    python -m mseditbench.eval.run_eval --help
    python -m mseditbench.eval.leaderboard --help
"""

from .run_eval import score_one

__all__ = ["score_one"]
