# MSEdit-Bench 接手指南

本文档是给接手者看的项目说明。它解释这个项目在做什么、目录里的文件分别负责什么、数据和代码之间怎样流动，以及怎样把一个新的视频编辑模型接入评测。

当前仓库根目录：

```bash
/home/xujiayang/projects/Multi-shot-bench/multi_shot_bench
```

## 1. 项目一句话

**MSEdit-Bench 是一个 multi-shot video editing benchmark**：给定一段已经包含多个镜头切换的源视频，再给一条编辑指令，要求视频编辑模型输出编辑后的视频；评测重点不是单帧好不好看，而是：

- 指令是否真的完成；
- 多个 shot 之间编辑是否一致；
- 不该改的区域是否保留；
- 角色身份、道具、风格是否跨镜头稳定；
- 像 T5 这种改镜头结构的任务，是否真的重排了 shot。

它不是一个训练仓库，主线是 **数据集 + prompt + baseline 输出 + 自动评测指标 + 论文材料**。

## 2. 当前最重要的版本

接手时优先以这套为准：

- 源视频：`data/source_videos_10s/videos/`，30 条 10 秒左右的 multi-shot 源视频。
- 编辑 prompt：`runs/edit_prompts_v2_10s/T1.json` 到 `T8.json`，共 500 条；T1/T2/T3/T5/T6/T7/T8 各 60 条，T4 80 条。
- 当前生产评测：`v2_10s + v3 metrics`。
- 已有 baseline 输出：
  - `runs/seedance_v2v_edit_v2_10s/videos/`
  - `runs/seedance_v2v_fast_edit_v2_10s/videos/`
  - `runs/wan_v2v_2.7_edit_v2_10s/videos/`
- 已有评测结果：
  - `runs/eval_seedance_v2v_v2_10s_v3/`
  - `runs/eval_seedance_v2v_fast_v2_10s_v3/`
  - `runs/eval_wan_v2v_2.7_v2_10s_v3/`
  - `runs/eval_t5_track/`（历史 TSF 结果，当前主线已停用）

注意：`scripts/*.sh`、`install.sh`、`HOWTO.md` 的可运行路径已经适配到当前本地 v2_10s 布局；`CLAUDE.md` 仍包含历史 HDFS 路径，只当作时间线记录，不当作当前运行配置。

## 3. 推荐阅读顺序

1. `README.md`：当前最接近真实状态的总览。
2. 本文档：接手路线、目录关系、运行命令。
3. `CLAUDE.md` 的状态总结：了解哪些决策已经定稿、哪些是历史背景。
4. `mseditbench/schema.py`：先看核心 JSON schema。
5. `mseditbench/eval/run_eval.py`：理解主评测入口。
6. `mseditbench/metrics/ee_v3.py`、`csep_v3.py`、`nep.py`、`usp.py`、`tac.py`、`psq.py`：理解指标。
7. `DEEP_DIVE.md`、`RESEARCH_PLAN.md`、`SURVEY_REPORT.md`、`RELATED_WORK_SURVEY.md`：论文动机和 related work。
8. `AGENT_BENCH_DESIGN.md`：agent 扩展轨的早期方案，不属于当前稳定主线。

## 4. 总体数据流

```text
source video prompts
  -> Seedance 生成 30 条源视频
  -> shot detection / manual QA
  -> 生成或手写 T1-T8 编辑 prompt
  -> 各视频编辑模型输出 edited videos
  -> run_eval.py 计算指标
  -> aggregate.json / leaderboard.csv
```

当前仓库里，大多数上游结果已经存在，所以日常接手最常见的工作是：

```text
放入一个新 baseline 的 edited videos
  -> 运行评测
  -> 读 aggregate.json
  -> 对比已有 baseline
```

## 5. T1 到 T8 任务

