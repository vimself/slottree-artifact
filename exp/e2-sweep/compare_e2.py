r"""E2 · 判读脚本。判据原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 判据开始 -->
**问题**：同 E1 的查询类；AGG 只用 COUNT(*)。要回答：r = T_OPP ÷ T_M 随每组每窗事件数 n 与谓词选择度 σ 怎么变，余量从哪里开始有。

**臂**：OPP、M（E1 第 1 节的定稿引擎，切换常数 c 用 E4 定下的值）。计时口径同 E1（3 进程中位、短行加长）。

**W 扫**：WPI 留出 5 只（价格 >，s = 10 s）、PAMAP2 subject105–109（心率 <，s = 30 s），加 Binance aggTrades（价格 >，s = 10 s）与 Porto 2013-07（速度 <，s = 1 min）若用户批了：W ∈ {1, 2, 5, 10, 30, 60} 分钟，每份数据 6 行。

**选择度扫**：W = 10 分钟，同样的数据；谓词改成 a_p · X ⋈ a_e（整数算：a_p · X_num ⋈ a_e · X_den，X_den = 1000），X 从 {0.900, 0.905, …, 1.100} 里按规则取：对每个目标 σ ∈ {0.1, 0.3, 0.5, 0.7, 0.9}，取使「同组、同一窗口内先到的 p 与后到的 e 组成的事件对里满足谓词的比例」最接近 σ 的 X；该比例由 `prep_e2.py` 在每份数据上算（每组每窗抽 ≤ 10⁴ 对，固定种子），X 与实际比例照报。两个臂同一谓词：索引的前缀阈值换成 a_e · X_den ÷ X_num 的对应整数边界，扫描的范围查找同样换。每份数据 5 行。

**K4**（C8；只看 WPI 与 PAMAP2 两份高频留出）：每份数据上 (i) r 随 W 的 6 个点单调不减，容 10% 噪声（每相邻两点 r_{i+1} ≥ 0.9 · r_i），且 r(60 min) ≥ 2 · r(1 min)；(ii) r(σ = 0.9) ≥ r(σ = 0.1)。
**二值**：两份数据 (i)(ii) 都成立 ⇒ **C8 进正文**（「余量随每组每窗事件数与选择度增长」）；否则不停，C8 改写成实测形状的描述，原因写进第 0 节。

**描述性**（照报，不进判据）：每行的每组每窗事件数中位 n（含 W 扫里 n 的实际值）；全部行 r 对 n 的散点（跨数据集，含 E1 的行）；每份数据 r 首次 ≥ 1 与 ≥ 1.5 的 n（相邻两点线性插值；没过就记「未过」）；M 每行的切换次数与索引模式事件占比；每行的工作量计数之比（OPP 窗口累加 ÷ M 槽读写）对照时间之比。
<!-- 判据结束 -->

用法：python3 -I exp/e2-sweep/compare_e2.py  → 写 report_e2.txt
输入：handoff/e2_times.tsv、handoff/e2_sel.tsv（由 run_e2.sh、prep_e2.py 产出）
实验段在判据文字之后补判读主体：K4 判读、r 对 n 的散点、交叉点。判据文字之后不动。
"""
import os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "e1-main"))
import compare_e1 as e1  # noqa: E402  （行时间、噪声带、每组每窗事件数的口径与 E1 同一份代码）

TIMES = os.path.join(HERE, "handoff", "e2_times.tsv")
SEL = os.path.join(HERE, "handoff", "e2_sel.tsv")
E1T = os.path.join(HERE, "..", "e1-main", "handoff", "e1_times.tsv")
DATA = ["wpi", "pamap2", "porto", "binance"]
WS = [60, 120, 300, 600, 1800, 3600]


def criteria_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 判据开始 -->"):s.index("<!-- 判据结束 -->")]
    return cut(me) == cut(rd)


def cross(ns, rs, thr):
    """r 首次 ≥ thr 的 n（相邻两点线性插值）；第一个点就过记「≤ n₀」，没过记「未过」。"""
    for i, (n, r) in enumerate(zip(ns, rs)):
        if r >= thr:
            if i == 0:
                return "≤ %g" % n
            n0, r0 = ns[i - 1], rs[i - 1]
            return "%.0f" % (n0 + (thr - r0) * (n - n0) / (r - r0))
    return "未过"


