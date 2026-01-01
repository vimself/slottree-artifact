#!/bin/bash
# E1 · 跑法（README 第 1 节计时口径、第 2.3 节）。Mac 本机、单线程；产出 handoff/e1_times.tsv。
# 用法：bash run_e1.sh gate          正确性闸 (a)(b)(c)（= tests/run_tests.sh）
#       bash run_e1.sh all           全部 54 行 × 六个臂，按「行 → 进程 → 臂」交错 → handoff/e1_times.tsv
#       bash run_e1.sh <数据>        只跑一份数据的 6 行（替换 e1_times.tsv 里该数据的行）
# 被 run_e4.sh、run_e2.sh、tests/run_tests.sh 用 E1_LIB=1 引入时只定义函数与登记表。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${HERE}/out/trend"
M1D="${HERE}/../m1-trend-index/data"
E4D="${HERE}/../e4-lowfreq/data"
# 代价规则常数 c：E4 开发段定（exp/e4-lowfreq/README.md 第 3 节），提交后不动
C_FIXED="${C_FIXED:-2}"   # 11-05 开发段：score 最小 c = 1，差不到 1% 的 1 / 1.5 / 2 里取大的
TAU5=16            # A5：M1 的 τ_low（τ_high = 32）
WS="300 600 1800"  # W 秒
AGGS="COUNT SUM"
ARMS="OPP M A1 A2 A4 A5"
P=3                # 每个 (臂 × 行) 的进程数
SLOW=60            # 慢行（README 第 3 节偏离 1，用户 11-05 拍板）：探测遍 ≥ 60 s 的 (臂 × 行) 只起 1 个进程、探测遍当预热、计时 1 遍

# 登记表：<数据>_<切分> → 文件、⋈、s（秒）。每份数据一个 ⋈、一个 s（沿用 T20 / M1；新数据见 README 第 2.2 节）
dfile() { case "$1" in
    wpi_dev|wpi_hold|pamap2_dev|pamap2_hold|nasdaq_hold|bus_hold) echo "${M1D}/$1.tsv" ;;
    binance_hold|porto_hold|metrla_hold) echo "${HERE}/data/$1.tsv" ;;
    intel_dev) echo "${E4D}/intel_dev.tsv" ;;
    *) echo "未登记的数据 $1" >&2; return 1 ;; esac; }
qp() { case "${1%_*}" in
    wpi) echo "> 10" ;; pamap2) echo "< 30" ;; nasdaq) echo "> 300" ;; bus) echo "< 300" ;;
    binance) echo "> 10" ;; porto) echo "< 60" ;; metrla) echo "> 300" ;; intel) echo "< 60" ;;
    *) echo "?"; return 1 ;; esac; }
E1_DATA="wpi_dev pamap2_dev wpi_hold pamap2_hold nasdaq_hold bus_hold porto_hold metrla_hold binance_hold"  # Binance 最慢，放最后

# 臂 → 二进制参数
armargs() { case "$1" in
    OPP|A1|A4) echo "--arm $1" ;;
    M|A2) [ -n "${C_FIXED}" ] || { echo "C_FIXED 未定（E4 开发段先定 c）" >&2; return 1; }; echo "--arm $1 --c ${C_FIXED}" ;;
    A5) echo "--arm A5 --tau ${TAU5}" ;;
    *) echo "未知的臂 $1" >&2; return 1 ;; esac; }

HEAD="arm	data	split	agg	W	s	proc	pass	seconds	maxrss_kb	work_pred	work_adds	work_nodes	switches	idx_events	checksum	copies	reps	warm	compactions	ratio_med	events	c	xnum"

# 跑一个进程：run_one <臂标签> <数据_切分> <AGG> <W 秒> <进程号> <D> <要不要 --work 0/1> <c 列> <xnum> -- <二进制参数…>
# 每个计时遍一行（HEAD 的列）；默认 --autopasses（1 遍预热定 R，E1 第 1 节）；环境变量 REPS_FIXED=5 时改成固定 5 遍（E4 开发段）
run_one() {
    local label="$1" ds="$2" agg="$3" W="$4" proc="$5" D="$6" work="$7" cval="$8" xnum="$9"; shift 9; [ "$1" = "--" ] && shift
    local op s; read -r op s <<< "$(qp "${ds}")"
    local wf=(); [ "${work}" = 1 ] && wf=(--work)
    local rp=(--autopasses); [ -n "${REPS_FIXED:-}" ] && rp=(--reps "${REPS_FIXED}")
    local out
    out="$("${BIN}" "$@" --data "$(dfile "${ds}")" --W $((W * 1000000)) --s $((s * 1000000)) --op "${op}" --agg "${agg}" \
        --warmup "${WARMUP:-1}" "${rp[@]}" --copies "${D}" --xnum "${xnum}" "${wf[@]+"${wf[@]}"}")"
    echo "${out}" | awk -F'\t' -v a="${label}" -v d="${ds%_*}" -v sp="${ds##*_}" -v g="${agg}" -v w="${W}" -v s="${s}" -v p="${proc}" \
        -v D="${D}" -v c="${cval}" -v x="${xnum}" '
        { v[$1] = $2 } $1 == "time" { t[$2] = $3; n = $2 }
        END { for (i = 1; i <= n; i++) printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
            a, d, sp, g, w, s, p, i, t[i], v["maxrss_kb"], (("work_pred" in v) ? v["work_pred"] : "-"), (("work_adds" in v) ? v["work_adds"] : "-"),
            (("work_nodes" in v) ? v["work_nodes"] : "-"), v["switches"], (("idx_events" in v) ? v["idx_events"] : "-"), v["checksum"], D, v["reps"], (("warm" in v) ? v["warm"] : "-"),
            v["compactions"], (("ratio_med" in v) ? v["ratio_med"] : "-"), (("events" in v) ? v["events"] : "-"), c, x }'
}