| 任务 | 名称 | 要测什么 |
|---|---|---|
| T1 | Cross-Shot Replacement | 30 条动态实体个体级替换 + 30 条功能兼容的静态物体类别级替换，重点看跨镜头一致性、局部替换质量和剧情动作是否仍然成立。 |
| T2 | Cross-Shot Attribute Edit | 改同一物体/主体的颜色、材质、图案、质感、发型、毛发长度等显著属性，不做新增配饰或物体类型替换。 |
| T3 | Global Style | 全片视觉风格重渲染，使用像素风格、新海诚风格、宫崎骏风格、JoJo 漫画风格、赛博朋克风格、水墨画风格、油画风格、美式漫画风格、3D 写实动画风格、粘土定格动画等明确大类风格。 |
| T4 | Cross-Shot Static/Dynamic Add/Delete | 静态物体、动态实体的添加和删除各 20 条，共 80 条，重点看是否漏 shot、是否误伤其他区域。 |
| T5 | Shot Reorder | 改变镜头顺序；TAC 根据 `extra.new_order` 重建期望时间线后评分。 |
| T6 | Cinematic Re-shoot | 改某个 shot 的景别、构图或相机运动，重点看目标 shot 是否被正确重拍。 |
| T7 | Global Lighting | 全片光照重渲染，只使用区分度强的光源类型，例如月光、黄昏、霓虹灯、手电筒、聚光灯、火光、黑光、频闪等。 |
| T8 | Global Background Replacement | 全片背景替换，例如把咖啡厅、工作室、街角等背景替换成山谷、森林、海滩等，同时保留前景主体、主要人物、关键物体和动作。 |

任务定义代码在 `mseditbench/edit_prompts/tasks.py`，当前正式手写 prompt 以 `runs/edit_prompts_v2_10s/T*.json` 为准；`mseditbench/edit_prompts/handwritten_t*.py` 主要保留旧 v1/v1.2 构建历史。

## 6. 核心指标

| 指标 | 代码 | 含义 |
|---|---|---|
| PSQ | `mseditbench/metrics/psq.py` | Perceptual / aesthetic quality，当前真实后端用 pyiqa 的 MUSIQ + LAION-Aes。 |
| EE v3 | `mseditbench/metrics/ee_v3.py` | Edit Effectiveness，用 VLM 判断每个相关 shot 是否完成编辑。当前应优先看 v3。 |
| CSEP v3 | `mseditbench/metrics/csep_v3.py` | Cross-Shot Edit Propagation，看相关 shot 的编辑覆盖率和一致性。当前应优先看 v3。 |
| NEP | `mseditbench/metrics/nep.py` | Non-Edit Preservation；局部编辑默认用 `edit.mask_queries` 的 source/edit union mask 外区域衡量保留，T8 用前景保留 mask 内区域衡量主体保持。 |
| USP | `mseditbench/metrics/usp.py` | Unedited Shot Preservation，只对未被编辑的 shot 计算 DINOv2 内容保持相似度；不再做人脸 ID 或 CLIP off-target。 |
| TAC | `mseditbench/metrics/tac.py` | Temporal Anchor Consistency，用 OmniShotCut 检测编辑后 shot，先检查 shot 数，再按起止时间锚点漂移扣分。 |

历史指标 `ee.py`、`ee_v2.py`、`csep.py`、`csep_v2.py` 还在代码里，但接手当前 v2_10s 结果时优先看 `ee_v3_mean` 和 `csep_v3_mean`。

## 7. 顶层文件和目录

