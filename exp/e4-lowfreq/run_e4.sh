#!/bin/bash
# E4 · 闸与开发段跑法（README 第 1 节开发段、第 2.3 节）。二进制与登记表用 E1 的（../e1-main/run_e1.sh）。Mac 本机、单线程。
# 用法：bash run_e4.sh gate    = E1 的闸 (a)(b)(c)
#       bash run_e4.sh dev     开发段 16 行 × c 的 7 档，只跑 M，每次 1 预热 + 5 遍、单进程 → handoff/e4_dev.tsv
# 留出段不另跑：compare_e4.py hold 读 ../e1-main/handoff/e1_times.tsv。
set -euo pipefail
E4H="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E4H}/../e1-main/run_e1.sh"   # 引入后 HERE 指 e1-main；本实验的目录用 E4H
CS="0.5 1 1.5 2 3 4 6"
# 开发段定下的 c（README 第 3 节）：C_FIXED = 2，写在 ../e1-main/run_e1.sh，E1 / E2 / 留出段共用
# 开发段的行：WPI 开发 × W ∈ {1, 2, 5} 分、PAMAP2 subject101–104 × {1, 2} 分、Intel Lab × {5, 10, 30} 分；× COUNT / SUM
DEV_ROWS="wpi_dev:60 wpi_dev:120 wpi_dev:300 pamap2_dev:60 pamap2_dev:120 intel_dev:300 intel_dev:600 intel_dev:1800"

main() {
    local mode="${1:-}"
    make -s -C "${E4H}/../e1-main" out/trend
    case "${mode}" in
    gate) bash "${E4H}/../e1-main/tests/run_tests.sh" ;;
    dev)
        mkdir -p "${E4H}/handoff" "${E4H}/logs"
        {
            echo "# $(date '+%F %T')  mode=dev  HEAD=$(git -C "${E4H}" rev-parse --short HEAD)  dirty=$(git -C "${E4H}" status --porcelain -- ../e1-main/src ../e1-main/Makefile | wc -l | tr -d ' ')"
            /usr/bin/clang++ --version | head -1; sysctl -n machdep.cpu.brand_string; pmset -g batt | head -1
        } > "${E4H}/logs/env_dev.txt"
        local f="${E4H}/handoff/e4_dev.tsv" tmp="${E4H}/logs/e4_dev.tmp"
        echo "${HEAD}" > "${tmp}"
        for rw in ${DEV_ROWS}; do for g in ${AGGS}; do for c in ${CS}; do
            REPS_FIXED=5 run_one M "${rw%:*}" "${g}" "${rw#*:}" 1 1 1 "${c}" 1000 -- --arm M --c "${c}" >> "${tmp}"
            echo "$(date '+%T') dev ${rw} ${g} c=${c}" >&2
        done; done; done
        mv "${tmp}" "${f}" ;;
    *) echo "用法：bash run_e4.sh gate|dev" >&2; return 1 ;;
    esac
}

main "${1:-}"
