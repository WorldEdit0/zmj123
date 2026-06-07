#!/usr/bin/env bash
# Unified MSEdit-Bench evaluation launcher.
# 中文注释：这是你日常评测最应该使用的统一入口。
# 它负责设置本地权重路径、选择 GPU、按任务调用 run_eval.py，
# 最后调用 summarize.py 汇总成 summary.csv 和 summary.md。
#
# Modes:
#   smoke [TASK...]   Run a 1-prompt end-to-end smoke test. Defaults to all tasks.
#   task TASK...      Run full eval for the listed tasks.
#   all              Run full eval for T1..T8.
#   summary          Rebuild summary.csv and summary.md from aggregate.json files.
#
# Common overrides:
#   GPU=7 BACKEND_VLM=qwen3vl EE_V3_FRAME_PAIRS=3 bash scripts/eval_suite.sh smoke T2
#   EVAL_OUT_ROOT=runs/eval_my_model BASELINE_VIDEOS_ROOT=runs/my/videos bash scripts/eval_suite.sh all

set -euo pipefail

MODE="${1:-help}"
if [[ "$#" -gt 0 ]]; then
  # 中文注释：第一个位置参数是模式 smoke/task/all/summary，剩下参数才是任务 ID。
  shift
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/eval_suite.sh smoke [TASK...]
  bash scripts/eval_suite.sh task TASK...
  bash scripts/eval_suite.sh all
  bash scripts/eval_suite.sh summary

Examples:
  GPU=7 BACKEND_VLM=qwen3vl bash scripts/eval_suite.sh smoke T2
  GPU=7 BACKEND_VLM=qwen3vl EE_V3_FRAME_PAIRS=3 bash scripts/eval_suite.sh smoke
  GPUS=0,1,2,3 NUM_SHARDS=4 BACKEND_VLM=qwen3vl bash scripts/eval_suite.sh task T1 T2 T3
  BACKEND_VLM=qwen3vl EVAL_OUT_ROOT=runs/eval_qwen3vl bash scripts/eval_suite.sh all

Key env vars:
  BASELINE_NAME          default: seedance_v2v
  BASELINE_VIDEOS_ROOT   default: runs/seedance_v2v_edit_v2_10s/videos
  EVAL_OUT_ROOT          default: runs/eval_smoke_${BASELINE_NAME}_${SNAPSHOT_ID} for smoke,
                                   runs/eval_${BASELINE_NAME}_${SNAPSHOT_ID} otherwise
  PROMPTS_DIR            default: runs/edit_prompts_v2_10s
  SOURCE_VIDEOS_ROOT     default: data/source_videos_10s/videos
  BACKEND_VLM            default: qwen3vl
  BACKEND_MASK           default: sam3
  BACKEND_PSQ            default: pyiqa
  BACKEND_SHOT           default: omnishotcut
  NUM_SAMPLES            default: 3, number of k outputs per prompt to score
  NUM_SHARDS             default: 1
  GPU                    default: 7
  GPUS                   default: 0,1,2,3,4,5,6,7 for NUM_SHARDS>1
  CLEAN                  default: 1, remove per-task output dirs before running
  EE_V3_FRAME_PAIRS      default: 3, source/edit frame pairs per applicable shot
  QWEN3VL_IMAGE_SIZE     default: 384
  QWEN3VL_MAX_NEW_TOKENS default: 8
EOF
}

if [[ "${MODE}" == "help" || "${MODE}" == "-h" || "${MODE}" == "--help" ]]; then
  usage
  exit 0
fi