| 路径 | 作用 | 和其他部分的关系 |
|---|---|---|
| `README.md` | 当前项目总览、任务、指标、运行方式。 | 最应该先读，但其中有些命令仍需按本机路径调整。 |
| `PROJECT_ONBOARDING.md` | 本接手指南。 | 给新接手者快速建立全局视图。 |
| `CLAUDE.md` | 原开发过程中的内部状态文档。 | 记录当前稳定版本、关键技术决策和后续 agent 方向。 |
| `HOWTO.md` | 旧流程操作手册。 | 多数流程仍有参考价值，但默认路径和版本偏旧。 |
| `DEEP_DIVE.md` | benchmark 设计深挖。 | 解释为什么要做 multi-shot edit，以及任务空间如何确定。 |
| `RESEARCH_PLAN.md` | 早期研究计划。 | 有论文 framing 和原始规模设想，当前实际版本已收敛到 30 视频、500 prompt。 |
| `SURVEY_REPORT.md` | 综述报告。 | 写 related work 和 motivation 时使用。 |
| `RELATED_WORK_SURVEY.md` | 方法卡片库。 | 更细的 related work 素材。 |
| `AGENT_BENCH_DESIGN.md` | agent 扩展轨设计。 | 不是当前稳定主线，适合作为下一阶段方向。 |
| `bench_config.json` | benchmark snapshot 和 model 配置记录。 | 保存 snapshot_id、baseline model string、K-sample 设置等元数据。 |
| `install.sh` | 环境安装脚本。 | 会安装评测依赖和预热模型权重，但含 ByteDance 内部代理与 HDFS/SAM-3 路径。 |
| `scripts/` | 评测和重算脚本。 | 是 `python -m mseditbench.eval.*` 的 shell 封装，需先修正默认路径。 |
| `data/` | 源视频和生成记录。 | `run_eval.py --videos_root` 指向这里的 `source_videos_10s/videos`。 |
| `runs/` | prompt、baseline 输出、评测输出。 | 项目最大目录，是主要实验产物。 |
| `mseditbench/` | Python 包。 | 包含 schema、预处理、prompt、baseline、metric、eval、test。 |
| `seedance_api_example/` | 源视频生成 API 示例。 | 解释源视频怎样通过 Seedance 生成，以及源视频 prompt schema。 |
| `.claude/` | Claude Code 本地设置。 | 不参与 benchmark 逻辑。 |
| `.vscode/` | VS Code 设置。 | 不参与 benchmark 逻辑。 |
| `.gitignore` | Git 忽略规则。 | 控制哪些中间产物不进版本。 |
| `.DS_Store`、`__pycache__/` | 系统或 Python 缓存。 | 可忽略，不应作为项目逻辑阅读。 |

## 8. `data/` 目录

```text
data/
  source_videos_10s/
    videos/
    inference_csv/
    success_csv/
```

- `videos/`：30 条源视频，命名通常为 `00000.mp4` 到 `00029.mp4`。
- `inference_csv/`：调用生成 API 时的记录。
- `success_csv/`：成功生成或下载的视频记录。

评测 prompt 里的 `source_video` 通常只是 `00000.mp4` 这种相对文件名，所以运行评测时要传：

```bash
--videos_root data/source_videos_10s/videos
```

## 9. `runs/` 目录

这是最重要的实验产物目录。

| 路径 | 作用 |
|---|---|
| `runs/edit_prompts_v2_10s/T1.json` 到 `T8.json` | 当前正式编辑 prompt，共 500 条；T4 为 80 条，其余任务各 60 条。 |
| `runs/edit_prompts_v2_10s/all_edit_handoff.json` | 所有任务 prompt 的合并 handoff 文件。 |
| `runs/pilot_v2_10s/shots/` | 10 秒源视频的 shot detection 结果。 |
| `runs/pilot_v2_10s/contact_sheets/` | 人工 QA 用 contact sheet。 |
| `runs/pilot_v5_final/shots/` | 另一版 pilot/final shot 结果，偏历史产物。 |
| `runs/seedance_v2v_edit_v2_10s/videos/` | Seedance Pro baseline 的编辑输出。 |
| `runs/seedance_v2v_fast_edit_v2_10s/videos/` | Seedance Fast baseline 的编辑输出。 |
| `runs/wan_v2v_2.7_edit_v2_10s/videos/` | WAN 2.7 baseline 的编辑输出。 |
| `runs/eval_seedance_v2v_v2_10s_v3/` | Seedance Pro 的 v3 评测结果。 |
| `runs/eval_seedance_v2v_fast_v2_10s_v3/` | Seedance Fast 的 v3 评测结果。 |
| `runs/eval_wan_v2v_2.7_v2_10s_v3/` | WAN 2.7 的 v3 评测结果，当前只有部分任务。 |
| `runs/eval_t5_track/` | 历史 T5 TSF 评测结果；当前主线使用 `run_eval.py` 的 TAC。 |

