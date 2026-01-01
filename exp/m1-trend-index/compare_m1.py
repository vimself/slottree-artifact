r"""M1 · 判读脚本。判据原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 判据开始 -->
**问题**：单类型 Kleene 模式的趋势聚合 `RETURN g, AGG PATTERN E+ SEMANTICS skip-till-any-match WHERE [g] AND E.a ⋈ NEXT(E).a WITHIN W SLIDE s`，⋈ ∈ {>, <}（严格），AGG ∈ {COUNT(*), SUM(E.a)}。语义同 T20 判据（`exp/t20-trend-headroom/README.md` 第 1 节）：窗口 j 覆盖 [j·s, j·s + W)，时间以数据最早时间为 0；每个窗口、每个组，所有「组内按时间递增、相邻两个事件满足 ⋈」的事件序列：COUNT 数序列个数，SUM 把每条序列里各事件的 a 相加再求总和（GRETA 定义 2、Cogra §2.3）。算术统一取模 2⁶⁴（无符号 64 位回绕），属性 a 取整数（分 / 次每分钟 / 秒）；所有臂同一口径。

**臂**：
- **OPP**：C++ 复现 GRETA 运行时（PVLDB'17 §7–8；单类型 Kleene + 相邻谓词时 Cogra SIGMOD'19 的混合粒度聚合器退化为它，Cogra §5 Alg. 2 第 10–11 行）：按窗格（= 滑动步长 s）分段，每个窗格一棵按 a 有序的顶点树，新事件在覆盖它的各窗格树上做范围查找，对每个合格前驱 p、对 p 与 e 的每个共同窗口累加一次；窗格在它所属的最后一个窗口关闭后整体删除。
- **M**：本文方法（第 2.3 节）：每组一棵按 a 有序的聚合树，结点存按窗口槽切分的部分聚合，新事件一次下降 + 一次插入；每组事件少时按规则退回 OPP 的扫描。
- 消融 **A1**（每个活跃窗口各一棵聚合树，不切槽）、**A4**（不按组规模切换，始终用索引）：照报，不进判据。

**主指标**：处理完整条流的墙钟时间（数据已解析进内存后，从第一个事件到最后一个窗口输出），单线程，每个 (数据 × 查询) 一行，1 次预热后重复 5 次取中位。行的比值 r = T_OPP ÷ T_M。

**开发 / 留出**：开发 = WPI 按代码排序的前 5 只（AMAT、CSCO、DELL、INTC、IPIX）+ PAMAP2 的 subject101–104；留出 = WPI 其余 5 只（MSFT、ORCL、QQQ、RIMM、YHOO）+ PAMAP2 的 subject105–109（高频，判 K1），Nasdaq 分钟线与 Dublin 公交全部（低频，判 K2）。方法只在开发集上迭代（每个变体在第 3 节记一行）；留出集每个臂只跑一次定稿版本。

**查询**（每份数据的 ⋈、s 沿用 T20；W 扫三档）：WPI 价格 >、s = 10 s；PAMAP2 心率 <、s = 30 s；Nasdaq 收盘价 >、s = 5 min；公交延误 <、s = 5 min；W ∈ {5, 10, 30} 分钟；AGG ∈ {COUNT, SUM}。每份数据 6 行。

**K1**（高频留出，WPI 6 行 + PAMAP2 6 行）：12 行 r 的中位 ≥ 1.5，且至少一行 r ≥ 2。
**K2**（低频留出）：Nasdaq 与公交各自 6 行 r 的中位 ≥ 1 / 1.1（即 M 不慢于 OPP 的 1.1 倍）。
**二值**：K1 与 K2 同时成立 ⇒ **MVP 过**；否则 **不过**（走 `<internal>` 第 2 节的退路，止损线在 `<internal>`）。

**中途检查**（11-02，开发集）：同样 12 行的口径在开发数据上算 r；中位 < 1.2 就如实报，由用户当次决定停不停。

**正确性闸**（不是判据；不过先查代码，不判读）：(a) 合成小流（每组 ≤ 60 个事件、随机 W / s / ⋈、属性值域小以制造重复值）上所有臂的每窗口 COUNT 与 SUM 等于按定义的暴力枚举（Python 大整数再取模）；(b) 每份真实数据每组前 2,000 个事件上，所有臂逐窗口相等。

**描述性**（照报，不进判据）：每行的峰值内存（ru_maxrss）；OPP 的前驱访问次数与 M 的结点访问次数（与 T20 的工作量模型对照）；A1、A4 的时间与 r；每组每窗事件数中位。
<!-- 判据结束 -->

用法：python3 -I exp/m1-trend-index/compare_m1.py [dev|hold]  → 写 report_m1.txt
输入：handoff/m1_times.tsv（列：arm data split agg W s rep seconds maxrss_kb work_units；由 run_m1.sh 产出）
"""
import math, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
K1_MED, K1_ONE, K2_MED = 1.5, 2.0, 1 / 1.1
HIGH, LOW = ("wpi", "pamap2"), ("nasdaq", "bus")
S_OF = {"wpi": 10, "pamap2": 30, "nasdaq": 300, "bus": 300}


