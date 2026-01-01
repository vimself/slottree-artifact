#!/bin/bash
# E9 · 跑法（README 第 2 节）。Mac 本机、单线程、接电源；v2 引擎 exp/e8-inpane/out/trend（c = 2、B = 1024，一行不改），
# 两臂 OPP（GRETA-C++）与 M（SlotTree）。计时口径同 E1（exp/e1-main/README.md 第 1 节，含偏离 1），直接调用 run_e1.sh 的 run_row：
# 每个臂一遍探测 → 定 D → 3 个进程 ×「进程 → 臂」交错、--autopasses、第 1 个进程带 --work；探测遍 ≥ 60 s 的 (臂 × 格) 单次计时。
# 本脚本只加：数据登记、M 的 --inpane、两条「不跑的规则」（README 第 2 节，外推公式在第 3 节）、探测遍上的两臂校验和闸。
#   不跑的规则（每格开跑前判，判定记进 handoff/e9_rules.tsv，跑与不跑都记）：
#   · GRETA-C++：W > 5 分的格，T̂ = 同流同 AGG 小一档 W 的 OPP 探测遍 ×（n(W) ÷ n(小一档)）×（W ÷ 小一档）；T̂ > 7,200 s ⇒ 该格 OPP 不跑
#     （小一档本身没跑时用它的 T̂）
#   · 内存：W = 30 分的格，M̂ = 同流同 AGG W = 10 分 M 的峰值内存（3 个进程的最大）×（3 × 3）；M̂ > 10 GiB ⇒ 该格两臂都不跑
# 用法：caffeinate -i bash exp/e9-aiinfra/run_e9.sh gate | all | gpu_hold | llm_hold    （all = 先 gpu_hold 后 llm_hold）
# 桩测用的环境变量（正式跑不设）：E9_DATADIR（数据目录）、E9_OUT（产出目录，代替 handoff/）、E9_TMAX、E9_MEMKB（两条上限）
set -euo pipefail
E9="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E9}/../e1-main/run_e1.sh"   # run_row、run_one、d_of、lt、HEAD、WS、AGGS、C_FIXED、P、SLOW（引入后 HERE 指 e1-main）
BIN="${E9}/../e8-inpane/out/trend"
B8=1024                      # 窗格内检查的间隔 B（E8 预登记）
ARMS9="OPP M"
E9_DATA="gpu_hold llm_hold"
T_MAX="${E9_TMAX:-7200}"                      # 秒
MEM_MAX_KB="${E9_MEMKB:-$((10 * 1024 * 1024))}"   # 10 GiB
DDIR="${E9_DATADIR:-${E9}/data}"
OUT="${E9_OUT:-${E9}/handoff}"
PROBES="${OUT}/e9_probe.tsv"
RULES="${OUT}/e9_rules.tsv"

dfile() { case "$1" in gpu_hold|llm_hold) echo "${DDIR}/$1.tsv" ;; *) echo "未登记的数据 $1" >&2; return 1 ;; esac; }
qp() { case "${1%_*}" in gpu|llm) echo "< 30" ;; *) echo "?"; return 1 ;; esac; }   # ⋈ 为 <（数值上升），s = 30 s
armargs() { case "$1" in
    OPP) echo "--arm OPP" ;;
    M) echo "--arm M --c ${C_FIXED} --inpane ${B8}" ;;
    *) echo "未知的臂 $1" >&2; return 1 ;; esac; }
kv() { echo "$1" | awk -F'\t' -v k="$2" '$1==k{print $2}'; }

