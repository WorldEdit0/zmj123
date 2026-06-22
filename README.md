# MSEdit-Bench

MSEdit-Bench is a benchmark and evaluation toolkit for multi-shot video
editing. It evaluates whether an editor can apply an instruction to videos
with multiple shot cuts while preserving identity, objects, scene structure,
and temporal anchors across shots.

This README describes the current files in this repository. Older v1/v2
material may still exist in code comments or companion notes for history and
ablation, but the current data path is the v3 prompt set under
`runs/edit_prompts_v3_vlm/`.

## Current Snapshot

| Item | Current value |
|---|---|
| Source prompt file | `source_prompts_multishot_v3_cn_flexible_draft.json` |
| Source videos | 30 local mp4s under `runs/source_videos_v3/videos/` |
| Source metadata | 10 seconds, 24 fps, expected 2-6 shots per video |
| Edit prompt set | `runs/edit_prompts_v3_vlm/T1.json` through `T9.json` |
| Prompt count | 560 total prompts |
| Current baseline videos | `runs/seedance_v2v_edit_v3_10s_0616/videos/` and `runs/seedance_v2v_fast_edit_v3_10s_0616/videos/` |
| Current eval summaries | `runs/eval_seedance_v2v_pro_v3_10s_0616_non_vlm/`, `runs/eval_seedance_v2v_fast_v3_10s_0616_non_vlm/`, and `runs/eval_seedance_v2v_pro_fast_v3_10s_0616_non_vlm/` |
| Main evaluator | `mseditbench/eval/run_eval.py` |
| Unified launchers | `scripts/eval_suite.sh`, `scripts/run_eval_parallel.sh` |
| Standalone VLM-only evaluator | `standalone_ee_csep_eval/` |

Generated videos, checkpoints, zips, and most large local assets are ignored by
git. The README still names their expected local paths because the evaluator
uses those paths directly.

## Task Set

The current v3 prompt manifest is
`runs/edit_prompts_v3_vlm/manifest.json`.

| Task | Count | What it tests |
|---|---:|---|
| T1 Cross-Shot Replacement | 60 | Dynamic entity replacement and static object replacement |
| T2 Cross-Shot Attribute Edit | 60 | Color, material, texture, pattern, text, hair, or other same-object changes |
| T3 Global Style | 60 | Whole-video style re-rendering while preserving content and shot order |
| T4 Cross-Shot Add/Delete | 80 | Static add, static delete, dynamic add, and dynamic delete, 20 prompts each |
| T5 Shot Reorder | 60 | Symbolic shot-order changes scored mainly through TAC |
| T6 Cinematic Re-shoot | 60 | Shot-local framing or camera-motion changes |
| T7 Global Lighting | 60 | Whole-video lighting changes |
| T8 Global Background Replacement | 60 | Background replacement with foreground preservation masks |
| T9 Composite Cross-Shot Editing | 60 | Shot-conditioned mixed edits plus persistent two-object composite edits |

T9 has two modes:

- `independent_per_shot`: different shots receive separate edit instructions;
  CSEP is skipped for one-shot edit units.
- `sequential_two_edit_prompt`: two object-level edits are scored separately
  and should persist wherever their target objects reappear.

## Metrics

The main evaluator writes one `{sample_id}_k*.eval.json` per edited video, then
one `{sample_id}.agg.json` per prompt, then a task-level `aggregate.json`.

| Metric | File | Meaning |
|---|---|---|
| PSQ | `mseditbench/metrics/psq.py` | Perceptual and aesthetic quality of edited frames |
| EE_v3 | `mseditbench/metrics/ee_v3.py` | VLM-as-judge edit effectiveness on applicable shots |
| CSEP_v3 | `mseditbench/metrics/csep_v3.py` | Cross-shot edit propagation: `sqrt(coverage * consistency)` |
| NEP | `mseditbench/metrics/nep.py` | Non-edit preservation using SAM3 masks and DINOv2 similarity |
| USP | `mseditbench/metrics/usp.py` | Preservation of source shots outside `edit.applicable_shots` |
| TAC | `mseditbench/metrics/tac.py` | Temporal anchor consistency from edited-video shot boundaries |

