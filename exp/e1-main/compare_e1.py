r"""E1 · 判读脚本。判据原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 判据开始 -->
**问题**：同 M1 判据（`exp/m1-trend-index/README.md` 第 1 节）：单类型 Kleene 模式的趋势聚合 `RETURN g, AGG PATTERN E+ SEMANTICS skip-till-any-match WHERE [g] AND E.a ⋈ NEXT(E).a WITHIN W SLIDE s`，⋈ ∈ {>, <}（严格），AGG ∈ {COUNT(*), SUM(E.a)}；语义、取模、整数属性、窗口编号全部沿用 M1。

**臂**（全部一个二进制，同一编译选项）：
- **OPP**：M1 的 GRETA / Cogra 复现，代码不改。
- **M**：窗口槽聚合树（M1 第 2.3 节）+ **代价规则选择器**（`exp/e4-lowfreq/README.md` 第 1 节定义：按扫描自身的累加计数与索引路径长度之比切换，常数 c 在 E4 开发段定、提交后不动）。
- 消融，照报、不进判据：**A1** 每个活跃窗口各一棵树（M1 同）；**A2** 过期改成逐个删（窗格结束时把死结点逐个从树里删除、沿路径重算子树槽），其余同 M；**A4** 始终索引（M1 同）；**A5** 切换规则换回 M1 的按组规模阈值（τ_low = 16、τ_high = 32），其余同 M。

**主指标**：处理完整条流的墙钟时间（数据已解析进内存后，从第一个事件到最后一个窗口输出），单线程。**计时口径（新）**：每个 (臂 × 行) 起 P = 3 个进程，同一行的 3 × 臂数 次调用按「进程 → 臂」交错轮着跑（不是一个臂连跑三次）；每个进程：解析数据（不计时）→ 预热 1 遍 → 重复 R 遍，R = min(200, max(5, ⌈2 s ÷ 预热遍时间⌉))，每遍新建全部结构、计时包住全流处理 + 最后一批窗口输出；进程内取 R 遍的中位，**行的时间 = 3 个进程的中位**；另报 3 个进程的最大 ÷ 最小作噪声带。**短行加长**：预热遍 < 5 ms 的行，把流复制 D = min(50, ⌈5 ms ÷ 预热遍时间⌉) 份首尾相接、每份时间平移整段时长（组不变、顺序不变），所有臂同一份加长流，表里注明 D。行的比值 r = T_OPP ÷ T_M。

**数据与查询**（每份数据一个 ⋈、一个 s，沿用 T20 / M1；W ∈ {5, 10, 30} 分钟；AGG ∈ {COUNT, SUM}；每份数据 6 行）：
- 留出：WPI 其余 5 只（价格 >，s = 10 s）、PAMAP2 subject105–109（心率 <，s = 30 s）、Nasdaq 分钟线（收盘价 >，s = 5 min）、Dublin 公交（延误 <，s = 5 min）；**新数据以用户批准为准、未批则不含、记入偏离**：Binance aggTrades 5 个交易对 × 1 天（价格 >，s = 10 s；高频）、Porto 出租车 2013-07（由 GPS 推导的速度 <，s = 1 min；中频）、METR-LA（车速 >，s = 5 min；低频）。
- 开发行照跑、表里标「开发」：WPI 前 5 只、PAMAP2 subject101–104。
- 数据准备规则在第 2.2 节（整数化、时间微秒、推导属性）；准备脚本提交后不改。

**K1**（C4；高频留出行 = WPI 6 + PAMAP2 6，加 Binance 6 若有）：r 的中位 ≥ 1.5，且至少一行 r ≥ 2。
**K3**（选择器不伤高频；同一组行）：T_M ÷ T_A5 的中位 ≤ 1.05。
**二值**：K1 与 K3 同时成立 ⇒ **主表成立**，C4 进正文；否则不停，C4 按实测数改写（账本行），原因写进第 0 节。
**不在本实验判的**：C5（中低频不慢于 1.1 倍）在 E4 的新留出数据上判；Nasdaq、公交两份在本实验照报，表里注明「切换规则在看过 M1 的公交结果后重设计，这两份不是规则的留出」。

**消融的设计规则**（不是判据，触发了就改设计并记偏离）：
- A1：只看 k ≥ 2 的留出行（k = 1 时两种设计是同一个结构）；若 T_A1 ÷ T_M 的中位 < 1 ⇒ 论文的多窗口方案改用 A1。
- A2：若高频留出行 T_A2 ÷ T_M 的中位 < 1 ⇒ 过期改用逐个删。
- A4、A5：照报；贡献 = Σ T_A ÷ Σ T_M 按数据直接合计，另报按行中位。

**正确性闸**（不是判据；不过先查代码，不计时）：M1 的 (a) 合成小流暴力对拍与 (b) 每份真实数据每组前 2,000 个事件逐窗口相等，对全部六个臂、全部数据重跑；另加 (c) 索引模式下降得到的「合格前驱累加数」逐事件等于扫描模式 OPP 的累加计数（E4 规则的输入）。

**描述性**（照报，不进判据）：每行每臂的峰值内存（ru_maxrss）与 M ÷ OPP 的范围，对照结点块的解析比（M 每结点 own k + sub k 个槽、SUM 时各 cnt、sum，加窗口号与活事件数；OPP 每顶点 k 或 2k 个数；压缩允许死结点 ≤ 活结点）；每行每臂的工作量计数（OPP 前驱访问、窗口累加；M 结点访问、槽读写）；M 每行的切换次数与各模式处理的事件占比；每组每窗事件数中位；3 进程噪声带；按样本直接合计的 Σ T_OPP ÷ Σ T_M（高频、低频各一个）。
<!-- 判据结束 -->

用法：python3 -I exp/e1-main/compare_e1.py  → 写 report_e1.txt
输入：handoff/e1_times.tsv（由 run_e1.sh 产出）
实验段在判据文字之后补判读主体：K1 / K3 判读、主表、消融、内存、工作量各表。判据文字之后不动。
"""
import math, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
TIMES = os.path.join(HERE, "handoff", "e1_times.tsv")
ARMS = ["OPP", "M", "A1", "A2", "A4", "A5"]
HIGH = ["wpi", "pamap2", "binance"]          # 高频留出（K1 / K3）
LOW = ["nasdaq", "bus", "porto", "metrla"]   # 中低频（照报；Porto / METR-LA 在 E4 判 K2'）
ORDER = ["wpi", "pamap2", "binance", "nasdaq", "bus", "porto", "metrla"]
S_OF = {"wpi": 10, "pamap2": 30, "binance": 10, "nasdaq": 300, "bus": 300, "porto": 60, "metrla": 300, "intel": 60}
NOTE_M1 = "切换规则在看过 M1 的公交结果后重设计，这两份不是规则的留出"