# 覆盖 run_e1.sh 的 probe_arm：同一遍探测（D = 1、1 遍预热、0 遍计时），另把秒数、校验和、峰值内存记进 PROBES；
# M 的探测与同一格 OPP 的探测校验和不同 ⇒ 返回非零（run_row 在 set -e 下停，不进计时）
probe_arm() {
    local ds="$1" agg="$2" W="$3" xnum="$4" arm="$5" op s out ck ref
    read -r op s <<< "$(qp "${ds}")"
    # shellcheck disable=SC2046
    out="$("${BIN}" $(armargs "${arm}") --data "$(dfile "${ds}")" --W $((W * 1000000)) --s $((s * 1000000)) --op "${op}" --agg "${agg}" \
        --warmup 1 --reps 0 --xnum "${xnum}")"
    ck="$(kv "${out}" checksum)"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "${ds%_*}" "${agg}" "${W}" "${arm}" "$(kv "${out}" warm)" "${ck}" "$(kv "${out}" maxrss_kb)" >> "${PROBES}"
    ref="$(awk -F'\t' -v d="${ds%_*}" -v g="${agg}" -v w="${W}" '$1==d && $2==g && $3==w && $4=="OPP" {c=$6} END {print c}' "${PROBES}")"
    if [ -n "${ref}" ] && [ "${ck}" != "${ref}" ]; then
        echo "🔴 校验和闸：${ds} ${agg} W=${W} ${arm} ${ck} ≠ OPP ${ref}，不计时" >&2; return 1
    fi
    kv "${out}" warm
}

# 小一档 W 的 OPP 单遍秒数：探测遍的实测，没跑时用 RULES 里的 T̂
opp_basis() {
    local d="$1" agg="$2" W="$3" v
    v="$(awk -F'\t' -v d="${d}" -v g="${agg}" -v w="${W}" '$1==d && $2==g && $3==w && $4=="OPP" {x=$5} END {print x}' "${PROBES}")"
    [ -n "${v}" ] || v="$(awk -F'\t' -v d="${d}" -v g="${agg}" -v w="${W}" '$1==d && $2==g && $3==w && $4=="opp_time" {x=$6} END {print x}' "${RULES}")"
    echo "${v}"
}
nval() { awk -v w="$2" '$1==w {print $2}' "${E9}/logs/n_$1.txt"; }

# 一格：先判两条规则，再交给 E1 的 run_row；跑完核这一格各臂、各进程的校验和都相同
run_cell() {
    local ds="$1" agg="$2" W="$3" tmp="$4" d="${1%_*}" arms="${ARMS9}" prev="" w mk pred base
    for w in ${WS}; do [ "${w}" -lt "${W}" ] && prev="${w}"; done
    if [ "${W}" = 1800 ]; then
        mk="$(awk -F'\t' -v d="${d}" -v g="${agg}" '$1=="M" && $2==d && $4==g && $5==600 && $10>m {m=$10} END {print m+0}' "${tmp}")"
        pred=$((mk * 9))
        if [ "${mk}" -le 0 ]; then echo "W = 10 分 M 的峰值内存缺失" >&2; return 1; fi
        if [ "${pred}" -gt "${MEM_MAX_KB}" ]; then
            printf "%s\t%s\t%s\tmem\t%s\t%s\t%s\t不跑\n" "${d}" "${agg}" "${W}" "${mk}" "${pred}" "${MEM_MAX_KB}" >> "${RULES}"
            echo "$(date '+%T') ${ds} ${agg} W=${W}：内存上限（外推 ${pred} KB）⇒ 两臂都不跑" >&2; return 0
        fi
        printf "%s\t%s\t%s\tmem\t%s\t%s\t%s\t跑\n" "${d}" "${agg}" "${W}" "${mk}" "${pred}" "${MEM_MAX_KB}" >> "${RULES}"
    fi
    if [ -n "${prev}" ]; then
        base="$(opp_basis "${d}" "${agg}" "${prev}")"
        [ -n "${base}" ] || { echo "小一档 W=${prev} 的 OPP 秒数缺失" >&2; return 1; }
        pred="$(awk -v b="${base}" -v n1="$(nval "${d}" "${prev}")" -v n2="$(nval "${d}" "${W}")" -v w1="${prev}" -v w2="${W}" \
            'BEGIN {printf "%.3f", b * (n2 / n1) * (w2 / w1)}')"
        if lt "${T_MAX}" "${pred}"; then
            printf "%s\t%s\t%s\topp_time\t%s\t%s\t%s\t不跑\n" "${d}" "${agg}" "${W}" "${base}" "${pred}" "${T_MAX}" >> "${RULES}"
            echo "$(date '+%T') ${ds} ${agg} W=${W}：GRETA-C++ 外推 ${pred} s > ${T_MAX} s ⇒ OPP 不跑" >&2
            arms="M"
        else
            printf "%s\t%s\t%s\topp_time\t%s\t%s\t%s\t跑\n" "${d}" "${agg}" "${W}" "${base}" "${pred}" "${T_MAX}" >> "${RULES}"
        fi
    fi
    run_row "${ds}" "${agg}" "${W}" "${arms}" "${C_FIXED}" >> "${tmp}"
    local nck
    nck="$(awk -F'\t' -v d="${d}" -v g="${agg}" -v w="${W}" '$2==d && $4==g && $5==w {print $16}' "${tmp}" | sort -u | wc -l | tr -d ' ')"
    [ "${nck}" = 1 ] || { echo "🔴 校验和闸：${ds} ${agg} W=${W} 计时遍里有 ${nck} 个不同的校验和" >&2; return 1; }
}