Legacy CLIP-based EE/CSEP files are retained for comparison, but the current
headline VLM metrics are `EE_v3` and `CSEP_v3`.

## Repository Layout

```text
.
|-- README.md
|-- README_zh.md
|-- source_prompts_multishot_v3_cn_flexible_draft.json
|-- modelscope_dl.py
|-- docs/
|   `-- metrics_flow_zh.md
|-- scripts/
|   |-- build_v3_vlm_edit_prompts.py
|   |-- eval_suite.sh
|   |-- recompute_usp_parallel.sh
|   `-- run_eval_parallel.sh
|-- mseditbench/
|   |-- schema.py
|   |-- preprocess/
|   |-- edit_prompts/
|   |-- metrics/
|   |-- eval/
|   |-- baselines/
|   |-- tracking/
|   |-- identity/
|   `-- tests/
|-- runs/
|   |-- source_videos_v3/
|   |-- edit_prompts_v3_vlm/
|   |-- seedance_v2v_edit_v3_10s_0616/
|   |-- seedance_v2v_fast_edit_v3_10s_0616/
|   |-- eval_seedance_v2v_pro_v3_10s_0616_non_vlm/
|   |-- eval_seedance_v2v_fast_v3_10s_0616_non_vlm/
|   `-- eval_seedance_v2v_pro_fast_v3_10s_0616_non_vlm/
|-- seedance_api_example/
`-- standalone_ee_csep_eval/
```

`CLAUDE.md` and `PROJECT_ONBOARDING.md` are useful historical notes, but they
may contain older local paths. Treat this README and the code under
`mseditbench/` as the current reference.

## Installation

There is no current top-level lockfile or install script in the repository.
Use Python 3.10+ or 3.11+, then install the dependencies needed by the backend
you plan to run.

Minimal smoke-test dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy opencv-python tqdm
```

Additional real backends are loaded lazily:

- `pyiqa` for PSQ.
- DINOv2 and PyTorch for NEP/USP.
- SAM3 checkpoints for NEP masks. Default path:
  `mseditbench/ckpt/sam3/sam3.pt`, or set `SAM3_CKPT`.
- OmniShotCut for TAC.
- `volcenginesdkarkruntime` plus `ARK_API_KEY` for `BACKEND_VLM=seed`.
- A local Qwen3-VL checkpoint plus `QWEN3VL_MODEL_PATH` for
  `BACKEND_VLM=qwen3vl`.

## Expected Video Layout

For each baseline, put edited videos under:

```text
runs/<baseline_name>/videos/<TASK>/<sample_id>_k0.mp4
```

For example:

```text
runs/seedance_v2v_edit_v3_10s_0616/videos/T1/00000_T1_0000_k0.mp4
```

Set `NUM_SAMPLES=1` for the current local v3 runs. If you generate multiple
samples per prompt, add `_k1`, `_k2`, etc. and set `NUM_SAMPLES` accordingly.

## Run a Smoke Test

This exercises the orchestration with mock heavy backends. It still needs the
source and edited videos to exist locally.

```bash
python3 -m mseditbench.eval.run_eval \
  --prompts_json runs/edit_prompts_v3_vlm/T1.json \
  --baseline_dir runs/seedance_v2v_edit_v3_10s_0616/videos/T1 \
  --videos_root runs/source_videos_v3/videos \
  --output_dir /tmp/mseditbench_smoke/T1 \
  --baseline seedance_v2v_pro \
  --snapshot_id smoke_v3 \
  --backend_dino mock \
  --backend_vlm mock \
  --backend_shot none \
  --backend_mask none \
  --backend_psq mock \
  --num_samples 1 \
  --limit 2
```

## Run the Current Non-VLM Evaluation

The current checked summaries are non-VLM summaries: PSQ, NEP, USP, and TAC are
filled, while EE_v3/CSEP_v3 are blank until a VLM run is performed.