def criteria_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 判据开始 -->"):s.index("<!-- 判据结束 -->")]
    return cut(me) == cut(rd)


def read_tsv(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:] if l]


class Times:
    """e1_times.tsv（或同列的 e2 / e4 表）→ 每个 (臂, 数据, 切分, AGG, W[, xnum]) 的行时间 = 各进程内中位的中位；噪声带 = 进程中位的最大 ÷ 最小。"""

    def __init__(self, path, key_extra=()):
        self.rows = read_tsv(path)
        self.extra = key_extra
        per = defaultdict(lambda: defaultdict(list))
        self.info = {}
        for r in self.rows:
            k = self.key(r)
            per[k][r["proc"]].append(float(r["seconds"]))
            inf = self.info.setdefault(k, {"maxrss": [], "copies": r["copies"]})
            inf["maxrss"].append(int(r["maxrss_kb"]))
            if r["work_adds"] != "-":
                inf.update(work_pred=int(r["work_pred"]), work_adds=int(r["work_adds"]), work_nodes=int(r["work_nodes"]),
                           idx=int(r["idx_events"]), events=int(r["events"]), ratio=float(r["ratio_med"]))
            inf["switches"] = int(r["switches"])
            inf["checksum"] = inf.get("checksum", set()) | {r["checksum"]}
        self.procmed = {k: [statistics.median(v) for _, v in sorted(d.items())] for k, d in per.items()}
        self.T = {k: statistics.median(v) for k, v in self.procmed.items()}

    def key(self, r):
        return (r["arm"], r["data"], r["split"], r["agg"], int(r["W"])) + tuple(r[e] for e in self.extra)

    def band(self, k):
        """只有 1 个进程（慢行单次计时，README 第 3 节偏离 1）时记 nan。"""
        v = self.procmed.get(k, [])
        return max(v) / min(v) if len(v) >= 2 else float("nan")

    def rowkeys(self):
        return sorted({k[1:] for k in self.T}, key=lambda k: (ORDER.index(k[0]) if k[0] in ORDER else 99, k[1] != "dev", k[2], k[3]) + k[4:])


