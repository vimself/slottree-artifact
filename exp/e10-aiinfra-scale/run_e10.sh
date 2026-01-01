#!/bin/bash
# E10 · 跑法（README 第 1 节判据、第 2 节要点、第 3 节定值）。单线程、接电源；v2 引擎 exp/e8-inpane/out/trend（c = 2、B = 1024，一行不改）。
# 计时口径同 E9（= E1 第 1 节，含偏离 1）：直接调用 run_e1.sh 的 run_row —— 每个臂一遍探测 → 3 个进程 ×「进程 → 臂」交错、--autopasses、
# 第 1 个进程带 --work；探测遍 ≥ 60 s 的 (臂 × 格) 单次计时。本脚本只加：数据登记、臂参数、不跑的规则、探测遍上的校验和闸、输入占用的测法。
#   部分 A（集群回放，COUNT，W = 10 → 30 分，每个 W 里 G = 25 → 100 → 400；臂 OPP、M）：
#     · GRETA-C++：G > 25 的格，T̂ = 同 W 小一档 G 的 OPP 探测遍秒数 × G 之比；> 7,200 s ⇒ 该格 OPP 不跑（小一档没跑时用它的 T̂）
#     · 内存：G > 25 的格，M̂ = 同 W 小一档 G 的 M 峰值内存（3 个进程的最大）× G 之比；> 10 GiB ⇒ 两臂都不跑（小一档没跑时用它的 M̂）
#     · 输入占用：每份回放文件「只解析不计算」（--warmup 0 --reps 0）3 次取峰值的最大，另用 1 个事件的文件测进程基线 → e10_mem.tsv
#   部分 B（全部模型，W = 5 → 10 → 30 分 × COUNT / SUM；臂 OPP、M、A4）：E9 的两条规则原样（exp/e9-aiinfra/README.md 第 3 节），
#     n 是本流的 n；A4（always index，描述性）另按它自己的 W = 10 分峰值 × 9 判内存，> 10 GiB 只去掉 A4
#   部分 C（逐事件延迟，E6 的协议）：E9 两条流 × {OPP, M}，W = 10 分、COUNT，--latency，预热 1 + 3 遍（E9 里单次计时的格不预热、1 遍）
#   部分 D（第二平台，只由 ws_e10.sh 在工作站调用）：mem → W gpu "OPP M" → W llm "OPP M" → A，即 E9 的 12 个设置（E9 的规则）+ 部分 A 的 6 格，
#     臂 OPP、M，内存线 150 GiB；E10_BIN、E10_DATADIR、E10_E9DATA、E10_TAG=e10_ws、E10_MEMKB 由 ws_e10.sh 给
# 用法：caffeinate -i bash exp/e10-aiinfra-scale/run_e10.sh gate | mem | A | B | C | all      （all = mem → A → B → C）
#       bash exp/e10-aiinfra-scale/run_e10.sh W <数据> "<臂…>"   （E9 规则的一条流；工作站用）
# 桩测用的环境变量（正式跑不设）：E10_BIN、E10_DATADIR（回放与全部模型的数据目录）、E10_E9DATA（E9 两条流的目录）、E10_OUT（产出目录）、
#   E10_LOG（日志目录）、E10_TAG（产出文件名前缀）、E10_TMAX、E10_MEMKB（两条上限）、E10_ONLY_W（只跑这几个 W 秒，空格分隔）
set -euo pipefail
E10="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E1_LIB=1 source "${E10}/../e1-main/run_e1.sh"   # run_row、run_one、d_of、lt、HEAD、C_FIXED、P、SLOW（引入后 HERE 指 e1-main）
BIN="${E10_BIN:-${E10}/../e8-inpane/out/trend}"
B8=1024                                        # 窗格内检查的间隔 B（E8 预登记）
DDIR="${E10_DATADIR:-${E10}/data}"
E9D="${E10_E9DATA:-${E10}/../e9-aiinfra/data}"
OUT="${E10_OUT:-${E10}/handoff}"
LOG="${E10_LOG:-${E10}/logs}"
TAG="${E10_TAG:-e10}"
T_MAX="${E10_TMAX:-7200}"                           # 秒
MEM_MAX_KB="${E10_MEMKB:-$((10 * 1024 * 1024))}"    # 10 GiB（工作站 150 GiB）
TIMES="${OUT}/${TAG}_times.tsv"
PROBES="${OUT}/${TAG}_probe.tsv"
RULES="${OUT}/${TAG}_rules.tsv"
MEMF="${OUT}/${TAG}_mem.tsv"
E9T="${E10}/../e9-aiinfra/handoff/e9_times.tsv"
GA="25 100 400"
WA="${E10_ONLY_W:-600 1800}"
WB="${E10_ONLY_W:-300 600 1800}"
AGGS="COUNT SUM"

