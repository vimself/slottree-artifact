"""E8 · 选择器的窗格内检查：判读 (i)(ii)(iii) 与旁证（README 第 1 节）。纯标准库。

<!-- 协议开始 -->
**改法（v2 引擎）**：`exp/e1-main/src/trend.cpp`（v1，冻结）复制到 `src/trend.cpp` 后只改 `ArmM`：扫描模式下，当前窗格每满 B 个事件（本窗格的事件数 n_p 是 B 的倍数时），用本窗格到目前为止的和做与窗格边界同样的比较 s_p ÷ n_p > 2c · i_p ÷ n_p（s_p、i_p 是本窗格内逐事件的扫描代价与索引代价模型之和，定义同 `exp/e4-lowfreq/README.md` 第 1 节），成立就当场切到索引（当前窗格已在扫描结构里，切换把全部活窗格搬进树，做法同窗格边界的切换）。索引 → 扫描仍只在窗格边界判；窗格边界的 EWMA 更新（α = 1/2，用整个窗格的 s_p ÷ n_p、i_p ÷ n_p，含切换前后的事件）与两条线（s̄ > 2c · ī 切索引、s̄ < c · ī 切回）不变。**c = 2 不变，B = 1024**。只有代价规则的两个臂（M = 论文里的 SlotTree、A2）受影响；OPP（GRETA）、A1、A4（始终索引）、A5（规模阈值）的代码路径不变（`tests/diff_v1.py`）。`--inpane 0` 关掉检查，与 v1 逐事件同决策（闸 (e)）。

**重跑范围**：只重跑 M 与 A2（v2，B = 1024、c = 2）；OPP / A1 / A4 / A5 的数从各实验 v1 的表复制。理由：这四个臂与 v1 是同一份源码、同一编译选项，代码路径没有改动；旁证见下面「OPP 旁证」。每个实验按它自己的原口径重跑：
- **E1**：54 行（9 份切分 × W ∈ {5, 10, 30} 分 × COUNT / SUM）× {M, A2}；E1 的计时口径（`exp/e1-main/README.md` 第 1 节：3 进程、「进程 → 臂」交错、自动遍数、第 1 个进程带工作量计数）与偏离 1（探测遍 ≥ 60 s 单次计时）。短行加长的份数 D 取 v1 表里该行的值（不再为定 D 探测 OPP，同一行 v1 / v2 用同一份加长流）；交错只在重跑的臂之间
- **E2**：W 扫 24 行 + 选择度扫 11 行 × {M}，口径同 E1
- **E4**：留出段不另跑，K2' 从 E1 的 v2 表读（同 E4 原做法）。开发段（定 c）不重跑：开发数据（WPI 开发、PAMAP2 subject101–104、Intel Lab）每组每窗格的事件数最多 265 / 275 / 36 < B，任何 c 下检查都不会触发，v2 在这些行上与 v1 逐事件同决策，c = 2 照旧
- **E5**：76 格 × {M}，E5 的计时口径（`exp/e5-synth/README.md` 第 1 节：探测遍 → < 60 s 新进程 1 遍预热 + 3 遍取中位，≥ 60 s 不预热计时 1 遍；S3 加 `--work`）
- **E6**：4 行 × {M, A2}，E6 的口径（逐事件计时，预热 1 遍 + 3 遍）
- **E7**：工作站 30 行 × {M}，E7 的口径（同 E1，D = 1），代跑入口 `ws_e8.sh`
- 产出与原实验同构的表（列、表头与 v1 逐字相同）进 `handoff/`：`e1_times_v2.tsv`、`e1_rerun_binance_v2.tsv`（E1 偏离 2 那一格，M / A2 换成 v2 的同一格）、`e2_times_v2.tsv`、`e5_times_v2.tsv`、`e6_latency_v2.tsv`、`e6_dist_v2.tsv`、`e7_times_v2.tsv`；每个 M / A2 进程的窗格内切换次数进 `handoff/e8_inpane.tsv`

**判据**（行时间的口径各同原实验：E1 / E2 / E7 = 3 个进程内中位的中位；E5 = 各遍中位）：
- **(i) 修法成功**：E5 S1 里 n ∈ {10⁵, 10⁶} 的 24 格（3 种取值分布 × 2 档 n × k ∈ {1, 2, 6, 30}），**每格** T_M(v2) ÷ T_A4 ≤ 1.5（T_A4 取 E5 v1 表的数）⇒ 修法成功。不成立不停：列出哪几格超线、超多少，写进第 0 节，论文怎么写由主会话定
- **(ii) 重判**（线一字不改，用原实验的比较代码在 v2 的表上算）：E1 的 K1、K3（`exp/e1-main/README.md` 第 1 节；`compare_e1.judge`）；E4 的 K2'（`exp/e4-lowfreq/README.md` 第 1 节；`compare_e4.hold`）；E2 的 K4（`exp/e2-sweep/README.md` 第 1 节；`compare_e2`）。各自的二值结论照原文给出，与 v1 的判读并排
- **(iii) 回归检查**（只报、不判）：每个实验、每个重跑的臂，逐格 T(v2) ÷ T(v1) 的中位与范围；E5 另按「窗格内检查触发过 / 没触发」分开报

**旁证**（只报、不判）：
- **OPP 旁证**：用 v2 二进制按 E1 口径重测 OPP 的 3 个快格（WPI、PAMAP2、Porto 留出，COUNT，W = 5 分），报 T_OPP(本次) ÷ T_OPP(v1) 与两次的 3 进程噪声带
- **A4 同会话重测**：(i) 的 24 格把 A4 在同一会话按 E5 口径重测一次，报 T_M(v2) ÷ T_A4(本次)，与 (i) 用的 v1 A4 并排

**正确性闸**（不是判据；不过先查代码、不计时；`tests/run_tests.sh`）：(a) 合成小流对暴力、(c) 逐事件扫描代价对暴力、(a′) 真枚举——直接调用 E1 的脚本，臂配置表追加 B ∈ {1, 2}、c ∈ {0.001, 0.05, 0.1, 0.2} 的 M / A2，使窗格内切换在小流上真被走到；(v) 每个追加配置至少在一条流上发生窗格内切换；(b) 10 份真实切分每组前 2,000 个事件 × 全部 W × COUNT / SUM × 12 个臂配置与 OPP 逐窗口相等；(c′) 真实数据上始终索引、始终扫描、窗格内切换三者的逐事件扫描代价相等；(e) 每份真实数据全量上 v2 `--inpane 0` 与 v1 的校验和、切换、压缩次数逐项相同。跑时：每个重跑格 M / A2 的校验和等于同一行 OPP 的校验和（E5 里 OPP 跳过的格对 v1 的 M / A4 / A5）；E7 工作站上 gcc 编出的 v2 先过 (a)(c)(a′)(v) 再计时。

**描述性**（照报）：每格的窗格内切换次数与切换总数；用原实验的比较代码在 v2 的表上重出整份报表（`report_e1_v2.txt`、`report_e2_v2.txt`、`report_e5_v2.txt`、`report_e6_v2.txt`、`report_e7_v2.txt`），其中 E6 的尾延迟会多出窗格内切换那一次建树的停顿。
<!-- 协议结束 -->

用法：python3 -I exp/e8-inpane/compare_e8.py   → report_e8.txt，并用原实验的比较代码重出 report_e1_v2 / e2_v2 / e5_v2 / e6_v2 / e7_v2.txt
输入：handoff/*_v2.tsv（merge_e8.py 拼出）、handoff/e8_opp_check.tsv、handoff/e5_a4_recheck.tsv、handoff/e8_inpane.tsv；v1 的表在各实验的 handoff/。
环境变量 E8_HANDOFF 可改读别的目录（桩测：把 v1 的表拷成 *_v2.tsv，判读应与 v1 相同、回归比值全是 1）。
"""
import contextlib, os, statistics, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
for d in ("e1-main", "e2-sweep", "e4-lowfreq", "e5-synth", "e6-latency", "e7-platform"):
    p = os.path.join(EXP, d)
    if p not in sys.path:
        sys.path.insert(0, p)
