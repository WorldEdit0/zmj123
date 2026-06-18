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
from mseditbench.eval.run_eval import (
    _build_t9_metric_plan,
    _build_t9_nep_masks,
    _score_t9_vlm_metrics,
)


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


class PromptScoredVlm(B.VlmBackend):
    """Return configured scores when a substring appears in the judge prompt."""
    def __init__(self, image_scores=None, pair_scores=None):
        self.image_scores = image_scores or {}
        self.pair_scores = pair_scores or {}

    def yes_no(self, frames, q): return False

    def _score(self, table, prompt):
        for key, value in table.items():
            if key in prompt:
                return float(value)
        return 0.0

    def rate_image_pair(self, frame_a, frame_b, prompt, max_score=5):
        return self._score(self.image_scores, prompt)

    def rate_pair(self, frames_a, frames_b, prompt, max_score=5):
        return self._score(self.pair_scores, prompt)


def _t9_seq_sample():
    return {
        "sample_id": "toy_T9_seq",
        "video_id": "toy",
        "source_video": "toy.mp4",
        "shots": [{"shot_id": i, "frame_start": (i - 1) * 10, "frame_end": i * 10 - 1} for i in range(1, 5)],
        "edit": {
            "task_id": "T9",
            "instruction": "Change source A to target A; change source B to target B.",
            "target_phrase": "persistent two-object edits",
            "applicable_shots": [1, 2, 3, 4],
            "extra": {
                "mode": "sequential_two_edit_prompt",
                "prompt_components": [
                    {
                        "edit_id": "A",
                        "source_task": "T2",
                        "edit_type": "attribute_edit",
                        "instruction_fragment": "edit A",
                        "target_phrase": "target A",
                        "applicable_shots": [1, 2],
                    },
                    {
                        "edit_id": "B",
                        "source_task": "T2",
                        "edit_type": "attribute_edit",
                        "instruction_fragment": "edit B",
                        "target_phrase": "target B",
                        "applicable_shots": [2, 3, 4],
                    },
                ],
                "object_edits": [
                    {"edit_id": "A", "source_task": "T2", "target_phrase": "target A", "applicable_shots": [1, 2]},
                    {"edit_id": "B", "source_task": "T2", "target_phrase": "target B", "applicable_shots": [2, 3, 4]},
                ],
                "metric_shot_impacts": [
                    {
                        "shot_id": 1,
                        "evaluation_targets": [
                            {
                                "edit_id": "A",
                                "source_task": "T2",
                                "edit_type": "attribute_edit",
                                "metric_source_query": "source A",
                                "metric_target_query": "target A",
                                "target_phrase": "target A",
                            }
                        ],
                    },
                    {
                        "shot_id": 2,
                        "evaluation_targets": [
                            {
                                "edit_id": "A",
                                "source_task": "T2",
                                "edit_type": "attribute_edit",
                                "metric_source_query": "source A",
                                "metric_target_query": "target A",
                                "target_phrase": "target A",
                            },
                            {
                                "edit_id": "B",
                                "source_task": "T2",
                                "edit_type": "attribute_edit",
                                "metric_source_query": "source B",
                                "metric_target_query": "target B",
                                "target_phrase": "target B",
                            },
                        ],
                    },
                    {
                        "shot_id": 3,
                        "evaluation_targets": [
                            {
                                "edit_id": "B",
                                "source_task": "T2",
                                "edit_type": "attribute_edit",
                                "metric_source_query": "source B",
                                "metric_target_query": "target B",
                                "target_phrase": "target B",
                            }
                        ],
                    },
                    {
                        "shot_id": 4,
                        "evaluation_targets": [
                            {
                                "edit_id": "B",
                                "source_task": "T2",
                                "edit_type": "attribute_edit",
                                "metric_source_query": "source B",
                                "metric_target_query": "target B",
                                "target_phrase": "target B",
                            }
                        ],
                    },
                ],
            },
        },
    }


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


