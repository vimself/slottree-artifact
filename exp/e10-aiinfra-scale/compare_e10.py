r"""E10 · 判读脚本。判据原文（与 README 第 1 节同文，提交后一字不改）：

<!-- 判据开始 -->
**臂与口径**：GRETA-C++（`OPP`）与 SlotTree（`M`，c = 2、B = 1024），E9 的同一个 v2 二进制；r = T_GRETA-C++ ÷ T_SlotTree；计时、不跑的规则、单次计时的条件都照 E9（`exp/e9-aiinfra/README.md` 第 2 节）。⋈ 为 <，s = 30 s，skip-till-any-match。线取 MVP 的线（1.5 与 2）。

**部分 A · 集群回放（二值，K6）**。问题：几百块 GPU 同时上报时，一个核跟得上多少块，每块 GPU 占多少状态内存。
- 回放流 R(G)：从 E9 流 A（`exp/e9-aiinfra/data/gpu_hold.tsv`，25 个 [作业, GPU]）切出每段 D = 3,600 s 的真实读数片段，G 块回放 GPU 各放一段、同时上报。切法（确定性，不许挑）：每个源组从它第一个事件的时间 t0 起切连续不重叠的片段 [t0 + mD, t0 + (m+1)D)，m = 0, 1, …；只留完整的片段（该组的时长盖住整段，且段内事件数 ≥ 0.5 × D × 10）；片段按（m, 源组在文件里首次出现的先后）排序，共 S 段。第 i 块回放 GPU（i = 0 … G − 1）放第 (i mod S) 段，时间平移到从 o_i = (i × 7,919) mod 100,000 微秒开始（各块 GPU 的采样相位错开），组号 = i；全部事件按（时间, 组号）排序。G > S 时片段重复使用（读数相同、相位不同），S 与重复次数照实写。
- 格：G ∈ {25, 100, 400} × W ∈ {10, 30} 分，AGG = COUNT（引言查询框的聚合；E9 里 COUNT 的 r 低于 SUM，取它不占便宜）。不跑的规则同 E9：GRETA-C++ 外推单遍 > 7,200 s 的格 GRETA-C++ 不跑；SlotTree 外推峰值内存 > 10 GiB 的格两臂都不跑。外推取同 W 小一档 G 的实测 × G 之比；G = 25 照跑。
- 每格报：事件数、两臂时间、r、**每核跟得上的 GPU 数** = G × D ÷ T（D 秒的读数用 T 秒处理完）、**每块 GPU 的状态内存** =（峰值 RSS − 输入占用）÷ G（输入占用的扣法跑之前写进第 3 节）。
- **K6（每个 W 各判一次，只用本机的格）**：该 W 跑完的格里**每一个** r ≥ 1.5，**且至少一个** r ≥ 2。跑完的格不足 2 个 ⇒ 该 W 记「未判」。
- 二值：两个 W 的 K6 都成立 ⇒ **C28 进正文**（「G 块 GPU 同时上报一小时的读数，GRETA-C++ 用 … 秒、SlotTree 用 … 秒；一个核各跟得上 … 块」，取跑完的最大 G），引言的钩子可以换成这个口径。只有一个 W 成立 ⇒ 只写成立的那个 W。都不成立 ⇒ 照报为适用边界，引言不用这个口径。每块 GPU 的状态内存无论哪种都进 Limitations。
- 预期（不设线，照报）：r 随 G 增大而下降（合成实验 E5 的 S2：组数 1 → 100 时 r 从 34 降到 18）。

**部分 B · 同一时段的全部模型（二值，K7）**。问题：E9 流 B 只取了最忙的 10 个模型，换成全部模型结论还在不在。
- 流：Chutes 第 0 个分片、E9 流 B 的同一段时间（开头 T = 27 小时）、**全部模型**的 `ttft` 非空请求；事件定义与 d = 3 同 E9。组 = 模型。
- 设置：W ∈ {5, 10, 30} 分 × COUNT / SUM，共 6 个。臂：GRETA-C++、SlotTree，另加 always index（`A4`）作描述性对照。
- **K7**：跑完的设置里**每一个** r ≥ 1.5，**且至少一个** r ≥ 2；跑完的不足 2 个 ⇒ 未判。这条流按中位 n 可能低于 106，所以 K5 的 n 条件这里不用：整条流的时间由最忙的几个模型决定，这正是要验的。
- 二值：成立 ⇒ **C29 进正文**（「同一时段全部 … 个模型上 r 为 …」），「取最忙的 10 个」写成一句切片规则。不成立 ⇒ 照报，并写明加速只在忙的模型上。
- 另报（不设线）：模型数、事件数、各 W 的 n 中位、n ≥ 106 的组占多少事件；T_always index ÷ T_SlotTree（同一条流里忙模型用树、冷门模型用扫描，选择器比始终索引省多少）。

**部分 C · 逐事件延迟（描述性，不设线）**。E6 的协议（`exp/e6-latency/README.md` 第 1 节）原样用于 E9 的两条流：W = 10 分、COUNT，两臂；报 p50 / p99 / p99.9 / 最大，压缩与切换的次数、占比与最长停顿。

**部分 D · 第二平台（描述性，不设线）**。E7 的协议（`exp/e7-platform/README.md` 第 1 节）原样：E9 的 12 个设置与部分 A 的 6 个回放格在工作站（i9-14900K、Linux、gcc）复跑，两臂；内存的不跑线改成 150 GiB（工作站 192 GB），7,200 s 的线不变。数据由工作站按 E9 的切片脚本自己下载并核 sha256（MIT Supercloud 许可不许再分发，不经 git 传）；Chutes 分片下不了就只跑 GPU 流与回放，照实写。校验和须与本机逐格相同（本机没跑的回放格只要求两臂一致）。报每条流 r 的最小 / 中位 / 最大、与本机 r 的 Spearman；回放格报部分 A 的同款量。K6 只在本机的格上判，工作站的回放格是描述性的。

**通用**：正确性闸不过不计时——每格各臂整流校验和相同；回放流 R(100) 与部分 B 的流，每组前 2,000 个事件对 `exp/e1-main/brute_e1.py` 的递推参考逐窗口相同。引擎与常数不许为这些流调；看过计时数据之后改的任何东西记第 3 节偏离。
<!-- 判据结束 -->

用法：python3 -I exp/e10-aiinfra-scale/compare_e10.py            → report_e10.txt、handoff/e10_replay.tsv
      python3 -I exp/e10-aiinfra-scale/compare_e10.py shape      → handoff/e10_streams.tsv（各流的形状与 sha256；第一次引擎运行之前写、提交）
      python3 -I exp/e10-aiinfra-scale/compare_e10.py nvals <tsv> → 每个 W（秒）的 n（run_e10.sh 部分 B 的不跑规则用，算法同 E1 / E9）
      python3 -I exp/e10-aiinfra-scale/compare_e10.py --dir <目录> --out <txt>   自测用：读 <目录>/e10_*.tsv，不写 handoff
输入（handoff/，run_e10.sh 产出）：e10_times.tsv（部分 A、B；列同 exp/e1-main/handoff/e1_times.tsv）、e10_rules.tsv（不跑规则逐格判定）、
e10_probe.tsv（探测遍）、e10_mem.tsv（部分 A 的输入占用）、e10_latency.tsv 与 e10_dist.tsv（部分 C）、e10_streams.tsv（流的形状）；
工作站回传后另有 e10_ws_times.tsv、e10_ws_rules.tsv、e10_ws_mem.tsv（部分 D）。行时间、噪声带、工作量调用 exp/e1-main/compare_e1.py
（Times、work），n 的算法同 exp/e1-main/prep_e1.py 的 stats；不复制。纯标准库。判据文字之后不动。
"""
import hashlib, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.normpath(os.path.join(HERE, "..", "e1-main"))
E9 = os.path.normpath(os.path.join(HERE, "..", "e9-aiinfra"))
if E1 not in sys.path:
    sys.path.insert(0, E1)