# 探测遍：一个臂 D = 1 跑一遍预热，输出秒数
probe_arm() {
    local ds="$1" agg="$2" W="$3" xnum="$4" arm="$5" op s; read -r op s <<< "$(qp "${ds}")"
    # shellcheck disable=SC2046
    "${BIN}" $(armargs "${arm}") --data "$(dfile "${ds}")" --W $((W * 1000000)) --s $((s * 1000000)) --op "${op}" --agg "${agg}" \
        --warmup 1 --reps 0 --xnum "${xnum}" | awk -F'\t' '$1=="warm"{print $2}'
}
lt() { awk -v a="$1" -v b="$2" 'BEGIN{exit !(a<b)}'; }
# 短行加长的 D（README 第 1 节；第 3 节「D 的定法」）：OPP 与 M 的探测遍取小的；< 5 ms ⇒ D = min(50, ⌈5 ms ÷ 它⌉)
d_of() { awk -v t="$1" 'BEGIN { if (t >= 0.005) print 1; else { d = 0.005 / t; D = (d == int(d)) ? d : int(d) + 1; if (D > 50) D = 50; print D } }'; }

# 一行：每个臂一遍探测 → 定 D → P 个进程 × 臂交错（第 1 个进程带 --work）；慢 (臂 × 行) 只在第 1 个进程跑、不预热、计时 1 遍
run_row() {
    local ds="$1" agg="$2" W="$3" arms="$4" cval="$5" xnum="${6:-1000}" D m="" probes="" a t
    for a in ${arms}; do
        t="$(probe_arm "${ds}" "${agg}" "${W}" "${xnum}" "${a}")"
        probes="${probes} ${a}=${t}"
        case "${a}" in OPP|M) if [ -z "${m}" ] || lt "${t}" "${m}"; then m="${t}"; fi ;; esac
    done
    D="$(d_of "${m}")"
    echo "$(date '+%T') 探测 ${ds} ${agg} W=${W} X=${xnum}:${probes} ⇒ D=${D}" >&2
    for p in $(seq 1 "${P}"); do
        for a in ${arms}; do
            local cv="-" slow=0; case "${a}" in M|A2) cv="${cval}" ;; esac
            t="$(echo "${probes}" | tr ' ' '\n' | awk -F= -v a="${a}" '$1==a{print $2}')"
            if [ "${D}" = 1 ] && ! lt "${t}" "${SLOW}"; then slow=1; fi
            if [ "${slow}" = 1 ] && [ "${p}" != 1 ]; then continue; fi
            if [ "${slow}" = 1 ]; then
                # shellcheck disable=SC2046
                WARMUP=0 REPS_FIXED=1 run_one "${a}" "${ds}" "${agg}" "${W}" "${p}" "${D}" 1 "${cv}" "${xnum}" -- $(armargs "${a}")
            else
                # shellcheck disable=SC2046
                run_one "${a}" "${ds}" "${agg}" "${W}" "${p}" "${D}" "$([ "${p}" = 1 ] && echo 1 || echo 0)" "${cv}" "${xnum}" -- $(armargs "${a}")
            fi
            echo "$(date '+%T') ${ds} ${agg} W=${W} X=${xnum} D=${D} proc=${p} ${a}$([ "${slow}" = 1 ] && echo ' 慢行单次')" >&2
        done
    done
}

envlog() {
    mkdir -p "${HERE}/handoff" "${HERE}/logs"
    {
        echo "# $(date '+%F %T')  mode=$1  C_FIXED=${C_FIXED}  HEAD=$(git -C "${HERE}" rev-parse --short HEAD)  dirty=$(git -C "${HERE}" status --porcelain -- src Makefile | wc -l | tr -d ' ')"
        /usr/bin/clang++ --version | head -1
        sysctl -n machdep.cpu.brand_string
        pmset -g batt | head -1
    } > "${HERE}/logs/env_$1.txt"
}

main() {
    local mode="${1:-}"
    make -s -C "${HERE}" out/trend
    case "${mode}" in
    gate) bash "${HERE}/tests/run_tests.sh" ;;
    all|wpi_dev|pamap2_dev|wpi_hold|pamap2_hold|binance_hold|nasdaq_hold|bus_hold|porto_hold|metrla_hold)
        [ -n "${C_FIXED}" ] || { echo "C_FIXED 未定（E4 开发段先定 c）" >&2; return 1; }
        envlog "${mode}"
        local f="${HERE}/handoff/e1_times.tsv" tmp="${HERE}/logs/e1_times.tmp" list="${E1_DATA}"
        [ "${mode}" != all ] && list="${mode}"
        if [ -f "${f}" ] && [ "${mode}" != all ]; then
            awk -F'\t' -v d="${mode%_*}" -v sp="${mode##*_}" 'NR==1 || !($2==d && $3==sp)' "${f}" > "${tmp}"
        else echo "${HEAD}" > "${tmp}"; fi
        for ds in ${list}; do for W in ${WS}; do for g in ${AGGS}; do
            run_row "${ds}" "${g}" "${W}" "${ARMS}" "${C_FIXED}" >> "${tmp}"
        done; done; done
        mv "${tmp}" "${f}" ;;
    *) echo "用法：bash run_e1.sh gate|all|<数据_切分>" >&2; return 1 ;;
    esac
}

if [ -z "${E1_LIB:-}" ]; then main "${1:-}"; fi