import compare_e1 as c1  # noqa: E402
import compare_e2 as c2  # noqa: E402
import compare_e4 as c4  # noqa: E402
import compare_e5 as c5  # noqa: E402
import compare_e6 as c6  # noqa: E402
import compare_e7 as c7  # noqa: E402

H = os.environ.get("E8_HANDOFF", os.path.join(HERE, "handoff"))
j = os.path.join
V1 = {"e1": j(EXP, "e1-main", "handoff", "e1_times.tsv"), "rerun": j(EXP, "e1-main", "handoff", "e1_rerun_binance.tsv"),
      "e2": j(EXP, "e2-sweep", "handoff", "e2_times.tsv"), "e5": j(EXP, "e5-synth", "handoff", "e5_times.tsv"),
      "e6": j(EXP, "e6-latency", "handoff", "e6_latency.tsv"), "e6d": j(EXP, "e6-latency", "handoff", "e6_dist.tsv"),
      "e7": j(EXP, "e7-platform", "handoff", "e7_times.tsv"), "e7m": j(EXP, "e7-platform", "relay", "platform_machine.txt")}
V2 = {"e1": j(H, "e1_times_v2.tsv"), "rerun": j(H, "e1_rerun_binance_v2.tsv"), "e2": j(H, "e2_times_v2.tsv"), "e5": j(H, "e5_times_v2.tsv"),
      "e6": j(H, "e6_latency_v2.tsv"), "e6d": j(H, "e6_dist_v2.tsv"), "e7": j(H, "e7_times_v2.tsv"), "e7m": j(HERE, "relay", "e7v2_machine.txt")}
