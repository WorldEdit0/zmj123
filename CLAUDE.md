# MSEdit-Bench — Project Context for Claude Code

> **如果你是刚 SSH 到服务器、第一次打开这个项目的 Claude Code，先读完这份文档再做事。**
> 这份文档承载了从 2026-05-19 本地开发阶段沉淀下来的全部决策、文件路径、约定、未决问题。本地 `~/.claude/projects/` 下的 memory 不会随仓库迁移，所以信息在这里。
>
> **三个文档的分工**：
> - **`README.md`** — 对外（GitHub）展示的项目入口；任务定义 + 用法 + Pro/Fast 参照表 + 路线图
> - **`HOWTO.md`** — 详细的 pipeline 命令手册（v1.2 路径，**待更新到 v3**）
> - **`CLAUDE.md`** — 本文档：内部 scope 决策 / 进度 / 未决问题 / 跨 session handoff
>
> 三者互相补充：README 给外人看，HOWTO 给跑 pipeline 的人看，CLAUDE.md 给下次接手的 Claude 看。

最后更新：2026-06-08（T4 dynamic-delete pruning）

---

## 0. 当前 release 状态（每次 session 开头先看这里）

### v1 已就绪 ★ — 准备 push GitHub
- 数据：30 个 10s 多镜头源视频 + 480 条手写 edit prompts（T1-T8 各 60）
- 2026-06-07 任务重构：T1=30 动态替换 + 30 静态替换；T4=static add / static delete / dynamic add 各 20，不做 dynamic delete；T3=纯 style（像素、新海诚、宫崎骏、JoJo、赛博朋克、水墨、油画、美式漫画、3D 写实动画、粘土定格动画等明确大类）；T7=纯 lighting
- 2026-06-08 prompt boundary QA：T1 的 30 条 static replacement 已改成跨物体类别替换（不是杯子换材质/颜色这类浅层变体）；T2 不再使用 `accessory` / `clothing_type` 作为属性类别，保留同一物体的颜色、材质、图案、质感、发型/毛发长度等显著属性变化；T7 已换成月光、黄昏、霓虹、聚光、手电筒、火光、频闪、黑光、警灯/荧光等高辨识光源，并压缩 instruction。
- 2026-06-08 second pass：T1 dynamic 已逐条手审为人物/动物个体级替换（性别、年龄、族裔、职业身份或机器人等主体变化），不再把同一人物的表面属性变化当 replacement；T1 static 已手写收紧为“类别不同但功能兼容”的替换，必须继续承接原动作/叙事；T2 的 `target_phrase` 已清成 edited attribute phrase，不再混入 old+new 对照。T5/T6 本轮未改。
- 2026-06-08 T4 pruning：删除 20 条 dynamic delete prompts，原因是删除人物/动物主体容易破坏后续剧情动作；T4 现在为 60 条，分布为 static add=20、static delete=20、dynamic add=20。
- 同步文件：`runs/edit_prompts_v2_10s/T1.json`、`T2.json`、`T4.json`、`T7.json` 和 `all_edit_handoff.json`；外部 handoff 当前为 480 条。本轮实际改动集中在 T4 和 handoff 同步。
- 2026-06-07 新增 T8：Global Background Replacement，替换背景但保留前景主体/主要人物/关键物体；T8 的 `mask_queries.score_region="mask"`，NEP 直接在前景 preserve mask 内算 DINOv2
- T5 当前只保留 reorder；不再单独走 TSF，统一进入 `run_eval.py`，TAC 会按 `extra.new_order` 重建期望时间线
- 评测：当前 headline metrics = PSQ / EE_v3 / CSEP_v3 / NEP / USP / TAC；SES/TSF 已退役
- 参照 baseline：Seedance 2.0 Pro & Fast 全 6 任务 K=3 数字已出，但这些结果对应 2026-06-07 前的 420-prompt snapshot；新 480-prompt 任务集需要重新跑编辑和评测
- 文档：README.md、CLAUDE.md、HOWTO.md、4 份 design docs (DEEP_DIVE / RESEARCH_PLAN / SURVEY / RELATED_WORK)、AGENT_BENCH_DESIGN.md
- 测试：`python3 -m mseditbench.tests.test_metrics` → 17/17 PASS

### 2026-06-07 T8 背景替换记录
- 新增 `runs/edit_prompts_v2_10s/T8.json`：60 条手写背景替换 prompt，每个 10s 源视频 2 条；后续 T4 dynamic-delete pruning 后，`all_edit_handoff.json` 当前为 480 条。
- T8 schema：`task_id="T8"`，`edit_scope="global_background"`，`edit_type="background_replace"`，`extra.new_background/old_background/preserve_queries` 明确记录目标背景和前景保留对象。
- T8 NEP：`mask_queries.source_queries == edited_queries == preserve_queries`，并设置 `score_region="mask"`；`run_eval.py` 会把它映射成 `mask_mode="inside"`，因此 NEP 在前景 mask 内算 DINOv2，而不是像 T1/T2/T4 那样算 mask 外。
- 相关入口已同步：`tasks.py`/`banks.py`/`generate.py`、`run_eval_parallel.sh`、`eval_suite.sh`、`recompute_usp_parallel.sh`、README/README_zh/PROJECT_ONBOARDING/docs。
- 已验证：T8 JSON 60 条 / 30 视频 / 每视频 2 条 / 60 个 unique new_background；`all_edit_handoff.json` 当前 480 条；`compileall` 通过；metric tests 17/17；T8 单样本 mock `run_eval.py` smoke 通过且 `nep_mask_mode="inside"`。

### 2026-06-07 T5 JSON 清理记录
- T5 最终生产文件固定为 `runs/edit_prompts_v2_10s/T5.json`；pipeline、handoff 和文档均只引用这个标准路径。
- 已按用户要求把原 `T5_new.json` 的场景化 rewrite 内容恢复为最终 `T5.json`，并同步 `all_edit_handoff.json` 的 60 条 T5 prompt。
- 已删除重复变体 `T5_1.json`；`T5_new.json` 不再单独保留，避免生产目录出现多个 T5 入口。
- `T5.json` 保留 60 条场景化 reorder，并显式设置 `mask_queries.nep_applicable=false`，避免新 NEP fallback 把 shot-reorder 当成 spatial local edit。

### 2026-06-07 指标重写记录
- **SES 删除并更名为 USP**：去掉 face/ArcFace ID 识别和 CLIP-T off-target，只保留未被编辑 shot 的 DINOv2 内容相似度；如果所有 shot 都被编辑，USP 返回 `None`。
- **TSF 删除**：T5 不再走 `mseditbench/eval/t5_track.py`；T5 通过统一 `run_eval.py` 评测，结构保持由 TAC 覆盖。
- **新增 TAC**：用 OmniShotCut 检测 edited video shot 边界；先检查 expected/edited shot 数是否一致，不一致给 0；一致时按 start/end 时间锚点漂移除以原 shot 时长扣分。
- **入口/脚本同步**：`run_eval.py`、`merge_shards.py`、`summarize.py`、`leaderboard.py`、`run_eval_parallel.sh`、`eval_suite.sh` 都已切到 USP/TAC；`recompute_ses.py`/`t5_track.py` 删除，新增 `recompute_usp.py` 和 `scripts/recompute_usp_parallel.sh`。

### v2 = agent 方向（**用户后续在另一个目录做**）
- 设计文档已写：`AGENT_BENCH_DESIGN.md`（715 行）
- 复用 v1 的 30 视频 + 480 prompts + v3 metrics
- 新增 T9-T11 复合任务 + trajectory metrics + agent baselines
- ⚠️ **v1 这个目录冻结**作为 stable benchmark；agent 方向在新目录开（避免污染 v1）

---

## 1. TL;DR — 这是什么项目

**MSEdit-Bench**（工作标题）：首个针对 multi-shot 视频 **编辑** 的评测基准，投 AAAI 2027。

- **核心任务**：在 multi-shot 源视频上给出 7 类编辑指令；评测商用编辑 API、开源编辑 baseline 和 agentic baseline 的表现
- **生成轨副榜**：同一套 prompt 去掉 source video → 评测 8 个商用 + 5 个开源生成器
- **核心指标**：PSQ / EE_v3 / CSEP_v3 / NEP / USP / TAC
- **关键差异化**：现有 multi-shot bench 全是 gen-only（MovieBench / MSVBench / EntityBench / Cine250K / ShotWeaver40K 等 15+ 个）；现有 video edit bench 全是 single-clip；唯一交集 UniVBench 只有 ~50 multi-shot edit 例。这是 pre-VBench 时刻

完整设计见 `DEEP_DIVE.md` §1-7、`RESEARCH_PLAN.md` 全文。

---

## 2. 当前状态（2026-05-22）

### 已完成
- 三份调研文档已写：`SURVEY_REPORT.md` / `RELATED_WORK_SURVEY.md` / `DEEP_DIVE.md`
- 研究计划已定：`RESEARCH_PLAN.md`（18 周时间表 / 8 个 task / 全部 metric 公式 / baseline 名单 / 预算 $35-65K）
- **30 条 multi-shot 源视频**：caption 用统一 `[scale, angle/movement]` 全小写客观格式（`seedance_api_example/source_prompts_multishot_v1.json`）
- **30 条源视频**最终落地在 **`/mnt/hdfs/xjy_hldy/datasets/multi_shot_bench/data/source_videos/`**：
  - `videos/` — 30 个 mp4，**全部 3.5-11.6 MB**（远低于 50MB API 限制）
  - `success_csv/` — TOS URL（按字典序合并：`all_seedance_*` < `retry_seedance_*` < `zz_loopmatch_*`，新覆盖旧）
  - `inference_csv/` — Seedance API 调用 log
- **Source 生成已加 size guard**：`infer_v2_mutilshot_source.py` 现在每 sample 最多调 3 次 API + inline 下载查 size，>50MB 则 retry，避免 v2v API 对大文件拒服务的问题
- **Shot detection: 30/30 (100%)** —— `runs/pilot_v5_final/`，0 off-by-one，0 错误。SAFE TO SCALE
- **★ Shot detector 升级到 OmniShotCut**（UVA CV Lab, arXiv:2604.24762）：
  - ckpt: `/mnt/hdfs/xjy_hldy/ckpt/OmniShotCut/OmniShotCut_ckpt.pth`
  - repo: `/mnt/hdfs/xjy_hldy/projects/OmniShotCut`
  - 新模块 `mseditbench/preprocess/omnishot_backend.py` 加载 + 推理（首次 lazy load，全局 cache）
  - `shot_detect.py` 优先级改为 **OmniShot > TransNetV2 > PySceneDetect**；输出 JSON 加 `omnishotcut` block + `consensus_backend` 字段
  - **OmniShot 比 TN/PS 准** —— 在我们 30 条上发现 3 个 case TN+PS 一致看错（漏切 / 过分切），OmniShot 检出真实切镜，迫使 retry 到所有 detector 都同意