def main():
    ok = criteria_same()
    L = ["判据两处同文：%s" % ok]
    if not ok:
        print(L[0]); sys.exit(1)
    if not os.path.exists(TIMES):
        print(L[0]); print("没有 handoff/e2_times.tsv（先 bash run_e2.sh w / sel）"); sys.exit(1)
    tm = e1.Times(TIMES, key_extra=("xnum",))
    sel = e1.read_tsv(SEL) if os.path.exists(SEL) else []
    R = lambda d, W, x="1000": tm.T[("OPP", d, "hold", "COUNT", W, x)] / tm.T[("M", d, "hold", "COUNT", W, x)] \
        if ("OPP", d, "hold", "COUNT", W, x) in tm.T and ("M", d, "hold", "COUNT", W, x) in tm.T else None
    ns = {d: e1.nmed(d, "hold", WS) for d in DATA}
    # K4
    L.append("## 判读 K4（README 第 1 节；只看 WPI 与 PAMAP2）")
    allok = True
    for d in ("wpi", "pamap2"):
        rs = [R(d, W) for W in WS]
        if None in rs:
            L.append("%s：W 扫不全（缺 %s）⇒ 不判" % (d, [W // 60 for W, r in zip(WS, rs) if r is None])); allok = False; continue
        adj = all(rs[i + 1] >= 0.9 * rs[i] for i in range(len(rs) - 1))
        dbl = rs[-1] >= 2 * rs[0]
        sx = {float(r["sigma"]): r["X_num"] for r in sel if r["data"] == d}
        r01, r09 = (R(d, 600, sx[0.1]) if 0.1 in sx else None), (R(d, 600, sx[0.9]) if 0.9 in sx else None)
        ii = r01 is not None and r09 is not None and r09 >= r01
        L.append("%s (i)：r 随 W = %s 分：%s；相邻两点都 ≥ 0.9 倍：%s；r(60) ÷ r(1) = %.2f（线 2）⇒ %s" % (
            d, "/".join(str(W // 60) for W in WS), " / ".join("%.3f" % r for r in rs), "是" if adj else "否", rs[-1] / rs[0], "成立" if adj and dbl else "不成立"))
        L.append("%s (ii)：r(σ = 0.9, X = %s) = %s，r(σ = 0.1, X = %s) = %s ⇒ %s" % (
            d, sx.get(0.9), "%.3f" % r09 if r09 else "-", sx.get(0.1), "%.3f" % r01 if r01 else "-", "成立" if ii else "不成立"))
        allok = allok and adj and dbl and ii
    L.append("二值：%s" % ("两份 (i)(ii) 都成立 ⇒ C8 进正文" if allok else "不全成立 ⇒ 不停，C8 改写成实测形状的描述（原因写进 README 第 0 节）"))
    # W 扫表
    L += ["", "## W 扫（COUNT；行时间 = 3 个进程内中位的中位，秒；n = 每组每窗事件数中位）",
          "数据\tW 分\tn\tD\tT_OPP\tT_M\tr\t带 OPP\t带 M\tOPP累加÷M槽\tM 切换\tM 索引事件占比"]
    for d in DATA:
        for W in WS:
            ko, km = ("OPP", d, "hold", "COUNT", W, "1000"), ("M", d, "hold", "COUNT", W, "1000")
            if ko not in tm.T or km not in tm.T:
                continue
            o, m = tm.info[ko], tm.info[km]
            L.append("%s\t%d\t%s\t%s\t%.4f\t%.4f\t%.3f\t%s\t%s\t%s\t%d\t%s" % (
                d, W // 60, ns[d].get(W), m["copies"], tm.T[ko], tm.T[km], tm.T[ko] / tm.T[km], e1.fb(tm.band(ko)), e1.fb(tm.band(km)),
                "%.2f" % (o["work_adds"] / max(1, m["work_adds"])) if "work_adds" in o and "work_adds" in m else "-",
                m["switches"], "%.3f" % (m["idx"] / max(1, m["events"])) if "idx" in m else "-"))
        pts = [(ns[d].get(W), R(d, W)) for W in WS if R(d, W) is not None and ns[d].get(W) is not None]
        if pts:
            L.append("%s：r 首次 ≥ 1 的 n = %s；首次 ≥ 1.5 的 n = %s" % (d, cross([p[0] for p in pts], [p[1] for p in pts], 1.0),
                                                                cross([p[0] for p in pts], [p[1] for p in pts], 1.5)))
    # 选择度扫表
    L += ["", "## 选择度扫（W = 10 分、COUNT；X 与实际比例来自 handoff/e2_sel.tsv；X = 1.000 的点即 W 扫的 W = 10 分）",
          "数据\t目标 σ\tX\t实际比例\tT_OPP\tT_M\tr\tM 切换\tM 索引事件占比"]
    for r in sel:
        d, x = r["data"], r["X_num"]
        ko, km = ("OPP", d, "hold", "COUNT", 600, x), ("M", d, "hold", "COUNT", 600, x)
        if ko in tm.T and km in tm.T:
            m = tm.info[km]
            L.append("%s\t%s\t%s\t%s\t%.4f\t%.4f\t%.3f\t%d\t%s" % (d, r["sigma"], r["X"], r["frac"], tm.T[ko], tm.T[km], tm.T[ko] / tm.T[km],
                                                              m["switches"], "%.3f" % (m["idx"] / max(1, m["events"])) if "idx" in m else "-"))
        else:
            L.append("%s\t%s\t%s\t%s\t（未跑）" % (d, r["sigma"], r["X"], r["frac"]))
    # r 对 n 的散点（含 E1）
    L += ["", "## r 对 n 的散点（跨数据集；E2 的 W 扫各行 + E1 的全部留出行，按 n 排序）", "来源\t数据\tAGG\tW 分\tn\tr"]
    pts = []
    for d in DATA:
        for W in WS:
            if R(d, W) is not None:
                pts.append(("E2", d, "COUNT", W, ns[d].get(W), R(d, W)))
    if os.path.exists(E1T):
        t1 = e1.Times(E1T)
        nn = {}
        for k in t1.rowkeys():
            if k[1] != "hold" or ("OPP",) + k not in t1.T or ("M",) + k not in t1.T:
                continue
            if k[0] not in nn:
                nn[k[0]] = e1.nmed(k[0], "hold", [3600, 1800, 600, 300])
            pts.append(("E1", k[0], k[2], k[3], nn[k[0]].get(k[3]), t1.T[("OPP",) + k] / t1.T[("M",) + k]))
    for p in sorted(pts, key=lambda p: (p[4] is None, p[4] or 0)):
        L.append("%s\t%s\t%s\t%d\t%s\t%.3f" % (p[0], p[1], p[2], p[3] // 60, p[4], p[5]))
    single = sorted("%s %s W=%d X=%s" % (k[0], k[1], k[4] // 60, k[5]) for k in tm.procmed if len(tm.procmed[k]) < 2)
    L.append("")
    L.append("慢行单次计时（探测遍 ≥ 60 s，README 第 3 节偏离 1）的 (臂 × 行)：%s" % ("、".join(single) or "无"))
    txt = "\n".join(L) + "\n"
    open(os.path.join(HERE, "report_e2.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
