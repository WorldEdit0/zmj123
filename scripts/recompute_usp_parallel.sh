#!/usr/bin/env bash
# Recompute USP/TAC on existing eval directories.
#
# Usage:
#   bash scripts/recompute_usp_parallel.sh PRO_EVAL_ROOT FAST_EVAL_ROOT

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PRO_ROOT="${1:-runs/eval_seedance_v2v_v2_10s_v3}"
FAST_ROOT="${2:-runs/eval_seedance_v2v_fast_v2_10s_v3}"
PROMPTS_DIR="${PROMPTS_DIR:-runs/edit_prompts_v2_10s}"
SOURCE_VIDEOS_ROOT="${SOURCE_VIDEOS_ROOT:-data/source_videos_10s/videos}"
BACKEND_DINO="${BACKEND_DINO:-v2s}"
BACKEND_SHOT="${BACKEND_SHOT:-omnishotcut}"
TASKS=(T1 T2 T3 T4 T5 T6 T7 T8)

cd "${REPO_ROOT}"

run_one() {
    local out_dir="$1"
    local task="$2"
    if [ ! -d "$out_dir/$task" ]; then
        echo "skip $out_dir/$task (missing)"
        return
    fi
    python3 -m mseditbench.eval.recompute_usp \
        --output_dir "$out_dir/$task" \
        --prompts_json "${PROMPTS_DIR}/$task.json" \
        --videos_root "${SOURCE_VIDEOS_ROOT}" \
        --backend_dino "${BACKEND_DINO}" \
        --backend_shot "${BACKEND_SHOT}" \
        > "$out_dir/$task/recompute_usp.log" 2>&1
    echo "  done: $out_dir/$task"
}

echo "================ Recomputing USP/TAC on Pro and Fast ================"
date
for TASK in "${TASKS[@]}"; do
    run_one "$PRO_ROOT"  "$TASK" &
    run_one "$FAST_ROOT" "$TASK" &
done
wait
date
echo ""
echo "================ Updated USP/TAC summary ================"
for ROOT in "$PRO_ROOT" "$FAST_ROOT"; do
    echo "--- $ROOT ---"
    for T in T1 T2 T3 T4 T5 T6 T7 T8; do
        if [ -f "$ROOT/$T/aggregate.json" ]; then
            python3 -c "
import json
d = json.load(open('$ROOT/$T/aggregate.json'))
usp_m = d.get('usp_mean'); usp_s = d.get('usp_std')
tac_m = d.get('tac_mean'); tac_s = d.get('tac_std')
def fmt(name, m, s):
    return f'{name}={m:.3f}±{s:.3f}' if isinstance(m, float) and isinstance(s, float) else f'{name}=—'
print('  $T: ' + fmt('USP', usp_m, usp_s) + '  ' + fmt('TAC', tac_m, tac_s))
"
        fi
    done
done