envlog9() {
    mkdir -p "${OUT}" "${E9}/logs"
    {
        echo "# $(date '+%F %T')  mode=$1  C_FIXED=${C_FIXED}  B=${B8}  HEAD=$(git -C "${E9}" rev-parse --short HEAD)  dirty=$(git -C "${E9}" status --porcelain -- "${E9}/../e8-inpane/src" "${E9}/../e8-inpane/Makefile" | wc -l | tr -d ' ')"
        echo "bin_sha256=$(shasum -a 256 "${BIN}" | cut -d' ' -f1)  src_sha256=$(shasum -a 256 "${E9}/../e8-inpane/src/trend.cpp" | cut -d' ' -f1)"
        /usr/bin/clang++ --version | head -1
        sysctl -n machdep.cpu.brand_string
        sysctl -n hw.memsize
        pmset -g batt | head -1
    } > "${E9}/logs/env_$1.txt"
}

main9() {
    local mode="${1:-}"
    make -s -C "${E9}/../e8-inpane" out/trend
    case "${mode}" in
    gate) python3 -I "${E9}/tests/gate_e9.py" "${BIN}" "$(dfile gpu_hold)" "$(dfile llm_hold)" ;;
    all|gpu_hold|llm_hold)
        envlog9 "${mode}"
        local f="${OUT}/e9_times.tsv" tmp="${E9}/logs/e9_times.tmp" list="${E9_DATA}" ds W g x
        [ "${mode}" != all ] && list="${mode}"
        if [ -f "${f}" ] && [ "${mode}" != all ]; then
            awk -F'\t' -v d="${mode%_*}" 'NR==1 || $2!=d' "${f}" > "${tmp}"
        else echo "${HEAD}" > "${tmp}"; fi
        for x in "${PROBES}" "${RULES}"; do
            if [ -f "${x}" ] && [ "${mode}" != all ]; then awk -F'\t' -v d="${mode%_*}" 'NR==1 || $1!=d' "${x}" > "${x}.tmp"; mv "${x}.tmp" "${x}"; fi
        done
        if [ "${mode}" = all ] || [ ! -f "${PROBES}" ]; then printf "data\tagg\tW\tarm\tprobe_seconds\tchecksum\tmaxrss_kb\n" > "${PROBES}"; fi
        if [ "${mode}" = all ] || [ ! -f "${RULES}" ]; then printf "data\tagg\tW\trule\tbasis\tpredicted\tlimit\tdecision\n" > "${RULES}"; fi
        for ds in ${list}; do
            python3 -I "${E9}/compare_e9.py" nvals "${ds%_*}" "$(dfile "${ds}")" > "${E9}/logs/n_${ds%_*}.txt"
            for W in ${WS}; do for g in ${AGGS}; do
                run_cell "${ds}" "${g}" "${W}" "${tmp}"
            done; done
        done
        mv "${tmp}" "${f}" ;;
    *) echo "用法：bash run_e9.sh gate|all|gpu_hold|llm_hold" >&2; return 1 ;;
    esac
}

main9 "${1:-}"
