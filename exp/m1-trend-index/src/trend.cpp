// M1 · 相邻比较谓词下的趋势聚合：OPP（GRETA 运行时复现）、M（窗口槽聚合树 + 按组规模切换）、A1、A4。
// 规格：exp/m1-trend-index/README.md 第 2 节。单线程；算术取模 2^64；整数属性；时间整数（与 W、s 同单位）。
//
// 用法：trend --arm OPP|M|A1|A4 --data <tsv> --W <W> --s <s> --op '>'|'<' --agg COUNT|SUM
//             [--reps 5] [--warmup 1] [--tau 64] [--opp-index vec|map] [--limit N] [--dump <文件>|-] [--work]
// 输出（stdout）：time <rep> <秒>、checksum、outputs、maxrss_kb、work（--work 时另跑一次只计数不计时）、groups_windows_med
#include <algorithm>
#include <chrono>
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

static Stream load(const char* path, long limit) {
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
    return S;
}

struct Query { bool gt; i64 W, s; int k; bool sum; };

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

// ================================================================ M：每组一棵窗口槽聚合树（treap，键 (a, 到达序)）
// 结点块：own_c[k]（+ own_s[k]）按偏移存；sub_w[k]、sub_c[k]（+ sub_s[k]）按槽号 = 窗口号 mod k 存，读时 wid 不等于所问窗口视为 0
template <bool SUM, bool CW>
struct Tree {
    int k = 0, S = 0, OS = 0, WD = 0, SC = 0, SS = 0;
    bool gt = false;
    std::vector<i64> A; std::vector<u32> PR; std::vector<i32> L, R; std::vector<i64> PN; std::vector<u32> SQ;
    std::vector<u64> B;
    i32 root = -1;
    u32 rng = 2463534242u;
    std::vector<i32> path;

