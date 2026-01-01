# M1 · 一个二进制：make → out/trend（out/ 被忽略）。编译选项与编译器版本记进 README 第 3 节。
CXX := /usr/bin/clang++
CXXFLAGS ?= -O2 -std=c++20 -Wall -Wextra
out/trend: src/trend.cpp
	mkdir -p out
	$(CXX) $(CXXFLAGS) -o $@ $<
clean:
	rm -f out/trend
.PHONY: clean
