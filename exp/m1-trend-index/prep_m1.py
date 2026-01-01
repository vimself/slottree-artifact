"""M1 · T20 的四份 TSV → data/<名>_{dev,hold}.tsv（每行：组 \t 时间整数微秒 \t 整数属性），不改顺序。纯标准库。

用法：python3 -I prep_m1.py [<T20 data 目录>]   默认 ../t20-trend-headroom/data
      python3 -I prep_m1.py shape <每窗事件数 n> <选择度 σ> <输出 tsv>   对手校准的合成流（第 2.2 节第 5 条）
口径（README 第 2.1 节）：时间以整份数据的最早时间为 0、按十进制串精确换成微秒；
WPI 价格、Nasdaq 收盘价 × 100 四舍五入，PAMAP2 心率、公交延误四舍五入取整。
"""
import os, sys
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = {"wpi": 100, "pamap2": 1, "nasdaq": 100, "bus": 1}
DEV = {"wpi": {"AMAT", "CSCO", "DELL", "INTC", "IPIX"},
       "pamap2": {"subject101", "subject102", "subject103", "subject104"},
       "nasdaq": set(), "bus": set()}


def usec(s):  # "28802.520000" → 28802520000，不经浮点
    whole, _, frac = s.partition(".")
    frac = (frac + "000000")[:6]
    neg = whole.startswith("-")
    v = int(whole.lstrip("-") or "0") * 1000000 + int(frac)
    return -v if neg else v


def prep(src, name):
    rows = []
    for line in open(os.path.join(src, name + ".tsv"), encoding="utf-8"):
        g, t, a = line.rstrip("\n").split("\t")
        rows.append((g, usec(t), int((Decimal(a) * SCALE[name]).to_integral_value(ROUND_HALF_UP))))
    t0 = min(r[1] for r in rows)
    out = os.path.join(HERE, "data")
    os.makedirs(out, exist_ok=True)
    split = {"dev": [], "hold": []}
    for g, t, a in rows:
        split["dev" if g in DEV[name] else "hold"].append("%s\t%d\t%d\n" % (g, t - t0, a))
    for sp, lines in split.items():
        if not lines:
            continue
        with open(os.path.join(out, "%s_%s.tsv" % (name, sp)), "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("%s_%s：%d 个事件、%d 个组" % (name, sp, len(lines), len({l.split("\t", 1)[0] for l in lines})))


def shape(n, sel, path):
    """单组、W = 100 s、s = 10 s、共 1,000 s，每窗约 n 个事件、等间隔到达。⋈ 取 <：
    每个事件以概率 σ 为「升」（a = i，先到的全部合格）、否则为「降」（a = −i，没有合格前驱）⇒ 合格前驱占比的期望 = σ。"""
    import random
    rnd = random.Random(n * 1000 + int(sel * 100))
    total, dur = 10 * n, 1000 * 1000000
    with open(path, "w", encoding="utf-8") as f:
        for i in range(total):
            a = i + 1 if rnd.random() < sel else -(i + 1)
            f.write("s\t%d\t%d\n" % (i * dur // total, a))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "shape":
        shape(int(sys.argv[2]), float(sys.argv[3]), sys.argv[4])
        sys.exit(0)
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "t20-trend-headroom", "data")
    for n in ("wpi", "pamap2", "nasdaq", "bus"):
        prep(src, n)
