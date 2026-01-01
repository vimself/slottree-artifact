#!/bin/bash
# E8 · E7 第二平台的 M 臂重跑（README 第 1 节）：E1 run_row 的口径（探测 → 3 进程交错、--autopasses、第 1 个进程带 --work、探测遍 ≥ 60 s 单次计时），
# 只跑 M（v2，B = 1024、c = 2），D 取 v1 E7 表里该行的值（E7 30 行都是 1）。由 ws_e8.sh 逐份数据调用；也能在 Mac 上单独跑（桩测）。
# 用法：bash exp/e8-inpane/run_e7v2.sh <数据_切分> <输出 tsv>   （输出不存在就先写表头；存在就追加）；窗格内切换记进 <输出> 同目录的 e7_inpane_v2.tsv
set -euo pipefail
E8H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ds="$1" out="$2"
SIDE="$(cd "$(dirname "${out}")" && pwd)/e7_inpane_v2.tsv"
E8_LIB=1 source "${E8H}/run_e8.sh"   # row8、run_one8、BIN（= exp/e8-inpane/out/trend）、WS、AGGS、HEAD
E7T="${E8H}/../e7-platform/handoff/e7_times.tsv"
[ -x "${BIN}" ] || { echo "没有引擎 ${BIN}（ws_e8.sh 的 build 步骤先编）" >&2; exit 1; }
[ -s "${out}" ] || echo "${HEAD}" > "${out}"
for W in ${WS}; do for g in ${AGGS}; do
    row8 e7 "${E7T}" "${ds}" "${g}" "${W}" "M" 1000 >> "${out}"
done; done
