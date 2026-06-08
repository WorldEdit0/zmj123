# MSEdit-Bench v1

> **首个用于多镜头视频编辑的基准。**
> 30 个多镜头视频 × 8 种任务类型 = 500 条手写编辑提示词，并通过 VLM-as-Judge 评估流程进行评测，该流程覆盖编辑有效性、跨镜头一致性、保留能力和时间结构。

[![Tests](https://img.shields.io/badge/tests-17%2F17-brightgreen)]() [![License](https://img.shields.io/badge/license-CC--BY--4.0-blue)]() [![Status](https://img.shields.io/badge/status-v1-blue)]()

---

## 为什么要做这个基准

现有的视频编辑基准（TGVE、EditBoard 等）都面向**单片段**编辑。但真实世界的视频存在**镜头切换**，一个 10 秒片段通常包含 3-5 个不同镜头，优秀的编辑器必须在**切换前后**保持身份、风格和因果状态。

**MSEdit-Bench** 是首个做到以下几点的基准：

1. 将多镜头视频作为一等对象来处理（逐镜头标注、跨镜头指标）
2. 覆盖 **8 类不同的编辑任务**（替换 / 属性 / 风格 / 添加删除 / 结构重排 / 电影化 / 光照 / 背景替换）
3. 用经过校准、且与人类判断一致的 **VLM-as-Judge** 评估，替代脆弱的 CLIP-T 代理指标

更完整的版本见 `RESEARCH_PLAN.md` 和 `DEEP_DIVE.md`。

---

## 概览

| | |
|---|---|
| **源视频** | 30 个 mp4，每个 10 秒，720p @ 24 fps，由 ModelScope 托管 |
| **镜头检测** | OmniShotCut（主）+ TransNetV2 + PySceneDetect（一致性投票）；重试后 30 / 30（100 %）命中率 |
| **编辑提示词** | Claude 手写生成 500 条（T1/T2/T3/T5/T6/T7/T8 各 60 条，T4 80 条） |
| **评估** | Mask-aware（SAM-3）+ DINOv2 + pyiqa + OmniShotCut + Seed VLM 2.0 Lite 作为裁判 |
| **K 样本协议** | 每条提示词 K = 3；报告 mean ± std |
| **参考基线** | Seedance 2.0 Pro 和 Fast 已归档旧 420-prompt snapshot；当前 500 条 prompt 需要重新跑 |

---

## 8 类任务

| ID | 名称 | 测试内容 | 示例指令 |
|---|---|---|---|
| **T1** | 跨镜头替换 | 动态实体个体级替换 + 功能兼容的静态物体类别级替换 | “将咖啡师替换为银发女咖啡师。”/“将拿铁杯换成宽口拿铁碗。” |
| **T2** | 跨镜头属性编辑 | 同一物体/主体上的颜色、材质、图案、质感、发型、毛发长度等显著属性变化 | “在每个镜头中，把咖啡师的黑色围裙改成深栗色围裙。” |
| **T3** | 全局风格 | 将整帧重新渲染为明确的大类视觉风格 | “将咖啡馆场景重新渲染为像素风格。” |
| **T4** | 跨镜头添加 / 删除 | 静态物体和动态实体的添加、删除，各类别 20 条 | “在白色陶瓷拿铁杯旁边放一个小黄铜桌铃。” |
| **T5** | 镜头重排 | 符号化镜头顺序编辑 | “将视频重排为镜头顺序 3, 1, 2。” |
| **T6** | 电影化重拍 | 单镜头构图 / 摄影机运动变化 | “将镜头 1 重拍为低角度镜头，并带有缓慢上仰。” |
| **T7** | 全局光照 | 具有明显特征、与场景关联的整体光照重渲染 | “将咖啡馆场景重新打成手电筒窄光束。” |
| **T8** | 全局背景替换 | 替换背景，同时保留前景主体、主要人物和关键物体 | “将咖啡馆背景替换成山谷，同时保留咖啡师、杯子和咖啡机。” |

T5 现在也走统一评测入口。TAC 会根据 `new_order` 重建期望的编辑后时间线，再比较 shot 时间锚点。

---

## 快速开始

### 1. 安装

```bash
git clone <this-repo>
cd multi_shot_bench
bash install.sh        # 安装 Python 依赖，并预取 DINOv2 / SAM-3 / OmniShotCut / pyiqa 权重
```

你需要：
- Python 3.11+
- 一块 CUDA GPU（SAM-3 推荐 ≥ 24 GB 显存）
- 用于 Seed VLM 裁判的 ARK API key（`export ARK_API_KEY=...`）

### 2. 运行一个编辑器基线（这里以 Seedance 参考为例）

我们将编辑器视为一个**黑盒**。将编辑后的 mp4 放入任意目录，只要目录布局如下：

```
runs/<your_baseline_name>/videos/T{1..8}/{sample_id}_k{0,1,2}.mp4
```

其中 `sample_id` 需要匹配 `runs/edit_prompts_v2_10s/T*.json` 中的 `sample_id` 字段，`k` 表示该提示词下 K = 3 个样本的索引。

对于 Seedance API 用户，可直接启动的脚本位于 [`seedance2.0/scripts/`](https://github.com/.../seedance2.0)：

```bash
# Pro
bash scripts/infer_v2_mutilshot_edit_v2_10s_all.sh

# Fast
bash scripts/infer_v2_fast_mutilshot_edit_v2_10s_all.sh
```

### 3. 评估

```bash
export ARK_API_KEY="<your-volcengine-ark-key>"

PROMPTS_DIR=runs/edit_prompts_v2_10s \
SOURCE_VIDEOS_ROOT=/abs/path/to/source_videos_10s/videos \
BASELINE_NAME=my_baseline \
BASELINE_VIDEOS_ROOT=runs/my_baseline/videos \
EVAL_OUT_ROOT=runs/eval_my_baseline_v3 \
SNAPSHOT_ID=my_baseline_v1 \
bash scripts/run_eval_parallel.sh T1 T2 T3 T4 T5 T6 T7 T8
```

该脚本会切分到 8 张 GPU 上并行运行，使用 mask-aware 后端 + Seed VLM 裁判计算所有指标，并写入：

```
runs/eval_my_baseline_v3/
├── T1/aggregate.json        # 每个指标的任务级 mean ± std
├── T1/<sample_id>.eval.json # 每条提示词 × 每个 K 的详细分数
└── ...
```

---

## 指标（v3 = 主指标）

| Metric | 衡量内容 | 后端 | 范围 |
|---|---|---|---|
| **PSQ** | 编辑帧的感知质量 | pyiqa MUSIQ + LAION-Aes | [0, 1] ↑ |
| **EE_v3** | 编辑是否执行了指令？ | Seed VLM 对每个镜头给出 0-5 评分 | [0, 1] ↑ |
| **CSEP_v3** | 编辑是否在镜头之间一致传播？ | √(coverage × consistency)；两者均由 VLM 评分 | [0, 1] ↑ |
| **NEP** | 未编辑 / 需要保留的区域是否保持？ | 局部编辑算 mask 外 DINOv2；T8 背景替换算前景保留 mask 内 DINOv2 | [0, 1] ↑ / 不适用返回 None |
| **USP** | 未被编辑指令覆盖的源 shot 是否保持？ | 对 `edit.applicable_shots` 之外的 shot 算 DINOv2 cos sim | [0, 1] ↑ / 所有 shot 都被编辑时返回 None |
| **TAC** | 编辑后视频的 shot 边界是否保持期望时间锚点？ | OmniShotCut 检测；shot 数不一致为 0，一致时按起止时间漂移扣分 | [0, 1] ↑ |

**每个指标在 `mseditbench/metrics/` 下都有自己的文件**，文件 docstring 中包含公式。v1/v2 版本仍被保留，并标注为 `DEPRECATED`，用于消融。

### 为什么使用 VLM-as-Judge（v3）？

在最终确定使用 VLM-as-Judge 之前，我们尝试过两个基于 CLIP-T 的版本：

- **v1**（二值 CLIP-T 阈值 + 3 个 VLM 全票一致）：当 CLIP-T 提升低于阈值时，会病态地把真实编辑清零；相关性较强的 VLM 投票会放大单个裁判错误。
- **v2**（连续 CLIP-T 提升）：分数范围更合理，但 Pro 一直得分*低于* Fast，因为 CLIP-T 更奖励小幅、局部的调整（Fast 的模式），而不是幅度更大但更干净的重渲染（Pro 的模式）。这是指标伪影，而不是模型真实性能。
- **v3**（VLM 直接按严格锚定量表给出 0-5 评分）：与人类判断一致，能直接捕捉视觉质量、完整性和正确性。Pro 的 PSQ 优势得以体现；Pro 和 Fast 最终相差约 4 个百分点以内，这与定性现实一致。

完整设计依据见 `mseditbench/metrics/ee_v3.py` 顶部。

---

## 参考结果

Seedance 2.0 Pro 与 Fast 在 2026-06-07 前 v2_10s 旧 420-prompt snapshot 上的归档结果（mask-aware，K=3，n=60 / task）。这些数值尚未按当前 500-prompt 任务集重跑：

| Task | PSQ Pro | PSQ Fast | EE_v3 Pro | EE_v3 Fast | CSEP_v3 Pro | CSEP_v3 Fast | NEP Pro | NEP Fast | 已退役 SES Pro | 已退役 SES Fast |
|---|---|---|---|---|---|---|---|---|---|---|
| T1 char | **0.596** | 0.576 | 0.523 | 0.543 | 0.531 | 0.537 | 0.855 | 0.893 | 1.000 | 1.000 |
| T2 attr | **0.598** | 0.573 | 0.567 | 0.627 | 0.681 | 0.717 | 0.950 | 0.972 | 0.797 | 0.822 |
| T3 style | **0.602** | 0.577 | 0.496 | 0.565 | 0.556 | 0.600 | 0.902 | 0.911 | **0.717** | 0.704 |
| T4 obj | **0.598** | 0.573 | 0.367 | 0.458 | 0.414 | 0.480 | 0.943 | 0.959 | 0.811 | 0.825 |
| T6 cam | **0.579** | 0.560 | **0.698** | 0.670 | — | — | 0.508 | 0.567 | 0.653 | 0.673 |

粗体 = 单任务胜出者。

**5 任务均值**（T1/T2/T3/T4/T6）：Pro 赢得 PSQ，在 EE_v3/CSEP_v3 上略低。表中的 SES 是已退役的 face/CLIP 旧指标，只用于解释旧结果；当前指标集需要重跑后才能报告 USP/TAC。

---

## 仓库结构

```
multi_shot_bench/
├── README.md                 # ← 你正在阅读的位置
├── HOWTO.md                  # 详细流水线说明
├── CLAUDE.md                 # 项目状态 / 面向未来贡献者的决策记录
│
├── DEEP_DIVE.md              # 长篇动机与相关工作
├── RESEARCH_PLAN.md          # 18 周计划，包含指标公式与时间安排
├── SURVEY_REPORT.md          # 领域调研（回顾 50+ 个基准）
├── RELATED_WORK_SURVEY.md    # 方法调研（编辑器 / 指标 / 评估器）
├── AGENT_BENCH_DESIGN.md     # agent-track 扩展（v2）的设计文档
│
├── install.sh                # 从零到可运行的安装脚本
├── bench_config.json         # 快照固定配置（商业 API 模型 ID）
│
├── mseditbench/              # Python 包
│   ├── schema.py             # 规范数据类
│   ├── preprocess/           # OmniShotCut + TN/PS 镜头检测、contact sheets
│   ├── tracking/             # Grounded-DINO + SAM-2-Video 实体轨迹管
│   ├── identity/             # InsightFace 人脸库
│   ├── edit_prompts/         # 任务模板 + 500 条手写提示词
│   ├── metrics/              # PSQ / EE / CSEP / NEP / USP / TAC
│   │   ├── ee_v3.py          # ★ v3 EE — VLM-as-Judge（主指标）
│   │   ├── csep_v3.py        # ★ v3 CSEP — VLM-as-Judge 成对评估
│   │   ├── ee.py             # v1 EE（DEPRECATED，保留用于消融）
│   │   ├── ee_v2.py          # v2 EE（DEPRECATED，保留用于消融）
│   │   ├── csep.py / csep_v2.py     # v1 / v2 CSEP（DEPRECATED）
│   │   ├── nep.py / psq.py / usp.py / tac.py / cxs_id.py
│   │   └── backends.py       # DINOv2 / SAM-3 / pyiqa / OmniShotCut / Seed VLM
│   ├── baselines/            # 编辑器基线接口（Aleph 参考实现）
│   ├── eval/                 # 编排器 + leaderboard + 重算工具
│   └── tests/                # 基于合成数据的 17 个单元测试，所有后端均 mock
│
├── scripts/                  # 顶层启动脚本
│   ├── run_eval_parallel.sh           # 8-GPU 并行 mask-aware 评估
│   ├── recompute_usp_parallel.sh      # 仅重新计算 USP/TAC
│   └── recompute_psq_parallel.sh      # 仅重新计算 PSQ
│
└── runs/                     # 所有流水线输出都落在这里
    ├── pilot_v2_10s/                    # ★ 镜头检测 30/30（当前）
    ├── edit_prompts_v2_10s/             # ★ 500 条生产提示词
    ├── seedance_v2v_edit_v2_10s/        # 旧 420-prompt Seedance Pro 归档输出
    ├── seedance_v2v_fast_edit_v2_10s/   # 旧 420-prompt Seedance Fast 归档输出
    ├── eval_seedance_v2v_v2_10s_v3/     # 旧 420-prompt Pro v3 leaderboard
    └── eval_seedance_v2v_fast_v2_10s_v3/ # 旧 420-prompt Fast v3 leaderboard
```

---

## 添加新的编辑器基线

按工作量从低到高，有三种方式：

1. **直接放入 mp4**（无需写代码）：在正确路径生成编辑后的视频，并使用正确的环境变量运行 `run_eval_parallel.sh`。见“快速开始”第 2 节。

2. **继承 `EditorBaseline`**：如果希望编排器端到端调用你的编辑器 API，可在 `mseditbench/baselines/base.py` 中继承 `EditorBaseline`，并注册到 `BASELINE_REGISTRY`。参考实现见 `mseditbench/baselines/aleph.py`。

3. **仅推理**：见 `seedance2.0/pyscripts/infer_v2_mutilshot_edit.py`，这是一个独立脚本，会调用远程 v2v API，并按预期布局写入 mp4。

---

## 快照协议

商业 API 的输出会随时间漂移。我们在 `bench_config.json` 中固定模型 ID，并归档所有生成视频。引用本基准时，请始终引用你的 `aggregate.json` 文件中出现的 snapshot ID（例如 `pilot_v2_10s_v3`）。

---

## 复现参考数值

```bash
# 1. 获取源视频（已在 data/source_videos_10s/ 中，或通过 ModelScope 获取）
#    https://modelscope.cn/datasets/inLine013/videobed_10s
# 2. 运行镜头检测（预期命中率 30/30）
python -m mseditbench.preprocess.shot_detect \
    --videos_dir data/source_videos_10s/videos \
    --output_dir runs/pilot_v2_10s/shots \
    --source_json seedance_api_example/source_prompts_multishot_v2_10s.json
python -m mseditbench.preprocess.pilot_report \
    --shots_dir runs/pilot_v2_10s/shots \
    --source_json seedance_api_example/source_prompts_multishot_v2_10s.json \
    --output_md runs/pilot_v2_10s/pilot_report.md \
    --output_json runs/pilot_v2_10s/pilot_report.json

# 3. 旧 420-prompt Seedance Pro / Fast 归档输出位于
#    runs/seedance_v2v_{edit,fast_edit}_v2_10s/videos/

# 4. 运行 v3 评估
export ARK_API_KEY=...
PROMPTS_DIR=runs/edit_prompts_v2_10s \
SOURCE_VIDEOS_ROOT=/abs/path/data/source_videos_10s/videos \
BASELINE_NAME=seedance_v2v_pro_v2_10s \
BASELINE_VIDEOS_ROOT=runs/seedance_v2v_edit_v2_10s/videos \
EVAL_OUT_ROOT=runs/eval_seedance_v2v_v2_10s_v3 \
SNAPSHOT_ID=pilot_v2_10s_v3 \
bash scripts/run_eval_parallel.sh T1 T2 T3 T4 T5 T6 T7 T8

# 5. 聚合结果会在 K 样本噪声范围内匹配 README leaderboard。
```

大致运行时间：8-GPU 并行 + 64 路 VLM 并发，标准任务集每个基线约 150 分钟。

---

## 路线图

**v1（本次发布）**：30 个源视频，500 条提示词，VLM-as-Judge 指标；归档 Pro/Fast 参考结果早于 2026-06-07 prompt 重构和 T8 新增，需要按当前任务集重跑。

**v1.x 后续步骤**（按优先级排序）：
1. VLM ensemble 多样化：添加 Gemini 2.5 Pro 和 GPT-4o 后端，避免裁判信号来自单一供应商
2. VACE 14B 作为第二个开源基线（已在 `seedance2.0/scripts/run_vace_*.sh` 中配置，等待启动）
3. 真实 Runway Aleph 基线（先做 T1 + T2）
4. Luma Modify / Veo 3.1 / Pika / DomoAI 商业基线

**v2 — Agent track（配套论文，独立目录）**：见 `AGENT_BENCH_DESIGN.md` 中 715 行的设计文档。使用相同的 30 个源视频和相同提示词，但通过**agent 分解式流水线**评估（Plan-Then-Execute、ReAct、CodeAct 等）。新增复合任务（T9 多轴 / T10 条件分支 / T11 迭代优化）和轨迹指标（计划质量 / 工具使用效率 / 反事实探针）。

---

## 引用

论文上传 arXiv 后会在这里补充引用块。当前请引用 GitHub 仓库 URL 以及你的评估运行的 snapshot ID。

---

## 许可证

- **代码和标注**：CC-BY-4.0
- **源视频文件**：再分发仅限约 100 个片段的定性子集（商业 API ToS；完整 30 视频集合托管在 ModelScope 的 `inLine013/videobed_10s` 下）
- **参考 Seedance 输出**：已归档以支持可复现性；不公开再分发
