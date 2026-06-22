# MSEdit-Bench

MSEdit-Bench 是一个面向多镜头视频编辑的 benchmark 和评测工具。它关注的不是单帧是否好看，而是视频编辑模型能否在有多次 shot cut 的视频中完成指令，并在跨镜头范围内保持身份、物体、场景结构和时间锚点。

本 README 按当前仓库中实际存在的文件更新。旧的 v1/v2 内容可能还留在代码注释或历史文档中，用于追溯和消融；当前主线以 `runs/edit_prompts_v3_vlm/` 下的 v3 prompt 集为准。

## 当前快照

| 项目 | 当前内容 |
|---|---|
| 源视频 prompt | `source_prompts_multishot_v3_cn_flexible_draft.json` |
| 源视频 | 本地 30 个 mp4，路径为 `runs/source_videos_v3/videos/` |
| 源视频元信息 | 10 秒，24 fps，每条预期 2-6 个 shot |
| 编辑 prompt 集 | `runs/edit_prompts_v3_vlm/T1.json` 到 `T9.json` |
| prompt 数量 | 共 560 条 |
| 当前 baseline 视频 | `runs/seedance_v2v_edit_v3_10s_0616/videos/` 和 `runs/seedance_v2v_fast_edit_v3_10s_0616/videos/` |
| 当前评测摘要 | `runs/eval_seedance_v2v_pro_v3_10s_0616_non_vlm/`、`runs/eval_seedance_v2v_fast_v3_10s_0616_non_vlm/`、`runs/eval_seedance_v2v_pro_fast_v3_10s_0616_non_vlm/` |
| 主评测入口 | `mseditbench/eval/run_eval.py` |
| 统一启动脚本 | `scripts/eval_suite.sh`、`scripts/run_eval_parallel.sh` |
| 独立 EE/CSEP 评测器 | `standalone_ee_csep_eval/` |

视频、模型权重、zip 和大部分本地大文件都被 git 忽略。README 仍然保留这些路径，因为本地评测会直接读取这些目录。

## 任务集

当前 v3 prompt manifest 位于 `runs/edit_prompts_v3_vlm/manifest.json`。

| 任务 | 数量 | 测试内容 |
|---|---:|---|
| T1 跨镜头替换 | 60 | 动态实体替换和静态物体替换 |
| T2 跨镜头属性编辑 | 60 | 颜色、材质、纹理、图案、文字、发型等同一对象属性变化 |
| T3 全局风格 | 60 | 全视频风格重渲染，同时保留内容和 shot 顺序 |
| T4 跨镜头添加/删除 | 80 | 静态添加、静态删除、动态添加、动态删除各 20 条 |
| T5 镜头重排 | 60 | 符号化 shot 顺序变化，主要由 TAC 评分 |
| T6 电影化重拍 | 60 | 单个 shot 的景别、构图或摄影机运动变化 |
| T7 全局光照 | 60 | 全视频光照变化 |
| T8 全局背景替换 | 60 | 替换背景，并用前景 mask 评估主体保留 |
| T9 跨镜头复合编辑 | 60 | shot 条件化混合编辑，以及两个对象级编辑的持续绑定 |

T9 有两种模式：

- `independent_per_shot`：不同 shot 接收不同编辑；单 shot edit unit 不计算 CSEP。
- `sequential_two_edit_prompt`：两个对象级编辑分开评分，并要求目标对象后续再次出现时持续保持编辑结果。

## 指标

主评测器会先为每个编辑视频写出 `{sample_id}_k*.eval.json`，再对同一个 prompt 的 K 个结果聚合成 `{sample_id}.agg.json`，最后生成任务级 `aggregate.json`。

| 指标 | 文件 | 含义 |
|---|---|---|
| PSQ | `mseditbench/metrics/psq.py` | 编辑后视频帧的感知质量和美学质量 |
| EE_v3 | `mseditbench/metrics/ee_v3.py` | VLM-as-judge 的编辑有效性，按 applicable shots 评分 |
| CSEP_v3 | `mseditbench/metrics/csep_v3.py` | 跨镜头编辑传播一致性，公式为 `sqrt(coverage * consistency)` |
| NEP | `mseditbench/metrics/nep.py` | 用 SAM3 mask 和 DINOv2 相似度衡量非编辑区域保留 |
| USP | `mseditbench/metrics/usp.py` | 衡量 `edit.applicable_shots` 之外的未编辑 shot 是否保持 |
| TAC | `mseditbench/metrics/tac.py` | 根据编辑后视频 shot 边界计算时间锚点一致性 |

旧版 CLIP-based EE/CSEP 文件仍保留用于对比；当前主指标是 `EE_v3` 和 `CSEP_v3`。