def nmed(data, split, Ws):
    """每组每窗事件数中位（只算含事件的窗口；被忽略的 data/ 不在就记 None）。"""
    import prep_e1
    sys.path.insert(0, HERE)
    f = os.path.join(HERE, "..", "m1-trend-index", "data", "%s_%s.tsv" % (data, split))
    if data in ("binance", "porto", "metrla"):
        f = os.path.join(HERE, "data", "%s_%s.tsv" % (data, split))
    if data == "intel":
        f = os.path.join(HERE, "..", "e4-lowfreq", "data", "intel_dev.tsv")
    if not os.path.exists(f):
        return {w: None for w in Ws}
    return prep_e1.stats(f, S_OF[data], Ws=sorted(set(Ws)))[2]


def fb(x):
    return "-" if x != x else "%.3f" % x


def med(v):
    return statistics.median(v) if v else float("nan")


def judge(tm):
    L = []
    hi = [k for k in tm.rowkeys() if k[0] in HIGH and k[1] == "hold" and ("OPP",) + k in tm.T and ("M",) + k in tm.T]
    have = sorted({k[0] for k in hi}, key=ORDER.index)
    r = [tm.T[("OPP",) + k] / tm.T[("M",) + k] for k in hi]
    L.append("## 判读（README 第 1 节；高频留出行 = %s，共 %d 行）" % (" + ".join(have), len(hi)))
    if "binance" not in have:
        L.append("Binance 不在表里 ⇒ K1 / K3 只用 WPI + PAMAP2 的 12 行（偏离记 README 第 3 节）")
    k1 = bool(r) and med(r) >= 1.5 and max(r) >= 2
    L.append("K1：r = T_OPP ÷ T_M 中位 %.3f（线 1.5）、最大 %.3f（线 2）、最小 %.3f ⇒ %s" % (med(r), max(r), min(r), "成立" if k1 else "不成立"))
    q = [tm.T[("M",) + k] / tm.T[("A5",) + k] for k in hi if ("A5",) + k in tm.T]
    k3 = len(q) == len(hi) and med(q) <= 1.05
    L.append("K3：T_M ÷ T_A5 中位 %.4f（线 1.05）、最大 %.4f、最小 %.4f（%d 行）⇒ %s" % (med(q), max(q), min(q), len(q), "成立" if k3 else "不成立"))
    L.append("二值：%s" % ("K1 与 K3 同时成立 ⇒ 主表成立，C4 进正文" if k1 and k3 else "不同时成立 ⇒ 不停，C4 按实测数改写（原因写进 README 第 0 节）"))
    return L


def main_table(tm):
    L = ["", "## 主表（行时间 = 3 个进程内中位的中位，秒；带 = 3 个进程中位的最大 ÷ 最小；D = 短行加长的份数；n = 每组每窗事件数中位）",
         "Nasdaq、公交两行组：" + NOTE_M1,
         "数据\t切分\tAGG\tW 分\tD\tn\t" + "\t".join("T_" + a for a in ARMS) + "\tr=OPP/M\t带 OPP\t带 M\t校验和一致"]
    ns = {}
    for k in tm.rowkeys():
        d, sp, agg, W = k[:4]
        if (d, sp) not in ns:
            ns[(d, sp)] = nmed(d, sp, [w for (dd, ss, _, w) in tm.rowkeys() if (dd, ss) == (d, sp)])
        ts = [tm.T.get((a,) + k) for a in ARMS]
        cks = set().union(*[tm.info[(a,) + k]["checksum"] for a in ARMS if (a,) + k in tm.info])
        rr = ts[0] / ts[1] if ts[0] and ts[1] else float("nan")
        L.append("%s\t%s\t%s\t%d\t%s\t%s\t%s\t%.3f\t%s\t%s\t%s" % (
            d, "开发" if sp == "dev" else "留出", agg, W // 60, tm.info[("M",) + k]["copies"] if ("M",) + k in tm.info else "-", ns[(d, sp)].get(W),
            "\t".join("%.4f" % t if t is not None else "-" for t in ts), rr,
            fb(tm.band(("OPP",) + k)), fb(tm.band(("M",) + k)), "是" if len(cks) == 1 else "否（%d 个）" % len(cks)))
    return L


