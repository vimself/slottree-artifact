"""E9 · 流 A（MIT Supercloud GPU 功耗）→ data/gpu_hold.tsv（README 第 2 节）。纯标准库。

用法：python3 -I prep_e9_gpu.py list     列出 gpu/ 全部键与大小 → data/raw/gpu_keys.tsv（S3 列表接口，每页 1000 键）
      python3 -I prep_e9_gpu.py fetch    按切片规则依次下载带标签作业的文件到 data/raw/gpu/，累计事件数 ≥ N_A 为止
      python3 -I prep_e9_gpu.py build    → data/gpu_hold.tsv（每行「组 \t 时间整数微秒 \t 整数属性」，时间以整条流最早为 0）
                                         与 handoff/e9_files_gpu.txt（取到哪个文件为止、文件清单与各文件大小）
切片（README 第 2 节，确定性）：取作业号在 labelled_jobids.csv 里的文件，按键的字典序排列；跳过大于 60 MB 的文件；
依次取，直到累计事件数 ≥ N_A。事件 = 文件里的一行（一块 GPU 在一个采样时刻）：组 = [作业文件, gpu_index]，
时间 = timestamp，x = power_draw_W × 100 取整（十进制串半数进位）。
"""
import csv, hashlib, os, sys, urllib.request, xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
GDIR = os.path.join(RAW, "gpu")
KEYS = os.path.join(RAW, "gpu_keys.tsv")
LABELS = os.path.join(RAW, "labelled_jobids.csv")
OUT = os.path.join(HERE, "data", "gpu_hold.tsv")
FILES = os.path.join(HERE, "handoff", "e9_files_gpu.txt")
BASE = "https://mit-supercloud-dataset.s3.us-west-2.amazonaws.com"
PREFIX = "datacenter-challenge/202201/gpu/"
N_A = 2_500_000   # 实验段定值（README 第 3 节「开发记录」，第一次引擎运行之前提交）
MAX_BYTES = 60 * 1000 * 1000   # 跳过大于 60 MB 的文件（README 第 2 节）
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


LABELS_SHA = "bd00b9e572442ed9ad900c8919de789e0a4bf225df8a657be9c7b389d7ca6d82"


def list_keys():
    """S3 ListObjectsV2，匿名 HTTPS；写「键 \t 字节数」，按键的字典序。另取 labelled_jobids.csv（不在时下载）并核 sha256。"""
    import urllib.parse
    if not os.path.exists(LABELS):
        os.makedirs(RAW, exist_ok=True)
        urllib.request.urlretrieve(BASE + "/datacenter-challenge/202201/labelled_jobids.csv", LABELS)
    if sha256(LABELS) != LABELS_SHA:
        sys.exit("labelled_jobids.csv 的 sha256 不符")
    rows, token = [], None
    while True:
        q = {"list-type": "2", "prefix": PREFIX, "max-keys": "1000"}
        if token:
            q["continuation-token"] = token
        with urllib.request.urlopen(BASE + "/?" + urllib.parse.urlencode(q), timeout=120) as r:
            root = ET.fromstring(r.read())
        for c in root.findall(NS + "Contents"):
            rows.append((c.find(NS + "Key").text, int(c.find(NS + "Size").text)))
        if root.find(NS + "IsTruncated").text != "true":
            break
        token = root.find(NS + "NextContinuationToken").text
        if len(rows) % 10000 == 0:
            print("已列 %d 个键" % len(rows), file=sys.stderr)
    rows.sort()
    with open(KEYS, "w", encoding="utf-8") as f:
        for k, s in rows:
            f.write("%s\t%d\n" % (k, s))
    print("gpu/ 共 %d 个键，%.1f GB → %s" % (len(rows), sum(s for _, s in rows) / 1e9, KEYS))


def labelled():
    with open(LABELS, encoding="utf-8", newline="") as f:
        return {r["id_job"]: r["model"] for r in csv.DictReader(f)}


def candidates():
    """切片的候选：作业号带标签的 .csv 文件，按键的字典序；返回 [(键, 字节数, 模型, 是否因 > 60 MB 跳过)]。"""
    lab = labelled()
    out = []
    for line in open(KEYS, encoding="utf-8"):
        k, s = line.rstrip("\n").split("\t")
        base = k.rsplit("/", 1)[-1]
        if not base.endswith(".csv"):
            continue
        job = base.split("-", 1)[0]
        if job in lab:
            out.append((k, int(s), lab[job], int(s) > MAX_BYTES))
    return out



def local(key):
    """data/raw/gpu/<NNNN>-<文件名>"""
    d, b = key.split("/")[-2:]
    return os.path.join(GDIR, "%s-%s" % (d, b))


def is_num(x):
    """power_draw_W 是十进制数（nvidia-smi 不支持或缺失时写的不是数）才算事件。"""
    try:
        Decimal(x)
        return x.strip() != "" and Decimal(x).is_finite()
    except Exception:
        return False


