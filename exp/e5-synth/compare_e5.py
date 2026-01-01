r"""E5 · 报表脚本。协议原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 协议开始 -->
**目的**：E1 的真实数据里每组每窗事件数 n 最多到约 10⁴（Binance W = 30 分），审稿人会问 n 再大、k 再大、取值分布换了、组多了、流量突发时窗口槽聚合树怎样。本实验在程序化合成的流上量这几条，只报数。

**查询**：同 E1（`exp/e1-main/README.md` 第 1 节「问题」）：`E+`、skip-till-any-match、⋈ 为 >（严格）、AGG 只取 COUNT（SUM 的相对代价 E1 已报）；W = 600 s 固定，k = W ÷ s ∈ {1, 2, 6, 30}（s = 600 / 300 / 100 / 20 s）。

**流**（`gen_e5.py`，纯标准库，种子由流名定，同名同流）：每组泊松到达，λ = n ÷ W，n = 每组每窗的期望事件数；组数 G 个、事件均匀分给各组；时长 H = max(10, ⌈10⁶ ÷ (n·G)⌉) 个窗口（每条流至少约 10⁶ 个事件、至少 10 个窗口）。属性三种：**u** 均匀独立同分布；**rw** 随机游走（步长均匀 ±1000）；**ht** 重尾随机游走（步长 Pareto α = 1.5、符号等概率）。比较谓词只看大小次序，独立同分布的重尾值与均匀值的次序过程相同，所以「重尾」放在随机游走的步长上（价格跳变）。**突发**：每 10 W 一个周期，[5 W, 6 W) 速率 × 10（占时长 10%）；突发流的 n 指基础速率下的数，H 与同名无突发流相同。细节在 `gen_e5.py` 文件头。

**格**（`run_e5.sh` 的 `cells`，共 76 格）：
- S1 分布 × n × k：{u, rw, ht} × n ∈ {10², 10³, 10⁴, 10⁵, 10⁶} × k ∈ {1, 2, 6, 30}，G = 1、无突发（60 格）
- S2 组数：rw、k = 6、n ∈ {10³, 10⁴} × G ∈ {10, 100}（4 格；G = 1 的对照是 S1 的同名格）
- S3 突发：rw、k = 6、n ∈ {10, 10², 10³} × G ∈ {1, 10} × 突发 {无, 有}（12 格）

**臂**（E1 的同一个二进制 `exp/e1-main/out/trend`、同一编译选项、参数同 `run_e1.sh`）：**OPP**（GRETA / Cogra 复现）、**M**（窗口槽聚合树 + 代价规则，c = 2，`C_FIXED`）、**A4**（始终索引）、**A5**（规模阈值 τ_low = 16）。

**计时**（比 E1 粗：单进程、固定遍数、不加长、不交错）：每格每臂先一个探测进程（预热 1 遍、计时 0 遍）；探测遍 < 60 s ⇒ 新起一个进程，预热 1 遍 + 计时 3 遍，取 3 遍的中位；≥ 60 s ⇒ 新起一个进程不预热、计时 1 遍（同 E1 偏离 1）。**OPP 的跳过规则**：预计单遍 = 同分布、同 k、同组数、同突发、n 小一档（÷ 10）那格的 OPP 时间 × 10 × 两条流的事件数之比；预计 > 600 s 的格不跑、表里记 skip 与预计值（小一档已跳过的同样跳过；n = 10⁶ 的 OPP 是二次方，预计远超）；预计 ≥ 60 s 的格不探测、直接计时 1 遍；没有小一档的格照常探测。S3 的 M 与 A5 另加 `--work` 一遍（不计时）数出索引模式处理的事件数。格按 `cells` 的顺序、格内按 OPP → M → A4 → A5 顺序跑；跑时接电源、不开别的重负载。

**产出**：`handoff/e5_times.tsv`（每个计时遍一行：组别、分布、n、G、突发、k、臂、事件数、方式 normal / single / skip、OPP 的预计、遍号、秒、峰值内存、切换次数、压缩次数、索引事件数、校验和）；`compare_e5.py` → `report_e5.txt`：
1. S1：每个分布、每个 k 一张表，行 = n：各臂时间、r = T_OPP ÷ T_M、T_M ÷ T_A4、T_M ÷ T_A5、M 每事件纳秒、M ÷ OPP 峰值内存；跳过的格写预计值
2. S2：G = 1 / 10 / 100 的同一张表（M 每事件纳秒、r）
3. S3：突发有 / 无并排：M 与 A5 的切换次数、索引模式事件占比、T_M ÷ T_A5、r
4. 每格四个臂的校验和是否一致；生成器记下的每条流的事件数、H、每组每窗（滚动窗口）事件中位

不设判据，报表只列数。
<!-- 协议结束 -->

用法：python3 -I exp/e5-synth/compare_e5.py [表 = handoff/e5_times.tsv] [报表 = report_e5.txt]
描述性：只列数，不判。
"""
import os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ["OPP", "M", "A4", "A5"]
DISTS = ["u", "rw", "ht"]
DNAME = {"u": "均匀", "rw": "随机游走", "ht": "重尾随机游走"}


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


def fmt_t(x):
    if x is None:
        return "-"
    return "%.3f" % x if x < 100 else "%.1f" % x


def ratio(a, b, nd=2):
    if a is None or b is None or b == 0:
        return "-"
    return ("%%.%df" % nd) % (a / b)


