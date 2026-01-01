#!/usr/bin/env python3
"""E11 · 合成流 n = 10⁶ 上补跑的两格（README 第 1 节）：描述性，不设判据。

读 handoff/e11_times.tsv（本实验的计时遍）与 exp/e8-inpane/handoff/e5_times_v2.tsv（E5 的预计值、E8 里同格 SlotTree 的时间），
写 report_e11.txt。每格报：T_GRETA-C++（单次计时）、T_SlotTree（3 遍中位）、r、实测 ÷ 预计、峰值内存、校验和是否一致。
校验和不一致的格作废、不进论文。用法：python3 -I exp/e11-synth-1e6/compare_e11.py
"""
import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
E5V2 = os.path.join(HERE, "..", "e8-inpane", "handoff", "e5_times_v2.tsv")
CELL = ("rw", "1000000", "1", "0")  # 分布、n、G、突发


def rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main():
    mine = rows(os.path.join(HERE, "handoff", "e11_times.tsv"))
    ref = [r for r in rows(E5V2) if (r["dist"], r["n"], r["G"], r["burst"]) == CELL]
    out = ["E11 · 合成流 n = 10⁶ 上补跑 GRETA-C++ 的两格（描述性，不设判据；主实验之后加的格，README 开头）",
           "流 rw-n1000000-g1-b0：随机游走、1 组、W = 600 s、COUNT、⋈ 为 >；GRETA-C++ 单次计时，SlotTree 取 3 遍中位", ""]
    out.append("\t".join(["k", "事件", "T_GRETA-C++ 秒", "T_SlotTree 秒", "r", "E5 的预计 秒", "实测÷预计",
                          "E8 表里 SlotTree 秒", "峰值 MB GRETA-C++", "峰值 MB SlotTree", "校验和一致"]))
    for k in sorted({r["k"] for r in mine}, key=int):
        opp = [r for r in mine if r["k"] == k and r["arm"] == "OPP"]
        m = [r for r in mine if r["k"] == k and r["arm"] == "M"]
        if not opp or not m:
            out.append("%s\t没跑完（GRETA-C++ %d 遍、SlotTree %d 遍）" % (k, len(opp), len(m)))
            continue
        t_opp = float(opp[0]["seconds"])
        t_m = statistics.median(float(r["seconds"]) for r in m)
        sums = {r["checksum"] for r in opp + m}
        pred = [r["pred_s"] for r in ref if r["k"] == k and r["arm"] == "OPP" and r["mode"] == "skip"]
        e8m = [float(r["seconds"]) for r in ref if r["k"] == k and r["arm"] == "M" and r["mode"] != "skip"]
        mb = lambda rs: max(int(r["maxrss_kb"]) for r in rs) / 1024.0
        out.append("\t".join([k, opp[0]["events"], "%.4f" % t_opp, "%.4f" % t_m, "%.1f" % (t_opp / t_m),
                              pred[0] if pred else "-", ("%.3f" % (t_opp / float(pred[0]))) if pred else "-",
                              ("%.4f" % statistics.median(e8m)) if e8m else "-", "%.0f" % mb(opp), "%.0f" % mb(m),
                              "是" if len(sums) == 1 else "否（该格作废）"]))
    out += ["", "对照（exp/e8-inpane/report_e5_v2.txt S1）：n = 10⁵ 时 12 格的 r 为 115–376；n = 10⁶ 其余 10 个 GRETA-C++ 格仍是预计、没跑。"]
    envp = os.path.join(HERE, "handoff", "e11_env.txt")
    if os.path.exists(envp):
        out += ["", "机器与负载（handoff/e11_env.txt）："] + ["  " + line.rstrip("\n") for line in open(envp, encoding="utf-8")]
    text = "\n".join(out) + "\n"
    with open(os.path.join(HERE, "report_e11.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