import compare_e1 as c1  # noqa: E402

HO = os.path.join(HERE, "handoff")
REPORT = os.path.join(HERE, "report_e10.txt")
E9_TIMES = os.path.join(E9, "handoff", "e9_times.tsv")
S = 30                      # 滑动 s（秒）
D_SEC = 3600                # 回放片段 D（秒）
GS = [25, 100, 400]
WA = [600, 1800]            # 部分 A 的 W（秒）
WB = [300, 600, 1800]       # 部分 B 的 W（秒）
AGGS = ["COUNT", "SUM"]
R_ALL, R_ONE = 1.5, 2.0     # K6、K7 的线（判据原文）
N_LINE = 106                # 部分 B 只描述：n ≥ 106 的组占多少事件
MIB = 1024 * 1024
# 形状表里的流：键 → (文件, 说明)
STREAM_FILES = [
    ("r25", os.path.join(HERE, "data", "replay_G25.tsv"), "回放 R(25)"),
    ("r100", os.path.join(HERE, "data", "replay_G100.tsv"), "回放 R(100)"),
    ("r400", os.path.join(HERE, "data", "replay_G400.tsv"), "回放 R(400)"),
    ("llmall", os.path.join(HERE, "data", "llm_all.tsv"), "Chutes 27 小时全部模型"),
    ("gpu", os.path.join(E9, "data", "gpu_hold.tsv"), "E9 流 A（GPU 功耗）"),
    ("llm", os.path.join(E9, "data", "llm_hold.tsv"), "E9 流 B（LLM 首 token 延迟，前 10 个模型）"),
]
SCOLS = ["data", "name", "events", "groups", "span_h", "n_300", "n_600", "n_1800", "bigshare_300", "bigshare_600", "bigshare_1800", "sha256"]


def criteria_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 判据开始 -->"):s.index("<!-- 判据结束 -->")]
    return cut(me) == cut(rd)


def read_tsv(path):
    return c1.read_tsv(path) if os.path.exists(path) else []


def fnum(x, f="%.4f"):
    return "-" if x is None or x != x else f % x


def med(v):
    return statistics.median(v) if v else None