- **整套 mseditbench Python 包已搭好**（40+ 文件 / ~4000 行 / 17 个 metric unit test 全过）：
  - `preprocess/` shot_detect / contact_sheet / pilot_report / `loop_until_match.py` / **`omnishot_backend.py`**
  - `tracking/` Grounded-DINO + SAM-2-Video（mock + real）
  - `identity/` InsightFace + 单链聚类
  - `edit_prompts/` T1-T8 templates / banks / **3 个版本生成器**（v1=template, v1.1=Seed Lite rewrite, v1.2=Claude handwritten）
  - `metrics/` PSQ / EE / NEP / CSEP / USP / TAC / CXS-ID + ACP-floor，全部带公式 docstring
  - `baselines/` editor 接口 + Aleph client + Snapshot Protocol
  - `eval/` orchestrator + leaderboard CSV，**支持 K-sample 聚合（mean ± std）**
  - `tests/` 15 个合成数据 metric 测试
- **真 VLM 后端**：Seed 2.0 Lite (`doubao-seed-2-0-lite-260428`) via Volcengine Ark，端到端跑通 EE。API key 在 `/mnt/hdfs/xjy_hldy/projects/emnlp_bench/pyscripts/run_rewrite_baseline_seed.py`
- **3 版 edit prompts × 536 条**：
  - `runs/edit_prompts_v1/` 模板生成（含 "hair hair" 等 bug，**不能用**）
  - `runs/edit_prompts_v1.1/` Seed Lite 改写版（语法干净但 91/304 T1-T4 加了不必要的 shot 列表）
  - `runs/edit_prompts_v1.2/` ⭐ **Claude 手写版（生产用），0 bugs，scene-aware，最适合 v2v editor**
  - 3-way LLM judge 做过（`runs/eval_3way/`）：v1=35, v1.1=419, v1.2=82 wins。但 judge 测的是「完整度」，对 v2v 不利 → 用 v1.2
- **K=3 协议已 wired**（RESEARCH_PLAN §5 要求）：
  - `infer_v2_mutilshot_edit.py` 加 `--num_samples` 参数，每 prompt 调 3 次 API，输出 `{sample_id}_k{0,1,2}.mp4`
  - `eval/run_eval.py` 加 `--num_samples`，分 K 打分 → 每 prompt mean/std → 跨 prompt mean/std
  - `edit_all.sh` / `edit.sh` 默认 `NUM_SAMPLES=3`
- **Seedance v2v edit baseline 已跑完**：
  - 1606/1608 编辑视频成功（99.88%）。2 个 sample（00020_T4_0033_k0、00025_T5_0050_k2）Seedance API 主动拒；所有 prompt 都有 ≥2 个 K 样本，K=3 mean±std 协议仍可用
  - 输出在 `runs/seedance_v2v_edit/{videos,inference_csv,download_success_csv}/{T1..T8}/`，文件名 `{sample_id}_k{0,1,2}.mp4`
- **真后端全部接好（2026-05-22）**，全部已验证 + 在 metric eval 用：
  - **CLIP**：OpenAI `clip` 包（HF 速度太慢、azure CDN 9.5MB/s 直下）。本地权重 `/tmp/clipdl/clip_vitb32.pt`（355 MB）。`backends.py:_make_real_clip` 优先 OpenAI 包，SigLIP 仍走 open_clip
  - **DINOv2-S**：timm 加载 + Meta CDN 直下（GitHub torch.hub 触发 rate limit 用不了）。本地权重 `/tmp/dinov2/dinov2_vits14.pth`（88 MB）。注意 timm 的 DINOv2 需要 **518×518** 输入，已修
  - **Seed VLM**：Lite 260428 (`doubao-seed-2-0-lite-260215` model id)。**429 backoff 加猛**（普通 4s × 2^attempt；rate-limit 30+15·attempt s；retries 3→8）。`SEED_VLM_MIN_INTERVAL_SEC` env var 可调节 throttle
- **Eval 性能优化（2026-05-22）**：
  - CLIP `score_video_text` 从 list-comp per-frame batch=1 → 全 frames 一次 GPU forward（~6× 加速）
  - VLM 调用并行化：`M.ee()` 和 `M.dps()` 用 ThreadPoolExecutor 同时发 3 VLM × N shots 全部调用（max_workers=9-12）
  - Source frames 缓存：同一 prompt 的 K=3 样本不再重复读 HDFS 源视频
  - VLM frames 数减少 4→2，max_side 512→384（每次调用 token 量减半，少撞 TPM）
  - 实测稳态 **~47 秒/prompt**（GPU 100%，VLM TPM 是新瓶颈）
- **★ T1 metric eval 已完成（pilot_v5 snapshot）**：
  - 输出 `runs/eval_seedance_v2v/T1/`（82 prompts × K=3 = 246 个 .eval.json + 82 个 .agg.json + 1 个 aggregate.json）
  - **首行真实 leaderboard 数据**：
    ```
    Seedance v2v on T1 (character replacement)
      PSQ    0.649 ±0.016
      EE     0.323 ±0.268    32% applicable shots 编辑生效
      NEP    0.737 ±0.137
      CSEP   0.562 ±0.293
      SES    1.000 ±0.000    无 off-target leakage
    ```
  - 64 分钟跑完
- **T2 部分跑完（41/82）后被中止**（用户要求停手）。剩 T2 后半 + T3-T8 待续
- **★ T1-T8 全 leaderboard 已出（Seedance 2.0 Pro v2v, 2026-05-22）**——首张 MSEdit-Bench 真实数据表：
    ```
    Task     PSQ            EE              NEP            CSEP           SES            DPS
    T1 char    0.649 ±0.016   0.323 ±0.268    0.737 ±0.137   0.562 ±0.293   1.000 ±0.000   —
    T2 attr    0.651 ±0.018   0.126 ±0.188    0.944 ±0.043   0.273 ±0.250   0.771 ±0.111   —
    T3 style   0.649 ±0.016   0.159 ±0.272    0.883 ±0.153   0.414 ±0.372   0.737 ±0.207   —
    T4 obj     0.651 ±0.022   0.028 ±0.063    0.922 ±0.074   0.108 ±0.132   0.866 ±0.081   —
    T5 struct* 0.648 ±0.017   0.124 ±0.177    0.767 ±0.234   0.192 ±0.209   0.788 ±0.152   —
    T6 cam     0.650 ±0.015   0.022 ±0.084    0.639 ±0.189   —              0.696 ±0.212   —
    T7 trans   0.650 ±0.017   0.000 ±0.000    0.969 ±0.041   0.016 ±0.045   0.855 ±0.091   —
    T8 dieg    0.648 ±0.016   0.018 ±0.087    0.950 ±0.050   0.231 ±0.236   0.805 ±0.109   0.627 ±0.202
    ```
    *T5 = Shot Insert/Delete/Reorder. EE/NEP/CSEP 用 source shot boundaries 切 edit 帧→编辑后镜头结构变了就错位。这些数字基本是噪声；T5 单独走 structural fidelity 轨道（见 §2 末尾）
  - 关键观察：PSQ ~0.65 全任务一致（无伪影）；EE 极低，T1 char-replace (32%) > T3 style-rerender (16%) >> T7 transition (0%) — Seedance v2v 几乎做不到结构性编辑；T1 CSEP 0.56 最高 = 角色替换能跨 shot 传播，T7 0.02 = 改不动；SES ≈ 1.0 几乎无 off-target leak；T8 DPS 0.627 比随机好但远没"理解"diegetic propagation
  - 8-GPU 并行 5× 加速：原 sequential 64 min/task → 现 12 min/task；T2-T8 总耗时 ~56 min
  - 输出在 `runs/eval_seedance_v2v/{T1..T8}/aggregate.json`
- **★ Seedance 2.0 Fast v2v 全 leaderboard 已出（2026-05-23）**——同一 K=3 协议跑了第二个变体作为 Pro 的 compute-trade-off reference：
    ```
    Task     PSQ            EE              NEP            CSEP           SES            DPS
    T1 char    0.647 ±0.017   0.304 ±0.245    0.755 ±0.136   0.627 ±0.258   1.000 ±0.000   —
    T2 attr    0.652 ±0.019   0.116 ±0.178    0.972 ±0.019   0.258 ±0.263   0.795 ±0.093   —
    T3 style   0.649 ±0.018   0.160 ±0.266    0.915 ±0.132   0.422 ±0.352   0.705 ±0.231   —
    T4 obj     0.650 ±0.018   0.045 ±0.088    0.926 ±0.080   0.145 ±0.166   0.860 ±0.076   —
    T5 struct* 0.651 ±0.020   0.133 ±0.191    0.794 ±0.236   0.196 ±0.209   0.789 ±0.164   —
    T6 cam     0.646 ±0.018   0.028 ±0.093    0.672 ±0.185   —              0.720 ±0.189   —
    T7 trans   0.648 ±0.018   0.000 ±0.000    0.982 ±0.023   0.028 ±0.055   0.856 ±0.076   —
    T8 dieg    0.648 ±0.016   0.010 ±0.066    0.978 ±0.017   0.216 ±0.241   0.801 ±0.108   0.597 ±0.220
    ```
  - 模型 `doubao-seedance-2-0-fast-260128`，单 sample API ~4m24s（Pro ~7.5min，~40% 加速）
  - **Pro vs Fast 对比**：EE 总体相当（Pro T1 0.323 / Fast 0.304；T8 Pro 0.018 / Fast 0.010）；NEP Fast 略高（preserves more, less destructive）；T1 CSEP Fast 0.627 比 Pro 0.562 反而高；T8 DPS Pro 0.627 > Fast 0.597（Pro 略懂 diegetic）。**结论**：Fast 与 Pro 编辑能力差距极小，Pro 的额外 40% 算力主要换 marginally better diegetic + slightly stronger structural edits。两个都标 † 不进 headline (CLAUDE.md §3)
  - 源视频走 ModelScope 公网镜像 `https://modelscope.cn/datasets/inLine013/videobed/resolve/master/{video_name}` —— 无 24h TTL，比 TOS pre-signed URL 省心
  - 输出在 `runs/eval_seedance_v2v_fast/{T1..T8}/aggregate.json`，编辑视频在 `runs/seedance_v2v_fast_edit/videos/{T1..T8}/`
