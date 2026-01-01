#!/bin/bash
# E1 · 偏离 2 的重跑（README 第 3 节偏离 2，补充实验 ①）：只重跑 Binance 留出 COUNT W = 10 分这一格的全部六个臂，
# 口径与 run_e1.sh 完全相同（run_row：探测 → D → 3 进程 ×「进程 → 臂」交错、--autopasses、探测遍 ≥ 60 s 的格单次计时）。
# 产出 handoff/e1_rerun_binance.tsv（列同 e1_times.tsv）；不碰 e1_times.tsv。环境记进 logs/env_rerun_binance.txt。
# 用法：caffeinate -i bash exp/e1-main/rerun_e1.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${HERE}/run_e1.sh"
make -s -C "${HERE}" out/trend
envlog rerun_binance
out="${HERE}/handoff/e1_rerun_binance.tsv" tmp="${HERE}/logs/e1_rerun_binance.tmp"
echo "${HEAD}" > "${tmp}"
run_row binance_hold COUNT 600 "${ARMS}" "${C_FIXED}" >> "${tmp}"
mv "${tmp}" "${out}"
echo "$(date '+%T') 重跑完 → ${out}" >&2