# ---------------------------------------------------------------- 流的形状（n 的算法同 exp/e1-main/prep_e1.py 的 stats，另按组留中位）
def group_stats(path, s=S, Ws=(300, 600, 1800)):
    """→ dict(events, groups, span_h, n={W: 每（组, 窗口）事件数中位}, ng={W: {组: 该组每窗事件数中位}}, ev={组: 事件数})。
    窗口 j 覆盖 [j·s, j·s + W)，只算含事件的窗口（同 prep_e1.stats）。"""
    import bisect
    su = s * 1000000
    panes, ev = {}, {}
    lo = hi = None
    for line in open(path, encoding="utf-8"):
        g, t, _ = line.split("\t", 2)
        t = int(t)
        d = panes.setdefault(g, {})
        p = t // su
        d[p] = d.get(p, 0) + 1
        ev[g] = ev.get(g, 0) + 1
        lo = t if lo is None or t < lo else lo
        hi = t if hi is None or t > hi else hi
    out = dict(events=sum(ev.values()), groups=len(ev), span_h=(hi - lo) / 3.6e9, n={}, ng={}, ev=ev)
    for w in Ws:
        k = w // s
        allsz, per = [], {}
        for g, pc in panes.items():
            ps = sorted(pc)
            pre = [0]
            for p in ps:
                pre.append(pre[-1] + pc[p])
            js, last = [], None
            for p in ps:
                a = p - k + 1 if last is None or p - k + 1 > last else last + 1
                js.extend(range(a, p + 1))
                last = p
            sz = [pre[bisect.bisect_left(ps, j + k)] - pre[bisect.bisect_left(ps, j)] for j in js]
            per[g] = statistics.median(sz)
            allsz.extend(sz)
        out["n"][w] = statistics.median(allsz)
        out["ng"][w] = per
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_shapes(path=os.path.join(HO, "e10_streams.tsv")):
    rows = []
    for d, f, name in STREAM_FILES:
        st = group_stats(f)
        big = {w: sum(st["ev"][g] for g, x in st["ng"][w].items() if x >= N_LINE) / st["events"] for w in WB}
        rows.append([d, name, st["events"], st["groups"], "%.3f" % st["span_h"]] + ["%g" % st["n"][w] for w in WB] +
                    ["%.4f" % big[w] for w in WB] + [sha256(f)])
        print("%s：%d 个事件、%d 个组、时长 %.2f h；n %s；n ≥ %d 的组占事件 %s" % (
            d, st["events"], st["groups"], st["span_h"], " / ".join("%g" % st["n"][w] for w in WB), N_LINE,
            " / ".join("%.4f" % big[w] for w in WB)))
        if d == "llmall":
            for w in WB:
                ng = st["ng"][w]
                print("  W = %d 分：n ≥ %d 的模型 %d 个（%s）" % (w // 60, N_LINE, sum(1 for x in ng.values() if x >= N_LINE),
                                                          "、".join("%s…:%g" % (g[:8], x) for g, x in sorted(ng.items(), key=lambda kv: -kv[1])[:12])))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fo:
        fo.write("\t".join(SCOLS) + "\n" + "".join("\t".join(map(str, r)) + "\n" for r in rows))
    print("→ %s" % path)


def shapes(path):
    return {r["data"]: r for r in read_tsv(path)}


# ---------------------------------------------------------------- 公共
def mb_max(tm, k):
    return max(tm.info[k]["maxrss"]) / 1024 if k in tm.info else None


def rules_of(path):
    return {(r["data"], r["agg"], int(r["W"]), r["rule"]): r for r in read_tsv(path)}


def skip_text(rules, d, agg, W):
    rm, rt = rules.get((d, agg, W, "mem")), rules.get((d, agg, W, "opp_time"))
    if rm and rm["decision"] == "不跑":
        return "两臂未跑：内存上限（SlotTree 外推 %.2f GiB > %.3g GiB）" % (int(rm["predicted"]) / MIB, int(rm["limit"]) / MIB)
    ra = rules.get((d, agg, W, "a4_mem"))
    s = ""
    if rt and rt["decision"] == "不跑":
        s = "GRETA-C++ 未跑：外推单遍 %s s > %s s" % (rt["predicted"], rt["limit"])
    if ra and ra["decision"] == "不跑":
        s += ("；" if s else "") + "always index 未跑：内存外推 %.2f GiB" % (int(ra["predicted"]) / MIB)
    return s


def how(tm, ks, names):
    if not any(k in tm.procmed for _, k in ks):
        return "-"
    single = [names[a] for a, k in ks if k in tm.procmed and len(tm.procmed[k]) == 1]
    return ("单次计时（探测遍 ≥ 60 s）：" + "、".join(single)) if single else "3 进程"


def ck_count(tm, keys):
    cks = set()
    for k in keys:
        if k in tm.info:
            cks |= tm.info[k]["checksum"]
    return len(cks)


NAMES = {"OPP": "GRETA-C++", "M": "SlotTree", "A4": "always index"}


def verdict(rs):
    """K6 / K7 的同一条线：跑完的里每一个 r ≥ 1.5 且至少一个 r ≥ 2；跑完的不足 2 个 ⇒ 未判。"""
    if len(rs) < 2:
        return "未判（跑完的只有 %d 个，判据要至少 2 个）" % len(rs)
    return "成立" if all(r >= R_ALL for r in rs) and any(r >= R_ONE for r in rs) else "不成立"


# ---------------------------------------------------------------- 部分 A
def mem_table(path):
    return {r["data"]: r for r in read_tsv(path)}


