#!/usr/bin/env python3
"""E12 · 第二平台诊断的报表（纯标准库）。协议：exp/e12-platform-diag/README.md 第 1 节。描述性，不设判据。

读 handoff/e12_times.tsv、handoff/e12_perf.tsv（ws_e12.sh 回传）与 E10 的两份计时表
（exp/e10-aiinfra-scale/handoff/e10_times.tsv = 本机，e10_ws_times.tsv = 工作站 E10 部分 D，作对照），
出 report_e12.txt（默认在实验目录下，--out 改路径；--trunc N = Mac 桩测的截断数据，不核校验和、数字无意义）。

协议的「读法」原文（与 README 第 1 节同文）：
  **读法**（跑之前写下；10% 是读数的线，工作站三进程噪声带此前不超过 4%）：
  1. A2 与 A 差超过 10% ⇒ 机器在这段时间里变了，本次只读差距明显大于这个幅度的条件
  2. P 比 A 快 10% 以上 ⇒ 基线慢的一部分来自没绑核；E 与 A 相差在 10% 以内 ⇒ 基线实际上跑在能效核上
  3. PH 比 P 快 10% 以上 ⇒ TLB 是原因之一
  4. PC 与 P 相差 10% 以上 ⇒ 编译器是原因之一
  5. 哪一条都不到 10% ⇒ 原因没找到，正文保持现在的写法（只写事实与运行环境）

实现时的口径（协议没写死、这里定下的）：
  - 「X 比 Y 快 10% 以上」= T_X ÷ T_Y ≤ 0.90；「相差 10% 以上」= |T_X ÷ T_Y − 1| > 0.10；「在 10% 以内」= |T_X ÷ T_Y − 1| ≤ 0.10
  - 每条读法对三个（格, 臂）分别算，列出每个的比值；有一个过线就把它列进「过线的」
  - 第 5 条只看第 2 条前半句（P 快于 A）、第 3 条、第 4 条；第 2 条后半句（E 与 A 接近）单列，不计入第 5 条
  - 一个（条件, 格, 臂）里任何一遍的校验和不等于 E10 部分 D 的值 ⇒ 这一格作废、不读（报表里写「作废」）
"""
import argparse
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E10 = os.path.join(HERE, "..", "e10-aiinfra-scale", "handoff")
CONDS = ["A", "P", "E", "PH", "PC", "A2"]
KEYS = [("1", "600", "OPP"), ("1", "600", "M"), ("2", "1800", "M")]
ARMNAME = {"OPP": "GRETA-C++", "M": "SlotTree"}
CK = {"1": "c94475db8516a335", "2": "fb93f1f10e32e9a7"}
EVENTS_R25 = 847149
LINE = 0.10
PERF_EVENTS = ["cycles", "instructions", "cache-misses", "LLC-load-misses", "dTLB-load-misses", "cpu-migrations", "context-switches"]


def die(msg):
    sys.stderr.write("compare_e12.py 错误：%s\n" % msg)
    sys.exit(2)


def read_tsv(path, need, allow_empty=False):
    if not os.path.isfile(path):
        die("找不到 %s" % path)
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f, delimiter="\t")
        if r.fieldnames is None:
            die("%s 是空文件（连表头都没有）" % path)
        miss = [c for c in need if c not in r.fieldnames]
        if miss:
            die("%s 缺列 %s" % (path, ", ".join(miss)))
        rows = list(r)
    if not rows and not allow_empty:
        die("%s 只有表头、没有数据行" % path)
    return rows


def shown(path):
    """仓库内的文件写相对仓库根的路径，其余写绝对路径"""
    p, root = os.path.abspath(path), os.path.abspath(os.path.join(HERE, "..", ".."))
    return os.path.relpath(p, root) if p.startswith(root + os.sep) else p


def kname(k):
    return "格 %s W=%s s %s" % (k[0], k[1], ARMNAME[k[2]])


def fnum(x, d=3):
    return "—" if x is None else ("%.*f" % (d, x))


def pct(r):
    return "%+.1f%%" % ((r - 1.0) * 100.0)


