#!/bin/bash
# E5 · 合成扩展性的跑法（README 第 1 节）。Mac 本机、单线程、单进程；引擎是 E1 的二进制（exp/e1-main/out/trend），臂参数同 E1。
# 用法：caffeinate -i bash exp/e5-synth/run_e5.sh [all|smoke]   → handoff/e5_times.tsv（smoke：只跑 3 格写进 logs/，桩测用）
# 每格每臂：探测遍（预热 1、计时 0）→ < 60 s：新进程 1 遍预热 + 3 遍计时；≥ 60 s：新进程不预热计时 1 遍（同 E1 偏离 1）
# OPP 另有跳过规则：预计单遍 > 600 s 不跑；预计 ≥ 60 s 不探测、直接计时 1 遍（预计的算法见 pred_opp）
set -euo pipefail
E5="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E5}/../e1-main/run_e1.sh"   # BIN、armargs、lt、C_FIXED、TAU5
W_US=600000000
SLOW5=60
SKIP5=600
ARMS5="OPP M A4 A5"
HEAD5="set	dist	n	G	burst	k	arm	events	mode	pred_s	pass	seconds	maxrss_kb	switches	compactions	idx_events	checksum"

# 格的清单：「组别 流名 k」。S1 = 分布 × n × k（G = 1、无突发）；S2 = 组数（rw、k = 6）；S3 = 突发对照（rw、k = 6）
cells() {
    local d n k g b
    for d in u rw ht; do for n in 100 1000 10000 100000 1000000; do for k in 1 2 6 30; do echo "S1 ${d}-n${n}-g1-b0 ${k}"; done; done; done
    for g in 10 100; do for n in 1000 10000; do echo "S2 rw-n${n}-g${g}-b0 6"; done; done
    for g in 1 10; do for n in 10 100 1000; do for b in 0 1; do echo "S3 rw-n${n}-g${g}-b${b} 6"; done; done; done
}
smoke_cells() { echo "S1 rw-n100-g1-b0 6"; echo "S2 rw-n1000-g10-b0 6"; echo "S3 rw-n10-g1-b1 6"; }

stream() {  # 流名 → 文件（没有就生成；生成记录追加进 logs/gen.txt）
    local f="${E5}/data/$1.tsv"
    if [ ! -s "${f}" ]; then mkdir -p "${E5}/data"; python3 -I "${E5}/gen_e5.py" "$1" "${f}.part" 2>> "${E5}/logs/gen.txt"; mv "${f}.part" "${f}"; fi
    echo "${f}"
}
nevents() { wc -l < "$1" | tr -d ' '; }

# 已写进表的某格某臂的单遍时间（各遍中位；跳过的格输出 skip；没有输出空）
tlookup() {  # <表> <流名> <k> <臂>
    awk -F'\t' -v nm="$2" -v k="$3" -v a="$4" '
        NR > 1 && ($2 "-n" $3 "-g" $4 "-b" $5) == nm && $6 == k && $7 == a { if ($9 == "skip") s = 1; else v[++m] = $12 }
        END { if (s) { print "skip"; exit } if (!m) exit; n = asort_(v, m); }
        function asort_(v, m,   i, j, t) { for (i = 2; i <= m; i++) { t = v[i]; for (j = i - 1; j >= 1 && v[j] > t; j--) v[j + 1] = v[j]; v[j + 1] = t }
            print (m % 2) ? v[(m + 1) / 2] : (v[m / 2] + v[m / 2 + 1]) / 2; return m }' "$1"
}

# OPP 的预计单遍：同分布、同 k、同组、同突发、n 小一档（÷ 10）的那格 OPP 时间 × 10 × 事件数之比；那格跳过 ⇒ skip；没有那格 ⇒ 空
pred_opp() {  # <表> <流名> <k> <本格事件数>
    local nm="$2" d n g b ref t e0
    d="${nm%%-*}"; n="$(echo "${nm}" | sed -E 's/.*-n([0-9]+)-.*/\1/')"; g="$(echo "${nm}" | sed -E 's/.*-g([0-9]+)-.*/\1/')"; b="${nm##*-}"
    [ "${n}" -ge 100 ] || return 0
    ref="${d}-n$((n / 10))-g${g}-${b}"
    t="$(tlookup "$1" "${ref}" "$3" OPP)"
    [ -n "${t}" ] || return 0
    if [ "${t}" = skip ]; then echo skip; return 0; fi
    [ -s "${E5}/data/${ref}.tsv" ] || return 0
    e0="$(nevents "${E5}/data/${ref}.tsv")"
    awk -v t="${t}" -v e="$4" -v e0="${e0}" 'BEGIN { printf "%.1f\n", t * 10 * e / e0 }'
}

