r"""E7 · 报表脚本。协议原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 协议开始 -->
**目的**：E1 的数全来自一台 Apple M4（arm64、Apple clang）。审稿人会问 r = T_OPP ÷ T_M 是不是这台机器、这个编译器的特产。本实验在另一种平台（用户的 Linux 工作站，x86-64 或其实际架构、gcc）上按 E1 原口径复跑主表的行，与 E1 同行的 r 并排，只报数。

**行**：E1 的留出行里 WPI、PAMAP2、Binance 各 6 行（高频 18 行）加 Porto、METR-LA 各 6 行，共 30 行（W ∈ {5, 10, 30} 分 × {COUNT, SUM}；数据、⋈、s 同 `run_e1.sh` 的登记表）。Nasdaq、公交、开发行不跑。

**臂**：OPP 与 M（c = 2），同一份源码 `exp/e1-main/src/trend.cpp`（含 E6 加的 `--latency` 旗标，默认关、本实验不开）。

**编译**：工作站上 `g++ -O2 -std=c++20 -Wall -Wextra`（与 E1 的选项相同、编译器换成 gcc），版本原样记进 `relay/platform_machine.txt`；记 CPU 型号、核数、频率调节器、内存、开跑前后的负载。

**正确性**：计时之前在工作站上用 gcc 编出的二进制重过闸 (a)(c)（`brute_e1.py gate`，300 条合成流）与 (a′)（`tests/brute_enum.py`，300 条），有一项错就不计时、回传失败。

**计时口径**：E1 原口径，直接调用 `run_e1.sh` 的 `run_row`（探测遍 → 短行加长的 D → 3 个进程 ×「进程 → 臂」交错 → 每进程 1 遍预热 + R 遍（`--autopasses`）→ 进程内中位、行 = 3 个进程的中位、带 = 最大 ÷ 最小；探测遍 ≥ 60 s 的 (臂 × 行) 按 E1 偏离 1 单次计时；第 1 个进程另跑一遍 `--work` 计数）。D 在工作站上按工作站的探测遍重新定，可能与 Mac 不同，表里两边的 D 都列。数据按 WPI → PAMAP2 → Porto → METR-LA → Binance 的顺序跑（Binance 最慢放最后），每份做完回传一次。

**数据**：工作站没有 E1 的 TSV。选**先打包 TSV**：Mac 上把这 5 份留出 TSV 用 xz 压好、连同未压缩文件的 SHA256SUMS 放进不并入 main 的孤儿分支 `e7-data`（`pack_e7.py pack`），用户推送；工作站入口 `git fetch origin e7-data`、逐个解压到 E1 登记表指向的原路径、sha256 不对就停。不选从原始数据重做：data.binance.vision 在境内校园网上不保证可达，Porto 的 UCI 包 534 MB，而 git 远端两边都已在用；这样两台机器读的是逐字节相同的输入。

**产出**：`handoff/e7_times.tsv`（列同 E1 的 `e1_times.tsv`）；`compare_e7.py` → `report_e7.txt`：逐行两平台的 T_OPP、T_M、r、D、噪声带与 r 工作站 ÷ r Mac（Binance COUNT W = 10 分另列 E1 偏离 2 的重跑），汇总高频 18 行、每份数据、中低频 12 行的 r 中位 / 最小 / 最大、Σ T_OPP ÷ Σ T_M、两平台 r 的 Spearman 秩相关；工作站上单次计时的格与噪声带。不设判据，报表只列数。
<!-- 协议结束 -->

用法：python3 -I exp/e7-platform/compare_e7.py   → 读 handoff/e7_times.tsv（工作站）与 ../e1-main/handoff/e1_times.tsv（Mac），写 report_e7.txt
描述性：只列数，不判。
"""
import os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
E1D = os.path.join(HERE, "..", "e1-main")
if E1D not in sys.path:
    sys.path.insert(0, E1D)
import compare_e1 as c1  # noqa: E402  Times：行时间 = 各进程内中位的中位

HIGH = ["wpi", "pamap2", "binance"]
LOW = ["porto", "metrla"]


def cut(s):
    return s[s.index("<!-- 协议开始 -->"):s.index("<!-- 协议结束 -->")]


def protocol_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    return cut(me) == cut(rd)


