#!/bin/bash
# E7 · 第二平台的计时（README 第 1 节）：E1 的 run_row 原样（探测 → D → 3 进程 ×「进程 → 臂」交错、--autopasses、探测遍 ≥ 60 s 单次计时），
# 臂只取 OPP 与 M（c = 2）。由 ws_e7.sh 逐份数据调用；也能在 Mac 上单独跑（桩测）。
# 用法：bash exp/e7-platform/run_e7.sh <数据_切分> <输出 tsv>     （输出不存在就先写表头；存在就追加）
set -euo pipefail
E7="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E7}/../e1-main/run_e1.sh"   # BIN、run_row、HEAD、WS、AGGS、C_FIXED
ds="$1" out="$2"
[ -x "${BIN}" ] || { echo "没有引擎 ${BIN}（ws_e7.sh 的 build 步骤先编）" >&2; exit 1; }
[ -s "${out}" ] || echo "${HEAD}" > "${out}"
for W in ${WS}; do for g in ${AGGS}; do
    run_row "${ds}" "${g}" "${W}" "OPP M" "${C_FIXED}" >> "${out}"
done; done