def criteria_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 判据开始 -->"):s.index("<!-- 判据结束 -->")]
    return cut(me) == cut(rd)


def read_tsv(name):
    path = os.path.join(HERE, "handoff", name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("\t")
        return [dict(zip(head, l.rstrip("\n").split("\t"))) for l in f if l.strip()]


def medians(rows, field="seconds", fn=statistics.median):
    reps = defaultdict(list)
    for r in rows:
        reps[(r["arm"], r["data"], r["split"], r["agg"], r["W"])].append(float(r[field]))
    return {key: fn(v) for key, v in reps.items()}


def load_times():
    rows = read_tsv("m1_times.tsv")
    return None if rows is None else medians(rows)


def ratios(med, split, datas, num="OPP", den="M"):
    out = []  # (data, agg, W, r)
    for (arm, data, sp, agg, W), t in sorted(med.items()):
        if arm != num or sp != split or data not in datas:
            continue
        tm = med.get((den, data, sp, agg, W))
        if tm:
            out.append((data, agg, W, t / tm))
    return out


def window_sizes(data, split, W):
    """每组每窗事件数（只算含事件的窗口）：按窗格计数再滑动求和。读被忽略的 data/，没有就跳过。"""
    path = os.path.join(HERE, "data", "%s_%s.tsv" % (data, split))
    if not os.path.exists(path):
        return None
    s = S_OF[data] * 1000000
    k = W // S_OF[data]
    panes = defaultdict(lambda: defaultdict(int))
    for line in open(path, encoding="utf-8"):
        g, t, _ = line.split("\t")
        panes[g][int(t) // s] += 1
    sizes = []
    for g, pc in panes.items():
        js = set()
        for p in pc:
            js.update(range(p - k + 1, p + 1))
        for j in js:
            sizes.append(sum(pc.get(p, 0) for p in range(j, j + k)))
    return statistics.median(sizes)


def main():
    split = sys.argv[1] if len(sys.argv) > 1 else "hold"
    L = ["判据两处同文：%s" % criteria_same(), ""]
    rows = read_tsv("m1_times.tsv")
    med = None if rows is None else medians([r for r in rows if r["split"] == split])
    if not med:
        L.append("尚无 handoff/m1_times.tsv 的 %s 行，不判读。" % split)
    else:
        hi = ratios(med, split, HIGH)
        L.append("## %s 段：高频 12 行 r = T_OPP ÷ T_M" % split)
        for d, a, W, r in hi:
            L.append("%s\t%s\tW=%s\t%.3f" % (d, a, W, r))
        if hi:
            m = statistics.median([x[3] for x in hi])
            L.append("中位 %.3f（行数 %d）；最大 %.3f" % (m, len(hi), max(x[3] for x in hi)))
            if split == "dev":
                L.append("中途检查：中位 %s 1.2 ⇒ %s" % (">=" if m >= 1.2 else "<", "继续" if m >= 1.2 else "如实报，由用户定停不停"))
            else:
                k1 = m >= K1_MED and max(x[3] for x in hi) >= K1_ONE
                L.append("K1：%s" % ("成立" if k1 else "不成立"))
                k2 = True
                for d in LOW:
                    lo = [x[3] for x in ratios(med, split, (d,))]
                    if lo:
                        md = statistics.median(lo)
                        ok = md >= K2_MED
                        k2 = k2 and ok
                        L.append("K2 %s：6 行 r 中位 %.3f（M ÷ OPP = %.3f）⇒ %s" % (d, md, 1 / md, "成立" if ok else "不成立"))
                    else:
                        k2 = False
                        L.append("K2 %s：无数据" % d)
                L.append("⇒ MVP %s" % ("过" if (k1 and k2) else "不过"))
        L += describe(rows, split)
    L += describe_tau() + describe_shape() + describe_diag()
    with open(os.path.join(HERE, "report_m1.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))


def describe(rows, split):
    """描述性（照报，不进判据）。"""
    rows = [r for r in rows if r["split"] == split]
    med, mn = medians(rows), medians(rows, fn=min)
    one = {}  # 每 (臂 × 行) 一份：内存、工作量、校验和
    for r in rows:
        one[(r["arm"], r["data"], r["agg"], r["W"])] = r
    datas = [d for d in HIGH + LOW if any(r["data"] == d for r in rows)]
    L = ["", "## 描述性（%s 段；不进判据）" % split,
         "数据\tAGG\tW\tT_OPP 中位 s\tT_M\tT_A1\tT_A4\tr=OPP/M\tr 按最小值\tr_A1=OPP/A1\tr_A4=OPP/A4\tM/A1 加速\t每组每窗事件中位"]
    for d in datas:
        for W in ("300", "600", "1800"):
            ws = window_sizes(d, split, int(W))
            for a in ("COUNT", "SUM"):
                g = lambda arm, m=med: m.get((arm, d, split, a, W))
                if g("OPP") is None:
                    continue
                f = lambda x: "%.4f" % x if x is not None else "—"
                rr = lambda x, y: "%.3f" % (x / y) if (x and y) else "—"
                L.append("\t".join([d, a, W, f(g("OPP")), f(g("M")), f(g("A1")), f(g("A4")), rr(g("OPP"), g("M")),
                                    rr(g("OPP", mn), g("M", mn)), rr(g("OPP"), g("A1")), rr(g("OPP"), g("A4")),
                                    rr(g("A1"), g("M")), "%g" % ws if ws is not None else "—"]))
    for name, ds in (("高频", HIGH), ("低频", LOW)):
        for den in ("M", "A1", "A4"):
            v = [x[3] for x in ratios(med, split, ds, den=den)]
            if v:
                L.append("%s r_%s = T_OPP ÷ T_%s：中位 %.3f、最小 %.3f、最大 %.3f（%d 行）" % (name, den, den, statistics.median(v), min(v), max(v), len(v)))
    v = [x[3] for x in ratios(med, split, HIGH + LOW, num="A1", den="M")]
    if v:
        L.append("M 比 A1 快的倍数（T_A1 ÷ T_M）：中位 %.3f、最小 %.3f（全部 %d 行；< 1 的行要按 README 第 2.4 节处理）" % (statistics.median(v), min(v), len(v)))
    tot = defaultdict(float)
    for (arm, d, sp, a, W), t in med.items():
        tot[(arm, d in HIGH)] += t
    for hf, name in ((True, "高频"), (False, "低频")):
        if tot.get(("OPP", hf)) and tot.get(("M", hf)):
            L.append("%s整组总时间之比 Σ T_OPP ÷ Σ T_M = %.3f（按样本直接合计，对照按行中位）" % (name, tot[("OPP", hf)] / tot[("M", hf)]))
    tot_d = defaultdict(float)
    for (arm, d, sp, a, W), t in med.items():
        tot_d[(arm, d)] += t
    for d in datas:
        if tot_d.get(("OPP", d)) and tot_d.get(("M", d)):
            L.append("%s 6 行总时间之比 Σ T_OPP ÷ Σ T_M = %.3f；Σ T_A4 ÷ Σ T_M = %.3f（切换的贡献）" % (
                d, tot_d[("OPP", d)] / tot_d[("M", d)], tot_d[("A4", d)] / tot_d[("M", d)]))
    slow = ["%s %s W=%s（T_A1 ÷ T_M = %.3f）" % x for x in ratios(med, split, HIGH + LOW, num="A1", den="M") if x[3] < 1]
    L.append("A1 比 M 快的行：%s" % ("；".join(slow) if slow else "无"))
    for name, ds in (("高频", HIGH), ("低频", LOW)):
        mr = [int(one[("M", d, a, W)]["maxrss_kb"]) / int(one[("OPP", d, a, W)]["maxrss_kb"])
              for d in ds for a in ("COUNT", "SUM") for W in ("300", "600", "1800") if ("M", d, a, W) in one and ("OPP", d, a, W) in one]
        if mr:
            L.append("%s峰值内存 M ÷ OPP：%.2f – %.2f 倍（%d 行，ru_maxrss）" % (name, min(mr), max(mr), len(mr)))
    L += ["", "峰值内存（ru_maxrss，MB）与工作量计数", "数据\tAGG\tW\tOPP MB\tM MB\tA1 MB\tA4 MB\tOPP 前驱访问\tOPP 窗口累加\tM 结点访问\tM 槽读写\t累加 ÷ 槽读写\tchecksum 一致"]
    for d in datas:
        for W in ("300", "600", "1800"):
            for a in ("COUNT", "SUM"):
                o = {arm: one.get((arm, d, a, W)) for arm in ("OPP", "M", "A1", "A4")}
                if not o["OPP"]:
                    continue
                mb = lambda r: "%.0f" % (int(r["maxrss_kb"]) / 1024) if r else "—"
                same = len({r["checksum"] for r in o.values() if r}) == 1
                wo, wm = int(o["OPP"]["work_units"]), int(o["M"]["work_units"]) if o["M"] else 0
                L.append("\t".join([d, a, W, mb(o["OPP"]), mb(o["M"]), mb(o["A1"]), mb(o["A4"]), o["OPP"]["work_pred"], str(wo),
                                    o["M"]["work_nodes"] if o["M"] else "—", str(wm), "%.2f" % (wo / wm) if wm else "—", str(same)]))
    return L


def describe_tau():
    rows = read_tsv("m1_tau.tsv")
    if not rows:
        return []
    reps = defaultdict(list)
    for r in rows:
        reps[(r["tau"], r["data"], r["agg"], r["W"])].append(float(r["seconds"]))
    tot = defaultdict(float)
    for (tau, d, a, W), v in reps.items():
        tot[tau] += statistics.median(v)
    best = min(tot, key=lambda t: (tot[t], int(t)))
    L = ["", "## τ_low（开发集 12 行、M 的中位时间之和；README 第 2.3 节，取最小）"]
    L += ["τ_low=%s\t%.4f s%s" % (t, tot[t], "  ← 最小" if t == best else "") for t in sorted(tot, key=int)]
    return L


def describe_shape():
    rows = read_tsv("m1_shape.tsv")
    if not rows:
        return []
    reps = defaultdict(list)
    work = {}
    for r in rows:
        reps[(r["arm"], int(r["n_per_window"]), float(r["selectivity"]))].append(float(r["seconds"]))
        work[(r["arm"], int(r["n_per_window"]), float(r["selectivity"]))] = int(r["work_units"])
    md = {k: statistics.median(v) for k, v in reps.items()}
    L = ["", "## 对手校准：合成流形状（README 第 2.2 节第 5 条；单组、W = 100 s、s = 10 s、⋈ 为 <、COUNT、3 次中位）",
         "臂\t每窗事件数\t选择度\t秒\t工作量（OPP 窗口累加 / M 槽读写）\t相对上一档的时间增长指数"]
    for arm in ("OPP", "A4"):
        prev = None
        for n in (1000, 2000, 5000, 10000, 20000):
            t = md.get((arm, n, 0.5))
            if t is None:
                continue
            ex = "%.2f" % (math.log(t / prev[1]) / math.log(n / prev[0])) if prev else "—"
            L.append("%s\t%d\t0.5\t%.4f\t%d\t%s" % (arm, n, t, work[(arm, n, 0.5)], ex))
            prev = (n, t)
        for sel in (0.1, 0.5, 0.9):
            t = md.get((arm, 5000, sel))
            if t is not None:
                L.append("%s\t5000\t%.1f\t%.4f\t%d\t（选择度扫描）" % (arm, sel, t, work[(arm, 5000, sel)]))
    return L


def describe_diag():
    """判读后诊断（不进判据、不改判读）：公交 6 行，同一 (臂 × 行) 3 个进程的中位，看进程间波动与「M 不切换」。"""
    rows = read_tsv("m1_diag.tsv")
    if not rows:
        return []
    reps = defaultdict(list)
    for r in rows:
        reps[(r["agg"], r["W"], r["arm"] + ("" if r["tau"] != "1000000000" else "-scan"), r["proc"])].append(float(r["seconds"]))
    md = {k: statistics.median(v) for k, v in reps.items()}
    arms = ("OPP", "M", "M-scan")
    L = ["", "## 判读后诊断：公交 6 行 × 3 个进程（run_m1.sh diag；不进判据、不改判读）",
         "每格是一个进程内 5 次的中位（秒），三个进程用 / 隔开；M-scan = M 取 τ_low = 10⁹（全程扫描，只多 M 的簿记）",
         "AGG\tW\tOPP\tM（τ_low=16）\tM-scan\tr=OPP/M 各进程\tr=OPP/M-scan 各进程"]
    for W in ("300", "600", "1800"):
        for a in ("COUNT", "SUM"):
            t = {arm: [md.get((a, W, arm, p)) for p in ("1", "2", "3")] for arm in arms}
            if None in t["OPP"]:
                continue
            fmt = lambda v: " / ".join("%.4f" % x for x in v)
            rr = lambda den: " / ".join("%.3f" % (o / m) for o, m in zip(t["OPP"], t[den]))
            L.append("\t".join([a, W, fmt(t["OPP"]), fmt(t["M"]), fmt(t["M-scan"]), rr("M"), rr("M-scan")]))
    for den in ("M", "M-scan"):
        v = [md[(a, W, "OPP", p)] / md[(a, W, den, p)] for a in ("COUNT", "SUM") for W in ("300", "600", "1800") for p in ("1", "2", "3")
             if (a, W, "OPP", p) in md and (a, W, den, p) in md]
        if v:
            L.append("r = OPP ÷ %s 全部 %d 个（行 × 进程）：中位 %.3f、最小 %.3f、最大 %.3f" % (den, len(v), statistics.median(v), min(v), max(v)))
    for arm in arms:
        sp = []
        for W in ("300", "600", "1800"):
            for a in ("COUNT", "SUM"):
                v = [md.get((a, W, arm, p)) for p in ("1", "2", "3")]
                if None not in v:
                    sp.append(max(v) / min(v))
        if sp:
            L.append("%s 同一行 3 个进程的最大 ÷ 最小：中位 %.3f、最大 %.3f" % (arm, statistics.median(sp), max(sp)))
    return L


if __name__ == "__main__":
    main()