dfile() { case "$1" in
    r25_hold) echo "${DDIR}/replay_G25.tsv" ;; r100_hold) echo "${DDIR}/replay_G100.tsv" ;; r400_hold) echo "${DDIR}/replay_G400.tsv" ;;
    llmall_hold) echo "${DDIR}/llm_all.tsv" ;;
    gpu_hold|llm_hold) echo "${E9D}/$1.tsv" ;;
    *) echo "未登记的数据 $1" >&2; return 1 ;; esac; }
qp() { case "${1%_*}" in r25|r100|r400|llmall|gpu|llm) echo "< 30" ;; *) echo "?"; return 1 ;; esac; }   # ⋈ 为 <，s = 30 s
armargs() { case "$1" in
    OPP) echo "--arm OPP" ;;
    M) echo "--arm M --c ${C_FIXED} --inpane ${B8}" ;;
    A4) echo "--arm A4" ;;
    *) echo "未知的臂 $1" >&2; return 1 ;; esac; }
kv() { echo "$1" | awk -F'\t' -v k="$2" '$1==k{print $2}'; }
sha_of() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }

# 覆盖 run_e1.sh 的 probe_arm：同一遍探测（D = 1、1 遍预热、0 遍计时），另把秒数、校验和、峰值内存记进 PROBES；
# 本格后探测的臂与本格第一个探测的臂（OPP 跑时就是 OPP）校验和不同 ⇒ 返回非零（run_row 在 set -e 下停，不进计时）
probe_arm() {
    local ds="$1" agg="$2" W="$3" xnum="$4" arm="$5" op s out ck ref
    read -r op s <<< "$(qp "${ds}")"
    # shellcheck disable=SC2046
    out="$("${BIN}" $(armargs "${arm}") --data "$(dfile "${ds}")" --W $((W * 1000000)) --s $((s * 1000000)) --op "${op}" --agg "${agg}" \
        --warmup 1 --reps 0 --xnum "${xnum}")"
    ck="$(kv "${out}" checksum)"
    ref="$(awk -F'\t' -v d="${ds%_*}" -v g="${agg}" -v w="${W}" '$1==d && $2==g && $3==w {print $6 " " $4; exit}' "${PROBES}")"
    printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "${ds%_*}" "${agg}" "${W}" "${arm}" "$(kv "${out}" warm)" "${ck}" "$(kv "${out}" maxrss_kb)" >> "${PROBES}"
    if [ -n "${ref}" ] && [ "${ck}" != "${ref%% *}" ]; then
        echo "🔴 校验和闸：${ds} ${agg} W=${W} ${arm} ${ck} ≠ ${ref##* } ${ref%% *}，不计时" >&2; return 1
    fi
    kv "${out}" warm
}