HAVE = {k: os.path.exists(v) for k, v in V2.items()}
RERUN_ARMS = {"e1": ("M", "A2"), "e2": ("M",), "e5": ("M",), "e6": ("M", "A2"), "e7": ("M",)}


def protocol_same():
    me = open(os.path.abspath(__file__), encoding="utf-8").read()
    rd = open(j(HERE, "README.md"), encoding="utf-8").read()
    cut = lambda s: s[s.index("<!-- 协议开始 -->"):s.index("<!-- 协议结束 -->")]
    return cut(me) == cut(rd)


@contextlib.contextmanager
def redirect(mod, pathmap, write_to):
    """在原实验的比较代码里把 v1 的表换成 v2 的（compare_e1.read_tsv 与该模块的 open），写报表改写到 write_to，print 静音。"""
    rmap = {os.path.realpath(a): b for a, b in pathmap.items()}
    real_read = c1.read_tsv

    def rd(path):
        return real_read(rmap.get(os.path.realpath(path), path))

    def op(path, mode="r", *a, **k):
        if "w" in mode:
            return open(write_to, mode, *a, **k)
        return open(rmap.get(os.path.realpath(path), path), mode, *a, **k)

    c1.read_tsv = rd
    mod.open = op
    mod.print = lambda *a, **k: None
    try:
        yield
    finally:
        c1.read_tsv = real_read
        del mod.open
        del mod.print


def vmap():
    return {V1[k]: V2[k] for k in V1 if HAVE.get(k)}


def section(txt, head):
    """报表里从以 head 开头的行到下一个 ## 标题之前。"""
    L = txt.splitlines()
    i = next((n for n, l in enumerate(L) if l.startswith(head)), None)
    if i is None:
        return []
    k = next((n for n in range(i + 1, len(L)) if L[n].startswith("## ")), len(L))
    return [l for l in L[i:k] if l.strip()]


def rng(v):
    if not v:
        return "（无）"
    return "中位 %.3f、范围 %.3f–%.3f（%d 格）" % (statistics.median(v), min(v), max(v), len(v))


# ---------------------------------------------------------------- E5：每格每臂的时间 = 各计时遍的中位（compare_e5 同口径）
def e5_times(path):
    rows = c1.read_tsv(path)
    per = defaultdict(list)
    info = {}
    for r in rows:
        if r["mode"] == "skip":
            continue
        k = (r["set"], r["dist"], int(r["n"]), int(r["G"]), r["burst"], int(r["k"]), r["arm"])
        per[k].append(float(r["seconds"]))
        info[k] = r
    return {k: statistics.median(v) for k, v in per.items()}, info