def test_nep_inside_mask_for_foreground_preservation():
    """T8-style NEP can score only the preserve foreground mask."""
    src = np.zeros((2, 8, 8, 3), dtype=np.uint8)
    edit = src.copy()
    src[:, :4, :4, :] = 180
    edit[:, :4, :4, :] = 180
    edit[:, 4:, 4:, :] = 240  # background changes outside the preserve mask
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[:4, :4] = 1
    r = M.nep(
        {1: src},
        {1: edit},
        per_shot_edit_masks={1: mask},
        require_masks=True,
        mask_mode="inside",
    )
    assert r["nep"] is not None and r["nep"] > 0.999, f"nep={r['nep']}"
    assert r["mask_mode"] == "inside"


def test_nep_resizes_edit_frames_and_masks():
    """Source/edit resolution mismatches should not make NEP fail."""
    src = np.zeros((2, 8, 8, 3), dtype=np.uint8)
    edit = np.zeros((2, 16, 16, 3), dtype=np.uint8)
    mask = np.zeros((16, 16), dtype=np.uint8)
    r = M.nep(
        {1: src},
        {1: edit},
        per_shot_edit_masks={1: mask},
        require_masks=True,
    )
    assert r["nep"] is not None and r["nep"] > 0.999, f"nep={r['nep']}"
    assert r["n_scored"] == 1


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


def test_tac_detects_source_shots_when_paths_are_provided():
    """Production TAC uses newly detected source shots, not prompt JSON shots."""
    prompt_src_shots = [{"shot_id": 1, "t_start": 0.0, "t_end": 99.0, "duration_sec": 99.0}]
    detected_source = [
        {"frame_start": 0, "frame_end": 47},
        {"frame_start": 48, "frame_end": 95},
    ]
    detected_edited = [
        {"frame_start": 0, "frame_end": 47},
        {"frame_start": 48, "frame_end": 95},
    ]

    def detect(path):
        return detected_source if path == "source.mp4" else detected_edited

    r = M.temporal_anchor_consistency(
        prompt_src_shots,
        "edited.mp4",
        source_video_path="source.mp4",
        source_fps=24.0,
        edited_fps=24.0,
        detect_shots_fn=detect,
    )
    assert r["tac"] is not None and r["tac"] > 0.999, f"tac={r['tac']}"
    assert r["expected_count"] == 2, f"expected_count={r['expected_count']}"
    assert r["source_count_from_detection"] is True


def test_tac_t5_reorder_uses_detected_source_anchors():
    """T5 reorder keeps prompt order, but durations come from source detection."""
    prompt_src_shots = [
        {"shot_id": 1, "t_start": 0.0, "t_end": 10.0, "duration_sec": 10.0},
        {"shot_id": 2, "t_start": 10.0, "t_end": 20.0, "duration_sec": 10.0},
    ]
    detected_source = [
        {"frame_start": 0, "frame_end": 23},   # 1s
        {"frame_start": 24, "frame_end": 71},  # 2s
    ]
    detected_edited = [
        {"frame_start": 0, "frame_end": 47},   # reordered shot 2
        {"frame_start": 48, "frame_end": 71},  # reordered shot 1
    ]

    def detect(path):
        return detected_source if path == "source.mp4" else detected_edited

    r = M.temporal_anchor_consistency(
        prompt_src_shots,
        "edited.mp4",
        source_video_path="source.mp4",
        source_fps=24.0,
        edited_fps=24.0,
        expected_order=[2, 1],
        detect_shots_fn=detect,
    )
    assert r["tac"] is not None and r["tac"] > 0.999, f"tac={r['tac']}"
    assert r["source_count_from_detection"] is True
    assert r["edited_count_from_detection"] is True


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