# 某格 OPP 的单遍秒数：探测遍的实测；没跑时用 RULES 里的 T̂
opp_basis() {
    local d="$1" agg="$2" W="$3" v
    v="$(awk -F'\t' -v d="${d}" -v g="${agg}" -v w="${W}" '$1==d && $2==g && $3==w && $4=="OPP" {x=$5} END {print x}' "${PROBES}")"
    [ -n "${v}" ] || v="$(awk -F'\t' -v d="${d}" -v g="${agg}" -v w="${W}" '$1==d && $2==g && $3==w && $4=="opp_time" {x=$6} END {print x}' "${RULES}")"
    echo "${v}"
}
# 某格某臂的峰值内存（KB，计时表里各进程的最大）；没跑时用 RULES 里这条规则的外推值
mem_basis() {   # <臂> <数据> <AGG> <W> <计时表> <规则名>
    local v
    v="$(awk -F'\t' -v a="$1" -v d="$2" -v g="$3" -v w="$4" '$1==a && $2==d && $4==g && $5==w && $10>m {m=$10} END {print m+0}' "$5")"
    if [ "${v}" -le 0 ]; then
        v="$(awk -F'\t' -v d="$2" -v g="$3" -v w="$4" -v r="$6" '$1==d && $2==g && $3==w && $4==r {x=$6} END {print x+0}' "${RULES}")"
    fi
    echo "${v}"
}
rule() { printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$@" >> "${RULES}"; }   # 数据 AGG W 规则 依据 外推 上限 判定
cell_ck() {   # 跑完核这一格各臂、各进程、各遍的校验和只有一个
    local nck
    nck="$(awk -F'\t' -v d="$1" -v g="$2" -v w="$3" '$2==d && $4==g && $5==w {print $16}' "$4" | sort -u | wc -l | tr -d ' ')"
    [ "${nck}" = 1 ] || { echo "🔴 校验和闸：$1 $2 W=$3 计时遍里有 ${nck} 个不同的校验和" >&2; return 1; }
}

# 部分 A 的一格：<G> <W> <计时表>
run_cellA() {
    local G="$1" W="$2" tmp="$3" d="r$1" prev="" arms="OPP M" base pred mk skip=0
    case "${G}" in 100) prev=25 ;; 400) prev=100 ;; esac
    if [ -n "${prev}" ]; then
        base="$(opp_basis "r${prev}" COUNT "${W}")"
        [ -n "${base}" ] || { echo "小一档 G=${prev} 的 OPP 秒数缺失" >&2; return 1; }
        pred="$(awk -v b="${base}" -v g="${G}" -v p="${prev}" 'BEGIN {printf "%.3f", b * g / p}')"
        if lt "${T_MAX}" "${pred}"; then
            rule "${d}" COUNT "${W}" opp_time "${base}" "${pred}" "${T_MAX}" 不跑; arms="M"
            echo "$(date '+%T') ${d} W=${W}：GRETA-C++ 外推 ${pred} s > ${T_MAX} s ⇒ OPP 不跑" >&2
        else rule "${d}" COUNT "${W}" opp_time "${base}" "${pred}" "${T_MAX}" 跑; fi
        mk="$(mem_basis M "r${prev}" COUNT "${W}" "${tmp}" mem)"
        [ "${mk}" -gt 0 ] || { echo "小一档 G=${prev} 的 SlotTree 峰值内存缺失" >&2; return 1; }
        pred=$((mk * G / prev))
        if [ "${pred}" -gt "${MEM_MAX_KB}" ]; then
            rule "${d}" COUNT "${W}" mem "${mk}" "${pred}" "${MEM_MAX_KB}" 不跑; skip=1
            echo "$(date '+%T') ${d} W=${W}：内存上限（SlotTree 外推 ${pred} KB）⇒ 两臂都不跑" >&2
        else rule "${d}" COUNT "${W}" mem "${mk}" "${pred}" "${MEM_MAX_KB}" 跑; fi
    fi
    [ "${skip}" = 1 ] && return 0
    run_row "${d}_hold" COUNT "${W}" "${arms}" "${C_FIXED}" >> "${tmp}"
    cell_ck "${d}" COUNT "${W}" "${tmp}"
}

