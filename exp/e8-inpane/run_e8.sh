#!/bin/bash
# E8 · 本机跑法（README 第 1 节协议、第 2 节要点）。v2 引擎 out/trend；只重跑用代价规则的 M、A2（B = 1024、c = 2），
# 别的臂的数从 v1 的表复制（merge_e8.py）。每个实验按它自己的原口径跑：
#   e1   E1 的 54 行 × {M, A2}：探测 → 3 进程 ×「进程 → 臂」交错、--autopasses、第 1 个进程带 --work、探测遍 ≥ 60 s 单次计时（E1 偏离 1）；
#        D（短行加长的份数）取 v1 表里该行的值，不再探测 OPP（同一行 v1 / v2 用同一份加长流）
#   e2   E2 的 35 行（W 扫 + 选择度扫）× {M}：同 e1
#   e5   E5 的 76 格 × {M}：探测 → < 60 s 新进程 1 预热 + 3 遍，≥ 60 s 不预热 1 遍；S3 加 --work；
#        另把 S1 n ≥ 10⁵ 的 24 格的 A4 在同一会话重测一次（描述性旁证，不进判据）→ handoff/e5_a4_recheck.tsv
#   e6   E6 的 4 行 × {M, A2}：逐事件计时 --latency，预热 1 + 3 遍
#   opp  OPP 旁证：E1 的 3 个快格（WPI / PAMAP2 / Porto 留出、COUNT、W = 5 分）按 e1 的口径重测 OPP → handoff/e8_opp_check.tsv
#   all  e1 → e2 → e5 → e6 → opp，最后 merge_e8.py 拼出与原实验同构的 *_v2.tsv
# 每个 M / A2 进程的窗格内切换次数另记 handoff/e8_inpane.tsv（实验、行、臂、进程、窗格内切换、切换总数）。
# 用法：caffeinate -i bash exp/e8-inpane/run_e8.sh gate|e1|e2|e5|e6|opp|all|smoke
set -euo pipefail
E8="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E8}/../e1-main/run_e1.sh"   # dfile、qp、armargs、lt、HEAD、WS、AGGS、E1_DATA、C_FIXED、P、SLOW（引入后 HERE 指 e1-main）
BIN="${E8}/out/trend"
B8=1024                                          # 窗格内检查的间隔 B（README 第 1 节，预登记）
E1T="${E8}/../e1-main/handoff/e1_times.tsv"
E2T="${E8}/../e2-sweep/handoff/e2_times.tsv"
E5T="${E8}/../e5-synth/handoff/e5_times.tsv"
E5D="${E8}/../e5-synth/data"
E6T="${E8}/../e6-latency/handoff/e6_latency.tsv"
LOG="${E8}/logs"
SIDE="${SIDE:-${LOG}/e8_inpane.part.tsv}"   # E7 的工作站段（run_e7v2.sh）改指 handoff/

