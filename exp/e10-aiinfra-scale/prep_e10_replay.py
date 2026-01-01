"""E10 · 部分 A 的回放流 R(G)（README 第 1 节部分 A，切法的读法在第 3 节「定值」）。纯标准库。

用法：python3 -I prep_e10_replay.py segments [流 A 的 tsv]      → 片段清单 handoff/e10_segments.tsv（S 与各源组贡献的片段数）
      python3 -I prep_e10_replay.py build [流 A 的 tsv] [输出目录]  → <输出目录>/replay_G{25,100,400}.tsv（默认 data/）
      python3 -I prep_e10_replay.py shape <tsv>…                    → 每份：事件数、组数、各 W 的 n（同 E1 的 stats）与 S_W（估时间用）
      python3 -I prep_e10_replay.py ws-gpu <输出目录> [S3 基址]     → 第二平台：按 E9 的切片记录下载 15 个文件、核大小与 sha256，
                                                                      用 prep_e9_gpu.py 的 build 原样重建 <输出目录>/gpu_hold.tsv
      python3 -I prep_e10_replay.py fetch-llm <目标文件> [网址]     → 第二平台：下载 Chutes 第 0 个分片并核 sha256（网址与 sha256 取自 E9 的切片记录）
流 A = exp/e9-aiinfra/data/gpu_hold.tsv（每行「组 \t 时间微秒 \t 整数功耗」，按时间排好；E9 的 prep_e9_gpu.py build 产出）。

切法（判据原文，确定性）：每个源组从它第一个事件的时间 t0 起切连续不重叠的片段 [t0 + mD, t0 + (m+1)D)，D = 3,600 s，m = 0, 1, …；
只留完整的片段：该组的时长盖住整段（组的最后一个事件 ≥ t0 + (m+1)D − 1 µs，即半开区间的最后一微秒也在组的时长里），
且段内事件数 ≥ 0.5 × D × 10 = 18,000；片段按（m, 源组在文件里首次出现的先后）排序，共 S 段。
第 i 块回放 GPU（i = 0 … G − 1）放第 (i mod S) 段；时间平移 t' = t − (t0 + mD) + o_i，o_i = (i × 7,919) mod 100,000 µs
（片段的起点对到 o_i，段内的相对时间不变）；组号 = i（写成十进制串）；x 不变。全部事件按（时间, 组号, 段内原顺序）排序。
"""
import bisect, hashlib, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "e9-aiinfra", "data", "gpu_hold.tsv"))
SEGS = os.path.join(HERE, "handoff", "e10_segments.tsv")
E9H = os.path.normpath(os.path.join(HERE, "..", "e9-aiinfra"))
D = 3600 * 1000000          # 片段长度（µs）
MIN_EV = D // 1000000 * 10 // 2   # 0.5 × D × 10 = 18,000
STEP, MOD = 7919, 100000    # o_i = (i × 7,919) mod 100,000 µs
GS = (25, 100, 400)
S_SLIDE = 30                # 滑动 s（秒）
WS = (300, 600, 1800)


def read_groups(path):
    """→ (组名按首次出现的先后, {组: [(t, x)]})，组内保持文件顺序。"""
    order, ev = [], {}
    for line in open(path, encoding="utf-8"):
        g, t, x = line.rstrip("\n").split("\t")
        if g not in ev:
            ev[g] = []
            order.append(g)
        ev[g].append((int(t), int(x)))
    return order, ev


def segments(order, ev):
    """→ [(m, 源组序号, 源组, 段起点 µs, 段内事件 [(t, x)])]，按（m, 源组序号）排序；另返回每个源组的（候选段数、完整段数、时长 µs）"""
    out, per = [], []
    for gi, g in enumerate(order):
        e = ev[g]
        ts = [t for t, _ in e]
        t0, tl = ts[0], ts[-1]
        m, cand, keep = 0, 0, 0
        while t0 + m * D <= tl:
            a, b = t0 + m * D, t0 + (m + 1) * D
            cand += 1
            lo, hi = bisect.bisect_left(ts, a), bisect.bisect_left(ts, b)
            if tl >= b - 1 and hi - lo >= MIN_EV:
                out.append((m, gi, g, a, e[lo:hi]))
                keep += 1
            m += 1
        per.append((g, cand, keep, tl - t0, len(e)))
    out.sort(key=lambda s: (s[0], s[1]))
    return out, per


def check_sorted(order, ev):
    for g in order:
        ts = [t for t, _ in ev[g]]
        if any(b < a for a, b in zip(ts, ts[1:])):
            sys.exit("组 %s 的时间不是不减的" % g)