- **★ 真 PSQ 接好（pyiqa MUSIQ + LAION-Aes，2026-05-23）**：之前的 PSQ 是 hash mock，0.65 是噪声完全无意义。装 `pyiqa`，加 `_make_pyiqa_psq()` 后端，`get_psq("pyiqa")` 调度。weights 自动从 HF 下载（musiq-koniq + laion_aes），共 ~1GB，存 `~/.cache/torch/hub/pyiqa/`。`run_eval.py` 加 `--backend_psq pyiqa` flag。**记得真 PSQ 是 0.55-0.59 这个量级**，不是 mock 的 0.65
- **★ Mask-aware metric eval (SAM-3, 2026-05-24)**：发现严重 bug——`run_eval.py` 调用 `nep/ee/csep/off_target` 时**完全没传 mask**，metric 公式里写的「编辑区域之外算 DINO 保留度」「编辑区域之内算 CLIP-T 提升」全部退化成「整帧」。这直接导致 NEP **奖励"啥也没改"**，当时 Pro NEP 0.737 vs Fast 0.760 那种反常结果就是这个。修复：
  - 用本地 SAM-3 (`/mnt/hdfs/xjy_hldy/ckpt/sam3/sam3.pt` + `/mnt/hdfs/xjy_hldy/projects/sam3/`) 作 mask backend。SAM-3 = 「Segment Anything with Concepts」，文本 prompt → 实例 mask，无需独立 detector。0.76s/frame on H800
  - `mseditbench/metrics/backends.py` 加 `_make_sam3_mask()` 和 `get_mask("sam3")`
  - `run_eval.py` 的 `score_one()` 加 `mask_backend` 参数：每 shot 用中间帧作 anchor，跑 SAM-3(target_phrase) → 2D mask → 同一 mask 给到 source/edit (空间对齐)，传进 NEP/EE/CSEP
  - `--backend_mask sam3 --backend_psq pyiqa` 是 paper-quality 跑法
  - 8-GPU 并行单 baseline ~ 100 min（Pro+Fast 共 ~3h）。score_threshold 0.3，低分 mask 退化到空（fall through）
  - **首张 mask-aware 真 leaderboard（2026-05-24）**：
    - Pro: `runs/eval_seedance_v2v_masked/{T1..T8}/aggregate.json`
    - Fast: `runs/eval_seedance_v2v_fast_masked/{T1..T8}/aggregate.json`
    ```
    Mean over 8 tasks    Pro      Fast      Δ(F-P)   Winner
    PSQ                  0.582    0.563     -0.019   Pro 全胜 8/8
    EE                   0.048    0.045     -0.003   ≈持平
    NEP                  0.880    0.905     +0.025   Fast 全胜 8/8
    CSEP                 0.056    0.051     -0.005   Pro 微胜
    SES                  0.999    0.999     ~0       持平
    DPS (T8)             0.629    0.598     -0.031   Pro
    ```
  - **解读**：Pro 在视觉质量 (PSQ)、跨镜头一致性 (CSEP)、diegetic 理解 (DPS) 上都赢；Fast 在 NEP 上赢，因为 Fast 更保守，全局变更小。Pro 的额外算力**确实在做更深的编辑（包括有意的和无意的全局副作用）**。这是真实的能力—保守度 trade-off，不是 bug
  - **EE 数字下来一截**（Pro 旧 0.119 → 新 0.048）。这是 mask 让 EE 门槛更严：mask 内的 CLIP-T 提升要超 τ_ee=0.05 + VLM unanimous，对于 SAM-3 没找到 target 的 shot 自动判 0。这个版本更"诚实"，paper 用
- **★ IDdrift 接通（2026-05-25）**：之前 `run_eval.py:97` 硬编码 `id_drift=None`，SES 实际上只有 `1 - OffTarget` 一支在工作；身份漂移完全没测。修复 + 全量重跑：
  - 加 `_compute_id_drift()` to `run_eval.py`：每 shot 取中间帧 → InsightFace 检脸 → 取最大脸 → 512-d L2-normed embedding → 源 vs 编辑 cosine distance → mean over shots
  - 仅在 task ∉ {T1} 上算（T1 = Cross-Shot Character Replacement 本来就要换人）。T3 不改身份，重度风格化下脸 embedding 漂移是真实信号
  - `--backend_face insightface` 在 `run_eval_parallel.sh` 里设为生产默认；mock 时跳过
  - 装 `insightface` + `onnxruntime-gpu`（CUDA 12 ORT 暂时跑 CPU，~0.4s/frame）
  - **不重跑全 eval，只用 `recompute_ses.py` 单点修复**：保留 PSQ/EE/NEP/CSEP/DPS 不动，只对每个 .eval.json 加跑 face detection → 更新 `id_drift` + `ses = 1 − max(IDdrift, OffTarget)`
  - 14 进程并行（Pro/Fast × T2-T8）跑 ~2.5h
  - **真实 SES 数字（2026-05-25 重跑）已替换 `runs/eval_seedance_v2v_masked` + `_fast_masked` 里的 SES 列**。新 leaderboard 见上面两张表
  - **每任务平均 IDdrift（Pro / Fast，越低越好）**：
    ```
    T2 attr   0.234 / 0.207     T6 cam    0.387 / 0.341  ← 最高，相机移动伴大量重渲染
    T3 style  0.275 / 0.295     T7 trans  0.146 / 0.144  ← 最低，转场基本不动主体
    T4 obj    0.135 / 0.140     T8 dieg   0.197 / 0.200
    T5 struct 0.227 / 0.229
    ```
  - **观察**：T6 (camera move) IDdrift 最高 0.36-0.39 → 镜头改+身份漂浮的 trade-off 显示出来；T3 (style) 0.28-0.30 → 重度风格化（cyberpunk / VHS）确实让 ArcFace 看不清同一个人；T7 (transition) 最低 ~0.14 → 转场操作基本不动主体；T4 (object add) 也低 0.14 → 加物体不影响人脸最一致
  - 文件：`mseditbench/eval/run_eval.py:_compute_id_drift / _largest_face_embedding`、`mseditbench/eval/recompute_ses.py`、`scripts/recompute_ses_parallel.sh`
- **★ 生产默认 backend（2026-05-25）**：`scripts/run_eval_parallel.sh` 现在默认 `BACKEND_MASK=sam3 BACKEND_PSQ=pyiqa BACKEND_FACE=insightface`。之前要手动 export，现在直接 `bash run_eval_parallel.sh T1 T2 ...` 就是 paper-quality 跑法
- **★ install.sh 写好（2026-05-25）**：从 0 配置一台机器到能跑完整 pipeline 的脚本。装 Python 包 + pre-fetch CLIP/DINOv2/SAM-3/InsightFace/MUSIQ/LAION 全部 weights + 单元测试 + 1-prompt 真后端 smoke。详见 `install.sh` 顶部 docstring
- **★ T5 单独 track + 任务标签纠错（2026-05-25）**：审计发现两个 bug：
  1. **Leaderboard 任务名几次都写错了**。当时的 canonical（2026-05-25，已被 2026-06-07 新任务表替换；当前见 §4.4）：T1=Char Replace / T2=Attribute / T3=Style+Lighting / T4=Object / **T5=Shot Insert/Delete/Reorder** / T6=Cinematic Re-shoot (camera) / T7=Transition / T8=Diegetic。之前误写 T5=action / T6=style / T7=cam 等
  2. **T5 的 EE/NEP/CSEP 数字基本是噪声**：per-shot frame extraction 用源视频的 shot 边界切编辑后视频。T5 操作（swap/insert/delete/reorder）改变了 shot 结构 → 边界对不上 → 拿到的是错位的内容。CLAUDE 之前 leaderboard 那行 T5 的数字读不出有意义信号
  - **解决**：写 `mseditbench/eval/t5_track.py`，T5 单独走 **TSF (T5 Structural Fidelity)** 指标轨：
    - `count_correct ∈ {0,1}`：编辑后用 OmniShotCut 检 shot 数，看是否等于预期（insert: src+1, delete: src-1, swap/reorder: src）
    - `content_alignment ∈ [0,1]`：每个 edit shot 的 mid-frame 用 DINOv2 embed，跟所有 source shots 比 max cos sim，再求平均
    - **TSF = 0.5 × count_correct + 0.5 × content_alignment**
    - Op 分类 regex：60 prompts → 29 insert / 18 delete / 8 swap / 5 reorder
  - **T5 track 真实 leaderboard（2026-05-25）**：
    ```
    Baseline           TSF             count_correct  content_align
    Seedance Pro       0.536 ±0.199    0.294          0.778
    Seedance Fast      0.543 ±0.226    0.300          0.786

    By op (Pro / Fast TSF):
      insert    n=29   0.429 ±0.125  /  0.440 ±0.161
      delete    n=18   0.503 ±0.103  /  0.488 ±0.133
      swap      n= 8   0.855 ±0.191  /  0.856 ±0.174
      reorder   n= 5   0.770 ±0.074  /  0.841 ±0.222
    ```
  - **Pro vs Fast 在 T5 上打平**——T5 的算力差距优势消失，两个都做不到改 shot 数。Swap/reorder 高分是因为它们**不需要**改 shot 数（保留 source 内容即可）；insert/delete 低分是 ground truth 难做
  - 输出：`runs/eval_t5_track/{seedance_v2v,seedance_v2v_fast}/aggregate.json`
- **IDdrift skip 列表纠错（2026-05-25）**：原来 `_IDENTITY_CHANGING_TASKS = {"T1", "T3"}`。T1=Character Replace 该跳；T3=Style 不改身份不该跳，改成 `{"T1"}`。下次 SES 重跑 T3 会有 IDdrift 信号
- **GPU zhanka 协议**：用户自定义的占卡 yaml，跑 GPU 前 `cp /mnt/hdfs/xjy_hldy/zhanka_50.yaml ~/zhanka.yaml`（让出资源），跑完后 `cp /mnt/hdfs/xjy_hldy/zhanka_4096.yaml ~/zhanka.yaml`（重新占满防止他人 squat）。**违反这个协议是会被骂的**。**注**：用户在 2026-05-23 后明确说「后面运行不需要改 zhanka.yaml 了」，目前默认就保持 4096 不动；除非用户再要求否则别动它