编辑视频文件布局是：

```text
runs/<baseline>_edit_v2_10s/videos/T1/<sample_id>_k0.mp4
runs/<baseline>_edit_v2_10s/videos/T1/<sample_id>_k1.mp4
runs/<baseline>_edit_v2_10s/videos/T1/<sample_id>_k2.mp4
...
```

例如：

```text
runs/seedance_v2v_edit_v2_10s/videos/T1/00000_T1_0000_k0.mp4
```

`run_eval.py --num_samples 3` 会找 `_k0`、`_k1`、`_k2`。如果你只有一个输出，可以用 `--num_samples 1`，文件名改成 `<sample_id>.mp4`。

## 10. `mseditbench/` Python 包

### 10.1 `schema.py`

项目的核心数据结构。重要类包括：

- `Shot`：shot_id、frame_start、frame_end。
- `ShotAnnotation`：一个视频的 shot 边界和元信息。
- `CharacterRecord`、`CharacterDB`：角色身份库。
- `EditSpec`：编辑任务、instruction、target entity、applicable shots。
- `EditPromptSample`：一条完整评测样本。
- `EvalResult`：评测输出结构。

关键约定：**frame index 是 canonical time unit**。秒数只是展示或 API 参数，评测、mask、shot 边界都按帧索引对齐。

### 10.2 `preprocess/`

负责源视频预处理和 shot detection。

| 文件 | 作用 |
|---|---|
| `preprocess/README.md` | 旧 pilot 的 shot detection 操作说明。 |
| `shot_detect.py` | 对源视频检测 shot 边界，组合 OmniShotCut、TransNetV2、PySceneDetect 等后端。 |
| `omnishot_backend.py` | OmniShotCut 推理封装，TAC 用它检测编辑后视频的 shot。 |
| `contact_sheet.py` | 把每个视频的 shot 关键帧拼成 QA 图。 |
| `pilot_report.py` | 汇总 shot detection 命中率和失败情况。 |
| `loop_until_match.py` | 生成源视频时循环重试，直到生成视频的 shot 数符合预期。 |
| `requirements.txt` | 预处理额外依赖。 |

### 10.3 `edit_prompts/`

负责定义和生成 T1-T8 prompt。

| 文件 | 作用 |
|---|---|
| `tasks.py` | T1-T8 的任务定义、模板、依赖字段。 |
| `banks.py` | prompt 生成用的候选属性、风格、对象等 bank。 |
| `generate.py` | 早期自动实例化 prompt 的 CLI。 |
| `build_v1_2_handwritten.py` | 构建旧版手写 prompt。 |
| `handwritten_t1.py` 到 `handwritten_t7.py` | 各任务的手写 prompt 内容或构造逻辑。 |
| `rewrite_with_llm.py`、`rewrite_v1_2_claude.py` | 用 LLM 改写或清洗 prompt 的脚本。 |
| `judge_3way.py` | prompt 或编辑结果的三路判断辅助脚本。 |

当前正式 prompt 已经落在 `runs/edit_prompts_v2_10s/T*.json`，日常评测一般不需要重新生成。

一条 prompt 的关键字段：

