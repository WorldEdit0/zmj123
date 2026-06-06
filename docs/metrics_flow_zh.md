# MSEdit-Bench 评测链路与指标计算图

这份文档是评测代码的阅读入口。建议先看本文件理解数据流，再进入对应源码文件看实现细节。

## 入口文件

```text
scripts/eval_suite.sh
  |
  |-- 普通任务 T1/T2/T3/T4/T6/T7
  |     -> python -m mseditbench.eval.run_eval
  |
  |-- 结构任务 T5
  |     -> python -m mseditbench.eval.t5_track
  |
  |-- 多 GPU 分片
  |     -> python -m mseditbench.eval.merge_shards
  |
  `-- 最终汇总
        -> python -m mseditbench.eval.summarize
```

对应文件：

- 启动脚本：`scripts/eval_suite.sh`
- 普通任务总入口：`mseditbench/eval/run_eval.py`
- T5 特殊入口：`mseditbench/eval/t5_track.py`
- 分片合并：`mseditbench/eval/merge_shards.py`
- 最终汇总：`mseditbench/eval/summarize.py`
- 后端加载：`mseditbench/metrics/backends.py`
- 切帧工具：`mseditbench/metrics/frame_io.py`

## 全局数据流

```text
prompt JSON
  |
  |  每条 sample 包含：
  |  source_video / shots / edit.instruction / target_phrase
  |  applicable_shots 等
  v
run_eval.py
  |
  |-- 读取 source video
  |-- 读取 edited video: {sample_id}.mp4 或 {sample_id}_k*.mp4
  |-- 按源视频 shot 边界抽帧
  v
{shot_id: frames[T,H,W,3]}
  |
  |-- PSQ     只看 edited frames
  |-- EE_v3   source/edit 对应帧对 -> Qwen3-VL 评分
  |-- NEP     局部任务 source/edit DINO 相似度，edit.mask_queries union mask 外区域
  |-- CSEP_v3 edited shot 两两比较 -> Qwen3-VL 一致性
  |-- SES     OffTarget + IDdrift
  v
{sample_id}_k{k}.eval.json
  |
  |-- 同一 prompt 的 K 个输出求均值
  v
{sample_id}.agg.json
  |
  |-- 同一任务内所有 prompt 等权平均
  v
aggregate.json
  |
  |-- 跨任务汇总
  v
summary.csv / summary.md
```

## NUM_SAMPLES 与 EE_V3_FRAME_PAIRS

```text
NUM_SAMPLES = K

prompt
  |
  |-- k0 edited video
  |-- k1 edited video
  `-- k2 edited video
       ...

每个 k 单独算指标，然后同一个 prompt 内对 K 个结果求 mean/std。
```

`NUM_SAMPLES=1`：只评测一个生成结果。代码会优先找 `{sample_id}.mp4`，找不到再找 `{sample_id}_k0.mp4`。

`NUM_SAMPLES=3`：评测 `{sample_id}_k0.mp4`、`{sample_id}_k1.mp4`、`{sample_id}_k2.mp4`，正式评测建议使用。

```text
EE_V3_FRAME_PAIRS = N

一个 applicable shot
  |
  |-- 从 source shot 抽 N 个相对时间点
  |-- 从 edited shot 抽相同 N 个相对时间点
  v
N 对 source/edit image pair
  |
  `-- 每对交给 Qwen3-VL 打 0-5 分
```

`EE_V3_FRAME_PAIRS=1`：只取 shot 中间帧，适合 smoke。

`EE_V3_FRAME_PAIRS=3`：取多个时间点，更稳，适合正式评测。

## PSQ

源码：`mseditbench/metrics/psq.py`

含义：Per-Shot Quality，只评价编辑后视频的视觉质量，不和源视频比较。

```text
edited video
  |
  v
按 shot 抽帧
  |
  v
每个 shot 的 frames
  |
  |-- MUSIQ(frames)       -> 0..100
  |-- LAION-Aes(frames)   -> 0..10
  v
shot_psq = 0.5 * (MUSIQ/100 + LAION_Aes/10)
  |
  v
PSQ = mean(所有 shot_psq)
```

返回 `None` 的情况：没有任何可评分 shot。

## EE_v3

源码：`mseditbench/metrics/ee_v3.py`

含义：Edit Effectiveness，判断目标编辑是否真的在 applicable shots 中完成。

```text
source per-shot frames          edited per-shot frames
          |                              |
          `------------+-----------------`
                       |
                       v
              只保留 applicable_shots
                       |
                       v
            对每个 shot 抽 N 个对应帧对
            N = EE_V3_FRAME_PAIRS
                       |
                       v
       Qwen3-VL 看 ORIGINAL image + EDITED image
                       |
                       v
             输出 0-5 整数，归一化到 0..1
                       |
                       v
          shot_ee = mean(该 shot 内所有帧对分)
                       |
                       v
              EE_v3 = mean(所有 shot_ee)
```

跳过情况：

- T5：shot 结构改变，不适合按源 shot 对齐算 EE。
- T7：转场类任务，不适合用“每个原始 shot 是否完成编辑”定义 EE。

返回 `None` 的情况：没有有效 applicable shot 或 source/edit 缺帧。

## NEP

源码：`mseditbench/metrics/nep.py`

含义：Non-Edit Preservation，衡量非编辑区域是否保持。

```text
source per-shot frames          edited per-shot frames
          |                              |
          |                              |
          +------ edit.mask_queries ------+
          | source_queries / edited_queries
          |                              |
          v                              v