def part_a_rows(tm, rules, mem):
    rows = []
    for W in WA:
        for G in GS:
            d = "r%d" % G
            o, m = ("OPP", d, "hold", "COUNT", W), ("M", d, "hold", "COUNT", W)
            x = dict(G=G, W=W, d=d, To=tm.T.get(o), Tm=tm.T.get(m), bo=tm.band(o) if o in tm.T else None, bm=tm.band(m) if m in tm.T else None,
                     mo=mb_max(tm, o), mm=mb_max(tm, m), skip=skip_text(rules, d, "COUNT", W), how=how(tm, [("OPP", o), ("M", m)], NAMES),
                     ck=ck_count(tm, [o, m]), events=None)
            x["r"] = x["To"] / x["Tm"] if x["To"] and x["Tm"] else None
            cp = 1                      # 短行加长的份数 D（E1 第 1 节）：这些流的探测遍都远超 5 ms，预计 D = 1；不是 1 时按每份折算、内存不算
            for a, k in (("o", o), ("m", m)):
                if k in tm.info:
                    cp = int(tm.info[k]["copies"])
                    if "events" in tm.info[k]:
                        x["events"] = tm.info[k]["events"] // cp
            x["copies"] = cp
            mt = mem.get(d)
            for a, k in (("o", o), ("m", m)):
                T = x["T" + a]
                x["core" + a] = G * D_SEC / (T / cp) if T else None
                pk = max(tm.info[k]["maxrss"]) if k in tm.info else None
                if pk is not None and mt and cp == 1:
                    x["st" + a] = (pk * 1024 - int(mt["base_kb"]) * 1024 - int(mt["input_bytes"])) / G / MIB
                    x["lo" + a] = (pk - int(mt["parse_peak_kb"])) * 1024 / G / MIB
                else:
                    x["st" + a] = x["lo" + a] = None
            rows.append(x)
    return rows