a8() { case "$1" in M|A2) echo "$(armargs "$1") --inpane ${B8}" ;; *) armargs "$1" ;; esac; }
kv() { echo "$1" | awk -F'\t' -v k="$2" '$1==k{print $2}'; }
side() { printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$4" "$(kv "$5" inpane_switches)" "$(kv "$5" switches)" >> "${SIDE}"; }

# 与 E1 run_one 同一套列（HEAD），另把窗格内切换记进 SIDE。run_one8 <实验> <臂> <数据_切分> <AGG> <W 秒> <进程号> <D> <work 0/1> <c 列> <xnum>
run_one8() {
    local ex="$1" label="$2" ds="$3" agg="$4" W="$5" proc="$6" D="$7" work="$8" cval="$9" xnum="${10}" op s out
    read -r op s <<< "$(qp "${ds}")"
    local wf=(); [ "${work}" = 1 ] && wf=(--work)
    local rp=(--autopasses); [ -n "${REPS_FIXED:-}" ] && rp=(--reps "${REPS_FIXED}")
    # shellcheck disable=SC2046
    out="$("${BIN}" $(a8 "${label}") --data "$(dfile "${ds}")" --W $((W * 1000000)) --s $((s * 1000000)) --op "${op}" --agg "${agg}" \
        --warmup "${WARMUP:-1}" "${rp[@]}" --copies "${D}" --xnum "${xnum}" "${wf[@]+"${wf[@]}"}")"
    side "${ex}" "${ds} ${agg} ${W} ${xnum}" "${label}" "${proc}" "${out}"
    echo "${out}" | awk -F'\t' -v a="${label}" -v d="${ds%_*}" -v sp="${ds##*_}" -v g="${agg}" -v w="${W}" -v s="${s}" -v p="${proc}" \
        -v D="${D}" -v c="${cval}" -v x="${xnum}" '
        { v[$1] = $2 } $1 == "time" { t[$2] = $3; n = $2 }
        END { for (i = 1; i <= n; i++) printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
            a, d, sp, g, w, s, p, i, t[i], v["maxrss_kb"], (("work_pred" in v) ? v["work_pred"] : "-"), (("work_adds" in v) ? v["work_adds"] : "-"),
            (("work_nodes" in v) ? v["work_nodes"] : "-"), v["switches"], (("idx_events" in v) ? v["idx_events"] : "-"), v["checksum"], D, v["reps"], (("warm" in v) ? v["warm"] : "-"),
            v["compactions"], (("ratio_med" in v) ? v["ratio_med"] : "-"), (("events" in v) ? v["events"] : "-"), c, x }'
}

# E1 run_row 的同一口径，D 取 v1 表的值。row8 <实验> <v1 表> <数据_切分> <AGG> <W 秒> <臂…> <xnum>
row8() {
    local ex="$1" v1="$2" ds="$3" agg="$4" W="$5" arms="$6" xnum="$7" op s D a t probes=""
    read -r op s <<< "$(qp "${ds}")"
    D="$(awk -F'\t' -v d="${ds%_*}" -v sp="${ds##*_}" -v g="${agg}" -v w="${W}" -v x="${xnum}" \
        'NR > 1 && $2 == d && $3 == sp && $4 == g && $5 == w && $24 == x { print $17; exit }' "${v1}")"
    [ -n "${D}" ] || { echo "v1 表里没有 ${ds} ${agg} W=${W} X=${xnum}" >&2; return 1; }
    for a in ${arms}; do
        # shellcheck disable=SC2046
        t="$("${BIN}" $(a8 "${a}") --data "$(dfile "${ds}")" --W $((W * 1000000)) --s $((s * 1000000)) --op "${op}" --agg "${agg}" \
            --warmup 1 --reps 0 --xnum "${xnum}" | awk -F'\t' '$1=="warm"{print $2}')"
        probes="${probes} ${a}=${t}"
    done
    echo "$(date '+%T') ${ex} 探测 ${ds} ${agg} W=${W} X=${xnum}:${probes}；D=${D}（v1）" >&2
    for p in $(seq 1 "${P}"); do
        for a in ${arms}; do
            local cv="-" slow=0; case "${a}" in M|A2) cv="${C_FIXED}" ;; esac
            t="$(echo "${probes}" | tr ' ' '\n' | awk -F= -v a="${a}" '$1==a{print $2}')"
            if [ "${D}" = 1 ] && ! lt "${t}" "${SLOW}"; then slow=1; fi
            if [ "${slow}" = 1 ] && [ "${p}" != 1 ]; then continue; fi
            if [ "${slow}" = 1 ]; then
                WARMUP=0 REPS_FIXED=1 run_one8 "${ex}" "${a}" "${ds}" "${agg}" "${W}" "${p}" "${D}" 1 "${cv}" "${xnum}"
            else
                run_one8 "${ex}" "${a}" "${ds}" "${agg}" "${W}" "${p}" "${D}" "$([ "${p}" = 1 ] && echo 1 || echo 0)" "${cv}" "${xnum}"
            fi
        done
    done
}

run_e1() {
    local out="${LOG}/e1_new.tsv" ds W g
    echo "${HEAD}" > "${out}"
    for ds in ${E1_DATA}; do for W in ${WS}; do for g in ${AGGS}; do
        row8 e1 "${E1T}" "${ds}" "${g}" "${W}" "M A2" 1000 >> "${out}"
    done; done; done
}

run_e2() {
    local out="${LOG}/e2_new.tsv" ds g W x
    echo "${HEAD}" > "${out}"
    # v1 表里的行，按 v1 的顺序（W 扫在前、选择度扫在后）
    awk -F'\t' 'NR > 1 && $1 == "M" && $7 == 1 && $8 == 1 { print $2 "_" $3, $4, $5, $24 }' "${E2T}" | while read -r ds g W x; do
        row8 e2 "${E2T}" "${ds}" "${g}" "${W}" "M" "${x}" >> "${out}"
    done
}

