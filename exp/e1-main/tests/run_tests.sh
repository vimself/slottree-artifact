#!/bin/bash
# E1 / E4 / E2 · 正确性闸（E1 README 第 1 节；E4 README 第 1 节闸 (c)）。全过退出码 0。
#   (a) 合成小流 × 全部臂配置对暴力（含 E2 的选择度谓词）；(c) 合成小流上逐事件扫描代价对暴力 —— brute_e1.py gate
#   (b) 每份真实数据每组前 2,000 个事件 × 该数据用到的全部查询 × 全部臂配置，与 OPP 逐窗口相等；
#       另加真实数据上的 (c)：W = 10 分 COUNT，始终索引（A4）与始终扫描（M 取 c = 10⁹）的逐事件扫描代价相等；E2 的 X ∈ {0.9, 1.1} 上 M 与 OPP 相等
# 用法：bash tests/run_tests.sh [个数 = 300]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E1_LIB=1 source "${HERE}/run_e1.sh"
make -s -C "${HERE}" out/trend
python3 -I "${HERE}/brute_e1.py" gate "${BIN}" "${1:-300}"
tmp="$(mktemp -d "${HERE}/out/gateb.XXXX")"
bad=0; n=0; cbad=0; cn=0; xbad=0; xn=0
# 每份数据的 W（分钟）：E1 的 {5, 10, 30}，加 E4 开发段与 E2 的 W 扫用到的
gws() { case "$1" in wpi_dev|pamap2_dev|wpi_hold|pamap2_hold|binance_hold|porto_hold) echo "1 2 5 10 30 60" ;; *) echo "5 10 30" ;; esac; }
CONFS=("--arm OPP" "--arm OPP --opp-index map" "--arm M --c 0.5" "--arm M --c 6" "--arm A1" "--arm A2 --c 0.5" "--arm A4" "--arm A5 --tau 16")
for ds in ${E1_DATA} intel_dev; do
    f="$(dfile "${ds}")"; [ -f "${f}" ] || { echo "缺数据 ${f}"; exit 1; }
    read -r op s <<< "$(qp "${ds}")"
    common=(--data "${f}" --limit 2000 --s $((s * 1000000)) --op "${op}" --reps 1 --warmup 0)
    for Wm in $(gws "${ds}"); do W=$((Wm * 60 * 1000000)); for g in ${AGGS}; do
        ref=""
        for conf in "${CONFS[@]}"; do
            # shellcheck disable=SC2086
            "${BIN}" ${conf} "${common[@]}" --W "${W}" --agg "${g}" --dump "${tmp}/d.tsv" > /dev/null
            h="$(shasum "${tmp}/d.tsv" | cut -d' ' -f1)"; n=$((n + 1))
            if [ -z "${ref}" ]; then ref="${h}"; elif [ "${h}" != "${ref}" ]; then bad=$((bad + 1)); echo "不一致 (b)：${ds} ${g} W=${Wm} ${conf}"; fi
        done
    done; done
    W=$((10 * 60 * 1000000))
    "${BIN}" --arm A4 "${common[@]}" --W "${W}" --agg COUNT --work --trace "${tmp}/t1.tsv" > /dev/null
    "${BIN}" --arm M --c 1e9 "${common[@]}" --W "${W}" --agg COUNT --work --trace "${tmp}/t2.tsv" > /dev/null
    cn=$((cn + 1)); cmp -s "${tmp}/t1.tsv" "${tmp}/t2.tsv" || { cbad=$((cbad + 1)); echo "不一致 (c)：${ds}"; }
    for x in 900 1100; do
        ref=""
        for conf in "--arm OPP" "--arm M --c 0.5" "--arm M --c 6" "--arm A4"; do
            # shellcheck disable=SC2086
            "${BIN}" ${conf} "${common[@]}" --W "${W}" --agg COUNT --xnum "${x}" --dump "${tmp}/d.tsv" > /dev/null
            h="$(shasum "${tmp}/d.tsv" | cut -d' ' -f1)"; xn=$((xn + 1))
            if [ -z "${ref}" ]; then ref="${h}"; elif [ "${h}" != "${ref}" ]; then xbad=$((xbad + 1)); echo "不一致 (b, X)：${ds} X=${x} ${conf}"; fi
        done
    done
    echo "$(date '+%T') 闸 (b) ${ds} 完" >&2
done
rm -rf "${tmp}"
echo "闸 (b)：${n} 次运行（10 份切分 × 各自的查询 × ${#CONFS[@]} 个臂配置），与 OPP 不一致 ${bad}"
echo "闸 (b, X)：${xn} 次运行（10 份 × X ∈ {0.9, 1.1} × 4 个臂配置，W = 10 分 COUNT），不一致 ${xbad}"
echo "闸 (c, 真实数据)：${cn} 份 × 始终索引对始终扫描的逐事件扫描代价，不一致 ${cbad}"
[ "${bad}" -eq 0 ] && [ "${cbad}" -eq 0 ] && [ "${xbad}" -eq 0 ]
