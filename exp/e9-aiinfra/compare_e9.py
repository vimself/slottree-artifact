r"""E9 · 判读脚本。判据原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 判据开始 -->
**背景**：论文在七条真实流上得到的经验法则是「每组每窗事件数中位 n ≥ 106 的设置，r = T_GRETA-C++ ÷ T_SlotTree ≥ 1.79」（`exp/e8-inpane/report_e8.txt`，Fig. 4 图注）。这两条流来自开发与此前留出都没碰过的领域，本实验是这条法则的一次样本外检验，线取 MVP 的线（1.5 与 2），不取事后看到的 1.79。

**设置**：每条流 6 个：W ∈ {5, 10, 30} 分 × AGG ∈ {COUNT, SUM}，滑动 s = 30 s（k = 10 / 20 / 60），⋈ 为 <（数值上升），skip-till-any-match。n = 该流在该 W 下每（组, 窗口）事件数的中位，算法同 E1。

**K5（每条流各判一次）**：该流 n ≥ 106 的设置里，**每一个** r ≥ 1.5，**且至少一个** r ≥ 2。一条流没有 n ≥ 106 的设置 ⇒ 该流记「未判（稀疏）」，数照报。按第 2 节的规则没跑的格（GRETA-C++ 超时、内存上限）不计入，但至少要有 2 个 n ≥ 106 的格跑完才判。

**二值**：
- 两条流的 K5 都成立 ⇒ **C26 进正文**：「在开发从未用过的 AI 基础设施遥测上，n 超过约一百的设置同样成立」，引言用这两条流的数开场。
- 只有一条成立 ⇒ 引言用成立的那条开场；另一条的数照报，写明没过线。
- 都不成立 ⇒ 引言只保留集群监控的引文动机，不用这两条流的数开场；两条流的结果作为方法的适用边界照报。
- 无论哪种，引擎与常数不许为这两条流调；看过结果之后改的任何东西记第 3 节偏离。
<!-- 判据结束 -->

用法：python3 -I exp/e9-aiinfra/compare_e9.py                 → report_e9.txt、handoff/e9_streams.tsv
      python3 -I exp/e9-aiinfra/compare_e9.py nvals <gpu|llm> [tsv]   → 每个 W（秒）的 n（run_e9.sh 的不跑规则用）
      python3 -I exp/e9-aiinfra/compare_e9.py --times <tsv> --rules <tsv> --out <txt> --streams <tsv>   自测用（不写 handoff）
输入：handoff/e9_times.tsv（run_e9.sh 产出，列同 exp/e1-main/handoff/e1_times.tsv）、handoff/e9_rules.tsv（两条不跑规则逐格的判定）；
n 与流的形状从 data/<流>_hold.tsv 算（被忽略；不在时读 handoff/e9_streams.tsv 里上次算的值）。行时间、噪声带、工作量表都调用
exp/e1-main/compare_e1.py（Times、work），n 调用 exp/e1-main/prep_e1.py 的 stats（同 E1 的算法），不复制。
判据文字之后不动。
"""
import os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.normpath(os.path.join(HERE, "..", "e1-main"))
if E1 not in sys.path:
    sys.path.insert(0, E1)
import compare_e1 as c1  # noqa: E402
import prep_e1  # noqa: E402

TIMES = os.path.join(HERE, "handoff", "e9_times.tsv")
RULES = os.path.join(HERE, "handoff", "e9_rules.tsv")
STREAMS = os.path.join(HERE, "handoff", "e9_streams.tsv")
REPORT = os.path.join(HERE, "report_e9.txt")
S = 30                                   # 滑动 s（秒）
WS = [300, 600, 1800]
AGGS = ["COUNT", "SUM"]
DATA = [("gpu", "GPU 功耗（MIT Supercloud，训练集群）", "power_draw <"),
        ("llm", "LLM 推理首 token 延迟（Chutes，服务集群）", "ttft <")]
N_LINE, R_ALL, R_ONE = 106, 1.5, 2.0    # K5 的线（判据原文）
RULE_OF_THUMB = 1.79                    # 论文七条流上的经验法则（背景，只作描述性对照，不进判定）
SCOLS = ["data", "name", "predicate", "s", "events", "groups", "span_h", "n_300", "n_600", "n_1800",
         "thr_M_Mev_s", "thr_OPP_Mev_s", "mem_M_MB", "mem_OPP_MB"]