BASELINE_NAME="${BASELINE_NAME:-seedance_v2v}"
# 中文注释：下面这些环境变量都可以在命令前覆盖，例如
# BASELINE_VIDEOS_ROOT=runs/my_model/videos bash scripts/eval_suite.sh all
BASELINE_VIDEOS_ROOT="${BASELINE_VIDEOS_ROOT:-runs/seedance_v2v_edit_v2_10s/videos}"
PROMPTS_DIR="${PROMPTS_DIR:-runs/edit_prompts_v2_10s}"
SOURCE_VIDEOS_ROOT="${SOURCE_VIDEOS_ROOT:-data/source_videos_10s/videos}"
SNAPSHOT_ID="${SNAPSHOT_ID:-qwen3vl_v2_10s}"
BACKEND_DINO="${BACKEND_DINO:-v2s}"
BACKEND_VLM="${BACKEND_VLM:-qwen3vl}"
BACKEND_MASK="${BACKEND_MASK:-sam3}"
BACKEND_PSQ="${BACKEND_PSQ:-pyiqa}"
BACKEND_SHOT="${BACKEND_SHOT:-omnishotcut}"
NUM_SAMPLES="${NUM_SAMPLES:-3}"
NUM_SHARDS="${NUM_SHARDS:-1}"
GPU="${GPU:-7}"
GPUS="${GPUS:-0,1,2,3,4,5,6,7}"
LIMIT="${LIMIT:-0}"
CLEAN="${CLEAN:-1}"

export MSEDITBENCH_CKPT_ROOT="${MSEDITBENCH_CKPT_ROOT:-${REPO_ROOT}/mseditbench/ckpt}"
# 中文注释：统一把各模型权重路径传给 Python 后端：
# SAM3、Qwen3-VL 都会从这些路径加载。
export SAM3_CKPT="${SAM3_CKPT:-${MSEDITBENCH_CKPT_ROOT}/sam3/sam3.pt}"
export QWEN3VL_MODEL_PATH="${QWEN3VL_MODEL_PATH:-${REPO_ROOT}/Qwen3-VL/ckpt}"
export EE_V3_FRAME_PAIRS="${EE_V3_FRAME_PAIRS:-3}"
export QWEN3VL_IMAGE_SIZE="${QWEN3VL_IMAGE_SIZE:-384}"
export QWEN3VL_MAX_NEW_TOKENS="${QWEN3VL_MAX_NEW_TOKENS:-8}"
if [[ "${BACKEND_VLM}" == "qwen3vl" || "${BACKEND_VLM}" == "qwen" ]]; then
  # 中文注释：本地 Qwen3-VL 是单个 GPU 模型，评测时串行生成更稳定。
  export VLM_MAX_WORKERS="${VLM_MAX_WORKERS:-1}"
else
  export VLM_MAX_WORKERS="${VLM_MAX_WORKERS:-8}"
fi

if [[ "${MODE}" == "smoke" ]]; then
  # 中文注释：smoke 默认只跑 1 条 prompt，用来快速验证链路是否可跑通。
  LIMIT="${LIMIT:-1}"
  if [[ "${LIMIT}" == "0" ]]; then
    LIMIT=1
  fi
  EVAL_OUT_ROOT="${EVAL_OUT_ROOT:-runs/eval_smoke_${BASELINE_NAME}_${SNAPSHOT_ID}}"
else
  EVAL_OUT_ROOT="${EVAL_OUT_ROOT:-runs/eval_${BASELINE_NAME}_${SNAPSHOT_ID}}"
fi

DEFAULT_TASKS=(T1 T2 T3 T4 T5 T6 T7 T8)

case "${MODE}" in
  smoke)
    if [[ "$#" -gt 0 ]]; then
      TASKS=("$@")
    else
      TASKS=("${DEFAULT_TASKS[@]}")
    fi
    ;;
  task)
    if [[ "$#" -eq 0 ]]; then
      echo "Mode 'task' requires at least one task." >&2
      exit 2
    fi
    TASKS=("$@")
    ;;
  all)
    TASKS=("${DEFAULT_TASKS[@]}")
    ;;
  summary)
    TASKS=()
    ;;
  *)
    TASKS=()
    ;;
esac

