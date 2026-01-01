#!/bin/bash
# E6 · 尾延迟的跑法（README 第 1 节）。Mac 本机、单线程；引擎是 E1 的二进制加 --latency（exp/e1-main/src/trend.cpp，默认关）。
# 用法：caffeinate -i bash exp/e6-latency/run_e6.sh [all|smoke]   → handoff/e6_latency.tsv、handoff/e6_dist.tsv（smoke 写进 logs/）
# 每 (行 × 臂) 一个进程：预热 1 遍 + 逐事件计时 3 遍；E1 里单次计时的格（偏离 1，探测遍 ≥ 60 s）不预热、逐事件计时 1 遍
set -euo pipefail
E6="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E6}/../e1-main/run_e1.sh"   # BIN、dfile、qp、armargs、C_FIXED
E1T="${E6}/../e1-main/handoff/e1_times.tsv"
ROWS6="wpi_hold pamap2_hold binance_hold porto_hold"
ARMS6="OPP M A2 A4"
W6=600
HEAD6="arm	data	split	agg	W	pass	seconds	events	mean_ns	p50_ns	p99_ns	p999_ns	p9999_ns	max_ns	n0	p50_0	p99_0	max_0	n1	p50_1	p99_1	max_1	n2	p50_2	p99_2	max_2	n3	p50_3	p99_3	max_3	clock_med_ns	clock_tick_ns	maxrss_kb	switches	compactions	checksum"

# E1 里这一格是不是单次计时（reps = 1）
e1_single() {  # <臂> <数据_切分>
    awk -F'\t' -v a="$1" -v d="${2%_*}" -v sp="${2##*_}" -v w="${W6}" 'NR > 1 && $1 == a && $2 == d && $3 == sp && $4 == "COUNT" && $5 == w && $18 == 1 { f = 1 } END { exit !f }' "${E1T}"
}

run_cell6() {  # <表> <分布表> <数据_切分> <臂> [--limit N]
    local tab="$1" dist="$2" ds="$3" arm="$4"; shift 4
    local op s f out wu=1 rp=3
    read -r op s <<< "$(qp "${ds}")"
    f="${E6}/logs/lat_${arm}_${ds}.tmp"
    if e1_single "${arm}" "${ds}"; then wu=0; rp=1; fi
    # shellcheck disable=SC2046
    out="$("${BIN}" $(armargs "${arm}") --data "$(dfile "${ds}")" --W $((W6 * 1000000)) --s $((s * 1000000)) --op "${op}" --agg COUNT \
        --warmup "${wu}" --reps "${rp}" --latency "${f}" "$@")"
    echo "${out}" | awk -F'\t' -v a="${arm}" -v d="${ds%_*}" -v sp="${ds##*_}" -v w="${W6}" '
        $1 == "lat" { m = $2; L[m] = $3 "\t" $4 "\t" $5 "\t" $6 "\t" $7 "\t" $8 "\t" $9 "\t" $10 }
        $1 == "latcat" { C[$2, $3] = $4 "\t" $5 "\t" $6 "\t" $7 }
        $1 == "clock" { ck = $2 "\t" $3 }
        $1 != "lat" && $1 != "latcat" && $1 != "clock" { v[$1] = $2 }
        END { for (i = 1; i <= m; i++) printf "%s\t%s\t%s\tCOUNT\t%s\t%d" "\t%s\t%s\t%s\t%s\t%s" "\t%s\t%s\t%s\t%s\t%s\n", a, d, sp, w, i, L[i],
              C[i, 0], C[i, 1], C[i, 2], C[i, 3], ck, v["maxrss_kb"], v["switches"], v["compactions"], v["checksum"] }' >> "${tab}"
    awk -F'\t' -v a="${arm}" -v d="${ds%_*}" -v w="${W6}" '{ print a "\t" d "\t" w "\t" $0 }' "${f}" >> "${dist}"
    rm -f "${f}"
    echo "$(date '+%T') ${ds} ${arm} 预热 ${wu} 遍、逐事件计时 ${rp} 遍" >&2
}

main6() {
    local mode="${1:-all}" tab dist ds arm lim=()
    mkdir -p "${E6}/logs" "${E6}/handoff"
    make -s -C "${E6}/../e1-main" out/trend
    {
        echo "# $(date '+%F %T')  mode=${mode}  C_FIXED=${C_FIXED}  HEAD=$(git -C "${E6}" rev-parse --short HEAD)  dirty=$(git -C "${E6}" status --porcelain -- ../e1-main/src ../e1-main/Makefile . | wc -l | tr -d ' ')"
        /usr/bin/clang++ --version | head -1
        sysctl -n machdep.cpu.brand_string
        pmset -g batt | head -1
    } > "${E6}/logs/env_${mode}.txt"
    if [ "${mode}" = smoke ]; then tab="${E6}/logs/e6_smoke.tsv"; dist="${E6}/logs/e6_smoke_dist.tsv"; lim=(--limit 2000)
    else tab="${E6}/logs/e6_latency.part.tsv"; dist="${E6}/logs/e6_dist.part.tsv"; fi
    echo "${HEAD6}" > "${tab}"
    printf "arm\tdata\tW\tkind\tpass\tf1\tf2\tf3\tf4\tf5\tf6\n" > "${dist}"
    for ds in ${ROWS6}; do for arm in ${ARMS6}; do
        run_cell6 "${tab}" "${dist}" "${ds}" "${arm}" "${lim[@]+"${lim[@]}"}"
    done; done
    if [ "${mode}" != smoke ]; then mv "${tab}" "${E6}/handoff/e6_latency.tsv"; mv "${dist}" "${E6}/handoff/e6_dist.tsv"; fi
    echo "$(date '+%T') E6 ${mode} 完" >&2
}

main6 "${1:-all}"
