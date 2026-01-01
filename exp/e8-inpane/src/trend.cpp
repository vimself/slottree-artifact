// E8 v2 引擎：exp/e1-main/src/trend.cpp（v1，冻结）复制后只加「窗格内检查」（exp/e8-inpane/README.md 第 2 节）：
//   ArmM::process 的代价规则块、ArmM::init 的 B 参数、--inpane B（默认 1024；0 = 关，与 v1 的决策逐事件相同）、输出 inpane_switches。
//   其余（OPP、A1、树、扫描、驱动）与 v1 逐字相同；diff 见 tests/diff_v1.py。
// 以下为 v1 文件头。
// E1 定稿引擎（从 M1 的 src/trend.cpp 复制后改；M1 冻结）。臂：OPP（GRETA 运行时复现，与 M1 同）、
// M（窗口槽聚合树 + 代价规则选择器，exp/e4-lowfreq/README.md 第 1 节）、A1、A2（过期逐个删）、A4（始终索引）、A5（M1 的规模阈值）。
// 规格：exp/e1-main/README.md 第 2 节、exp/e4-lowfreq/README.md 第 2.1 节、exp/m1-trend-index/README.md 第 2 节。
// 单线程；算术取模 2^64；整数属性；时间整数（与 W、s 同单位）。
//
// 用法：trend --arm OPP|M|A1|A2|A4|A5 --data <tsv> --W <W> --s <s> --op '>'|'<' --agg COUNT|SUM
//             [--c <c>]（M / A2 的代价规则常数，必给）[--rule cost|size|none] [--tau 16] [--expire compact|delete]
//             [--reps 5] [--warmup 1] [--autopasses] [--copies D] [--xnum 1000]
//             [--opp-index vec|map] [--limit N] [--dump <文件>|-] [--work] [--trace <文件>] [--inpane B]
// 输出（stdout）：warm <秒>、time <rep> <秒>、reps、checksum、outputs、switches、compactions、maxrss_kb；
//   --work 时另跑一次只计数不计时：work_pred / work_adds / work_nodes、idx_events（索引模式处理的事件数）、ratio_med（s̄ ÷ ī 的中位）；
//   --trace（要 --work）：逐事件写「组 \t 扫描代价」，扫描代价 = 按 OPP 处理该事件的窗口累加次数（闸 (c)）
//   --latency <文件>（E6，exp/e6-latency/README.md 第 1 节；默认关）：预热遍照常，计时遍改成逐事件计时（每个 process 调用
//   前后各读一次 steady_clock，含它触发的窗格边界工作）；每遍 stdout 一行 lat、四行 latcat，直方图与前 100 大值写进 <文件>；
//   另先做一次时钟标定（clock 行）。关着时计时遍的循环与原来逐字相同（run_arm 开头多一个指针判空）
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <map>
#include <numeric>
#include <string>
#include <sys/resource.h>
#include <unordered_map>
#include <vector>

using u64 = uint64_t;
using i64 = int64_t;
using u32 = uint32_t;
using i32 = int32_t;
static constexpr i64 NONE = INT64_MIN;

// ---------------------------------------------------------------- 工作量计数（--work 单独一次调用）
struct Work {
    u64 pred = 0;   // OPP：被遍历的前驱个数
    u64 adds = 0;   // OPP：窗口累加次数；A1 / M：槽读写次数
    u64 nodes = 0;  // M / A1：结点访问次数
};
static Work WK;

// ---------------------------------------------------------------- 流
struct Stream {
    std::vector<std::string> gname;
    std::vector<i32> g;
    std::vector<i64> t, a;
    size_t n() const { return g.size(); }
};

static Stream load(const char* path, long limit, int copies, i64 s) {
    Stream S;
    FILE* f = fopen(path, "r");
    if (!f) { perror(path); exit(2); }
    std::unordered_map<std::string, i32> id;
    std::vector<long> seen;
    char buf[512];
    std::vector<i32> g; std::vector<i64> t, a;
    while (fgets(buf, sizeof buf, f)) {
        char* p1 = strchr(buf, '\t'); if (!p1) continue;
        *p1 = 0;
        char* p2 = strchr(p1 + 1, '\t'); if (!p2) continue;
        auto it = id.find(buf);
        i32 gi;
        if (it == id.end()) { gi = (i32)S.gname.size(); id.emplace(buf, gi); S.gname.emplace_back(buf); seen.push_back(0); }
        else gi = it->second;
        if (limit > 0 && seen[gi] >= limit) continue;
        seen[gi]++;
        g.push_back(gi); t.push_back(strtoll(p1 + 1, nullptr, 10)); a.push_back(strtoll(p2 + 1, nullptr, 10));
    }
    fclose(f);
    // 全局按时间处理（各组交错）：按时间稳定排序；同一时刻按组在文件里的先后、再按文件顺序
    std::vector<u32> ord(g.size());
    std::iota(ord.begin(), ord.end(), 0);
    std::stable_sort(ord.begin(), ord.end(), [&](u32 x, u32 y) { return t[x] < t[y]; });
    S.g.resize(g.size()); S.t.resize(g.size()); S.a.resize(g.size());
    for (size_t i = 0; i < ord.size(); i++) { S.g[i] = g[ord[i]]; S.t[i] = t[ord[i]]; S.a[i] = a[ord[i]]; }
    // 短行加长（E1 第 1 节）：流复制 D 份首尾相接，第 c 份时间平移 c × 整段时长（按整窗格取整，窗格对齐、不重叠）；组与顺序不变
    if (copies > 1 && S.n() > 0) {
        size_t n0 = S.n(); i64 span = ((S.t[n0 - 1] - S.t[0]) / s + 1) * s;
        S.g.reserve(n0 * copies); S.t.reserve(n0 * copies); S.a.reserve(n0 * copies);
        for (int c = 1; c < copies; c++)
            for (size_t i = 0; i < n0; i++) { S.g.push_back(S.g[i]); S.t.push_back(S.t[i] + c * span); S.a.push_back(S.a[i]); }
    }
    return S;
}

struct Query { bool gt; i64 W, s; int k; bool sum; i64 xnum = 1000; };

// E2 的选择度谓词 a_p · X_num ⋈ a_e · 1000：换成对 a_p 的整数阈值 θ（> 时 a_p > θ，< 时 a_p < θ），树与顶点树照常按 a_p 查
static inline i64 thr(const Query& q, i64 a) {
    __int128 num = (__int128)a * 1000, d = q.xnum;
    __int128 fl = num / d; bool exact = num % d == 0;
    if (!exact && ((num < 0) != (d < 0))) fl--;
    if (q.gt) return (i64)fl;                 // a_p·X > a_e·1000 ⇔ a_p > ⌊a_e·1000 / X⌋
    return (i64)(exact ? fl : fl + 1);        // a_p·X < a_e·1000 ⇔ a_p < ⌈a_e·1000 / X⌉
}

// ---------------------------------------------------------------- 每组的最终聚合：按窗口号模 k 的环，槽被新窗口占用时把旧窗口输出
struct Fin {
    std::vector<i64> wid; std::vector<u64> val;
    std::vector<std::pair<i64, u64>> out;
    void init(int k) { wid.assign(k, NONE); val.assign(k, 0); out.clear(); }
    // own[o] 是窗口 j0 + o 上本事件的贡献，o ∈ [0, k)；窗口 j0 + o 的槽号 (base + o) mod k
    inline void add(int k, i64 j0, int base, const u64* own) {
        for (int o = 0; o < k; o++) {
            int i = base + o; if (i >= k) i -= k;
            i64 j = j0 + o;
            if (wid[i] != j) { if (wid[i] != NONE) out.emplace_back(wid[i], val[i]); wid[i] = j; val[i] = 0; }
            val[i] += own[o];
        }
    }
    void flush() { for (size_t i = 0; i < wid.size(); i++) if (wid[i] != NONE) { out.emplace_back(wid[i], val[i]); wid[i] = NONE; } }
};

