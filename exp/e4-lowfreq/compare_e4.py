r"""E4 · 判读脚本。判据原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 判据开始 -->
**问题**：同 E1 / M1 的查询类。要回答的是：把 M1 的「按组规模阈值」换成下面的代价规则之后，方法在中低频真实流上是否不慢于 GRETA / Cogra 复现（OPP）的 1.1 倍，同时高频上不损失（后者在 E1 的 K3 判）。

**代价规则（M 的定稿切换规则）**：每组两种模式（索引 = 窗口槽聚合树；扫描 = OPP 的结构，代码共用），初始为扫描。每组维护两个按事件平均、按窗格做 EWMA（α = 1/2，初值 0）的量：
- s̄：**扫描代价** = 若按 OPP 处理这个事件要做的窗口累加次数（= Σ 合格前驱 p 的 |共同窗口|）。扫描模式下就是扫描实际做的次数；索引模式下由下降给出：每个子树槽除 cnt、sum 外多存一个「本窗口的活事件数」nev，下降累出的 Σ_j acc_nev_j 正好等于这个数。
- ī：**索引代价模型** = k · 2 · ⌈log₂(n_live + 2)⌉（下降与插入各碰约 log n 个结点、每个结点 k 个槽；n_live = 该组活事件数）。两种模式都用模型，不用实测。
每个窗格结束（该组下一个事件进到新窗格、过期之后）用刚结束的窗格里 n_p 个事件的平均更新 s̄、ī（n_p = 0 不更新），然后：扫描模式且 s̄ > 2c · ī ⇒ 切到索引；索引模式且 s̄ < c · ī ⇒ 切回扫描（滞回 2）。切换的做法同 M1（活事件重建另一种结构）。**c 只用开发数据定**：c ∈ {0.5, 1, 1.5, 2, 3, 4, 6}。

**臂**：OPP（M1 的复现，不改）；M（窗口槽聚合树 + 上面的规则）；对照 A5（同一棵树 + M1 的规模阈值 τ_low = 16）与 A4（始终索引），从 E1 读。

**开发段（定 c）**：行 = WPI 开发 5 只（s = 10 s）× W ∈ {1, 2, 5} min、PAMAP2 subject101–104（s = 30 s）× W ∈ {1, 2} min、Intel Lab 54 个 mote 全部（温度 <，s = 1 min）× W ∈ {5, 10, 30} min，各 × AGG ∈ {COUNT, SUM}；Intel Lab 以用户批准为准、未批则不含、记入偏离。每行对 c 的 7 档各跑一次（1 预热 + 5 遍取中位，单进程），score(c) = 各行 T_M(c) ÷ min_c′ T_M(c′) 的几何平均；取 score 最小的 c，相差不到 1% 时取大的（偏向扫描）。定下后写进本 README 第 3 节与 `run_e4.sh`，**留出不再动**。

**留出段（判 K2'）**：Porto 出租车 2013-07（中频，速度 <，s = 1 min）与 METR-LA（低频，车速 >，s = 5 min），各 W ∈ {5, 10, 30} min × AGG ∈ {COUNT, SUM} = 6 行；时间从 E1 的 `handoff/e1_times.tsv`（E1 的计时口径：3 进程中位、短行加长）读 OPP 与 M；r = T_OPP ÷ T_M。两份都以用户批准下载为准。
**K2'**：Porto 6 行与 METR-LA 6 行**各自** r 的中位 ≥ 1 / 1.1。
**二值**：两份都成立 ⇒ **C5 成立**（「中低频留出流上不慢于对手 1.1 倍」进正文，切换规则作为自己设计的环节写进方法节，消融 A4 / A5）；否则 **C5 不成立**，正文把它写成方法的代价（低频流上退回扫描仍慢若干，数照报），切换规则仍照实报贡献。只有一份数据可用时，只判那一份、另一份记「未判」。

**不在本实验判的**：Nasdaq、公交两份在新规则下的 12 行照报（从 E1 读），表里注明「规则在看过 M1 的公交结果后重设计，这两份不是规则的留出」；M1 的判读与数一字不改。

**正确性闸**（不是判据；不过先查代码）：E1 的 (a)(b)，加 (c) 合成小流上索引模式算出的 Σ_j acc_nev_j 逐事件等于扫描模式的累加计数（c 取极小与极大各一档，保证两种模式都被走到）。

**描述性**（照报，不进判据）：开发段每行 7 档 c 的时间曲线与 score(c)；留出每行的切换次数、各模式处理的事件占比、s̄ ÷ ī 的中位；A5、A4 在留出上的 r 作对照；每组每窗事件数中位；Intel Lab（开发）、Porto、METR-LA 的事件数与组数。
<!-- 判据结束 -->

用法：python3 -I exp/e4-lowfreq/compare_e4.py [dev|hold]  → 写 report_e4.txt
输入：dev：handoff/e4_dev.tsv；hold：../e1-main/handoff/e1_times.tsv
实验段在判据文字之后补判读主体：dev：score(c) 与 c 的取值；hold：K2' 判读与描述性。判据文字之后不动。
"""
import math, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "e1-main"))
import compare_e1 as e1  # noqa: E402  （行时间、噪声带、每组每窗事件数的口径与 E1 同一份代码）

