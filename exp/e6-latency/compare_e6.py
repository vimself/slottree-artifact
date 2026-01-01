r"""E6 · 报表脚本。协议原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 协议开始 -->
**目的**：E1 只报整条流的墙钟时间。窗口槽聚合树在窗格边界上有成块的工作（M 的压缩重建、扫描 ↔ 索引切换时的建树或拆树），审稿人会问这些会不会变成单个事件的长停顿。本实验量逐事件的处理时间分布，只报数。

**引擎**：E1 的二进制（`exp/e1-main/src/trend.cpp`）加 `--latency <文件>` 旗标，默认关；关着时 E1 / E2 / E4 的计时循环不变（`run_arm` 开头多一次指针判空）。开着时预热遍照常，计时遍逐事件计时：每个事件的 `process` 调用前后各读一次 `std::chrono::steady_clock`，差值（纳秒，u32，存进预分配数组）就是该事件的处理时间，**含它触发的窗格边界工作**（OPP 的整窗格清除、M 的窗格簿记 / 压缩 / 切换、A2 的逐个删都在本组下一个事件的 `process` 里做）；最后一批窗口的输出（`finish`）不归到任何事件。每个事件另记一个类别：0 普通；1 本组进入新窗格；2 这次调用里发生了压缩；3 这次调用里发生了切换（2、3 只有树的臂有，两样都有记 3）。进程开头先做一次时钟标定（10⁶ 对背靠背读时钟：差的中位 = 读一次时钟的开销，最小正差 = 分辨率），照报。加了旗标之后闸 (a) 重过一遍（`brute_e1.py gate`，记项数与错误数），并核对计时遍的校验和与不开旗标时相同。

**行**（W = 10 分、COUNT；数据、⋈、s 同 E1 的登记表）：E1 高频留出 WPI、PAMAP2、Binance 各一行，加 Porto 留出一行，共 4 行；不加长（D = 1）。

**臂**：OPP、M（c = 2）、A2（c = 2，逐个删）、A4（始终索引）；参数同 `run_e1.sh`。

**跑法**（`run_e6.sh`）：每 (行 × 臂) 一个进程，预热 1 遍 + 逐事件计时 3 遍；E1 里单次计时的格（偏离 1，探测遍 ≥ 60 s；这 16 格里只有 Binance 的 OPP）不预热、逐事件计时 1 遍。按「行 → 臂」顺序跑；跑时接电源、不开别的重负载。

**指标**（每遍算一次；行 × 臂的值 = 3 遍的中位，最大值另取 3 遍的最大）：逐事件处理时间的 p50 / p99 / p99.9 / p99.99 / 最大与平均；按类别分的事件数、p50、p99、最大，其中类别 2（压缩）、3（切换）的次数与最大值就是「窗格边界停顿」，类别 1 是普通的窗格边界；直方图（对数分桶，每倍 8 桶）与前 100 大的事件（纳秒、类别、组、时间）。分位数用最近秩（排序后第 ⌈p·n⌉ 个）。

**产出**：`handoff/e6_latency.tsv`（每个计时遍一行）、`handoff/e6_dist.tsv`（直方图与前 100 大值）；`compare_e6.py` → `report_e6.txt`：每行一张表（臂 × 分位数、各类别的次数与最大值），加时钟开销与分辨率、计时遍总时间对 E1 同格行时间之比（逐事件计时本身的开销）、校验和一致性。不设判据，报表只列数。
<!-- 协议结束 -->

用法：python3 -I exp/e6-latency/compare_e6.py [表 = handoff/e6_latency.tsv] [分布 = handoff/e6_dist.tsv] [报表 = report_e6.txt]
描述性：只列数，不判。
"""
import os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
E1D = os.path.join(HERE, "..", "e1-main")
if E1D not in sys.path:
    sys.path.insert(0, E1D)
ARMS = ["OPP", "M", "A2", "A4"]
ROWS = ["wpi", "pamap2", "binance", "porto"]
CAT = {0: "普通", 1: "窗格边界", 2: "压缩", 3: "切换"}


def cut(s):
    return s[s.index("<!-- 协议开始 -->"):s.index("<!-- 协议结束 -->")]


def protocol_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    return cut(me) == cut(rd)


def read(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l]


def us(ns):
    """纳秒 → 好读的单位。"""
    ns = float(ns)
    if ns < 1e3:
        return "%.0f ns" % ns
    if ns < 1e6:
        return "%.1f µs" % (ns / 1e3)
    return "%.2f ms" % (ns / 1e6)