def judge_i(L):
    L.append("## (i) 修法成功：E5 S1 n ∈ {10⁵, 10⁶} 的 24 格，每格 T_M(v2) ÷ T_A4(v1 表) ≤ 1.5")
    if not HAVE["e5"]:
        L.append("没有 handoff/e5_times_v2.tsv ⇒ 未判"); return
    t2, _ = e5_times(V2["e5"])
    t1, _ = e5_times(V1["e5"])
    rc = j(H, "e5_a4_recheck.tsv")
    ta = e5_times(rc)[0] if os.path.exists(rc) else {}
    L.append("分布\tn\tk\tT_M v1\tT_M v2\tT_A4 v1\tM v2 ÷ A4 v1\tM v1 ÷ A4 v1\tT_A4 同会话\tM v2 ÷ A4 同会话")
    bad, qs = [], []
    for d in ("u", "rw", "ht"):
        for n in (100000, 1000000):
            for k in (1, 2, 6, 30):
                key = ("S1", d, n, 1, "0", k)
                m2, m1, a4 = t2.get(key + ("M",)), t1.get(key + ("M",)), t1.get(key + ("A4",))
                a4s = ta.get(key + ("A4",))
                if m2 is None or a4 is None:
                    L.append("%s\t%d\t%d\t缺数" % (d, n, k)); bad.append((d, n, k, None)); continue
                q = m2 / a4
                qs.append(q)
                if q > 1.5:
                    bad.append((d, n, k, q))
                L.append("%s\t%d\t%d\t%.3f\t%.3f\t%.3f\t%.3f\t%s\t%s\t%s" % (d, n, k, m1, m2, a4, q, "%.2f" % (m1 / a4) if m1 else "-",
                         "%.3f" % a4s if a4s else "-", "%.3f" % (m2 / a4s) if a4s else "-"))
    L.append("T_M(v2) ÷ T_A4(v1)：%s" % rng(qs))
    if bad:
        L.append("⇒ 修法不成功：%d 格超线或缺数：%s" % (len(bad), "、".join("%s n=%d k=%d %s" % (d, n, k, "缺数" if q is None else "%.3f" % q) for d, n, k, q in bad)))
    else:
        L.append("⇒ 24 格都 ≤ 1.5：修法成功")


def judge_ii(L):
    L.append("")
    L.append("## (ii) 重判（线一字不改；原实验的比较代码分别读 v1 与 v2 的表）")
    if HAVE["e1"]:
        for tag, path in (("v1", V1["e1"]), ("v2", V2["e1"])):
            L.append("### E1（%s：%s）" % (tag, os.path.relpath(path, EXP)))
            L += [l for l in c1.judge(c1.Times(path)) if not l.startswith("##")]
        for tag, mp in (("v1", {}), ("v2", vmap())):
            with redirect(c4, mp, j(HERE, "logs", "_e4.txt")):
                ls = c4.hold()
            L.append("### E4 K2'（%s）" % tag)
            L += [l for l in ls[1:] if l.startswith("K2'") or l.startswith("二值")]
    else:
        L.append("没有 handoff/e1_times_v2.tsv ⇒ E1 K1 / K3、E4 K2' 未判")
    if HAVE["e2"]:
        for tag, mp, out in (("v1", {}, j(HERE, "logs", "_e2_v1.txt")), ("v2", vmap(), j(HERE, "report_e2_v2.txt"))):
            with redirect(c2, mp, out):
                c2.main()
            L.append("### E2 K4（%s）" % tag)
            L += section(open(out, encoding="utf-8").read(), "## 判读 K4")[1:]
    else:
        L.append("没有 handoff/e2_times_v2.tsv ⇒ E2 K4 未判")