# E9 规则的一格（部分 B 的全部模型、部分 D 的 E9 两条流）：<数据> <AGG> <W> <臂> <计时表>
nval() { awk -v w="$2" '$1==w {print $2}' "${LOG}/n_$1.txt"; }
run_cellW() {
    local d="$1" agg="$2" W="$3" arms="$4" tmp="$5" prev="" w base pred mk
    for w in ${WB}; do [ "${w}" -lt "${W}" ] && prev="${w}"; done   # 小一档 = 本次跑的 W 里比它小的最大一个（正式跑 WB = 300 600 1800）
    if [ -n "${prev}" ] && [[ " ${arms} " == *" OPP "* ]]; then
        base="$(opp_basis "${d}" "${agg}" "${prev}")"
        [ -n "${base}" ] || { echo "小一档 W=${prev} 的 OPP 秒数缺失" >&2; return 1; }
        pred="$(awk -v b="${base}" -v n1="$(nval "${d}" "${prev}")" -v n2="$(nval "${d}" "${W}")" -v w1="${prev}" -v w2="${W}" \
            'BEGIN {printf "%.3f", b * (n2 / n1) * (w2 / w1)}')"
        if lt "${T_MAX}" "${pred}"; then
            rule "${d}" "${agg}" "${W}" opp_time "${base}" "${pred}" "${T_MAX}" 不跑; arms="${arms/OPP /}"; arms="${arms/OPP/}"
            echo "$(date '+%T') ${d} ${agg} W=${W}：GRETA-C++ 外推 ${pred} s > ${T_MAX} s ⇒ OPP 不跑" >&2
        else rule "${d}" "${agg}" "${W}" opp_time "${base}" "${pred}" "${T_MAX}" 跑; fi
    fi
    if [ "${W}" = 1800 ]; then
        mk="$(mem_basis M "${d}" "${agg}" 600 "${tmp}" mem)"
        [ "${mk}" -gt 0 ] || { echo "W = 10 分 M 的峰值内存缺失" >&2; return 1; }
        pred=$((mk * 9))
        if [ "${pred}" -gt "${MEM_MAX_KB}" ]; then
            rule "${d}" "${agg}" "${W}" mem "${mk}" "${pred}" "${MEM_MAX_KB}" 不跑
            echo "$(date '+%T') ${d} ${agg} W=${W}：内存上限（外推 ${pred} KB）⇒ 都不跑" >&2; return 0
        fi
        rule "${d}" "${agg}" "${W}" mem "${mk}" "${pred}" "${MEM_MAX_KB}" 跑
        if [[ " ${arms} " == *" A4 "* ]]; then
            mk="$(mem_basis A4 "${d}" "${agg}" 600 "${tmp}" a4_mem)"
            pred=$((mk * 9))
            if [ "${mk}" -gt 0 ] && [ "${pred}" -gt "${MEM_MAX_KB}" ]; then
                rule "${d}" "${agg}" "${W}" a4_mem "${mk}" "${pred}" "${MEM_MAX_KB}" 不跑; arms="${arms/ A4/}"
            else rule "${d}" "${agg}" "${W}" a4_mem "${mk}" "${pred}" "${MEM_MAX_KB}" 跑; fi
        fi
    fi
    run_row "${d}_hold" "${agg}" "${W}" "${arms}" "${C_FIXED}" >> "${tmp}"
    cell_ck "${d}" "${agg}" "${W}" "${tmp}"
}

# 输入占用（部分 A）：每份回放文件的事件数、20 字节 × 事件数（引擎 Stream 的三列 i32 + i64 + i64）、进程基线（1 个事件的文件只解析，3 次的最大）、
# 只解析不计算的峰值（同一份文件 --warmup 0 --reps 0，3 次的最大）
parse_peak() {   # <文件>
    local i m=0 v
    for i in 1 2 3; do
        v="$("${BIN}" --arm M --c "${C_FIXED}" --inpane "${B8}" --data "$1" --W 600000000 --s 30000000 --op "<" --agg COUNT --warmup 0 --reps 0 | awk -F'\t' '$1=="maxrss_kb"{print $2}')"
        [ "${v}" -gt "${m}" ] && m="${v}"
    done
    echo "${m}"
}
run_mem() {
    local G f n base one="${LOG}/one_event.tsv"
    head -n 1 "$(dfile r25_hold)" > "${one}"
    base="$(parse_peak "${one}")"
    printf "data\tevents\tinput_bytes\tbase_kb\tparse_peak_kb\n" > "${MEMF}"
    for G in ${GA}; do
        f="$(dfile "r${G}_hold")"
        n="$(wc -l < "${f}" | tr -d ' ')"
        printf "r%s\t%s\t%s\t%s\t%s\n" "${G}" "${n}" "$((n * 20))" "${base}" "$(parse_peak "${f}")" >> "${MEMF}"
        echo "$(date '+%T') 输入占用 r${G}：${n} 个事件" >&2
    done
}

