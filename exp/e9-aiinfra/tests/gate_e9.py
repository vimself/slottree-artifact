"""E9 · 正确性闸 (b)（README 第 2 节「正确性闸」）：每条流每组前 2,000 个事件（文件顺序，同引擎的 --limit）× W ∈ {5, 10, 30} 分 × COUNT / SUM，
引擎 --dump 的逐窗口输出与 exp/e1-main/brute_e1.py 的递推参考（brute，import 不复制）逐行相同。纯标准库；递推参考按（组, W, AGG）分进程并行。
引擎配置：计时用的两臂（OPP；M = SlotTree，c = 2、B = 1024），另加 M c = 0.001（一开窗就切索引）、M c = 10⁹（始终扫描）、A4（始终索引）。

用法：python3 -I exp/e9-aiinfra/tests/gate_e9.py <二进制> <数据 tsv>…   全过退出码 0
"""
import multiprocessing as mp, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.normpath(os.path.join(HERE, "..", "..", "e1-main"))
if E1 not in sys.path:
    sys.path.insert(0, E1)
import brute_e1  # noqa: E402

m1 = brute_e1.m1
S = 30 * 1000000
OP = "<"
WS = (300, 600, 1800)
AGGS = ("COUNT", "SUM")
LIMIT = 2000
CONFS = [["--arm", "OPP"], ["--arm", "M", "--c", "2", "--inpane", "1024"], ["--arm", "M", "--c", "0.001", "--inpane", "1024"],
         ["--arm", "M", "--c", "1e9", "--inpane", "1024"], ["--arm", "A4"]]


def head(path):
    """每组前 LIMIT 个事件（文件顺序；文件已按时间排好，组内即到达序）。"""
    groups = {}
    for line in open(path, encoding="utf-8"):
        g, t, a = line.rstrip("\n").split("\t")
        ev = groups.setdefault(g, [])
        if len(ev) < LIMIT:
            ev.append((int(t), int(a)))
    return groups


def ref(task):
    g, ev, W, agg = task
    return (g, W, agg), m1.fmt(brute_e1.brute({g: ev}, W * 1000000, S, OP, agg, 1000))


def main(binary, paths):
    bad = runs = 0
    ctx = mp.get_context("spawn")
    for path in paths:
        t0 = time.time()
        groups = head(path)
        tasks = [(g, ev, W, agg) for g, ev in groups.items() for W in WS for agg in AGGS]
        tasks.sort(key=lambda x: -len(x[1]) * x[2])
        with ctx.Pool(os.cpu_count()) as pool:
            out = dict(pool.imap_unordered(ref, tasks))
        nwin = 0
        for W in WS:
            for agg in AGGS:
                want = "".join(out[(g, W, agg)] for g in sorted(groups))
                nwin += want.count("\n")
                for conf in CONFS:
                    cmd = [binary] + conf + ["--data", path, "--limit", str(LIMIT), "--W", str(W * 1000000), "--s", str(S), "--op", OP,
                                             "--agg", agg, "--reps", "1", "--warmup", "0", "--dump", "-"]
                    got = subprocess.run(cmd, capture_output=True, text=True)
                    runs += 1
                    if got.returncode != 0 or got.stdout != want:
                        bad += 1
                        print("不一致 (b)：%s W=%d %s %s" % (os.path.basename(path), W // 60, agg, " ".join(conf)))
        print("闸 (b) %s：%d 个组 × 每组前 %d 个事件（共 %d 个）、%d 个（组, 窗口, W, AGG），%d 个引擎配置；递推参考 %.0f s" % (
            os.path.basename(path), len(groups), LIMIT, sum(len(v) for v in groups.values()), nwin, len(CONFS), time.time() - t0))
    print("闸 (b)：%d 次引擎运行与递推参考逐窗口比对，不一致 %d" % (runs, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