def regress(L):
    L.append("")
    L.append("## (iii) 回归检查：逐格 T(v2) ÷ T(v1)（只报、不判）")
    for ex, key_extra in (("e1", ()), ("e2", ("xnum",)), ("e7", ())):
        if not HAVE[ex]:
            L.append("%s：没有 v2 表" % ex.upper()); continue
        a, b = c1.Times(V1[ex], key_extra), c1.Times(V2[ex], key_extra)
        for arm in RERUN_ARMS[ex]:
            q = [b.T[k] / a.T[k] for k in b.T if k[0] == arm and k in a.T]
            L.append("%s %s：%s" % (ex.upper(), arm, rng(q)))
            if ex == "e1":
                for grp, ds in (("高频留出", c1.HIGH), ("中低频", c1.LOW)):
                    q = [b.T[k] / a.T[k] for k in b.T if k[0] == arm and k in a.T and k[1] in ds and k[2] == "hold"]
                    L.append("  %s：%s" % (grp, rng(q)))
                q = [b.T[k] / a.T[k] for k in b.T if k[0] == arm and k in a.T and k[1] == "binance"]
                L.append("  其中 Binance（唯一有窗格 ≥ B 的真实数据）：%s" % rng(q))
    if HAVE["e5"]:
        t1, _ = e5_times(V1["e5"]); t2, _ = e5_times(V2["e5"])
        fired = inpane_cells("e5")
        q1 = [t2[k] / t1[k] for k in t2 if k[-1] == "M" and k in t1 and fired.get(cell5(k), 0) > 0]
        q0 = [t2[k] / t1[k] for k in t2 if k[-1] == "M" and k in t1 and fired.get(cell5(k), 0) == 0]
        L.append("E5 M：窗格内检查触发过的格 %s；没触发的格 %s" % (rng(q1), rng(q0)))
    if HAVE["e6"]:
        def sec6(p):
            per = defaultdict(list)
            for r in c1.read_tsv(p):
                per[(r["arm"], r["data"])].append(float(r["seconds"]))
            return {k: statistics.median(v) for k, v in per.items()}
        a, b = sec6(V1["e6"]), sec6(V2["e6"])
        for arm in ("M", "A2"):
            L.append("E6 %s（逐事件计时那几遍的整流秒数，各遍中位）：%s" % (arm, "；".join(
                "%s %.3f" % (k[1], b[k] / a[k]) for k in sorted(b) if k[0] == arm and k in a)))


def cell5(k):
    return "%s %s-n%d-g%d-b%s k=%d" % (k[0], k[1], k[2], k[3], k[4], k[5])


def inpane_cells(ex):
    """handoff/e8_inpane.tsv：每个 (实验, 行) 的 M 窗格内切换次数（各进程取最大）。"""
    p = j(H, "e8_inpane.tsv")
    res = {}
    if os.path.exists(p):
        for r in c1.read_tsv(p):
            if r["exp"] == ex and r["arm"] == "M":
                res[r["row"]] = max(res.get(r["row"], 0), int(r["inpane_switches"] or 0))
    return res


def checksums(L):
    L.append("")
    L.append("## 正确性：每个重跑格的校验和对 v1（E1 / E2 / E7 对同一行 OPP；E5 对同一格 v1 各臂；E6 对同一行 OPP）")
    for ex, key_extra in (("e1", ()), ("e2", ("xnum",)), ("e7", ())):
        if not HAVE[ex]:
            continue
        a, b = c1.Times(V1[ex], key_extra), c1.Times(V2[ex], key_extra)
        n = bad = 0
        for k in b.T:
            if k[0] in RERUN_ARMS[ex]:
                n += 1
                ref = a.info.get(("OPP",) + k[1:], {}).get("checksum", set())
                if b.info[k]["checksum"] != ref or len(ref) != 1:
                    bad += 1; L.append("  不一致：%s %s" % (ex, k))
        L.append("%s：%d 个 (臂 × 行)，不一致 %d" % (ex.upper(), n, bad))
    if HAVE["e5"]:
        _, i1 = e5_times(V1["e5"]); _, i2 = e5_times(V2["e5"])
        ref = defaultdict(set)
        for k, r in i1.items():
            ref[k[:-1]].add(r["checksum"])
        n = bad = 0
        for k, r in i2.items():
            if k[-1] == "M":
                n += 1
                if ref.get(k[:-1]) != {r["checksum"]}:
                    bad += 1; L.append("  不一致：E5 %s" % cell5(k))
        L.append("E5：%d 格，不一致 %d" % (n, bad))
    if HAVE["e6"]:
        r1 = {(r["arm"], r["data"]): r["checksum"] for r in c1.read_tsv(V1["e6"])}
        rows = [r for r in c1.read_tsv(V2["e6"]) if r["arm"] in ("M", "A2")]
        bad = [r for r in rows if r["checksum"] != r1.get(("OPP", r["data"]))]
        L.append("E6：%d 个计时遍，不一致 %d" % (len(rows), len(bad)))


