"""E10 · 部分 B 的流：Chutes 第 0 个分片、E9 流 B 的同一段时间（开头 T = 27 小时）、全部模型的 ttft 非空请求 → data/llm_all.tsv
（README 第 1 节部分 B；读法在第 3 节「定值」）。读 Parquet 要第三方库 ⇒ E10 里只有本脚本用仓库根 .venv（pyarrow、numpy，
版本同 exp/e9-aiinfra/requirements.txt）；分片、sha256、逐行组读法、十进制位数的读法都调用 exp/e9-aiinfra/prep_e9_llm.py（import，不复制）。

用法：.venv/bin/python -I exp/e10-aiinfra-scale/prep_e10_llm_all.py build [分片] [输出 tsv] [切片记录]
      默认 分片 = exp/e9-aiinfra/data/raw/llm/train-00000-of-00045.parquet，输出 = data/llm_all.tsv，切片记录 = handoff/e10_slice_llm_all.txt
      .venv/bin/python -I exp/e10-aiinfra-scale/prep_e10_llm_all.py e9 <分片> <输出 tsv> <切片记录>
      → 用 E9 的 build 原样重做 E9 流 B（只把输出与切片记录改到给定路径；工作站第二平台用，不碰 E9 的已提交文件）
事件（同 E9）：组 = chute_id，时间 = started_at（微秒）减去本流第一个事件的时间，x = ttft 的 float32 最短往返十进制写法 × 10^3
（d = 3 同 E9；多于 3 位小数的值半数进位）。切片：started_at ∈ [t0, t0 + 27 h)，t0 = 分片里最早的 started_at（同 E9），ttft 非空，不按模型筛。
"""
import collections, os, sys
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
E9 = os.path.normpath(os.path.join(HERE, "..", "e9-aiinfra"))
sys.path.insert(0, E9)
import prep_e9_llm as p9  # noqa: E402

OUT = os.path.join(HERE, "data", "llm_all.tsv")
SLICE = os.path.join(HERE, "handoff", "e10_slice_llm_all.txt")
T_HOURS = 27      # E9 流 B 的 T（exp/e9-aiinfra/handoff/e9_slice_llm.txt 的 T_hours；下面核对）
D_DEC = 3         # E9 流 B 的 d（同上 ttft_decimals_d）
HOUR = p9.HOUR


def e9_record():
    rec = {}
    for line in open(os.path.join(E9, "handoff", "e9_slice_llm.txt"), encoding="utf-8"):
        if not line.startswith("#") and "\t" in line:
            k, v = line.rstrip("\n").split("\t", 1)
            rec[k] = v
    return rec


def build(shard, out, slice_path):
    rec = e9_record()
    if int(rec["T_hours"]) != T_HOURS or int(rec["ttft_decimals_d"]) != D_DEC:
        sys.exit("E9 的切片记录与本脚本的 T / d 不符")
    if p9.sha256(shard) != p9.SHA:
        sys.exit("分片 sha256 不符")
    f = pq.ParquetFile(shard)
    t0 = None
    G, TS, V = [], [], []
    for t, ts in p9.batches(f):          # E9 的逐行组读法（含 started_at 不减的核对）
        if t0 is None:
            t0 = int(ts[0])
        end = t0 + T_HOURS * HOUR
        if ts[0] >= end:
            break
        ttft = t.column("ttft")
        m = pc.and_(pc.is_valid(ttft), pc.less(t.column("started_at").cast(pa.int64()), end))
        mm = m.to_numpy(zero_copy_only=False)
        G.extend(t.column("chute_id").to_numpy(zero_copy_only=False)[mm].tolist())
        TS.extend(ts[mm].tolist())
        V.extend(ttft.to_numpy(zero_copy_only=False)[mm].tolist())
    uniq = sorted(set(V))
    rep = {v: np.format_float_positional(np.float32(v), unique=True, trim="-") for v in uniq}
    dig = collections.Counter(p9.decimals(rep[v]) for v in V)
    scale = Decimal(10) ** D_DEC
    xof = {v: int((Decimal(rep[v]) * scale).to_integral_value(ROUND_HALF_UP)) for v in uniq}
    tmin = TS[0]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fo:
        for g, t, v in zip(G, TS, V):
            fo.write("%s\t%d\t%d\n" % (g, t - tmin, xof[v]))
    per = collections.Counter(G)
    os.makedirs(os.path.dirname(slice_path), exist_ok=True)
    with open(slice_path, "w", encoding="utf-8") as fo:
        fo.write("# E10 部分 B 的流（README 第 1 节部分 B）：Chutes 生产流量 harvardMadsys/chutes_metadata，%s\n" % p9.URL)
        fo.write("# 分片 sha256 %s，%d 行；t0 = 分片最早的 started_at = %d µs；流的第一个事件 %d µs（时间列减去它）\n" % (
            p9.SHA, f.metadata.num_rows, t0, tmin))
        fo.write("# 规则：[t0, t0 + %d h) 里 ttft 非空的全部请求（不按模型筛）；x = ttft 的 float32 最短十进制写法 × 10^%d，多于 %d 位的半数进位\n" % (
            T_HOURS, D_DEC, D_DEC))
        fo.write("T_hours\t%d\n" % T_HOURS)
        fo.write("events\t%d\n" % len(G))
        fo.write("models\t%d\n" % len(per))
        fo.write("ttft_decimals_d\t%d\n" % D_DEC)
        fo.write("# ttft 的 float32 最短十进制写法的小数位分布：%s\n" % "，".join("%d 位 %d" % kv for kv in sorted(dig.items())))
        fo.write("chute_id\tnonnull_ttft_requests\n")
        for c, v in sorted(per.items(), key=lambda kv: (-kv[1], kv[0])):
            fo.write("%s\t%d\n" % (c, v))
    print("llm_all：T = %d 小时、%d 个事件、%d 个模型、d = %d、tmin = %d → %s" % (T_HOURS, len(G), len(per), D_DEC, tmin, out))


def e9_again(shard, out, slice_path):
    """E9 流 B 原样重做：调用 prep_e9_llm.build，只把它的分片、输出与切片记录指到给定路径（第二平台用）。"""
    p9.SHARD, p9.OUT, p9.SLICE = shard, out, slice_path
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p9.build()


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["build"]:
        build(a[1] if len(a) > 1 else p9.SHARD, a[2] if len(a) > 2 else OUT, a[3] if len(a) > 3 else SLICE)
    elif a[:1] == ["e9"] and len(a) == 4:
        e9_again(a[1], a[2], a[3])
    else:
        print(__doc__); sys.exit(2)