```json
{
  "sample_id": "00000_T1_0000",
  "video_id": "00000",
  "source_video": "00000.mp4",
  "shots": [{"shot_id": 1, "frame_start": 0, "frame_end": 88}],
  "characters": [{"id": "C1", "desc": "..."}],
  "key_objects": ["..."],
  "edit": {
    "task_id": "T1",
    "instruction": "...",
    "target_phrase": "...",
    "target_entity": "C1",
    "applicable_shots": [1, 2, 3]
  }
}
```

### 10.4 `baselines/`

定义“编辑模型”接口和少量示例 baseline。

| 文件 | 作用 |
|---|---|
| `base.py` | `EditorBaseline` 抽象类，统一 `edit(source_video, instruction, output_path, seed, extra)` 接口。 |
| `aleph.py` | Runway Aleph baseline 示例或封装。 |
| `snapshot.py` | baseline snapshot 元数据。 |
| `run_baseline.py` | 批量运行 baseline，把输出视频和 call manifest 写到 `runs/`。 |
| `__init__.py` | baseline registry。 |

当前接新模型有两种方式：

1. 最简单：直接把新模型输出的 mp4 按 `runs/<name>_edit_v2_10s/videos/T*/<sample_id>_k*.mp4` 放好，再跑 eval。
2. 更工程化：实现一个 `EditorBaseline` 子类，再用 `run_baseline.py` 批量调用模型。

### 10.5 `metrics/`

评测指标和后端。

| 文件 | 作用 |
|---|---|
| `backends.py` | DINOv2、Seed VLM、SAM-3、pyiqa 等当前主评测后端工厂；CLIP/Face 接口保留给旧消融代码。 |
| `frame_io.py` | 从视频按 shot / stride 取帧。 |
| `psq.py` | 画质和美学分。 |
| `ee.py`、`ee_v2.py`、`ee_v3.py` | 编辑完成度，当前看 v3。 |
| `csep.py`、`csep_v2.py`、`csep_v3.py` | 跨 shot 编辑传播一致性，当前看 v3。 |
| `nep.py` | 非编辑区域保留。 |
| `usp.py` | 未编辑 shot 的 DINOv2 内容保持。 |
| `tac.py` | 编辑前后 shot 时间锚点一致性。 |
| `ses.py` | 已退役 SES 的兼容 shim；当前主评测不再使用。 |
| `cxs_id.py` | 早期 cross-shot identity 相关指标。 |

`run_eval.py` 会把这些指标组合起来，每个 sample 输出一个 `*.eval.json`，每个 prompt 的 K 次输出一个 `*.agg.json`，每个任务输出 `aggregate.json`。

### 10.6 `eval/`

评测入口。

| 文件 | 作用 |
|---|---|
| `run_eval.py` | 主评测入口，适合 T1/T2/T3/T4/T5/T6/T7/T8 等任务。 |
| `merge_shards.py` | 多 shard 评测后合并 `aggregate.json`。 |
| `recompute_psq.py` | 在已有 eval 结果上重算 PSQ。 |
| `recompute_usp.py` | 在已有 eval 结果上重算 USP，并可选重算 TAC。 |
| `leaderboard.py` | 从 `aggregate.json` 生成 CSV，当前列包含 PSQ/EE_v3/NEP/CSEP_v3/USP/TAC。 |

### 10.7 `identity/`

角色身份相关的历史/辅助模块。

| 文件 | 作用 |
|---|---|
| `face_extract.py` | 用 InsightFace 从视频抽脸特征。 |
| `face_cluster.py` | 聚类同一角色的脸。 |
| `run_batch.py` | 批量处理入口。 |

当前主评测不再使用人脸身份漂移；这些文件主要保留为历史/辅助模块。

### 10.8 `tracking/`

实体检测和跟踪相关的历史/辅助模块。

| 文件 | 作用 |
|---|---|
| `detector.py` | Grounded-DINO 等检测后端封装。 |
| `tracker.py` | SAM2 / tube 跟踪逻辑。 |
| `run_video.py` | 单视频跟踪入口。 |
| `run_batch.py` | 批量跟踪入口。 |

