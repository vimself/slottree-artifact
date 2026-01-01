"""E1 · 闸 (a′)：真枚举对拍（补充实验 ②，README 第 3 节「闸」(a′)）。纯标准库，Python 大整数再取模 2⁶⁴。

闸 (a) 的「暴力」（`../m1-trend-index/brute_m1.py`）其实是按定义写的递推 c(e) = 1 + Σ c(p)；这里不用递推，
直接按 skip-till-any-match 的定义把每个窗口里的全部趋势一条条列出来：窗口内的事件按到达序（时间不减、同一时刻按文件顺序，
与引擎和 M1 的语义相同）排好，**每个非空子序列**都试一遍，相邻两个事件都满足 E.a ⋈ NEXT(E).a 的算一条趋势；
COUNT = 趋势条数，SUM = 全部趋势里事件属性之和；两者都取模 2⁶⁴。

流：每组 n ≤ 15 个事件（窗口里至多 15 个，子序列至多 2¹⁵ − 1 个），1–3 组，随机 W = k·s、⋈、属性值域
（小值域制造重复值，含负数；另有 ±2⁶² 量级的大值让 SUM 取模回绕）、时间可重复也可有跨多个窗格的空档。种子固定。

核对顺序：① 枚举 = 递推（brute_m1.brute）；② 枚举 = 引擎各臂配置的逐窗口输出（`--dump -`）。
臂配置：E1 的六个臂按 E1 参数（M、A2 取 c = 2，A5 取 τ = 16），另加三个强制走索引与来回切换的配置
（M、A2 取 c = 0.001，A5 取 τ = 1）——小流上 E1 参数的 M 很少进索引模式。

用法：python3 -I exp/e1-main/tests/brute_enum.py <二进制> [流数 = 300]   → 打印项数与错误数；错一项退出码 1
"""
import itertools, os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
M1D = os.path.join(HERE, "..", "..", "m1-trend-index")
if M1D not in sys.path:
    sys.path.insert(0, M1D)
import brute_m1 as m1  # noqa: E402

MOD = 1 << 64
NMAX = 15
SEED = 20261108
CONFS = [("OPP", []), ("M", ["--c", "2"]), ("A1", []), ("A2", ["--c", "2"]), ("A4", []), ("A5", ["--tau", "16"]),
         ("M", ["--c", "0.001"]), ("A2", ["--c", "0.001"]), ("A5", ["--tau", "1"])]


def enum_window(av, op):
    """av：窗口内按到达序的属性。返回 (趋势条数, 属性和, 试过的子序列数)。不取模，调用方取。"""
    m = len(av)
    cnt = tot = tried = 0
    ok = (lambda x, y: x > y) if op == ">" else (lambda x, y: x < y)
    for size in range(1, m + 1):
        for idx in itertools.combinations(range(m), size):
            tried += 1
            if all(ok(av[idx[i]], av[idx[i + 1]]) for i in range(size - 1)):
                cnt += 1
                tot += sum(av[i] for i in idx)
    return cnt, tot, tried


def enum(groups, W, s, op, stats):
    """每个组、每个含事件的窗口（与 brute_m1 同一组窗口）→ [(组, 窗口, COUNT, SUM)]，都已取模。"""
    out = []
    cache = {}
    for g in sorted(groups):
        ev = groups[g]
        js = set()
        for t, _ in ev:
            js.update(range((t - W) // s + 1, t // s + 1))
        for j in sorted(js):
            av = tuple(a for t, a in ev if j * s <= t < j * s + W)
            if av not in cache:
                cache[av] = enum_window(av, op)
                stats["tried"] += cache[av][2]
            c, sm, _ = cache[av]
            stats["windows"] += 1
            stats["trends"] += c
            out.append((g, j, c % MOD, sm % MOD))
    return out


def synth(rnd):
    s = rnd.choice([1, 2, 3, 5, 10])
    k = rnd.choice([1, 2, 3, 4, 5, 8])
    op = rnd.choice(["<", ">"])
    span = rnd.choice([10, 30, 100, 300])
    dom = rnd.choice([2, 3, 5, 10, 1000, 1 << 62])
    lines = []
    for gi in range(rnd.randint(1, 3)):
        n = rnd.randint(1, NMAX)
        ts = sorted(rnd.randrange(span) for _ in range(n))
        if rnd.random() < 0.3:  # 长空档：跨越多个空窗格
            cut = rnd.randrange(n)
            ts = ts[:cut] + [t + 5 * k * s for t in ts[cut:]]
        lo = rnd.choice([0, -dom // 2])
        for t in ts:
            lines.append("g%d\t%d\t%d\n" % (gi, t, rnd.randint(lo, lo + dom)))
    return "".join(lines), k * s, s, op


def main(binary, n):
    rnd = random.Random(SEED)
    stats = {"windows": 0, "trends": 0, "tried": 0}
    rec_items = rec_bad = arm_items = arm_bad = 0
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "s.tsv")
        for it in range(n):
            text, W, s, op = synth(rnd)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            groups = m1.load(path)
            rows = enum(groups, W, s, op, stats)
            for ai, agg in enumerate(("COUNT", "SUM")):
                want = m1.fmt([(g, j, v[ai]) for g, j, *v in rows])
                rec_items += 1
                if m1.fmt(m1.brute(groups, W, s, op, agg)) != want:
                    rec_bad += 1
                    print("枚举 ≠ 递推：第 %d 条 %s W=%d s=%d op=%s" % (it, agg, W, s, op))
                for arm, extra in CONFS:
                    cmd = [binary, "--arm", arm, "--data", path, "--W", str(W), "--s", str(s), "--op", op,
                           "--agg", agg, "--reps", "1", "--warmup", "0", "--dump", "-"] + extra
                    got = subprocess.run(cmd, capture_output=True, text=True)
                    arm_items += 1
                    if got.returncode != 0 or got.stdout != want:
                        arm_bad += 1
                        if arm_bad <= 3:
                            print("枚举 ≠ 引擎：第 %d 条 %s %s %s W=%d s=%d op=%s\n%s" % (it, arm, " ".join(extra), agg, W, s, op, got.stderr[-300:]))
    print("闸 (a′) 真枚举：%d 条合成流（每组 ≤ %d 个事件，种子 %d）、%d 个（组, 窗口）、枚举 %d 个子序列、其中趋势 %d 条"
          % (n, NMAX, SEED, stats["windows"], stats["tried"], stats["trends"]))
    print("  枚举 vs 递推（brute_m1）：%d 项（流 × COUNT / SUM），错误 %d" % (rec_items, rec_bad))
    print("  枚举 vs 引擎：%d 项（流 × COUNT / SUM × %d 个臂配置），错误 %d" % (arm_items, len(CONFS), arm_bad))
    return 1 if rec_bad or arm_bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 300))