- **★ VACE 14B 开源 baseline 配置完成（2026-05-26）**：第一个非 Seedance 的开源 editor baseline 接好了。Wan2.1-VACE-14B (Tongyi Lab, ICCV 2025, Apache-2.0)。设置过程踩坑很多，记下来：
  - **VACE 仓库**：`/mnt/hdfs/xjy_hldy/projects/VACE`（已 `pip install -e .`）。整个 stack：preprocess (depth/salient/sam2/gdino) → DiT (Wan2.1 14B 主干) → VAE decode
  - **Weights 全部走 ModelScope，不走 HF**（HF 极慢，ModelScope 9-10 MB/s）：
    - 用户已下载 `Wan2.1-VACE-14B` 到 `/mnt/hdfs/xjy_hldy/ckpt/Wan2.1-VACE-14B/`（70GB，含 7-shard safetensors + T5 + VAE）
    - 用户已下载 `Wan2.1-VACE-1.3B` 到 `/mnt/hdfs/xjy_hldy/ckpt/Wan2.1-VACE-1.3B/`（18GB，备用）
    - 我下载了 `iic/VACE-Annotators` 到 `/mnt/hdfs/xjy_hldy/ckpt/iic/iic/VACE-Annotators/`（4.4GB，含 salient/sam2/gdino/depth weights）
    - VACE 期望 `<repo>/models/{Wan2.1-VACE-14B,VACE-Annotators}/`，所以用 symlink 指过去
  - **Python deps（坑很多）**：
    - `wan` (`pip install git+https://github.com/Wan-Video/Wan2.1.git`)
    - `vace` (本地 -e install)
    - `xfuser>=0.4.0`（用于 Ulysses 序列并行）
    - `groundingdino-py`（VACE 配的 cp310 wheel 不兼容 cp311，要从 PyPI 装）
    - `SAM-2`（`pip install git+https://github.com/facebookresearch/sam2.git`）
    - **`wandb<0.18`**（很关键！timm 间接 import wandb，新版 wandb 跟 protobuf 7 冲突 → 整个 gdino 链 import 失败）
    - 其他：dashscope, easydict, decord, ftfy, pycocotools, hydra-core
  - **三大 footgun 必记**：
    1. **HDFS fuse 不刷盘 mp4 buffer**：VACE 默认把 preprocess 中间 mp4 写到 `processed/...`（在 VACE repo 下，HDFS 上）→ moov atom missing → decord 读失败。**必须 `--pre_save_dir /tmp/...`** 强制本地盘。脚本里硬编码了
    2. **14B 720p × 81 帧单卡 OOM**：80GB A100 都 OOM 在 VAE decode。必须 ulysses + dit_fsdp 多 GPU 切
    3. **VACE 内部隐式降采样**：源 360 帧（24fps×15s）→ VACE 用 `np.linspace(0, 15s, 81)` 均匀采样到 81 帧，按 `sample_fps=16` 写出 → **输出 mp4 = 5.06s（内容是 15s 但 3× 加速播放）**。VACE 的 `seq_len=75600`（720p）/`32760`（480p）是模型预训练硬上限，不能调大。要保留原 timing 必须 per-shot inference 拼接（脚本暂未实现）
  - **运行架构（针对 Arnold 集群 16 GPU/node L20 46GB）**：
    - **不用** Arnold 默认的多 node 同 job 模板（跨机 InfiniBand 太慢）
    - 改成：每个 node **独立 torchrun --nnodes=1 --nproc_per_node=16**（intra-node Ulysses 走 NVLink）；跨 node 并行靠 prompt 切片（`awk 'NR%${ARNOLD_WORKER_NUM}==${ARNOLD_ID}'`）
    - 显存：`--ulysses_size 16 --dit_fsdp --t5_fsdp --t5_cpu` → DiT 28GB / 16 = 1.75GB/卡，激活 ~10GB，VAE decode rank 0 一次性 ~5GB → ~15GB/卡 << 46GB
  - **脚本**（在 `scripts/`）：
    - `run_vace_one.sh <SAMPLE_ID> <K_INDEX> <TASK>` —— 单 prompt 单元：先单 GPU preprocess 写到 /tmp，再 16-GPU torchrun inference，最后拷 mp4 到 HDFS
    - `run_vace_arnold.sh` —— Arnold 顶层 launcher：按 ARNOLD_ID 切 prompt，每 prompt 调用 `run_vace_one.sh`。env vars: `TASKS / N_PER_TASK / K / TASK_MODE / SAMPLE_STEPS`
    - 旧脚本 `run_vace_single.sh` / `run_vace_all.sh` 是 1.3B 单卡版（备用，保留）
  - **状态**：1.3B + 480p + depth 在单卡 A100 smoke 通过（10 min/prompt 50 steps）。**14B + 720p + 16-GPU 配置好了但还没在 Arnold 上实跑**，等用户 launch
  - **预期速度**（16 GPU L20 ulysses）：14B 720p 81 帧 50 步 ≈ 3-5 min/inference。1608 K-sample 在 8 节点 ≈ 17h，16 节点 ≈ 8h
  - **TASK_MODE 选择**：默认 `depth`（保结构 + 重渲染，通用）。`inpainting`（salientmasktrack 自动抠主体）更适合 T1/T2/T4 局部编辑。脚本支持切换，未来按 task 自动选最优 mode
  - 输出：`runs/vace_14b_edit/videos/{T1..T8}/{sample_id}_k{0,1,2}.mp4`，与 Seedance 同结构 → 直接复用 `run_eval_parallel.sh` 评测

- **★ v2_10s 全 pipeline stand-up 完成（2026-05-28）**——这是 v2 主轨；v1 (15s) 仍保留作 Seedance-only 参照。
  - **30 个 10s 源视频**：`data/source_videos_10s/videos/{00..29}.mp4`（24fps × 240 帧 × 720p × 16:9）。源 prompt：`seedance_api_example/source_prompts_multishot_v2_10s.json`（30 条全新 10s scene，分布 6×3-shot + 18×4-shot + 6×5-shot），3 个文件因 shot 数错位被 retry：00019 (BBQ, 5→4), 00023 (busker, 5→4), 00024 (mechanic, 6→5)
  - **OmniShotCut shot detection: 30/30 (100%)** —— `runs/pilot_v2_10s/shots/`，consensus_backend=omnishotcut。`runs/pilot_v2_10s/contact_sheets/` 30 张 QA 图，`pilot_report.md` 含每视频 grid + match/miss 标注
  - **480 条 edit prompts 全部由 Claude 手写完成**：`runs/edit_prompts_v2_10s/T{1..8}.json`。T1-T8 各 60 条。2026-06-07 新分布：T1=30 dynamic replacement + 30 static replacement；T4=static add 20 + static delete 20 + dynamic add 20，不做 dynamic delete；T3=style-only；T7=lighting-only；T8=background replacement with foreground preservation。2026-06-08 QA 后，T1 dynamic 必须是主体个体级替换，T1 static 必须是功能兼容的物体类别级替换，T2 必须是同一物体/主体的显著属性变化，T7 必须是视觉差异明确的光源类型。**T5 op 分布**：60 reorder。
  - **shots 字段已替换为真实边界**（`mseditbench/preprocess/contact_sheet.py` consensus → `T{1..8}.json` 的 `shots`，覆盖占位值）。下游 metric eval 切 source frames 不再错位
  - **all_edit_handoff.json**（`runs/edit_prompts_v2_10s/all_edit_handoff.json`）整合所有 480 条为 `{filename, source_url, edit_prompt}` 三字段平铺给外部协作方跑别的 v2v 模型。每条 source_url 用 ModelScope `inLine013/videobed_10s/{vid}.mp4`
  - **ModelScope 镜像**（`https://modelscope.cn/datasets/inLine013/videobed_10s/resolve/master/{video_name}`）含全部 30 个最新源视频（00019/00023/00024 已 reupload 替换）。无 24h TTL，是 v2_10s 的 source_url 真相源
  - **Seedance Pro / Fast edit launcher 就绪**：
    - `seedance2.0/scripts/infer_v2_mutilshot_edit_v2_10s_all.sh` (Pro: `doubao-seedance-2-0-260128`)
    - `seedance2.0/scripts/infer_v2_fast_mutilshot_edit_v2_10s_all.sh` (Fast: `doubao-seedance-2-0-fast-260128`)
    - 都用 `--source_url_template` ModelScope 直链，`--duration 10`，`--num_samples 3`（K=3）
    - 输出：`runs/seedance_v2v_edit_v2_10s/` 和 `runs/seedance_v2v_fast_edit_v2_10s/`（与 v1 平行结构，可直接复用 eval pipeline）
    - 当前 prompt 集工作量：480 prompts × 3 K = 1440 calls；ARNOLD_WORKER_NUM=64 时 Pro/Fast 预计与旧 420-prompt 集接近
  - **Python infer 脚本不动**——`seedance2.0/pyscripts/infer_v2_mutilshot_edit.py` 已支持 `--source_url_template` / `--duration` / `--model`，新 shell 只是路径换皮

- **★ v2_10s Seedance Pro / Fast 编辑跑完 + mask-aware leaderboard 出炉（2026-05-28，旧 420-prompt snapshot）**：
  - **Edit 出片量（旧 420-prompt snapshot）**：Pro 1437/1440（缺 sample 00028_T4_0057 三个 K，Seedance API 拒）；Fast 1440/1440（100%）
  - **Eval 协议**：`scripts/run_eval_parallel.sh` 通过 env vars 驱动（已 generalize：`PROMPTS_DIR / SOURCE_VIDEOS_ROOT / BASELINE_NAME / BASELINE_VIDEOS_ROOT / EVAL_OUT_ROOT / SNAPSHOT_ID` 都可 override；不再需要 fork 脚本）。SAM-3 mask + pyiqa MUSIQ+LAION-Aes PSQ + InsightFace IDdrift 全开
  - **Pro 8-task eval ≈ 2h**（4:02 PM → 6:06 PM），**Fast 8-task ≈ 2h**（6:09 PM → 8:10 PM）。8-GPU 并行 sequential per-task
  - **Pro v2_10s mask-aware leaderboard**（K=3 mean ± std, n_prompts=60 each）：
    ```
    Task        PSQ            EE              NEP            CSEP           SES            DPS
    T1 char     0.596 ±0.031   0.099 ±0.157    0.861 ±0.135   0.104 ±0.228   1.000 ±0.000   —
    T2 attr     0.598 ±0.029   0.044 ±0.116    0.949 ±0.097   0.095 ±0.182   0.797 ±0.238   —
    T3 style    0.602 ±0.032   0.017 ±0.057    0.907 ±0.113   0.009 ±0.054   0.717 ±0.288   —
    T4 obj      0.598 ±0.029   0.037 ±0.085    0.946 ±0.091   0.032 ±0.106   0.811 ±0.238   —
    T5 struct*  0.593 ±0.030   0.001 ±0.011    0.869 ±0.148   0.015 ±0.046   0.799 ±0.184   —
    T6 cam      0.579 ±0.041   0.011 ±0.086    0.589 ±0.180   —              0.653 ±0.262   —
    T7 trans    0.599 ±0.030   0.000 ±0.000    0.978 ±0.019   0.000 ±0.000   0.871 ±0.081   —
    T8 dieg     0.600 ±0.029   0.000 ±0.000    0.975 ±0.033   0.023 ±0.073   0.869 ±0.092   0.543 ±0.212
    ```
  - **Fast v2_10s mask-aware leaderboard**：
    ```
    Task        PSQ            EE              NEP            CSEP           SES            DPS
    T1 char     0.576 ±0.027   0.082 ±0.133    0.900 ±0.090   0.089 ±0.177   1.000 ±0.000   —
    T2 attr     0.573 ±0.031   0.031 ±0.095    0.972 ±0.023   0.096 ±0.166   0.822 ±0.100   —
    T3 style    0.577 ±0.037   0.027 ±0.087    0.920 ±0.097   0.023 ±0.087   0.704 ±0.242   —
    T4 obj      0.573 ±0.031   0.034 ±0.080    0.965 ±0.027   0.033 ±0.120   0.825 ±0.116   —
    T5 struct*  0.570 ±0.029   0.000 ±0.000    0.916 ±0.107   0.005 ±0.024   0.825 ±0.126   —
    T6 cam      0.560 ±0.038   0.028 ±0.111    0.631 ±0.184   —              0.673 ±0.280   —
    T7 trans    0.573 ±0.030   0.000 ±0.000    0.981 ±0.009   0.001 ±0.008   0.851 ±0.092   —
    T8 dieg     0.574 ±0.030   0.000 ±0.000    0.980 ±0.010   0.023 ±0.059   0.848 ±0.093   0.563 ±0.210
    ```
  - **Pro vs Fast 对比（mean over 8 tasks）**：
    ```
    Metric    Pro       Fast      Δ(F-P)    Winner (8/8 dominance)
    PSQ       0.596     0.572     -0.024    Pro 8/8
    EE        0.026     0.025     -0.001    ≈ (打平)
    NEP       0.884     0.908     +0.024    Fast 8/8
    CSEP*     0.040     0.039     -0.001    ≈
    SES       0.815     0.819     +0.004    ≈
    DPS (T8)  0.543     0.563     +0.020    Fast
    ```
    *CSEP averaged over T1-T5,T7,T8（T6 单 shot 不算 CSEP）。结论：v2_10s 上 Pro 视觉质量更高、Fast 保留更多；EE/CSEP/SES 都 ≈ 持平。比 v1 更接近——Pro 的算力优势在 10s 短源上更难发挥
  - **v2_10s vs v1 对比关键差异**：
    - **PSQ ↑**（v2 Pro 0.596 vs v1 Pro 0.582）——10s 更短 → 每帧更多算力 → 视觉质量好
    - **EE ↓ ≈ 一半**（v2 Pro 0.026 vs v1 Pro 0.048）——Seedance 在短源上**编辑保守**，几乎不动手；多数任务 EE → 0
    - NEP / CSEP / SES 量级一致
    - 解读：10s 短源对 v2v 模型是"挑战 mode"，编辑能力天花板更低；这反而让 paper 的「v2v 模型在 multi-shot 编辑上能力有限」论点更尖锐
  - **T6 NEP 暴跌**（Pro 0.589 / Fast 0.631）——Cinematic Re-shoot 改单 shot 整体重渲，整片 NEP 必然低；与 v1 (0.639/0.672) 同量级
  - **T7/T8 EE → 0**：Seedance v2v 几乎无法做转场风格 + diegetic 因果传播。这正是 agent 应该胜出的领域（见 `AGENT_BENCH_DESIGN.md`）
  - 输出：
    - Pro: `runs/eval_seedance_v2v_v2_10s_masked/{T1..T8}/aggregate.json`
    - Fast: `runs/eval_seedance_v2v_fast_v2_10s_masked/{T1..T8}/aggregate.json`
  - **TODO**：T5 单独走 TSF 轨（`mseditbench/eval/t5_track.py`，需要把 baseline_dir 指 v2_10s）；leaderboard 上 T5 EE/NEP/CSEP 是噪声，不进 paper headline