当前 v3 主评测更依赖 `SAM-3 mask backend`，但这些文件解释了早期 entity tube 思路。

### 10.9 `tests/`

| 文件 | 作用 |
|---|---|
| `test_metrics.py` | metric 单元测试，通常用 mock backend，适合快速确认代码没坏。 |

快速跑：

```bash
python3 -m mseditbench.tests.test_metrics
```

## 11. `scripts/` 目录

| 文件 | 作用 | 接手注意 |
|---|---|---|
| `run_eval_parallel.sh` | 8 GPU 并行评测多个 task。 | 默认指向本地 `runs/edit_prompts_v2_10s`、`data/source_videos_10s/videos` 和 v2_10s baseline 输出；可用环境变量覆盖。 |
| `recompute_psq_parallel.sh` | 对已有 eval 目录并行重算 PSQ。 | 默认 prompt 目录为 `runs/edit_prompts_v2_10s`；可用 `PROMPTS_DIR` 覆盖。 |
| `recompute_usp_parallel.sh` | 对已有 eval 目录重算 USP/TAC。 | 默认处理 T1-T8；TAC 需要 OmniShotCut 权重。 |

本机直接跑评测时，推荐先不用这些 shell 脚本，先用下一节的显式命令。

## 12. `seedance_api_example/`

这个目录解释源视频是怎样生成的。主要文件包括：

- `README_multishot.md`：多镜头源视频生成说明、源视频 prompt schema、为什么 shot 用 frame index 作为 canonical。
- `source_prompts_multishot_v1.json` 等源视频 prompt 文件：描述每条源视频的 scene、characters、key_objects、caption、expected_shots。
- `pyscripts/infer_v2.py`、`download_videos.py` 等脚本：调用 Seedance API 并下载结果。

如果只是接一个新编辑模型，不需要动这里。只有要重建源视频集或扩数据时才需要读。

## 13. 环境和依赖

基本要求：

- Python 3.11+
- CUDA 和 NVIDIA GPU，真实后端会用到 GPU
- `ARK_API_KEY`，用于 Seed VLM 后端
- pyiqa、DINOv2、SAM-3、OmniShotCut 等模型依赖；历史消融代码仍可能需要 CLIP/InsightFace

安装脚本：

```bash
bash install.sh --skip-smoke --no-proxy
```

但要注意：

- `install.sh` 默认会使用 ByteDance 内部代理。
- SAM-3 默认检查 `checkpoints/sam3/sam3.pt`，也可用 `SAM3_CKPT` 覆盖。
- smoke test 默认使用本地 `runs/edit_prompts_v2_10s`、`runs/seedance_v2v_edit_v2_10s` 和 `data/source_videos_10s/videos`。
- 如果只是理解代码或跑 mock 测试，可以先不安装所有真实后端。

## 14. 快速验证命令

### 14.1 单元测试

```bash
cd /home/xujiayang/projects/Multi-shot-bench/multi_shot_bench
python3 -m mseditbench.tests.test_metrics
```

### 14.2 用 mock backend 跑 1 条 T1 评测

这个命令不需要 VLM API、SAM-3、pyiqa 真实后端，适合确认路径和评测入口是通的：

```bash
cd /home/xujiayang/projects/Multi-shot-bench/multi_shot_bench
python3 -m mseditbench.eval.run_eval \
  --prompts_json runs/edit_prompts_v2_10s/T1.json \
  --baseline_dir runs/seedance_v2v_edit_v2_10s/videos/T1 \
  --videos_root data/source_videos_10s/videos \
  --output_dir /tmp/msb_smoke_T1 \
  --baseline seedance_v2v_pro_v2_10s \
  --snapshot_id local_smoke \
  --backend_dino mock \
  --backend_vlm mock \
  --backend_shot none \
  --backend_mask none \
  --backend_psq mock \
  --num_samples 3 \
  --limit 1
```