def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for t in range(i, j + 1):
            r[o[t]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 3:
        return float("nan")
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def main():
    ws_tab = os.path.join(HERE, "handoff", "e7_times.tsv")
    L = ["# E7 · 第二平台报表（compare_e7.py）", "协议同文自检：%s" % ("一致" if protocol_same() else "不一致！"),
         "描述性：只列数，不判。行时间 = 3 个进程内中位的中位（单次计时的格只有 1 个进程）；r = T_OPP ÷ T_M。"]
    mf = os.path.join(HERE, "relay", "platform_machine.txt")
    if not os.path.exists(mf):
        mf = os.path.join(HERE, "logs", "machine.txt")
    if os.path.exists(mf):
        L.append("工作站（%s）：" % os.path.relpath(mf, HERE))
        L += ["  " + l.rstrip("\n") for l in open(mf, encoding="utf-8") if l.strip()]
    ws = c1.Times(ws_tab)
    mac = c1.Times(os.path.join(E1D, "handoff", "e1_times.tsv"))
    rr_f = os.path.join(E1D, "handoff", "e1_rerun_binance.tsv")
    rr = c1.Times(rr_f) if os.path.exists(rr_f) else None
    L += ["", "## 逐行（Mac = E1 主表；Binance COUNT W = 10 分另列 E1 偏离 2 的重跑）",
          "数据\tAGG\tW 分\tD Mac\tD 工作站\tT_OPP Mac\tT_M Mac\tr Mac\tT_OPP 工作站\tT_M 工作站\tr 工作站\tr 工作站 ÷ r Mac\t带 OPP 工作站\t带 M 工作站\t校验和同（D 相同时）"]
    res = {}
    for k in ws.rowkeys():
        d, sp, agg, W = k
        o, m = ("OPP",) + k, ("M",) + k
        if o not in ws.T or m not in ws.T or o not in mac.T or m not in mac.T:
            continue
        rw, rm = ws.T[o] / ws.T[m], mac.T[o] / mac.T[m]
        res[k] = (rw, rm)
        Dw, Dm = ws.info[m]["copies"], mac.info[m]["copies"]
        same = "-"
        if Dw == Dm:
            same = str(ws.info[m]["checksum"] == mac.info[m]["checksum"] == ws.info[o]["checksum"])
        L.append("\t".join([d, agg, str(W // 60), Dm, Dw, "%.4f" % mac.T[o], "%.4f" % mac.T[m], "%.3f" % rm,
                            "%.4f" % ws.T[o], "%.4f" % ws.T[m], "%.3f" % rw, "%.3f" % (rw / rm), c1.fb(ws.band(o)), c1.fb(ws.band(m)), same]))
        if rr is not None and d == "binance" and agg == "COUNT" and W == 600 and o in rr.T and m in rr.T:
            L.append("\t".join(["  (E1 重跑)", agg, "10", "", "", "%.4f" % rr.T[o], "%.4f" % rr.T[m], "%.3f" % (rr.T[o] / rr.T[m]), "", "", "", "%.3f" % (rw / (rr.T[o] / rr.T[m])), "", "", ""]))
    L += ["", "## 汇总"]

    def summ(name, keys):
        if not keys:
            return
        rw = [res[k][0] for k in keys]
        rm = [res[k][1] for k in keys]
        so = sum(ws.T[("OPP",) + k] for k in keys) / sum(ws.T[("M",) + k] for k in keys)
        smac = sum(mac.T[("OPP",) + k] for k in keys) / sum(mac.T[("M",) + k] for k in keys)
        L.append("%s（%d 行）：工作站 r 中位 %.3f、最小 %.3f、最大 %.3f、Σ T_OPP ÷ Σ T_M = %.3f；Mac r 中位 %.3f、最小 %.3f、最大 %.3f、Σ 比 %.3f；"
                 "r 工作站 ÷ r Mac 中位 %.3f（%.3f–%.3f）；两平台 r 的 Spearman 秩相关 %.3f"
                 % (name, len(keys), statistics.median(rw), min(rw), max(rw), so, statistics.median(rm), min(rm), max(rm), smac,
                    statistics.median([a / b for a, b in zip(rw, rm)]), min(a / b for a, b in zip(rw, rm)), max(a / b for a, b in zip(rw, rm)), spearman(rw, rm)))

    summ("高频留出（WPI + PAMAP2 + Binance）", [k for k in res if k[0] in HIGH])
    for d in HIGH + LOW:
        summ(d, [k for k in res if k[0] == d])
    summ("中低频（Porto + METR-LA）", [k for k in res if k[0] in LOW])
    single = sorted("%s %s %s W=%d" % (k[0], k[1], k[3], k[4] // 60) for k in ws.T if len(ws.procmed[k]) == 1)
    L.append("工作站上单次计时（探测遍 ≥ 60 s，E1 偏离 1）的 (臂 × 行)：%s" % ("、".join(single) or "无"))
    allb = [ws.band(k) for k in ws.T if len(ws.procmed[k]) >= 2]
    if allb:
        L.append("工作站 3 进程噪声带：中位 %.3f、最大 %.3f（%d 个）" % (statistics.median(allb), max(allb), len(allb)))
    txt = "\n".join(L) + "\n"
    open(os.path.join(HERE, "report_e7.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