// 一个顶点（事件）的数据块：cnt[k]（+ sum[k]），按「相对本事件第一个窗口的偏移」存：o = j − (π − k + 1)
// GRETA 原文每个顶点一个窗口哈希表；这里换成密集数组，对它有利（README 第 2.2 节第 2 条）

// ================================================================ OPP：GRETA 运行时（每组、每窗格一棵按 a 有序的顶点树）
// 顶点树两种实现，取快的（README 第 2.2 节第 1 条）：vec = 有序数组（单叶 B 树，范围扫描连续），map = std::multimap
template <bool SUM, bool CW, bool MAP>
struct Scan {
    struct Pane {
        i64 id = NONE;
        std::vector<std::pair<i64, u32>> idx;  // (a, 局部号)，按 a 有序；同值按到达序
        std::multimap<i64, u32> mp;
        std::vector<u64> data;                 // 局部号 × K2
        std::vector<i64> av; std::vector<u32> seq;
        void clear() { id = NONE; idx.clear(); mp.clear(); data.clear(); av.clear(); seq.clear(); }
        size_t size() const { return av.size(); }
    };
    int k = 0, K2 = 0;
    std::vector<Pane> ring;  // 按窗格号模 k
    std::deque<int> live;    // 存在的窗格（环里的位置），窗格号递增
    size_t n = 0;

    void init(int k_) { k = k_; K2 = SUM ? 2 * k : k; ring.assign(k, Pane()); live.clear(); n = 0; }

    // 窗格 π' ≤ π − k 已为它所属的全部窗口贡献完，整体删除（GRETA §7 pane purge）
    void purge(i64 pi) {
        while (!live.empty() && ring[live.front()].id <= pi - k) { n -= ring[live.front()].size(); ring[live.front()].clear(); live.pop_front(); }
    }

    // 逐个合格前驱、逐个共同窗口累加（GRETA Alg. 2 第 8–10 行，§8 Thm 4 证明）
    inline void query(i64 pi, i64 a, bool gt, u64* ac, u64* as) {
        for (int slot : live) {
            Pane& P = ring[slot];
            int d = (int)(pi - P.id), len = k - d;
            auto body = [&](u32 li) {
                const u64* c = &P.data[(size_t)li * K2] + d;
                for (int o = 0; o < len; o++) ac[o] += c[o];
                if constexpr (SUM) { const u64* s = c + k; for (int o = 0; o < len; o++) as[o] += s[o]; }
                if constexpr (CW) { WK.pred++; WK.adds += len; }
            };
            if constexpr (MAP) {
                if (gt) for (auto it = P.mp.upper_bound(a); it != P.mp.end(); ++it) body(it->second);
                else for (auto it = P.mp.begin(), e = P.mp.lower_bound(a); it != e; ++it) body(it->second);
            } else {
                auto cmp = [](const std::pair<i64, u32>& x, i64 v) { return x.first < v; };
                auto cmp2 = [](i64 v, const std::pair<i64, u32>& x) { return v < x.first; };
                if (gt) { for (auto it = std::upper_bound(P.idx.begin(), P.idx.end(), a, cmp2); it != P.idx.end(); ++it) body(it->second); }
                else { for (auto it = P.idx.begin(), e = std::lower_bound(P.idx.begin(), P.idx.end(), a, cmp); it != e; ++it) body(it->second); }
            }
        }
    }

    // own：长 K2 的块（cnt[k]，SUM 时再接 sum[k]），偏移相对 π − k + 1
    inline void insert(i64 pi, i64 a, u32 sq, const u64* own) {
        if (live.empty() || ring[live.back()].id != pi) {
            int slot = (int)(pi % k);
            ring[slot].clear(); ring[slot].id = pi; live.push_back(slot);
        }
        Pane& P = ring[live.back()];
        u32 li = (u32)P.av.size();
        P.av.push_back(a); P.seq.push_back(sq);
        P.data.insert(P.data.end(), own, own + K2);
        if constexpr (MAP) P.mp.emplace(a, li);
        else {
            auto it = std::upper_bound(P.idx.begin(), P.idx.end(), a, [](i64 v, const std::pair<i64, u32>& x) { return v < x.first; });
            P.idx.insert(it, {a, li});
        }
        n++;
    }
};

// M 的扫描模式：与 OPP 同一结构（purge / insert 继承，不改），查询循环同 Scan 的 vec 分支，
// 只多数一个「本事件的窗口累加次数」last_adds = Σ_窗格 合格前驱数 × |共同窗口|（每窗格一次乘加，E4 规则的输入）
template <bool SUM, bool CW>
struct ScanC : Scan<SUM, CW, false> {
    u64 last_adds = 0;
    inline void query(i64 pi, i64 a, bool gt, u64* ac, u64* as) {
        last_adds = 0;
        const int k = this->k, K2 = this->K2;
        for (int slot : this->live) {
            auto& P = this->ring[slot];
            int d = (int)(pi - P.id), len = k - d;
            auto body = [&](u32 li) {
                const u64* c = &P.data[(size_t)li * K2] + d;
                for (int o = 0; o < len; o++) ac[o] += c[o];
                if constexpr (SUM) { const u64* s = c + k; for (int o = 0; o < len; o++) as[o] += s[o]; }
                if constexpr (CW) { WK.pred++; WK.adds += len; }
            };
            auto cmp = [](const std::pair<i64, u32>& x, i64 v) { return x.first < v; };
            auto cmp2 = [](i64 v, const std::pair<i64, u32>& x) { return v < x.first; };
            if (gt) {
                auto it = std::upper_bound(P.idx.begin(), P.idx.end(), a, cmp2);
                last_adds += (u64)(P.idx.end() - it) * (u64)len;
                for (; it != P.idx.end(); ++it) body(it->second);
            } else {
                auto e = std::lower_bound(P.idx.begin(), P.idx.end(), a, cmp);
                last_adds += (u64)(e - P.idx.begin()) * (u64)len;
                for (auto it = P.idx.begin(); it != e; ++it) body(it->second);
            }
        }
    }
};

// ================================================================ M：每组一棵窗口槽聚合树（treap，键 (a, 到达序)）
// 结点块：own_c[k]（+ own_s[k]）按偏移存；sub_w[k]、sub_c[k]（+ sub_s[k]）、sub_n[k] 按槽号 = 窗口号 mod k 存，读时 wid 不等于所问窗口视为 0
// sub_n = 子树里在该窗口活着的事件数 nev（E4 第 2.1 节；own 的 nev 恒为 1，不存）：下降累出的 Σ_j acc_nev_j = 按 OPP 处理本事件的窗口累加次数
// del = true 是 A2：窗格边界上把死结点逐个删（旋到叶、摘掉、沿路径重算），不压缩；删掉的结点号进空闲表重用
template <bool SUM, bool CW>
struct Tree {
    int k = 0, S = 0, OS = 0, WD = 0, SC = 0, SS = 0, SN = 0;
    bool gt = false, del = false;
    std::vector<i64> A; std::vector<u32> PR; std::vector<i32> L, R; std::vector<i64> PN; std::vector<u32> SQ;
    std::vector<u64> B;
    i32 root = -1;
    u32 rng = 2463534242u;
    std::vector<i32> path;
    std::vector<i32> fre; std::deque<i32> fifo;  // A2：空闲结点号；活结点按到达序（窗格号不减）
    u64 last_nev = 0;                            // 上一次 query 的 Σ_j acc_nev_j