# ---------------------------------------------------------------- E5（E5 README 第 1 节计时；列同 E5 的 HEAD5）
HEAD5="set	dist	n	G	burst	k	arm	events	mode	pred_s	pass	seconds	maxrss_kb	switches	compactions	idx_events	checksum"
emit5() {  # <组别> <分布> <n> <G> <突发> <k> <臂> <事件数> <mode> -- <引擎参数…>
    local set="$1" d="$2" n="$3" g="$4" b="$5" k="$6" arm="$7" ev="$8" mode="$9" out; shift 9; [ "$1" = "--" ] && shift
    out="$("${BIN}" "$@")"
    side e5 "${set} ${d}-n${n}-g${g}-b${b} k=${k}" "${arm}" 1 "${out}"
    echo "${out}" | awk -F'\t' -v S="${set}" -v d="${d}" -v n="${n}" -v g="${g}" -v b="${b}" -v k="${k}" -v a="${arm}" -v ev="${ev}" -v mo="${mode}" '
        { v[$1] = $2 } $1 == "time" { t[$2] = $3; m = $2 }
        END { for (i = 1; i <= m; i++) printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t-\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n", S, d, n, g, b, k, a, ev, mo, i, t[i],
            v["maxrss_kb"], v["switches"], v["compactions"], (("idx_events" in v) ? v["idx_events"] : "-"), v["checksum"] }'
}
cell5() {  # <输出> <组别> <分布> <n> <G> <突发> <k> <臂>
    local out="$1" set="$2" d="$3" n="$4" g="$5" b="$6" k="$7" arm="$8" nm f ev s warm
    nm="${d}-n${n}-g${g}-b${b}"; f="${E5D}/${nm}.tsv"
    if [ ! -s "${f}" ]; then mkdir -p "${E5D}"; python3 -I "${E8}/../e5-synth/gen_e5.py" "${nm}" "${f}.part" 2>> "${LOG}/gen.txt"; mv "${f}.part" "${f}"; fi
    ev="$(wc -l < "${f}" | tr -d ' ')"; s=$((600000000 / k))
    # shellcheck disable=SC2046
    local aa=($(a8 "${arm}")) common=(--data "${f}" --W 600000000 --s "${s}" --op ">" --agg COUNT)
    warm="$("${BIN}" "${aa[@]}" "${common[@]}" --warmup 1 --reps 0 | awk -F'\t' '$1=="warm"{print $2}')"
    local wk=(); if [ "${set}" = S3 ] && [ "${arm}" = M ]; then wk=(--work); fi
    if lt "${warm}" 60; then emit5 "${set}" "${d}" "${n}" "${g}" "${b}" "${k}" "${arm}" "${ev}" normal -- "${aa[@]}" "${common[@]}" --warmup 1 --reps 3 "${wk[@]+"${wk[@]}"}" >> "${out}"
    else emit5 "${set}" "${d}" "${n}" "${g}" "${b}" "${k}" "${arm}" "${ev}" single -- "${aa[@]}" "${common[@]}" --warmup 0 --reps 1 "${wk[@]+"${wk[@]}"}" >> "${out}"; fi
    echo "$(date '+%T') e5 ${set} ${nm} k=${k} ${arm} 探测 ${warm} s" >&2
}
run_e5() {
    local out="${LOG}/e5_new.tsv" chk="${LOG}/e5_a4_recheck.tsv"
    echo "${HEAD5}" > "${out}"; echo "${HEAD5}" > "${chk}"
    awk -F'\t' 'NR > 1 && $7 == "M" && $11 == 1 { print $1, $2, $3, $4, $5, $6 }' "${E5T}" | while read -r set d n g b k; do
        cell5 "${out}" "${set}" "${d}" "${n}" "${g}" "${b}" "${k}" M
    done
    awk -F'\t' 'NR > 1 && $1 == "S1" && $3 >= 100000 && $7 == "A4" && $11 == 1 { print $1, $2, $3, $4, $5, $6 }' "${E5T}" | while read -r set d n g b k; do
        cell5 "${chk}" "${set}" "${d}" "${n}" "${g}" "${b}" "${k}" A4
    done
}

