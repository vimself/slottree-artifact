#!/bin/bash
# M1 · 全部行的跑法（README 第 2.5、2.7 节）。Mac 本机、单线程；产出 handoff/。
# 用法：bash run_m1.sh tau     开发段 12 行 × τ_low ∈ {16,32,64,128,256}，只跑 M → handoff/m1_tau.tsv（第 2.3 节）
#       bash run_m1.sh dev     开发段 12 行 × 四个臂 → handoff/m1_times.tsv（替换其中 split=dev 的行）
#       bash run_m1.sh hold    留出段 24 行 × 四个臂，每臂一次定稿版本 → 同上（替换 split=hold 的行）
#       bash run_m1.sh shape   对手校准的合成流形状（第 2.2 节第 5 条）→ handoff/m1_shape.tsv
#       bash run_m1.sh diag    判读后诊断（不进判据、不改判读；README 第 3 节）：公交 6 行 × {OPP, M τ=16, M 不切换} × 3 个进程 → handoff/m1_diag.tsv
# 被 tests/run_tests.sh 用 M1_LIB=1 引入时只定义函数。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${HERE}/out/trend"
TAU="${TAU:-16}"   # τ_low：开发集上定（run_m1.sh tau → 12 行总时间最小的 16，README 第 3 节），留出集不再动
WS="300 600 1800"  # W 秒
AGGS="COUNT SUM"
ARMS="OPP M A1 A4"

# 每份数据的 ⋈ 与 s（秒），沿用 T20
qp() { case "$1" in wpi) echo "> 10" ;; pamap2) echo "< 30" ;; nasdaq) echo "> 300" ;; bus) echo "< 300" ;; *) echo "?" ; return 1 ;; esac; }
datas() { case "$1" in dev) echo "wpi pamap2" ;; hold) echo "wpi pamap2 nasdaq bus" ;; esac; }

# 跑一个 (臂 × 行)，把每次重复的时间写成 m1_times.tsv 的行
# 列：arm data split agg W s rep seconds maxrss_kb work_units work_pred work_nodes checksum tau
run_row() {
    local arm="$1" data="$2" split="$3" agg="$4" W="$5" tau="$6"
    local op s; read -r op s <<< "$(qp "${data}")"
    local out
    out="$("${BIN}" --arm "${arm}" --data "${HERE}/data/${data}_${split}.tsv" --W $((W * 1000000)) --s $((s * 1000000)) \
        --op "${op}" --agg "${agg}" --reps 5 --warmup 1 --tau "${tau}" --work)"
    local rss wu wp wn ck
    rss="$(echo "${out}" | awk -F'\t' '$1=="maxrss_kb"{print $2}')"
    wu="$(echo "${out}" | awk -F'\t' '$1=="work_adds"{print $2}')"
    wp="$(echo "${out}" | awk -F'\t' '$1=="work_pred"{print $2}')"
    wn="$(echo "${out}" | awk -F'\t' '$1=="work_nodes"{print $2}')"
    ck="$(echo "${out}" | awk -F'\t' '$1=="checksum"{print $2}')"
    echo "${out}" | awk -F'\t' -v a="${arm}" -v d="${data}" -v sp="${split}" -v g="${agg}" -v w="${W}" -v s="${s}" \
        -v rss="${rss}" -v wu="${wu}" -v wp="${wp}" -v wn="${wn}" -v ck="${ck}" -v t="${tau}" \
        '$1=="time"{printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", a,d,sp,g,w,s,$2,$3,rss,wu,wp,wn,ck,t}'
}
HEAD="arm	data	split	agg	W	s	rep	seconds	maxrss_kb	work_units	work_pred	work_nodes	checksum	tau"