输出会在 `/tmp/msb_smoke_T1/`，核心文件是：

- `<sample_id>_k0.eval.json`
- `<sample_id>_k1.eval.json`
- `<sample_id>_k2.eval.json`
- `<sample_id>.agg.json`
- `aggregate.json`

### 14.3 跑真实 v3 评测

真实评测需要 `ARK_API_KEY`、DINOv2、SAM-3、pyiqa、OmniShotCut 等依赖都能用。下面是单任务直跑版本：

```bash
cd /home/xujiayang/projects/Multi-shot-bench/multi_shot_bench
export ARK_API_KEY=<your_key>
CUDA_VISIBLE_DEVICES=0 VLM_MAX_WORKERS=4 python3 -m mseditbench.eval.run_eval \
  --prompts_json runs/edit_prompts_v2_10s/T2.json \
  --baseline_dir runs/seedance_v2v_edit_v2_10s/videos/T2 \
  --videos_root data/source_videos_10s/videos \
  --output_dir runs/eval_seedance_v2v_v2_10s_v3/T2 \
  --baseline seedance_v2v_pro_v2_10s \
  --snapshot_id v2_10s_v3 \
  --backend_dino v2s \
  --backend_vlm seed \
  --backend_shot omnishotcut \
  --backend_mask sam3 \
  --backend_psq pyiqa \
  --num_samples 3
```

多 GPU 时可以参考 `scripts/run_eval_parallel.sh`，但先把里面的 `cd`、`PROMPTS_DIR`、`SOURCE_VIDEOS_ROOT`、`BASELINE_VIDEOS_ROOT`、`EVAL_OUT_ROOT` 改成当前路径。

### 14.4 T5 评测

T5 改变 shot 顺序，EE_v3/NEP/CSEP_v3 会按任务规则跳过或返回 None；结构保持由 TAC 负责。运行方式仍然是 `run_eval.py`，只要传入 `T5.json` 和 T5 输出目录即可。

## 15. 接入一个新 baseline

### 15.1 准备输出视频

假设新模型叫 `my_editor`，建议放：

```text
runs/my_editor_edit_v2_10s/videos/T1/<sample_id>_k0.mp4
runs/my_editor_edit_v2_10s/videos/T1/<sample_id>_k1.mp4
runs/my_editor_edit_v2_10s/videos/T1/<sample_id>_k2.mp4
...
runs/my_editor_edit_v2_10s/videos/T7/<sample_id>_k2.mp4
```

`sample_id` 必须来自对应的 prompt JSON，例如：

```bash
jq -r '.[].sample_id' runs/edit_prompts_v2_10s/T1.json
```

如果模型只能产一版，使用：

```text
runs/my_editor_edit_v2_10s/videos/T1/<sample_id>.mp4
```

然后评测时传 `--num_samples 1`。

### 15.2 跑普通任务评测

```bash
python3 -m mseditbench.eval.run_eval \
  --prompts_json runs/edit_prompts_v2_10s/T1.json \
  --baseline_dir runs/my_editor_edit_v2_10s/videos/T1 \
  --videos_root data/source_videos_10s/videos \
  --output_dir runs/eval_my_editor_v2_10s_v3/T1 \
  --baseline my_editor \
  --snapshot_id v2_10s_v3 \
  --backend_dino v2s \
  --backend_vlm seed \
  --backend_shot omnishotcut \
  --backend_mask sam3 \
  --backend_psq pyiqa \
  --num_samples 3
```

对 T1/T2/T3/T4/T5/T6/T7/T8 分别跑。

### 15.3 读结果

每个任务最终看：

```text
runs/eval_my_editor_v2_10s_v3/T1/aggregate.json
```

重点字段：

- `n_prompts`
- `psq_mean`
- `ee_v3_mean`
- `csep_v3_mean`
- `nep_mean`
- `usp_mean`
- `tac_mean`

### 15.4 生成 leaderboard