- **★★ EE / CSEP 完全重做为 v3：VLM-as-Judge（2026-05-29 凌晨）**——v1（CLIP-T binary 阈值 + 3-VLM 一致投票）和 v2（连续 CLIP-T uplift / directional CLIP）**两条线全部废弃**。CLIP-T 是 proxy 不是 ground truth：捕捉文本-图像相似度，但看不出「编辑做得好不好」（特别是看不出 Pro 的视觉质量优势）。v3 用 VLM 直接看图判断，与人类判断对齐。
  - **诊断 v1/v2 失败原因**：
    - **v1 mask-aware Pro EE 跨任务全部 ≤ 0.10**——被 binary CLIP-T 阈值 (0.05) + 3-VLM 一致 YES 双重 gate 卡死；mask 用 target_phrase 做 SAM-3 query 静默 fall-through 到 whole-frame
    - **v2 续努力 (continuous CLIP-T uplift, per-task DELTA_MAX)** 把数字推到 0.3-0.5 区间，但 **Pro 反而比 Fast 弱 5-15%**——CLIP-T uplift 奖励"小步对方向移动"，Fast 的 conservative 编辑反而吃香；Pro 大幅重渲让 CLIP image embedding 偏离了原 target 文本方向
    - 根本问题：CLIP-T 不能识别「视觉质量」「编辑完整度」「跨 shot 一致性」——这些恰是 Pro 强于 Fast 的维度
  - **v3 设计（VLM-judge）**：
    - **EE_v3** = `mean over applicable shots of VLM_score(0-5) / 5`
      - VLM 输入：source mid-frames (FRAME-SET A) + edit mid-frames (FRAME-SET B) + instruction
      - 严格 4 准则评分：(i) instruction faithfulness (ii) region correctness (iii) visual quality (iv) completeness
      - **Anchored 0-5 scale**（关键 prompt 工程）：「most edits 应在 2-4 区间，5 留给 truly excellent」——避免 VLM 默认 stamp 5
      - 后端：Seed 2.0 Lite via Volcengine Ark；未来加 Gemini 2.5 + GPT-4o ensemble
    - **CSEP_v3** = `sqrt(coverage × consistency)` 几何平均
      - coverage = mean per-shot EE_v3
      - consistency = mean over (k1,k2) pairs of VLM 0-5 评分「这两个 edit shot 的结果一致吗」
      - <2 applicable shots → CSEP=None
  - **v3 真实 leaderboard（K=3 mean ± std, n=60 each, mask-aware sam3+pyiqa+insightface, Seed Lite VLM）**：
    ```
    Pro v2_10s:
    Task        PSQ            EE_v3           CSEP_v3         NEP            SES            DPS
    T1 char     0.596 ±0.031   0.523 ±0.189    0.531 ±0.248    0.855 ±0.128   1.000 ±0.000   —
    T2 attr     0.598 ±0.029   0.567 ±0.210    0.681 ±0.199    0.950 ±0.095   0.797 ±0.238   —
    T3 style    0.602 ±0.032   0.496 ±0.241    0.556 ±0.223    0.902 ±0.114   0.717 ±0.288   —
    T4 obj      0.598 ±0.029   0.367 ±0.210    0.414 ±0.246    0.943 ±0.088   0.811 ±0.238   —
    T6 cam      0.579 ±0.041   0.698 ±0.142    —               0.508 ±0.145   0.653 ±0.262   —
    T8 dieg     0.600 ±0.029   0.341 ±0.273    0.363 ±0.247    0.975 ±0.033   0.869 ±0.092   0.550 ±0.213

    Fast v2_10s:
    T1 char     0.576 ±0.027   0.543 ±0.185    0.537 ±0.230    0.900 ±0.090   1.000 ±0.000   —
    T2 attr     0.573 ±0.031   0.627 ±0.187    0.717 ±0.198    0.972 ±0.023   0.822 ±0.100   —
    T3 style    0.577 ±0.037   0.565 ±0.198    0.600 ±0.205    0.920 ±0.097   0.704 ±0.242   —
    T4 obj      0.573 ±0.031   0.458 ±0.197    0.480 ±0.231    0.965 ±0.027   0.825 ±0.116   —
    T6 cam      0.560 ±0.038   0.670 ±0.206    —               0.631 ±0.184   0.673 ±0.280   —
    T8 dieg     0.574 ±0.030   0.352 ±0.229    0.396 ±0.218    0.980 ±0.010   0.848 ±0.093   0.557 ±0.219
    ```
  - **Pro vs Fast 6-task mean**：
    ```
    Metric      Pro      Fast     Δ(P-F)    Winner
    PSQ         0.595    0.572    +0.023    Pro     (Pro 全胜 6/6)
    EE_v3       0.499    0.536    -0.037    Fast    (T6 单项 Pro 胜)
    CSEP_v3     0.509    0.546    -0.037    Fast
    NEP         0.855    0.880    -0.025    Fast    (Fast 保留更多)
    SES         0.808    0.812    -0.004    ≈
    DPS (T8)    0.550    0.557    -0.007    ≈
    ```
    - **数字真实可解读**：v3 在 0.34-0.70 区间（v1 几乎全 0；v2 偏低偏 saturated）
    - **Pro 优势体现在 PSQ（视觉质量全胜）+ T6 cinematic re-shoot**（VLM 能识别复杂运镜的完整度）
    - Fast 在 T2/T3/T4 略胜——更靶向、更保守的编辑反而被 VLM 评高分
    - Pro/Fast 整体差距 3-4pt，**符合「Pro 不低于 Fast 太多」标准**
    - 这与 v1 mask-aware 已观察到的趋势一致：Pro 和 Fast 编辑能力相当，Pro 视觉质量略胜
  - **代码位置**：
    - `mseditbench/metrics/ee_v3.py` — VLM-judge per-shot EE rating
    - `mseditbench/metrics/csep_v3.py` — VLM-judge pairwise CSEP rating + coverage 几何平均
    - `mseditbench/metrics/backends.py` — 加 `VlmBackend.rate(frames, prompt)` 和 `rate_pair(frames_a, frames_b, prompt)` 方法 + `_parse_rating` 整数解析
    - `mseditbench/eval/run_eval.py` — v1 / v2 EE/CSEP 设为 None 跳过；v3 是 headline
    - `eval.json` 新字段：`ee_v3`, `csep_v3`, `csep_v3_coverage`, `csep_v3_consistency`, `extra.ee_v3_per_shot`, `extra.csep_v3_pair_scores`
    - 输出：`runs/eval_seedance_v2v_v2_10s_v3/{T1..T8}/aggregate.json`（Pro）+ `runs/eval_seedance_v2v_fast_v2_10s_v3/...`（Fast）
  - **VLM 调用预算**：每 prompt = 4 ee + 6 csep = 10 calls (4-shot)。60 prompts × K=3 × 10 ≈ 1800 calls/task。Seed Lite ~$0.0005/call → ~$1/task。**全 6 任务 × 2 baselines ≈ $12** ✓
  - **运行时间**：8-GPU shard parallel + 8 VLM workers/shard = 64 concurrent VLM calls。受 Seed Lite TPM throttle 约束，实测 Pro ~150min, Fast ~150min。比 v1/v2（~80min）慢 ~2x，但数据质量值得
  - **v1/v2 ablation 字段保留**（在 eval.json 里都是 None）；需要重做老指标对照只要解注释 run_eval 里那段计算块即可

- **★ Wan 2.7 v2v 第三个 baseline 上线（2026-06-01）**——首个非 Seedance 的开源/异厂 v2v 编辑器接入。
  - **数据来源**：用户提供 `runs/wan_v2v_2.7_edit_v2_10s/videos/`。**T1-T4 完整度 75-97%**（n: T1=58, T2=57, T3=52, T4=45）；T5-T8 残缺跳过
  - **K=1**（用户因费用未跑 K=3）：eval pipeline 通过 `NUM_SAMPLES=1` env var 切换
  - **Wan 2.7 v3 leaderboard**：
    ```
    Task        PSQ            EE_v3           CSEP_v3         NEP            SES
    T1 char     0.636 ±0.028   0.620 ±0.170    0.635 ±0.206    0.771 ±0.102   1.000 ±0.000
    T2 attr     0.628 ±0.031   0.673 ±0.161    0.754 ±0.180    0.830 ±0.085   0.517 ±0.219
    T3 style    0.614 ±0.066   0.661 ±0.103    0.751 ±0.117    0.671 ±0.137   0.315 ±0.239
    T4 obj      0.627 ±0.032   0.541 ±0.173    0.574 ±0.217    0.759 ±0.141   0.548 ±0.212
    ```
  - **3-way 4-task means（T1-T4）**：
    ```
    Metric    Pro      Fast     Wan 2.7   Winner    Δ(Wan-bestSeed)
    PSQ       0.598    0.575    0.626     Wan       +0.027
    EE_v3     0.488    0.548    0.624     Wan       +0.075
    CSEP_v3   0.545    0.583    0.678     Wan       +0.095
    NEP       0.912    0.934    0.758     Fast      -0.176
    SES       0.831    0.838    0.595     Fast      -0.243
    ```
  - **解读**：Wan 2.7 更激进——PSQ/EE/CSEP 全胜但 NEP/SES 显著低于 Seedance（编辑强但越界）。经典 edit-strength vs preservation tradeoff
  - 输出：`runs/eval_wan_v2v_2.7_v2_10s_v3/{T1..T4}/aggregate.json`