def criteria_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 判据开始 -->"):s.index("<!-- 判据结束 -->")]
    return cut(me) == cut(rd)


def shape(d, cached, f=None):
    """(事件数, 组数, 时长小时, {W: n})。data/<d>_hold.tsv 在就现算（n = prep_e1.stats，同 E1），不在就读上次写的 e9_streams.tsv。"""
    f = f or os.path.join(HERE, "data", "%s_hold.tsv" % d)
    if os.path.exists(f):
        ev, gr, ns = prep_e1.stats(f, S, Ws=WS)
        lo = hi = None
        for line in open(f, encoding="utf-8"):
            t = int(line.split("\t", 2)[1])
            lo = t if lo is None or t < lo else lo
            hi = t if hi is None or t > hi else hi
        return ev, gr, (hi - lo) / 3.6e9, {w: ns[w] for w in WS}
    r = cached.get(d)
    if r is None:
        return None
    return int(r["events"]), int(r["groups"]), float(r["span_h"]), {w: float(r["n_%d" % w]) for w in WS}


def read_rules(path):
    if not os.path.exists(path):
        return {}
    out = {}
    for r in c1.read_tsv(path):
        out[(r["data"], r["agg"], int(r["W"]), r["rule"])] = r
    return out


def fnum(x, f="%.4f"):
    return "-" if x is None or x != x else f % x


def mb(tm, k):
    return max(tm.info[k]["maxrss"]) / 1024 if k in tm.info else None


def per_stream(tm, rules, d, sh):
    """d 这条流的 6 个设置 → [dict]（n、两臂时间、r、带、内存、计时方式、未跑原因、校验和）"""
    rows = []
    for W in WS:
        for agg in AGGS:
            k = (d, "hold", agg, W)
            o, m = ("OPP",) + k, ("M",) + k
            x = dict(W=W, agg=agg, n=sh[3][W] if sh else None, To=tm.T.get(o), Tm=tm.T.get(m),
                     bo=tm.band(o) if o in tm.T else None, bm=tm.band(m) if m in tm.T else None,
                     mo=mb(tm, o), mm=mb(tm, m), skip="", single=[])
            x["r"] = x["To"] / x["Tm"] if x["To"] and x["Tm"] else None
            x["memr"] = x["mm"] / x["mo"] if x["mm"] and x["mo"] else None
            for a, kk in (("OPP", o), ("M", m)):
                if kk in tm.procmed and len(tm.procmed[kk]) == 1:
                    x["single"].append(a)
            rm, rt = rules.get((d, agg, W, "mem")), rules.get((d, agg, W, "opp_time"))
            if rm and rm["decision"] == "不跑":
                x["skip"] = "两臂未跑：内存上限（M 外推 %.2f GiB > %.3g GiB）" % (int(rm["predicted"]) / 1024 ** 2, int(rm["limit"]) / 1024 ** 2)
            elif rt and rt["decision"] == "不跑":
                x["skip"] = "GRETA-C++ 未跑：外推单遍 %s s > %s s" % (rt["predicted"], rt["limit"])
            cks = set().union(*[tm.info[kk]["checksum"] for kk in (o, m) if kk in tm.info]) if (o in tm.info or m in tm.info) else set()
            x["ck"] = len(cks)
            rows.append(x)
    return rows


def k5(rows):
    """判据 K5：该流 n ≥ 106 的设置里每一个 r ≥ 1.5 且至少一个 r ≥ 2；没跑的格不计入；n ≥ 106 的格跑完的不足 2 个不判。"""
    elig = [x for x in rows if x["n"] is not None and x["n"] >= N_LINE]
    done = [x for x in elig if x["r"] is not None]
    if not elig:
        return "未判（稀疏）", elig, done
    if len(done) < 2:
        return "未判（n ≥ 106 的格跑完的只有 %d 个，判据要至少 2 个）" % len(done), elig, done
    ok = all(x["r"] >= R_ALL for x in done) and any(x["r"] >= R_ONE for x in done)
    return ("成立" if ok else "不成立"), elig, done


