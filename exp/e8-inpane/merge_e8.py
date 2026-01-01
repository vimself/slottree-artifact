"""E8 · 把重跑的 M / A2 行与 v1 表里别的臂拼成与原实验同构的 v2 表（README 第 2 节「产出」）。纯标准库。

规则：按 v1 表的行序走；某个（臂, 行键）是重跑过的，就在它第一次出现的位置换成新跑的全部行，其余 v1 行原样复制。列与表头和 v1 逐字相同。
  E1  ../e1-main/handoff/e1_times.tsv + logs/e1_new.tsv（M、A2）            → handoff/e1_times_v2.tsv
      ../e1-main/handoff/e1_rerun_binance.tsv + e1_new 里同一格的 M、A2     → handoff/e1_rerun_binance_v2.tsv（E1 偏离 2 那一格；表 2 用它）
  E2  ../e2-sweep/handoff/e2_times.tsv + logs/e2_new.tsv（M）               → handoff/e2_times_v2.tsv
  E5  ../e5-synth/handoff/e5_times.tsv + logs/e5_new.tsv（M）               → handoff/e5_times_v2.tsv；logs/e5_a4_recheck.tsv 原样 → handoff/
  E6  ../e6-latency/handoff/e6_latency.tsv、e6_dist.tsv + logs/e6_*new.tsv（M、A2）→ handoff/e6_latency_v2.tsv、e6_dist_v2.tsv
  E7  ../e7-platform/handoff/e7_times.tsv + relay 回传的 handoff/e7_m_v2.tsv（M）→ handoff/e7_times_v2.tsv（回传到了才拼）
  OPP 旁证 logs/opp_new.tsv → handoff/e8_opp_check.tsv；窗格内切换 logs/e8_inpane_*.tsv 与回传的 handoff/e7_inpane_v2.tsv → handoff/e8_inpane.tsv
缺哪份新跑的就跳过哪份。用法：python3 -I exp/e8-inpane/merge_e8.py
"""
import os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
H, LOG = os.path.join(HERE, "handoff"), os.path.join(HERE, "logs")
K_E1 = ("arm", "data", "split", "agg", "W", "xnum")
K_E5 = ("set", "dist", "n", "G", "burst", "k", "arm")
K_E6 = ("arm", "data", "split", "agg", "W")
K_E6D = ("arm", "data", "W")


def read(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    head = lines[0].split("\t")
    return lines[0], head, [l for l in lines[1:] if l]


def merge(v1, new, keys, out, only=None):
    """only：只从 new 里取满足条件的行（dict → bool）。返回 (换掉的组数, 新行数)。"""
    h1, head, rows1 = read(v1)
    h2, head2, rows2 = read(new)
    assert head == head2, "表头不同：%s vs %s" % (v1, new)
    idx = [head.index(k) for k in keys]
    key = lambda l: tuple(l.split("\t")[i] for i in idx)
    groups = {}
    for l in rows2:
        if only is None or only(dict(zip(head, l.split("\t")))):
            groups.setdefault(key(l), []).append(l)
    done, outl = set(), [h1]
    for l in rows1:
        k = key(l)
        if k in groups:
            if k not in done:
                outl += groups[k]; done.add(k)
            continue
        outl.append(l)
    for k, ls in groups.items():  # v1 里没有的组（不该有）
        if k not in done:
            outl += ls
    open(out, "w", encoding="utf-8").write("\n".join(outl) + "\n")
    print("%s：换掉 %d 组（%d 行新数据）%s" % (os.path.relpath(out, EXP), len(done), sum(len(v) for v in groups.values()),
                                       "；v1 里没有的组 %d 个" % (len(groups) - len(done)) if len(groups) > len(done) else ""))


def main():
    os.makedirs(H, exist_ok=True)
    j = os.path.join
    if os.path.exists(j(LOG, "e1_new.tsv")):
        merge(j(EXP, "e1-main", "handoff", "e1_times.tsv"), j(LOG, "e1_new.tsv"), K_E1, j(H, "e1_times_v2.tsv"))
        merge(j(EXP, "e1-main", "handoff", "e1_rerun_binance.tsv"), j(LOG, "e1_new.tsv"), K_E1, j(H, "e1_rerun_binance_v2.tsv"),
              only=lambda r: r["data"] == "binance" and r["split"] == "hold" and r["agg"] == "COUNT" and r["W"] == "600")
    if os.path.exists(j(LOG, "e2_new.tsv")):
        merge(j(EXP, "e2-sweep", "handoff", "e2_times.tsv"), j(LOG, "e2_new.tsv"), K_E1, j(H, "e2_times_v2.tsv"))
    if os.path.exists(j(LOG, "e5_new.tsv")):
        merge(j(EXP, "e5-synth", "handoff", "e5_times.tsv"), j(LOG, "e5_new.tsv"), K_E5, j(H, "e5_times_v2.tsv"))
    if os.path.exists(j(LOG, "e5_a4_recheck.tsv")):
        shutil.copy(j(LOG, "e5_a4_recheck.tsv"), j(H, "e5_a4_recheck.tsv"))
    if os.path.exists(j(LOG, "e6_new.tsv")):
        merge(j(EXP, "e6-latency", "handoff", "e6_latency.tsv"), j(LOG, "e6_new.tsv"), K_E6, j(H, "e6_latency_v2.tsv"))
        merge(j(EXP, "e6-latency", "handoff", "e6_dist.tsv"), j(LOG, "e6_dist_new.tsv"), K_E6D, j(H, "e6_dist_v2.tsv"))
    if os.path.exists(j(H, "e7_m_v2.tsv")):
        merge(j(EXP, "e7-platform", "handoff", "e7_times.tsv"), j(H, "e7_m_v2.tsv"), K_E1, j(H, "e7_times_v2.tsv"))
    if os.path.exists(j(LOG, "opp_new.tsv")):
        shutil.copy(j(LOG, "opp_new.tsv"), j(H, "e8_opp_check.tsv"))
    side = [j(LOG, "e8_inpane_%s.tsv" % m) for m in ("e1", "e2", "e5", "e6", "opp")] + [j(H, "e7_inpane_v2.tsv")]  # E7 的由 relay 回传
    side = [p for p in side if os.path.exists(p)]
    if side:
        with open(j(H, "e8_inpane.tsv"), "w", encoding="utf-8") as f:
            f.write("exp\trow\tarm\tproc\tinpane_switches\tswitches\n")
            for p in side:
                f.write(open(p, encoding="utf-8").read())
        print("handoff/e8_inpane.tsv：%d 份" % len(side))


if __name__ == "__main__":
    main()