    void init(int k_, bool gt_, u32 seed) {
        k = k_; gt = gt_;
        OS = k; WD = SUM ? 2 * k : k; SC = WD + k; SS = SC + k; S = SUM ? 5 * k : 3 * k;
        A.clear(); PR.clear(); L.clear(); R.clear(); PN.clear(); SQ.clear(); B.clear(); root = -1;
        rng = seed * 2654435761u + 12345u; if (!rng) rng = 1;
    }
    size_t size() const { return A.size(); }
    inline u32 rnd() { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
    inline u64* blk(i32 x) { return &B[(size_t)x * S]; }
    inline bool qual(i64 ax, i64 a) const { return gt ? ax > a : ax < a; }

    // 子树 y 在窗口 j0 … j0+k−1 上的聚合加进 acc
    inline void add_sub(i32 y, i64 j0, int base, u64* ac, u64* as) {
        u64* b = blk(y);
        const i64* w = (const i64*)(b + WD); const u64* c = b + SC; const u64* s = b + SS;
        int m = k - base;
        for (int o = 0; o < m; o++) { int i = base + o; u64 ok = (w[i] == j0 + o) ? ~0ull : 0; ac[o] += c[i] & ok; if constexpr (SUM) as[o] += s[i] & ok; }
        for (int o = m; o < k; o++) { int i = o - m; u64 ok = (w[i] == j0 + o) ? ~0ull : 0; ac[o] += c[i] & ok; if constexpr (SUM) as[o] += s[i] & ok; }
        if constexpr (CW) WK.adds += k;
    }
    // 结点 x 自己在共同窗口 [j0, π_x] 上的值
    inline void add_own(i32 x, i64 pi, u64* ac, u64* as) {
        int d = (int)(pi - PN[x]); if (d >= k) return;  // 死结点：窗口都已关闭
        int len = k - d; u64* b = blk(x);
        for (int o = 0; o < len; o++) ac[o] += b[d + o];
        if constexpr (SUM) for (int o = 0; o < len; o++) as[o] += b[OS + d + o];
        if constexpr (CW) WK.adds += len;
    }

    // 一次下降：所有满足 ⋈ 的结点在 J(e) 上的聚合；同时记下插入路径（同值的插入方向与查询方向一致，两条路径相同）
    inline void query(i64 pi, i64 a, u64* ac, u64* as) {
        i64 j0 = pi - k + 1; int base = (int)((pi + 1) % k);
        path.clear();
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

    inline i32 new_node(i64 a, i64 pi, u32 sq, u32 pr) {
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
        const u64* bl = L[x] != -1 ? blk(L[x]) : nullptr; const u64* br = R[x] != -1 ? blk(R[x]) : nullptr;
        for (int o = 0; o < k; o++) {
            int i = base + o; if (i >= k) i -= k;
            i64 j = j0 + o;
            u64 vc = 0, vs = 0;
            if (d + o < k) { vc = b[d + o]; if constexpr (SUM) vs = b[OS + d + o]; }
            if (bl && ((const i64*)(bl + WD))[i] == j) { vc += bl[SC + i]; if constexpr (SUM) vs += bl[SS + i]; }
            if (br && ((const i64*)(br + WD))[i] == j) { vc += br[SC + i]; if constexpr (SUM) vs += br[SS + i]; }
            w[i] = j; c[i] = vc; if constexpr (SUM) s[i] = vs;
        }
        if constexpr (CW) WK.adds += k;
    }

    // 一次插入：沿 query 记下的路径把本事件的 J 槽加进祖先的 sub，挂叶子，按 treap 优先级向上旋转
    inline void insert(i64 pi, i64 a, u32 sq, const u64* own) {
        i64 j0 = pi - k + 1; int base = (int)((pi + 1) % k);
        const u64* oc = own; const u64* os = own + k;
        for (i32 x : path) {
            u64* b = blk(x);
            i64* w = (i64*)(b + WD); u64* c = b + SC; u64* s = b + SS;
            int m = k - base;
            for (int o = 0; o < m; o++) { int i = base + o; i64 j = j0 + o; u64 keep = (w[i] == j) ? ~0ull : 0; w[i] = j; c[i] = (c[i] & keep) + oc[o]; if constexpr (SUM) s[i] = (s[i] & keep) + os[o]; }
            for (int o = m; o < k; o++) { int i = o - m; i64 j = j0 + o; u64 keep = (w[i] == j) ? ~0ull : 0; w[i] = j; c[i] = (c[i] & keep) + oc[o]; if constexpr (SUM) s[i] = (s[i] & keep) + os[o]; }
            if constexpr (CW) WK.adds += k;
        }
        i32 n = new_node(a, pi, sq, rnd());
        u64* b = blk(n);
        memcpy(b, own, sizeof(u64) * (SUM ? 2 * k : k));
        {
            i64* w = (i64*)(b + WD); u64* c = b + SC; u64* s = b + SS;
            for (int o = 0; o < k; o++) { int i = base + o; if (i >= k) i -= k; w[i] = j0 + o; c[i] = oc[o]; if constexpr (SUM) s[i] = os[o]; }
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
        Tree T; T.init(k, gt, 0); T.rng = rng;
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

template <bool SUM, bool CW, bool MAP>
struct ArmOPP : ArmBase {
    std::vector<Scan<SUM, CW, MAP>> gs;
    void init(const Query& q_, int G) { base_init(q_, G); gs.assign(G, Scan<SUM, CW, MAP>()); for (auto& s : gs) s.init(q.k); }
    inline void process(int g, i64 pi, i64 a) {
        auto& S = gs[g];
        if (pi != last[g]) { S.purge(pi); last[g] = pi; }
        clear_acc();
        S.query(pi, a, q.gt, ac.data(), as.data());
        own_from_acc<SUM>(q.k, a, ac.data(), as.data(), own.data());
        emit(g, pi);
        S.insert(pi, a, seq[g]++, own.data());
    }
};

// M（switching = true）与 A4（false）
template <bool SUM, bool CW>
struct ArmM : ArmBase {
    struct G {
        bool index = false;
        Scan<SUM, CW, false> scan; Tree<SUM, CW> tree;
        std::vector<i64> pid; std::vector<u32> pcnt; u64 live = 0;  // 每个窗格的事件数（环）
    };
    std::vector<G> gs;
    bool switching = true; u64 tau_lo = 64, tau_hi = 128;
    u64 n_switch = 0, n_compact = 0;
    void init(const Query& q_, int Gn, bool sw, u64 tau) {
        base_init(q_, Gn); switching = sw; tau_lo = tau; tau_hi = 2 * tau; n_switch = n_compact = 0;
        gs.assign(Gn, G());
        for (int g = 0; g < Gn; g++) {
            auto& x = gs[g]; x.scan.init(q.k); x.tree.init(q.k, q.gt, (u32)g + 1); x.index = !sw;
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
        int K2 = SUM ? 2 * q.k : q.k;
        for (i32 y : keep) x.scan.insert(T.PN[y], T.A[y], T.SQ[y], T.blk(y));
        (void)K2;
        T.init(q.k, q.gt, T.rng); x.index = false; n_switch++;
    }
    inline void boundary(G& x, i64 pi) {
        int k = q.k;
        for (int i = 0; i < k; i++) if (x.pid[i] != NONE && x.pid[i] <= pi - k) { x.live -= x.pcnt[i]; x.pid[i] = NONE; x.pcnt[i] = 0; }
        if (!x.index) {
            x.scan.purge(pi);
            if (switching && x.live >= tau_hi) to_index(x, pi);
        } else {
            if (switching && x.live < tau_lo) to_scan(x, pi);
            else if (x.tree.size() > 2 * x.live) { x.tree.compact(pi); n_compact++; }
        }
    }
    inline void process(int g, i64 pi, i64 a) {
        auto& x = gs[g];
        if (pi != last[g]) { boundary(x, pi); last[g] = pi; }
        clear_acc();
        u32 sq = seq[g]++;
        if (x.index) {
            x.tree.query(pi, a, ac.data(), as.data());
            own_from_acc<SUM>(q.k, a, ac.data(), as.data(), own.data());
            emit(g, pi);
            x.tree.insert(pi, a, sq, own.data());
        } else {
            x.scan.query(pi, a, q.gt, ac.data(), as.data());
            own_from_acc<SUM>(q.k, a, ac.data(), as.data(), own.data());
            emit(g, pi);
            x.scan.insert(pi, a, sq, own.data());
        }
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
    std::string arm = "M", data, op = ">", agg = "COUNT", dump, oppidx = "vec";
    i64 W = 0, s = 0; int reps = 5, warmup = 1; long tau = 64, limit = 0; bool work = false;
};

static u64 mix(u64 x) { x += 0x9e3779b97f4a7c15ull; x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ull; x = (x ^ (x >> 27)) * 0x94d049bb133111ebull; return x ^ (x >> 31); }

struct Result { double sec; u64 checksum, outputs; std::vector<std::vector<std::pair<i64, u64>>> out; u64 extra1 = 0, extra2 = 0; };

template <class Arm, class InitF>
static Result run_arm(const Stream& S, const Query& q, InitF initf, bool keep) {
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
    if constexpr (requires { arm.n_switch; }) { r.extra1 = arm.n_switch; r.extra2 = arm.n_compact; }
    return r;
}

template <bool SUM, bool CW>
static Result dispatch(const Opt& o, const Stream& S, const Query& q, bool keep) {
    int Gn = (int)S.gname.size();
    if (o.arm == "OPP") {
        if (o.oppidx == "map") return run_arm<ArmOPP<SUM, CW, true>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
        return run_arm<ArmOPP<SUM, CW, false>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
    }
    if (o.arm == "M") return run_arm<ArmM<SUM, CW>>(S, q, [&](auto& a) { a.init(q, Gn, true, (u64)o.tau); }, keep);
    if (o.arm == "A4") return run_arm<ArmM<SUM, CW>>(S, q, [&](auto& a) { a.init(q, Gn, false, (u64)o.tau); }, keep);
    if (o.arm == "A1") return run_arm<ArmA1<SUM, CW>>(S, q, [&](auto& a) { a.init(q, Gn); }, keep);
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
        else { fprintf(stderr, "未知参数 %s\n", k.c_str()); return 2; }
    }
    if (o.data.empty() || o.W <= 0 || o.s <= 0 || o.W % o.s) { fprintf(stderr, "要 --data，且 W 被 s 整除\n"); return 2; }
    Stream S = load(o.data.c_str(), o.limit);
    Query q{o.op == ">", o.W, o.s, (int)(o.W / o.s), o.agg == "SUM"};
    bool keep = !o.dump.empty();
    FILE* info = o.dump == "-" ? stderr : stdout;  // 输出到 stdout 时，其余信息改走 stderr
    u64 ck = 0, outs = 0; bool first = true; bool same = true;
    Result last;
    for (int r = 0; r < o.warmup + o.reps; r++) {
        Result res = q.sum ? dispatch<true, false>(o, S, q, keep && r == o.warmup + o.reps - 1) : dispatch<false, false>(o, S, q, keep && r == o.warmup + o.reps - 1);
        if (first) { ck = res.checksum; outs = res.outputs; first = false; } else if (res.checksum != ck) same = false;
        if (r >= o.warmup) fprintf(info, "time\t%d\t%.6f\n", r - o.warmup + 1, res.sec);
        fflush(info);
        last = std::move(res);
    }
    fprintf(info, "checksum\t%016llx\n", (unsigned long long)ck);
    fprintf(info, "outputs\t%llu\n", (unsigned long long)outs);
    fprintf(info, "switches\t%llu\ncompactions\t%llu\n", (unsigned long long)last.extra1, (unsigned long long)last.extra2);
    if (!same) { fprintf(info, "checksum_mismatch_between_reps\n"); }
    if (o.work) {
        WK = Work();
        if (q.sum) dispatch<true, true>(o, S, q, false); else dispatch<false, true>(o, S, q, false);
        fprintf(info, "work_pred\t%llu\nwork_adds\t%llu\nwork_nodes\t%llu\n", (unsigned long long)WK.pred, (unsigned long long)WK.adds, (unsigned long long)WK.nodes);
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