# 跑一个进程，把每个计时遍写成一行
emit() {  # <组别> <流名> <k> <臂> <事件数> <mode> <pred> -- <引擎参数…>
    local set="$1" nm="$2" k="$3" arm="$4" ev="$5" mode="$6" pred="$7"; shift 7; [ "$1" = "--" ] && shift
    local d n g b out
    d="${nm%%-*}"; n="$(echo "${nm}" | sed -E 's/.*-n([0-9]+)-.*/\1/')"; g="$(echo "${nm}" | sed -E 's/.*-g([0-9]+)-.*/\1/')"; b="${nm##*-b}"
    out="$("${BIN}" "$@")"
    echo "${out}" | awk -F'\t' -v S="${set}" -v d="${d}" -v n="${n}" -v g="${g}" -v b="${b}" -v k="${k}" -v a="${arm}" -v ev="${ev}" -v mo="${mode}" -v pr="${pred}" '
        { v[$1] = $2 } $1 == "time" { t[$2] = $3; m = $2 }
        END { for (i = 1; i <= m; i++) printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n", S, d, n, g, b, k, a, ev, mo, pr, i, t[i],
            v["maxrss_kb"], v["switches"], v["compactions"], (("idx_events" in v) ? v["idx_events"] : "-"), v["checksum"] }'
}

run_cell() {  # <表> <组别> <流名> <k>
    local tab="$1" set="$2" nm="$3" k="$4" f ev s arm pred warm common
    f="$(stream "${nm}")"; ev="$(nevents "${f}")"; s=$((W_US / k))
    common=(--data "${f}" --W "${W_US}" --s "${s}" --op ">" --agg COUNT)
    for arm in ${ARMS5}; do
        pred="-"
        # shellcheck disable=SC2046
        local aa=($(armargs "${arm}"))
        if [ "${arm}" = OPP ]; then
            pred="$(pred_opp "${tab}" "${nm}" "${k}" "${ev}")"; [ -n "${pred}" ] || pred="-"
            if [ "${pred}" = skip ] || { [ "${pred}" != - ] && lt "${SKIP5}" "${pred}"; }; then
                printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\tskip\t%s\t0\t-\t-\t-\t-\t-\t-\n" "${set}" "${nm%%-*}" \
                    "$(echo "${nm}" | sed -E 's/.*-n([0-9]+)-.*/\1/')" "$(echo "${nm}" | sed -E 's/.*-g([0-9]+)-.*/\1/')" "${nm##*-b}" "${k}" OPP "${ev}" "${pred}" >> "${tab}"
                echo "$(date '+%T') ${nm} k=${k} OPP 跳过（预计 ${pred} s）" >&2
                continue
            fi
            if [ "${pred}" != - ] && ! lt "${pred}" "${SLOW5}"; then
                emit "${set}" "${nm}" "${k}" OPP "${ev}" single "${pred}" -- "${aa[@]}" "${common[@]}" --warmup 0 --reps 1 >> "${tab}"
                echo "$(date '+%T') ${nm} k=${k} OPP 单次（预计 ${pred} s）" >&2
                continue
            fi
        fi
        warm="$("${BIN}" "${aa[@]}" "${common[@]}" --warmup 1 --reps 0 | awk -F'\t' '$1=="warm"{print $2}')"
        local wk=(); if [ "${set}" = S3 ] && { [ "${arm}" = M ] || [ "${arm}" = A5 ]; }; then wk=(--work); fi
        if lt "${warm}" "${SLOW5}"; then
            emit "${set}" "${nm}" "${k}" "${arm}" "${ev}" normal "${pred}" -- "${aa[@]}" "${common[@]}" --warmup 1 --reps 3 "${wk[@]+"${wk[@]}"}" >> "${tab}"
        else
            emit "${set}" "${nm}" "${k}" "${arm}" "${ev}" single "${pred}" -- "${aa[@]}" "${common[@]}" --warmup 0 --reps 1 "${wk[@]+"${wk[@]}"}" >> "${tab}"
        fi
        echo "$(date '+%T') ${nm} k=${k} ${arm} 探测 ${warm} s" >&2
    done
}

main5() {
    local mode="${1:-all}" tab list
    mkdir -p "${E5}/logs" "${E5}/handoff"
    make -s -C "${E5}/../e1-main" out/trend
    {
        echo "# $(date '+%F %T')  mode=${mode}  C_FIXED=${C_FIXED}  TAU5=${TAU5}  HEAD=$(git -C "${E5}" rev-parse --short HEAD)  dirty=$(git -C "${E5}" status --porcelain -- ../e1-main/src ../e1-main/Makefile . | wc -l | tr -d ' ')"
        /usr/bin/clang++ --version | head -1
        sysctl -n machdep.cpu.brand_string
        pmset -g batt | head -1
    } > "${E5}/logs/env_${mode}.txt"
    if [ "${mode}" = smoke ]; then tab="${E5}/logs/e5_smoke.tsv"; list="$(smoke_cells)"; else tab="${E5}/logs/e5_times.part.tsv"; list="$(cells)"; fi
    echo "${HEAD5}" > "${tab}"
    while read -r set nm k; do run_cell "${tab}" "${set}" "${nm}" "${k}"; done <<< "${list}"
    if [ "${mode}" != smoke ]; then mv "${tab}" "${E5}/handoff/e5_times.tsv"; fi
    echo "$(date '+%T') E5 ${mode} 完 → ${tab/part./}" >&2
}

main5 "${1:-all}"