## 仓库结构

```text
.
├── README.md
├── README_zh.md
├── source_prompts_multishot_v3_cn_flexible_draft.json
├── modelscope_dl.py
├── docs/
│   └── metrics_flow_zh.md
├── scripts/
│   ├── build_v3_vlm_edit_prompts.py
│   ├── eval_suite.sh
│   ├── recompute_usp_parallel.sh
│   └── run_eval_parallel.sh
├── mseditbench/
│   ├── schema.py
│   ├── preprocess/
│   ├── edit_prompts/
│   ├── metrics/
│   ├── eval/
│   ├── baselines/
│   ├── tracking/
│   ├── identity/
│   └── tests/
├── runs/
│   ├── source_videos_v3/
│   ├── edit_prompts_v3_vlm/
│   ├── seedance_v2v_edit_v3_10s_0616/
│   ├── seedance_v2v_fast_edit_v3_10s_0616/
│   ├── eval_seedance_v2v_pro_v3_10s_0616_non_vlm/
│   ├── eval_seedance_v2v_fast_v3_10s_0616_non_vlm/
│   └── eval_seedance_v2v_pro_fast_v3_10s_0616_non_vlm/
├── seedance_api_example/
└── standalone_ee_csep_eval/
```

`CLAUDE.md` 和 `PROJECT_ONBOARDING.md` 是有用的历史说明，但里面可能包含旧路径。当前运行请以本 README 和 `mseditbench/` 下的代码为准。

## 安装

当前仓库没有顶层 lockfile 或安装脚本。建议使用 Python 3.10+ 或 3.11+，再按需要安装对应后端依赖。

最小 smoke test 依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy opencv-python tqdm
```

真实后端会懒加载：

- `pyiqa`：用于 PSQ。
- DINOv2 和 PyTorch：用于 NEP/USP。
- SAM3 权重：用于 NEP mask。默认路径为 `mseditbench/ckpt/sam3/sam3.pt`，也可设置 `SAM3_CKPT`。
- OmniShotCut：用于 TAC。
- `volcenginesdkarkruntime` 和 `ARK_API_KEY`：用于 `BACKEND_VLM=seed`。
- 本地 Qwen3-VL 权重和 `QWEN3VL_MODEL_PATH`：用于 `BACKEND_VLM=qwen3vl`。

## 视频布局

每个 baseline 的编辑后视频应放在：

```text
runs/<baseline_name>/videos/<TASK>/<sample_id>_k0.mp4
```

例如：

```text
runs/seedance_v2v_edit_v3_10s_0616/videos/T1/00000_T1_0000_k0.mp4
```

当前本地 v3 结果使用 `NUM_SAMPLES=1`。如果每条 prompt 生成多个样本，就继续增加 `_k1`、`_k2`，并同步设置 `NUM_SAMPLES`。

## Smoke Test

下面命令用 mock 重后端验证评测编排流程；仍然要求本地存在源视频和编辑后视频。

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

## 运行当前 non-VLM 评测

当前已有摘要是 non-VLM 摘要：PSQ、NEP、USP、TAC 有值，EE_v3/CSEP_v3 需要 VLM 后端重跑后才会填充。

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

小机器可以设置 `NUM_SHARDS=1`。

## 运行 EE_v3 和 CSEP_v3

使用 Ark/Seed VLM：

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

如果使用本地 Qwen3-VL，设置 `BACKEND_VLM=qwen3vl`，并把 `QWEN3VL_MODEL_PATH` 指向本地 checkpoint。

如果只需要 EE_v3/CSEP_v3，不想依赖整个主仓库，可以用 `standalone_ee_csep_eval/`。它已经包含 T1-T9 prompt 副本、VLM prompt 模板和独立评测脚本：

```bash
cd standalone_ee_csep_eval
pip install -r requirements.txt
cp .env.example .env
source .env
python src/eval_ee_csep.py --tasks T1,T2,T9
```

## 当前参考结果

当前本地对比是 non-VLM，且 `K=1`。

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

因为这批结果不包含 VLM 指标，所以不能当作最终指令遵循能力结论。正式报告编辑有效性和跨镜头一致性时，需要补跑 EE_v3/CSEP_v3。

## 测试

指标测试使用 mock 重后端：

```bash
python3 -m mseditbench.tests.test_metrics
```

## Git 说明

`.gitignore` 会忽略生成视频、压缩包、模型权重，以及 `CLIP/`、`OmniShotCut/`、`sam3/`、`Qwen3-VL/` 等本地模型目录。Python、Markdown 和 JSON 文件会放行，这样 prompt 和评测元数据可以和大体积二进制文件分开管理。