SAM3 分别在 source / edited 查询目标区域
取 source mask 与 edited mask 的 union 外区域
          |
          v
DINOv2 embed source frames -> shot source embedding
DINOv2 embed edited frames -> shot edited embedding
          |
          v
shot_nep = cosine(source_embedding, edited_embedding)
          |
          v
NEP = mean(所有可评分 shot_nep)
```

注意：

- SAM3 mask 当前只用于 NEP 的非编辑区域比较。
- NEP 只对局部编辑任务启用；T3/T5/T6/T7 这类全局、结构或转场任务返回 `None`。
- 对局部任务，mask miss 的 shot 会跳过，不再退回整帧 NEP；miss 细节记录在 `extra.mask_hits`。
- T4 的 anchor 只表示空间关系，不再作为 NEP 的编辑区域 mask query。

## CSEP_v3

源码：`mseditbench/metrics/csep_v3.py`

含义：Cross-Shot Edit Consistency，衡量多个 applicable shots 中编辑结果是否一致。

```text
edited per-shot frames
  |
  v
只保留 applicable_shots
  |
  v
所有 shot 两两组合
  |
  v
Qwen3-VL 比较 edited shot A 和 edited shot B
  |
  v
pair_score = 0..1
  |
  v
consistency = mean(所有 pair_score)

EE_v3 per-shot 分数
  |
  v
coverage = mean(所有 applicable shot 的 ee_v3)

最终：
CSEP_v3 = sqrt(coverage * consistency)
```

为什么要乘 coverage：

```text
如果所有 shot 都没编辑：
  edited shots 可能很一致
  consistency 高
  但 EE_v3 低 -> coverage 低
  所以 CSEP_v3 仍然低
```

返回 `None` 的情况：有效 applicable shots 少于 2 个，无法定义跨 shot 一致性。

## SES

源码：`mseditbench/metrics/ses.py`，ID drift 在 `mseditbench/eval/run_eval.py`

含义：Side-Effect Score，衡量不该被改的东西有没有被破坏。

SES 由两部分副作用组成：

```text
IDdrift
  |
  |-- 每个 shot 取 source 中间帧最大人脸
  |-- 每个 shot 取 edited 中间帧最大人脸
  |-- InsightFace embedding
  |-- drift = 1 - cosine(source_face, edited_face)
  v
id_drift = mean(所有可检测 face 的 drift)
```

```text
OffTarget
  |
  |-- absent_shots = 不应该出现目标编辑的 shots
  |-- CLIP(source shot, target_phrase)
  |-- CLIP(edited shot, target_phrase)
  |-- delta = max(0, edited_score - source_score - tau)
  v
off_target_mean = mean(所有 absent shot delta)
```

最终：

```text
worst = max(id_drift, off_target_mean)
SES = 1 - worst
裁剪到 [0,1]
```

特殊情况：

- T1 是主动替换人物身份，IDdrift 不参与 SES，只用 OffTarget。
- 如果没有可检测人脸，`id_drift=None`，SES 只看 OffTarget。

## TSF

源码：`mseditbench/eval/t5_track.py`

含义：T5 Structural Fidelity，用于只包含 reorder 的镜头顺序任务。

T5 不走普通 `run_eval.py`，因为它改变 shot 结构，源视频 shot 边界不再能对齐 edited video。

```text
T5 instruction
  |
  v
读取 edit.extra.new_order
```

```text
source shots middle frames -> DINO embeddings
edited shots middle frames -> DINO embeddings
  |
  v
对每个期望位置 i：
  edited shot i 对齐 source shot new_order[i]
  |
  v
content_alignment = mean(cosine)
```

最终：

```text
TSF = content_alignment
```

注意：T5 现在没有 insert/delete，shot 数不再作为单独指标奖励或惩罚。输出 JSON 仍记录 `edit_shot_count` 便于排查，但聚合只看 `tsf_mean` / `content_alignment_mean`。

## 聚合逻辑

源码：

- K 内聚合和任务聚合：`mseditbench/eval/run_eval.py`
- T5 聚合：`mseditbench/eval/t5_track.py`
- 分片合并：`mseditbench/eval/merge_shards.py`
- 最终表格：`mseditbench/eval/summarize.py`

```text
单个 k 输出：
  {sample_id}_k{k}.eval.json
       |
       v
同一个 prompt 的 K 个输出：
  {sample_id}.agg.json
  metric_mean = mean(非 None 的 k 分数)
       |
       v
同一任务所有 prompts：
  aggregate.json
  metric_mean = mean(所有 prompt-level metric_mean)
       |
       v
summary.csv / summary.md
```

`None` 的含义：

```text
None = 不可评估 / 被任务规则跳过
不是 0 分
聚合时跳过 None
```

## task_score 规则

源码：`mseditbench/eval/summarize.py`

```text
默认任务：
task_score = mean(PSQ, EE_v3, NEP, CSEP_v3, SES 中非 None 的项)

T5：
task_score = TSF
```

注意：`task_score` 是快速比较用的单数汇总，不应替代每个指标的逐列分析。