def main(times=TIMES, rules_path=RULES, out=REPORT, streams=STREAMS):
    ok = criteria_same()
    L = ["判据两处同文：%s" % ok]
    if not ok:
        print(L[0]); sys.exit(1)
    if not os.path.exists(times):
        print(L[0]); print("没有 %s（先 bash run_e9.sh all）" % times); sys.exit(1)
    tm = c1.Times(times)
    rules = read_rules(rules_path)
    cached = {r["data"]: r for r in c1.read_tsv(streams)} if os.path.exists(streams) else {}
    shapes = {d: shape(d, cached) for d, _, _ in DATA}
    verdict, allrows = {}, {}
    L.append("")
    L.append("## 判读（README 第 1 节 K5，每条流各判一次；r = T_GRETA-C++ ÷ T_SlotTree，线：n ≥ %d 的设置每个 r ≥ %.1f 且至少一个 r ≥ %.0f）" % (N_LINE, R_ALL, R_ONE))
    for d, name, _ in DATA:
        rows = per_stream(tm, rules, d, shapes[d])
        allrows[d] = rows
        v, elig, done = k5(rows)
        verdict[d] = v
        rs = [x["r"] for x in done]
        L.append("%s：n ≥ %d 的设置 %d 个、跑完 %d 个；r 最小 %s、中位 %s、最大 %s ⇒ K5 %s" % (
            name, N_LINE, len(elig), len(done), fnum(min(rs) if rs else None, "%.3f"), fnum(statistics.median(rs) if rs else None, "%.3f"),
            fnum(max(rs) if rs else None, "%.3f"), v))
    held = [d for d, _, _ in DATA if verdict[d] == "成立"]
    if len(held) == 2:
        L.append("二值：两条流的 K5 都成立 ⇒ C26 进正文：「在开发从未用过的 AI 基础设施遥测上，n 超过约一百的设置同样成立」，引言用这两条流的数开场")
    elif len(held) == 1:
        L.append("二值：只有 %s 成立 ⇒ 引言用成立的那条开场；另一条的数照报，写明没过线" % held[0])
    else:
        L.append("二值：都不成立 ⇒ 引言只保留集群监控的引文动机，不用这两条流的数开场；两条流的结果作为方法的适用边界照报")
    L.append("（K5 只认判据原文的线；论文七条流上的经验法则 r ≥ %.2f 是背景，下面只作描述性对照）" % RULE_OF_THUMB)

    for d, name, pred in DATA:
        sh = shapes[d]
        L += ["", "## %s（谓词 %s，s = %d s）" % (name, pred, S)]
        if sh:
            L.append("事件 %d、组 %d、时长 %.1f 小时；n（每组每窗事件数中位）：%s" % (
                sh[0], sh[1], sh[2], "，".join("W = %d 分 %s" % (w // 60, fnum(sh[3][w], "%g")) for w in WS)))
        L.append("W 分\tAGG\tn\tT_GRETA-C++\tT_SlotTree\tr\t带 GRETA-C++\t带 SlotTree\tMB GRETA-C++\tMB SlotTree\t内存比 S÷G\t计时\t校验和一致")
        for x in allrows[d]:
            how = x["skip"] or ("单次计时（探测遍 ≥ 60 s，E1 偏离 1）：" + "、".join("GRETA-C++" if a == "OPP" else "SlotTree" for a in x["single"]) if x["single"] else "3 进程")
            L.append("%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s" % (
                x["W"] // 60, x["agg"], fnum(x["n"], "%g"), fnum(x["To"]), fnum(x["Tm"]), fnum(x["r"], "%.3f"), fnum(x["bo"], "%.3f"), fnum(x["bm"], "%.3f"),
                fnum(x["mo"], "%.1f"), fnum(x["mm"], "%.1f"), fnum(x["memr"], "%.2f"), how, "是" if x["ck"] == 1 else ("否（%d 个）" % x["ck"] if x["ck"] else "-")))
        both = [x for x in allrows[d] if x["r"] is not None]
        if both:
            L.append("按样本直接合计 Σ T_GRETA-C++ ÷ Σ T_SlotTree = %.3f（%d 个设置）；内存比 %.2f – %.2f；n ≥ %d 且 r ≥ %.2f 的设置 %d / %d（描述性）" % (
                sum(x["To"] for x in both) / sum(x["Tm"] for x in both), len(both), min(x["memr"] for x in both), max(x["memr"] for x in both),
                N_LINE, RULE_OF_THUMB, sum(1 for x in both if x["n"] >= N_LINE and x["r"] >= RULE_OF_THUMB), sum(1 for x in both if x["n"] >= N_LINE)))

    w = c1.work(tm)   # ["", 标题, 表头, 行…]；行按流、AGG、W 重排
    order = [x[0] for x in DATA]
    body = sorted(w[3:], key=lambda l: (order.index(l.split("\t")[0]) if l.split("\t")[0] in order else 99, l.split("\t")[2], int(l.split("\t")[3])))
    L += ["", "## 工作量与模式（第 1 个进程的 --work 计数；OPP累加÷M槽 = 两臂逐事件工作量之比；描述性）", w[2]] + body
    bands = [tm.band(k) for k in tm.procmed if len(tm.procmed[k]) >= 2]
    single = sorted("%s %s %s W=%d" % (k[0], k[1], k[3], k[4] // 60) for k in tm.procmed if len(tm.procmed[k]) < 2)
    L += ["", "## 噪声与计时方式",
          "3 进程噪声带（全部 臂 × 格）：中位 %s、最大 %s（%d 个）" % (fnum(statistics.median(bands) if bands else None, "%.3f"), fnum(max(bands) if bands else None, "%.3f"), len(bands)),
          "单次计时（探测遍 ≥ 60 s）的 (臂 × 格)：%s" % ("、".join(single) or "无")]
    L += ["", "## 不跑的规则（README 第 2 节；公式在第 3 节；逐格判定在 %s）" % os.path.relpath(rules_path, HERE),
          "数据\tAGG\tW 分\t规则\t依据\t外推\t上限\t判定"]
    for (d, agg, W, rule), r in sorted(rules.items(), key=lambda kv: ([x[0] for x in DATA].index(kv[0][0]), kv[0][2], kv[0][1], kv[0][3])):
        L.append("%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s" % (d, agg, W // 60, "GRETA-C++ 单遍秒数" if rule == "opp_time" else "SlotTree 峰值 KB", r["basis"], r["predicted"], r["limit"], r["decision"]))

    # 表 1 同款列：W = 10 分 COUNT 的吞吐（百万事件 / 秒 = events ÷ 行时间）与两臂峰值内存
    srows = []
    for d, name, pred in DATA:
        sh = shapes[d]
        k = (d, "hold", "COUNT", 600)
        thr = {}
        for a in ("M", "OPP"):
            kk = (a,) + k
            thr[a] = tm.info[kk]["events"] / tm.T[kk] / 1e6 if kk in tm.T and "events" in tm.info.get(kk, {}) else None
        srows.append([d, name, pred, S] + ([sh[0], sh[1], "%.1f" % sh[2]] + [fnum(sh[3][w], "%g") for w in WS] if sh else ["-"] * 6) +
                     [fnum(thr["M"], "%.3f"), fnum(thr["OPP"], "%.3f"), fnum(mb(tm, ("M",) + k), "%.0f"), fnum(mb(tm, ("OPP",) + k), "%.0f")])
    L += ["", "## 表 1 同款（W = 10 分、COUNT；吞吐 = 百万事件 / 秒；内存 MB；%s）" % os.path.relpath(streams, HERE), "\t".join(SCOLS)]
    L += ["\t".join(map(str, r)) for r in srows]
    txt = "\n".join(L) + "\n"
    with open(streams, "w", encoding="utf-8") as f:
        f.write("\t".join(SCOLS) + "\n" + "".join("\t".join(map(str, r)) + "\n" for r in srows))
    with open(out, "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["nvals"]:
        sh = shape(a[1], {}, a[2] if len(a) > 2 else None)
        print("\n".join("%d %s" % (w, sh[3][w]) for w in WS))
    else:
        kw = {}
        for i in range(0, len(a), 2):
            kw[{"--times": "times", "--rules": "rules_path", "--out": "out", "--streams": "streams"}[a[i]]] = a[i + 1]
        main(**kw)