def e10_median(path, W, arm):
    rows = read_tsv(path, ["arm", "data", "agg", "W", "seconds"])
    xs = [float(r["seconds"]) for r in rows if r["data"] == "r25" and r["agg"] == "COUNT" and r["W"] == W and r["arm"] == arm]
    return statistics.median(xs) if xs else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(HERE, "report_e12.txt"))
    ap.add_argument("--times", default=os.path.join(HERE, "handoff", "e12_times.tsv"))
    ap.add_argument("--perf", default=os.path.join(HERE, "handoff", "e12_perf.tsv"))
    ap.add_argument("--local", default=os.path.join(E10, "e10_times.tsv"))
    ap.add_argument("--ws", default=os.path.join(E10, "e10_ws_times.tsv"))
    ap.add_argument("--trunc", type=int, default=0, help="桩测：数据截成前 N 行（不核校验和；每事件的数按 N 个事件算）")
    a = ap.parse_args()

    trows = read_tsv(a.times, ["cond", "cell", "W", "arm", "pass", "seconds", "checksum", "maxrss_kb", "cpu", "freq_before_khz", "freq_after_khz", "bin"])
    prows = read_tsv(a.perf, ["cell", "W", "arm", "mode", "event", "value", "unit"], allow_empty=True)
    nev = a.trunc if a.trunc > 0 else EVENTS_R25

    # ── 每个（条件, 格, 臂）的中位时间；校验和不符 ⇒ 作废 ──
    grp = {}
    for r in trows:
        k = (r["cond"], r["cell"], r["W"], r["arm"])
        grp.setdefault(k, []).append(r)
    med, status, nps, freqs, badck = {}, {}, {}, {}, []
    for k, rs in grp.items():
        try:
            xs = [float(r["seconds"]) for r in rs]
        except ValueError:
            die("%s 里 %s 的 seconds 不是数" % (a.times, k))
        nps[k] = len(xs)
        freqs[k] = sorted(set((r["cpu"], r["freq_before_khz"], r["freq_after_khz"], r["bin"]) for r in rs))
        bad = [r["checksum"] for r in rs if r["checksum"] != CK.get(r["cell"])]
        if bad and not a.trunc:
            status[k] = "作废"
            badck.append("%s %s：%s ≠ %s" % (k[0], kname(k[1:]), sorted(set(bad)), CK.get(k[1])))
            continue
        status[k] = "ok"
        med[k] = statistics.median(xs)

    def T(cond, key):
        return med.get((cond,) + key)

    def cellstr(cond, key):
        k = (cond,) + key
        if k not in status:
            return "没跑"
        if status[k] != "ok":
            return "作废"
        s = fnum(med[k])
        return s if nps[k] == 3 else "%s(%d遍)" % (s, nps[k])

    loc = {key: e10_median(a.local, key[1], key[2]) for key in KEYS}
    wsd = {key: e10_median(a.ws, key[1], key[2]) for key in KEYS}

    L = []
    w = L.append
    w("# E12 · 第二平台诊断（exp/e12-platform-diag/README.md 第 1 节；描述性，不设判据）")
    w("输入：%s（%d 行）、%s（%d 行）" % (shown(a.times), len(trows), shown(a.perf), len(prows)))
    if a.trunc:
        w("⚠ 桩测：数据截成前 %d 行，不核校验和 —— 下面的数字没有意义，只验证流程" % a.trunc)
    w("回放 R(25)，COUNT，⋈ 为 <，s = 30 s；每个（条件, 格, 臂）一个进程，预热 1 + 计时 3，取 3 遍中位（秒）")
    w("")
    if badck:
        w("🔴🔴 校验和不符（这些格作废、不读，先报用户）：")
        for b in badck:
            w("  - " + b)
        w("")

    hdr = "%-30s" % "（格, 臂）" + "".join("%12s" % c for c in CONDS)
    w("## 1. 中位时间（秒）")
    w(hdr)
    for key in KEYS:
        w("%-30s" % kname(key) + "".join("%12s" % cellstr(c, key) for c in CONDS))
    w("")

    w("## 2. 各条件 ÷ A")
    w(hdr)
    for key in KEYS:
        cs = []
        for c in CONDS:
            x, b = T(c, key), T("A", key)
            cs.append(fnum(x / b) if x is not None and b else cellstr(c, key) if cellstr(c, key) in ("没跑", "作废") else "—")
        w("%-30s" % kname(key) + "".join("%12s" % s for s in cs))
    w("")

    w("## 3. 各条件 ÷ 本机同格（本机 = e10_times.tsv 同格中位；E10 部分 D = e10_ws_times.tsv 同格中位，作对照）")
    w("%-30s%10s%10s%10s" % ("（格, 臂）", "本机", "E10 D", "D÷本机") + "".join("%12s" % c for c in CONDS))
    for key in KEYS:
        lo, d = loc[key], wsd[key]
        cs = []
        for c in CONDS:
            x = T(c, key)
            cs.append(fnum(x / lo) if x is not None and lo else cellstr(c, key) if cellstr(c, key) in ("没跑", "作废") else "—")
        w("%-30s%10s%10s%10s" % (kname(key), fnum(lo), fnum(d), fnum(d / lo) if d and lo else "—") + "".join("%12s" % s for s in cs))
    w("")

    w("## 4. r = T_GRETA-C++ ÷ T_SlotTree（格 1）")
    ro = ("1", "600", "OPP")
    rm = ("1", "600", "M")
    w("%-30s" % "" + "".join("%12s" % c for c in CONDS))
    rs = []
    for c in CONDS:
        x, y = T(c, ro), T(c, rm)
        rs.append(fnum(x / y, 2) if x is not None and y else "—")
    w("%-30s" % "r（本条件）" + "".join("%12s" % s for s in rs))
    w("对照：本机 r = %s；E10 部分 D r = %s" % (fnum(loc[ro] / loc[rm], 2) if loc[ro] and loc[rm] else "—",
                                         fnum(wsd[ro] / wsd[rm], 2) if wsd[ro] and wsd[rm] else "—"))
    w("")

    w("## 5. 频率（kHz；每个进程前后各读一次 scaling_cur_freq：绑核时读所绑的核，不绑核时读全部核里最高的；? = 读不到）")
    for c in CONDS:
        for key in KEYS:
            k = (c,) + key
            if k not in freqs:
                continue
            for cpu, fb, fa, b in freqs[k]:
                w("  %-3s %-28s cpu=%-3s bin=%-6s 前 %s → 后 %s" % (c, kname(key), cpu, b, fb, fa))
    if not freqs:
        w("  （没有计时行）")
    w("")

    w("## 6. 硬件计数器（条件 P 的绑核方式；每遍 = (parse+3 − parse) ÷ 3；每事件 = 每遍 ÷ %d 个事件）" % nev)
    if not prows:
        w("  没跑（perf 不可用或条件 P 没跑；原因见 relay/diag_status.txt 的 notes）")
    else:
        pv = {}
        for r in prows:
            try:
                v = float(r["value"])
            except ValueError:
                v = None
            pv[(r["cell"], r["W"], r["arm"], r["mode"], r["event"])] = (v, r["value"])
        evs = sorted(set(r["event"] for r in prows), key=lambda e: (e.split("/")[0] if "/" in e else "", PERF_EVENTS.index(e.split("/")[1]) if "/" in e and e.split("/")[1] in PERF_EVENTS else PERF_EVENTS.index(e) if e in PERF_EVENTS else 99, e))
        w("%-30s %-30s %16s %16s %16s %12s" % ("（格, 臂）", "事件", "parse", "parse+3", "每遍", "每事件"))
        perpass = {}
        for key in KEYS:
            for e in evs:
                a0 = pv.get(key + ("parse", e))
                a3 = pv.get(key + ("parse+3", e))
                if a0 is None and a3 is None:
                    continue
                v0 = a0[0] if a0 else None
                v3 = a3[0] if a3 else None
                pp = (v3 - v0) / 3.0 if v0 is not None and v3 is not None else None
                perpass[key + (e,)] = pp
                w("%-30s %-30s %16s %16s %16s %12s" % (kname(key), e, a0[1] if a0 else "—", a3[1] if a3 else "—",
                                                       fnum(pp, 0), fnum(pp / nev, 2) if pp is not None else "—"))
        w("IPC（每遍 instructions ÷ 每遍 cycles，按 PMU 分开）：")
        any_ipc = False
        for key in KEYS:
            pmus = sorted(set(e.split("/")[0] if "/" in e else "" for e in evs))
            for p in pmus:
                ci = (p + "/cycles/") if p else "cycles"
                ii = (p + "/instructions/") if p else "instructions"
                cy, ins = perpass.get(key + (ci,)), perpass.get(key + (ii,))
                if cy and ins is not None:
                    any_ipc = True
                    w("  %-30s %-10s IPC = %s" % (kname(key), p or "-", fnum(ins / cy, 2)))
        if not any_ipc:
            w("  （没有可用的 cycles / instructions 对）")
    w("")

    # ── 读法 ──
    def ratios(cx, cy):
        out = []
        for key in KEYS:
            x, y = T(cx, key), T(cy, key)
            if x is not None and y:
                out.append((key, x / y))
        return out

    def listing(rl, cx, cy):
        return "；".join("%s T_%s÷T_%s = %s（%s）" % (kname(k), cx, cy, fnum(r), pct(r)) for k, r in rl)

    w("## 7. 读法（协议第 1 节；10% 是读数的线）")
    r1 = ratios("A2", "A")
    drift = max((abs(r - 1) for _, r in r1), default=None)
    if not r1:
        w("读法 1：没跑（A 或 A2 没有可读的格）")
        caveat = ""
    else:
        hit = [k for k, r in r1 if abs(r - 1) > LINE]
        w("读法 1：%s ⇒ %s" % (listing(r1, "A2", "A"),
                             ("超过 10%%（%s）：机器在这段时间里变了，下面只读差距明显大于 %.1f%% 的条件" % ("、".join(kname(k) for k in hit), drift * 100)) if hit
                             else "都在 10% 以内：机器这段时间没有明显漂移"))
        caveat = ("（读法 1 已触发：只有差距明显大于 %.1f%% 的才读）" % (drift * 100)) if hit else ""

    found = []
    r2 = ratios("P", "A")
    if not r2:
        s2a = "P 没跑"
    else:
        hit = [k for k, r in r2 if r <= 1 - LINE]
        if hit:
            found.append("P 快于 A")
        s2a = "%s ⇒ %s" % (listing(r2, "P", "A"), ("P 比 A 快 10%% 以上（%s）：基线慢的一部分来自没绑核" % "、".join(kname(k) for k in hit)) if hit else "P 都没有比 A 快 10% 以上")
    r2e = ratios("E", "A")
    if not r2e:
        s2b = "E 没跑"
    else:
        hit = [k for k, r in r2e if abs(r - 1) <= LINE]
        s2b = "%s ⇒ %s" % (listing(r2e, "E", "A"), ("E 与 A 相差在 10%% 以内（%s）：基线实际上跑在能效核上" % "、".join(kname(k) for k in hit)) if hit else "E 与 A 都相差 10% 以上")
    w("读法 2：%s。%s%s" % (s2a, s2b, caveat))

    r3 = ratios("PH", "P")
    if not r3:
        w("读法 3：没跑（PH 或 P 没有可读的格）")
    else:
        hit = [k for k, r in r3 if r <= 1 - LINE]
        if hit:
            found.append("PH 快于 P")
        w("读法 3：%s ⇒ %s%s" % (listing(r3, "PH", "P"), ("PH 比 P 快 10%% 以上（%s）：TLB 是原因之一" % "、".join(kname(k) for k in hit)) if hit else "PH 都没有比 P 快 10% 以上", caveat))

    r4 = ratios("PC", "P")
    if not r4:
        w("读法 4：没跑（PC 或 P 没有可读的格）")
    else:
        hit = [k for k, r in r4 if abs(r - 1) > LINE]
        if hit:
            found.append("PC 与 P 不同")
        w("读法 4：%s ⇒ %s%s" % (listing(r4, "PC", "P"), ("PC 与 P 相差 10%% 以上（%s）：编译器是原因之一" % "、".join(kname(k) for k in hit)) if hit else "PC 与 P 都相差在 10% 以内", caveat))

    notrun = [n for n, rl in (("第 2 条（P÷A）", r2), ("第 3 条（PH÷P）", r3), ("第 4 条（PC÷P）", r4)) if not rl]
    if found:
        w("读法 5：不适用 —— 过线的有：%s" % "、".join(found))
    elif len(notrun) == 3:
        w("读法 5：第 2 条前半句、第 3 条、第 4 条都没跑 ⇒ 什么原因也没量到；按第 5 条，正文保持现在的写法（只写事实与运行环境）")
    else:
        w("读法 5：跑了的%s都不到 10%%%s ⇒ 原因没找到，正文保持现在的写法（只写事实与运行环境）"
          % ("、".join(n for n, rl in (("第 2 条前半句", r2), ("第 3 条", r3), ("第 4 条", r4)) if rl),
             ("（没跑的：%s）" % "、".join(notrun)) if notrun else ""))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
