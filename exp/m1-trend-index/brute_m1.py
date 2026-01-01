"""M1 · 按定义的暴力真值与正确性闸 (a)（README 第 2.6 节）。纯标准库、Python 大整数再取模 2⁶⁴。

用法：python3 -I brute_m1.py brute <tsv> <W> <s> <op> <COUNT|SUM>   → stdout「组 \t 窗口 \t 值」（按组、窗口排序）
      python3 -I brute_m1.py gate <二进制> [个数]                      → 闸 (a)：合成小流 × 全部臂逐窗口对暴力；错一项退出码 1
时间、W、s 同一单位（整数）；窗口 j 覆盖 [j·s, j·s + W)，时间已以最早为 0。
"""
import os, random, subprocess, sys, tempfile

MOD = 1 << 64


def load(path):
    groups = {}
    for line in open(path, encoding="utf-8"):
        g, t, a = line.rstrip("\n").split("\t")
        groups.setdefault(g, []).append((int(t), int(a)))
    return groups


def brute(groups, W, s, op, agg):
    """每个组、每个含事件的窗口：c(e) = 1 + Σ_{先到、满足 ⋈ 的 p} c(p)，sum(e) = a_e·c(e) + Σ sum(p)。"""
    out = []
    for g in sorted(groups):
        ev = groups[g]
        js = set()
        for t, _ in ev:
            js.update(range((t - W) // s + 1, t // s + 1))
        for j in sorted(js):
            inw = [a for t, a in ev if j * s <= t < j * s + W]
            cs, ss = [], []
            for i, a in enumerate(inw):
                c, sm = 1, 0
                for q in range(i):
                    if (inw[q] > a) if op == ">" else (inw[q] < a):
                        c += cs[q]
                        sm += ss[q]
                cs.append(c)
                ss.append(a * c + sm)
            out.append((g, j, (sum(cs) if agg == "COUNT" else sum(ss)) % MOD))
    return out


def fmt(rows):
    return "".join("%s\t%d\t%d\n" % r for r in rows)


def synth(rnd):
    """每组 ≤ 60 个事件、随机 W / s / ⋈、属性值域小（制造重复值）、时间可重复也可有长空档。"""
    s = rnd.choice([1, 2, 3, 5, 10])
    k = rnd.choice([1, 2, 3, 4, 5, 8, 10])
    op = rnd.choice(["<", ">"])
    span = rnd.choice([20, 60, 200, 600])
    dom = rnd.choice([2, 3, 5, 10, 1000])
    lines = []
    for gi in range(rnd.randint(1, 4)):
        n = rnd.randint(1, 60)
        ts = sorted(rnd.randrange(span) for _ in range(n))
        if rnd.random() < 0.3:  # 长空档：跨越多个空窗格
            cut = rnd.randrange(n)
            ts = ts[:cut] + [t + 5 * k * s for t in ts[cut:]]
        lo = rnd.choice([0, -dom // 2])
        for t in ts:
            lines.append("g%d\t%d\t%d\n" % (gi, t, rnd.randint(lo, lo + dom)))
    return "".join(lines), k * s, s, op


ARMS = [("OPP", []), ("OPP", ["--opp-index", "map"]), ("A1", []), ("A4", [])] + \
       [("M", ["--tau", str(t)]) for t in (1, 2, 3, 8, 64)]


def gate(binary, n):
    rnd = random.Random(1971)
    bad = checks = 0
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "s.tsv")
        for it in range(n):
            text, W, s, op = synth(rnd)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            groups = load(path)
            for agg in ("COUNT", "SUM"):
                want = fmt(brute(groups, W, s, op, agg))
                for arm, extra in ARMS:
                    cmd = [binary, "--arm", arm, "--data", path, "--W", str(W), "--s", str(s), "--op", op,
                           "--agg", agg, "--reps", "1", "--warmup", "0", "--dump", "-"] + extra
                    got = subprocess.run(cmd, capture_output=True, text=True)
                    checks += 1
                    dump = "".join(l + "\n" for l in got.stdout.splitlines() if not l.startswith("#"))
                    if got.returncode != 0 or dump != want:
                        bad += 1
                        if bad <= 3:
                            print("不一致：第 %d 条 %s %s %s W=%d s=%d op=%s\n%s" % (it, arm, " ".join(extra), agg, W, s, op, got.stderr[-500:]))
                            keep = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "gate_fail_%d.tsv" % it)
                            os.makedirs(os.path.dirname(keep), exist_ok=True)
                            with open(keep, "w", encoding="utf-8") as f:
                                f.write(text)
    print("闸 (a)：%d 条合成流、%d 项核对，错误 %d" % (n, checks, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1] == "brute":
        _, _, p, W, s, op, agg = sys.argv
        sys.stdout.write(fmt(brute(load(p), int(W), int(s), op, agg)))
    elif sys.argv[1] == "gate":
        sys.exit(gate(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 300))
