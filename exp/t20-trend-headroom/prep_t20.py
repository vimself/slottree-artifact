"""T20 · 四份原始数据 → data/<名>.tsv（每行：组 \t 时间秒 \t 属性），组内按时间、再按文件顺序排好。纯标准库。

用法：python3 -I prep_t20.py <data 目录>
原始文件（README 第 2 节）：<data>/wpi/TimeAndSales_*.txt、<data>/pamap2/pamap2.zip、<data>/gloria/Nasdaq_bursty_20.csv、<data>/gloria/bus_stream.csv
"""
import csv, glob, io, os, sys, zipfile


def write(path, rows):
    rows.sort(key=lambda r: (r[0], r[1], r[3]))  # 组、时间、文件顺序
    with open(path, "w", encoding="utf-8") as f:
        for g, t, a, _ in rows:
            f.write("%s\t%.6f\t%.10g\n" % (g, t, a))
    print("%s：%d 个事件、%d 个组" % (os.path.basename(path), len(rows), len({r[0] for r in rows})))


def wpi(d):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "wpi", "TimeAndSales_*.txt"))):
        for line in open(p, encoding="utf-8"):
            f = line.split()
            if len(f) < 6:
                continue
            hh, mm, ss = f[4].split(":")
            t = int(hh) * 3600 + int(mm) * 60 + float(ss)
            rows.append((f[0], t, float(f[3]), int(f[1])))  # 文件按时间倒序，同一时刻按成交号递增
    write(os.path.join(d, "wpi.tsv"), rows)


def pamap2(d):
    inner = os.path.join(d, "pamap2", "PAMAP2_Dataset.zip")
    if not os.path.exists(inner):
        with zipfile.ZipFile(os.path.join(d, "pamap2", "pamap2.zip")) as z, open(inner, "wb") as out:
            with z.open("PAMAP2_Dataset.zip") as src:
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    out.write(b)
    rows = []
    with zipfile.ZipFile(inner) as z:
        names = sorted(n for n in z.namelist() if "/Protocol/" in n and n.endswith(".dat"))
        for n in names:
            subj = os.path.basename(n)[:-4]
            with z.open(n) as raw:
                for i, line in enumerate(io.TextIOWrapper(raw, encoding="utf-8")):
                    f = line.split()
                    if len(f) < 3 or f[2].lower() == "nan":
                        continue
                    rows.append((subj, float(f[0]), float(f[2]), i))
    write(os.path.join(d, "pamap2.tsv"), rows)


def nasdaq(d):
    rows, seen = [], set()
    with open(os.path.join(d, "gloria", "Nasdaq_bursty_20.csv"), encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for i, x in enumerate(r):
            key = (x[0], x[1])
            if key in seen:  # 突发复制的重复行（README 第 2 节）
                continue
            seen.add(key)
            s = x[1]
            t = ((int(s[6:8]) * 24 + int(s[8:10])) * 60 + int(s[10:12])) * 60.0
            rows.append((x[0], t, float(x[5]), i))
    write(os.path.join(d, "nasdaq.tsv"), rows)


def bus(d):
    rows = []
    with open(os.path.join(d, "gloria", "bus_stream.csv"), encoding="utf-8") as f:
        r = csv.reader(f)
        head = next(r)
        it, iv, idl = head.index("timestamp"), head.index("vehicle_id"), head.index("delay")
        for i, x in enumerate(r):
            rows.append((x[iv], int(x[it]) / 1e6, float(x[idl]), i))
    write(os.path.join(d, "bus.tsv"), rows)


if __name__ == "__main__":
    d = sys.argv[1]
    wpi(d)
    pamap2(d)
    nasdaq(d)
    bus(d)