def read_file(path):
    """一个文件 → [(gpu_index, 时间微秒, x)]（文件顺序）与丢弃的行数。时间 = timestamp（Unix 秒，十进制串）× 10⁶；x = power_draw_W × 100 半数进位。"""
    ev, bad = [], 0
    with open(path, encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        head = next(rd)
        iT, iG, iP = head.index("timestamp"), head.index("gpu_index"), head.index("power_draw_W")
        for r in rd:
            if len(r) != len(head) or not is_num(r[iP]) or not is_num(r[iT]) or not r[iG].strip().isdigit():
                bad += 1
                continue
            t = Decimal(r[iT]) * 1000000
            if t != t.to_integral_value():
                bad += 1
                continue
            ev.append((int(r[iG]), int(t), int((Decimal(r[iP]) * 100).to_integral_value(ROUND_HALF_UP))))
    return ev, bad


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


MANIFEST = os.path.join(RAW, "gpu_fetch.tsv")


def fetch():
    """按切片规则依次取文件：候选按键的字典序，跳过 > 60 MB 的，下载、数事件，累计 ≥ N_A 停。清单 → data/raw/gpu_fetch.tsv。"""
    os.makedirs(GDIR, exist_ok=True)
    rows, total = [], 0
    for key, size, model, skip in candidates():
        if skip:
            rows.append((key, size, model, "跳过（> 60 MB）", "-", 0, 0, 0))
            continue
        path = local(key)
        if not (os.path.exists(path) and os.path.getsize(path) == size):
            tmp = path + ".part"
            urllib.request.urlretrieve(BASE + "/" + key, tmp)
            if os.path.getsize(tmp) != size:
                sys.exit("大小不符：%s" % key)
            os.replace(tmp, path)
        ev, bad = read_file(path)
        total += len(ev)
        rows.append((key, size, model, "取", sha256(path), len(ev), bad, len({g for g, _, _ in ev})))
        print("%s  %d 个事件（丢 %d 行）累计 %d" % (key.rsplit("/", 2)[-2] + "/" + key.rsplit("/", 1)[-1], len(ev), bad, total), file=sys.stderr)
        if total >= N_A:
            break
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("key\tbytes\tmodel\tstatus\tsha256\tevents\tdropped_rows\tgpus\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    print("取了 %d 个文件、跳过 %d 个（> 60 MB），累计 %d 个事件 ≥ N_A = %d" % (
        sum(1 for r in rows if r[3] == "取"), sum(1 for r in rows if r[3] != "取"), total, N_A))


def manifest():
    lines = open(MANIFEST, encoding="utf-8").read().splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def build():
    """→ data/gpu_hold.tsv：组 = <文件名去 .csv>:<gpu_index>；按（时间, 文件序, 行序）排序，时间减整条流最早时间。
    另写 handoff/e9_files_gpu.txt。"""
    rows = []
    man = manifest()
    taken = [m for m in man if m["status"] == "取"]
    for fi, m in enumerate(taken):
        path = local(m["key"])
        if sha256(path) != m["sha256"]:
            sys.exit("sha256 不符：%s" % m["key"])
        base = m["key"].rsplit("/", 1)[-1][:-4]
        ev, _ = read_file(path)
        for ri, (g, t, x) in enumerate(ev):
            rows.append(("%s:%d" % (base, g), t, x, fi, ri))
    rows.sort(key=lambda r: (r[1], r[3], r[4]))
    t0 = rows[0][1]
    with open(OUT, "w", encoding="utf-8") as f:
        for g, t, x, _, _ in rows:
            f.write("%s\t%d\t%d\n" % (g, t - t0, x))
    os.makedirs(os.path.dirname(FILES), exist_ok=True)
    with open(FILES, "w", encoding="utf-8") as f:
        f.write("# E9 流 A 的切片（README 第 2 节）：MIT Supercloud Dataset 202201，%s/<键>\n" % BASE)
        f.write("# 规则：作业号在 labelled_jobids.csv 里的 gpu/ 文件，按键的字典序；跳过 > 60 MB 的文件；依次取到累计事件数 ≥ N_A = %d\n" % N_A)
        f.write("# 取到第 %d 个文件为止（%s），共 %d 个事件、%d 个组；跳过 %d 个 > 60 MB 的文件；丢弃的行（power_draw_W 或时间不是数）%d\n" % (
            len(taken), taken[-1]["key"], len(rows), len({r[0] for r in rows}), sum(1 for m in man if m["status"] != "取"),
            sum(int(m["dropped_rows"]) for m in taken)))
        f.write("# 许可 CC BY-NC-ND 4.0：工件只放本清单与下载脚本（prep_e9_gpu.py list / fetch / build），不放数据\n")
        f.write("key\tbytes\tmodel\tstatus\tsha256\tevents\tdropped_rows\tgpus\n")
        for m in man:
            f.write("\t".join(m[h] for h in ("key", "bytes", "model", "status", "sha256", "events", "dropped_rows", "gpus")) + "\n")
    print("gpu_hold：%d 个事件、%d 个组 → %s" % (len(rows), len({r[0] for r in rows}), OUT))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "list":
        list_keys()
    elif cmd == "fetch":
        fetch()
    elif cmd == "build":
        build()
    else:
        print(__doc__); sys.exit(2)