DEV = os.path.join(HERE, "handoff", "e4_dev.tsv")
HOLD = os.path.join(HERE, "..", "e1-main", "handoff", "e1_times.tsv")
CS = [0.5, 1, 1.5, 2, 3, 4, 6]


def criteria_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 判据开始 -->"):s.index("<!-- 判据结束 -->")]
    return cut(me) == cut(rd)


def dev():
    """开发段：每行 7 档 c 各一次（单进程，5 遍中位）；score(c) = 各行 T_M(c) ÷ min_c′ T_M(c′) 的几何平均；取最小，差不到 1% 取大的 c。"""
    rows = e1.read_tsv(DEV)
    T, inf = {}, {}
    for r in rows:
        k = (r["data"], r["agg"], int(r["W"]), float(r["c"]))
        T.setdefault(k, []).append(float(r["seconds"]))
        if r["work_adds"] != "-":
            inf[k] = (int(r["switches"]), int(r["idx_events"]) / max(1, int(r["events"])), float(r["ratio_med"]))
    T = {k: statistics.median(v) for k, v in T.items()}
    keys = sorted({k[:3] for k in T}, key=lambda k: (e1.ORDER.index(k[0]) if k[0] in e1.ORDER else 99, k[2], k[1]))
    L = ["## 开发段（定 c；README 第 1 节）：%d 行 × c 的 %d 档，每格 5 遍中位（秒）" % (len(keys), len(CS)),
         "数据\tAGG\tW 分\tn\t" + "\t".join("c=%g" % c for c in CS) + "\t最快的 c"]
    ns = {}
    score = {c: 0.0 for c in CS}
    for k in keys:
        if k[0] not in ns:
            ns[k[0]] = e1.nmed(k[0], "dev", [kk[2] for kk in keys if kk[0] == k[0]])
        ts = [T[k + (c,)] for c in CS]
        best = min(ts)
        for c, t in zip(CS, ts):
            score[c] += math.log(t / best)
        L.append("%s\t%s\t%d\t%s\t%s\t%g" % (k[0], k[1], k[2] // 60, ns[k[0]].get(k[2]), "\t".join("%.4f" % t for t in ts), CS[ts.index(best)]))
    score = {c: math.exp(v / len(keys)) for c, v in score.items()}
    m = min(score.values())
    pick = max(c for c in CS if score[c] <= m * 1.01)
    L.append("score(c)：" + "、".join("c=%g %.4f" % (c, score[c]) for c in CS))
    L.append("取值：score 最小 %.4f；与最小相差不到 1%% 的 c：%s ⇒ 取大的 c = %g" % (m, "、".join("%g" % c for c in CS if score[c] <= m * 1.01), pick))
    L.append("")
    L.append("各行在每档 c 下的切换次数 / 索引模式事件占比 / s̄÷ī 中位（--work 计数，描述性）")
    L.append("数据\tAGG\tW 分\t" + "\t".join("c=%g" % c for c in CS))
    for k in keys:
        L.append("%s\t%s\t%d\t%s" % (k[0], k[1], k[2] // 60, "\t".join("%d/%.2f" % inf[k + (c,)][:2] if k + (c,) in inf else "-" for c in CS)))
    L.append("s̄÷ī 中位（与 c 无关，两种模式算出的扫描代价相同，闸 (c)）：" + "、".join(
        "%s %s W=%d %.3g" % (k[0], k[1], k[2] // 60, inf[k + (CS[0],)][2]) for k in keys if k + (CS[0],) in inf))
    return L, pick


def hold():
    """留出段：Porto、METR-LA 各 6 行，读 E1 的 e1_times.tsv；r = T_OPP ÷ T_M；K2'：每份各自 r 中位 ≥ 1 / 1.1。"""
    tm = e1.Times(HOLD)
    L = ["## 留出段（判 K2'；时间读 ../e1-main/handoff/e1_times.tsv，E1 的计时口径）"]
    res = {}
    for d in ("porto", "metrla"):
        ks = [k for k in tm.rowkeys() if k[0] == d and k[1] == "hold" and ("OPP",) + k in tm.T and ("M",) + k in tm.T]
        if not ks:
            L.append("K2' %s：没有数据 ⇒ 未判" % d)
            res[d] = None
            continue
        r = [tm.T[("OPP",) + k] / tm.T[("M",) + k] for k in ks]
        okk = statistics.median(r) >= 1 / 1.1
        res[d] = okk
        L.append("K2' %s：%d 行 r 中位 %.3f（线 %.3f；M ÷ OPP = %.3f）、最小 %.3f、最大 %.3f ⇒ %s" % (
            d, len(ks), statistics.median(r), 1 / 1.1, 1 / statistics.median(r), min(r), max(r), "成立" if okk else "不成立"))
    judged = [v for v in res.values() if v is not None]
    if judged and all(judged):
        L.append("二值：%s ⇒ C5 成立" % ("两份都成立" if len(judged) == 2 else "只有一份可判、它成立（另一份未判）"))
    elif judged:
        L.append("二值：有一份不成立 ⇒ C5 不成立（正文写成方法的代价，数照报）")
    L += ["", "## 留出与照报各行（描述性）",
          "Nasdaq、公交：规则在看过 M1 的公交结果后重设计，这两份不是规则的留出",
          "数据\tAGG\tW 分\tn\tT_OPP\tT_M\tr\tr_A5=OPP/A5\tr_A4=OPP/A4\t带 OPP\t带 M\tM 切换\tM 索引事件占比\ts̄÷ī 中位"]
    ns = {}
    for k in tm.rowkeys():
        if k[0] not in ("porto", "metrla", "nasdaq", "bus") or ("M",) + k not in tm.T:
            continue
        if k[0] not in ns:
            ns[k[0]] = e1.nmed(k[0], "hold", [kk[3] for kk in tm.rowkeys() if kk[0] == k[0]])
        o, m = tm.T[("OPP",) + k], tm.T[("M",) + k]
        mi = tm.info[("M",) + k]
        L.append("%s\t%s\t%d\t%s\t%.4f\t%.4f\t%.3f\t%s\t%s\t%.3f\t%.3f\t%d\t%s\t%s" % (
            k[0], k[2], k[3] // 60, ns[k[0]].get(k[3]), o, m, o / m,
            "%.3f" % (o / tm.T[("A5",) + k]) if ("A5",) + k in tm.T else "-", "%.3f" % (o / tm.T[("A4",) + k]) if ("A4",) + k in tm.T else "-",
            tm.band(("OPP",) + k), tm.band(("M",) + k), mi["switches"],
            "%.3f" % (mi["idx"] / max(1, mi["events"])) if "idx" in mi else "-", "%.3g" % mi["ratio"] if "ratio" in mi else "-"))
    for d in ("porto", "metrla", "nasdaq", "bus"):
        ks = [k for k in tm.rowkeys() if k[0] == d and ("OPP",) + k in tm.T and ("M",) + k in tm.T]
        if ks:
            L.append("%s：Σ T_OPP ÷ Σ T_M = %.3f；A5 %.3f；A4 %.3f（按样本直接合计）" % (
                d, sum(tm.T[("OPP",) + k] for k in ks) / sum(tm.T[("M",) + k] for k in ks),
                sum(tm.T[("OPP",) + k] for k in ks) / sum(tm.T[("A5",) + k] for k in ks),
                sum(tm.T[("OPP",) + k] for k in ks) / sum(tm.T[("A4",) + k] for k in ks)))
    return L


def main():
    ok = criteria_same()
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    L = ["判据两处同文：%s" % ok]
    if not ok:
        print(L[0]); sys.exit(1)
    rp = os.path.join(HERE, "report_e4.txt")
    old = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
    keep = {}
    for part in ("## 开发段", "## 留出段"):  # 报表两段各自重写，另一段保留
        if part in old:
            seg = old[old.index(part):]
            other = "## 留出段" if part == "## 开发段" else None
            keep[part] = seg[:seg.index(other)] if other and other in seg else seg
    if not os.path.exists(DEV if mode == "dev" else HOLD):
        print(L[0]); print("没有 %s（先跑 run_e4.sh dev / run_e1.sh all）" % (DEV if mode == "dev" else HOLD)); sys.exit(1)
    if mode == "dev":
        Ld, pick = dev()
        keep["## 开发段"] = "\n".join(Ld) + "\n\n"
    else:
        keep["## 留出段"] = "\n".join(hold()) + "\n"
    txt = L[0] + "\n\n" + keep.get("## 开发段", "") + keep.get("## 留出段", "")
    open(rp, "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