旧版 leaderboard：

```bash
python3 -m mseditbench.eval.leaderboard \
  --eval_root runs/eval_my_editor_v2_10s_v3 \
  --output_csv runs/eval_my_editor_v2_10s_v3/leaderboard.csv
```

`leaderboard.py` 当前默认列已经包含 `ee_v3_mean`、`csep_v3_mean`、`usp_mean` 和 `tac_mean`。

## 16. 已有 baseline 结果怎么读

当前已有结果覆盖情况：

| Baseline | 结果目录 | 覆盖任务 |
|---|---|---|
| Seedance Pro | `runs/eval_seedance_v2v_v2_10s_v3/` | T1/T2/T3/T4/T6 |
| Seedance Fast | `runs/eval_seedance_v2v_fast_v2_10s_v3/` | T1/T2/T3/T4/T6 |
| WAN 2.7 | `runs/eval_wan_v2v_2.7_v2_10s_v3/` | T1/T2/T3/T4 |
| T5 Seedance Pro/Fast | `runs/eval_t5_track/` | T5 历史 TSF 结果 |

快速查看：

```bash
jq '.baseline, .task_id, .n_prompts, .psq_mean, .ee_v3_mean, .csep_v3_mean, .nep_mean, .usp_mean, .tac_mean' \
  runs/eval_seedance_v2v_v2_10s_v3/T1/aggregate.json
```

## 17. 常见坑

1. **版本混淆**：当前用 `runs/edit_prompts_v2_10s`，不是旧的 `runs/edit_prompts_v1.2`。
2. **源视频目录**：当前本机源视频在 `data/source_videos_10s/videos`，不是 `data/source_videos/videos`。
3. **外部模型路径**：OmniShotCut、SAM-3 等大模型权重默认按本地 `checkpoints/` 或相邻 checkout 查找；缺失时用 `OMNISHOTCUT_REPO`、`OMNISHOTCUT_CKPT`、`SAM3_ROOT`、`SAM3_CKPT` 覆盖。
4. **T5 的普通 per-shot 指标会部分跳过**：T5 改 shot 顺序，当前结构评测看 `tac_mean`；TAC 会按 `new_order` 重建期望时间线。
5. **K-sample 命名要一致**：`--num_samples 3` 找 `_k0/_k1/_k2`；`--num_samples 1` 找无 `_k` 的 `<sample_id>.mp4`。
6. **SES 已停用**：当前保留性指标看 `nep_mean` 和 `usp_mean`，时间结构看 `tac_mean`。
7. **SAM-3 权重路径**：真实 mask backend 依赖本机权重路径，迁移机器时最容易坏。
8. **VLM 调用成本和并发**：`backend_vlm seed` 需要 `ARK_API_KEY`，`VLM_MAX_WORKERS` 设置过大可能触发限流。
9. **旧文档规模不是当前规模**：`RESEARCH_PLAN.md` 提过 930 prompt，但当前已落地的是 500 prompt。
10. **缓存文件不用读**：`.DS_Store`、`__pycache__`、`.pyc` 都不是项目逻辑。

## 18. 你真正需要掌握的最小闭环

如果目标是“能接手并使用项目”，先掌握这个闭环：

1. 打开 `runs/edit_prompts_v2_10s/T1.json`，理解一条 prompt 的 `sample_id`、`source_video`、`shots`、`edit.instruction`。
2. 在 `runs/<baseline>_edit_v2_10s/videos/T1/` 找同名 edited video。
3. 用 `mseditbench.eval.run_eval` 对这个 task 打分。
4. 打开 `aggregate.json`，读 `ee_v3_mean`、`csep_v3_mean`、`nep_mean`、`usp_mean`、`tac_mean`。
5. 对 T5 同样使用 `mseditbench.eval.run_eval`，重点读 `tac_mean`。

能跑通这 5 步，就已经掌握了这个项目最核心的使用方式。
