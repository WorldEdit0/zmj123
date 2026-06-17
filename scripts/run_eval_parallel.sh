#!/usr/bin/env bash
# Parallel metric eval: shard prompts across 8 GPUs, one process per GPU.
#
# Each process:
#   - CUDA_VISIBLE_DEVICES=N   (only sees one GPU)
#   - --shard_id N --num_shards 8
# Total VLM concurrency = 8 processes × VLM_MAX_WORKERS (default 8) = 64.
#
# Usage:
#   bash scripts/run_eval_parallel.sh T1            # one task, 8-way parallel
#   bash scripts/run_eval_parallel.sh T1 T2 T3 ...  # tasks run sequentially,
#                                                   # 8 GPUs in parallel within each
#
# After all shards finish for a task, runs merge_shards.py to build the
# final aggregate.json from the per-prompt .agg.json files.

set -euo pipefail

TASKS=("$@")
if [ ${#TASKS[@]} -eq 0 ]; then
    TASKS=(T1 T2 T3 T4 T5 T6 T7 T8)
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Override via env to point at a different baseline. Defaults to local v2_10s data.
BASELINE_NAME="${BASELINE_NAME:-seedance_v2v}"
BASELINE_VIDEOS_ROOT="${BASELINE_VIDEOS_ROOT:-runs/seedance_v2v_edit_v2_10s/videos}"
EVAL_OUT_ROOT="${EVAL_OUT_ROOT:-runs/eval_seedance_v2v_v2_10s_v3}"
PROMPTS_DIR="${PROMPTS_DIR:-runs/edit_prompts_v2_10s}"
SOURCE_VIDEOS_ROOT="${SOURCE_VIDEOS_ROOT:-data/source_videos_10s/videos}"
SNAPSHOT_ID="${SNAPSHOT_ID:-v2_10s_v3}"
# Production defaults: real backends across the board. Override to "none"/"mock"
# only when smoke-testing.
BACKEND_MASK="${BACKEND_MASK:-sam3}"
BACKEND_PSQ="${BACKEND_PSQ:-pyiqa}"
BACKEND_VLM="${BACKEND_VLM:-seed}"
BACKEND_DINO="${BACKEND_DINO:-v2s}"
BACKEND_SHOT="${BACKEND_SHOT:-omnishotcut}"
METRICS="${METRICS:-all}"

NEEDS_VLM=0
if [[ "${METRICS}" == "all" || "${METRICS}" == *"ee_v3"* || "${METRICS}" == *"csep_v3"* ]]; then
    NEEDS_VLM=1
fi

if [[ "${NEEDS_VLM}" == "1" && "${BACKEND_VLM}" == "seed" && -z "${ARK_API_KEY:-}" ]]; then
    echo "Set ARK_API_KEY env var first, or run with BACKEND_VLM=qwen3vl for local VLM."
    exit 1
fi

export MSEDITBENCH_CKPT_ROOT="${MSEDITBENCH_CKPT_ROOT:-${REPO_ROOT}/mseditbench/ckpt}"
export SAM3_CKPT="${SAM3_CKPT:-${MSEDITBENCH_CKPT_ROOT}/sam3/sam3.pt}"
export QWEN3VL_MODEL_PATH="${QWEN3VL_MODEL_PATH:-${REPO_ROOT}/Qwen3-VL/ckpt}"

# 8 processes × 8 VLM workers each = 64 concurrent VLM calls (per-account TPM still applies)
NUM_SHARDS=${NUM_SHARDS:-8}
if [[ "${BACKEND_VLM}" == "qwen3vl" || "${BACKEND_VLM}" == "qwen" ]]; then
    export VLM_MAX_WORKERS="${VLM_MAX_WORKERS:-1}"
else
    export VLM_MAX_WORKERS="${VLM_MAX_WORKERS:-8}"
fi

cd "${REPO_ROOT}"

for TASK_ID in "${TASKS[@]}"; do
    OUT_DIR="${EVAL_OUT_ROOT}/${TASK_ID}"
    mkdir -p "${OUT_DIR}"
    echo "================ Eval ${BASELINE_NAME} ${TASK_ID} (${NUM_SHARDS}-way parallel) ================"
    date

    # Launch one process per shard (one GPU each)
    for (( SHARD=0; SHARD < ${NUM_SHARDS}; SHARD++ )); do
        GPU=$(( SHARD % 8 ))
        CUDA_VISIBLE_DEVICES=${GPU} python3 -m mseditbench.eval.run_eval \
            --prompts_json "${PROMPTS_DIR}/${TASK_ID}.json" \
            --baseline_dir "${BASELINE_VIDEOS_ROOT}/${TASK_ID}" \
            --videos_root "${SOURCE_VIDEOS_ROOT}" \
            --output_dir "${OUT_DIR}" \
            --baseline ${BASELINE_NAME} --snapshot_id ${SNAPSHOT_ID} \
            --backend_dino ${BACKEND_DINO} --backend_vlm ${BACKEND_VLM} \
            --backend_shot ${BACKEND_SHOT} \
            --backend_mask ${BACKEND_MASK} --backend_psq ${BACKEND_PSQ} \
            --metrics ${METRICS} \
            --num_samples ${NUM_SAMPLES:-3} \
            --num_shards ${NUM_SHARDS} --shard_id ${SHARD} \
            > "${OUT_DIR}/shard_${SHARD}.log" 2>&1 &
    done

    # Wait for all shards
    wait
    echo "  All ${NUM_SHARDS} shards finished."

    # Merge per-prompt .agg.json into final aggregate.json
    python3 -m mseditbench.eval.merge_shards --output_dir "${OUT_DIR}"
    date
    echo ""
done

echo "================ ALL DONE ================"
date