    void init(int k_, bool gt_, u32 seed) {  // 不动 del
        k = k_; gt = gt_;
        OS = k; WD = SUM ? 2 * k : k; SC = WD + k; SS = SC + k; SN = SUM ? 5 * k : 3 * k; S = SN + k;
        A.clear(); PR.clear(); L.clear(); R.clear(); PN.clear(); SQ.clear(); B.clear(); root = -1;
        fre.clear(); fifo.clear();
        rng = seed * 2654435761u + 12345u; if (!rng) rng = 1;
    }
    size_t size() const { return A.size(); }
    inline u32 rnd() { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
    inline u64* blk(i32 x) { return &B[(size_t)x * S]; }
    inline bool qual(i64 ax, i64 a) const { return gt ? ax > a : ax < a; }

    // 子树 y 在窗口 j0 … j0+k−1 上的聚合加进 acc
    inline void add_sub(i32 y, i64 j0, int base, u64* ac, u64* as) {
        u64* b = blk(y);
        const i64* w = (const i64*)(b + WD); const u64* c = b + SC; const u64* s = b + SS; const u64* nv = b + SN;
        int m = k - base; u64 tn = 0;
        for (int o = 0; o < m; o++) { int i = base + o; u64 ok = (w[i] == j0 + o) ? ~0ull : 0; ac[o] += c[i] & ok; if constexpr (SUM) as[o] += s[i] & ok; tn += nv[i] & ok; }
        for (int o = m; o < k; o++) { int i = o - m; u64 ok = (w[i] == j0 + o) ? ~0ull : 0; ac[o] += c[i] & ok; if constexpr (SUM) as[o] += s[i] & ok; tn += nv[i] & ok; }
        last_nev += tn;
        if constexpr (CW) WK.adds += k;
    }
    // 结点 x 自己在共同窗口 [j0, π_x] 上的值
    inline void add_own(i32 x, i64 pi, u64* ac, u64* as) {
        int d = (int)(pi - PN[x]); if (d >= k) return;  // 死结点：窗口都已关闭
        int len = k - d; u64* b = blk(x);
        last_nev += (u64)len;
        for (int o = 0; o < len; o++) ac[o] += b[d + o];
        if constexpr (SUM) for (int o = 0; o < len; o++) as[o] += b[OS + d + o];
        if constexpr (CW) WK.adds += len;
    }

    // 一次下降：所有满足 ⋈ 的结点在 J(e) 上的聚合；同时记下插入路径（同值的插入方向与查询方向一致，两条路径相同）
    inline void query(i64 pi, i64 a, u64* ac, u64* as) {
        i64 j0 = pi - k + 1; int base = (int)((pi + 1) % k);
        path.clear(); last_nev = 0;
        i32 x = root;
        while (x != -1) {
            path.push_back(x);
            if constexpr (CW) WK.nodes++;
            if (qual(A[x], a)) {
                i32 y = gt ? R[x] : L[x];
                if (y != -1) add_sub(y, j0, base, ac, as);
                add_own(x, pi, ac, as);
                x = gt ? L[x] : R[x];
            } else x = gt ? R[x] : L[x];
        }
    }

    // E2（X ≠ 1）：查询阈值 θ 与插入键 a 不同，插入路径另走一遍（同值的方向同 query）
    inline void find_path(i64 a) {
        path.clear();
        i32 x = root;
        while (x != -1) { path.push_back(x); if constexpr (CW) WK.nodes++; x = qual(A[x], a) ? (gt ? L[x] : R[x]) : (gt ? R[x] : L[x]); }
    }

    inline i32 new_node(i64 a, i64 pi, u32 sq, u32 pr) {
        if (!fre.empty()) {
            i32 x = fre.back(); fre.pop_back();
            A[x] = a; PR[x] = pr; L[x] = R[x] = -1; PN[x] = pi; SQ[x] = sq;
            return x;
        }
        i32 x = (i32)A.size();
        A.push_back(a); PR.push_back(pr); L.push_back(-1); R.push_back(-1); PN.push_back(pi); SQ.push_back(sq);
        B.resize(B.size() + S);
        return x;
    }

    // 子树 x 在窗口 j0 … j0+k−1 上的 sub 由 own + 两个孩子的 sub 重算
    inline void recompute(i32 x, i64 pi) {
        i64 j0 = pi - k + 1; int base = (int)((pi + 1) % k);
        u64* b = blk(x);
        i64* w = (i64*)(b + WD); u64* c = b + SC; u64* s = b + SS;
        int d = (int)(pi - PN[x]);
        u64* nv = b + SN;
        const u64* bl = L[x] != -1 ? blk(L[x]) : nullptr; const u64* br = R[x] != -1 ? blk(R[x]) : nullptr;
        for (int o = 0; o < k; o++) {
            int i = base + o; if (i >= k) i -= k;
            i64 j = j0 + o;
            u64 vc = 0, vs = 0, vn = 0;
            if (d + o < k) { vc = b[d + o]; if constexpr (SUM) vs = b[OS + d + o]; vn = 1; }
            if (bl && ((const i64*)(bl + WD))[i] == j) { vc += bl[SC + i]; if constexpr (SUM) vs += bl[SS + i]; vn += bl[SN + i]; }
            if (br && ((const i64*)(br + WD))[i] == j) { vc += br[SC + i]; if constexpr (SUM) vs += br[SS + i]; vn += br[SN + i]; }
            w[i] = j; c[i] = vc; if constexpr (SUM) s[i] = vs; nv[i] = vn;
        }
        if constexpr (CW) WK.adds += k;
    }

    // 一次插入：沿 query 记下的路径把本事件的 J 槽加进祖先的 sub，挂叶子，按 treap 优先级向上旋转
    inline void insert(i64 pi, i64 a, u32 sq, const u64* own) {
        i64 j0 = pi - k + 1; int base = (int)((pi + 1) % k);
        const u64* oc = own; const u64* os = own + k;
        for (i32 x : path) {
            u64* b = blk(x);
            i64* w = (i64*)(b + WD); u64* c = b + SC; u64* s = b + SS; u64* nv = b + SN;
            int m = k - base;
            for (int o = 0; o < m; o++) { int i = base + o; i64 j = j0 + o; u64 keep = (w[i] == j) ? ~0ull : 0; w[i] = j; c[i] = (c[i] & keep) + oc[o]; if constexpr (SUM) s[i] = (s[i] & keep) + os[o]; nv[i] = (nv[i] & keep) + 1; }
            for (int o = m; o < k; o++) { int i = o - m; i64 j = j0 + o; u64 keep = (w[i] == j) ? ~0ull : 0; w[i] = j; c[i] = (c[i] & keep) + oc[o]; if constexpr (SUM) s[i] = (s[i] & keep) + os[o]; nv[i] = (nv[i] & keep) + 1; }
            if constexpr (CW) WK.adds += k;
        }
        i32 n = new_node(a, pi, sq, rnd());
        if (del) fifo.push_back(n);
        u64* b = blk(n);
        memcpy(b, own, sizeof(u64) * (SUM ? 2 * k : k));
        {
            i64* w = (i64*)(b + WD); u64* c = b + SC; u64* s = b + SS; u64* nv = b + SN;
            for (int o = 0; o < k; o++) { int i = base + o; if (i >= k) i -= k; w[i] = j0 + o; c[i] = oc[o]; if constexpr (SUM) s[i] = os[o]; nv[i] = 1; }
        }
        if (path.empty()) { root = n; return; }
        i32 p = path.back();
        if (qual(A[p], a)) { if (gt) L[p] = n; else R[p] = n; } else { if (gt) R[p] = n; else L[p] = n; }
        // 向上旋转
        while (!path.empty()) {
            i32 P = path.back();
            if (PR[n] <= PR[P]) break;
            path.pop_back();
            i32 Gp = path.empty() ? -1 : path.back();
            if (L[P] == n) { L[P] = R[n]; R[n] = P; } else { R[P] = L[n]; L[n] = P; }
            if (Gp == -1) root = n; else if (L[Gp] == P) L[Gp] = n; else R[Gp] = n;
            // n 的新子树 = P 的旧子树：sub 整块照搬；P 由 own + 孩子重算
            memcpy(blk(n) + WD, blk(P) + WD, sizeof(u64) * (S - WD));
            recompute(P, pi);
            if constexpr (CW) WK.nodes += 2;
        }
    }

    // 由按键有序的结点建 treap（笛卡尔树，线性时间），再后序重算窗口 [π−k+1, π] 的 sub
    void build_from_sorted(const std::vector<i32>& ord, i64 pi) {
        std::vector<i32> st;
        for (i32 x : ord) {
            L[x] = R[x] = -1;
            i32 last = -1;
            while (!st.empty() && PR[st.back()] < PR[x]) { last = st.back(); st.pop_back(); }
            L[x] = last;
            if (!st.empty()) R[st.back()] = x;
            st.push_back(x);
        }
        root = st.empty() ? -1 : st.front();
        // 后序
        std::vector<std::pair<i32, bool>> stk;
        if (root != -1) stk.push_back({root, false});
        while (!stk.empty()) {
            auto [x, done] = stk.back(); stk.pop_back();
            if (done) { recompute(x, pi); continue; }
            stk.push_back({x, true});
            if (L[x] != -1) stk.push_back({L[x], false});
            if (R[x] != -1) stk.push_back({R[x], false});
        }
    }

    void inorder(std::vector<i32>& out) const {
        out.clear();
        std::vector<i32> st; i32 x = root;
        while (x != -1 || !st.empty()) {
            while (x != -1) { st.push_back(x); x = L[x]; }
            x = st.back(); st.pop_back(); out.push_back(x); x = R[x];
        }
    }

    // 压缩：只留活结点（π_x > π − k），线性时间重建平衡树（README 第 2.3 节第 4 条）
    void compact(i64 pi) {
        std::vector<i32> ord; inorder(ord);
        Tree T; T.init(k, gt, 0); T.rng = rng; T.del = del;
        std::vector<i32> ord2;
        for (i32 x : ord) if (PN[x] > pi - k) {
            i32 y = T.new_node(A[x], PN[x], SQ[x], PR[x]);
            memcpy(T.blk(y), blk(x), sizeof(u64) * (SUM ? 2 * k : k));
            ord2.push_back(y);
        }
        T.build_from_sorted(ord2, pi);
        T.path.swap(path);
        *this = std::move(T);
    }

    // A2：x 在中序里是否在 y 之前（键 (a, 到达序)；同值时 > 新者在右、< 新者在左，同插入）
    inline bool before(i32 x, i32 y) const { return A[x] != A[y] ? A[x] < A[y] : (gt ? SQ[x] < SQ[y] : SQ[x] > SQ[y]); }
    // A2：删一个结点：按键找到、旋到叶（每次把优先级大的孩子旋上来）、摘掉，再自底向上重算路径上的活窗口槽
    void erase(i32 x, i64 pi) {
        path.clear();
        i32 y = root;
        while (y != x) { path.push_back(y); if constexpr (CW) WK.nodes++; y = before(x, y) ? L[y] : R[y]; }
        while (L[x] != -1 || R[x] != -1) {
            i32 c = L[x] == -1 ? R[x] : R[x] == -1 ? L[x] : (PR[L[x]] > PR[R[x]] ? L[x] : R[x]);
            i32 par = path.empty() ? -1 : path.back();
            if (c == L[x]) { L[x] = R[c]; R[c] = x; } else { R[x] = L[c]; L[c] = x; }
            if (par == -1) root = c; else if (L[par] == x) L[par] = c; else R[par] = c;
            path.push_back(c);
            if constexpr (CW) WK.nodes++;
        }
        i32 par = path.empty() ? -1 : path.back();
        if (par == -1) root = -1; else if (L[par] == x) L[par] = -1; else R[par] = -1;
        fre.push_back(x);
        for (size_t i = path.size(); i-- > 0;) recompute(path[i], pi);
    }
    // A2：窗格 π 开始时删掉所有 π_x ≤ π − k 的结点（fifo 按到达序，窗格号不减）
    void expire(i64 pi) {
        while (!fifo.empty() && PN[fifo.front()] <= pi - k) { erase(fifo.front(), pi); fifo.pop_front(); }
    }
};

// ================================================================ 臂的公共骨架：每组的「最终聚合 + 结构」，全局按时间逐事件处理
template <bool SUM>
static inline void own_from_acc(int k, i64 a, const u64* ac, const u64* as, u64* own) {
    for (int o = 0; o < k; o++) own[o] = 1 + ac[o];
    if constexpr (SUM) for (int o = 0; o < k; o++) own[k + o] = (u64)a * own[o] + as[o];
}

struct ArmBase {
    Query q;
    std::vector<Fin> fin;
    std::vector<i64> last;  // 每组上一个事件的窗格
    std::vector<u32> seq;
    std::vector<u64> ac, as, own;
    void base_init(const Query& q_, int G) {
        q = q_; fin.assign(G, Fin()); for (auto& f : fin) f.init(q.k);
        last.assign(G, NONE); seq.assign(G, 0);
        ac.assign(q.k, 0); as.assign(q.k, 0); own.assign(2 * q.k, 0);
    }
    inline void clear_acc() { std::fill(ac.begin(), ac.end(), 0); if (q.sum) std::fill(as.begin(), as.end(), 0); }
    inline void emit(int g, i64 pi) {
        const u64* v = q.sum ? own.data() + q.k : own.data();
        fin[g].add(q.k, pi - q.k + 1, (int)((pi + 1) % q.k), v);
    }
    void finish() { for (auto& f : fin) f.flush(); }
};

template <bool SUM, bool CW, bool MAP, bool XN = false>
struct ArmOPP : ArmBase {
    std::vector<Scan<SUM, CW, MAP>> gs;
    void init(const Query& q_, int G) { base_init(q_, G); gs.assign(G, Scan<SUM, CW, MAP>()); for (auto& s : gs) s.init(q.k); }
    inline void process(int g, i64 pi, i64 a) {
        auto& S = gs[g];
        if (pi != last[g]) { S.purge(pi); last[g] = pi; }
        clear_acc();
        if constexpr (XN) S.query(pi, thr(q, a), q.gt, ac.data(), as.data()); else  // E2 的选择度谓词；E1 用 XN = false，与 M1 同
        S.query(pi, a, q.gt, ac.data(), as.data());
        own_from_acc<SUM>(q.k, a, ac.data(), as.data(), own.data());
        emit(g, pi);
        S.insert(pi, a, seq[g]++, own.data());
    }
};

// M、A2、A4、A5：同一棵窗口槽聚合树，差在切换规则与过期方式
//   rule = COST（M / A2，E4 第 1 节的代价规则）、SIZE（A5，M1 的规模阈值 τ_low / τ_high = 2 τ_low）、NONE（A4，始终索引）
//   del = true（A2）：窗格边界逐个删死结点；false：死 > 活时压缩（M1 同）
static inline u64 ceil_log2(u64 m) { return m <= 1 ? 0 : 64 - (u64)__builtin_clzll(m - 1); }

template <bool SUM, bool CW>
struct ArmM : ArmBase {
    enum Rule { NONE, SIZE, COST };
    struct G {
        bool index = false;
        ScanC<SUM, CW> scan; Tree<SUM, CW> tree;
        std::vector<i64> pid; std::vector<u32> pcnt; u64 live = 0;  // 每个窗格的事件数（环）
        double sbar = 0, ibar = 0;                                   // 按窗格做 EWMA（α = 1/2）的每事件扫描代价、索引代价模型
        u64 sp = 0, ip = 0; u64 np = 0;                              // 当前窗格内的和与事件数
    };
    std::vector<G> gs;
    Rule rule = COST; double cc = 1; u64 tau_lo = 16, tau_hi = 32; bool del = false;
    u64 inpane = 1024;                     // E8：扫描模式下窗格内每 B 个事件检查一次代价（0 = 关，回到 v1 只在窗格边界判）
    u64 n_switch = 0, n_compact = 0, n_idx = 0, n_inpane = 0;
    std::vector<double> ratios;            // CW：每次更新后的 s̄ ÷ ī
    std::vector<std::pair<i32, u64>>* trace = nullptr;  // CW：逐事件（组, 扫描代价）
    void init(const Query& q_, int Gn, Rule r, double c, u64 tau, bool del_, u64 B) {
        base_init(q_, Gn); rule = r; cc = c; tau_lo = tau; tau_hi = 2 * tau; del = del_; inpane = B;
        n_switch = n_compact = n_idx = n_inpane = 0; ratios.clear();
        gs.assign(Gn, G());
        for (int g = 0; g < Gn; g++) {
            auto& x = gs[g]; x.scan.init(q.k); x.tree.init(q.k, q.gt, (u32)g + 1); x.tree.del = del; x.index = (r == NONE);
            x.pid.assign(q.k, NONE); x.pcnt.assign(q.k, 0); x.live = 0;
        }
    }
    void to_index(G& x, i64 pi) {  // 扫描 → 索引：活顶点按键排序后线性建树
        auto& T = x.tree; T.init(q.k, q.gt, T.rng);
        struct V { i64 a; u32 sq; i32 node; };
        std::vector<V> vs;
        int K2 = SUM ? 2 * q.k : q.k;
        for (int slot : x.scan.live) {
            auto& P = x.scan.ring[slot];
            for (size_t li = 0; li < P.size(); li++) {
                i32 y = T.new_node(P.av[li], P.id, P.seq[li], T.rnd());
                memcpy(T.blk(y), &P.data[li * K2], sizeof(u64) * K2);
                vs.push_back({P.av[li], P.seq[li], y});
            }
        }
        if (del) {  // A2：活结点按到达序进 fifo
            std::vector<std::pair<u32, i32>> bysq; bysq.reserve(vs.size());
            for (auto& v : vs) bysq.push_back({v.sq, v.node});
            std::sort(bysq.begin(), bysq.end());
            for (auto& [sq, y] : bysq) T.fifo.push_back(y);
        }
        // 键 (a, 到达序)；⋈ 为 < 时同值新者在前（与查询方向一致）
        bool gt = q.gt;
        std::sort(vs.begin(), vs.end(), [gt](const V& u, const V& v) { return u.a != v.a ? u.a < v.a : (gt ? u.sq < v.sq : u.sq > v.sq); });
        std::vector<i32> ord; ord.reserve(vs.size()); for (auto& v : vs) ord.push_back(v.node);
        T.build_from_sorted(ord, pi);
        x.scan.init(q.k); x.index = true; n_switch++;
    }
    void to_scan(G& x, i64 pi) {  // 索引 → 扫描：中序取活结点，按窗格放回顶点树（中序已按 a 有序）
        auto& T = x.tree; std::vector<i32> ord; T.inorder(ord);
        x.scan.init(q.k);
        std::vector<i32> keep;
        for (i32 y : ord) if (T.PN[y] > pi - q.k) keep.push_back(y);
        std::stable_sort(keep.begin(), keep.end(), [&](i32 u, i32 v) { return T.SQ[u] < T.SQ[v]; });  // 按到达序放进各窗格
        for (i32 y : keep) x.scan.insert(T.PN[y], T.A[y], T.SQ[y], T.blk(y));
        T.init(q.k, q.gt, T.rng); x.index = false; n_switch++;
    }
    inline void boundary(G& x, i64 pi) {
        int k = q.k;
        for (int i = 0; i < k; i++) if (x.pid[i] != NONE && x.pid[i] <= pi - k) { x.live -= x.pcnt[i]; x.pid[i] = NONE; x.pcnt[i] = 0; }
        if (rule == COST && x.np) {  // 用刚结束的窗格里 n_p 个事件的平均更新 s̄、ī（n_p = 0 不更新）
            double sm = (double)x.sp / (double)x.np, im = (double)x.ip / (double)x.np;
            x.sbar = 0.5 * x.sbar + 0.5 * sm; x.ibar = 0.5 * x.ibar + 0.5 * im;
            x.sp = x.ip = x.np = 0;
            if constexpr (CW) ratios.push_back(x.ibar > 0 ? x.sbar / x.ibar : 0.0);
        }
        if (!x.index) {
            x.scan.purge(pi);
            bool go = rule == SIZE ? x.live >= tau_hi : (rule == COST && x.sbar > 2 * cc * x.ibar);
            if (go) to_index(x, pi);
        } else {
            bool back = rule == SIZE ? x.live < tau_lo : (rule == COST && x.sbar < cc * x.ibar);
            if (back) to_scan(x, pi);
            else if (del) x.tree.expire(pi);
            else if (x.tree.size() > 2 * x.live) { x.tree.compact(pi); n_compact++; }
        }
    }
    inline void process(int g, i64 pi, i64 a) {
        auto& x = gs[g];
        if (pi != last[g]) { boundary(x, pi); last[g] = pi; }
        clear_acc();
        u32 sq = seq[g]++;
        const i64 qa = q.xnum != 1000 ? thr(q, a) : a;
        u64 sc;
        if (x.index) {
            x.tree.query(pi, qa, ac.data(), as.data());
            sc = x.tree.last_nev;
            if (qa != a) x.tree.find_path(a);
            own_from_acc<SUM>(q.k, a, ac.data(), as.data(), own.data());
            emit(g, pi);
            x.tree.insert(pi, a, sq, own.data());
            if constexpr (CW) n_idx++;
        } else {
            x.scan.query(pi, qa, q.gt, ac.data(), as.data());
            sc = x.scan.last_adds;
            own_from_acc<SUM>(q.k, a, ac.data(), as.data(), own.data());
            emit(g, pi);
            x.scan.insert(pi, a, sq, own.data());
        }
        if (rule == COST) {
            x.sp += sc; x.ip += (u64)q.k * 2 * ceil_log2(x.live + 2); x.np++;
            // E8 窗格内检查：扫描模式下本窗格每满 B 个事件，用本窗格到目前为止的平均（sp ÷ np 对 ip ÷ np）做窗格边界同样的比较，
            // 超过就当场切到索引（本事件已插进扫描结构，to_index 把全部活窗格、含当前窗格，搬进树）；索引 → 扫描仍只在窗格边界判
            if (inpane && !x.index && x.np % inpane == 0 && (double)x.sp > 2 * cc * (double)x.ip) { to_index(x, pi); n_inpane++; }
        }
        if constexpr (CW) if (trace) trace->push_back({g, sc});
        int i = (int)(pi % q.k);
        if (x.pid[i] != pi) { x.pid[i] = pi; x.pcnt[i] = 0; }
        x.pcnt[i]++; x.live++;
    }
};

// A1：每个活跃窗口各一棵 treap（结点只存一对 cnt、sum），事件插进它所属的 k 棵树、查询做 k 次下降
template <bool SUM, bool CW>
struct ArmA1 : ArmBase {
    struct WT {
        i64 wid = NONE; i32 root = -1;
        std::vector<i64> A; std::vector<u32> PR; std::vector<i32> L, R;
        std::vector<u64> V;  // 每结点 own_c, sub_c（SUM 时再 own_s, sub_s）
        void reset(i64 j) { wid = j; root = -1; A.clear(); PR.clear(); L.clear(); R.clear(); V.clear(); }
    };
    struct G { std::vector<WT> ring; u32 rng = 1; };
    std::vector<G> gs;
    static constexpr int ST = SUM ? 4 : 2;
    std::vector<i32> path;
    void init(const Query& q_, int Gn) {
        base_init(q_, Gn); gs.assign(Gn, G());
        for (int g = 0; g < Gn; g++) { gs[g].ring.assign(q.k, WT()); gs[g].rng = (u32)(g + 1) * 2654435761u + 12345u; if (!gs[g].rng) gs[g].rng = 1; }
    }
    inline bool qual(i64 ax, i64 a) const { return q.gt ? ax > a : ax < a; }
    inline void process(int g, i64 pi, i64 a) {
        auto& x = gs[g]; int k = q.k;
        i64 j0 = pi - k + 1; int base = (int)((pi + 1) % k);
        for (int o = 0; o < k; o++) {
            int i = base + o; if (i >= k) i -= k;
            WT& T = x.ring[i];
            if (T.wid != j0 + o) T.reset(j0 + o);  // 窗口关闭：整棵树丢掉，槽给新窗口
            // 下降
            u64 c = 0, s = 0; path.clear();
            i32 y = T.root;
            while (y != -1) {
                path.push_back(y);
                if constexpr (CW) WK.nodes++;
                if (qual(T.A[y], a)) {
                    i32 z = q.gt ? T.R[y] : T.L[y];
                    if (z != -1) { c += T.V[(size_t)z * ST + 1]; if constexpr (SUM) s += T.V[(size_t)z * ST + 3]; }
                    c += T.V[(size_t)y * ST]; if constexpr (SUM) s += T.V[(size_t)y * ST + 2];
                    y = q.gt ? T.L[y] : T.R[y];
                } else y = q.gt ? T.R[y] : T.L[y];
            }
            u64 oc = 1 + c, os = (u64)a * oc + s;
            own[o] = oc; if constexpr (SUM) own[k + o] = os;
            // 插入
            for (i32 z : path) { T.V[(size_t)z * ST + 1] += oc; if constexpr (SUM) T.V[(size_t)z * ST + 3] += os; }
            i32 n = (i32)T.A.size();
            x.rng ^= x.rng << 13; x.rng ^= x.rng >> 17; x.rng ^= x.rng << 5;
            T.A.push_back(a); T.PR.push_back(x.rng); T.L.push_back(-1); T.R.push_back(-1);
            if constexpr (SUM) { T.V.push_back(oc); T.V.push_back(oc); T.V.push_back(os); T.V.push_back(os); }
            else { T.V.push_back(oc); T.V.push_back(oc); }
            if (path.empty()) { T.root = n; continue; }
            i32 p = path.back();
            if (qual(T.A[p], a)) { if (q.gt) T.L[p] = n; else T.R[p] = n; } else { if (q.gt) T.R[p] = n; else T.L[p] = n; }
            while (!path.empty()) {
                i32 P = path.back();
                if (T.PR[n] <= T.PR[P]) break;
                path.pop_back();
                i32 Gp = path.empty() ? -1 : path.back();
                if (T.L[P] == n) { T.L[P] = T.R[n]; T.R[n] = P; } else { T.R[P] = T.L[n]; T.L[n] = P; }
                if (Gp == -1) T.root = n; else if (T.L[Gp] == P) T.L[Gp] = n; else T.R[Gp] = n;
                T.V[(size_t)n * ST + 1] = T.V[(size_t)P * ST + 1];
                u64 sc = T.V[(size_t)P * ST];
                if (T.L[P] != -1) sc += T.V[(size_t)T.L[P] * ST + 1];
                if (T.R[P] != -1) sc += T.V[(size_t)T.R[P] * ST + 1];
                T.V[(size_t)P * ST + 1] = sc;
                if constexpr (SUM) {
                    T.V[(size_t)n * ST + 3] = T.V[(size_t)P * ST + 3];
                    u64 ss = T.V[(size_t)P * ST + 2];
                    if (T.L[P] != -1) ss += T.V[(size_t)T.L[P] * ST + 3];
                    if (T.R[P] != -1) ss += T.V[(size_t)T.R[P] * ST + 3];
                    T.V[(size_t)P * ST + 3] = ss;
                }
                if constexpr (CW) WK.nodes += 2;
            }
        }
        emit(g, pi);
    }
};

// ================================================================ 驱动
struct Opt {
    std::string arm = "M", data, op = ">", agg = "COUNT", dump, oppidx = "vec", rule, expire, trace, latency;
    i64 W = 0, s = 0, xnum = 1000; int reps = 5, warmup = 1, copies = 1; long tau = 16, limit = 0, inpane = 1024; bool work = false, autop = false;
    double c = -1;
};

static u64 mix(u64 x) { x += 0x9e3779b97f4a7c15ull; x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ull; x = (x ^ (x >> 27)) * 0x94d049bb133111ebull; return x ^ (x >> 31); }

struct Result {
    double sec; u64 checksum, outputs; std::vector<std::vector<std::pair<i64, u64>>> out;
    u64 extra1 = 0, extra2 = 0, idx = 0, inpane = 0; double ratio_med = -1;
};

// ---------------------------------------------------------------- E6：逐事件延迟（--latency；默认 LAT = nullptr，E1 / E2 / E4 的路径不进来）
// 每个事件一个纳秒数（u32，预分配）与一个类别：0 普通；1 本组进了新窗格（OPP 的整窗格清除、M 的窗格边界簿记、A2 的逐个删都在这一类）；
// 2 这次调用里发生了压缩；3 这次调用里发生了扫描 ↔ 索引切换（2、3 只有树的臂有；同一次调用两样都有记 3）
struct LatBuf { std::vector<uint32_t> ns; std::vector<uint8_t> cat; };
static LatBuf* LAT = nullptr;

template <class Arm, class InitF>
static Result run_arm_lat(const Stream& S, const Query& q, InitF initf, bool keep) {
    Arm arm;
    initf(arm);
    const size_t n = S.n();
    const i32* G = S.g.data(); const i64* T = S.t.data(); const i64* A = S.a.data();
    const i64 s = q.s;
    LAT->ns.assign(n, 0); LAT->cat.assign(n, 0);
    uint32_t* NS = LAT->ns.data(); uint8_t* CT = LAT->cat.data();
    std::vector<i64> lp(S.gname.size(), NONE);
    u64 sw0 = 0, cp0 = 0;
    using clk = std::chrono::steady_clock;
    auto t0 = clk::now();
    for (size_t i = 0; i < n; i++) {
        const int g = G[i]; const i64 pi = T[i] / s;
        uint8_t c = 0;
        if (pi != lp[g]) { c = 1; lp[g] = pi; }
        auto a = clk::now();
        arm.process(g, pi, A[i]);
        auto b = clk::now();
        if constexpr (requires { arm.n_switch; }) {
            if (arm.n_switch != sw0) { c = 3; sw0 = arm.n_switch; cp0 = arm.n_compact; }
            else if (arm.n_compact != cp0) { c = 2; cp0 = arm.n_compact; }
        }
        long long d = std::chrono::duration_cast<std::chrono::nanoseconds>(b - a).count();
        NS[i] = (uint32_t)std::min<long long>(std::max<long long>(d, 0), UINT32_MAX); CT[i] = c;
    }
    arm.finish();
    auto t1 = clk::now();
    Result r; r.sec = std::chrono::duration<double>(t1 - t0).count();
    r.checksum = 0; r.outputs = 0;
    for (size_t g = 0; g < arm.fin.size(); g++)
        for (auto& [j, v] : arm.fin[g].out) { r.checksum += mix(mix(g * 0x100000001b3ull + (u64)j) ^ v); r.outputs++; }
    if (keep) { r.out.resize(arm.fin.size()); for (size_t g = 0; g < arm.fin.size(); g++) r.out[g] = std::move(arm.fin[g].out); }
    if constexpr (requires { arm.n_switch; }) { r.extra1 = arm.n_switch; r.extra2 = arm.n_compact; r.inpane = arm.n_inpane; }
    return r;
}

// 第 p 分位（最近秩：排序后第 ⌈p·n⌉ 个，p ∈ (0, 1]）
static uint32_t pct(std::vector<uint32_t>& v, double p) {
    if (v.empty()) return 0;
    size_t r = (size_t)std::ceil(p * (double)v.size()); if (r < 1) r = 1; if (r > v.size()) r = v.size();
    std::nth_element(v.begin(), v.begin() + (r - 1), v.end());
    return v[r - 1];
}

// 一遍的汇总：stdout 一行 lat 与每类一行 latcat；<文件> 追加直方图（每倍 8 桶，桶 b 覆盖 [2^(b/8), 2^((b+1)/8)) ns，0 ns 记 b = −1）与前 100 大值
static void lat_report(FILE* info, FILE* lf, int pass, double sec, const Stream& S) {
    const auto& ns = LAT->ns; const auto& ct = LAT->cat; size_t n = ns.size();
    std::vector<uint32_t> v(ns.begin(), ns.end());
    long double sum = 0; for (auto x : ns) sum += x;
    uint32_t mx = n ? *std::max_element(ns.begin(), ns.end()) : 0;
    fprintf(info, "lat\t%d\t%.6f\t%zu\t%.1f\t%u\t%u\t%u\t%u\t%u\n", pass, sec, n, n ? (double)(sum / n) : 0.0,
            pct(v, 0.5), pct(v, 0.99), pct(v, 0.999), pct(v, 0.9999), mx);
    for (int c = 0; c < 4; c++) {
        std::vector<uint32_t> w; long double cs = 0;
        for (size_t i = 0; i < n; i++) if (ct[i] == c) { w.push_back(ns[i]); cs += ns[i]; }
        uint32_t cm = w.empty() ? 0 : *std::max_element(w.begin(), w.end());
        fprintf(info, "latcat\t%d\t%d\t%zu\t%u\t%u\t%u\t%.0f\n", pass, c, w.size(), pct(w, 0.5), pct(w, 0.99), cm, (double)cs);
    }
    if (!lf) return;
    std::map<int, u64> h;
    for (auto x : ns) h[x == 0 ? -1 : (int)std::floor(8.0 * std::log2((double)x))]++;
    for (auto& [b, c] : h) fprintf(lf, "hist\t%d\t%d\t%llu\n", pass, b, (unsigned long long)c);
    std::vector<u32> id(n); std::iota(id.begin(), id.end(), 0);
    size_t m = std::min<size_t>(100, n);
    std::partial_sort(id.begin(), id.begin() + m, id.end(), [&](u32 x, u32 y) { return ns[x] != ns[y] ? ns[x] > ns[y] : x < y; });
    for (size_t r = 0; r < m; r++) {
        u32 i = id[r];
        fprintf(lf, "top\t%d\t%zu\t%u\t%d\t%s\t%u\t%lld\n", pass, r + 1, ns[i], (int)ct[i], S.gname[S.g[i]].c_str(), i, (long long)S.t[i]);
    }
}

// 时钟标定：10⁶ 对背靠背的 steady_clock::now()，报差的中位（读一次时钟的开销）与最小正差（分辨率）
static void clock_calib(FILE* info) {
    using clk = std::chrono::steady_clock;
    std::vector<uint32_t> d(1000000);
    for (auto& x : d) { auto a = clk::now(); auto b = clk::now(); x = (uint32_t)std::chrono::duration_cast<std::chrono::nanoseconds>(b - a).count(); }
    uint32_t mp = UINT32_MAX; for (auto x : d) if (x > 0 && x < mp) mp = x;
    fprintf(info, "clock\t%u\t%u\n", pct(d, 0.5), mp == UINT32_MAX ? 0 : mp);
}

template <class Arm, class InitF>
static Result run_arm(const Stream& S, const Query& q, InitF initf, bool keep) {
    if (LAT) return run_arm_lat<Arm>(S, q, initf, keep);  // E6；E1 / E2 / E4 时 LAT 为空
    Arm arm;
    initf(arm);
    const size_t n = S.n();
    const i32* G = S.g.data(); const i64* T = S.t.data(); const i64* A = S.a.data();
    const i64 s = q.s;
    auto t0 = std::chrono::steady_clock::now();
    for (size_t i = 0; i < n; i++) arm.process(G[i], T[i] / s, A[i]);
    arm.finish();
    auto t1 = std::chrono::steady_clock::now();
    Result r; r.sec = std::chrono::duration<double>(t1 - t0).count();
    r.checksum = 0; r.outputs = 0;
    for (size_t g = 0; g < arm.fin.size(); g++)
        for (auto& [j, v] : arm.fin[g].out) { r.checksum += mix(mix(g * 0x100000001b3ull + (u64)j) ^ v); r.outputs++; }
    if (keep) { r.out.resize(arm.fin.size()); for (size_t g = 0; g < arm.fin.size(); g++) r.out[g] = std::move(arm.fin[g].out); }
    if constexpr (requires { arm.n_switch; }) {
        r.extra1 = arm.n_switch; r.extra2 = arm.n_compact; r.idx = arm.n_idx; r.inpane = arm.n_inpane;
        if (!arm.ratios.empty()) {
            auto v = arm.ratios; size_t h = v.size() / 2;
            std::nth_element(v.begin(), v.begin() + h, v.end()); double m = v[h];
            if (v.size() % 2 == 0) { m = 0.5 * (m + *std::max_element(v.begin(), v.begin() + h)); }
            r.ratio_med = m;
        }
    }
    return r;
}

template <bool SUM, bool CW>
static Result dispatch(const Opt& o, const Stream& S, const Query& q, bool keep, std::vector<std::pair<i32, u64>>* trace = nullptr) {
    int Gn = (int)S.gname.size();
    bool xn = q.xnum != 1000;
    if (o.arm == "OPP") {
        if (o.oppidx == "map") {
            if (xn) return run_arm<ArmOPP<SUM, CW, true, true>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
            return run_arm<ArmOPP<SUM, CW, true>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
        }
        if (xn) return run_arm<ArmOPP<SUM, CW, false, true>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
        return run_arm<ArmOPP<SUM, CW, false>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
    }
    if (o.arm == "M" || o.arm == "A2" || o.arm == "A4" || o.arm == "A5") {
        using AM = ArmM<SUM, CW>;
        std::string rule = o.rule.empty() ? (o.arm == "A4" ? "none" : o.arm == "A5" ? "size" : "cost") : o.rule;
        typename AM::Rule r = rule == "none" ? AM::NONE : rule == "size" ? AM::SIZE : AM::COST;
        if (rule != "none" && rule != "size" && rule != "cost") { fprintf(stderr, "未知的规则 %s\n", rule.c_str()); exit(2); }
        if (r == AM::COST && o.c <= 0) { fprintf(stderr, "代价规则要 --c\n"); exit(2); }
        bool del = o.expire.empty() ? o.arm == "A2" : o.expire == "delete";
        return run_arm<AM>(S, q, [&](auto& a) { a.init(q, Gn, r, o.c, (u64)o.tau, del, (u64)o.inpane); a.trace = trace; }, keep);
    }
    if (o.arm == "A1") {
        if (xn) { fprintf(stderr, "A1 不支持 --xnum\n"); exit(2); }
        return run_arm<ArmA1<SUM, CW>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
    }
    fprintf(stderr, "未知的臂 %s\n", o.arm.c_str()); exit(2);
}

int main(int argc, char** argv) {
    Opt o;
    for (int i = 1; i < argc; i++) {
        std::string k = argv[i];
        auto nx = [&]() -> const char* { if (i + 1 >= argc) { fprintf(stderr, "%s 缺值\n", k.c_str()); exit(2); } return argv[++i]; };
        if (k == "--arm") o.arm = nx(); else if (k == "--data") o.data = nx(); else if (k == "--W") o.W = atoll(nx());
        else if (k == "--s") o.s = atoll(nx()); else if (k == "--op") o.op = nx(); else if (k == "--agg") o.agg = nx();
        else if (k == "--reps") o.reps = atoi(nx()); else if (k == "--warmup") o.warmup = atoi(nx()); else if (k == "--tau") o.tau = atol(nx());
        else if (k == "--limit") o.limit = atol(nx()); else if (k == "--dump") o.dump = nx(); else if (k == "--work") o.work = true;
        else if (k == "--opp-index") o.oppidx = nx();
        else if (k == "--c") o.c = atof(nx()); else if (k == "--rule") o.rule = nx(); else if (k == "--expire") o.expire = nx();
        else if (k == "--copies") o.copies = atoi(nx()); else if (k == "--autopasses") o.autop = true;
        else if (k == "--xnum") o.xnum = atoll(nx()); else if (k == "--trace") o.trace = nx();
        else if (k == "--latency") o.latency = nx();
        else if (k == "--inpane") o.inpane = atol(nx());
        else { fprintf(stderr, "未知参数 %s\n", k.c_str()); return 2; }
    }
    if (o.data.empty() || o.W <= 0 || o.s <= 0 || o.W % o.s) { fprintf(stderr, "要 --data，且 W 被 s 整除\n"); return 2; }
    if (o.copies < 1 || o.xnum <= 0) { fprintf(stderr, "--copies ≥ 1、--xnum > 0\n"); return 2; }
    if (o.inpane < 0) { fprintf(stderr, "--inpane ≥ 0\n"); return 2; }
    if (o.autop && o.warmup < 1) { fprintf(stderr, "--autopasses 要至少 1 遍预热\n"); return 2; }
    if (!o.trace.empty() && !o.work) { fprintf(stderr, "--trace 要 --work\n"); return 2; }
    if (!o.latency.empty() && (o.work || o.autop)) { fprintf(stderr, "--latency 不和 --work、--autopasses 同用\n"); return 2; }
    Stream S = load(o.data.c_str(), o.limit, o.copies, o.s);
    Query q{o.op == ">", o.W, o.s, (int)(o.W / o.s), o.agg == "SUM", o.xnum};
    bool keep = !o.dump.empty();
    FILE* info = o.dump == "-" ? stderr : stdout;  // 输出到 stdout 时，其余信息改走 stderr
    u64 ck = 0, outs = 0; bool first = true; bool same = true;
    Result last;
    int reps = o.reps;
    LatBuf lb; FILE* lf = nullptr;
    if (!o.latency.empty()) { lf = fopen(o.latency.c_str(), "w"); if (!lf) { perror(o.latency.c_str()); return 2; } clock_calib(info); }
    for (int r = 0; r < o.warmup + reps; r++) {
        bool lastpass = r == o.warmup + reps - 1;
        if (lf) LAT = r < o.warmup ? nullptr : &lb;  // 预热遍照常；计时遍逐事件计时
        Result res = q.sum ? dispatch<true, false>(o, S, q, keep && lastpass) : dispatch<false, false>(o, S, q, keep && lastpass);
        if (LAT) lat_report(info, lf, r - o.warmup + 1, res.sec, S);
        LAT = nullptr;
        if (first) { ck = res.checksum; outs = res.outputs; first = false; } else if (res.checksum != ck) same = false;
        if (r < o.warmup) {
            fprintf(info, "warm\t%.6f\n", res.sec);
            // E1 第 1 节：R = min(200, max(5, ⌈2 s ÷ 预热遍时间⌉))
            if (o.autop && r == o.warmup - 1) { double x = res.sec > 0 ? std::ceil(2.0 / res.sec) : 200; reps = (int)std::min(200.0, std::max(5.0, x)); }
        } else fprintf(info, "time\t%d\t%.6f\n", r - o.warmup + 1, res.sec);
        fflush(info);
        last = std::move(res);
    }
    if (lf) fclose(lf);
    fprintf(info, "reps\t%d\ncopies\t%d\n", reps, o.copies);
    fprintf(info, "checksum\t%016llx\n", (unsigned long long)ck);
    fprintf(info, "outputs\t%llu\n", (unsigned long long)outs);
    fprintf(info, "switches\t%llu\ncompactions\t%llu\n", (unsigned long long)last.extra1, (unsigned long long)last.extra2);
    fprintf(info, "inpane_switches\t%llu\n", (unsigned long long)last.inpane);
    if (!same) { fprintf(info, "checksum_mismatch_between_reps\n"); }
    if (o.work) {
        WK = Work();
        std::vector<std::pair<i32, u64>> tr; auto* tp = o.trace.empty() ? nullptr : &tr;
        Result w = q.sum ? dispatch<true, true>(o, S, q, false, tp) : dispatch<false, true>(o, S, q, false, tp);
        if (w.checksum != ck) { fprintf(info, "checksum_mismatch_work_pass\n"); same = false; }
        fprintf(info, "work_pred\t%llu\nwork_adds\t%llu\nwork_nodes\t%llu\n", (unsigned long long)WK.pred, (unsigned long long)WK.adds, (unsigned long long)WK.nodes);
        fprintf(info, "idx_events\t%llu\nevents\t%zu\nratio_med\t%.6g\n", (unsigned long long)w.idx, S.n(), w.ratio_med);
        if (tp) {
            FILE* f = fopen(o.trace.c_str(), "w");
            for (auto& [g, v] : tr) fprintf(f, "%s\t%llu\n", S.gname[g].c_str(), (unsigned long long)v);
            fclose(f);
        }
    }
    struct rusage ru; getrusage(RUSAGE_SELF, &ru);
#ifdef __APPLE__
    long kb = ru.ru_maxrss / 1024;  // macOS 给字节
#else
    long kb = ru.ru_maxrss;
#endif
    fprintf(info, "maxrss_kb\t%ld\n", kb);
    if (keep) {
        // 按组名、窗口排序输出「组 \t 窗口 \t 值」
        std::vector<int> gi(S.gname.size()); std::iota(gi.begin(), gi.end(), 0);
        std::sort(gi.begin(), gi.end(), [&](int x, int y) { return S.gname[x] < S.gname[y]; });
        FILE* f = o.dump == "-" ? stdout : fopen(o.dump.c_str(), "w");
        for (int g : gi) {
            auto v = last.out[g]; std::sort(v.begin(), v.end());
            for (auto& [j, val] : v) fprintf(f, "%s\t%lld\t%llu\n", S.gname[g].c_str(), (long long)j, (unsigned long long)val);
        }
        if (f != stdout) fclose(f);
    }
    return same ? 0 : 3;
}
