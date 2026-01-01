"""E5 · 合成流生成器（README 第 1 节「流」）。纯标准库、种子由流名定（zlib.crc32），同名同流、逐字节可复现。

流名 <分布>-n<每组每窗事件数>-g<组数>-b<0|1>，例如 rw-n1000-g10-b1。
- 窗口 W = 600 s 固定（时间整数微秒）；查询的 k = W ÷ s 由 run_e5.sh 选，与流无关
- 到达：全流一个泊松过程，速率 G·λ(t)，每个事件均匀随机分给一组（等价于 G 个独立的泊松流）；λ = n ÷ W
- 突发（b1）：每 10 W 为一个周期，周期内 [5 W, 6 W) 速率乘 10（占时长 10%）；分段常速率，跨段时从段界按新速率重抽（无记忆性，精确）
- 时长 H 个窗口：H = max(10, ⌈10⁶ ÷ (n·G)⌉)（n 是基础速率下的数，b1 与同名 b0 的 H 相同；突发组 n ≤ 10³ 的 H 都 ≥ 100、是 10 的倍数，至少 10 个周期）；流从时间 0 开始
- 属性（每组各自一条序列）：
    u   均匀：a ~ U{0, …, 10⁹ − 1}，独立同分布
    rw  随机游走：a₀ = 10⁹，步长 ⌊(2U − 1)·1000⌋（U ~ U[0, 1)）
    ht  重尾随机游走：a₀ = 10⁹，步长 ±⌊1000·(U^(−1/1.5) − 1)⌋，符号等概率（Pareto α = 1.5，方差无穷）
  比较谓词只看大小次序，独立同分布的重尾值与均匀值的次序过程相同 ⇒ 「重尾」放在随机游走的步长上（价格跳变）

用法：python3 -I gen_e5.py <流名> <输出 tsv>       → 写「组 \t 时间 µs \t 属性」，stderr 一行：事件数、组数、H、按滚动窗口数的每组每窗事件中位
"""
import math, random, statistics, sys, zlib

W_US = 600 * 1000 * 1000


def parse(name):
    d, n, g, b = name.split("-")
    assert d in ("u", "rw", "ht") and n[0] == "n" and g[0] == "g" and b in ("b0", "b1"), name
    return d, int(n[1:]), int(g[1:]), b == "b1"


def horizon(n, G):
    return max(10, math.ceil(1e6 / (n * G)))


def gen(name, out):
    dist, n, G, burst = parse(name)
    H = horizon(n, G)
    rnd = random.Random(zlib.crc32(name.encode()))
    T = H * W_US
    lam = n * G / W_US                        # 全流基础速率（事件 / µs）
    state = [1000 * 1000 * 1000] * G
    cnt = {}
    t = 0.0
    nev = 0
    rr = rnd.random
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        buf = []
        while True:
            if burst:
                cyc = t % (10 * W_US)
                hot = 5 * W_US <= cyc < 6 * W_US
                rate = lam * (10 if hot else 1)
                seg_end = t - cyc + (6 * W_US if hot else (5 * W_US if cyc < 5 * W_US else 15 * W_US))
                nt = t + rnd.expovariate(rate)
                if nt >= seg_end:      # 跨段：从段界按新速率重抽
                    t = seg_end
                    if t >= T:
                        break
                    continue
                t = nt
            else:
                t += rnd.expovariate(lam)
            if t >= T:
                break
            g = int(rr() * G) if G > 1 else 0
            if dist == "u":
                a = int(rr() * 1e9)
            elif dist == "rw":
                state[g] += int((2 * rr() - 1) * 1000)
                a = state[g]
            else:
                u = 1.0 - rr()                 # (0, 1]
                step = int(1000 * (u ** (-1 / 1.5) - 1))
                state[g] += step if rr() < 0.5 else -step
                a = state[g]
            ti = int(t)
            buf.append("g%d\t%d\t%d\n" % (g, ti, a))
            key = (g, ti // W_US)
            cnt[key] = cnt.get(key, 0) + 1
            nev += 1
            if len(buf) >= 65536:
                f.write("".join(buf))
                buf.clear()
        f.write("".join(buf))
    med = statistics.median([cnt.get((g, h), 0) for g in range(G) for h in range(H)])
    sys.stderr.write("%s\tevents=%d\tgroups=%d\tH=%d\tmed_per_window=%g\n" % (name, nev, G, H, med))


if __name__ == "__main__":
    gen(sys.argv[1], sys.argv[2])
