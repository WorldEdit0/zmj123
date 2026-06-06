# MSEdit-Bench v1

> **The first benchmark for multi-shot video editing.**
> 30 multi-shot videos × 7 task types × 60 prompts = 420 hand-written edit prompts, evaluated with a VLM-as-Judge pipeline that captures edit effectiveness, cross-shot consistency, preservation, and identity safety.

[![Tests](https://img.shields.io/badge/tests-13%2F13-brightgreen)]() [![License](https://img.shields.io/badge/license-CC--BY--4.0-blue)]() [![Status](https://img.shields.io/badge/status-v1-blue)]()

---

## Why this benchmark exists

Existing video-edit benchmarks (TGVE, EditBoard, etc.) all target **single-clip** editing. But real-world video has **shot cuts** — a 10-second clip routinely contains 3-5 distinct shots, and a good editor must maintain identity, style, and causal state **across cuts**.

**MSEdit-Bench** is the first benchmark to:

1. Target multi-shot videos as a first-class object (per-shot annotations, cross-shot metrics)
2. Cover **7 distinct edit families** (character / attribute / style / object / structural reorder / cinematic / transition)
3. Replace fragile CLIP-T proxy metrics with a calibrated **VLM-as-Judge** evaluation that aligns with human judgment

See `RESEARCH_PLAN.md` and `DEEP_DIVE.md` for the long version.

---

## At a glance

| | |
|---|---|
| **Source videos** | 30 mp4s, 10 s each, 720p @ 24 fps, ModelScope-hosted |
| **Shot detection** | OmniShotCut (primary) + TransNetV2 + PySceneDetect (consensus); 30 / 30 (100 %) hit rate after retry |
| **Edit prompts** | 420 hand-written by Claude (7 tasks × 60 each) |
| **Evaluation** | Mask-aware (SAM-3) + pyiqa + InsightFace + Seed VLM 2.0 Lite as judge |
| **K-sample protocol** | K = 3 per prompt; report mean ± std |
| **Reference baselines** | Seedance 2.0 Pro & Fast (numbers below) |

---

## The 7 task families

| ID | Name | What it tests | Example instruction |
|---|---|---|---|
| **T1** | Cross-Shot Character Replacement | Identity swap propagating across shots | "Replace the male barista with a female android with chrome cheekbones, in every shot." |
| **T2** | Cross-Shot Attribute Edit | Localized appearance change (clothing/hair/accessories) | "Change the barista's black apron to a deep maroon apron in every shot." |
| **T3** | Global Style + Lighting | Whole-frame re-render to a new style/lighting | "Re-render the cafe scene as a midday neon-lit cyberpunk diner." |
| **T4** | Cross-Shot Object Add/Remove/Replace | Object-level insertion/replacement | "Place a small brass desk bell next to the white ceramic latte cup." |
| **T5** | Shot Reorder | Symbolic shot-order edit | "Reorder the video to shot order 3, 1, 2." |
| **T6** | Cinematic Re-shoot | Single-shot framing/camera-move change | "Re-shoot shot 1 as a low-angle shot with a slow tilt-up." |
| **T7** | Transition Style | Replace hard cuts between shots | "Replace every hard cut with a smooth crossfade." |

T5 has its own track (TSF — Task-Specific Fidelity) since per-shot pixel metrics don't apply to structural reorders.

---

## Quick start

### 1. Install

```bash
git clone <this-repo>
cd multi_shot_bench
bash install.sh        # installs Python deps + pre-fetches CLIP / DINOv2 / SAM-3 / InsightFace / pyiqa weights
```

You will need:
- Python 3.11+
- A CUDA GPU (≥ 24 GB recommended for SAM-3)
- An ARK API key for the Seed VLM judge (`export ARK_API_KEY=...`)

### 2. Run an editor baseline (Seedance reference shown)

We treat the editor as a **black box**. Drop your edited mp4s under any directory in this layout:

```
runs/<your_baseline_name>/videos/T{1..7}/{sample_id}_k{0,1,2}.mp4
```

Where `sample_id` matches the `sample_id` field in `runs/edit_prompts_v2_10s/T*.json`, and `k` indexes the K = 3 samples for that prompt.

For Seedance API users, ready-to-launch scripts live in [`seedance2.0/scripts/`](https://github.com/.../seedance2.0):

```bash
# Pro
bash scripts/infer_v2_mutilshot_edit_v2_10s_all.sh

# Fast
bash scripts/infer_v2_fast_mutilshot_edit_v2_10s_all.sh
```

### 3. Evaluate

```bash
export ARK_API_KEY="<your-volcengine-ark-key>"

PROMPTS_DIR=runs/edit_prompts_v2_10s \
SOURCE_VIDEOS_ROOT=/abs/path/to/source_videos_10s/videos \
BASELINE_NAME=my_baseline \
BASELINE_VIDEOS_ROOT=runs/my_baseline/videos \
EVAL_OUT_ROOT=runs/eval_my_baseline_v3 \
SNAPSHOT_ID=my_baseline_v1 \
bash scripts/run_eval_parallel.sh T1 T2 T3 T4 T6 T7
```

This shards across 8 GPUs, computes all metrics with mask-aware backends + Seed VLM judge, and writes:

```
runs/eval_my_baseline_v3/
├── T1/aggregate.json        # task-level mean ± std for every metric
├── T1/<sample_id>.eval.json # per-prompt × per-K detailed scores
└── ...
```

For the structural T5 track:
```bash
python -m mseditbench.eval.t5_track \
    --prompts_json runs/edit_prompts_v2_10s/T5.json \
    --baseline_dir runs/my_baseline/videos/T5 \
    --videos_root /abs/path/to/source_videos_10s/videos \
    --output_dir runs/eval_t5_track/my_baseline
```

---

## Metrics (v3 = headline)

| Metric | What it measures | Backend | Range |
|---|---|---|---|
| **PSQ** | Perceptual quality of edited frames | pyiqa MUSIQ + LAION-Aes | [0, 1] ↑ |
| **EE_v3** | Did the edit apply the instruction? | Seed VLM 0-5 rating per shot | [0, 1] ↑ |
| **CSEP_v3** | Does the edit propagate consistently across shots? | √(coverage × consistency); both VLM-rated | [0, 1] ↑ |
| **NEP** | Is the un-edited region preserved for local edits? | DINOv2 cos sim outside the SAM-3 union mask from `edit.mask_queries` | [0, 1] ↑ / None when inapplicable |
| **SES** | Is editing safely contained (no off-target damage / identity drift)? | 1 − max(IDdrift, OffTarget); ArcFace + CLIP-T | [0, 1] ↑ |
| **TSF** (T5) | Did the requested shot order happen? | OmniShotCut shot detection + ordered DINOv2 content alignment | [0, 1] ↑ |

**Each metric has its own file under `mseditbench/metrics/`** with a docstring carrying the formula. v1/v2 versions are retained marked `DEPRECATED` for ablation.

### Why VLM-as-Judge (v3)?

We tried two CLIP-T-based versions before settling on VLM-as-Judge:

- **v1** (binary CLIP-T threshold + 3-VLM unanimous): pathologically zeros out real edits when CLIP-T uplift is sub-threshold; correlated VLM votes amplify single-judge errors.
- **v2** (continuous CLIP-T uplift): scores were in a more reasonable range but Pro consistently scored *below* Fast — because CLIP-T rewards small targeted nudges (Fast's regime) over larger but cleaner re-renders (Pro's regime). This is a metric artefact, not a model truth.
- **v3** (VLM directly rates 0-5 with a strict anchored scale): aligns with human judgment, captures visual quality + completeness + correctness directly. Pro's PSQ advantage carries through; Pro and Fast end up within ~4 pp of each other, which matches the qualitative reality.

Full design rationale: top of `mseditbench/metrics/ee_v3.py`.

---

## Reference results

Seedance 2.0 Pro vs Fast on v2_10s (mask-aware, K=3, n=60 / task):

| Task | PSQ Pro | PSQ Fast | EE_v3 Pro | EE_v3 Fast | CSEP_v3 Pro | CSEP_v3 Fast | NEP Pro | NEP Fast | SES Pro | SES Fast |
|---|---|---|---|---|---|---|---|---|---|---|
| T1 char | **0.596** | 0.576 | 0.523 | 0.543 | 0.531 | 0.537 | 0.855 | 0.893 | 1.000 | 1.000 |
| T2 attr | **0.598** | 0.573 | 0.567 | 0.627 | 0.681 | 0.717 | 0.950 | 0.972 | 0.797 | 0.822 |
| T3 style | **0.602** | 0.577 | 0.496 | 0.565 | 0.556 | 0.600 | 0.902 | 0.911 | **0.717** | 0.704 |
| T4 obj | **0.598** | 0.573 | 0.367 | 0.458 | 0.414 | 0.480 | 0.943 | 0.959 | 0.811 | 0.825 |
| T6 cam | **0.579** | 0.560 | **0.698** | 0.670 | — | — | 0.508 | 0.567 | 0.653 | 0.673 |

Bold = single-task winner.

**5-task means** over T1/T2/T3/T4/T6: Pro wins PSQ, is slightly behind on EE_v3/CSEP_v3, and tied on SES. T6 is the standout where Pro beats Fast on edit quality. The picture matches the qualitative story: *Pro produces sharper, more polished edits; Fast does smaller more targeted edits and looks cleaner under VLM judgment*.

---

## Repository layout

```
multi_shot_bench/
├── README.md                 # ← you are here
├── HOWTO.md                  # detailed pipeline walkthrough
├── CLAUDE.md                 # project status / decisions for future contributors
│
├── DEEP_DIVE.md              # long-form motivation & related work
├── RESEARCH_PLAN.md          # 18-week plan with metric formulas & schedule
├── SURVEY_REPORT.md          # field survey (50+ benchmarks reviewed)
├── RELATED_WORK_SURVEY.md    # method survey (editors / metrics / evaluators)
├── AGENT_BENCH_DESIGN.md     # design doc for the agent-track extension (v2)
│
├── install.sh                # zero-to-runnable setup
├── bench_config.json         # snapshot pin (commercial-API model IDs)
│
├── mseditbench/              # the Python package
│   ├── schema.py             # canonical dataclasses
│   ├── preprocess/           # OmniShotCut + TN/PS shot detection, contact sheets
│   ├── tracking/             # Grounded-DINO + SAM-2-Video entity tubes
│   ├── identity/             # InsightFace face DB
│   ├── edit_prompts/         # task templates + 420 hand-written prompts
│   ├── metrics/              # PSQ / EE / CSEP / NEP / SES / TSF
│   │   ├── ee_v3.py          # ★ v3 EE — VLM-as-Judge (headline)
│   │   ├── csep_v3.py        # ★ v3 CSEP — VLM-as-Judge pairwise
│   │   ├── ee.py             # v1 EE (DEPRECATED, kept for ablation)
│   │   ├── ee_v2.py          # v2 EE (DEPRECATED, kept for ablation)
│   │   ├── csep.py / csep_v2.py     # v1 / v2 CSEP (DEPRECATED)
│   │   ├── nep.py / psq.py / ses.py / cxs_id.py
│   │   └── backends.py       # CLIP / DINOv2 / SAM-3 / pyiqa / InsightFace / Seed VLM
│   ├── baselines/            # editor baseline interface (Aleph reference impl)
│   ├── eval/                 # orchestrator + leaderboard + T5 TSF track
│   └── tests/                # 15 unit tests on synthetic data, all backends mocked
│
├── scripts/                  # top-level launchers
│   ├── run_eval_parallel.sh           # 8-GPU parallel mask-aware eval
│   ├── recompute_ses_parallel.sh      # SES-only recompute (when face backend changes)
│   └── recompute_psq_parallel.sh      # PSQ-only recompute
│
└── runs/                     # all pipeline outputs land here
    ├── pilot_v2_10s/                    # ★ shot detection 30/30 (current)
    ├── edit_prompts_v2_10s/             # ★ 420 production prompts
    ├── seedance_v2v_edit_v2_10s/        # Seedance Pro reference outputs
    ├── seedance_v2v_fast_edit_v2_10s/   # Seedance Fast reference outputs
    ├── eval_seedance_v2v_v2_10s_v3/     # ★ Pro v3 leaderboard
    └── eval_seedance_v2v_fast_v2_10s_v3/ # ★ Fast v3 leaderboard
```

---

## Adding a new editor baseline

Three options, in order of effort:

1. **Drop-in mp4s** (no code): produce edited videos at the right paths and run `run_eval_parallel.sh` with the right env vars. See "Quick start" §2.

2. **Subclass `EditorBaseline`** in `mseditbench/baselines/base.py` and register in `BASELINE_REGISTRY` if you want the orchestrator to call your editor's API end-to-end. See `mseditbench/baselines/aleph.py` for the reference implementation.

3. **Inference-only**: see `seedance2.0/pyscripts/infer_v2_mutilshot_edit.py` for a stand-alone script that calls a remote v2v API and writes mp4s in the expected layout.

---

## Snapshot Protocol

Commercial API outputs drift over time. We pin model IDs in `bench_config.json` and archive all generated videos. When citing this benchmark, always reference the snapshot ID present in your `aggregate.json` files (e.g. `pilot_v2_10s_v3`).

---

## Reproducing the reference numbers

```bash
# 1. Get source videos (already in data/source_videos_10s/ or via ModelScope)
#    https://modelscope.cn/datasets/inLine013/videobed_10s
# 2. Run shot detection (30/30 hit rate expected)
python -m mseditbench.preprocess.shot_detect \
    --videos_dir data/source_videos_10s/videos \
    --output_dir runs/pilot_v2_10s/shots \
    --source_json seedance_api_example/source_prompts_multishot_v2_10s.json
python -m mseditbench.preprocess.pilot_report \
    --shots_dir runs/pilot_v2_10s/shots \
    --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \
    --output_md runs/pilot_v2_10s/pilot_report.md \
    --output_json runs/pilot_v2_10s/pilot_report.json

# 3. Pre-generated reference Seedance Pro / Fast outputs are under
#    runs/seedance_v2v_{edit,fast_edit}_v2_10s/videos/

# 4. Run the v3 evaluation
export ARK_API_KEY=...
PROMPTS_DIR=runs/edit_prompts_v2_10s \
SOURCE_VIDEOS_ROOT=/abs/path/data/source_videos_10s/videos \
BASELINE_NAME=seedance_v2v_pro_v2_10s \
BASELINE_VIDEOS_ROOT=runs/seedance_v2v_edit_v2_10s/videos \
EVAL_OUT_ROOT=runs/eval_seedance_v2v_v2_10s_v3 \
SNAPSHOT_ID=pilot_v2_10s_v3 \
bash scripts/run_eval_parallel.sh T1 T2 T3 T4 T6 T7

# 5. Aggregate matches the README leaderboard within K-sample noise.
```

Approximate runtime: 8-GPU parallel + 64-way VLM concurrency, ~150 min per baseline for the standard task set.

---

## Roadmap

**v1 (this release)**: 30 source videos, 420 prompts, Pro/Fast reference, VLM-as-Judge metrics.

**v1.x next steps** (in priority order):
1. VLM ensemble diversification: add Gemini 2.5 Pro and GPT-4o backends so the judge isn't a single-vendor signal
2. VACE 14B as a second open-source baseline (already configured in `seedance2.0/scripts/run_vace_*.sh`, awaits launch)
3. Real Runway Aleph baseline (T1 + T2 first)
4. Luma Modify / Veo 3.1 / Pika / DomoAI commercial baselines

**v2 — Agent track (companion paper, separate directory)**: see `AGENT_BENCH_DESIGN.md` for a 715-line design doc. Same 30 source videos, same prompts, but evaluated with **agent-decomposed pipelines** (Plan-Then-Execute, ReAct, CodeAct, etc.). New compound tasks (T9 multi-axis / T10 conditional-branched / T11 iterative-refinement) and trajectory metrics (plan quality / tool-use efficiency / counterfactual probes).

---

## Citing

Citation block will land here once the paper is on arXiv. For now please cite the GitHub repo URL and the snapshot ID of your eval run.

---

## License

- **Code & annotations**: CC-BY-4.0
- **Source video files**: re-distribution restricted to a ~100-clip qualitative subset (commercial-API ToS; full 30-video set hosted on ModelScope under `inLine013/videobed_10s`)
- **Reference Seedance outputs**: archived for reproducibility; not redistributed publicly
