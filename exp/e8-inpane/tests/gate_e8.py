"""E8 · 闸 (a)(c)(a′) 对 v2 引擎：直接 import E1 的 `brute_e1.gate` 与 `tests/brute_enum.main`（不复制），只在它们的臂配置表后面追加
窗格内检查的配置。v2 默认 B = 1024，小合成流里一个窗格到不了 1024 个事件、新代码走不到 ⇒ 追加 B ∈ {1, 2} 的 M / A2，
c 取极小（每个窗格的第 B 个事件就切到索引）与 0.05–0.2（窗格内切入、窗格边界按 EWMA 切回，来回切换），保证「窗格内 扫描 → 索引、边界 索引 → 扫描」都被走到。
另加 (v) 一项：每个追加配置在多少条流上真的发生了窗格内切换（引擎的 inpane_switches 行），其中多少条还有别的切换（边界切回等，
切换总数 > 窗格内切换数）；窗格内切换为 0 的配置说明没测到新代码，记失败。

用法：python3 -I exp/e8-inpane/tests/gate_e8.py <v2 二进制> [流数 = 300]   → 错一项退出码 1
"""
import os, random, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.join(HERE, "..", "..", "e1-main")
for p in (E1, os.path.join(E1, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)
import brute_e1  # noqa: E402
import brute_enum  # noqa: E402

# 追加的窗格内检查配置（v1 的配置原样保留在表前面；它们在 v2 上跑的是默认 B = 1024）
# c 取小值：小流上每事件的扫描代价只有个位数，c = 2 的线（s̄ > 4 ī）几乎碰不到；c ∈ [0.05, 0.2] 时多数流既有窗格内切入、又有边界切回
INPANE = [("M", ["--c", "0.001", "--inpane", "1"]), ("M", ["--c", "0.05", "--inpane", "1"]), ("M", ["--c", "0.1", "--inpane", "2"]),
          ("M", ["--c", "0.2", "--inpane", "1"]), ("A2", ["--c", "0.001", "--inpane", "1"]), ("A2", ["--c", "0.1", "--inpane", "1"])]
brute_e1.ARMS = brute_e1.ARMS + INPANE
brute_e1.TRACE_ARMS = brute_e1.TRACE_ARMS + INPANE
brute_enum.CONFS = brute_enum.CONFS + INPANE


def coverage(binary, n):
    """(v)：在闸 (a) 的同一串合成流上，每个追加配置有几条流发生了窗格内切换。"""
    import brute_m1 as m1
    rnd = random.Random(1971)
    hit = {i: 0 for i in range(len(INPANE))}
    rt = {i: 0 for i in range(len(INPANE))}
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "s.tsv")
        for _ in range(n):
            text, W, s, op = m1.synth(rnd)
            open(path, "w", encoding="utf-8").write(text)
            for i, (arm, extra) in enumerate(INPANE):
                out = subprocess.run([binary, "--arm", arm, "--data", path, "--W", str(W), "--s", str(s), "--op", op,
                                      "--agg", "COUNT", "--reps", "1", "--warmup", "0"] + extra, capture_output=True, text=True).stdout
                v = dict(l.split("\t", 1) for l in out.splitlines() if "\t" in l)
                ip = int(v.get("inpane_switches", "0"))
                if ip > 0:
                    hit[i] += 1
                    rt[i] += int(v["switches"]) > ip
    bad = 0
    for i, (arm, extra) in enumerate(INPANE):
        print("  (v) %s %s：%d / %d 条流发生了窗格内切换，其中 %d 条另有别的切换" % (arm, " ".join(extra), hit[i], n, rt[i]))
        bad += hit[i] == 0
    print("闸 (v) 覆盖：%d 个追加配置里没走到窗格内切换的 %d 个" % (len(INPANE), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    b, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 300
    print("追加配置（%d 个）：%s" % (len(INPANE), "；".join("%s %s" % (a, " ".join(e)) for a, e in INPANE)))
    r1 = brute_e1.gate(b, n)
    r2 = brute_enum.main(b, n)
    r3 = coverage(b, n)
    sys.exit(1 if r1 or r2 or r3 else 0)