# ---------------------------------------------------------------- E6（E6 README 第 1 节；列同 E6 的 HEAD6，逐事件分布同 e6_dist.tsv）
HEAD6="$(head -1 "${E6T}")"
run_e6() {
    local tab="${LOG}/e6_new.tsv" dist="${LOG}/e6_dist_new.tsv" ds arm op s f out
    echo "${HEAD6}" > "${tab}"
    printf "arm\tdata\tW\tkind\tpass\tf1\tf2\tf3\tf4\tf5\tf6\n" > "${dist}"
    for ds in wpi_hold pamap2_hold binance_hold porto_hold; do for arm in M A2; do
        read -r op s <<< "$(qp "${ds}")"
        f="${LOG}/lat_${arm}_${ds}.tmp"
        # shellcheck disable=SC2046
        out="$("${BIN}" $(a8 "${arm}") --data "$(dfile "${ds}")" --W 600000000 --s $((s * 1000000)) --op "${op}" --agg COUNT \
            --warmup 1 --reps 3 --latency "${f}")"
        side e6 "${ds} COUNT 600" "${arm}" 1 "${out}"
        echo "${out}" | awk -F'\t' -v a="${arm}" -v d="${ds%_*}" -v sp="${ds##*_}" -v w=600 '
            $1 == "lat" { m = $2; L[m] = $3 "\t" $4 "\t" $5 "\t" $6 "\t" $7 "\t" $8 "\t" $9 "\t" $10 }
            $1 == "latcat" { C[$2, $3] = $4 "\t" $5 "\t" $6 "\t" $7 }
            $1 == "clock" { ck = $2 "\t" $3 }
            $1 != "lat" && $1 != "latcat" && $1 != "clock" { v[$1] = $2 }
            END { for (i = 1; i <= m; i++) printf "%s\t%s\t%s\tCOUNT\t%s\t%d" "\t%s\t%s\t%s\t%s\t%s" "\t%s\t%s\t%s\t%s\t%s\n", a, d, sp, w, i, L[i],
                  C[i, 0], C[i, 1], C[i, 2], C[i, 3], ck, v["maxrss_kb"], v["switches"], v["compactions"], v["checksum"] }' >> "${tab}"
        awk -F'\t' -v a="${arm}" -v d="${ds%_*}" '{ print a "\t" d "\t600\t" $0 }' "${f}" >> "${dist}"
        rm -f "${f}"
        echo "$(date '+%T') e6 ${ds} ${arm}" >&2
    done; done
}

run_opp() {
    local out="${LOG}/opp_new.tsv" ds
    echo "${HEAD}" > "${out}"
    for ds in wpi_hold pamap2_hold porto_hold; do row8 opp "${E1T}" "${ds}" COUNT 300 "OPP" 1000 >> "${out}"; done
}

envlog() {
    {
        echo "# $(date '+%F %T')  mode=$1  C_FIXED=${C_FIXED}  B=${B8}  HEAD=$(git -C "${E8}" rev-parse --short HEAD)  dirty=$(git -C "${E8}" status --porcelain -- src Makefile run_e8.sh | wc -l | tr -d ' ')"
        /usr/bin/clang++ --version | head -1
        sysctl -n machdep.cpu.brand_string
        pmset -g batt | head -1
    } > "${LOG}/env_$1.txt"
}

main8() {
    local mode="${1:-}"
    mkdir -p "${LOG}" "${E8}/handoff"
    make -s -C "${E8}" out/trend
    case "${mode}" in
    gate) bash "${E8}/tests/run_tests.sh" ;;
    e1|e2|e5|e6|opp)
        envlog "${mode}"; : > "${SIDE}"
        "run_${mode}"
        mv "${SIDE}" "${LOG}/e8_inpane_${mode}.tsv" ;;
    all)
        envlog all
        for m in e1 e2 e5 e6 opp; do : > "${SIDE}"; "run_${m}"; mv "${SIDE}" "${LOG}/e8_inpane_${m}.tsv"; echo "$(date '+%T') E8 ${m} 完" >&2; done
        python3 -I "${E8}/merge_e8.py" ;;
    smoke)  # 桩测：每个跑法一小格，产物只进 logs/smoke_*（不进 handoff）
        envlog smoke; : > "${SIDE}"
        echo "${HEAD}" > "${LOG}/smoke_e1.tsv"
        row8 e1 "${E1T}" nasdaq_hold COUNT 300 "M A2" 1000 >> "${LOG}/smoke_e1.tsv"
        row8 e2 "${E2T}" porto_hold COUNT 600 "M" 1100 >> "${LOG}/smoke_e1.tsv"
        echo "${HEAD5}" > "${LOG}/smoke_e5.tsv"
        cell5 "${LOG}/smoke_e5.tsv" S3 rw 10 1 1 6 M
        cell5 "${LOG}/smoke_e5.tsv" S1 rw 10000 1 0 1 M
        mv "${SIDE}" "${LOG}/smoke_inpane.tsv" ;;
    *) echo "用法：bash run_e8.sh gate|e1|e2|e5|e6|opp|all|smoke" >&2; return 1 ;;
    esac
}

# 被 run_e7v2.sh 用 E8_LIB=1 引入时只定义函数
if [ -z "${E8_LIB:-}" ]; then main8 "${1:-}"; fi
