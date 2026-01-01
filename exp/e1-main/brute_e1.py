"""E1 · 正确性闸 (a)(c)（README 第 1 节「正确性闸」）。纯标准库；合成流、暴力真值的格式沿用 M1（import `../m1-trend-index/brute_m1.py`）。

用法：python3 -I brute_e1.py gate <二进制> [个数]   → 闸 (a) 合成小流 × 全部臂配置逐窗口对暴力；闸 (c) 逐事件扫描代价对暴力。错一项退出码 1
加在 M1 之上的：E2 的选择度谓词 a_p · X ⋈ a_e · 1000（每三条流一条取 X ≠ 1）；E4 规则输入「按 OPP 处理事件 e 的窗口累加次数」
= Σ_{先到、合格的 p} |p 与 e 的共同窗口|，共同窗口 = [π_e − k + 1, π_p]（M1 第 2.1 节）。
"""
import os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "m1-trend-index"))
import brute_m1 as m1  # noqa: E402

MOD = m1.MOD


def ok(ap, ae, op, xnum):
    return ap * xnum > ae * 1000 if op == ">" else ap * xnum < ae * 1000


def brute(groups, W, s, op, agg, xnum):
    """同 M1 的 brute，谓词换成 a_p · X ⋈ a_e · 1000（X = xnum / 1000）。"""
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
                    if ok(inw[q], a, op, xnum):
                        c += cs[q]
                        sm += ss[q]
                cs.append(c)
                ss.append(a * c + sm)
            out.append((g, j, (sum(cs) if agg == "COUNT" else sum(ss)) % MOD))
    return out


def costs(groups, W, s, op, xnum):
    """每组逐事件（到达序）的扫描代价。"""
    k = W // s
    res = {}
    for g, ev in groups.items():
        v = []
        for i, (te, ae) in enumerate(ev):
            pe = te // s
            tot = 0
            for tp, ap in ev[:i]:
                pp = tp // s
                if pp >= pe - k + 1 and ok(ap, ae, op, xnum):
                    tot += pp - pe + k
            v.append(tot)
        res[g] = v
    return res


# 臂配置：c 取极小 / 极大保证两种模式与两个方向的切换都走到；τ 小的 A5 每条流都会切换
ARMS = [("OPP", []), ("OPP", ["--opp-index", "map"]), ("A1", []), ("A4", []),
        ("A5", []), ("A5", ["--tau", "1"]), ("A5", ["--tau", "3"]),
        ("M", ["--c", "0.001"]), ("M", ["--c", "1"]), ("M", ["--c", "1e9"]),
        ("A2", ["--c", "0.001"]), ("A2", ["--c", "1"]), ("A4", ["--expire", "delete"]), ("A5", ["--tau", "2", "--expire", "delete"])]
TRACE_ARMS = [("M", ["--c", "0.001"]), ("M", ["--c", "1e9"]), ("M", ["--c", "1"]), ("A4", []), ("A2", ["--c", "0.001"]), ("A5", ["--tau", "1"])]


def gate(binary, n):
    rnd = random.Random(1971)      # 与 M1 同一串合成流
    rx = random.Random(2027)       # X 的取法另用一个种子
    bad = checks = cbad = cchecks = 0
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "s.tsv")
        tpath = os.path.join(td, "t.tsv")
        for it in range(n):
            text, W, s, op = m1.synth(rnd)
            xnum = rx.choice([900, 950, 990, 1010, 1050, 1100]) if it % 3 == 2 else 1000
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            groups = m1.load(path)
            arms = [a for a in ARMS if not (xnum != 1000 and a[0] == "A1")]
            base = [binary, "--data", path, "--W", str(W), "--s", str(s), "--op", op, "--xnum", str(xnum)]
            for agg in ("COUNT", "SUM"):
                want = m1.fmt(brute(groups, W, s, op, agg, xnum))
                for arm, extra in arms:
                    cmd = base + ["--arm", arm, "--agg", agg, "--reps", "1", "--warmup", "0", "--dump", "-"] + extra
                    got = subprocess.run(cmd, capture_output=True, text=True)
                    checks += 1
                    if got.returncode != 0 or got.stdout != want:
                        bad += 1
                        if bad <= 3:
                            print("不一致 (a)：第 %d 条 %s %s %s W=%d s=%d op=%s X=%d\n%s" % (it, arm, " ".join(extra), agg, W, s, op, xnum, got.stderr[-500:]))
                            keep = os.path.join(HERE, "out", "gate_fail_%d.tsv" % it)
                            os.makedirs(os.path.dirname(keep), exist_ok=True)
                            with open(keep, "w", encoding="utf-8") as f:
                                f.write(text)
            want_c = costs(groups, W, s, op, xnum)
            for arm, extra in TRACE_ARMS:
                cmd = base + ["--arm", arm, "--agg", "COUNT", "--reps", "1", "--warmup", "0", "--work", "--trace", tpath] + extra
                got = subprocess.run(cmd, capture_output=True, text=True)
                cchecks += 1
                tr = {}
                if got.returncode == 0:
                    for line in open(tpath, encoding="utf-8"):
                        g, v = line.rstrip("\n").split("\t")
                        tr.setdefault(g, []).append(int(v))
                if got.returncode != 0 or tr != want_c:
                    cbad += 1
                    if cbad <= 3:
                        print("不一致 (c)：第 %d 条 %s %s W=%d s=%d op=%s X=%d" % (it, arm, " ".join(extra), W, s, op, xnum))
    print("闸 (a)：%d 条合成流（其中 X ≠ 1 的 %d 条）、%d 项核对，错误 %d" % (n, n // 3, checks, bad))
    print("闸 (c)：%d 条合成流 × %d 个臂配置 = %d 项逐事件核对扫描代价，错误 %d" % (n, len(TRACE_ARMS), cchecks, cbad))
    return 1 if bad or cbad else 0


if __name__ == "__main__":
    if sys.argv[1] == "gate":
        sys.exit(gate(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 300))
