"""Synthetic-data tests for the metrics layer.

These tests use mock backends — they verify the math (aggregation, edge
cases, formula structure) rather than model semantics. Run with:

    python -m mseditbench.tests.test_metrics

Each test prints a single PASS/FAIL line; non-zero exit on any failure.
"""

from __future__ import annotations
import numpy as np
import sys
import traceback

from mseditbench import metrics as M
from mseditbench.metrics import backends as B


# -- helpers -----------------------------------------------------------------

def _make_frames(seed: int, T: int = 4, H: int = 32, W: int = 32) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(T, H, W, 3), dtype=np.uint8)


class FailingClip(B.ClipBackend):
    """CLIP that gives a fixed delta on (source, edit) pairs we control."""
    def __init__(self, delta: float = 0.20):
        self.delta = delta
    def score_video_text(self, frames, text):
        if frames.shape[0] == 0: return 0.0
        return 0.5 + (self.delta if frames.mean() > 100 else 0.0)
    def score_image_text(self, frame, text):
        return self.score_video_text(frame[None], text)


class AlwaysYesVlm(B.VlmBackend):
    def yes_no(self, frames, q): return True


class AlwaysNoVlm(B.VlmBackend):
    def yes_no(self, frames, q): return False


# -- tests -------------------------------------------------------------------

