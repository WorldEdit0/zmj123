"""MSEdit-Bench: multi-shot video editing benchmark for AAAI 2027.

Subpackages:
    preprocess     shot detection (TransNetV2 + PySceneDetect)
    tracking       per-shot entity tubes (Grounded-SAM2 + DEVA)
    identity       cross-shot character DB (InsightFace + cluster)
    metrics        PSQ / EE / NEP / CSEP / USP / TAC / CXS-ID
    edit_prompts   T1-T8 task templates + per-video instantiation
    baselines      editor API clients (Aleph, ...)
    eval           orchestrator: score one (video, edit, baseline) tuple

See HOWTO.md at the repo root for the end-to-end walkthrough.
"""

__version__ = "0.1.0"
