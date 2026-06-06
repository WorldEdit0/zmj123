# Source Video Generation via Seedance 2.0（多镜头版）

## 一、用法

```bash
# 1. 填 API key（在 pyscripts/infer_v2.py 第 21 行）

# 2. 单 shard 测试（生成全部 30 条 prompt 之中的一份子集）
python3 pyscripts/infer_v2.py \
    --input_json source_prompts_multishot_v1.json \
    --csv_path test_results.csv \
    --num_shards 1 --shard_id 0 \
    --split_num 1 --split_index 0

# 3. 下载视频
python3 download_videos.py \
    --csv_path test_results.csv \
    --output_dir videos_1080p \
    --success_csv test_success.csv \
    --shards_num 1 --shard_id 0
```

`infer_v2.sh` 是多机多分片的批量脚本，沿用原配置即可（只需把 `input_json` 换成 `source_prompts_multishot_v1.json`，把 `duration` 不再写死 5s）。

## 二、infer_v2.py 改动总结（最小化）

只动了 3 处：

1. **L50** —— CSV 加 5 列元数据（`duration_sec` / `fps` / `expected_shots` / `scene_id` / `category`），供下游 TransNetV2 切分和评测复用
2. **L71-90** —— `client.tasks.create()` 调用：
   - 去掉原来的"相机机位固定 / 只有一个场景 / 不要场景切换"反多镜头包裹
   - `duration` / `ratio` / `resolution` 从 item 读取，默认 `15s / 16:9 / 1080p`（Seedance 2.0 Pro 上限 15s，拉满以争取更多镜头数）
   - `caption` 直接传给 API（caption 自身已含 `[shot tag]` 风格的多镜头指令）
3. **L111-140** —— writer.writerow 写入元数据列

其余（断点续传 / shard 切分 / 异常处理）一字未动。

## 三、JSON schema

`source_prompts_multishot_v1.json` 是一个 list，每条 item：

```jsonc
{
  "global_index": 0,                // 必填，用于生成文件名 00000.mp4
  "scene_id": "kitchen_morning_dialogue",  // 场景标识，用于追踪
  "category": "dialogue_2person_indoor",   // 类别，用于按类型抽样和评测
  "duration_sec": 15,               // 必填，Seedance 2.0 Pro 上限 15s，本 bench 默认拉满
  "fps": 24,                        // Seedance 固定 24fps，显式记录
  "expected_shots": 4,              // 预期镜头数：v1 分布为 6×3-shot + 18×4-shot + 6×5-shot，生成后用 TransNetV2 校验
  "characters": [                   // 反复出现的角色，用于后续 T1/T2 编辑任务
    {"id": "C1", "desc": "young woman with long brown hair, wearing a red knit sweater"},
    {"id": "C2", "desc": "older man with short grey hair, wearing a navy blue shirt"}
  ],
  "key_objects": ["white ceramic coffee cup", "wooden kitchen counter"],  // 关键道具，用于 T4 编辑
  "caption": "[Wide shot, soft morning light through window] A young woman... [Medium close-up of her hands] She picks up... [Over-the-shoulder shot] An older man..."
}
```

**关键约定**：
- caption 用 `[shot tag] description.` 的格式，**每个 [.] 标签触发一次镜头切换**
- shot tag 推荐写法：`[Wide shot]` / `[Medium shot]` / `[Close-up]` / `[Over-the-shoulder shot]` / `[Low-angle shot]` / `[Tracking shot]` / `[POV shot]` 等。Seedance 会按这些 hint 切镜
- 角色描述要"identifiable"（颜色/发型/服装清晰），后续做编辑任务时角色 ID 才能 ArcFace / DINOv2 锚住
- 道具要明确，方便 T4 add/remove/replace

## 四、为什么用 frame number 而不是 time 来标 shot？

**简短答**：JSON 里只存 `duration_sec` + `fps` 让 Seedance 调用；生成后 **canonical shot annotation 用 frame index**，time 是 derived field。

**理由**：