# 部分 C 的一个 (流 × 臂)：E6 的列（HEAD6）末尾加 inpane_switches；E9 里单次计时的格不预热、1 遍
HEAD6="arm	data	split	agg	W	pass	seconds	events	mean_ns	p50_ns	p99_ns	p999_ns	p9999_ns	max_ns	n0	p50_0	p99_0	max_0	n1	p50_1	p99_1	max_1	n2	p50_2	p99_2	max_2	n3	p50_3	p99_3	max_3	clock_med_ns	clock_tick_ns	maxrss_kb	switches	compactions	checksum	inpane_switches"
run_lat() {   # <表> <分布表> <数据_切分> <臂>
    local tab="$1" dist="$2" ds="$3" arm="$4" op s f out wu=1 rp=3
    read -r op s <<< "$(qp "${ds}")"
    f="${LOG}/lat_${arm}_${ds}.tmp"
    if awk -F'\t' -v a="${arm}" -v d="${ds%_*}" 'NR > 1 && $1 == a && $2 == d && $4 == "COUNT" && $5 == 600 && $18 == 1 { f = 1 } END { exit !f }' "${E9T}"; then wu=0; rp=1; fi
    # shellcheck disable=SC2046
    out="$("${BIN}" $(armargs "${arm}") --data "$(dfile "${ds}")" --W 600000000 --s $((s * 1000000)) --op "${op}" --agg COUNT \
        --warmup "${wu}" --reps "${rp}" --latency "${f}")"
    echo "${out}" | awk -F'\t' -v a="${arm}" -v d="${ds%_*}" -v sp="${ds##*_}" '
        $1 == "lat" { m = $2; L[m] = $3 "\t" $4 "\t" $5 "\t" $6 "\t" $7 "\t" $8 "\t" $9 "\t" $10 }
        $1 == "latcat" { C[$2, $3] = $4 "\t" $5 "\t" $6 "\t" $7 }
        $1 == "clock" { ck = $2 "\t" $3 }
        $1 != "lat" && $1 != "latcat" && $1 != "clock" { v[$1] = $2 }
        END { for (i = 1; i <= m; i++) printf "%s\t%s\t%s\tCOUNT\t600\t%d" "\t%s\t%s\t%s\t%s\t%s" "\t%s\t%s\t%s\t%s\t%s\t%s\n", a, d, sp, i, L[i],
              C[i, 0], C[i, 1], C[i, 2], C[i, 3], ck, v["maxrss_kb"], v["switches"], v["compactions"], v["checksum"], v["inpane_switches"] }' >> "${tab}"
    awk -F'\t' -v a="${arm}" -v d="${ds%_*}" '{ print a "\t" d "\t600\t" $0 }' "${f}" >> "${dist}"
    rm -f "${f}"
    echo "$(date '+%T') 延迟 ${ds} ${arm}：预热 ${wu} 遍、逐事件计时 ${rp} 遍" >&2
}

envlog10() {
    mkdir -p "${OUT}" "${LOG}"
    {
        echo "# $(date '+%F %T')  mode=$1  C_FIXED=${C_FIXED}  B=${B8}  HEAD=$(git -C "${E10}" rev-parse --short HEAD)  dirty=$(git -C "${E10}" status --porcelain -- "${E10}/../e8-inpane/src" "${E10}/../e8-inpane/Makefile" "${E10}/run_e10.sh" | wc -l | tr -d ' ')"
        echo "bin=${BIN}  bin_sha256=$(sha_of "${BIN}")  src_sha256=$(sha_of "${E10}/../e8-inpane/src/trend.cpp")"
        if [ "$(uname)" = Darwin ]; then
            /usr/bin/clang++ --version | head -1; sysctl -n machdep.cpu.brand_string; sysctl -n hw.memsize; pmset -g batt | head -1
        else
            g++ --version | head -1; uname -srm
        fi
    } > "${LOG}/env_${TAG}_$1.txt"
}