```bash
PROMPTS_DIR=runs/edit_prompts_v3_vlm \
SOURCE_VIDEOS_ROOT=runs/source_videos_v3/videos \
BASELINE_NAME=seedance_v2v_pro \
BASELINE_VIDEOS_ROOT=runs/seedance_v2v_edit_v3_10s_0616/videos \
EVAL_OUT_ROOT=runs/eval_seedance_v2v_pro_v3_10s_0616_non_vlm \
SNAPSHOT_ID=v3_10s_0616_non_vlm \
NUM_SAMPLES=1 \
NUM_SHARDS=8 \
METRICS=non_vlm \
bash scripts/run_eval_parallel.sh T1 T2 T3 T4 T5 T6 T7 T8 T9

python3 -m mseditbench.eval.summarize \
  --eval_root runs/eval_seedance_v2v_pro_v3_10s_0616_non_vlm
```

For a smaller machine, set `NUM_SHARDS=1`.

## Run EE_v3 and CSEP_v3

For Ark/Seed VLM:

```bash
export ARK_API_KEY="<your-key>"

PROMPTS_DIR=runs/edit_prompts_v3_vlm \
SOURCE_VIDEOS_ROOT=runs/source_videos_v3/videos \
BASELINE_NAME=seedance_v2v_pro \
BASELINE_VIDEOS_ROOT=runs/seedance_v2v_edit_v3_10s_0616/videos \
EVAL_OUT_ROOT=runs/eval_seedance_v2v_pro_v3_10s_0616_vlm \
SNAPSHOT_ID=v3_10s_0616_vlm \
NUM_SAMPLES=1 \
NUM_SHARDS=8 \
METRICS=all \
BACKEND_VLM=seed \
bash scripts/run_eval_parallel.sh T1 T2 T3 T4 T5 T6 T7 T8 T9
```

For local Qwen3-VL, set `BACKEND_VLM=qwen3vl` and point
`QWEN3VL_MODEL_PATH` to the checkpoint.

If you only need EE_v3/CSEP_v3 without the full repository, use
`standalone_ee_csep_eval/`. It contains copied T1-T9 prompts, VLM prompt
templates, and a self-contained evaluator:

```bash
cd standalone_ee_csep_eval
pip install -r requirements.txt
cp .env.example .env
source .env
python src/eval_ee_csep.py --tasks T1,T2,T9
```

## Current Reference Results

The current local comparison is non-VLM only and uses `K=1`.

| Task | Prompts | Pro score | Fast score | Fast - Pro |
|---|---:|---:|---:|---:|
| T1 | 60 | 0.8642 | 0.8643 | 0.0001 |
| T2 | 60 | 0.8652 | 0.8670 | 0.0019 |
| T3 | 60 | 0.7536 | 0.7733 | 0.0198 |
| T4 | 80 | 0.8703 | 0.8681 | -0.0022 |
| T5 | 60 | 0.5237 | 0.5075 | -0.0162 |
| T6 | 60 | 0.8288 | 0.8164 | -0.0124 |
| T7 | 60 | 0.7515 | 0.7613 | 0.0098 |
| T8 | 60 | 0.8206 | 0.8209 | 0.0003 |
| T9 | 60 | 0.8618 | 0.8428 | -0.0190 |
| Overall |  | 0.7933 | 0.7913 | -0.0020 |

Because these are non-VLM summaries, they should not be read as final
instruction-following scores. Run EE_v3/CSEP_v3 for final edit-effectiveness
and cross-shot consistency reporting.

## Tests

The metrics tests use mocked heavy backends:

```bash
python3 -m mseditbench.tests.test_metrics
```

## Git Notes

`.gitignore` intentionally excludes generated videos, archives, checkpoints,
and local model folders such as `CLIP/`, `OmniShotCut/`, `sam3/`, and
`Qwen3-VL/`. Python, Markdown, and JSON files are allowed through so prompt and
evaluation metadata can be tracked separately from large binary artifacts.