### 接下来（按优先级）
1. **★ T5 TSF eval（v2_10s, 全 3 baselines）**
2. **VLM ensemble 多样化**：加 Gemini 2.5 + GPT-4o
3. **跑真实 Runway Aleph**：先 T1+T2
4. **加 Luma Modify / Veo 3.1 / Pika / DomoAI 商用 baseline**
5. **MSEdit-Agent-Bench 立项**（设计文档：`AGENT_BENCH_DESIGN.md`）
6. **写 paper results 表 + 分析**——3-way 对比已经能写

### 当前 session 状态（2026-06-01 晚）
- Wan 2.7 第三个 baseline 接入完成（K=1, T1-T4, v3 eval done）
- 3-way leaderboard：Wan PSQ/EE/CSEP 全胜，Seedance NEP/SES 全胜
- `scripts/run_eval_parallel.sh` 加了 NUM_SAMPLES env var 支持 K=1
- 下一步：T5 TSF + VLM ensemble + 更多 baseline

---

## 3. 已确认的 scope 决策（不要再 debate）

这些是用户已经选定、不要重新讨论的方向：

| 决策 | 选择 | 理由 |
|---|---|---|
| **编辑 vs 生成** | Edit 为主、Gen 作对照 | Multi-shot gen 已有 15+ 个 bench；edit 是空地 |
| **闭源 API** | 纳入评测（Sora 2 / Veo 3 / Seedance / Kling / Aleph / Luma 等） | 接受工程成本换取相关性 |
| **规模** | ~480-1500 prompt（中等），目标 930 | 对照 VBench / EvalCrafter 量级 |
| **源视频来源** | 全部用 Seedance 2.0 Pro 生成 | 为加速，跳过 Pexels 收集；但需配 30 段真实视频作 robustness 子集（详见 `seedance_api_example/README_multishot.md` §五） |
| **视频时长** | **10s（v2 版本）/ 15s（v1 版本）** | v2 选 10s 因为多数开源模型不支持 15s 输入；v1 保留 15s 作 Seedance-only 参照 |
| **fps** | 24（Seedance 固定） | 显式记录 |
| **分辨率** | 1080p | benchmark 质量优先 |
| **Shot 边界 canonical 格式** | **frame index**（time 是 derived） | 跨模型 fps 不同；下游所有工具用 frame；详见 `seedance_api_example/README_multishot.md` §四 |
| **Shot 数分布** | 6×3-shot + 18×4-shot + 6×5-shot | 按场景节奏分配，给 T5/T7 足够 shot 数 |
| **Shot 切分检测器** | **OmniShotCut 主**（arXiv:2604.24762）+ TransNetV2 + PySceneDetect 验证 | OmniShot 在我们 30 条 Seedance 视频上比 TN+PS 更准（发现真实切镜，不被快速运动迷惑） |
| **License 策略** | 只 redistribute hash + prompt + ~100 qualitative subset 视频 | 商用 API 视频 ToS 风险，提前和 ByteDance Seed 法务沟通 |
| **Reproducibility** | Snapshot Protocol：冻结 API model string + archive 全部生成视频到 Zenodo | 商用 API 快速迭代会让数字过期 |
| **不评 audio-coupled edits in v1** | 推到 future work | annotator 成本高 |
| **绝不用 Seedance 作编辑 baseline** | 仅作源视频生成器 | 防 Seedance-on-Seedance 数据泄漏 unfair |

---

## 4. 文件清单

### 4.1 仓库内（`/mnt/hdfs/xjy_hldy/datasets/multi_shot_bench/`）

```
multi_shot_bench/
├── CLAUDE.md / HOWTO.md / SURVEY_REPORT.md / RELATED_WORK_SURVEY.md
├── DEEP_DIVE.md / RESEARCH_PLAN.md / bench_config.json
│
├── seedance_api_example/                  历史副本（保留）
│   └── source_prompts_multishot_v1.json   30 条 15s multi-shot prompt（v2 客观格式）
│
├── data/                                  ★ 源视频（v2_10s 是 2026-05-27/28 的真相源）
│   └── source_videos_10s/                ★ 30 个 10s mp4（当前主轨；ModelScope 镜像同步）
│       ├── videos/                        30 个 mp4（含 retry 后的 00019/00023/00024）
│       ├── inference_csv/                 Seedance API 调用 CSV
│       └── success_csv/                   含 30 条 all_seedance_* + 3 条 zz_loopmatch_*
│
├── mseditbench/                           ★ 核心 Python 包（39+ 文件）
│   ├── schema.py                          canonical dataclasses
│   ├── preprocess/
│   │   ├── shot_detect.py / contact_sheet.py / pilot_report.py
│   │   └── loop_until_match.py            ★ loop 重试到命中（自动删旧 mp4）
│   ├── tracking/                          Grounded-DINO + SAM-2-Video
│   ├── identity/                          InsightFace + 单链聚类
│   ├── edit_prompts/
│   │   ├── tasks.py / banks.py            T1-T8 模板 + value 库
│   │   ├── generate.py                    v1 模板生成器
│   │   ├── rewrite_with_llm.py            v1.1 Seed Lite 改写器
│   │   ├── handwritten_t{1..8}.py         ★ v1.2 我亲手写的 536 条字面量
│   │   ├── build_v1_2_handwritten.py      v1.2 builder
│   │   └── judge_3way.py                  v1 vs v1.1 vs v1.2 盲评
│   ├── metrics/                           PSQ/EE/NEP/CSEP/USP/TAC/CXS-ID
│   │   ├── backends.py                    DINO/VLM/SAM-3/pyiqa 等当前后端；CLIP/Face 保留给旧消融
│   │   └── frame_io.py
│   ├── baselines/                         editor API client
│   │   ├── aleph.py / snapshot.py / run_baseline.py
│   ├── eval/                              run_eval.py + leaderboard.py
│   │   ├── run_eval.py                    ★ 主评测脚本（PSQ/EE_v3/NEP/CSEP_v3/USP/TAC）
│   │   ├── recompute_psq.py               ★ 单点修：从 mock PSQ → pyiqa
│   │   ├── recompute_usp.py               ★ 单点修：重算 USP/TAC
│   │   └── merge_shards.py                shard agg → final aggregate
│   └── tests/test_metrics.py              17 个 unit test
│
├── scripts/                              ★ 顶层 launcher
│   ├── run_eval_parallel.sh              8-GPU 并行评测（默认 sam3+pyiqa+omnishotcut）
│   ├── recompute_psq_parallel.sh         PSQ 重算并行
│   ├── recompute_usp_parallel.sh         USP/TAC 重算并行
│   ├── run_vace_one.sh                   ★ VACE 14B 单 prompt（preprocess + 16-GPU 推理）
│   ├── run_vace_arnold.sh                ★ VACE 14B Arnold 多机批量 launcher
│   └── run_vace_single.sh / run_vace_all.sh  VACE 1.3B 单卡版（备用）
│
└── runs/                                  所有 pipeline 输出
    ├── pilot_v5_final/                    ★ v1 30/30 (100%) shot detection
    ├── pilot_v2_10s/                      ★ v2_10s 30/30 (100%) shot detection（当前 v2 权威）
    │   ├── shots/{vid}.shots.json         OmniShot+TN+PS consensus
    │   ├── contact_sheets/                30 张 QA 图
    │   └── pilot_report.{md,json}

    ├── edit_prompts_v2_10s/               ★ v2_10s: 480 条 Claude 手写（**当前主轨**）
    │   ├── T{1..8}.json                   各 60；shots 已是 OmniShot 真实边界
    │   └── all_edit_handoff.json          整合给外部协作的 480 条平铺 JSON
    ├── eval_3way/                         v1/v1.1/v1.2 盲评结果

    ├── seedance_v2v_edit_v2_10s/          旧 420-prompt Pro 编辑结果（1437/1440）
    ├── seedance_v2v_fast_edit_v2_10s/     旧 420-prompt Fast 编辑结果（1440/1440）
    ├── eval_seedance_v2v_v2_10s_v3/       旧 420-prompt Pro v3 leaderboard
    ├── eval_seedance_v2v_fast_v2_10s_v3/  旧 420-prompt Fast v3 leaderboard
    ├── eval_wan_v2v_2.7_v2_10s_v3/        ★ Wan 2.7 v3 leaderboard（T1-T4）

    ├── eval_t5_track/                     ★ v1 T5 TSF 指标（Pro+Fast）
    └── vace_14b_edit/                     VACE 14B 编辑结果（待跑）
        └── videos/{T1..T8}/{sample_id}_k{0,1,2}.mp4
```

### 4.2 仓库外 / 视频侧（`/mnt/hdfs/xjy_hldy/datasets/seedance2.0/`）

```
seedance2.0/
├── source_prompts_multishot_v1.json   与 multi_shot_bench/ 内副本同步
├── mismatch_ids.txt                   当前 mismatch 列表
├── download_videos.py                 ⚠️ line 32-34 footgun（详见 §6）
├── pyscripts/
│   ├── infer_v2_mutilshot_source.py   全量生成
│   ├── infer_v2_mutilshot_retry.py    按 mismatch_ids 过滤后生成
│   └── infer_v2_mutilshot_edit.py     v2v 编辑（按 task_id 过滤）
├── scripts/
│   ├── infer_v2_mutilshot_source.sh   写到 multi_shot_bench/data/source_videos/
│   ├── infer_v2_mutilshot_retry.sh    含「下载前删旧 mp4」逻辑（修了 §6 的 footgun）
│   ├── infer_v2_mutilshot_edit.sh     单 task v2v
│   ├── infer_v2_mutilshot_edit_all.sh ARNOLD 8 task 一次跑完（v1, Pro, TOS CSV）
│   ├── infer_v2_fast_mutilshot_edit_all.sh   v1 Fast（ModelScope template）
│   ├── infer_v2_mutilshot_source_v2_10s.sh   ★ v2_10s 源视频生成
│   ├── infer_v2_mutilshot_edit_v2_10s_all.sh ★ v2_10s Pro v2v edit（ModelScope template）
│   ├── infer_v2_fast_mutilshot_edit_v2_10s_all.sh  ★ v2_10s Fast v2v edit
│   └── migrate_seedance_outputs.sh    legacy
└── 0519_videos_720p/                  legacy（弃，新视频在 multi_shot_bench/data/）
```

⚠️ **视频生产真相源 = `multi_shot_bench/data/source_videos_10s/`**（v1 15s 已删除）。
**ModelScope 镜像**：`https://modelscope.cn/datasets/inLine013/videobed_10s/resolve/master/{vid}.mp4` —— 30 个最新源视频（含 retry 后的 00019/00023/00024），无 24h TTL。

### 4.3 VACE 相关外部路径

