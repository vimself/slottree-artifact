"""E1 · OPP 路径与 M1 的 diff（README 第 2.1 节「OPP 路径不动，差异用 diff 核」）。纯标准库。
用法：python3 -I tests/diff_opp.py → 逐块打印 diff；OPP 路径上的块（Fin、Scan、ArmBase、own_from_acc、ArmOPP）。"""
import difflib, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
M1 = os.path.join(HERE, "..", "..", "m1-trend-index", "src", "trend.cpp")
E1 = os.path.join(HERE, "..", "src", "trend.cpp")


def block(text, start):
    """从含 start 的那一行（连同它上面紧挨的 template 行）到第一个顶格的 `};` 或 `}`。"""
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if re.match(start, l):
            j0 = i - 1 if i > 0 and lines[i - 1].startswith("template") else i
            for j in range(i, len(lines)):
                if lines[j] in ("};", "}"):
                    return lines[j0:j + 1]
    raise SystemExit("找不到 " + start)


m1, e1 = open(M1, encoding="utf-8").read(), open(E1, encoding="utf-8").read()
for name, pat in [("Fin", r"struct Fin \{"), ("Scan", r"struct Scan \{"), ("own_from_acc", r"static inline void own_from_acc"),
                  ("ArmBase", r"struct ArmBase \{"), ("ArmOPP", r"struct ArmOPP : ArmBase \{")]:
    d = list(difflib.unified_diff(block(m1, pat), block(e1, pat), "M1", "E1", lineterm="", n=0))
    print("== %s：%s" % (name, "与 M1 相同" if not d else "%d 行不同" % sum(1 for l in d if l[:1] in "+-" and l[:3] not in ("+++", "---"))))
    for l in d[2:]:
        print("   " + l)