def replay(segs, G):
    S = len(segs)
    rows = []
    for i in range(G):
        m, gi, g, a, e = segs[i % S]
        o = (i * STEP) % MOD
        for j, (t, x) in enumerate(e):
            rows.append((t - a + o, i, j, x))
    rows.sort()
    return rows


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def cmd_segments(src):
    order, ev = read_groups(src)
    check_sorted(order, ev)
    segs, per = segments(order, ev)
    os.makedirs(os.path.dirname(SEGS), exist_ok=True)
    with open(SEGS, "w", encoding="utf-8") as f:
        f.write("# E10 部分 A 的片段（prep_e10_replay.py segments；源 = E9 流 A，sha256 %s）\n" % sha256(src))
        f.write("# D = %d s；完整 = 组的最后一个事件 ≥ 段终点 − 1 µs 且段内事件 ≥ %d；按（m, 源组首次出现的先后）排序；S = %d\n" % (D // 1000000, MIN_EV, len(segs)))
        f.write("# 源组\t首次出现序\t候选段数\t完整段数\t时长（小时）\t事件数\n")
        for gi, (g, cand, keep, span, n) in enumerate(per):
            f.write("# %s\t%d\t%d\t%d\t%.3f\t%d\n" % (g, gi, cand, keep, span / 3.6e9, n))
        f.write("seg\tm\tsrc_order\tsrc_group\tstart_us\tevents\n")
        for k, (m, gi, g, a, e) in enumerate(segs):
            f.write("%d\t%d\t%d\t%s\t%d\t%d\n" % (k, m, gi, g, a, len(e)))
    print("S = %d 段（源组 %d 个，其中贡献 ≥ 1 段的 %d 个）→ %s" % (len(segs), len(per), sum(1 for p in per if p[2]), SEGS))
    for g, cand, keep, span, n in per:
        print("  %-42s 时长 %7.2f h  候选 %3d  完整 %3d  事件 %d" % (g, span / 3.6e9, cand, keep, n))
    for G in GS:
        rep = [G // len(segs) + (1 if k < G % len(segs) else 0) for k in range(len(segs))]
        print("G = %d：每段用 %d–%d 次；事件 %d" % (G, min(rep), max(rep), sum(len(segs[i % len(segs)][4]) for i in range(G))))
    return segs


def cmd_build(src, outdir):
    order, ev = read_groups(src)
    check_sorted(order, ev)
    segs, _ = segments(order, ev)
    os.makedirs(outdir, exist_ok=True)
    for G in GS:
        p = os.path.join(outdir, "replay_G%d.tsv" % G)
        with open(p, "w", encoding="utf-8") as f:
            for t, i, _, x in replay(segs, G):
                f.write("%d\t%d\t%d\n" % (i, t, x))
        print("R(%d)：S = %d、%s → %s（sha256 %s）" % (G, len(segs), "%d 个事件" % sum(len(segs[i % len(segs)][4]) for i in range(G)), p, sha256(p)))


def sw(path, s=S_SLIDE, Ws=WS):
    """S_W = Σ 每个事件 ×（窗口内同组前驱数 × 共同窗口数），从每组每窗格的事件数算（E9 第 3 节的估时口径）：
    窗格 p 的事件对窗格 q（p − k < q < p）的前驱共 k − (p − q) 个共同窗口，同一窗格内的前驱共 k 个。"""
    su = s * 1000000
    panes = {}
    for line in open(path, encoding="utf-8"):
        g, t, _ = line.split("\t", 2)
        d = panes.setdefault(g, {})
        p = int(t) // su
        d[p] = d.get(p, 0) + 1
    res = {}
    for w in Ws:
        k = w // s
        tot = 0
        for pc in panes.values():
            for p, c in pc.items():
                acc = c * (c - 1) // 2 * k
                for dq in range(1, k):
                    cq = pc.get(p - dq)
                    if cq:
                        acc += c * cq * (k - dq)
                tot += acc
        res[w] = tot
    return res


def cmd_shape(paths):
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "e1-main")))
    import prep_e1
    for p in paths:
        n, g, ns = prep_e1.stats(p, S_SLIDE, Ws=list(WS))
        s = sw(p)
        print("%s：%d 个事件、%d 个组；n %s；S_W %s" % (os.path.basename(p), n, g, " / ".join("%g" % ns[w] for w in WS),
                                                   " / ".join("%.3g" % s[w] for w in WS)))