# 部分的产出合进总表：先删掉总表里这一部分的数据的行，再追加这一部分的新行（部分 A 跑完 B 断了，A 的数也已落盘）
merge_part() {   # <新行文件（带表头）> <数据名…>
    local new="$1"; shift
    local pat=" $* "
    if [ -f "${TIMES}" ]; then
        awk -F'\t' -v p="${pat}" 'NR == 1 || index(p, " " $2 " ") == 0' "${TIMES}" > "${TIMES}.tmp"
    else echo "${HEAD}" > "${TIMES}.tmp"; fi
    tail -n +2 "${new}" >> "${TIMES}.tmp"
    mv "${TIMES}.tmp" "${TIMES}"
}
part_begin() {   # 规则表、探测表里删掉这一部分的数据的行（表不在就写表头）
    local pat=" $* " x
    for x in "${PROBES}" "${RULES}"; do
        if [ -f "${x}" ]; then awk -F'\t' -v p="${pat}" 'NR == 1 || index(p, " " $1 " ") == 0' "${x}" > "${x}.tmp"; mv "${x}.tmp" "${x}"; fi
    done
    [ -f "${PROBES}" ] || printf "data\tagg\tW\tarm\tprobe_seconds\tchecksum\tmaxrss_kb\n" > "${PROBES}"
    [ -f "${RULES}" ] || printf "data\tagg\tW\trule\tbasis\tpredicted\tlimit\tdecision\n" > "${RULES}"
}

partA() {
    local tmp="${LOG}/${TAG}_A.tmp" W G
    part_begin r25 r100 r400
    echo "${HEAD}" > "${tmp}"
    for W in ${WA}; do for G in ${GA}; do run_cellA "${G}" "${W}" "${tmp}"; done; done
    merge_part "${tmp}" r25 r100 r400
}
partW() {   # <数据…>：E9 规则的流；臂由 ARMS_W 给
    local tmp="${LOG}/${TAG}_W.tmp" d W g
    part_begin "$@"
    echo "${HEAD}" > "${tmp}"
    for d in "$@"; do
        python3 -I "${E10}/compare_e10.py" nvals "$(dfile "${d}_hold")" > "${LOG}/n_${d}.txt"
        for W in ${WB}; do for g in ${AGGS}; do run_cellW "${d}" "${g}" "${W}" "${ARMS_W}" "${tmp}"; done; done
    done
    merge_part "${tmp}" "$@"
}
partC() {
    local tab="${LOG}/${TAG}_latency.part.tsv" dist="${LOG}/${TAG}_dist.part.tsv" ds arm
    echo "${HEAD6}" > "${tab}"
    printf "arm\tdata\tW\tkind\tpass\tf1\tf2\tf3\tf4\tf5\tf6\n" > "${dist}"
    for ds in gpu_hold llm_hold; do for arm in OPP M; do run_lat "${tab}" "${dist}" "${ds}" "${arm}"; done; done
    mv "${tab}" "${OUT}/${TAG}_latency.tsv"; mv "${dist}" "${OUT}/${TAG}_dist.tsv"
}

main10() {
    local mode="${1:-}"
    mkdir -p "${OUT}" "${LOG}"
    [ -n "${E10_BIN:-}" ] || make -s -C "${E10}/../e8-inpane" out/trend
    case "${mode}" in
    gate) python3 -I "${E10}/tests/gate_e10.py" "${BIN}" "$(dfile r100_hold)" "$(dfile llmall_hold)" ;;
    mem) envlog10 mem; run_mem ;;
    A) envlog10 A; partA ;;
    B) envlog10 B; ARMS_W="OPP M A4" partW llmall ;;
    C) envlog10 C; partC ;;
    all)
        envlog10 all
        run_mem;                        echo "$(date '+%T') E10 输入占用 完" >&2
        partA;                          echo "$(date '+%T') E10 部分 A 完" >&2
        ARMS_W="OPP M A4" partW llmall; echo "$(date '+%T') E10 部分 B 完" >&2
        partC;                          echo "$(date '+%T') E10 部分 C 完" >&2 ;;
    W)    # 部分 D（工作站，ws_e10.sh 逐条流调用，E10_TAG=e10_ws）：E9 规则的一条流，臂由第 3 个参数给
        envlog10 "W_${2}"; ARMS_W="${3}" partW "${2}" ;;
    *) echo "用法：bash run_e10.sh gate|mem|A|B|C|all|W <数据> <臂>" >&2; return 1 ;;
    esac
}

main10 "$@"
