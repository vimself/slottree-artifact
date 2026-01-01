# E8 v2 引擎 · 一个二进制：make → out/trend（out/ 被忽略）。编译选项、编译器同 E1（exp/e1-main/Makefile）。
CXX := /usr/bin/clang++
CXXFLAGS ?= -O2 -std=c++20 -Wall -Wextra
out/trend: src/trend.cpp
	mkdir -p out
	$(CXX) $(CXXFLAGS) -o $@ $<
clean:
	rm -f out/trend
.PHONY: clean