main() {
    local mode="$1"
    make -s -C "${HERE}" out/trend
    mkdir -p "${HERE}/handoff" "${HERE}/logs"
    {
        echo "# $(date '+%F %T')  mode=${mode}  TAU=${TAU}  HEAD=$(git -C "${HERE}" rev-parse --short HEAD)"
        /usr/bin/clang++ --version | head -1
        sysctl -n machdep.cpu.brand_string
        pmset -g batt | head -1
    } > "${HERE}/logs/env_${mode}.txt"
    case "${mode}" in
    tau)
        local f="${HERE}/handoff/m1_tau.tsv"; echo "${HEAD}" > "${f}"
        for tau in 16 32 64 128 256; do
            for d in $(datas dev); do for W in ${WS}; do for g in ${AGGS}; do
                run_row M "${d}" dev "${g}" "${W}" "${tau}" >> "${f}"; echo "τ=${tau} ${d} ${g} W=${W}" >&2
            done; done; done
        done ;;
    dev|hold)
        local f="${HERE}/handoff/m1_times.tsv" tmp="${HERE}/logs/m1_times.tmp"
        if [ -f "${f}" ]; then awk -F'\t' -v sp="${mode}" 'NR==1 || $3!=sp' "${f}" > "${tmp}"; else echo "${HEAD}" > "${tmp}"; fi
        for d in $(datas "${mode}"); do for W in ${WS}; do for g in ${AGGS}; do
            for arm in ${ARMS}; do
                run_row "${arm}" "${d}" "${mode}" "${g}" "${W}" "${TAU}" >> "${tmp}"; echo "${mode} ${d} ${g} W=${W} ${arm}" >&2
            done
        done; done; done
        mv "${tmp}" "${f}" ;;
    shape)
        local f="${HERE}/handoff/m1_shape.tsv"
        echo "arm	n_per_window	selectivity	rep	seconds	work_units	work_pred	checksum" > "${f}"
        local sd="${HERE}/data/shape"; mkdir -p "${sd}"
        for spec in "1000 0.5" "2000 0.5" "5000 0.5" "10000 0.5" "20000 0.5" "5000 0.1" "5000 0.9"; do
            local n sel; read -r n sel <<< "${spec}"
            python3 -I "${HERE}/prep_m1.py" shape "${n}" "${sel}" "${sd}/s_${n}_${sel}.tsv"
            for arm in OPP A4; do
                local out; out="$("${BIN}" --arm "${arm}" --data "${sd}/s_${n}_${sel}.tsv" --W 100000000 --s 10000000 --op '<' --agg COUNT --reps 3 --warmup 1 --work)"
                local wu wp ck
                wu="$(echo "${out}" | awk -F'\t' '$1=="work_adds"{print $2}')"; wp="$(echo "${out}" | awk -F'\t' '$1=="work_pred"{print $2}')"
                ck="$(echo "${out}" | awk -F'\t' '$1=="checksum"{print $2}')"
                echo "${out}" | awk -F'\t' -v a="${arm}" -v n="${n}" -v s="${sel}" -v wu="${wu}" -v wp="${wp}" -v ck="${ck}" \
                    '$1=="time"{printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n", a,n,s,$2,$3,wu,wp,ck}' >> "${f}"
                echo "shape n=${n} σ=${sel} ${arm}" >&2
            done
        done ;;
    diag)
        # 进程间的波动：同一 (臂 × 行) 起 3 个进程、交错跑；M 不切换 = τ_low 取 10⁹（全程扫描，只多 M 的簿记）
        local f="${HERE}/handoff/m1_diag.tsv"; echo "${HEAD}	proc" > "${f}"
        for W in ${WS}; do for g in ${AGGS}; do for p in 1 2 3; do
            for spec in "OPP ${TAU}" "M ${TAU}" "M 1000000000"; do
                local arm tau; read -r arm tau <<< "${spec}"
                run_row "${arm}" bus hold "${g}" "${W}" "${tau}" | awk -v p="${p}" '{print $0 "\t" p}' >> "${f}"
                echo "diag bus ${g} W=${W} proc=${p} ${arm} τ=${tau}" >&2
            done
        done; done; done ;;
    *) echo "用法：bash run_m1.sh tau|dev|hold|shape|diag" >&2; return 1 ;;
    esac
}

if [ -z "${M1_LIB:-}" ]; then main "${1:-}"; fi