```
/mnt/hdfs/xjy_hldy/projects/VACE/           VACE 仓库（已 pip install -e）
/mnt/hdfs/xjy_hldy/ckpt/Wan2.1-VACE-14B/   14B 主权重（70GB，7-shard + T5 + VAE）
/mnt/hdfs/xjy_hldy/ckpt/Wan2.1-VACE-1.3B/  1.3B 备用（18GB）
/mnt/hdfs/xjy_hldy/ckpt/iic/iic/VACE-Annotators/   salient/sam2/gdino/depth 预处理权重（4.4GB）

symlinks（VACE runtime 使用 <repo>/models/ 下的 symlink）:
  VACE/models/Wan2.1-VACE-14B   → /mnt/hdfs/xjy_hldy/ckpt/Wan2.1-VACE-14B
  VACE/models/Wan2.1-VACE-1.3B  → /mnt/hdfs/xjy_hldy/ckpt/Wan2.1-VACE-1.3B
  VACE/models/VACE-Annotators   → /mnt/hdfs/xjy_hldy/ckpt/iic/iic/VACE-Annotators
```

### 4.4 任务 ID ↔ 名称对照（canonical，来自 `tasks.py`）

| Task ID | Canonical name | 简写 | 描述 |
|---|---|---|---|
| T1 | Cross-Shot Replacement | repl | 30 动态实体个体级替换 + 30 功能兼容的静态物体类别级替换 |
| T2 | Cross-Shot Attribute Edit | attr | 同一物体/主体的颜色、材质、图案、质感、发型/毛发长度 |
| T3 | Global Style | style | 全片视觉风格重渲 |
| T4 | Cross-Shot Add/Delete | obj | static add / static delete / dynamic add 各 20；不做 dynamic delete |
| T5 | Shot Reorder | struct | 改镜头顺序（★per-shot eval 不适用，需 TSF 单独轨） |
| T6 | Cinematic Re-shoot | cam | 改单 shot 运镜/构图 |
| T7 | Global Lighting | light | 全片高辨识光源重渲 |
| T8 | Global Background Replacement | bg | 替换背景并保留前景主体/物体 |

⚠️ **2026-06-07 更新**：T1/T4/T3/T7 已按新定义重构；旧 420-prompt baseline/eval 结果只能作为历史 snapshot。
⚠️ **2026-06-08 更新**：T1 dynamic 已手审为主体个体级替换；T1 static 已从同类物体变体改为功能兼容的类别级替换；T2 已移除新增配饰/服装类型替换并清理 `target_phrase`；T7 已替换为区分度强的光源类型。
⚠️ **2026-06-07 更新**：T8 已作为 background replacement 重新启用；NEP 对 T8 使用 foreground preserve mask 内部区域算 DINOv2。
⚠️ **2026-06-06 更新**：T5 只保留 reorder，TSF 不再使用 shot-count 分。
⚠️ **2026-05-25 之前 CLAUDE.md / leaderboard 表里的 T3="char" T5="act" T6="style" T7="cam" 全部是错标。正确标签见上表。数字不受影响（按 task_id 索引无错位），文字已修正。**

---

## 5. 用户的当前工作流

视频和 shot detection 都已完成（见 §2）。现在的入口是 `HOWTO.md` —— 那里有完整的命令清单。

下面是几个最常用的 one-liner（详细参数见 HOWTO.md）：

```bash
cd /mnt/hdfs/xjy_hldy/datasets/multi_shot_bench

# 跑 metric 单元测试（应 17/17 通过）
python3 -m mseditbench.tests.test_metrics

# 重生成 T1-T8 edit prompts（改 banks.py 后跑这个）
python3 -m mseditbench.edit_prompts.generate \
    --source_json seedance_api_example/source_prompts_multishot_v1.json \
    --shots_dir runs/pilot_v2/shots \
    --output_dir runs/edit_prompts_v1 \
    --tasks T1,T2,T3,T4,T5,T6,T7,T8 --max_per_video 2

# Mock end-to-end smoke（不需要任何 API key / GPU）
python3 -m mseditbench.baselines.run_baseline \
    --prompts_json runs/edit_prompts_v1/T1.json \
    --videos_dir /mnt/hdfs/xjy_hldy/datasets/seedance2.0 \
    --output_dir runs/edits_aleph_mock/T1 --baseline aleph_mock --limit 5

python3 -m mseditbench.eval.run_eval \
    --prompts_json runs/edit_prompts_v1/T1.json \
    --baseline_dir runs/edits_aleph_mock/T1 \
    --videos_root /mnt/hdfs/xjy_hldy/datasets/seedance2.0 \
    --output_dir runs/eval_aleph_mock/T1 \
    --baseline aleph_mock --snapshot_id ad-hoc --limit 5
```

如果 pilot 视频要重测（少见，因为 pilot_v2 已 97% 通过），见 `mseditbench/preprocess/README.md`。

---

## 6. 必须遵守的约定

### Frame vs Time
- **canonical = frame index**；time 是 `frame / fps` 算出来的 derived field
- 理由：跨模型 fps 不同（Seedance 24 / Kling 30 / Sora 混合），用秒会有舍入误差；所有下游工具（TransNetV2 / PySceneDetect / SAM-2 / Grounding-DINO / CoTracker / ArcFace）原生用 frame
- 例外：API 调用（Seedance / Veo / Sora 的 `duration` 参数）必须用秒
- 详见 `seedance_api_example/README_multishot.md` §四

### 已知 footgun（踩过的坑，下次别再踩）

**1. `seedance2.0/download_videos.py:32-34` 短路逻辑**
```python
if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
    return True, video_name, url   # ← 不下载、不告警，直接说成功
```
**症状**：retry / loopmatch 调 API 生成新视频拿到新 URL，但 download 看到本地有旧 mp4 → 跳过 → 本地内容还是旧版，shot_detect 看到老结果。**两次 retry 全部"无效果"原因就是这个**。

**修复**：retry.sh 已加显式 `python -c "csv.DictReader → os.remove"` 删旧 mp4；loop_until_match.py 也内置了 `if os.path.exists: os.remove`。**写新的 retry-style 工具时记得加上**。

**2. Seedance v2v API 拒绝 100MB+ 源视频**
某些场景（动态密集、夜景、海浪）Seedance 出来的源 mp4 会到 100-130MB。v2v API 调用时 generic exception，python 没存错误信息只写 `status=exception`。这次 30 个源视频里 10 个都 >100MB（00003/00005/00008/00009/00021/00023/00025/00026/00027/00029），全部跑 v2v 失败。

**修复**：跑 v2v 前用 `ffmpeg -crf 28` 转码到 <20MB；或 source 阶段就生成 480p 减小体积；或单独把这 10 条源换地方上传。

**3. Seed VLM TPM rate limit (429)**
1606 prompt × 12 VLM 调用 × 2-4 帧/次 = ~80k tokens/min，撞 Lite TPM 上限。一开始 retries=3 + 2s 退避完全不够，半数 sample 直接报错。

**修复（已生效在 `backends.py:_make_seed_vlm`）**：
- max_retries 3 → 8
- 普通错误 4s × 2^attempt 退避（max ~600s）
- **429 专用退避**：30 + 15·attempt s（一直等到 TPM 窗口刷新）
- VLM 每次发 frames 数减少 4→2，max_side 512→384（每调用 token 量减半）
- `SEED_VLM_MIN_INTERVAL_SEC` env var 可设最小间隔节流

**4. CLIP/DINO 下载从 HF 太慢**
HF 提供的 vit_base_patch32_clip_224 模型 ~150 KB/s（被代理 throttle 或 HF 限速）。同样 OpenAI 的 ViT-B-32.pt 从 azure CDN 下载是 9.5 MB/s。GitHub 的 torch.hub.load 还会触发 rate-limit (HTTP 403)。

**修复（已生效）**：CLIP 用 OpenAI `clip` 包加载本地 `/tmp/clipdl/clip_vitb32.pt`；DINOv2 从 Meta CDN `dl.fbaipublicfiles.com` 直下到 `/tmp/dinov2/`，再用 timm 加载（注意 timm 的 DINOv2 需要 **518×518** 输入，不是 224）。

**5. CLIP score_video_text 默认 batch=1**
之前实现是 `np.mean([clip._embed_image(f) for f in frames])` —— 每帧单独 GPU forward。GPU 看到的是几十个独立的 batch=1 调用，效率极低（GPU 启动开销 >> 实际计算）。

**修复（已生效）**：`_OpenAICLIP.score_video_text` 现在所有 frames 一次性 stack 后单次 forward。GPU 利用率从 0% 跳到 100%，单调用从 ~500ms 降到 ~90ms（8 frames）。

**6. GPU 占卡协议（用户内部规范）**
跑任何 GPU 前：`cp /mnt/hdfs/xjy_hldy/zhanka_50.yaml ~/zhanka.yaml`（让出资源）。
跑完后：`cp /mnt/hdfs/xjy_hldy/zhanka_4096.yaml ~/zhanka.yaml`（重新占满防 squat）。
**违反这个协议会被骂**。看到 nvidia-smi 还在 100% 用就别忘了切回 4096。

### Shot tag 格式（caption 里 `[...]` 内容）
2026-05-20 起统一为 `[scale, angle/movement]` **全小写客观格式**，氛围/灯光/场景修饰全部移到 prose。词表：
- scale: `wide`, `medium`, `medium close-up`, `close-up`, `extreme close-up`
- angle: `low-angle`, `high-angle`, `overhead`, `profile`, `from behind`
- movement: `tracking`, `pan`, `tilt`
- 特殊: `over-the-shoulder`, `reverse`, `two-shot`, `establishing`, `POV`

例：`[wide] In a sunlit kitchen, a young woman walks in...` （✓）  
而不是 `[Wide shot, soft morning light through window] A young woman...` （✗ 旧格式）

写新 prompt 时严守此格式；改格式会让 30 视频的 v2 ↔ v1 不一致，重新做 shot detection 校验成本高。

### 文件命名
- 视频：`{global_index:05d}.mp4`（5 位补零，例 `00000.mp4`）
- Shot annotation：`{video_id}.shots.json`
- Contact sheet：`{video_id}_contact.jpg`
- Edit prompt：`{video_id}_T{N}_{count:04d}` 作为 `sample_id`
- runs 目录：`runs/{pilot_v1, pilot_v2, edit_prompts_v1, edits_<baseline>_<task>, eval_<baseline>_<task>}/`

### 评测指标公式（在 `DEEP_DIVE.md` §4 和 `RESEARCH_PLAN.md` §4 完整定义）
- 写 metric 实现时直接照抄公式
- 任何 cross-shot ID / style metric 必须配 **ACP-floor**（anti-copy-paste variance penalty），否则 static-frame 提交会占榜
- preservation 必须 source-aligned per-shot（绕开 cross-cut DINO 问题）—— `Preserve_k = DINO(mask_out(source_k), mask_out(edited_k))`

### Snapshot Protocol（任何商用 API 调用必须做）
- 冻结 model identifier 到 `bench_config.yaml`（如 `bytedance/seedance-1.0-pro@2026-04-15`）
- 关 prompt rewriting（Veo 的 `enhance_prompt: false`）
- 无 seed 的 API 跑 K=3 sample，报 mean ± std
- 全部生成视频 + per-call API request/response JSON archive 到 HF Dataset / Zenodo

