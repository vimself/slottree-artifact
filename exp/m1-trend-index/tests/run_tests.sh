#!/bin/bash
# M1 · 正确性闸（README 第 2.6 节）：(a) 合成小流 × 全部臂对暴力；(b) 每份真实数据每组前 2,000 个事件 × 6 个查询 × 全部臂逐窗口相等。
# 用法：bash tests/run_tests.sh      全过退出码 0
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
M1_LIB=1 source "${HERE}/run_m1.sh"
make -s -C "${HERE}" out/trend
python3 -I "${HERE}/brute_m1.py" gate "${BIN}" 300
tmp="$(mktemp -d "${HERE}/out/gateb.XXXX")"
bad=0; n=0
for f in wpi_dev wpi_hold pamap2_dev pamap2_hold nasdaq_hold bus_hold; do
    d="${f%_*}"; read -r op s <<< "$(qp "${d}")"
    for W in ${WS}; do for g in ${AGGS}; do
        ref=""
        for arm in "OPP" "OPP --opp-index map" "M --tau ${TAU}" "M --tau 4" "A1" "A4"; do
            # shellcheck disable=SC2086
            "${BIN}" --arm ${arm} --data "${HERE}/data/${f}.tsv" --limit 2000 --W $((W * 1000000)) --s $((s * 1000000)) \
                --op "${op}" --agg "${g}" --reps 1 --warmup 0 --dump "${tmp}/d.tsv" > /dev/null
            h="$(shasum "${tmp}/d.tsv" | cut -d' ' -f1)"; n=$((n + 1))
            if [ -z "${ref}" ]; then ref="${h}"; elif [ "${h}" != "${ref}" ]; then bad=$((bad + 1)); echo "不一致：${f} ${g} W=${W} ${arm}"; fi
        done
    done; done
done
rm -rf "${tmp}"
echo "闸 (b)：${n} 次运行（6 份 × 6 个查询 × 6 个臂配置），与 OPP 不一致 ${bad}"
[ "${bad}" -eq 0 ]
