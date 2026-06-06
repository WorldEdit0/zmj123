# MSEdit-Bench Preprocess: Shot Detection Pipeline

视频生成完之后第一件事 —— 检测 shot 边界、和 `expected_shots` 对照、看 Seedance 切镜是否对得上。

## 安装

```bash
cd /Users/bytedance/Desktop/AAAI2027/multi_shot_bench
pip install -r mseditbench/preprocess/requirements.txt

# TransNetV2（推荐，比 PySceneDetect 准）二选一：
pip install transnetv2-pytorch   # PyTorch 版（推荐，无 TF 依赖）
# 或
pip install transnetv2           # 原版 TensorFlow
```

> 如果 TransNetV2 装不上，pipeline 会自动 fallback 到只用 PySceneDetect，但准确率会差一些。

## 三步走

### 1. 检测 shot 边界

```bash
python mseditbench/preprocess/shot_detect.py \
    --videos_dir /path/to/your/videos_1080p \
    --output_dir runs/pilot_v1/shots \
    --source_json seedance_api_example/source_prompts_multishot_v1.json
```

产出：`runs/pilot_v1/shots/00000.shots.json`（每个视频一个），含 TransNetV2 + PySceneDetect 双检测结果 + 自动对照 `expected_shots`。

### 2. 生成可视化 contact sheet

```bash
python mseditbench/preprocess/contact_sheet.py \
    --shots_dir runs/pilot_v1/shots \
    --videos_dir /path/to/your/videos_1080p \
    --output_dir runs/pilot_v1/contact_sheets
```

产出：`runs/pilot_v1/contact_sheets/00000_contact.jpg`，每张图是一个视频的所有 shot 的 start/mid/end keyframe 拼接，header 标 actual vs expected 是否对得上（绿色 OK / 红色 MISMATCH）。**这是人工 QA 的主要工具。**

### 3. 聚合 pilot 报告

```bash
python mseditbench/preprocess/pilot_report.py \
    --shots_dir runs/pilot_v1/shots \
    --source_json seedance_api_example/source_prompts_multishot_v1.json \
    --contact_sheets_dir runs/pilot_v1/contact_sheets \
    --output_md runs/pilot_v1/pilot_report.md \
    --output_json runs/pilot_v1/pilot_report.json
```

产出：`pilot_report.md` 含总命中率、off-by-one 率、按 category 的命中率、每视频明细 + 嵌入 contact sheet。终端也会打一份摘要。

## 怎么读 pilot 报告

| 命中率 | 行动 |
|---|---|
| **≥ 85%** | ✅ 直接扩到 150 prompt，进入 Phase 1 全量数据生成 |
| **70-85%** | ⚠️ 看 contact sheet 找规律（哪类场景失败），改 prompt 重跑失败的 |
| **< 70%** | ❌ 别扩。Seedance 没按 `[shot tag]` 切镜；要换 prompt 风格 |

## 常见失败模式与建议

| 现象 | 可能原因 | 修复 |
|---|---|---|
| 大量 actual=1（完全没切） | `[shot tag]` 没被 Seedance 当作 cut 指令 | 试 `[Cut to wide shot:]` 或中文 `[切换到广角镜头]` |
| actual > expected | Seedance 自由切镜（在长 shot 里又自己切了一刀） | 每个 shot 加更多动作描述让模型"留在 shot 里"；或减少 prompt 中的运动词 |
| actual < expected | 相邻 shot 太相似，Seedance 没切 | shot 间用强对比（"室内 → 室外"、"大景 → 特写"、加镜头类型反差） |
| TransNetV2 ↔ PySceneDetect 不一致 | 视频含 dissolve / fade（不是 hard cut） | 看 contact sheet 人工判定；可调 `--pyscenedetect_threshold` 或 `--transnet_threshold` |
| TN 多 PS 少 | TN 对运动敏感（误报） | 调高 `--transnet_threshold`（从 0.5 提到 0.6-0.7） |

## Shot JSON schema（下游评测会复用）

```json
{
  "video_id": "00000",
  "fps": 24.0,
  "total_frames": 360,
  "duration_sec": 15.0,
  "width": 1920,
  "height": 1080,
  "expected_shots": 4,
  "transnetv2": {
    "n_shots": 4,
    "backend": "transnetv2_pytorch",
    "threshold": 0.5,
    "shots": [
      {"shot_id": 1, "frame_start": 0, "frame_end": 89,
       "duration_frames": 90, "t_start": 0.0, "t_end": 3.75, "duration_sec": 3.75},
      ...
    ]
  },
  "pyscenedetect": { ... },
  "agreement": {
    "shot_count_match": true,
    "boundaries_within_tolerance": true,
    "tolerance_sec": 0.25
  },
  "consensus_shots": [...],
  "consensus_n_shots": 4,
  "matches_expected": true
}
```

**frame 是 canonical，time 是 derived**（详见 `seedance_api_example/README_multishot.md` §四）。

## 下一步（pilot 通过后）

1. **跑 150 条全量 prompt** → 重复 1-3 步，得到全量 shots.json
2. **建立 entity tracking pipeline**：Grounded-SAM2 + DEVA 对每个视频抽 per-shot entity tube（角色/物体）
3. **建立 character face DB**：InsightFace + cluster 跨 shot 同一角色 → entity_id
4. **开始写 T1-T7 edit prompt**（基于 source JSON 的 characters + key_objects + 实际检测到的 shot 数）
