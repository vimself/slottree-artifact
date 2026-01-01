#!/bin/bash
# E8 · v2 引擎的正确性闸（README 第 1 节「正确性闸」）。全过退出码 0。日志进 logs/gate.txt（调用方重定向）。
#   (a)(c)(a′)(v)  tests/gate_e8.py：E1 的合成小流对暴力、逐事件扫描代价、真枚举（import E1 的脚本），臂配置表追加窗格内检查的小 B 配置
#   (b)  10 份真实切分 × 每组前 2,000 个事件 × 该数据用到的全部 W × COUNT / SUM × 臂配置，与 OPP 逐窗口相等（E1 闸 (b) 的做法，配置表加小 B）
#   (c′) 真实数据 W = 10 分 COUNT：始终索引（A4）、始终扫描（M c = 10⁹）、窗格内切换（M c = 2 B = 1）三者的逐事件扫描代价相等
#   (e)  与 v1 的决策等价：每份真实数据全量、W = 10 分 COUNT，M 与 A2（c = 2）
#        · v2 --inpane 0 与 v1 的校验和、切换次数、压缩次数逐项相同（关掉检查就是 v1）
#        · v2 默认（B = 1024）的窗格内切换次数；为 0 的数据上切换、压缩次数与 v1 相同（检查不触发 ⇒ 决策与 v1 逐事件相同）
# 用法：bash exp/e8-inpane/tests/run_tests.sh [合成流个数 = 300]
set -euo pipefail
E8="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E1_LIB=1 source "${E8}/../e1-main/run_e1.sh"   # dfile、qp、AGGS、E1_DATA（引入后 HERE、BIN 指 e1-main）
V1="${BIN}"
BIN="${E8}/out/trend"
make -s -C "${E8}" out/trend
make -s -C "${E8}/../e1-main" out/trend
python3 -I "${E8}/tests/gate_e8.py" "${BIN}" "${1:-300}"

tmp="$(mktemp -d "${E8}/out/gateb.XXXX")"
bad=0; n=0; cbad=0; cn=0; ebad=0; en=0
gws() { case "$1" in wpi_dev|pamap2_dev|wpi_hold|pamap2_hold|binance_hold|porto_hold) echo "1 2 5 10 30 60" ;; *) echo "5 10 30" ;; esac; }
# E1 闸 (b) 的 8 个配置（v2 上 M / A2 是默认 B = 1024）+ 窗格内检查的 4 个
CONFS=("--arm OPP" "--arm OPP --opp-index map" "--arm M --c 0.5" "--arm M --c 6" "--arm A1" "--arm A2 --c 0.5" "--arm A4" "--arm A5 --tau 16"
       "--arm M --c 2 --inpane 1" "--arm M --c 0.5 --inpane 4" "--arm A2 --c 2 --inpane 1" "--arm M --c 2 --inpane 16")
kv() { awk -F'\t' -v k="$2" '$1==k{print $2}' "$1"; }
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
    "${BIN}" --arm M --c 2 --inpane 1 "${common[@]}" --W "${W}" --agg COUNT --work --trace "${tmp}/t3.tsv" > /dev/null
    cn=$((cn + 1))
    if ! cmp -s "${tmp}/t1.tsv" "${tmp}/t2.tsv" || ! cmp -s "${tmp}/t1.tsv" "${tmp}/t3.tsv"; then cbad=$((cbad + 1)); echo "不一致 (c′)：${ds}"; fi
    # (e) 全量数据
    full=(--data "${f}" --s $((s * 1000000)) --op "${op}" --reps 1 --warmup 0 --W "${W}" --agg COUNT)
    for arm in M A2; do
        "${V1}" --arm "${arm}" --c 2 "${full[@]}" > "${tmp}/e1.txt"
        "${BIN}" --arm "${arm}" --c 2 --inpane 0 "${full[@]}" > "${tmp}/e0.txt"
        "${BIN}" --arm "${arm}" --c 2 "${full[@]}" > "${tmp}/e2.txt"
        en=$((en + 1))
        for key in checksum switches compactions; do
            [ "$(kv "${tmp}/e1.txt" "${key}")" = "$(kv "${tmp}/e0.txt" "${key}")" ] || { ebad=$((ebad + 1)); echo "不一致 (e)：${ds} ${arm} --inpane 0 的 ${key}"; }
        done
        [ "$(kv "${tmp}/e1.txt" checksum)" = "$(kv "${tmp}/e2.txt" checksum)" ] || { ebad=$((ebad + 1)); echo "不一致 (e)：${ds} ${arm} B = 1024 的校验和"; }
        ip="$(kv "${tmp}/e2.txt" inpane_switches)"
        same="-"
        if [ "${ip}" = 0 ]; then
            same="与 v1 相同"
            for key in switches compactions; do
                [ "$(kv "${tmp}/e1.txt" "${key}")" = "$(kv "${tmp}/e2.txt" "${key}")" ] || { ebad=$((ebad + 1)); same="与 v1 不同"; echo "不一致 (e)：${ds} ${arm} 窗格内切换 0 次但 ${key} 与 v1 不同"; }
            done
        fi
        echo "  (e) ${ds} ${arm}：v1 切换 $(kv "${tmp}/e1.txt" switches)、压缩 $(kv "${tmp}/e1.txt" compactions)；v2 B = 1024 窗格内切换 ${ip}、切换 $(kv "${tmp}/e2.txt" switches)、压缩 $(kv "${tmp}/e2.txt" compactions)（${same}）"
    done
    echo "$(date '+%T') 闸 (b)(c′)(e) ${ds} 完" >&2
done
rm -rf "${tmp}"
echo "闸 (b)：${n} 次运行（10 份切分 × 各自的查询 × ${#CONFS[@]} 个臂配置），与 OPP 不一致 ${bad}"
echo "闸 (c′)：${cn} 份 × 始终索引 / 始终扫描 / 窗格内切换的逐事件扫描代价，不一致 ${cbad}"
echo "闸 (e)：${en} 项（10 份 × M / A2，全量、W = 10 分 COUNT）与 v1 的决策等价核对，不一致 ${ebad}"
[ "${bad}" -eq 0 ] && [ "${cbad}" -eq 0 ] && [ "${ebad}" -eq 0 ]
