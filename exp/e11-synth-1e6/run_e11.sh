#!/bin/bash
# E11 · 合成流 n = 10⁶ 上补跑 GRETA-C++ 的两格（README 第 1 节）。本机、单线程、一次只跑一个进程；引擎是 E8 的 v2 二进制。
# 用法：caffeinate -i bash exp/e11-synth-1e6/run_e11.sh   → handoff/e11_times.tsv、handoff/e11_env.txt
# 顺序：k = 1 的 SlotTree → k = 1 的 GRETA-C++ → k = 6 的 SlotTree → k = 6 的 GRETA-C++
# SlotTree：探测遍，再新进程预热 1 遍 + 计时 3 遍；GRETA-C++：新进程不预热、计时 1 遍（E5 对 ≥ 60 s 的格的规则）
# 续跑（README 第 2 节的偏离）：E11_RESUME=1 时不重写表头与环境文件，TSV 里已有的（k, 臂）跳过，只补没跑完的遍
set -euo pipefail
E11="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E8="${E11}/../e8-inpane"
E5="${E11}/../e5-synth"
BIN="${E8}/out/trend"
NM="rw-n1000000-g1-b0"
F="${E5}/data/${NM}.tsv"
OUT="${E11}/handoff/e11_times.tsv"
ENV="${E11}/handoff/e11_env.txt"
W_US=600000000
mkdir -p "${E11}/handoff" "${E11}/logs" "${E5}/logs"

make -s -C "${E8}" out/trend
if [ ! -s "${F}" ]; then mkdir -p "${E5}/data"; python3 -I "${E5}/gen_e5.py" "${NM}" "${F}.part" 2>> "${E5}/logs/gen.txt"; mv "${F}.part" "${F}"; fi
EV="$(wc -l < "${F}" | tr -d ' ')"

load() { echo "$(date '+%F %T')  $1  load$(uptime | sed -E 's/.*load averages?:/:/')" >> "${ENV}"; }
{
    echo "# E11 run  $(date '+%F %T %Z')"
    /usr/bin/clang++ --version | head -1
    sysctl -n machdep.cpu.brand_string
    echo "memory_bytes $(sysctl -n hw.memsize)"
    echo "stream ${NM}  events ${EV}  sha256 $(shasum -a 256 "${F}" | cut -d' ' -f1)"
    echo "source sha256 $(shasum -a 256 "${E8}/src/trend.cpp" | cut -d' ' -f1)"
} > "${ENV}.head"
RESUME="${E11_RESUME:-0}"
if [ "${RESUME}" = 1 ] && [ -s "${OUT}" ]; then
    { echo "# E11 resume  $(date '+%F %T %Z')"; tail -n +2 "${ENV}.head"; } >> "${ENV}"; rm -f "${ENV}.head"
else
    RESUME=0; mv "${ENV}.head" "${ENV}"
    printf "k\tarm\tevents\tmode\tpass\tseconds\tmaxrss_kb\tswitches\tinpane_switches\tcompactions\tchecksum\n" > "${OUT}"
fi
have() { [ "${RESUME}" = 1 ] && awk -F'\t' -v k="$1" -v a="$2" 'NR > 1 && $1 == k && $2 == a { f = 1 } END { exit !f }' "${OUT}"; }
emit() {  # <k> <臂> <mode> -- <引擎参数…>
    local k="$1" arm="$2" mode="$3" out; shift 3; [ "$1" = "--" ] && shift
    out="$("${BIN}" "$@")"
    echo "${out}" | awk -F'\t' -v k="${k}" -v a="${arm}" -v ev="${EV}" -v mo="${mode}" '
        { v[$1] = $2 } $1 == "time" { t[$2] = $3; m = $2 }
        END { for (i = 1; i <= m; i++) printf "%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n", k, a, ev, mo, i, t[i],
            v["maxrss_kb"], v["switches"], v["inpane_switches"], v["compactions"], v["checksum"] }' >> "${OUT}"
}

for k in 1 6; do
    s=$((W_US / k))
    common=(--data "${F}" --W "${W_US}" --s "${s}" --op ">" --agg COUNT)
    if ! have "${k}" M; then
    warm="$("${BIN}" --arm M --c 2 --inpane 1024 "${common[@]}" --warmup 1 --reps 0 | awk -F'\t' '$1=="warm"{print $2}')"
    echo "$(date '+%T') k=${k} SlotTree 探测 ${warm} s" >&2
    emit "${k}" M normal -- --arm M --c 2 --inpane 1024 "${common[@]}" --warmup 1 --reps 3
    echo "$(date '+%T') k=${k} SlotTree 计时完" >&2
    fi
    if have "${k}" OPP; then continue; fi
    load "k=${k} GRETA-C++ 开始前"
    emit "${k}" OPP single -- --arm OPP "${common[@]}" --warmup 0 --reps 1
    load "k=${k} GRETA-C++ 结束后"
    echo "$(date '+%T') k=${k} GRETA-C++ 计时完" >&2
done
echo "# done $(date '+%F %T %Z')" >> "${ENV}"
