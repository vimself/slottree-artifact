"""E10 · 正确性闸 (b)（README 第 1 节「通用」）：回放流 R(100) 与部分 B 的全部模型流，每组前 2,000 个事件（文件顺序，同引擎的 --limit），
引擎 --dump 的逐窗口输出与 exp/e1-main/brute_e1.py 的递推参考逐行相同。直接调用 exp/e9-aiinfra/tests/gate_e9.py 的 main（import，不复制）：
5 个引擎配置（OPP；M c = 2、B = 1024；M c = 0.001；M c = 10⁹；A4）× COUNT / SUM；W 取各流在本实验里跑的 W
（R(100)：10、30 分 = 部分 A；全部模型：5、10、30 分 = 部分 B）。纯标准库。

用法：python3 -I exp/e10-aiinfra-scale/tests/gate_e10.py <二进制> <replay_G100.tsv> <llm_all.tsv>   全过退出码 0
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
G9 = os.path.normpath(os.path.join(HERE, "..", "..", "e9-aiinfra", "tests"))
if G9 not in sys.path:
    sys.path.insert(0, G9)
import gate_e9  # noqa: E402

if __name__ == "__main__":
    binary, r100, llmall = sys.argv[1:4]
    bad = 0
    for path, ws in ((r100, (600, 1800)), (llmall, (300, 600, 1800))):
        gate_e9.WS = ws
        print("—— %s：W = %s 分" % (os.path.basename(path), " / ".join(str(w // 60) for w in ws)), flush=True)
        bad += gate_e9.main(binary, [path])
    print("闸 (b) E10：%s" % ("全过" if bad == 0 else "有不一致"))
    sys.exit(1 if bad else 0)