def part_a(tm, rules, mem, replay_out):
    rows = part_a_rows(tm, rules, mem)
    L = ["", "## 部分 A · 集群回放（K6；r = T_GRETA-C++ ÷ T_SlotTree；每核跟得上的 GPU 数 = G × %d ÷ T；COUNT，⋈ 为 <，s = %d s）" % (D_SEC, S)]
    held = {}
    for W in WA:
        done = [x for x in rows if x["W"] == W and x["r"] is not None]
        v = verdict([x["r"] for x in done])
        held[W] = v
        L.append("W = %d 分：跑完 %d 格（G = %s）；r %s ⇒ K6 %s" % (
            W // 60, len(done), "、".join(str(x["G"]) for x in done) or "-", "、".join("%.3f" % x["r"] for x in done) or "-", v))
    ok = [W for W in WA if held[W] == "成立"]

    def c28(W):
        done = [x for x in rows if x["W"] == W and x["r"] is not None]
        x = max(done, key=lambda y: y["G"])
        return ("W = %d 分：%d 块 GPU 同时上报一小时的读数，GRETA-C++ 用 %.1f 秒、SlotTree 用 %.2f 秒；一个核各跟得上 %.0f 块、%.0f 块" % (
            W // 60, x["G"], x["To"], x["Tm"], x["coreo"], x["corem"]))
    if len(ok) == 2:
        L.append("二值：两个 W 的 K6 都成立 ⇒ C28 进正文（取跑完的最大 G）：「%s」；「%s」；引言的钩子可以换成这个口径" % (c28(WA[0]), c28(WA[1])))
    elif len(ok) == 1:
        L.append("二值：只有 W = %d 分的 K6 成立 ⇒ 只写这个 W：「%s」" % (ok[0] // 60, c28(ok[0])))
    else:
        L.append("二值：两个 W 的 K6 都不成立（或未判）⇒ 照报为适用边界，引言不用这个口径")
    L.append("每块 GPU 的状态内存无论哪种都进 Limitations（下表；扣法见 README 第 3 节）")
    L.append("W 分\tG\tD\t事件\tT_GRETA-C++\tT_SlotTree\tr\t带 GRETA-C++\t带 SlotTree\t每核 GPU 数 GRETA-C++\t每核 GPU 数 SlotTree\t"
             "峰值 MB GRETA-C++\t峰值 MB SlotTree\t每 GPU 状态 MB GRETA-C++\t每 GPU 状态 MB SlotTree\t（下界）GRETA-C++\t（下界）SlotTree\t计时\t校验和一致")
    for x in rows:
        L.append("\t".join([str(x["W"] // 60), str(x["G"]), str(x["copies"]), fnum(x["events"], "%d"), fnum(x["To"]), fnum(x["Tm"]), fnum(x["r"], "%.3f"),
                            fnum(x["bo"], "%.3f"), fnum(x["bm"], "%.3f"), fnum(x["coreo"], "%.1f"), fnum(x["corem"], "%.1f"),
                            fnum(x["mo"], "%.1f"), fnum(x["mm"], "%.1f"), fnum(x["sto"], "%.2f"), fnum(x["stm"], "%.2f"),
                            fnum(x["loo"], "%.2f"), fnum(x["lom"], "%.2f"), x["skip"] or x["how"],
                            "是" if x["ck"] == 1 else ("否（%d 个）" % x["ck"] if x["ck"] else "-")]))
    L.append("每核 GPU 数 = G × %d ÷（T ÷ D）；每 GPU 状态 =（该臂 3 个进程的峰值 RSS 最大 − 进程基线 − 20 字节 × 事件数）÷ G；（下界）=（峰值 − 只解析不计算的进程峰值）÷ G（README 第 3 节；D ≠ 1 的格内存不算）" % D_SEC)
    if mem:
        L.append("输入占用（e10_mem.tsv）：" + "；".join("%s 事件 %s、20 字节 × 事件 %.1f MB、进程基线 %.1f MB、只解析的峰值 %.1f MB" % (
            d, r["events"], int(r["input_bytes"]) / MIB, int(r["base_kb"]) / 1024, int(r["parse_peak_kb"]) / 1024) for d, r in sorted(mem.items(), key=lambda kv: int(kv[0][1:]))))
    if replay_out:
        cols = ["W", "G", "events", "T_OPP", "T_M", "r", "gpus_per_core_OPP", "gpus_per_core_M", "peak_MB_OPP", "peak_MB_M",
                "state_MB_per_gpu_OPP", "state_MB_per_gpu_M", "state_lo_MB_per_gpu_OPP", "state_lo_MB_per_gpu_M", "skip"]
        with open(replay_out, "w", encoding="utf-8") as f:
            f.write("\t".join(cols) + "\n")
            for x in rows:
                f.write("\t".join([str(x["W"]), str(x["G"]), fnum(x["events"], "%d"), fnum(x["To"], "%.6f"), fnum(x["Tm"], "%.6f"), fnum(x["r"], "%.4f"),
                                   fnum(x["coreo"], "%.3f"), fnum(x["corem"], "%.3f"), fnum(x["mo"], "%.1f"), fnum(x["mm"], "%.1f"),
                                   fnum(x["sto"], "%.3f"), fnum(x["stm"], "%.3f"), fnum(x["loo"], "%.3f"), fnum(x["lom"], "%.3f"), x["skip"] or "-"]) + "\n")
    return L, rows, held


# ---------------------------------------------------------------- 部分 B
def part_b(tm, rules, sh):
    d = "llmall"
    rows = []
    for W in WB:
        for agg in AGGS:
            ks = {a: (a, d, "hold", agg, W) for a in ("OPP", "M", "A4")}
            x = dict(W=W, agg=agg, T={a: tm.T.get(k) for a, k in ks.items()}, mb={a: mb_max(tm, k) for a, k in ks.items()},
                     band={a: (tm.band(k) if k in tm.T else None) for a, k in ks.items()}, skip=skip_text(rules, d, agg, W),
                     how=how(tm, list(ks.items()), NAMES), ck=ck_count(tm, list(ks.values())))
            x["r"] = x["T"]["OPP"] / x["T"]["M"] if x["T"]["OPP"] and x["T"]["M"] else None
            x["a4"] = x["T"]["A4"] / x["T"]["M"] if x["T"]["A4"] and x["T"]["M"] else None
            rows.append(x)
    done = [x for x in rows if x["r"] is not None]
    v = verdict([x["r"] for x in done])
    s = sh.get(d)
    L = ["", "## 部分 B · 同一时段的全部模型（K7；Chutes 第 0 个分片开头 27 小时、ttft 非空的全部请求；组 = 模型；⋈ 为 <，s = %d s）" % S]
    if s:
        L.append("模型 %s 个、事件 %s、时长 %.2f 小时；n（每组每窗事件数中位）：%s；n ≥ %d 的组占事件：%s" % (
            s["groups"], s["events"], float(s["span_h"]), "，".join("W = %d 分 %s" % (w // 60, s["n_%d" % w]) for w in WB), N_LINE,
            "，".join("W = %d 分 %.1f%%" % (w // 60, 100 * float(s["bigshare_%d" % w])) for w in WB)))
    rs = [x["r"] for x in done]
    L.append("跑完 %d / %d 个设置；r 最小 %s、中位 %s、最大 %s ⇒ K7 %s" % (len(done), len(rows), fnum(min(rs) if rs else None, "%.3f"),
                                                                 fnum(med(rs), "%.3f"), fnum(max(rs) if rs else None, "%.3f"), v))
    if v == "成立":
        L.append("二值：K7 成立 ⇒ C29 进正文：「同一时段全部 %s 个模型上 r 为 %s – %s（中位 %s）」，「取最忙的 10 个」写成一句切片规则" % (
            s["groups"] if s else "?", fnum(min(rs), "%.1f"), fnum(max(rs), "%.1f"), fnum(med(rs), "%.1f")))
    elif v == "不成立":
        L.append("二值：K7 不成立 ⇒ 照报，并写明加速只在忙的模型上")
    else:
        L.append("二值：K7 未判 ⇒ 照报")
    L.append("W 分\tAGG\tT_GRETA-C++\tT_SlotTree\tT_always index\tr\tT_always index ÷ T_SlotTree\t带 GRETA-C++\t带 SlotTree\t带 always index\t"
             "MB GRETA-C++\tMB SlotTree\tMB always index\t计时\t校验和一致")
    for x in rows:
        L.append("\t".join([str(x["W"] // 60), x["agg"]] + [fnum(x["T"][a]) for a in ("OPP", "M", "A4")] + [fnum(x["r"], "%.3f"), fnum(x["a4"], "%.3f")] +
                           [fnum(x["band"][a], "%.3f") for a in ("OPP", "M", "A4")] + [fnum(x["mb"][a], "%.1f") for a in ("OPP", "M", "A4")] +
                           [x["skip"] or x["how"], "是" if x["ck"] == 1 else ("否（%d 个）" % x["ck"] if x["ck"] else "-")]))
    both = [x for x in rows if x["r"] is not None]
    if both:
        L.append("按样本直接合计 Σ T_GRETA-C++ ÷ Σ T_SlotTree = %.3f（%d 个设置）" % (sum(x["T"]["OPP"] for x in both) / sum(x["T"]["M"] for x in both), len(both)))
    a4 = [x for x in rows if x["a4"] is not None]
    if a4:
        L.append("always index ÷ SlotTree（描述性）：中位 %.3f、最小 %.3f、最大 %.3f；直接合计 Σ T_always index ÷ Σ T_SlotTree = %.3f（%d 个设置）" % (
            med([x["a4"] for x in a4]), min(x["a4"] for x in a4), max(x["a4"] for x in a4),
            sum(x["T"]["A4"] for x in a4) / sum(x["T"]["M"] for x in a4), len(a4)))
    # 同一时段前 10 个模型（E9 流 B）的 r 并排（描述性）
    if os.path.exists(E9_TIMES):
        t9 = c1.Times(E9_TIMES)
        pairs = []
        for x in rows:
            o, m = ("OPP", "llm", "hold", x["agg"], x["W"]), ("M", "llm", "hold", x["agg"], x["W"])
            if o in t9.T and m in t9.T and x["r"] is not None:
                pairs.append("W = %d 分 %s：全部模型 %.2f 对前 10 个 %.2f" % (x["W"] // 60, x["agg"], x["r"], t9.T[o] / t9.T[m]))
        if pairs:
            L.append("对照 E9 流 B（同一时段前 10 个模型；描述性）：" + "；".join(pairs))
    return L, rows, v


# ---------------------------------------------------------------- 部分 C
CAT = {0: "普通", 1: "窗格边界", 2: "压缩", 3: "切换"}


def us(ns):
    ns = float(ns)
    if ns < 1e3:
        return "%.0f ns" % ns
    if ns < 1e6:
        return "%.1f µs" % (ns / 1e3)
    return "%.2f ms" % (ns / 1e6)


def part_c(lat_path, dist_path):
    rows = read_tsv(lat_path)
    if not rows:
        return ["", "## 部分 C · 逐事件延迟：没有 %s" % os.path.relpath(lat_path, HERE)]
    by = {}
    for r in rows:
        by.setdefault((r["data"], r["arm"]), []).append(r)
    t9 = c1.Times(E9_TIMES) if os.path.exists(E9_TIMES) else None
    L = ["", "## 部分 C · 逐事件延迟（E6 的协议；W = 10 分、COUNT；描述性，不设线。分位数 = 各计时遍取中位，最大取各遍的最大）",
         "时钟标定（读一次 steady_clock 的开销中位 ns, 最小正差 ns）：%s" % "、".join("(%s, %s)" % c for c in sorted({(r["clock_med_ns"], r["clock_tick_ns"]) for r in rows}))]
    for d, name in (("gpu", "E9 流 A · GPU 功耗"), ("llm", "E9 流 B · LLM 首 token 延迟")):
        L.append("%s" % name)
        L.append("臂\t遍数\t事件数\t平均\tp50\tp99\tp99.9\tp99.99\t最大\t压缩次数\t切换次数（窗格内）\t压缩 + 切换占事件\t最长停顿（压缩 / 切换）\t逐事件计时遍总时间 ÷ E9 行时间")
        for a in ("OPP", "M"):
            v = by.get((d, a))
            if not v:
                continue
            m = lambda c: statistics.median(float(x[c]) for x in v)
            n2, n3 = m("n2"), m("n3")
            pause = max([float(x["max_2"]) for x in v if int(x["n2"])] + [float(x["max_3"]) for x in v if int(x["n3"])] or [0])
            ov = "-"
            if t9 is not None:
                k = (a, d, "hold", "COUNT", 600)
                if k in t9.T:
                    ov = "%.2f" % (m("seconds") / (t9.T[k] / int(t9.info[k]["copies"])))
            L.append("\t".join([NAMES[a], str(len(v)), v[0]["events"], us(m("mean_ns")), us(m("p50_ns")), us(m("p99_ns")), us(m("p999_ns")),
                                us(m("p9999_ns")), us(max(float(x["max_ns"]) for x in v)), "%d" % n2,
                                "%s（%s）" % (v[0]["switches"], v[0].get("inpane_switches", "-")),
                                "%.4f%%" % (100 * (n2 + n3) / int(v[0]["events"])), us(pause) if pause else "-", ov]))
        L.append("按类别（次数 = 各遍中位；p99 = 各遍中位；最大 = 各遍最大）：")
        L.append("臂\t" + "\t".join("%s 次数\t%s p99\t%s 最大" % (CAT[c], CAT[c], CAT[c]) for c in range(4)))
        for a in ("OPP", "M"):
            v = by.get((d, a))
            if not v:
                continue
            cells = []
            for c in range(4):
                n = statistics.median(int(x["n%d" % c]) for x in v)
                cells += ["0", "-", "-"] if n == 0 else ["%d" % n, us(statistics.median(float(x["p99_%d" % c]) for x in v)), us(max(float(x["max_%d" % c]) for x in v))]
            L.append("\t".join([NAMES[a]] + cells))
    drows = read_tsv(dist_path)
    if drows:
        top = {}
        for r in drows:
            if r["kind"] == "top" and r["pass"] == "1":
                top.setdefault((r["data"], r["arm"]), []).append(r)
        L.append("前 100 大的事件（第 1 遍）按类别计数，以及第 100 大的值")
        L.append("流\t臂\t" + "\t".join(CAT[c] for c in range(4)) + "\t第 100 大")
        for d in ("gpu", "llm"):
            for a in ("OPP", "M"):
                v = top.get((d, a))
                if v:
                    L.append("\t".join([d, NAMES[a]] + [str(sum(1 for x in v if x["f3"] == str(c))) for c in range(4)] + [us(min(float(x["f2"]) for x in v))]))
    cks = {}
    for r in rows:
        cks.setdefault(r["data"], set()).add(r["checksum"])
    L.append("每条流各臂、各遍的校验和一致：%s" % "、".join("%s %s" % (d, len(c) == 1) for d, c in sorted(cks.items())))
    if t9 is not None:
        L.append("与 E9 同格（COUNT W = 10 分）的校验和相同：%s" % "、".join(
            "%s %s" % (d, cks[d] == t9.info[("M", d, "hold", "COUNT", 600)]["checksum"]) for d in sorted(cks) if ("M", d, "hold", "COUNT", 600) in t9.info))
    return L


# ---------------------------------------------------------------- 部分 D
def spearman(x, y):
    def rank(v):
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
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def part_d(tm, ws_dir):
    wt = os.path.join(ws_dir, "e10_ws_times.tsv")
    if not os.path.exists(wt):
        return ["", "## 部分 D · 第二平台：工作站没有回传（%s 不在）；跑不跑由用户定" % os.path.relpath(wt, HERE)]
    tw = c1.Times(wt)
    rules = rules_of(os.path.join(ws_dir, "e10_ws_rules.tsv"))
    mem = mem_table(os.path.join(ws_dir, "e10_ws_mem.tsv"))
    t9 = c1.Times(E9_TIMES) if os.path.exists(E9_TIMES) else None
    L = ["", "## 部分 D · 第二平台（E7 的协议；工作站 %s；描述性，K6 只在本机的格上判）" % os.path.relpath(wt, HERE)]
    cells = [(d, agg, W) for d in ("gpu", "llm") for W in WB for agg in AGGS] + [("r%d" % G, "COUNT", W) for W in WA for G in GS]
    L.append("流\tAGG\tW 分\tT_GRETA-C++ 工作站\tT_SlotTree 工作站\tr 工作站\tr 本机\tr 工作站 ÷ r 本机\t带 GRETA-C++\t带 SlotTree\t计时\t校验和（工作站两臂一致 / 与本机相同）")
    xs, ys, per = [], [], {}
    for d, agg, W in cells:
        o, m = ("OPP", d, "hold", agg, W), ("M", d, "hold", agg, W)
        To, Tm = tw.T.get(o), tw.T.get(m)
        r = To / Tm if To and Tm else None
        loc = t9 if d in ("gpu", "llm") else tm
        rl = loc.T[o] / loc.T[m] if loc is not None and o in loc.T and m in loc.T else None
        wck = set().union(*[tw.info[k]["checksum"] for k in (o, m) if k in tw.info]) if (o in tw.info or m in tw.info) else set()
        lck = set().union(*[loc.info[k]["checksum"] for k in (o, m) if loc is not None and k in loc.info]) if loc is not None else set()
        same = "-" if not wck else ("%s / %s" % ("是" if len(wck) == 1 else "否", ("是" if wck == lck else "否") if lck else "本机没跑"))
        if r is not None:
            per.setdefault("回放" if d.startswith("r") else d, []).append(r)
            if rl is not None:
                xs.append(r); ys.append(rl)
        L.append("\t".join([d, agg, str(W // 60), fnum(To), fnum(Tm), fnum(r, "%.3f"), fnum(rl, "%.3f"), fnum(r / rl if r and rl else None, "%.3f"),
                            fnum(tw.band(o) if o in tw.T else None, "%.3f"), fnum(tw.band(m) if m in tw.T else None, "%.3f"),
                            skip_text(rules, d, agg, W) or how(tw, [("OPP", o), ("M", m)], NAMES), same]))
    for k, v in per.items():
        L.append("%s：工作站 r 最小 %.3f、中位 %.3f、最大 %.3f（%d 格）" % (k, min(v), med(v), max(v), len(v)))
    if len(xs) >= 2:
        L.append("两平台 r 的 Spearman 秩相关 %.3f（%d 格，两边都跑完的）" % (spearman(xs, ys), len(xs)))
    rows = part_a_rows(tw, rules, mem)
    L.append("回放格在工作站上（部分 A 的同款量）：")
    L.append("W 分\tG\tT_GRETA-C++\tT_SlotTree\tr\t每核 GPU 数 GRETA-C++\t每核 GPU 数 SlotTree\t每 GPU 状态 MB GRETA-C++\t每 GPU 状态 MB SlotTree")
    for x in rows:
        L.append("\t".join([str(x["W"] // 60), str(x["G"]), fnum(x["To"]), fnum(x["Tm"]), fnum(x["r"], "%.3f"), fnum(x["coreo"], "%.1f"),
                            fnum(x["corem"], "%.1f"), fnum(x["sto"], "%.2f"), fnum(x["stm"], "%.2f")]))
    return L


# ---------------------------------------------------------------- 报表
def rules_section(rules, path):
    L = ["", "## 不跑的规则（README 第 1 节、第 3 节；逐格判定在 %s）" % os.path.relpath(path, HERE), "数据\tAGG\tW 分\t规则\t依据\t外推\t上限\t判定"]
    order = ["r25", "r100", "r400", "llmall", "gpu", "llm"]
    for (d, agg, W, rule), r in sorted(rules.items(), key=lambda kv: (order.index(kv[0][0]) if kv[0][0] in order else 99, kv[0][2], kv[0][1], kv[0][3])):
        L.append("%s\t%s\t%d\t%s\t%s\t%s\t%s\t%s" % (d, agg, W // 60, {"opp_time": "GRETA-C++ 单遍秒数", "mem": "SlotTree 峰值 KB",
                                                                    "a4_mem": "always index 峰值 KB"}.get(rule, rule), r["basis"], r["predicted"], r["limit"], r["decision"]))
    return L


def main(d=HO, out=REPORT, replay_out=os.path.join(HO, "e10_replay.tsv")):
    ok = criteria_same()
    L = ["判据两处同文：%s" % ok]
    if not ok:
        print(L[0]); sys.exit(1)
    times = os.path.join(d, "e10_times.tsv")
    if not os.path.exists(times):
        print(L[0]); print("没有 %s（先 bash run_e10.sh all）" % times); sys.exit(1)
    tm = c1.Times(times)
    rules = rules_of(os.path.join(d, "e10_rules.tsv"))
    mem = mem_table(os.path.join(d, "e10_mem.tsv"))
    sh = shapes(os.path.join(HO, "e10_streams.tsv"))
    la, arows, held = part_a(tm, rules, mem, replay_out)
    lb, brows, v7 = part_b(tm, rules, sh)
    L.append("")
    L.append("## 判读摘要")
    L.append("K6（部分 A，每个 W 各判一次）：" + "；".join("W = %d 分 %s" % (W // 60, held[W]) for W in WA))
    L.append("K7（部分 B）：%s" % v7)
    L += la + lb
    L += part_c(os.path.join(d, "e10_latency.tsv"), os.path.join(d, "e10_dist.tsv"))
    L += part_d(tm, d)
    if sh:
        L += ["", "## 流的形状（%s；n = 每（组, 窗口）事件数中位，算法同 E1；bigshare = n ≥ %d 的组占的事件比例）" % (
            os.path.relpath(os.path.join(HO, "e10_streams.tsv"), HERE), N_LINE), "\t".join(SCOLS[:-1])]
        L += ["\t".join(r[c] for c in SCOLS[:-1]) for r in sh.values()]
    w = c1.work(tm)   # ["", 标题, 表头, 行…]；行按流、AGG、W 重排
    order = ["r25", "r100", "r400", "llmall"]
    body = sorted(w[3:], key=lambda l: (order.index(l.split("\t")[0]) if l.split("\t")[0] in order else 99, l.split("\t")[2], int(l.split("\t")[3])))
    L += ["", "## 工作量与模式（第 1 个进程的 --work 计数；OPP累加÷M槽 = 两臂逐事件工作量之比；描述性）", w[2]] + body
    bands = [tm.band(k) for k in tm.procmed if len(tm.procmed[k]) >= 2]
    single = sorted("%s %s %s W=%d" % (k[0], k[1], k[3], k[4] // 60) for k in tm.procmed if len(tm.procmed[k]) < 2)
    L += ["", "## 噪声与计时方式",
          "3 进程噪声带（全部 臂 × 格）：中位 %s、最大 %s（%d 个）" % (fnum(med(bands), "%.3f"), fnum(max(bands) if bands else None, "%.3f"), len(bands)),
          "单次计时（探测遍 ≥ 60 s）的 (臂 × 格)：%s" % ("、".join(single) or "无")]
    L += rules_section(rules, os.path.join(d, "e10_rules.tsv"))
    txt = "\n".join(L) + "\n"
    with open(out, "w", encoding="utf-8") as f:
        f.write(txt)
    print(txt)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["shape"]:
        write_shapes()
    elif a[:1] == ["nvals"]:
        st = group_stats(a[1])
        print("\n".join("%d %s" % (w, st["n"][w]) for w in WB))
    else:
        kw = {}
        for i in range(0, len(a), 2):
            kw[{"--dir": "d", "--out": "out", "--replay": "replay_out"}[a[i]]] = a[i + 1]
        if "d" in kw and "replay_out" not in kw:
            kw["replay_out"] = os.path.join(kw["d"], "e10_replay.tsv")
        main(**kw)
