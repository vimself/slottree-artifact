"""E9 · 流 B（Chutes LLM 推理服务的首 token 延迟）→ data/llm_hold.tsv（README 第 2 节）。读 Parquet 要第三方库 ⇒ 只有本脚本用仓库根 .venv
（pyarrow、numpy，版本在 requirements.txt）；输出与其余流同格式的 TSV，其余脚本保持纯标准库。

用法：.venv/bin/python -I exp/e9-aiinfra/prep_e9_llm.py build    → data/llm_hold.tsv 与 handoff/e9_slice_llm.txt
原始文件：data/raw/llm/train-00000-of-00045.parquet（Hugging Face harvardMadsys/chutes_metadata，data/trace/，CC BY 4.0；sha256 见下）
切片（README 第 2 节，确定性）：只用第 0 个分片；t0 = 分片里最早的 started_at；取最小的整小时数 T，使 [t0, t0 + T 小时) 里
ttft 非空的请求数最多的 10 个模型（同数按 chute_id 字典序）合计 ≥ N_B；流 = 这 10 个模型在这 T 小时里的全部 ttft 非空请求。
事件：组 = chute_id，时间 = started_at（微秒），x = ttft × 10^d 取整。
d 的读法（README 只写「按数据的实际精度」）：ttft 在文件里是 float32，二进制值乘 10 的幂不会恰好是整数 ⇒ 每个值取它在 float32 精度下
最短的往返十进制写法（numpy format_float_positional(unique=True)，与 pyarrow 转字符串相同），数小数位；d = 使流里 ≥ 99% 的值
小数位 ≤ d 的最小 d，上限 6；x = 该十进制写法 × 10^d（小数位多于 d 的值半数进位）。
"""
import collections, hashlib, os, sys
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
SHARD = os.path.join(HERE, "data", "raw", "llm", "train-00000-of-00045.parquet")
SHA = "1d3bf71db1ca5357654db4e52f1c55c9fbd184e7da0918f6b0b25c8612623a47"
URL = "https://huggingface.co/datasets/harvardMadsys/chutes_metadata/resolve/main/data/trace/train-00000-of-00045.parquet"
OUT = os.path.join(HERE, "data", "llm_hold.tsv")
SLICE = os.path.join(HERE, "handoff", "e9_slice_llm.txt")
N_B = 2_500_000   # 实验段定值（README 第 3 节「开发记录」，第一次引擎运行之前提交）
TOP = 10
HOUR = 3600 * 1000000
DMAX = 6


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def batches(f):
    """逐个行组读 chute_id、started_at（微秒整数）、ttft；核对 started_at 不减。"""
    last = None
    for i in range(f.metadata.num_row_groups):
        t = f.read_row_group(i, columns=["chute_id", "started_at", "ttft"])
        ts = t.column("started_at").cast(pa.int64()).to_numpy()
        if (last is not None and ts[0] < last) or (np.diff(ts) < 0).any():
            sys.exit("started_at 不是不减的（行组 %d）" % i)
        last = int(ts[-1])
        yield t, ts


def decimals(s):
    return len(s.split(".", 1)[1]) if "." in s else 0


def build():
    if sha256(SHARD) != SHA:
        sys.exit("分片 sha256 不符")
    f = pq.ParquetFile(SHARD)
    # 第一遍：每小时、每个模型的 ttft 非空请求数，直到够判 T
    t0 = None
    hourly = collections.defaultdict(collections.Counter)
    rows_seen = 0
    T = None
    done_hours = 0
    for t, ts in batches(f):
        if t0 is None:
            t0 = int(ts[0])
        hr = (ts - t0) // HOUR
        nn = pc.is_valid(t.column("ttft")).to_numpy(zero_copy_only=False)
        ch = t.column("chute_id").to_numpy(zero_copy_only=False)
        for h, c in zip(hr[nn].tolist(), ch[nn].tolist()):
            hourly[h][c] += 1
        rows_seen += len(ts)
        # 已读完的整小时：本行组最后一个事件所在小时之前的都完整
        complete = int(hr[-1])
        while done_hours < complete:
            done_hours += 1
            per = collections.Counter()
            for h in range(done_hours):
                per.update(hourly[h])
            top = sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]
            if sum(v for _, v in top) >= N_B:
                T = done_hours
                break
        if T is not None:
            break
    if T is None:
        sys.exit("第 0 个分片里凑不够 N_B")
    per = collections.Counter()
    for h in range(T):
        per.update(hourly[h])
    top = sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]
    keep = {c for c, _ in top}
    # 第二遍：取流
    G, TS, V = [], [], []
    end = t0 + T * HOUR
    for t, ts in batches(f):
        if ts[0] >= end:
            break
        ttft = t.column("ttft")
        ch = t.column("chute_id")
        m = pc.and_(pc.is_valid(ttft), pc.less(t.column("started_at").cast(pa.int64()), end))
        m = pc.and_(m, pc.is_in(ch, value_set=pa.array(sorted(keep))))
        mm = m.to_numpy(zero_copy_only=False)
        G.extend(ch.to_numpy(zero_copy_only=False)[mm].tolist())
        TS.extend(ts[mm].tolist())
        V.extend(ttft.to_numpy(zero_copy_only=False)[mm].tolist())
    if len(G) != sum(v for _, v in top):
        sys.exit("第二遍事件数 %d 与第一遍 %d 不符" % (len(G), sum(v for _, v in top)))
    # d：float32 最短往返十进制写法的小数位
    uniq = sorted(set(V))
    rep = {v: np.format_float_positional(np.float32(v), unique=True, trim="-") for v in uniq}
    dig = collections.Counter(decimals(rep[v]) for v in V)
    n = len(V)
    d = DMAX
    for dd in range(DMAX + 1):
        if sum(c for k, c in dig.items() if k <= dd) >= 0.99 * n:
            d = dd
            break
    scale = Decimal(10) ** d
    xof = {v: int((Decimal(rep[v]) * scale).to_integral_value(ROUND_HALF_UP)) for v in uniq}
    tmin = TS[0]
    with open(OUT, "w", encoding="utf-8") as fo:
        for g, t, v in zip(G, TS, V):
            fo.write("%s\t%d\t%d\n" % (g, t - tmin, xof[v]))
    os.makedirs(os.path.dirname(SLICE), exist_ok=True)
    with open(SLICE, "w", encoding="utf-8") as fo:
        fo.write("# E9 流 B 的切片（README 第 2 节）：Chutes 生产流量 harvardMadsys/chutes_metadata，%s\n" % URL)
        fo.write("# 分片 sha256 %s，%d 行；started_at 已归一化（分片最早 t0 = %d µs）\n" % (SHA, f.metadata.num_rows, t0))
        fo.write("# 规则：最小的整小时数 T，使 [t0, t0 + T h) 里 ttft 非空请求数最多的 %d 个模型合计 ≥ N_B = %d\n" % (TOP, N_B))
        fo.write("T_hours\t%d\n" % T)
        fo.write("events\t%d\n" % n)
        fo.write("ttft_decimals_d\t%d\n" % d)
        fo.write("# ttft 的 float32 最短十进制写法的小数位分布：%s\n" % "，".join("%d 位 %d" % kv for kv in sorted(dig.items())))
        fo.write("chute_id\tnonnull_ttft_requests\n")
        for c, v in top:
            fo.write("%s\t%d\n" % (c, v))
    print("llm_hold：T = %d 小时、%d 个事件、%d 个组、d = %d → %s" % (T, n, len(keep), d, OUT))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__); sys.exit(2)