def ablation(tm):
    L = ["", "## 消融（README 第 1 节「消融的设计规则」）"]
    hold = [k for k in tm.rowkeys() if k[1] == "hold"]
    kk = lambda k: k[3] // S_OF[k[0]]
    a1 = [tm.T[("A1",) + k] / tm.T[("M",) + k] for k in hold if kk(k) >= 2 and ("A1",) + k in tm.T]
    lt = [k for k in hold if kk(k) >= 2 and ("A1",) + k in tm.T and tm.T[("A1",) + k] < tm.T[("M",) + k]]
    L.append("A1（留出、k ≥ 2 的 %d 行）：T_A1 ÷ T_M 中位 %.3f、最小 %.3f ⇒ %s；A1 快于 M 的行：%s" % (
        len(a1), med(a1), min(a1), "触发（论文的多窗口方案改用 A1）" if med(a1) < 1 else "不触发",
        "、".join("%s %s W=%d" % (k[0], k[2], k[3] // 60) for k in lt) or "无"))
    hi = [k for k in hold if k[0] in HIGH and ("A2",) + k in tm.T]
    a2 = [tm.T[("A2",) + k] / tm.T[("M",) + k] for k in hi]
    L.append("A2（高频留出 %d 行）：T_A2 ÷ T_M 中位 %.3f、最小 %.3f、最大 %.3f ⇒ %s" % (
        len(a2), med(a2), min(a2), max(a2), "触发（过期改用逐个删）" if med(a2) < 1 else "不触发"))
    for a in ("A1", "A2", "A4", "A5"):
        parts = []
        for d in ORDER:
            ks = [k for k in hold if k[0] == d and (a,) + k in tm.T and ("M",) + k in tm.T]
            if ks:
                parts.append("%s %.3f（行中位 %.3f）" % (d, sum(tm.T[(a,) + k] for k in ks) / sum(tm.T[("M",) + k] for k in ks),
                                                   med([tm.T[(a,) + k] / tm.T[("M",) + k] for k in ks])))
        L.append("%s 贡献 Σ T_%s ÷ Σ T_M（留出，按数据直接合计）：%s" % (a, a, "；".join(parts)))
    return L


def memory(tm):
    L = ["", "## 内存（ru_maxrss，3 个进程的最大，MB；描述性）",
         "解析比（每个活事件）：M 结点 = own k（SUM 再 k）+ 子树槽 k ×（窗口号、cnt、[sum]、nev）个 8 字节数 + 32 字节键与指针，压缩允许死结点 ≤ 活结点；"
         "OPP 顶点 = k（SUM 2k）个 8 字节数 + 28 字节 ⇒ k 大时 M ÷ OPP → 4（COUNT）/ 3（SUM），算上死结点 ≤ 8 / 6",
         "数据\t切分\tAGG\tW 分\t" + "\t".join("MB_" + a for a in ARMS) + "\tM÷OPP\t解析比（活）"]
    rat = defaultdict(list)
    for k in tm.rowkeys():
        mb = [max(tm.info[(a,) + k]["maxrss"]) / 1024 if (a,) + k in tm.info else None for a in ARMS]
        kk = k[3] // S_OF[k[0]]
        an = ((6 if k[2] == "SUM" else 4) * kk * 8 + 32) / ((2 if k[2] == "SUM" else 1) * kk * 8 + 28)
        x = mb[1] / mb[0] if mb[0] and mb[1] else float("nan")
        rat["高频" if k[0] in HIGH else "中低频"].append(x)
        L.append("%s\t%s\t%s\t%d\t%s\t%.2f\t%.2f" % (k[0], k[1], k[2], k[3] // 60, "\t".join("%.1f" % m if m else "-" for m in mb), x, an))
    for g, v in rat.items():
        L.append("%s M ÷ OPP 峰值内存：%.2f – %.2f（%d 行）" % (g, min(v), max(v), len(v)))
    return L


def work(tm):
    L = ["", "## 工作量与模式（第 1 个进程的 --work 计数；描述性）",
         "数据\t切分\tAGG\tW 分\tOPP 前驱访问\tOPP 窗口累加\tM 结点访问\tM 槽读写\tOPP累加÷M槽\tM 切换\tM 索引事件占比\tA2 切换\ts̄÷ī 中位"]
    for k in tm.rowkeys():
        o, m, a2 = tm.info.get(("OPP",) + k, {}), tm.info.get(("M",) + k, {}), tm.info.get(("A2",) + k, {})
        if "work_adds" not in o or "work_adds" not in m:
            continue
        L.append("%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%.2f\t%d\t%.3f\t%s\t%.3g" % (
            k[0], k[1], k[2], k[3] // 60, o["work_pred"], o["work_adds"], m["work_nodes"], m["work_adds"],
            o["work_adds"] / max(1, m["work_adds"]), m["switches"], m["idx"] / max(1, m["events"]), a2.get("switches", "-"), m["ratio"]))
    return L


def totals(tm):
    L = ["", "## 按样本直接合计（留出；README 第 1 节描述性）"]
    for name, ds in (("高频", HIGH), ("中低频", LOW)):
        ks = [k for k in tm.rowkeys() if k[0] in ds and k[1] == "hold" and ("OPP",) + k in tm.T and ("M",) + k in tm.T]
        if ks:
            L.append("%s（%s）Σ T_OPP ÷ Σ T_M = %.3f（%d 行；按行 r 中位 %.3f）" % (
                name, " + ".join(d for d in ds if any(k[0] == d for k in ks)), sum(tm.T[("OPP",) + k] for k in ks) / sum(tm.T[("M",) + k] for k in ks),
                len(ks), med([tm.T[("OPP",) + k] / tm.T[("M",) + k] for k in ks])))
    for d in ORDER:
        ks = [k for k in tm.rowkeys() if k[0] == d and k[1] == "hold" and ("OPP",) + k in tm.T and ("M",) + k in tm.T]
        if ks:
            L.append("%s：Σ T_OPP ÷ Σ T_M = %.3f；行 r 中位 %.3f、最小 %.3f、最大 %.3f%s" % (
                d, sum(tm.T[("OPP",) + k] for k in ks) / sum(tm.T[("M",) + k] for k in ks),
                med([tm.T[("OPP",) + k] / tm.T[("M",) + k] for k in ks]), min(tm.T[("OPP",) + k] / tm.T[("M",) + k] for k in ks),
                max(tm.T[("OPP",) + k] / tm.T[("M",) + k] for k in ks), "（" + NOTE_M1 + "）" if d in ("nasdaq", "bus") else ""))
    bands = [tm.band(k) for k in tm.procmed if len(tm.procmed[k]) >= 2]
    single = sorted("%s %s %s %s W=%d" % ((k[0],) + k[1:4] + (k[4] // 60,)) for k in tm.procmed if len(tm.procmed[k]) < 2)
    L.append("3 进程噪声带（全部 臂 × 行）：中位 %.3f、最大 %.3f（%d 个）" % (med(bands), max(bands), len(bands)))
    L.append("慢行单次计时（探测遍 ≥ 60 s，README 第 3 节偏离 1）的 (臂 × 行)：%s" % ("、".join(single) or "无"))
    return L


def rerun(tm):
    """README 第 3 节偏离 2（补充实验 ①）：Binance 留出 COUNT W = 10 分一格的重跑，只读 handoff/e1_rerun_binance.tsv，只报不判。"""
    f = os.path.join(HERE, "handoff", "e1_rerun_binance.tsv")
    if not os.path.exists(f):
        return []
    rr = Times(f)
    row = ("binance", "hold", "COUNT", 600)
    L = ["", "## 重跑（README 第 3 节偏离 2：Binance 留出 COUNT W = 10 分一格，同口径另跑一次；原表与上面各节不改，只报不判）",
         "臂	原 T	原 带	重跑 T	重跑 带	重跑 ÷ 原"]
    for a in ARMS:
        k = (a,) + row
        if k in rr.T and k in tm.T:
            L.append("%s\t%.4f\t%s\t%.4f\t%s\t%.3f" % (a, tm.T[k], fb(tm.band(k)), rr.T[k], fb(rr.band(k)), rr.T[k] / tm.T[k]))
    def q(t, a, b):
        return t.T[(a,) + row] / t.T[(b,) + row] if (a,) + row in t.T and (b,) + row in t.T else float("nan")
    L.append("r = T_OPP ÷ T_M：原 %.3f、重跑 %.3f；T_M ÷ T_A5：原 %.4f、重跑 %.4f" % (q(tm, "OPP", "M"), q(rr, "OPP", "M"), q(tm, "M", "A5"), q(rr, "M", "A5")))
    cks = {c for k in rr.info if k[1:] == row for c in rr.info[k]["checksum"]} | {c for k in tm.info if k[1:] == row for c in tm.info[k]["checksum"]}
    L.append("六个臂、两次跑的整流校验和一致：%s" % (len(cks) == 1))
    single = sorted("%s" % k[0] for k in rr.T if len(rr.procmed[k]) == 1)
    L.append("重跑里单次计时（探测遍 ≥ 60 s，偏离 1）的臂：%s" % ("、".join(single) or "无"))
    return L


def main():
    ok = criteria_same()
    L = ["判据两处同文：%s" % ok]
    if not ok:
        print(L[0]); sys.exit(1)
    if not os.path.exists(TIMES):
        print(L[0]); print("没有 handoff/e1_times.tsv（先 bash run_e1.sh all）"); sys.exit(1)
    tm = Times(TIMES)
    L += judge(tm) + main_table(tm) + ablation(tm) + memory(tm) + work(tm) + totals(tm) + rerun(tm)
    txt = "\n".join(L) + "\n"
    open(os.path.join(HERE, "report_e1.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
