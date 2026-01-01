"""E4 · Intel Lab → data/intel_dev.tsv（每行「组 \t 时间整数微秒 \t 整数属性」，时间以最早为 0；README 第 2.2 节）。纯标准库。

用法：python3 -I prep_e4.py      原始文件在被忽略的 data/raw/intel/data.txt.gz（sha256 见 README 第 3 节）
列 date time epoch moteid temperature humidity light voltage；组 = moteid（54 个 mote，1–54），时间 = date + time → 微秒，属性 = 温度 × 100 四舍五入。
缺字段（不足 8 列）或温度非数的行丢弃；moteid 不在 1–54 的行丢弃（README 只有 54 个 mote）。按（时间, 文件顺序）稳定排序。
"""
import datetime, gzip, os, sys
from decimal import Decimal, InvalidOperation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "e1-main"))
from prep_e1 import rint, stats  # noqa: E402


def usec(d, t):
    hms, _, frac = t.partition(".")
    dt = datetime.datetime.strptime(d + " " + hms, "%Y-%m-%d %H:%M:%S")
    return int((dt - datetime.datetime(1970, 1, 1)).total_seconds()) * 1000000 + int((frac + "000000")[:6])


def main():
    rows, drop = [], {"缺字段": 0, "温度非数": 0, "mote 不在 1–54": 0, "时间坏": 0}
    for ln, line in enumerate(gzip.open(os.path.join(HERE, "data", "raw", "intel", "data.txt.gz"), "rt", encoding="utf-8")):
        f = line.split()
        if len(f) < 8:
            drop["缺字段"] += 1
            continue
        try:
            temp = Decimal(f[4])
            if not temp.is_finite():
                raise InvalidOperation
        except InvalidOperation:
            drop["温度非数"] += 1
            continue
        if not f[3].isdigit() or not 1 <= int(f[3]) <= 54:
            drop["mote 不在 1–54"] += 1
            continue
        try:
            t = usec(f[0], f[1])
        except ValueError:
            drop["时间坏"] += 1
            continue
        rows.append((int(f[3]), t, rint(temp * 100), ln))
    rows.sort(key=lambda r: (r[1], r[3]))
    t0 = rows[0][1]
    path = os.path.join(HERE, "data", "intel_dev.tsv")
    with open(path, "w", encoding="utf-8") as fo:
        for g, t, a, _ in rows:
            fo.write("mote%d\t%d\t%d\n" % (g, t - t0, a))
    print("丢弃：%s" % "、".join("%s %d" % kv for kv in drop.items()))
    print("intel_dev：%d 个事件、%d 个组、每组每窗（10 分钟）事件中位 %s" % stats(path, 60))


if __name__ == "__main__":
    main()