| 维度 | Frame number | Time (秒) |
|---|---|---|
| 跨模型对齐（Seedance 24fps / Kling 30fps / Sora 混合） | ✅ 无歧义 | ❌ 4.5s 在不同 fps 下落到不同帧 |
| 下游工具兼容（TransNetV2 / PySceneDetect / SAM-2 / Grounding-DINO / CoTracker） | ✅ 全部原生 frame | ❌ 都要转 frame 才能用 |
| Edit mask 帧级对齐 | ✅ 帧精度 | ❌ 边界帧归属模糊 |
| CSEP 聚合（"applicable shots"） | ✅ 不引入舍入误差 | ❌ |
| API 调用（Seedance / Veo / Sora 的 `duration` 参数） | ❌ API 都用秒 | ✅ |
| 人类可读（论文配图 / prompt 注释） | ❌ "frame 108" 反人类 | ✅ "在第 4.5 秒" |
| 同行 benchmark（MovieBench / Cine250K / ShotWeaver40K / ShotBench） | ✅ 都用 frame | — |

**实操**：生成完每个视频后，跑一遍 TransNetV2，产出：

```jsonc
{
  "video_id": "00000",
  "fps": 24,
  "total_frames": 240,
  "shots": [
    {"shot_id": 1, "frame_start": 0,   "frame_end": 71,  "t_start": 0.000, "t_end": 2.958},
    {"shot_id": 2, "frame_start": 72,  "frame_end": 151, "t_start": 3.000, "t_end": 6.292},
    {"shot_id": 3, "frame_start": 152, "frame_end": 239, "t_start": 6.333, "t_end": 9.958}
  ]
}
```

frame 是 ground truth，time 是 `frame / fps` 算出来的展示字段。所有 metric、mask、entity track 都按 frame 索引。

## 五、"用 AI 生成源视频"的 tradeoff（必须 aware）

`RESEARCH_PLAN.md` §3.1 原本计划 Pexels + YouTube CC + 部分 SkyReels 合成。你现在选择**用 Seedance 全部合成**为加速 —— 这是合理 shortcut，但有以下需要在论文里 disclose 或 mitigate 的点：

| 风险 | 影响 | 缓解建议 |
|---|---|---|
| **领域偏移**：源视频全是 AI 生成 → benchmark 评估的是"在 AI 视频上编辑"而非"在真实视频上编辑" | 中。审稿人会问"你的指标在真实视频上是否成立" | (a) 留 ~20% 真实视频对照集（Pexels 30 段）做 robustness sanity check；(b) 在 Limitations 节明示 |
| **Seedance bias**：源视频带 Seedance 自身的视觉先验（颜色/构图/运动风格） | 中。可能 unfairly 偏向 Seedance 系产品（Seedance 编辑 Seedance 视频更容易） | 编辑 baseline 评测时**禁止用 Seedance 作为编辑器**（仅作源视频生成器），或者把 Seedance 作为编辑器的成绩单独标注 |
| **Shot 数不可控**：prompt 写 3 shots，模型可能出 2 或 4 | 中。可能要丢弃 / 重标一部分 | 生成后用 TransNetV2 自动校验，`actual_shots != expected_shots` 的视频按 actual 重标；如完全不切（出 1 shot），重生成 |
| **跨 shot 一致性"过强"**：Seedance 自身有 multi-shot 优化，跨 shot 角色一致性比真实素材好 | 低 | 这反而是好的——给编辑器一个干净起点，后续评测 "编辑是否破坏了原有一致性" 更敏感 |
| **License**：Volcengine ToS 允许商用但学术 redistribution 案例少 | 中 | 提前和 ByteDance Seed 法务确认是否允许把生成视频随 benchmark 发布；如不能，只发 hash + prompt |
| **复现性**：Seedance 模型版本会迭代（2.0 → 2.5 等） | 高 | 锁 `doubao-seedance-2-0-260128` 模型 ID；archive 所有生成视频到 HF / Zenodo |

**我的建议**：用 Seedance 生成主集（150 段）+ 配 30 段 Pexels 真实视频做 robustness 子集。论文 Experiments 节同时报两者，证明指标在真实和合成上都成立。这样既快又稳。

## 六、Pilot 步骤建议

1. **先跑 5 条**（`global_index` 0-4），验证：
   - Seedance 确实按 `[shot tag]` 切镜
   - 1080p / 10s 实际生成成本（fal 估 ~$2.50/视频，volcengine 可能更低）
   - 生成的视频质量是否够 benchmark 用
2. **跑 TransNetV2** 校验 `actual_shots == expected_shots` 的比例，<70% 的话需要调 prompt 风格
3. **如果 OK 再跑全部 30 条**，验证整体 workflow
4. **扩到 150 条**（手写或 LLM 扩展 + 人工 QA）→ 进入 Phase 1 正式数据
