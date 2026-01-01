#!/bin/bash
# E2 · 跑法（README 第 1 节、第 2 节）。二进制、登记表、计时口径用 E1 的（../e1-main/run_e1.sh：3 进程中位、短行加长、慢行单次计时）。
# 用法：bash run_e2.sh w      W 扫：4 份数据 × W ∈ {1, 2, 5, 10, 30, 60} 分 × COUNT × {OPP, M} → handoff/e2_times.tsv（替换 xnum = 1000 的行）
#       bash run_e2.sh sel    选择度扫：W = 10 分，按 handoff/e2_sel.tsv（prep_e2.py）里每份数据不同的 X → 同上（替换 xnum ≠ 1000 的行）
#                             X = 1.000 的点就是 W 扫的 W = 10 分那一行（同一实验、同一口径），不重跑
set -euo pipefail
E2H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E2H}/../e1-main/run_e1.sh"   # 引入后 HERE 指 e1-main；本实验的目录用 E2H
E2_DATA="wpi_hold pamap2_hold porto_hold binance_hold"   # Binance 最慢，放最后
WS2="60 120 300 600 1800 3600"

main() {
    local mode="${1:-}"
    make -s -C "${E2H}/../e1-main" out/trend
    mkdir -p "${E2H}/handoff" "${E2H}/logs"
    {
        echo "# $(date '+%F %T')  mode=${mode}  C_FIXED=${C_FIXED}  HEAD=$(git -C "${E2H}" rev-parse --short HEAD)  dirty=$(git -C "${E2H}" status --porcelain -- ../e1-main/src ../e1-main/Makefile | wc -l | tr -d ' ')"
        /usr/bin/clang++ --version | head -1; sysctl -n machdep.cpu.brand_string; pmset -g batt | head -1
    } > "${E2H}/logs/env_${mode}.txt"
    local f="${E2H}/handoff/e2_times.tsv" tmp="${E2H}/logs/e2_times.tmp"
    case "${mode}" in
    w)
        if [ -f "${f}" ]; then awk -F'\t' 'NR==1 || $24!="1000"' "${f}" > "${tmp}"; else echo "${HEAD}" > "${tmp}"; fi
        for ds in ${E2_DATA}; do for W in ${WS2}; do
            run_row "${ds}" COUNT "${W}" "OPP M" "${C_FIXED}" 1000 >> "${tmp}"
        done; done ;;
    sel)
        [ -f "${E2H}/handoff/e2_sel.tsv" ] || { echo "先跑 prep_e2.py" >&2; return 1; }
        if [ -f "${f}" ]; then awk -F'\t' 'NR==1 || $24=="1000"' "${f}" > "${tmp}"; else echo "${HEAD}" > "${tmp}"; fi
        for ds in ${E2_DATA}; do
            for x in $(awk -F'\t' -v d="${ds%_*}" '$1==d && $3!="1000"{print $3}' "${E2H}/handoff/e2_sel.tsv" | sort -un); do
                run_row "${ds}" COUNT 600 "OPP M" "${C_FIXED}" "${x}" >> "${tmp}"
            done
        done ;;
    *) echo "用法：bash run_e2.sh w|sel" >&2; return 1 ;;
    esac
    mv "${tmp}" "${f}"
}

main "${1:-}"