def test_t9_independent_per_shot_disables_csep():
    sample = {
        "sample_id": "toy_T9_ind",
        "video_id": "toy",
        "source_video": "toy.mp4",
        "shots": [{"shot_id": 1, "frame_start": 0, "frame_end": 9}, {"shot_id": 2, "frame_start": 10, "frame_end": 19}],
        "edit": {
            "task_id": "T9",
            "instruction": (
                "Shot 1: [EDIT] Change the blue bar to a bright red bar.\n"
                "Shot 2: [EDIT] Change the shooting style of shot 2 to a close-up shot."
            ),
            "target_phrase": "shot-local edits",
            "applicable_shots": [1, 2],
            "extra": {
                "mode": "independent_per_shot",
                "shot_edits": [
                    {
                        "shot_id": 1,
                        "source_task": "T2",
                        "edit_type": "attribute_edit",
                        "target_phrase": "bright red bar",
                        "metric_nep_applicable": True,
                        "metric_source_queries": ["explicit source bar"],
                        "metric_edited_queries": ["explicit edited bar"],
                        "metric_score_region": "complement",
                    },
                    {"shot_id": 2, "source_task": "T6", "edit_type": "cinematic_reshoot", "target_phrase": "close-up shot"},
                ],
            },
        },
    }
    plan = _build_t9_metric_plan(sample)
    assert [u["applicable_shots"] for u in plan["ee_units"]] == [[1], [2]]
    assert plan["nep_targets"][0]["source_queries"] == ["explicit source bar"]
    assert plan["nep_targets"][0]["edited_queries"] == ["explicit edited bar"]
    src = {1: _make_frames(1, T=1), 2: _make_frames(2, T=1)}
    edit = {1: _make_frames(3, T=1), 2: _make_frames(4, T=1)}
    vlm = PromptScoredVlm(image_scores={"bright red bar": 0.2, "close-up shot": 0.8})
    ee_r, csep_r = _score_t9_vlm_metrics(src, edit, sample, plan, [vlm])
    assert abs(ee_r["ee"] - 0.5) < 1e-6, f"ee={ee_r['ee']}"
    assert csep_r["csep"] is None, f"independent T9 should not have CSEP, got {csep_r['csep']}"


def test_t9_sequential_ee_and_csep_are_edit_weighted():
    sample = _t9_seq_sample()
    plan = _build_t9_metric_plan(sample)
    src = {i: _make_frames(i, T=1) for i in range(1, 5)}
    edit = {i: _make_frames(i + 10, T=1) for i in range(1, 5)}
    vlm = PromptScoredVlm(
        image_scores={"edit A": 0.4, "edit B": 1.0},
        pair_scores={"edit A": 0.25, "edit B": 1.0},
    )
    ee_r, csep_r = _score_t9_vlm_metrics(src, edit, sample, plan, [vlm])

    assert abs(ee_r["ee"] - 0.7) < 1e-6, f"EE should average edit A and B equally, got {ee_r['ee']}"
    expected_a = (0.4 * 0.25) ** 0.5
    expected = (expected_a + 1.0) / 2
    assert abs(csep_r["csep"] - expected) < 1e-6, f"csep={csep_r['csep']} expected={expected}"
    assert len(csep_r["t9_units"]) == 2, f"units={csep_r['t9_units']}"


def test_t9_nep_unions_multiple_edit_masks_per_shot():
    sample = _t9_seq_sample()
    plan = _build_t9_metric_plan(sample)
    src = {i: np.zeros((1, 20, 20, 3), dtype=np.uint8) for i in range(1, 5)}
    edit = {i: np.zeros((1, 20, 20, 3), dtype=np.uint8) for i in range(1, 5)}

    def mask_backend(frames, query):
        masks = np.zeros((len(frames), 20, 20), dtype=np.uint8)
        if query in {"source A", "target A"}:
            masks[:, :, :10] = 1
        elif query in {"source B", "target B"}:
            masks[:, :, 10:] = 1
        return masks

    masks, hits = _build_t9_nep_masks(sample, src, edit, plan["nep_targets"], mask_backend)
    assert masks is not None and 2 in masks, "shot 2 should have a union edit mask"
    assert int(masks[2].sum()) == 400, f"shot 2 union mask should cover both halves, got {masks[2].sum()}"
    assert hits["2"]["used"] is True


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