def main(tab, rep):
    rows = read(tab)
    cell = defaultdict(lambda: defaultdict(list))   # (set, dist, n, G, burst, k) → arm → [秒]
    info = {}
    for r in rows:
        key = (r["set"], r["dist"], int(r["n"]), int(r["G"]), r["burst"], int(r["k"]))
        a = r["arm"]
        inf = info.setdefault((key, a), {"events": int(r["events"]), "mode": r["mode"], "pred": r["pred_s"]})
        if r["mode"] == "skip":
            cell[key][a] = None
            continue
        cell[key][a].append(float(r["seconds"]))
        inf.update(maxrss=int(r["maxrss_kb"]), switches=int(r["switches"]), compactions=int(r["compactions"]),
                   idx=None if r["idx_events"] == "-" else int(r["idx_events"]), checksum=r["checksum"])

    def T(key, a):
        v = cell[key].get(a)
        return statistics.median(v) if v else None

    out = []
    p = out.append
    p("# E5 · 合成扩展性报表（compare_e5.py，读 %s）" % os.path.relpath(tab, HERE))
    p("协议同文自检：%s" % ("一致" if protocol_same() else "不一致！"))
    p("描述性：只列数，不判。时间 = 计时遍的中位（single = 单次计时；skip = 预计单遍 > 600 s 未跑，括号里是预计秒数）。")
    p("")

    def row_s1(key):
        t = {a: T(key, a) for a in ARMS}
        io = info.get((key, "OPP"), {})
        im = info.get((key, "M"), {})
        opp = fmt_t(t["OPP"]) if t["OPP"] is not None else ("skip(%s)" % io.get("pred", "?") if io else "-")
        if io.get("mode") == "single":
            opp += "*"
        ev = im.get("events") or io.get("events") or 0
        nsev = "%.0f" % (t["M"] / ev * 1e9) if t["M"] is not None and ev else "-"
        mem = ratio(im.get("maxrss"), info.get((key, "OPP"), {}).get("maxrss"))
        return [opp, fmt_t(t["M"]), fmt_t(t["A4"]), fmt_t(t["A5"]), ratio(t["OPP"], t["M"]), ratio(t["M"], t["A4"], 3),
                ratio(t["M"], t["A5"], 3), nsev, mem, str(im.get("switches", "-")), str(ev)]

    hdr = "n\tT_OPP\tT_M\tT_A4\tT_A5\tr=OPP/M\tM/A4\tM/A5\tM_ns/事件\t内存M/OPP\tM切换\t事件数"
    p("## 1. S1：分布 × n × k（G = 1、无突发；* = OPP 单次计时）")
    for d in DISTS:
        for k in (1, 2, 6, 30):
            p("")
            p("### %s（%s），k = %d" % (d, DNAME[d], k))
            p(hdr)
            for n in (100, 1000, 10000, 100000, 1000000):
                key = ("S1", d, n, 1, "0", k)
                if key in cell:
                    p("\t".join([str(n)] + row_s1(key)))
    p("")
    p("## 2. S2：组数（rw、k = 6；G = 1 取 S1 同名格）")
    p("G\t" + hdr)
    for n in (1000, 10000):
        for g in (1, 10, 100):
            key = ("S1" if g == 1 else "S2", "rw", n, g, "0", 6)
            if key in cell:
                p("\t".join([str(g)] + [str(n)] + row_s1(key)))
    p("")
    p("## 3. S3：突发（rw、k = 6；突发 = 每 10 W 里 1 W 速率 × 10）")
    p("n\tG\t突发\tT_OPP\tT_M\tT_A5\tr=OPP/M\tM/A5\tM切换\tA5切换\tM索引占比\tA5索引占比\t事件数")
    for g in (1, 10):
        for n in (10, 100, 1000):
            for b in ("0", "1"):
                key = ("S3", "rw", n, g, b, 6)
                if key not in cell:
                    continue
                im, i5 = info.get((key, "M"), {}), info.get((key, "A5"), {})
                ev = im.get("events", 0)
                fr = lambda inf: "%.3f" % (inf["idx"] / ev) if inf.get("idx") is not None and ev else "-"
                t = {a: T(key, a) for a in ARMS}
                p("\t".join(map(str, [n, g, "有" if b == "1" else "无", fmt_t(t["OPP"]), fmt_t(t["M"]), fmt_t(t["A5"]),
                                      ratio(t["OPP"], t["M"]), ratio(t["M"], t["A5"], 3), im.get("switches", "-"), i5.get("switches", "-"),
                                      fr(im), fr(i5), ev])))
    p("")
    p("## 4. 校验和与流")
    bad = []
    for key in cell:
        cs = {info[(key, a)]["checksum"] for a in ARMS if (key, a) in info and "checksum" in info[(key, a)]}
        if len(cs) > 1:
            bad.append(key)
    p("每格各臂（跑了的）校验和一致：%d 格中不一致 %d 格%s" % (len(cell), len(bad), ("：" + str(bad)) if bad else ""))
    skipped = sorted(((k, info[(k, "OPP")]["pred"]) for k in cell if cell[k].get("OPP", 0) is None), key=str)
    p("OPP 跳过的格（预计单遍秒数）：%s" % ("、".join("%s n=%d G=%d k=%d (%s)" % (k[1], k[2], k[3], k[5], pr) for k, pr in skipped) or "无"))
    singles = sorted(k for k in info if info[k]["mode"] == "single")
    p("单次计时的 (格, 臂)：%s" % ("、".join("%s %s n=%d G=%d b=%s k=%d" % (a, k[1], k[2], k[3], k[4], k[5]) for k, a in singles) or "无"))
    gen = os.path.join(HERE, "logs", "gen.txt")
    if os.path.exists(gen):
        p("生成器记录（logs/gen.txt）：")
        for l in open(gen, encoding="utf-8"):
            p("  " + l.rstrip("\n"))
    open(rep, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("写了 %s（%d 行）" % (rep, len(out)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "handoff", "e5_times.tsv"),
         sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "report_e5.txt"))
