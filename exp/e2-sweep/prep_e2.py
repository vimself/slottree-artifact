"""E2 · 选择度扫的 X（README 第 1 节「选择度扫」）。纯标准库。

用法：python3 -I prep_e2.py [数据 …]   默认 wpi_hold pamap2_hold porto_hold binance_hold → handoff/e2_sel.tsv、handoff/e2_selcurve.tsv
谓词 a_p · X_num ⋈ a_e · 1000（X = X_num ÷ 1000），X_num ∈ {900, 905, …, 1100}。比例 = 同组、同一窗口（W = 10 分，窗口 j 覆盖
[j·s, j·s + W)）内先到的 p 与后到的 e 组成的事件对里满足谓词的占比，各窗口的对合在一起算（窗口滑动，同一对在它们共同的每个窗口里各算一次）。
每组每窗：对数 n(n−1)/2 ≤ 10⁴ 的窗口全取，否则无放回地均匀抽 10⁴ 对里的一对 × 10⁴ 次（有放回，种子固定 197）。
全取的小窗口按「对 × 它们共同所在的小窗口数」一次累加（与逐窗口枚举相同）；对每个目标 σ 取比例最接近的 X，并列时取离 1 近的、再取小的。
"""
import os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "e1-main"))
GRID = list(range(900, 1101, 5))
SIGMAS = [0.1, 0.3, 0.5, 0.7, 0.9]
CAP = 10000
W = 600
SPEC = {"wpi_hold": (">", 10), "pamap2_hold": ("<", 30), "porto_hold": ("<", 60), "binance_hold": (">", 10)}


def path_of(ds):
    d = ds.split("_")[0]
    if d in ("wpi", "pamap2"):
        return os.path.join(HERE, "..", "m1-trend-index", "data", ds + ".tsv")
    return os.path.join(HERE, "..", "e1-main", "data", ds + ".tsv")


def interval(ap, ae, gt):
    """满足谓词的 X_num 区间（网格下标的闭区间 [lo, hi]），没有则 None。"""
    num = 1000 * ae
    if ap == 0:
        ok = (0 > num) if gt else (0 < num)
        return (0, len(GRID) - 1) if ok else None
    # gt：ap·X > num；lt：ap·X < num。ap > 0 时 gt ⇔ X ≥ ⌊num/ap⌋ + 1，lt ⇔ X ≤ ⌈num/ap⌉ − 1；ap < 0 时方向反过来
    if (ap > 0) == gt:
        m = num // ap + 1                     # X ≥ m
        lo = max(0, -((900 - m) // 5))
        return (lo, len(GRID) - 1) if lo < len(GRID) else None
    M = -((-num) // ap) - 1                   # X ≤ M
    hi = min(len(GRID) - 1, (M - 900) // 5)
    return (0, hi) if hi >= 0 else None


def curve(ds):
    op, s = SPEC[ds]
    gt = op == ">"
    su = s * 1000000
    k = W // s
    groups = {}
    for line in open(path_of(ds), encoding="utf-8"):
        g, t, a = line.rstrip("\n").split("\t")
        groups.setdefault(g, []).append((int(t), int(a)))
    rnd = random.Random(197)
    diff = [0] * (len(GRID) + 1)
    total = 0
    nsmall = nlarge = 0
    for g in sorted(groups):
        ev = sorted(groups[g], key=lambda x: x[0])  # 稳定：同时间保持文件顺序
        P = [t // su for t, _ in ev]
        A = [a for _, a in ev]
        n = len(ev)
        # 含事件的窗口 j 与它的下标区间 [lo, hi)
        first = {}
        for i, p in enumerate(P):
            if p not in first:
                first[p] = i
        ps = sorted(first)
        import bisect
        wins = []
        last = None
        for p in ps:
            lo = p - k + 1 if last is None or p - k + 1 > last else last + 1
            wins.extend(range(lo, p + 1))
            last = p
        small = set()
        for j in wins:
            a = bisect.bisect_left(P, j)
            b = bisect.bisect_left(P, j + k)
            m = b - a
            if m < 2:
                continue
            if m * (m - 1) // 2 <= CAP:
                small.add(j)
                continue
            nlarge += 1
            for _ in range(CAP):  # 大窗口：均匀抽一对 (x < y)
                x = a + int(rnd.random() * m)
                y = a + int(rnd.random() * (m - 1))
                if y >= x:
                    y += 1
                else:
                    x, y = y, x
                iv = interval(A[x], A[y], gt)
                if iv:
                    diff[iv[0]] += 1
                    diff[iv[1] + 1] -= 1
            total += CAP
        nsmall += len(small)
        if not small:
            continue
        # 小窗口全取：对 (i < e) 的权重 = [π_e − k + 1, π_i] 里小窗口的个数
        sw = sorted(small)
        for e in range(n):
            pe = P[e]
            lo_j = pe - k + 1
            q = bisect.bisect_left(sw, lo_j)
            if q == len(sw) or sw[q] > pe:
                continue
            jstar = sw[q]
            i0 = bisect.bisect_left(P, jstar)
            ae = A[e]
            for i in range(i0, e):
                w = bisect.bisect_right(sw, P[i]) - q
                if w <= 0:
                    continue
                total += w
                iv = interval(A[i], ae, gt)
                if iv:
                    diff[iv[0]] += w
                    diff[iv[1] + 1] -= w
    cnt, run = [], 0
    for i in range(len(GRID)):
        run += diff[i]
        cnt.append(run)
    return [c / total for c in cnt], total, nsmall, nlarge


def main():
    dss = sys.argv[1:] or ["wpi_hold", "pamap2_hold", "porto_hold", "binance_hold"]
    os.makedirs(os.path.join(HERE, "handoff"), exist_ok=True)
    sel = ["data\tsigma\tX_num\tX\tfrac"]
    cur = ["data\tX_num\tfrac\tpairs\tsmall_windows\tlarge_windows"]
    for ds in dss:
        fr, total, ns, nl = curve(ds)
        d = ds.split("_")[0]
        for x, f in zip(GRID, fr):
            cur.append("%s\t%d\t%.6f\t%d\t%d\t%d" % (d, x, f, total, ns, nl))
        for sg in SIGMAS:
            best = min(range(len(GRID)), key=lambda i: (abs(fr[i] - sg), abs(GRID[i] - 1000), GRID[i]))
            sel.append("%s\t%.1f\t%d\t%.3f\t%.6f" % (d, sg, GRID[best], GRID[best] / 1000, fr[best]))
        print("%s：%d 对（全取的小窗口 %d 个、抽样的大窗口 %d 个）；X = 0.900 / 1.000 / 1.100 时比例 %.4f / %.4f / %.4f" % (
            ds, total, ns, nl, fr[0], fr[GRID.index(1000)], fr[-1]), flush=True)
    open(os.path.join(HERE, "handoff", "e2_sel.tsv"), "w", encoding="utf-8").write("\n".join(sel) + "\n")
    open(os.path.join(HERE, "handoff", "e2_selcurve.tsv"), "w", encoding="utf-8").write("\n".join(cur) + "\n")
    print("\n".join(sel))


if __name__ == "__main__":
    main()