def test_csep_perfect():
    """Identical strong signal in all applicable shots → coverage=1, consistency=1, csep=1."""
    src = {1: _make_frames(0, T=2) // 4, 2: _make_frames(1, T=2) // 4, 3: _make_frames(2, T=2) // 4}
    edit = {1: _make_frames(3, T=2) * 0 + 200, 2: _make_frames(4, T=2) * 0 + 200, 3: _make_frames(5, T=2) * 0 + 200}
    r = M.csep(src, edit, [1, 2, 3], "anything", clip_backend=FailingClip(0.2), tau_csep=0.05)
    assert r["csep"] is not None and r["csep"] > 0.99, f"csep={r['csep']}"
    assert abs(r["coverage"] - 1.0) < 1e-3, f"coverage={r['coverage']}"


def test_csep_partial_coverage():
    """Signal in 1 of 3 shots → coverage≈0.33, consistency low → csep < 0.5."""
    src = {1: _make_frames(0) // 4, 2: _make_frames(1) // 4, 3: _make_frames(2) // 4}
    edit = {1: _make_frames(3) * 0 + 200, 2: _make_frames(4) // 4, 3: _make_frames(5) // 4}
    r = M.csep(src, edit, [1, 2, 3], "T", clip_backend=FailingClip(0.2), tau_csep=0.05)
    assert r["coverage"] < 0.5, f"coverage={r['coverage']}"
    assert r["csep"] < 0.6, f"csep={r['csep']}"


def test_csep_skipped_when_one_shot():
    """|S_app|=1 → consistency undefined → csep is None."""
    r = M.csep({1: _make_frames(0)}, {1: _make_frames(1) + 100}, [1], "T",
               clip_backend=FailingClip(0.2), tau_csep=0.05)
    assert r["csep"] is None, f"csep should be None, got {r['csep']}"


def test_ee_unanimous_required():
    """Even with strong CLIP-Δ, EE=0 if any of 3 VLMs says no."""
    src = {1: _make_frames(0) // 4, 2: _make_frames(1) // 4}
    edit = {1: _make_frames(3) * 0 + 200, 2: _make_frames(4) * 0 + 200}
    r = M.ee(src, edit, [1, 2],
             "target", "edit it", clip_backend=FailingClip(0.2),
             vlm_backends=[AlwaysYesVlm(), AlwaysYesVlm(), AlwaysNoVlm()])
    assert r["ee"] == 0.0, f"ee={r['ee']}"


def test_ee_full_pass():
    src = {1: _make_frames(0) // 4, 2: _make_frames(1) // 4}
    edit = {1: _make_frames(3) * 0 + 200, 2: _make_frames(4) * 0 + 200}
    r = M.ee(src, edit, [1, 2],
             "target", "edit it", clip_backend=FailingClip(0.2),
             vlm_backends=[AlwaysYesVlm(), AlwaysYesVlm(), AlwaysYesVlm()])
    assert r["ee"] == 1.0, f"ee={r['ee']}"


def test_nep_identity_is_one():
    """If edit == source, DINO sim → 1, NEP → 1."""
    src = {1: _make_frames(0), 2: _make_frames(1)}
    r = M.nep(src, src)  # edit = source
    assert r["nep"] is not None and r["nep"] > 0.999, f"nep={r['nep']}"


def test_nep_skips_inserted_shots():
    src = {1: _make_frames(0), 2: _make_frames(1)}
    edit = {1: _make_frames(0), 2: _make_frames(1), 3: _make_frames(2)}
    r = M.nep(src, edit, skip_shots=[3])
    assert r["nep"] is not None and r["n_scored"] == 2, f"n_scored={r['n_scored']}"


def test_nep_requires_masks_when_requested():
    src = {1: _make_frames(0), 2: _make_frames(1)}
    r = M.nep(src, src, require_masks=True)
    assert r["nep"] is None, f"nep should be None without required masks, got {r['nep']}"
    assert r["n_mask_missing"] == 2, f"n_mask_missing={r['n_mask_missing']}"

    masks = {1: np.zeros((32, 32), dtype=np.uint8), 2: np.zeros((32, 32), dtype=np.uint8)}
    r = M.nep(src, src, per_shot_edit_masks=masks, require_masks=True)
    assert r["nep"] is not None and r["n_scored"] == 2, f"n_scored={r['n_scored']}"


def test_usp_identity_is_one():
    """If an unedited shot is unchanged, USP DINO similarity is 1."""
    src = {1: _make_frames(0), 2: _make_frames(1)}
    r = M.usp(src, src, [2])
    assert r["usp"] is not None and r["usp"] > 0.999, f"usp={r['usp']}"
    assert r["n_scored"] == 1, f"n_scored={r['n_scored']}"


def test_usp_none_when_no_unedited_shots():
    r = M.usp({1: _make_frames(0)}, {1: _make_frames(0)}, [])
    assert r["usp"] is None, f"usp should be None, got {r['usp']}"
    assert r["reason"] == "no unedited shots for this prompt"


def test_tac_perfect_when_boundaries_match():
    src_shots = [
        {"shot_id": 1, "t_start": 0.0, "t_end": 2.0, "duration_sec": 2.0},
        {"shot_id": 2, "t_start": 2.0, "t_end": 5.0, "duration_sec": 3.0},
    ]
    edited_shots = [
        {"frame_start": 0, "frame_end": 47},
        {"frame_start": 48, "frame_end": 119},
    ]
    r = M.temporal_anchor_consistency(
        src_shots, edited_shots=edited_shots, source_fps=24.0, edited_fps=24.0
    )
    assert r["tac"] is not None and r["tac"] > 0.999, f"tac={r['tac']}"


def test_tac_zero_when_count_mismatch():
    src_shots = [
        {"shot_id": 1, "t_start": 0.0, "t_end": 2.0, "duration_sec": 2.0},
        {"shot_id": 2, "t_start": 2.0, "t_end": 4.0, "duration_sec": 2.0},
    ]
    r = M.temporal_anchor_consistency(
        src_shots,
        edited_shots=[{"frame_start": 0, "frame_end": 95}],
        source_fps=24.0,
        edited_fps=24.0,
    )
    assert r["tac"] == 0.0, f"tac={r['tac']}"
    assert r["shot_count_match"] is False


def test_tac_penalizes_anchor_drift():
    src_shots = [{"shot_id": 1, "t_start": 0.0, "t_end": 2.0, "duration_sec": 2.0}]
    edited_shots = [{"frame_start": 0, "frame_end": 71}]  # 0-3s at 24 fps
    r = M.temporal_anchor_consistency(
        src_shots, edited_shots=edited_shots, source_fps=24.0, edited_fps=24.0
    )
    assert r["tac"] is not None and 0.0 < r["tac"] < 1.0, f"tac={r['tac']}"
    assert r["mean_anchor_error_sec"] > 0.0


def test_cxs_id_acp_floor_kicks_in():
    """When intra-shot embeddings are identical (static copy), ACP factor is small."""
    same = np.tile(np.eye(384)[0], (4, 1))  # 4 identical frame embeds
    e = {1: same, 2: same}
    r = M.cxs_id_one_entity(e, tau_acp=0.05)
    assert r["acp_factor"] == 0.0, f"acp={r['acp_factor']}"
    assert r["cxs_id"] == 0.0, f"cxs_id={r['cxs_id']}"


def test_cxs_id_normal_case():
    rng = np.random.default_rng(42)
    s1 = rng.standard_normal((4, 384)).astype(np.float32)
    s1 /= np.linalg.norm(s1, axis=1, keepdims=True)
    s2 = s1 + 0.01 * rng.standard_normal(s1.shape).astype(np.float32)
    s2 /= np.linalg.norm(s2, axis=1, keepdims=True)
    r = M.cxs_id_one_entity({1: s1, 2: s2}, tau_acp=0.001)
    assert r["cxs_id"] is not None and r["cxs_id"] > 0.5, f"cxs_id={r['cxs_id']}"
    assert r["acp_factor"] > 0, f"acp={r['acp_factor']}"


def test_psq_aggregation():
    src = {1: _make_frames(0), 2: _make_frames(1)}
    r = M.psq(src)
    assert r["psq"] is not None and 0.0 <= r["psq"] <= 1.0


# -- runner ------------------------------------------------------------------

def main():
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    fail = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            fail += 1
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - fail}/{len(tests)} passed")
    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