def side(L):
    L.append("")
    L.append("## 旁证（只报、不判）")
    p = j(H, "e8_opp_check.tsv")
    if os.path.exists(p):
        a, b = c1.Times(V1["e1"]), c1.Times(p)
        L.append("OPP 旁证（v2 二进制按 E1 口径重测）：数据\tT_OPP v1\t带 v1\tT_OPP 本次\t带 本次\t本次 ÷ v1")
        for k in sorted(b.T):
            L.append("  %s\t%.4f\t%s\t%.4f\t%s\t%.3f" % (k[1], a.T[k], c1.fb(a.band(k)), b.T[k], c1.fb(b.band(k)), b.T[k] / a.T[k]))
    else:
        L.append("没有 handoff/e8_opp_check.tsv")
    L.append("A4 同会话重测：见 (i) 表最后两列")
    p = j(H, "e8_inpane.tsv")
    if os.path.exists(p):
        L.append("")
        L.append("## 窗格内切换（每个 (实验, 行, 臂) 各进程取最大；只列触发过的）")
        mx = {}
        for r in c1.read_tsv(p):
            k = (r["exp"], r["row"], r["arm"])
            v = (int(r["inpane_switches"] or 0), int(r["switches"] or 0))
            mx[k] = max(mx.get(k, (0, 0)), v)
        for ex in ("e1", "e2", "e5", "e6", "e7"):
            ks = [k for k in mx if k[0] == ex]
            hit = [k for k in ks if mx[k][0] > 0]
            L.append("%s：%d 个 (行 × 臂) 里触发过 %d 个" % (ex.upper(), len(ks), len(hit)))
            for k in sorted(hit):
                L.append("  %s %s：窗格内切换 %d、切换总数 %d" % (k[1], k[2], mx[k][0], mx[k][1]))


def full_reports(L):
    """用原实验的比较代码在 v2 的表上重出整份报表。"""
    out = []
    if HAVE["e1"]:
        with redirect(c1, vmap(), j(HERE, "report_e1_v2.txt")):
            c1.main()
        out.append("report_e1_v2.txt")
    if HAVE["e2"]:
        out.append("report_e2_v2.txt")  # judge_ii 里已重出
    if HAVE["e5"]:
        c5.print = lambda *a, **k: None
        c5.main(V2["e5"], j(HERE, "report_e5_v2.txt"))
        del c5.print
        out.append("report_e5_v2.txt")
    if HAVE["e6"] and HAVE["e6d"]:
        c6.print = lambda *a, **k: None
        c6.main(V2["e6"], V2["e6d"], j(HERE, "report_e6_v2.txt"))
        del c6.print
        out.append("report_e6_v2.txt")
    if HAVE["e7"]:
        with redirect(c7, vmap(), j(HERE, "report_e7_v2.txt")):
            c7.main()
        out.append("report_e7_v2.txt")
    L.append("")
    L.append("## 用原实验的比较代码在 v2 表上重出的整份报表：%s" % ("、".join(out) or "无"))


def main():
    ok = protocol_same()
    L = ["# E8 · 选择器的窗格内检查（compare_e8.py）", "协议同文自检：%s" % ("一致" if ok else "不一致！"),
         "v2 的表：%s" % "、".join("%s %s" % (k, "有" if v else "缺") for k, v in HAVE.items())]
    if not ok:
        print("\n".join(L)); sys.exit(1)
    os.makedirs(j(HERE, "logs"), exist_ok=True)
    L.append("")
    judge_i(L)
    judge_ii(L)
    regress(L)
    checksums(L)
    side(L)
    full_reports(L)
    txt = "\n".join(L) + "\n"
    open(j(HERE, "report_e8.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