### 绝不做的事
- **不要用 Seedance 作 edit baseline**（仅作源视频生成器；防数据泄漏）
- **不要对 multi-shot 完整视频跑 VideoScore**（训练集是 single-clip，把 cut 当 inconsistency；只能 per-shot subclip）
- **不要用 FVD 作 headline metric**（已被 demoted，I3D 在新一代生成器上 OOD）
- **不要跨 cut 算 frame-pair similarity 作 consistency**（cut 本来就该差异；ID/style metric 是同 entity 跨 shot 比；preservation 是同 shot 源 vs 编辑后比）

---

## 7. 待核实 / 开放问题

### 必须 PDF 级核实的指标公式（投稿前补做）
- VBench / VBench-2.0 / T2V-CompBench / VideoScore 的 per-dim 人类 Spearman
- MuSS 的 **ACP-Var 准确公式**（abstract 没有；当前按设计原理采纳）
- AniEval voting 机制细节
- DreamFactory Cross-Scene Face/Style Score 公式
- CineTrans / SEINE 转场指标公式
- DIRECT / Mashup-Bench 完整 abstract
- "Soap2Soap" 是否 arXiv 正式发表（找不到，可能是 internal codename）

### 商用 API 必须二次核实
- Sora 2 / Sora 2 Pro 官方 OpenAI 定价（fal/Replicate 是 proxy）
- Sora 2 API deprecation 日期（Replicate 标 2026-09-24，likely 是 next-gen 切换非全停）
- Volcengine ARK 上 Seedance 定价
- Kling / Vidu 官方 dev 定价
- Runway Aleph 最大输入时长 + seed 参数
- Veo 3.1 seed 参数 API 引用
- Sora 2 academic / research access program

### 用户尚未决定
- Benchmark 正式 title（建议 MSEdit-Bench，搜索友好 + 和 MSVBench 对仗）
- 作者顺序 / 合作单位
- Live leaderboard 是否带 submission portal（带的话要反作弊机制）
- 是否额外做一个 MSEdit-Bench 微调的 evaluator（作为 VLM ensemble Spearman 不够时的 fallback）
- 数据 license 细节（CC-BY-4.0 for annotations，per-clip license tag for videos）

---

## 8. 论文坐标 & 关键引用

**目标**：AAAI 2027（一般 8 月初截稿，按 18 周倒推 = Phase 1 必须在 5 月底前启动）

**最强对照论文**（Related Work 必引）：
- **OpenVE-3M / OpenVE-Bench** [arXiv:2512.07826](https://arxiv.org/abs/2512.07826) —— editing 侧最强对照；含 Camera Multi-Shot Edit 子类
- **UniVBench** [arXiv:2602.21835](https://arxiv.org/abs/2602.21835) —— 唯一 multi-shot edit 交集；200 视频 4 任务（我们做 930 一个任务）
- **MovieBench** [arXiv:2411.15262](https://arxiv.org/abs/2411.15262) (CVPR'25) —— 多 shot 数据集典范
- **MSVBench** [arXiv:2602.23969](https://arxiv.org/abs/2602.23969) (ACL'26 Findings) —— 自称 "first comprehensive multi-shot benchmark"
- **EntityBench** [arXiv:2605.15199](https://arxiv.org/abs/2605.15199) —— 长程实体一致性
- **MuSS** [arXiv:2604.23789](https://arxiv.org/abs/2604.23789) —— ACP-Var 来源
- **PRIMEdit / MIVE** [arXiv:2412.12877](https://arxiv.org/abs/2412.12877) —— CIA score 来源

**编辑 baseline**（必跑）：
- TokenFlow [2307.10373](https://arxiv.org/abs/2307.10373)
- AnyV2V [2403.14468](https://arxiv.org/abs/2403.14468)
- VideoGrain [2502.17258](https://arxiv.org/abs/2502.17258) (ICLR'25)
- PRIMEdit [2412.12877](https://arxiv.org/abs/2412.12877)
- EVA [2403.16111](https://arxiv.org/abs/2403.16111)
- OCVE [2504.14335](https://arxiv.org/abs/2504.14335) (CVPR'25)

**Multi-shot 生成器**（反向用作编辑器）：
- HoloCine [2510.20822](https://arxiv.org/abs/2510.20822)
- LCT [2503.10589](https://arxiv.org/abs/2503.10589)
- ShotAdapter [2505.07652](https://arxiv.org/abs/2505.07652) (CVPR'25)
- CineTrans [2508.11484](https://arxiv.org/abs/2508.11484) (ICLR'26)
- VGoT [2412.02259](https://arxiv.org/abs/2412.02259)
- SkyReels-V2 [2504.13074](https://arxiv.org/abs/2504.13074)
- StoryDiffusion [2405.01434](https://arxiv.org/abs/2405.01434) (NeurIPS'24)

**Identity / consistency 原语**：
- IP-Adapter [2308.06721](https://arxiv.org/abs/2308.06721)
- PhotoMaker [2312.04461](https://arxiv.org/abs/2312.04461) (CVPR'24)
- InstantID [2401.07519](https://arxiv.org/abs/2401.07519)
- ConsisID [2411.17440](https://arxiv.org/abs/2411.17440) (CVPR'25)
- OpenS2V-Nexus [2505.20292](https://arxiv.org/abs/2505.20292)

**评测协议**：
- VBench [2311.17982](https://arxiv.org/abs/2311.17982) (NeurIPS'24)
- VBench-2.0 [2503.21755](https://arxiv.org/abs/2503.21755)
- StoryEval [2412.16211](https://arxiv.org/abs/2412.16211) —— VLM unanimous voting 协议来源
- LOVEU-TGVE [2310.16003](https://arxiv.org/abs/2310.16003) —— 单镜头 edit 评测协议参考

**摄影 / 镜头理解**：
- ShotBench [2506.21356](https://arxiv.org/abs/2506.21356) (NeurIPS'25)
- CineTechBench [2505.15145](https://arxiv.org/abs/2505.15145)

**Agentic editing**：
- Soap2Soap [2605.17423](https://arxiv.org/abs/2605.17423) (unverified — 可能是 internal codename)
- DIRECT / Mashup-Bench [2604.04875](https://arxiv.org/abs/2604.04875) (partial verified)

⚠️ **2511.x / 2512.x / 2604.x / 2605.x 的 arXiv ID 需在正式投稿前重新到 arXiv 核验**（部分是 2026 年 paper，要确认 ID 没漂）。

---

## 9. 给 Claude Code 的额外指令

当用户在这个目录下打开你时：

1. **先读 `CLAUDE.md` (本文件) + `HOWTO.md`**。本文件是 scope 决策 / 待办；HOWTO 是命令手册。再按需读 source-of-truth：
   - 任务定义问题 → `RESEARCH_PLAN.md` §2-3
   - 指标公式问题 → `RESEARCH_PLAN.md` §4 或 `DEEP_DIVE.md` §4 或直接读 `mseditbench/metrics/<metric>.py` 的 docstring（公式都在）
   - 数据 / API 问题 → `RESEARCH_PLAN.md` §3, §6 或 `DEEP_DIVE.md` §3
   - 现有 benchmark 对照 → `DEEP_DIVE.md` §2
   - 完整方法库 → `RELATED_WORK_SURVEY.md`
   - 跑 pipeline 的具体命令 → `HOWTO.md`

2. **不要重新讨论已 scope 决策**（见 §3）。如果用户暗示要改方向，先用 AskUserQuestion 确认是否真的要推翻。

3. **不要重做调研**。三份 survey 已经覆盖；如果用户问 "X 方法是什么"，先在 `RELATED_WORK_SURVEY.md` 搜，搜不到再查 arXiv。

4. **不要新建文档**除非用户明确要求。已有 5 份 md（CLAUDE / HOWTO / SURVEY / RELATED / DEEP_DIVE / RESEARCH_PLAN）已经 ~150KB+，再加会冗余。修改既有文档。

5. **不要新建一份并行的 Python 包**。`mseditbench/` 已经搭完整了 7 个子包 + 38 文件 / ~3900 行；新功能加到既有子包，不要另起 `mseditbench2/` 或散落的 script。

6. **进度跟踪**：复杂多步任务用 TaskCreate / TaskUpdate。

7. **commit 习惯**：用户没说要 commit 就不要 commit。这个 repo 是否在 git 里现在未知（环境提示 `Is a git repository: false`），先 `git status` 确认。

8. **mock vs real 后端**：metrics / tracking / identity 都有 mock 后端用作 unit test 和零依赖 smoke。**别忘了用户最终需要 real 后端**——不要把 mock 数字当真实结果汇报。换 real 后端的 flag 见 `HOWTO.md`「Real backends」表。

9. **写代码风格**（来自 base system prompt）：
   - 默认不写注释，除非 WHY 不明显
   - 不为假想未来需求做抽象
   - 不加无用的 error handling
   - 简洁优于完备

---

## 10. 紧急 sanity check (v1 release)

如果你不确定项目状态，跑这几个命令快速确认：

```bash
cd /mnt/hdfs/xjy_hldy/datasets/multi_shot_bench

# 1. 文件齐全？
ls README.md CLAUDE.md HOWTO.md AGENT_BENCH_DESIGN.md
ls mseditbench/ runs/ data/

# 2. Python 包完整 / 测试通过？
python3 -m mseditbench.tests.test_metrics    # 应输出 17/17 passed

# 3. v2_10s 源视频齐？
ls data/source_videos_10s/videos/ | wc -l                # 应 = 30

# 4. v2_10s shot detection 100%？
python3 -c "import json; r=json.load(open('runs/pilot_v2_10s/pilot_report.json')); print(f\"{r['summary']['n_exact_match']}/{r['summary']['n_total']} match\")"

# 5. v2_10s 480 条 prompts 齐？T1-T8 均应为 60
python3 -c "import json; exp={f'T{i}':60 for i in range(1,9)}; [print(t, len(json.load(open(f'runs/edit_prompts_v2_10s/{t}.json'))), 'expected', n) for t,n in exp.items()]"

# 6. v3 leaderboard 出炉？
ls runs/eval_seedance_v2v_v2_10s_v3/*/aggregate.json | wc -l           # 应 = 6
ls runs/eval_seedance_v2v_fast_v2_10s_v3/*/aggregate.json | wc -l      # 应 = 6

# 7. git 状态
git status 2>/dev/null || echo "not a git repo (yet)"
```

v1 release 期望状态：
- 4 份顶层文档：README.md / CLAUDE.md / HOWTO.md / AGENT_BENCH_DESIGN.md（+ 4 份 design surveys）
- `mseditbench/` 50+ 个 .py 文件（含 ee_v3.py / csep_v3.py，v1/v2 已加 DEPRECATED 标）
- `data/source_videos_10s/videos/` 30 个 mp4
- `runs/pilot_v2_10s/` 30/30 shot detection
- `runs/edit_prompts_v2_10s/T{1..8}.json` 共 480 条（T1-T8 各 60）
- `runs/eval_seedance_v2v_{,fast_}v2_10s_v3/` 6 任务 aggregate.json 完整
- 当前阶段：v1 准备 push GitHub；user 后续在另一目录开 agent 方向（v2）

如果状态对得上 ⇒ 等用户的 edit 跑完，跑 metric eval。
如果 edit 还没跑完 ⇒ 不要打扰，关注 `runs/seedance_v2v_edit/` 的 mtime 看进度。
