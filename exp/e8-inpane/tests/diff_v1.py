"""E8 · v2 引擎与 v1（exp/e1-main/src/trend.cpp，冻结）的 diff（README 第 2 节「与 v1 的 diff 在哪一段」）。纯标准库。
每一处改动归到它所在的顶层块（往上找最近的顶格 struct / static / template / int main 行），打印块名与改动行；
改动只许落在：文件头注释、ArmM、Opt、Result、run_arm_lat、run_arm、dispatch、main。落到别处（OPP、Scan、ScanC、Tree、A1、Fin…）退出码 1。
用法：python3 -I exp/e8-inpane/tests/diff_v1.py
"""
import difflib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.join(HERE, "..", "..", "e1-main", "src", "trend.cpp")
V2 = os.path.join(HERE, "..", "src", "trend.cpp")
ALLOWED = {"文件头", "ArmM", "Opt", "Result", "run_arm_lat", "run_arm", "dispatch", "main"}
DECL = re.compile(r"^(?:template\s*<.*>\s*)?(?:struct\s+(\w+)|static\s+[\w:<>, ]+?\b(\w+)\s*\(|int\s+(main)\s*\()")


def owner(lines, i):
    """第 i 行（0 起）所在的顶层块名；template 行单独一行时看下一行。"""
    for j in range(min(i, len(lines) - 1), -1, -1):
        l = lines[j]
        if l.startswith("template") and j + 1 < len(lines) and not DECL.match(l):
            l = lines[j + 1]
        m = DECL.match(l)
        if m:
            return next(g for g in m.groups() if g)
    return "文件头"


a = open(V1, encoding="utf-8").read().split("\n")
b = open(V2, encoding="utf-8").read().split("\n")
blocks = {}
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
    if tag == "equal":
        continue
    name = owner(a, i1 if i1 < len(a) else len(a) - 1) if i1 > 0 else "文件头"
    blocks.setdefault(name, []).append((i1 + 1, a[i1:i2], b[j1:j2]))
bad = sorted(set(blocks) - ALLOWED)
for name, hs in blocks.items():
    print("== %s：%d 处改动" % (name, len(hs)))
    for ln, old, new in hs:
        for l in old:
            print("   v1:%d - %s" % (ln, l.strip()[:150]))
        for l in new:
            print("          + %s" % l.strip()[:150])
print("改动所在的块：%s；不许改的块里有改动：%s" % ("、".join(blocks), "、".join(bad) if bad else "无"))
sys.exit(1 if bad else 0)