def main(tab, dist, rep):
    rows = read(tab)
    by = {}
    for r in rows:
        by.setdefault((r["data"], r["arm"]), []).append(r)
    e1 = None
    try:
        import compare_e1
        e1 = compare_e1.Times(os.path.join(E1D, "handoff", "e1_times.tsv"))
    except Exception as ex:  # 报表照出，只是少一列
        sys.stderr.write("读不到 E1 表：%s\n" % ex)
    out = []
    p = out.append
    p("# E6 · 尾延迟报表（compare_e6.py，读 %s）" % os.path.relpath(tab, HERE))
    p("协议同文自检：%s" % ("一致" if protocol_same() else "不一致！"))
    p("描述性：只列数，不判。分位数 = 各计时遍的值取中位（最大值取各遍的最大）；单位见各格。")
    ck = sorted({(r["clock_med_ns"], r["clock_tick_ns"]) for r in rows})
    p("时钟标定（读一次 steady_clock 的开销中位 ns, 最小正差 ns）：%s" % "、".join("(%s, %s)" % c for c in ck))
    p("")
    for d in ROWS:
        p("## %s 留出 · COUNT · W = 10 分" % d)
        p("臂\t遍数\t事件数\t平均\tp50\tp99\tp99.9\tp99.99\t最大\t逐事件计时遍总时间 ÷ E1 行时间\t切换\t压缩")
        for a in ARMS:
            v = by.get((d, a))
            if not v:
                continue
            m = lambda c: statistics.median(float(x[c]) for x in v)
            mx = max(float(x["max_ns"]) for x in v)
            sec = m("seconds")
            ov = "-"
            if e1 is not None:
                k = (a, d, "hold", "COUNT", 600)
                if k in e1.T:
                    D = int(e1.info[k]["copies"])
                    ov = "%.2f" % (sec / (e1.T[k] / D))
            p("\t".join([a, str(len(v)), v[0]["events"], us(m("mean_ns")), us(m("p50_ns")), us(m("p99_ns")), us(m("p999_ns")), us(m("p9999_ns")),
                         us(mx), ov, v[0]["switches"], v[0]["compactions"]]))
        p("按类别（次数 = 各遍中位；p99 = 各遍中位；最大 = 各遍最大）：")
        p("臂\t" + "\t".join("%s 次数\t%s p99\t%s 最大" % (CAT[c], CAT[c], CAT[c]) for c in range(4)))
        for a in ARMS:
            v = by.get((d, a))
            if not v:
                continue
            cells = []
            for c in range(4):
                n = statistics.median(int(x["n%d" % c]) for x in v)
                if n == 0:
                    cells += ["0", "-", "-"]
                else:
                    cells += ["%d" % n, us(statistics.median(float(x["p99_%d" % c]) for x in v)), us(max(float(x["max_%d" % c]) for x in v))]
            p("\t".join([a] + cells))
        p("")
    # 前 100 大值里各类别的个数（第 1 遍）
    if os.path.exists(dist):
        top = {}
        for r in read(dist):
            if r["kind"] == "top" and r["pass"] == "1":
                top.setdefault((r["data"], r["arm"]), []).append(r)
        p("## 前 100 大的事件（第 1 遍）按类别计数，以及第 100 大的值")
        p("行\t臂\t" + "\t".join(CAT[c] for c in range(4)) + "\t第 100 大")
        for d in ROWS:
            for a in ARMS:
                v = top.get((d, a))
                if not v:
                    continue
                cnt = [sum(1 for x in v if x["f3"] == str(c)) for c in range(4)]
                p("\t".join([d, a] + [str(c) for c in cnt] + [us(min(float(x["f2"]) for x in v))]))
        p("")
    cks = {}
    for r in rows:
        cks.setdefault(r["data"], set()).add(r["checksum"])
    p("每行各臂、各遍的校验和一致：%s" % ("、".join("%s %s" % (d, len(c) == 1) for d, c in sorted(cks.items()))))
    if e1 is not None:
        same = []
        for d in ROWS:
            k = ("M", d, "hold", "COUNT", 600)
            if k in e1.info and d in cks and int(e1.info[k]["copies"]) == 1:
                same.append("%s %s" % (d, cks[d] == e1.info[k]["checksum"]))
        p("与 E1 同格（D = 1 的行）的校验和相同：%s" % ("、".join(same) or "-"))
    open(rep, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("写了 %s（%d 行）" % (rep, len(out)))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0] if len(a) > 0 else os.path.join(HERE, "handoff", "e6_latency.tsv"),
         a[1] if len(a) > 1 else os.path.join(HERE, "handoff", "e6_dist.tsv"),
         a[2] if len(a) > 2 else os.path.join(HERE, "report_e6.txt"))
