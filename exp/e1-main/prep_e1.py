"""E1 · 新数据 → data/<名>_hold.tsv（每行「组 \t 时间整数微秒 \t 整数属性」，时间以整份数据最早时间为 0；README 第 2.2 节）。纯标准库。

用法：python3 -I prep_e1.py binance|porto|metrla|all      原始文件在被忽略的 data/raw/<名>/（下载与 sha256 见 README 第 3 节）
      python3 -I prep_e1.py stats <tsv> <s 秒> [W 秒 = 600]  事件数、组数、每组每窗事件数中位（只算含事件的窗口，同 M1）
产物按（时间, 文件顺序）稳定排序：引擎本来就按时间稳定排序（M1 的 load），排好只让 --limit 取的是每组时间上最早的事件。
"""
import csv, datetime, io, math, os, statistics, sys, zipfile
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
OUT = os.path.join(HERE, "data")
PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]


def rint(x):
    """十进制串 → 四舍五入（半数进位）的整数。"""
    return int(Decimal(x).to_integral_value(ROUND_HALF_UP))


def write(name, rows):
    """rows：(组, 时间微秒, 属性, 文件顺序)。按（时间, 文件顺序）排序、时间减最早时间，写 data/<名>_hold.tsv。"""
    rows.sort(key=lambda r: (r[1], r[3]))
    t0 = rows[0][1]
    path = os.path.join(OUT, "%s_hold.tsv" % name)
    with open(path, "w", encoding="utf-8") as f:
        for g, t, a, _ in rows:
            f.write("%s\t%d\t%d\n" % (g, t - t0, a))
    return path


def binance():
    """组 = 交易对；时间 = 成交时间戳取到毫秒（原始文件给微秒，取 ⌊µs ÷ 1000⌋ 毫秒再 × 1000 存微秒）；属性 = 价格 × 10⁸ 取整。"""
    rows = []
    for p in PAIRS:
        z = zipfile.ZipFile(os.path.join(RAW, "binance", "%s-aggTrades-2025-10-01.zip" % p))
        name = z.namelist()[0]
        for i, r in enumerate(csv.reader(io.TextIOWrapper(z.open(name), encoding="utf-8"))):
            # agg_trade_id, price, quantity, first_trade_id, last_trade_id, transact_time, is_buyer_maker, is_best_match
            ts = int(r[5])
            ms = ts // 1000 if ts > 10 ** 14 else ts  # 2025 起现货文件是微秒；毫秒的老格式原样
            rows.append((p, ms * 1000, rint(Decimal(r[1]) * 100000000), (PAIRS.index(p), i)))
    return write("binance", rows)


def hav(lon1, lat1, lon2, lat2):
    """大圆距离（米），地球半径 6,371,000 m。"""
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def porto():
    """UCI 339 的 train.csv：TIMESTAMP（Unix 秒，按 UTC）落在 2013-07、MISSING_DATA 为 False 的行；第 i 个点时间 = TIMESTAMP + 15 i 秒；
    属性 = 第 i−1 到第 i 个点的大圆距离 ÷ 15 s（m/s × 100 四舍五入；第一个点丢弃）；组 = TAXI_ID。"""
    import json
    lo, hi = 1372636800, 1375315200  # 2013-07-01 00:00 UTC、2013-08-01 00:00 UTC
    rows = []
    zp = os.path.join(RAW, "porto", "x", "train.csv")
    with open(zp, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        head = next(rd)
        iT, iX, iM, iP = head.index("TIMESTAMP"), head.index("TAXI_ID"), head.index("MISSING_DATA"), head.index("POLYLINE")
        for ln, r in enumerate(rd):
            ts = int(r[iT])
            if not (lo <= ts < hi) or r[iM] != "False":
                continue
            pts = json.loads(r[iP])
            for i in range(1, len(pts)):
                v = hav(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]) / 15.0
                rows.append((r[iX], (ts + 15 * i) * 1000000, int(math.floor(v * 100 + 0.5)), (ln, i)))
    return write("porto", rows)


def metrla():
    """Zenodo 5146275 的 METR-LA.csv（首列时间、其余 207 列传感器车速，5 分钟一格）；事件 = （传感器, 时间, 车速 × 10 四舍五入），车速 0 视为缺失丢弃。"""
    rows = []
    with open(os.path.join(RAW, "metrla", "METR-LA.csv"), encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        head = next(rd)
        sensors = head[1:]
        for ln, r in enumerate(rd):
            t = datetime.datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
            us = int((t - datetime.datetime(1970, 1, 1)).total_seconds()) * 1000000
            for j, v in enumerate(r[1:]):
                if Decimal(v) == 0:
                    continue
                rows.append((sensors[j], us, rint(Decimal(v) * 10), (ln, j)))
    return write("metrla", rows)


def stats(path, s, W=600, Ws=None):
    """事件数、组数、每组每窗事件数中位（窗口 j 覆盖 [j·s, j·s + W)，只算含事件的窗口；同 M1 compare 的 window_sizes）。
    Ws 给一串 W（秒）时返回 (事件数, 组数, {W: 中位})，只读一遍文件。"""
    import bisect
    su = s * 1000000
    panes = {}
    n = 0
    for line in open(path, encoding="utf-8"):
        g, t, _ = line.split("\t", 2)
        d = panes.setdefault(g, {})
        p = int(t) // su
        d[p] = d.get(p, 0) + 1
        n += 1
    res = {}
    for w in (Ws or [W]):
        k = w // s
        sizes = []
        for pc in panes.values():
            ps = sorted(pc)
            pre = [0]
            for p in ps:
                pre.append(pre[-1] + pc[p])
            js, last = [], None
            for p in ps:  # 含事件的窗口 = ∪ [p − k + 1, p]，按顺序去重
                lo = p - k + 1 if last is None or p - k + 1 > last else last + 1
                js.extend(range(lo, p + 1))
                last = p
            for j in js:
                sizes.append(pre[bisect.bisect_left(ps, j + k)] - pre[bisect.bisect_left(ps, j)])
        res[w] = statistics.median(sizes)
    return (n, len(panes), res) if Ws else (n, len(panes), res[W])


S_OF = {"binance": 10, "porto": 60, "metrla": 300}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if sys.argv[1] == "stats":
        print("%s：%d 个事件、%d 个组、每组每窗事件中位 %s" % ((sys.argv[2],) + stats(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 600)))
        sys.exit(0)
    for name in (["binance", "porto", "metrla"] if sys.argv[1] == "all" else [sys.argv[1]]):
        p = {"binance": binance, "porto": porto, "metrla": metrla}[name]()
        print("%s_hold：%d 个事件、%d 个组、每组每窗（10 分钟）事件中位 %s" % ((name,) + stats(p, S_OF[name])))