prepare_out_dir() {
  local out_dir="$1"
  if [[ "${CLEAN}" == "1" ]]; then
    # 中文注释：默认清理本次任务输出，避免旧的 *.agg.json 混入新汇总。
    # 为了防止误删，只允许清理 /tmp 或 runs 下的目录。
    case "${out_dir}" in
      /tmp/*|runs/*|"${REPO_ROOT}"/runs/*)
        rm -rf -- "${out_dir}"
        ;;
      *)
        echo "Refusing CLEAN=1 outside runs/ or /tmp: ${out_dir}" >&2
        exit 2
        ;;
    esac
  fi
  mkdir -p "${out_dir}"
}

gpu_for_shard() {
  local shard="$1"
  # 中文注释：多分片时按 shard_id 轮询分配 GPU，例如 8 shard 对 8 张卡。
  IFS=',' read -ra GPU_ARR <<< "${GPUS}"
  local n="${#GPU_ARR[@]}"
  echo "${GPU_ARR[$(( shard % n ))]}"
}

run_standard_task() {
  local task="$1"
  local out_dir="${EVAL_OUT_ROOT}/${task}"
  prepare_out_dir "${out_dir}"
  echo "================ ${MODE} ${BASELINE_NAME} ${task} ================"
  date

  local limit_args=()
  if [[ "${LIMIT}" != "0" ]]; then
    limit_args=(--limit "${LIMIT}")
  fi

  if [[ "${NUM_SHARDS}" == "1" ]]; then
    # 中文注释：单 GPU/单进程路径，适合 smoke 或单任务调试。
    CUDA_VISIBLE_DEVICES="${GPU}" python3 -m mseditbench.eval.run_eval \
      --prompts_json "${PROMPTS_DIR}/${task}.json" \
      --baseline_dir "${BASELINE_VIDEOS_ROOT}/${task}" \
      --videos_root "${SOURCE_VIDEOS_ROOT}" \
      --output_dir "${out_dir}" \
      --baseline "${BASELINE_NAME}" --snapshot_id "${SNAPSHOT_ID}" \
      --backend_dino "${BACKEND_DINO}" \
      --backend_vlm "${BACKEND_VLM}" --backend_shot "${BACKEND_SHOT}" \
      --backend_mask "${BACKEND_MASK}" --backend_psq "${BACKEND_PSQ}" \
      --num_samples "${NUM_SAMPLES}" \
      "${limit_args[@]}"
  else
    # 中文注释：多 GPU 路径。每个 shard 只处理 prompts[shard_id::num_shards]，
    # 所有 shard 写到同一个任务目录，最后 merge_shards.py 合成 aggregate.json。
    for (( shard=0; shard<NUM_SHARDS; shard++ )); do
      local gpu
      gpu="$(gpu_for_shard "${shard}")"
      CUDA_VISIBLE_DEVICES="${gpu}" python3 -m mseditbench.eval.run_eval \
        --prompts_json "${PROMPTS_DIR}/${task}.json" \
        --baseline_dir "${BASELINE_VIDEOS_ROOT}/${task}" \
        --videos_root "${SOURCE_VIDEOS_ROOT}" \
        --output_dir "${out_dir}" \
        --baseline "${BASELINE_NAME}" --snapshot_id "${SNAPSHOT_ID}" \
        --backend_dino "${BACKEND_DINO}" \
        --backend_vlm "${BACKEND_VLM}" --backend_shot "${BACKEND_SHOT}" \
        --backend_mask "${BACKEND_MASK}" --backend_psq "${BACKEND_PSQ}" \
        --num_samples "${NUM_SAMPLES}" \
        --num_shards "${NUM_SHARDS}" --shard_id "${shard}" \
        "${limit_args[@]}" \
        > "${out_dir}/shard_${shard}.log" 2>&1 &
    done
    wait
    python3 -m mseditbench.eval.merge_shards --output_dir "${out_dir}"
  fi
  echo ""
}

summarize() {
  # 中文注释：读取每个任务目录里的 aggregate.json，输出最终 CSV/Markdown 表。
  python3 -m mseditbench.eval.summarize \
    --eval_root "${EVAL_OUT_ROOT}" \
    --output_csv "${EVAL_OUT_ROOT}/summary.csv" \
    --output_md "${EVAL_OUT_ROOT}/summary.md"
}

case "${MODE}" in
  smoke|task|all)
    for task in "${TASKS[@]}"; do
      run_standard_task "${task}"
    done
    summarize
    ;;
  summary)
    summarize
    ;;
  *)
    usage
    exit 2
    ;;
esac