# ---------------------------------------------------------------- 第二平台（部分 D）的数据：只下载、核对、调用 E9 的脚本，不改切法
def download(url, dest, tries=3):
    """流式下载到 dest（1 MB 一块）；失败重试 3 次。用 urllib，跟随环境里的 https_proxy。"""
    import urllib.request
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
                n = 0
                for b in iter(lambda: r.read(1 << 20), b""):
                    f.write(b)
                    n += len(b)
            return n
        except Exception as ex:  # 网络错误：重试，最后一次照抛
            print("下载失败（第 %d 次）：%s：%s" % (k + 1, url, ex), file=sys.stderr)
            if k == tries - 1:
                raise
            time.sleep(10 * (k + 1))


def ws_gpu(outdir, base=None):
    """按 exp/e9-aiinfra/handoff/e9_files_gpu.txt 里「取」的 15 个键下载（已在且大小、sha256 都对就跳过），逐个核大小与 sha256；
    再把 prep_e9_gpu 的路径改到 <输出目录>（GDIR、MANIFEST、OUT、FILES），调用它的 build 原样重建流 A。"""
    sys.path.insert(0, E9H)
    import prep_e9_gpu as g9
    base = base or g9.BASE
    lines = [l for l in open(os.path.join(E9H, "handoff", "e9_files_gpu.txt"), encoding="utf-8").read().splitlines() if l and not l.startswith("#")]
    head = lines[0].split("\t")
    rows = [dict(zip(head, l.split("\t"))) for l in lines[1:]]
    raw = os.path.join(outdir, "raw")
    g9.GDIR = os.path.join(raw, "gpu")
    g9.MANIFEST = os.path.join(raw, "gpu_fetch.tsv")
    g9.OUT = os.path.join(outdir, "gpu_hold.tsv")
    g9.FILES = os.path.join(raw, "e9_files_gpu.txt")
    os.makedirs(g9.GDIR, exist_ok=True)
    for r in rows:
        if r["status"] != "取":
            continue
        p = g9.local(r["key"])
        if os.path.exists(p) and os.path.getsize(p) == int(r["bytes"]) and sha256(p) == r["sha256"]:
            print("已在、sha256 对：%s" % r["key"].rsplit("/", 1)[-1])
            continue
        download(base + "/" + r["key"], p + ".part")
        if os.path.getsize(p + ".part") != int(r["bytes"]) or sha256(p + ".part") != r["sha256"]:
            sys.exit("大小或 sha256 不符：%s" % r["key"])
        os.replace(p + ".part", p)
        print("下载完、sha256 对：%s（%s 字节）" % (r["key"].rsplit("/", 1)[-1], r["bytes"]))
    with open(g9.MANIFEST, "w", encoding="utf-8") as f:
        f.write("\t".join(head) + "\n" + "".join("\t".join(r[h] for h in head) + "\n" for r in rows))
    g9.build()


def fetch_llm(dest, url=None):
    """Chutes 第 0 个分片：网址与 sha256 取自 exp/e9-aiinfra/handoff/e9_slice_llm.txt 的头两行；已在且 sha256 对就跳过。"""
    head = open(os.path.join(E9H, "handoff", "e9_slice_llm.txt"), encoding="utf-8").read().splitlines()[:2]
    want = re.search(r"[0-9a-f]{64}", head[1]).group(0)
    url = url or re.search(r"https://\S+?\.parquet", head[0]).group(0)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    if os.path.exists(dest) and sha256(dest) == want:
        print("分片已在、sha256 对：%s" % dest)
        return
    n = download(url, dest + ".part")
    if sha256(dest + ".part") != want:
        sys.exit("分片 sha256 不符（%d 字节）" % n)
    os.replace(dest + ".part", dest)
    print("分片下载完、sha256 对：%d 字节 → %s" % (n, dest))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["segments"]:
        cmd_segments(a[1] if len(a) > 1 else SRC)
    elif a[:1] == ["build"]:
        cmd_build(a[1] if len(a) > 1 else SRC, a[2] if len(a) > 2 else os.path.join(HERE, "data"))
    elif a[:1] == ["shape"]:
        cmd_shape(a[1:])
    elif a[:1] == ["ws-gpu"] and len(a) >= 2:
        ws_gpu(a[1], a[2] if len(a) > 2 else None)
    elif a[:1] == ["fetch-llm"] and len(a) >= 2:
        fetch_llm(a[1], a[2] if len(a) > 2 else None)
    else:
        print(__doc__); sys.exit(2)
