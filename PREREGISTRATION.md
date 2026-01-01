# Pre-registered Criteria: English Translation

This file translates the pre-registered pass/fail criteria of every experiment that has them,
and gives the outcome of each criterion with the report that judges it.

- **The Chinese text is authoritative.** Each pre-registration is the block of the experiment's
  `README.md` between the markers `<!-- 判据开始 -->` and `<!-- 判据结束 -->` ("criteria begin /
  end"; for E8, `<!-- 协议开始 -->` and `<!-- 协议结束 -->`, "protocol begin / end"). The same
  text is repeated at the top of the experiment's `compare_*.py`, which checks that the two copies
  are identical before it judges (first line of each report).
- **The originals were committed before the runs.** Each block was committed to version control
  before the first timing run of its experiment and has not changed since: for every block, the
  text in the commit that introduced it is identical, character by character, to the text in this
  archive (checked when this file was written). Commit identifiers are replaced by `<commit>` in
  this archive for anonymity, so the table below gives the dates of the commits and of the first
  timing runs (local time of the test machine, from the commits and the run logs).
- **This translation was written afterwards**, for this archive, after the runs of M1–E9 and of the
  local Parts A–C of E10; the outcome of E10's second-platform Part D was added when it returned. It covers the criteria blocks only; the implementation notes, development records and
  deviations (Sec. 2 and 3 of each README) are not translated. Text in [square brackets] is a
  translator's note, not part of the original.
- **Outcomes are as computed.** "Held" and "failed" are the verdicts that the experiment's own
  `compare_*.py` prints on the shipped logs (`README.md` Sec. 1 regenerates them). Criteria that
  failed are listed as they are.
- **Names.** In the logs and below, `OPP` is GRETA-C++ and `M` is SlotTree; `A1`, `A2`, `A4`, `A5`
  are the ablations per-window trees, eager deletion, always index and size threshold (table in
  `README.md`). "Development" and "test" are the development and test parts of a stream (`dev`,
  `hold` in the logs). C4, C5, C8, C26, C28 and C29 name claims in our internal claim ledger, the
  list that maps each claim of the paper to its evidence; each is explained where it first appears.
  `<internal>` replaces internal document names.
- **Engine versions.** M1, E1, E2 and E4 ran engine v1. E8 re-judged the criteria of E1, E2 and E4
  on engine v2, which the paper reports, with every line unchanged; E9 and E10 use v2.
- E5, E6, E7, E11 and E12 (synthetic streams, per-event latency, second platform, two added synthetic
  settings with 10⁶ events per window, a diagnosis of the second platform) are descriptive: their
  protocols were also committed before the runs but set no pass/fail line, so they do not appear here.
  E11 and E12 were added after the main experiments.

| Experiment | Chinese original | Criteria committed | First timing run | Outcome | Report |
|---|---|---|---|---|---|
| M1 (MVP) | `exp/m1-trend-index/README.md` Sec. 1 | 2026-10-27 | 2026-11-04 | **Failed**: K1 held; K2 held on Nasdaq and **failed on the Dublin bus** | `exp/m1-trend-index/report_m1.txt` |
| E1 (main table) | `exp/e1-main/README.md` Sec. 1 | 2026-11-04 | 2026-11-05 | Held: K1 and K3, on v1 and on v2 | `exp/e1-main/report_e1.txt`; v2: `exp/e8-inpane/report_e8.txt` |
| E2 (sweeps) | `exp/e2-sweep/README.md` Sec. 1 | 2026-11-04 | 2026-11-05 | Held: K4 on both streams, on v1 and on v2 | `exp/e2-sweep/report_e2.txt`; v2: `exp/e8-inpane/report_e8.txt` |
| E4 (selector) | `exp/e4-lowfreq/README.md` Sec. 1 | 2026-11-04 | 2026-11-05 | **Failed**: K2' held on Porto and **failed on METR-LA**, on v1 and on v2 | `exp/e4-lowfreq/report_e4.txt`; v2: `exp/e8-inpane/report_e8.txt` |
| E8 (engine v2) | `exp/e8-inpane/README.md` Sec. 1 | 2026-11-08 | 2026-11-08, after the commit | Held: (i); (ii) every verdict equals v1's | `exp/e8-inpane/report_e8.txt` |
| E9 (telemetry) | `exp/e9-aiinfra/README.md` Sec. 1 | 2026-11-10 | 2026-11-10 | Held: K5 on both streams | `exp/e9-aiinfra/report_e9.txt` |
| E10 (telemetry at scale) | `exp/e10-aiinfra-scale/README.md` Sec. 1 | 2026-11-11 | 2026-11-11 | K6 held at W = 10 min and was **not judged** at W = 30 min (one completed cell, two required); K7 held; Part D (second platform, descriptive): all 18 cells completed, checksums equal to the local ones | `exp/e10-aiinfra-scale/report_e10.txt` |

---

## M1 · MVP: the window-slot aggregation tree vs. the C++ re-implementation of GRETA / Cogra

Original: `exp/m1-trend-index/README.md` Sec. 1 (also at the top of `compare_m1.py`).

**Problem.** Trend aggregation over a single-type Kleene pattern
`RETURN g, AGG PATTERN E+ SEMANTICS skip-till-any-match WHERE [g] AND E.a ⋈ NEXT(E).a WITHIN W SLIDE s`,
⋈ ∈ {>, <} (strict), AGG ∈ {COUNT(*), SUM(E.a)}. Semantics as in the T20 criteria [an earlier
headroom test, not in this archive]: window j covers [j·s, j·s + W), with time 0 at the earliest time
in the data; for every window and every group, take all event sequences that are in increasing time
order within the group and whose every two adjacent events satisfy ⋈: COUNT counts the sequences,
SUM adds up the a of the events in each sequence and sums over the sequences (GRETA Definition 2,
Cogra §2.3). All arithmetic is modulo 2⁶⁴ (unsigned 64-bit wrap-around), and the attribute a is an
integer (cents / beats per minute / seconds); all arms use the same convention.

**Arms.**
- **OPP**: a C++ re-implementation of the GRETA runtime (PVLDB'17 §7–8; for a single-type Kleene
  pattern with an adjacent-event predicate, the mixed-granularity aggregator of Cogra (SIGMOD'19)
  reduces to it, Cogra §5 Alg. 2 lines 10–11): the stream is cut into panes (= the slide s), each pane
  has a vertex tree ordered by a, a new event does a range lookup in the trees of the panes covering
  it, and for every qualifying predecessor p and every window shared by p and e it adds once; a pane
  is deleted as a whole after the last window it belongs to closes.
- **M**: our method (Sec. 2.3): one aggregation tree per group, ordered by a, whose nodes store partial
  aggregates split by window slot; a new event does one descent and one insertion; when a group has
  few events, it falls back to OPP's scan by a rule.
- Ablations **A1** (one aggregation tree per active window, no slots) and **A4** (no switching by group
  size, always the index): reported, not part of the criteria.

**Primary metric.** Wall-clock time to process the whole stream (after the data is parsed into
memory, from the first event to the output of the last window), single thread, one row per
(data × query), median of 5 repetitions after 1 warm-up. The ratio of a row is r = T_OPP ÷ T_M.

**Development / test.** Development = the first 5 WPI stocks in ticker order (AMAT, CSCO, DELL, INTC,
IPIX) + PAMAP2 subjects 101–104; test = the other 5 WPI stocks (MSFT, ORCL, QQQ, RIMM, YHOO) + PAMAP2
subjects 105–109 (high frequency, judged by K1), and all of the Nasdaq minute bars and the Dublin bus
data (low frequency, judged by K2). The method is iterated on the development set only (one line per
variant in Sec. 3); on the test set every arm runs the final version once.

**Queries** (⋈ and s of each dataset as in T20; three window sizes): WPI price >, s = 10 s; PAMAP2
heart rate <, s = 30 s; Nasdaq close >, s = 5 min; bus delay <, s = 5 min; W ∈ {5, 10, 30} minutes;
AGG ∈ {COUNT, SUM}. 6 rows per dataset.

**K1** (high-frequency test, 6 WPI rows + 6 PAMAP2 rows): the median of r over the 12 rows is ≥ 1.5,
and at least one row has r ≥ 2.
**K2** (low-frequency test): for Nasdaq and for the bus data, each separately, the median of r over its
6 rows is ≥ 1 / 1.1 (i.e., M is not slower than 1.1 times OPP).
**Binary**: K1 and K2 both hold ⇒ **the MVP passes**; otherwise **it fails** (take the fallback of
`<internal>` Sec. 2; the stop-loss line is in `<internal>`).

**Mid-way check** (11-02, development set): compute r for the same 12 rows on the development data;
if the median is < 1.2, report it as is, and the user decides at that time whether to stop.

**Correctness gate** (not a criterion; if it fails, check the code first and do not judge): (a) on small
synthetic streams (≤ 60 events per group, random W / s / ⋈, a small attribute domain to create
duplicate values), every arm's per-window COUNT and SUM equal a brute-force enumeration by the
definition (Python big integers, then modulo); (b) on every real dataset, on the first 2,000 events of
every group, all arms are equal window by window.

**Descriptive** (reported, not part of the criteria): peak memory of every row (ru_maxrss); OPP's
predecessor visits and M's node visits (compared with T20's work model); time and r of A1 and A4;
median events per group and window.

**Outcome** (judged 2026-11-04; `exp/m1-trend-index/report_m1.txt`):
- K1 **held**: median r 10.28 over the 12 rows, maximum 95.14, minimum 2.08.
- K2 Nasdaq **held**: median r 0.968 (line 1 / 1.1 = 0.909).
- K2 Dublin bus **failed**: median r 0.893, i.e., M took 1.12 times OPP's time.
- Binary: **the MVP failed.**
- The mid-way check ran on 2026-11-04 instead of 11-02 (a schedule deviation, README Sec. 3):
  development median r 10.52 (minimum 2.20), above 1.2. The shipped `report_m1.txt` is the test run;
  `python3 -I exp/m1-trend-index/compare_m1.py dev` rewrites it with the development rows from the
  shipped logs.
- After this result the group-size rule was replaced by the cost rule of E4. The Nasdaq and bus data
  are therefore not test data for that rule, which E1 and E4 state in their criteria.

---

## E1 · Main table, ablations and memory

Original: `exp/e1-main/README.md` Sec. 1 (also at the top of `compare_e1.py`).

**Problem.** As in the M1 criteria (`exp/m1-trend-index/README.md` Sec. 1): trend aggregation over a
single-type Kleene pattern
`RETURN g, AGG PATTERN E+ SEMANTICS skip-till-any-match WHERE [g] AND E.a ⋈ NEXT(E).a WITHIN W SLIDE s`,
⋈ ∈ {>, <} (strict), AGG ∈ {COUNT(*), SUM(E.a)}; semantics, modular arithmetic, integer attributes and
window numbering all as in M1.

**Arms** (all in one binary, with the same compiler options):
- **OPP**: M1's GRETA / Cogra re-implementation, code unchanged.
- **M**: the window-slot aggregation tree (M1 Sec. 2.3) + the **cost-rule selector** (defined in
  `exp/e4-lowfreq/README.md` Sec. 1: it switches by the ratio of the scan's own accumulation count to
  the index path length; the constant c is set in E4's development phase and not changed once
  committed).
- Ablations, reported, not part of the criteria: **A1** one tree per active window (as in M1); **A2**
  expiry by deleting one by one (at the end of a pane, delete the dead nodes from the tree one by one
  and recompute the subtree slots along the path), otherwise as M; **A4** always index (as in M1);
  **A5** the switching rule reverted to M1's group-size threshold (τ_low = 16, τ_high = 32), otherwise
  as M.

**Primary metric.** Wall-clock time to process the whole stream (after the data is parsed into memory,
from the first event to the output of the last window), single thread. **Timing procedure (new)**:
every (arm × row) starts P = 3 processes; the 3 × (number of arms) runs of a row are interleaved
"process → arm" in turn (not one arm three times in a row); each process: parse the data (not timed)
→ 1 warm-up pass → R repetitions, R = min(200, max(5, ⌈2 s ÷ warm-up time⌉)), each pass building all
structures anew, with the timer around the processing of the whole stream + the output of the last
batch of windows; within a process take the median of the R passes; **the time of a row = the median
of the 3 processes**; also report the maximum ÷ minimum of the 3 processes as a noise band.
**Lengthening short rows**: for a row whose warm-up pass takes < 5 ms, concatenate
D = min(50, ⌈5 ms ÷ warm-up time⌉) copies of the stream, each shifted in time by the whole duration
(groups and order unchanged); all arms use the same lengthened stream, and the table states D. The
ratio of a row is r = T_OPP ÷ T_M.

**Data and queries** (one ⋈ and one s per dataset, as in T20 / M1; W ∈ {5, 10, 30} minutes;
AGG ∈ {COUNT, SUM}; 6 rows per dataset):
- Test: the other 5 WPI stocks (price >, s = 10 s), PAMAP2 subjects 105–109 (heart rate <, s = 30 s),
  Nasdaq minute bars (close >, s = 5 min), Dublin bus (delay <, s = 5 min); **new data only if the
  user approves; if not approved it is left out and recorded as a deviation**: Binance aggTrades, 5
  trading pairs × 1 day (price >, s = 10 s; high frequency), Porto taxis 2013-07 (speed derived from
  GPS <, s = 1 min; medium frequency), METR-LA (vehicle speed >, s = 5 min; low frequency).
- The development rows are run as well and marked "development" in the table: the first 5 WPI stocks,
  PAMAP2 subjects 101–104.
- The data preparation rules are in Sec. 2.2 (conversion to integers, time in microseconds, derived
  attributes); the preparation script is not changed after it is committed.

**K1** (C4 [the main-table claim]; high-frequency test rows = 6 WPI + 6 PAMAP2, plus 6 Binance if
available): the median of r is ≥ 1.5, and at least one row has r ≥ 2.
**K3** (the selector does not hurt high frequency; the same rows): the median of T_M ÷ T_A5 is ≤ 1.05.
**Binary**: K1 and K3 both hold ⇒ **the main table holds**, and C4 goes into the main text; otherwise
do not stop: rewrite C4 according to the measured numbers (in the claim ledger) and write the reason in
Sec. 0.
**Not judged in this experiment**: C5 (not slower than 1.1 times on medium- and low-frequency data) is
judged on E4's new test data; Nasdaq and bus are reported in this experiment, with the note in the
table "the switching rule was redesigned after seeing M1's bus result; these two are not test data for
the rule".

**Design rules for the ablations** (not criteria; if one is triggered, change the design and record a
deviation):
- A1: only the test rows with k ≥ 2 (at k = 1 the two designs are the same structure); if the median of
  T_A1 ÷ T_M is < 1 ⇒ the paper's multi-window scheme switches to A1.
- A2: if the median of T_A2 ÷ T_M over the high-frequency test rows is < 1 ⇒ expiry switches to deleting
  one by one.
- A4, A5: reported; contribution = Σ T_A ÷ Σ T_M summed directly per dataset, plus the median over rows.

**Correctness gate** (not a criterion; if it fails, check the code first and do not time): M1's (a)
brute-force check on small synthetic streams and (b) window-by-window equality on the first 2,000
events of every group of every real dataset, rerun for all six arms and all data; plus (c) in index
mode, the "accumulated count of qualifying predecessors" obtained by the descent equals OPP's
accumulation count in scan mode, event by event (the input of E4's rule).

**Descriptive** (reported, not part of the criteria): peak memory (ru_maxrss) of every row and arm and
the range of M ÷ OPP, compared with the analytic ratio of node sizes (M: own k + sub k slots per node,
with cnt and sum each for SUM, plus the window number and the live-event count; OPP: k or 2k numbers
per vertex; compaction allows dead nodes ≤ live nodes); work counts of every row and arm (OPP:
predecessor visits, window additions; M: node visits, slot reads and writes); M's switches per row and
the share of events processed in each mode; median events per group and window; the noise band of the
3 processes; Σ T_OPP ÷ Σ T_M summed directly over the samples (one for high, one for low frequency).

**Outcome** (judged 2026-11-05; v1: `exp/e1-main/report_e1.txt`; v2: `exp/e8-inpane/report_e8.txt`
and `exp/e8-inpane/report_e1_v2.txt`):
- K1 **held**: over the 18 high-frequency test rows (WPI, PAMAP2, Binance) median r 11.89, maximum
  107.8, minimum 1.83. v2: 12.46, 107.5, 1.79.
- K3 **held**: median T_M ÷ T_A5 1.031 (line 1.05). v2: 1.047, a margin of 0.003.
- Binary: the main table holds, on v1 and on v2.
- Ablation design rules: not triggered. A1 median 3.55 (v2 3.51); A2 median 1.40 (v2 1.41).
- After the judgment, one row (Binance, COUNT, W = 10 min) was found disturbed during its run and was
  re-run (README Sec. 3, deviation 2); the verdicts were left as judged.

---

## E2 · Sweeps over the window size and the predicate's selectivity

Original: `exp/e2-sweep/README.md` Sec. 1 (also at the top of `compare_e2.py`).

**Problem.** The query class of E1; AGG is COUNT(*) only. To answer: how r = T_OPP ÷ T_M changes with
the events per group and window n and with the predicate's selectivity σ, and where the headroom
begins.

**Arms**: OPP, M (the final engine of E1 Sec. 1, with the switching constant c set by E4). Timing as in
E1 (median of 3 processes, lengthening of short rows).

**W sweep**: the 5 WPI test stocks (price >, s = 10 s), PAMAP2 subjects 105–109 (heart rate <,
s = 30 s), plus Binance aggTrades (price >, s = 10 s) and Porto 2013-07 (speed <, s = 1 min) if the user
has approved them: W ∈ {1, 2, 5, 10, 30, 60} minutes, 6 rows per dataset.

**Selectivity sweep**: W = 10 minutes, the same data; the predicate becomes a_p · X ⋈ a_e (in
integers: a_p · X_num ⋈ a_e · X_den, X_den = 1000), with X chosen from {0.900, 0.905, …, 1.100} by this
rule: for each target σ ∈ {0.1, 0.3, 0.5, 0.7, 0.9}, take the X for which "the share of pairs that
satisfy the predicate, among the event pairs of an earlier p and a later e in the same group and the
same window" is closest to σ; `prep_e2.py` computes this share on each dataset (≤ 10⁴ pairs sampled
per group and window, fixed seed), and X and the actual share are reported. Both arms use the same
predicate: the index's prefix threshold becomes the corresponding integer bound of
a_e · X_den ÷ X_num, and the scan's range lookup changes the same way. 5 rows per dataset.

**K4** (C8 [the claim that the headroom grows with the events per group and window and with
selectivity]; only the two high-frequency test datasets, WPI and PAMAP2): on each dataset, (i) r is
non-decreasing over the 6 points of W, allowing 10% noise (for every two adjacent points
r_{i+1} ≥ 0.9 · r_i), and r(60 min) ≥ 2 · r(1 min); (ii) r(σ = 0.9) ≥ r(σ = 0.1).
**Binary**: (i) and (ii) hold on both datasets ⇒ **C8 goes into the main text** ("the headroom grows
with the events per group and window and with selectivity"); otherwise do not stop: rewrite C8 as a
description of the measured shape and write the reason in Sec. 0.

**Descriptive** (reported, not part of the criteria): the median events per group and window n of every
row (including the actual n in the W sweep); a scatter plot of r against n over all rows (across
datasets, including E1's rows); for every dataset, the n at which r first reaches ≥ 1 and ≥ 1.5 (linear
interpolation between adjacent points; "not reached" if it is not reached); M's switches per row and the
share of events in index mode; the ratio of work counts per row (OPP window additions ÷ M slot reads
and writes) against the ratio of times.

**Outcome** (judged 2026-11-07; v1: `exp/e2-sweep/report_e2.txt`; v2: `exp/e8-inpane/report_e8.txt`):
- WPI (i) **held**: r = 1.04 / 1.21 / 1.84 / 2.75 / 4.61 / 8.49 for W = 1 / 2 / 5 / 10 / 30 / 60 min,
  r(60) ÷ r(1) = 8.15; (ii) **held**: r 4.83 at σ = 0.9 against 1.26 at σ = 0.1.
  v2: r(60) ÷ r(1) = 8.48; 4.87 against 1.27.
- PAMAP2 (i) **held**: r from 2.33 to 154.9, every step increasing, r(60) ÷ r(1) = 66.4; (ii) **held**:
  21.9 against 8.79. v2: r(60) ÷ r(1) = 62.96; 22.4 against 8.86.
- Binary: C8 goes into the main text, on v1 and on v2.

---

## E4 · Cost-rule selector: setting c on development data, medium/low-frequency test

Original: `exp/e4-lowfreq/README.md` Sec. 1 (also at the top of `compare_e4.py`). The development
phase ran before E1, and c was committed before E1 ran; the test rows are E1's.

**Problem.** The query class of E1 / M1. To answer: after M1's "group-size threshold" is replaced by
the cost rule below, is the method not slower than 1.1 times the GRETA / Cogra re-implementation (OPP)
on real medium- and low-frequency streams, without a loss on high frequency (the latter is judged by
E1's K3)?

**Cost rule (M's final switching rule)**: every group has two modes (index = the window-slot
aggregation tree; scan = OPP's structure, shared code) and starts in scan. Every group keeps two
quantities, averaged per event and smoothed per pane by an EWMA (α = 1/2, initial value 0):
- s̄: the **scan cost** = the number of window additions that processing this event the OPP way would
  take (= the sum over qualifying predecessors p of |shared windows|). In scan mode it is what the scan
  actually does; in index mode the descent gives it: every subtree slot stores, besides cnt and sum,
  "the number of live events of this window", nev, and the Σ_j acc_nev_j accumulated by the descent
  equals exactly this number.
- ī: the **index cost model** = k · 2 · ⌈log₂(n_live + 2)⌉ (the descent and the insertion each touch
  about log n nodes, with k slots per node; n_live = the group's live events). Both modes use the model,
  not a measurement.
At the end of every pane (when the group's next event enters a new pane, after expiry), update s̄ and ī
with the average over the n_p events of the pane that just ended (no update if n_p = 0); then: in scan
mode, if s̄ > 2c · ī ⇒ switch to index; in index mode, if s̄ < c · ī ⇒ switch back to scan
(hysteresis 2). Switching is done as in M1 (rebuild the other structure from the live events). **c is
set on development data only**: c ∈ {0.5, 1, 1.5, 2, 3, 4, 6}.

**Arms**: OPP (M1's re-implementation, unchanged); M (the window-slot aggregation tree + the rule
above); for comparison A5 (the same tree + M1's size threshold τ_low = 16) and A4 (always index), read
from E1.

**Development phase (setting c)**: rows = the 5 WPI development stocks (s = 10 s) × W ∈ {1, 2, 5} min,
PAMAP2 subjects 101–104 (s = 30 s) × W ∈ {1, 2} min, all 54 motes of Intel Lab (temperature <,
s = 1 min) × W ∈ {5, 10, 30} min, each × AGG ∈ {COUNT, SUM}; Intel Lab only if the user approves; if not
approved it is left out and recorded as a deviation. [Under the preparation rules of README Sec. 2.2,
two motes have no complete row, so the stream has the 52 groups given in the paper (README Sec. 3).] Every row is run once
for each of the 7 values of c (1 warm-up + median of 5 passes, single process);
score(c) = the geometric mean over the rows of T_M(c) ÷ min_c′ T_M(c′); take the c with the smallest
score, and the larger c when they differ by less than 1% (biased toward the scan). Once set, c is
written into Sec. 3 of this README and into `run_e4.sh`, and **it is not changed for the test**.

**Test phase (judging K2')**: Porto taxis 2013-07 (medium frequency, speed <, s = 1 min) and METR-LA
(low frequency, vehicle speed >, s = 5 min), each W ∈ {5, 10, 30} min × AGG ∈ {COUNT, SUM} = 6 rows; the
times of OPP and M are read from E1's `handoff/e1_times.tsv` (E1's timing: median of 3 processes,
lengthening of short rows); r = T_OPP ÷ T_M. Both datasets only if the user approves the download.
**K2'**: for the 6 Porto rows and the 6 METR-LA rows, **each separately**, the median of r is ≥ 1 / 1.1.
**Binary**: both hold ⇒ **C5 holds** ("not slower than 1.1 times the competitor on medium- and
low-frequency test streams" goes into the main text, and the switching rule is written into the method
section as a component of our own design, with the ablations A4 / A5); otherwise **C5 fails**: the main
text writes it as a cost of the method (on low-frequency streams the fallback to the scan is still
somewhat slower; numbers reported), and the switching rule's contribution is still reported as
measured. If only one dataset is available, judge only that one and mark the other "not judged".

**Not judged in this experiment**: the 12 rows of Nasdaq and bus under the new rule are reported (read
from E1), with the note in the table "the rule was redesigned after seeing M1's bus result; these two
are not test data for the rule"; M1's judgment and numbers are not changed.

**Correctness gate** (not a criterion; if it fails, check the code first): E1's (a)(b), plus (c) on small
synthetic streams, the Σ_j acc_nev_j computed in index mode equals the scan mode's accumulation count
event by event (with one very small and one very large c, so that both modes are exercised).

**Descriptive** (reported, not part of the criteria): for every development row, the time curve over the
7 values of c and score(c); for every test row, the switches, the share of events processed in each
mode and the median of s̄ ÷ ī; r of A5 and A4 on the test rows for comparison; median events per group
and window; the events and groups of Intel Lab (development), Porto and METR-LA.

**Outcome** (development 2026-11-05, test judged 2026-11-05; v1: `exp/e4-lowfreq/report_e4.txt`;
v2: `exp/e8-inpane/report_e8.txt`):
- Development: c = 2 (the smallest score, 1.0297, is at c = 1; c = 1, 1.5 and 2 are within 1% of it, so
  the largest, 2).
- K2' Porto **held**: median r 0.963 (line 0.909; range 0.908–1.003). v2: 0.966.
- K2' METR-LA **failed**: median r 0.827, i.e., M took 1.21 times OPP's time (range 0.810–0.877).
  v2: 0.815.
- Binary: **C5 failed**, on v1 and on v2. As the criterion prescribes, the paper reports the slowdown on
  sparse streams as a cost of the method.

---

## E8 · Engine v2: the selector also checks inside a pane

Original: `exp/e8-inpane/README.md` Sec. 1, the protocol block (also at the top of `compare_e8.py`).
The protocol was approved by the user and committed on 2026-11-08 before the runs; the local runs
started the same evening and the second-platform run on 2026-11-09.

**Change (engine v2)**: copy `exp/e1-main/src/trend.cpp` (v1, frozen) to `src/trend.cpp` and change
only `ArmM`: in scan mode, every time the current pane has B more events (when the pane's event count
n_p is a multiple of B), make the same comparison as at a pane boundary with the pane's sums so far,
s_p ÷ n_p > 2c · i_p ÷ n_p (s_p and i_p are the sums over the pane's events of the scan cost and of the
index cost model, defined as in `exp/e4-lowfreq/README.md` Sec. 1), and if it holds, switch to the index
at once (the current pane is already in the scan structure; the switch moves all live panes into the
tree, as a switch at a pane boundary does). Index → scan is still decided only at pane boundaries; the
EWMA update at the pane boundary (α = 1/2, with s_p ÷ n_p and i_p ÷ n_p of the whole pane, including the
events before and after the switch) and the two lines (s̄ > 2c · ī to the index, s̄ < c · ī back) are
unchanged. **c = 2 unchanged, B = 1024.** Only the two arms with the cost rule (M = SlotTree in the
paper, A2) are affected; the code paths of OPP (GRETA), A1, A4 (always index) and A5 (size threshold)
are unchanged (`tests/diff_v1.py`). `--inpane 0` turns the check off and makes the same decision as v1
for every event (gate (e)).

**Scope of the re-runs**: only M and A2 are re-run (v2, B = 1024, c = 2); the numbers of
OPP / A1 / A4 / A5 are copied from each experiment's v1 table. Reason: these four arms are the same
source with the same compiler options as v1, and their code paths did not change; supporting evidence
in "OPP check" below. Every experiment is re-run under its own original procedure:
- **E1**: 54 rows (9 splits × W ∈ {5, 10, 30} min × COUNT / SUM) × {M, A2}; E1's timing procedure
  (`exp/e1-main/README.md` Sec. 1: 3 processes, "process → arm" interleaving, automatic pass count, work
  counters in the first process) and its deviation 1 (single timing when the probe pass takes ≥ 60 s).
  The lengthening factor D of a short row is taken from the row in the v1 table (no new OPP probe to set
  D; a row uses the same lengthened stream in v1 and v2); interleaving only among the re-run arms.
- **E2**: the 24 rows of the W sweep + the 11 rows of the selectivity sweep × {M}, procedure as in E1.
- **E4**: no separate test run; K2' is read from E1's v2 table (as E4 originally did). The development
  phase (setting c) is not re-run: the development data (WPI development, PAMAP2 subjects 101–104,
  Intel Lab) have at most 265 / 275 / 36 events per group and pane, < B, so the check cannot trigger for
  any c, v2 makes the same decision as v1 for every event on these rows, and c = 2 stands.
- **E5**: 76 cells × {M}, E5's timing procedure (`exp/e5-synth/README.md` Sec. 1: a probe pass → if
  < 60 s, a new process with 1 warm-up + median of 3 passes; if ≥ 60 s, 1 timed pass without warm-up;
  S3 with `--work`).
- **E6**: 4 rows × {M, A2}, E6's procedure (per-event timing, 1 warm-up + 3 passes).
- **E7**: 30 rows on the workstation × {M}, E7's procedure (as E1, D = 1), remote entry `ws_e8.sh`.
- Output tables with the same structure as the original experiments' (columns and headers identical to
  v1) go into `handoff/`: `e1_times_v2.tsv`, `e1_rerun_binance_v2.tsv` (the cell of E1's deviation 2,
  with M / A2 replaced by v2 on the same cell), `e2_times_v2.tsv`, `e5_times_v2.tsv`,
  `e6_latency_v2.tsv`, `e6_dist_v2.tsv`, `e7_times_v2.tsv`; the number of in-pane switches of every
  M / A2 process goes into `handoff/e8_inpane.tsv`.

**Criteria** (the row time is computed as in each original experiment: E1 / E2 / E7 = the median of the
3 within-process medians; E5 = the median of the passes):
- **(i) The fix works**: in E5's S1, on the 24 cells with n ∈ {10⁵, 10⁶} (3 value distributions × 2
  values of n × k ∈ {1, 2, 6, 30}), **every cell** has T_M(v2) ÷ T_A4 ≤ 1.5 (T_A4 from E5's v1 table)
  ⇒ the fix works. If not, do not stop: list which cells exceed the line and by how much, and write it
  in Sec. 0; how the paper reports it is decided by the main session [the session that plans the
  paper].
- **(ii) Re-judging** (lines unchanged, computed by the original experiments' comparison code on the v2
  tables): E1's K1 and K3 (`exp/e1-main/README.md` Sec. 1; `compare_e1.judge`); E4's K2'
  (`exp/e4-lowfreq/README.md` Sec. 1; `compare_e4.hold`); E2's K4 (`exp/e2-sweep/README.md` Sec. 1;
  `compare_e2`). Each binary verdict is given as in the original, side by side with the v1 judgment.
- **(iii) Regression check** (reported only, not judged): for every experiment and every re-run arm, the
  median and range of T(v2) ÷ T(v1) per cell; for E5 also split into "in-pane check triggered / not
  triggered".

**Supporting evidence** (reported only, not judged):
- **OPP check**: with the v2 binary, re-time OPP on 3 fast cells of E1 (WPI, PAMAP2 and Porto test,
  COUNT, W = 5 min) under E1's procedure; report T_OPP(this run) ÷ T_OPP(v1) and the 3-process noise
  bands of both runs.
- **A4 re-timed in the same session**: re-time A4 once on the 24 cells of (i) in the same session under
  E5's procedure; report T_M(v2) ÷ T_A4(this run), side by side with the v1 A4 used in (i).

**Correctness gate** (not a criterion; if it fails, check the code first and do not time;
`tests/run_tests.sh`): (a) brute force on small synthetic streams, (c) per-event scan cost against brute
force, (a′) true enumeration, all by calling E1's scripts directly, with M / A2 configurations with
B ∈ {1, 2} and c ∈ {0.001, 0.05, 0.1, 0.2} appended to the table of arm configurations so that in-pane
switches really happen on small streams; (v) every appended configuration makes an in-pane switch on at
least one stream; (b) on 10 real splits, the first 2,000 events of every group × all W × COUNT / SUM ×
12 arm configurations equal OPP window by window; (c′) on real data, always index, always scan and
in-pane switching give the same per-event scan cost; (e) on the full data of every real dataset, v2 with
`--inpane 0` and v1 have identical checksums, switch counts and compaction counts. During the runs: in
every re-run cell, the checksum of M / A2 equals the checksum of OPP on the same row (for the E5 cells
where OPP was skipped, v1's M / A4 / A5); on the E7 workstation the gcc-built v2 first passes
(a)(c)(a′)(v), then the timing runs.

**Descriptive** (reported): the in-pane switches and the total switches of every cell; the full reports
regenerated by the original experiments' comparison code on the v2 tables (`report_e1_v2.txt`,
`report_e2_v2.txt`, `report_e5_v2.txt`, `report_e6_v2.txt`, `report_e7_v2.txt`), where E6's tail
latency will include the pause of the one tree build of the in-pane switch.

**Outcome** (`exp/e8-inpane/report_e8.txt`):
- (i) **held**: all 24 cells ≤ 1.5; T_M(v2) ÷ T_A4(v1) median 0.983, range 0.813–1.104. On v1, 17 of
  the 24 cells were above 1.5, up to 214.
- (ii) Every binary verdict equals v1's: E1 K1 **held** (median r 12.46) and K3 **held** (1.0471, line
  1.05); E4 K2' **held** on Porto (0.966) and **failed** on METR-LA (0.815), so C5 failed as on v1; E2 K4
  **held** on WPI and PAMAP2 (r(60) ÷ r(1) = 8.48 and 62.96). Details under E1, E2 and E4 above.
- (iii) Reported in the report's section (iii); for example E1's M arm, v2 ÷ v1 per cell, median 1.003
  (0.889–1.140, 54 cells).
- One deviation (README Sec. 3): the in-pane switch summary first missed the second platform's
  switch log and was regenerated; it affects only a descriptive section.

---

## E9 · AI-infrastructure telemetry: GPU power and LLM serving latency

Original: `exp/e9-aiinfra/README.md` Sec. 1 (also at the top of `compare_e9.py`). The slicing parameters
that Sec. 2 leaves to the experiment stage were set from the data's shape only and also committed before
the first engine run (README Sec. 3).

**Background**: the rule of thumb the paper obtained on seven real streams is "settings with median
events per group and window n ≥ 106 have r = T_GRETA-C++ ÷ T_SlotTree ≥ 1.79"
(`exp/e8-inpane/report_e8.txt`, caption of Fig. 4). These two streams come from a domain that neither
development nor the earlier tests touched; this experiment is an out-of-sample test of the rule, with
the MVP's lines (1.5 and 2), not the 1.79 seen after the fact.

**Settings**: 6 per stream: W ∈ {5, 10, 30} min × AGG ∈ {COUNT, SUM}, slide s = 30 s
(k = 10 / 20 / 60), ⋈ is < (rising values), skip-till-any-match. n = the median, for the stream and that
W, of the events per (group, window), computed as in E1.

**K5 (judged once per stream)**: among the stream's settings with n ≥ 106, **every one** has r ≥ 1.5,
**and at least one** has r ≥ 2. A stream with no setting of n ≥ 106 ⇒ the stream is marked "not judged
(sparse)", numbers reported. Cells not run under the rules of Sec. 2 (GRETA-C++ timeout, memory cap) are
not counted, but a judgment needs at least 2 completed cells with n ≥ 106.

**Binary**:
- K5 holds on both streams ⇒ **C26 goes into the main text**: "on AI-infrastructure telemetry never used
  in development, the same holds for settings with n above about a hundred", and the introduction opens
  with the numbers of these two streams.
- Only one holds ⇒ the introduction opens with the stream that holds; the other's numbers are reported,
  stating that it missed the line.
- Neither holds ⇒ the introduction keeps only the cited motivation of cluster monitoring and does not
  open with the numbers of these two streams; the results of both streams are reported as the limits of
  the method's applicability.
- In every case, the engine and the constants may not be tuned for these two streams; anything changed
  after seeing the results is recorded as a deviation in Sec. 3.

**Outcome** (2026-11-10; `exp/e9-aiinfra/report_e9.txt`):
- GPU power (MIT Supercloud): 6 settings with n ≥ 106, all completed; r from 8.14 to 38.14, median
  12.07 ⇒ K5 **held**.
- LLM time to first token (Chutes): 6 settings with n ≥ 106, all completed; r from 13.19 to 57.09,
  median 18.34 ⇒ K5 **held**.
- Binary: C26 goes into the main text.

---

## E10 · AI-infrastructure telemetry at cluster scale

Original: `exp/e10-aiinfra-scale/README.md` Sec. 1 (also at the top of `compare_e10.py`). The values that
Sec. 3 leaves to the experiment stage (S, the input-footprint subtraction, the shapes of the streams)
were set from the data's shape only and committed before the first engine run (README Sec. 3).

**Arms and procedure**: GRETA-C++ (`OPP`) and SlotTree (`M`, c = 2, B = 1024), the same v2 binary as in
E9; r = T_GRETA-C++ ÷ T_SlotTree; timing, the not-run rules and the conditions for single timing all as
in E9 (`exp/e9-aiinfra/README.md` Sec. 2). ⋈ is <, s = 30 s, skip-till-any-match. The lines are the
MVP's (1.5 and 2).

**Part A · Cluster replay (binary, K6).** Question: when a few hundred GPUs report at the same time, how
many GPUs can one core keep up with, and how much state memory does each GPU take?
- Replay stream R(G): from E9's stream A (`exp/e9-aiinfra/data/gpu_hold.tsv`, 25 [job, GPU] pairs), cut
  segments of real readings of D = 3,600 s each; each of G replayed GPUs plays one segment, all
  reporting at the same time. Cutting (deterministic, no picking): from the time t0 of each source
  group's first event, cut consecutive non-overlapping segments [t0 + mD, t0 + (m+1)D), m = 0, 1, …;
  keep only complete segments (the group's duration covers the whole segment, and the segment holds
  ≥ 0.5 × D × 10 events); sort the segments by (m, the order in which the source group first appears in
  the file), S segments in all. The i-th replayed GPU (i = 0 … G − 1) plays segment (i mod S), shifted
  in time to start at o_i = (i × 7,919) mod 100,000 microseconds (staggering the GPUs' sampling phases),
  with group id i; all events are sorted by (time, group id). When G > S, segments are reused (the same
  readings with different phases); S and the number of reuses are reported as they are.
- Cells: G ∈ {25, 100, 400} × W ∈ {10, 30} min, AGG = COUNT (the aggregate of the query box in the
  introduction; in E9, COUNT's r is lower than SUM's, so choosing it gains nothing). Not-run rules as in
  E9: GRETA-C++ is not run on a cell whose extrapolated single pass exceeds 7,200 s; neither arm is run
  on a cell whose extrapolated SlotTree peak memory exceeds 10 GiB. The extrapolation takes the
  measurement at the next smaller G with the same W, times the ratio of the G values; G = 25 is always
  run.
- Reported per cell: events, the times of both arms, r, **GPUs one core keeps up with** = G × D ÷ T
  (D seconds of readings processed in T seconds), **state memory per GPU** = (peak RSS − input
  footprint) ÷ G (how the input footprint is subtracted is written into Sec. 3 before the runs).
- **K6 (judged once per W, on the local cells only)**: among the completed cells of that W, **every one**
  has r ≥ 1.5, **and at least one** has r ≥ 2. Fewer than 2 completed cells ⇒ that W is marked "not
  judged".
- Binary: K6 holds for both W ⇒ **C28 goes into the main text** ("for one hour of readings of G GPUs
  reporting at the same time, GRETA-C++ takes … s and SlotTree … s; one core keeps up with … and …
  GPUs", with the largest completed G), and the introduction's hook may switch to this framing. Only one
  W holds ⇒ only that W is written. Neither holds ⇒ reported as a limit of applicability, and the
  introduction does not use this framing. The per-GPU state memory goes into the Limitations in every
  case.
- Expectation (no line, reported): r decreases as G grows (E5's synthetic S2: r falls from 34 to 18 as
  the groups go from 1 to 100).

**Part B · All models of the same period (binary, K7).** Question: E9's stream B took only the 10 busiest
models; does the conclusion still hold with all models?
- Stream: Chutes shard 0, the same period as E9's stream B (the first T = 27 hours), the requests of
  **all models** with a non-empty `ttft`; event definition and d = 3 as in E9. Group = model.
- Settings: W ∈ {5, 10, 30} min × COUNT / SUM, 6 in all. Arms: GRETA-C++ and SlotTree, plus always index
  (`A4`) as a descriptive comparison.
- **K7**: among the completed settings, **every one** has r ≥ 1.5, **and at least one** has r ≥ 2; fewer
  than 2 completed ⇒ not judged. By its median n this stream may fall below 106, so K5's condition on n
  is not used here: the time of the whole stream is decided by its few busiest models, which is exactly
  what is to be tested.
- Binary: holds ⇒ **C29 goes into the main text** ("on all … models of the same period, r is …"), and
  "the 10 busiest" is written as a one-sentence slicing rule. Fails ⇒ reported, stating that the speed-up
  holds only on busy models.
- Also reported (no line): the number of models, the events, the median n for each W, the share of
  events in groups with n ≥ 106; T_always index ÷ T_SlotTree (in the same stream busy models use the
  tree and rare models the scan: how much the selector saves over always indexing).

**Part C · Per-event latency (descriptive, no line).** E6's protocol (`exp/e6-latency/README.md`
Sec. 1) applied unchanged to E9's two streams: W = 10 min, COUNT, both arms; report p50 / p99 / p99.9 /
maximum, and the counts, shares and longest pauses of compactions and switches.

**Part D · Second platform (descriptive, no line).** E7's protocol (`exp/e7-platform/README.md` Sec. 1)
unchanged: E9's 12 settings and Part A's 6 replay cells re-run on the workstation (i9-14900K, Linux,
gcc), both arms; the memory not-run line becomes 150 GiB (the workstation has 192 GB), the 7,200 s line
is unchanged. The workstation downloads the data itself with E9's slicing scripts and checks the
sha256 (the MIT Supercloud license forbids redistribution, so the data does not travel through git); if
the Chutes shard cannot be downloaded, only the GPU stream and the replay are run, and this is reported.
Checksums must equal the local ones cell by cell (for replay cells not run locally, only the two arms
must agree). Report each stream's minimum / median / maximum r and the Spearman correlation with the
local r; for the replay cells, the same quantities as in Part A. K6 is judged only on the local cells;
the workstation's replay cells are descriptive.

**General**: no timing unless the correctness gate passes: on every cell the arms have identical
whole-stream checksums; on the replay stream R(100) and on Part B's stream, the first 2,000 events of
every group equal the recurrence reference of `exp/e1-main/brute_e1.py` window by window. The engine and
the constants may not be tuned for these streams; anything changed after seeing timing data is recorded
as a deviation in Sec. 3.

**Outcome** (local Parts A–C, 2026-11-11; `exp/e10-aiinfra-scale/report_e10.txt`):
- Part A, K6 at W = 10 min **held**: all 3 cells completed, r = 14.11 / 14.00 / 12.13 for G = 25 / 100 /
  400.
- Part A, K6 at W = 30 min **not judged**: only G = 25 completed (r = 39.19). By the pre-registered memory
  rule, R(100) and R(400) were extrapolated to 13.33 and 53.33 GiB, above 10 GiB, so neither arm ran
  (`handoff/e10_rules.tsv`).
- Binary: only W = 10 min holds, so C28 is written for W = 10 min only: for one hour of readings of 400
  GPUs, GRETA-C++ takes 570.7 s and SlotTree 47.04 s; one core keeps up with 2,523 and 30,609 GPUs.
- State memory per GPU (goes into the Limitations): SlotTree 16.89 / 12.15 / 7.23 MB at W = 10 min for
  G = 25 / 100 / 400 (lower bound 15.71 / 10.86 / 5.91 MB) and 135.84 MB at W = 30 min, G = 25; GRETA-C++
  2.47 / 1.94 / 1.56 MB and 11.05 MB.
- Part B, K7 **held**: 48 models, 2,645,481 events; all 6 settings completed, r = 13.04 / 13.43 (W = 5 min,
  COUNT / SUM), 17.20 / 15.97 (10 min), 43.47 / 111.05 (30 min); minimum 13.04, median 16.59. Binary: C29
  goes into the main text. Always index ÷ SlotTree: median 1.012 (0.955–1.028).
- Part C (descriptive): the latency quantiles, compactions, switches and longest pauses of both
  telemetry streams are in the report's Part C tables.
- Part D (second platform, descriptive; returned 2026-11-12, workstation time): all 18 cells completed on
  the i9-14900K (g++ 13.3.0, same source and flags); neither not-run rule triggered. The five stream files
  have the same SHA-256 as the local ones; the checksums of the two arms agree on all 18 cells and equal
  the local ones on the 16 cells run on both machines. GPU power: r minimum 4.88, median 11.37, maximum
  38.15; LLM latency: 7.26 / 16.08 / 62.08; r(workstation) ÷ r(local) is 0.55–1.10, and the Spearman
  correlation of r over the 16 common cells is 0.853. Replay: r = 6.43 / 10.36 / 8.61 at W = 10 min and
  33.06 / 25.73 / 21.53 at W = 30 min for G = 25 / 100 / 400; at W = 30 min and G = 400, GRETA-C++ takes
  3,993 s and SlotTree 185.5 s for the hour of readings. State memory per GPU: SlotTree 12.80 / 12.12 /
  11.89 MB at W = 10 min and 84.36 / 82.58 / 82.45 MB at W = 30 min; GRETA-C++ 1.83 / 1.64 / 1.73 MB and
  13.09 / 13.23 / 13.58 MB. These differ from the local G = 25 cells (16.89 and 135.84 MB; GRETA-C++ 2.47
  and 11.05 MB); the cause was not investigated, and the paper reports the range over both machines.
  K6 is judged on the local cells only, so its verdicts are unchanged. Timing quality: the workstation
  was shared (load 3.3–4.7 on 32 threads); its 3-process noise band is 1.000–1.026, and its single-timed
  cells differ from their probe pass by less than 9%.
- Timing quality, reported as is (README Sec. 0): the machine was busier than during E9; other
  applications held memory, and at 04:08 the swap used 8.1 of 9.2 GB. The 3-process noise band has median
  1.010 and maximum 1.349 (E9: maximum 1.146). Two single-timed cells differ much from their probe pass
  (`handoff/e10_probe.tsv`): in Part B at W = 30 min, SUM, GRETA-C++'s timing pass took 1,255 s against a
  probe pass of 699 s (1.80 times; E9 took 589 s / 601 s on the same period), so with the probe pass r
  would be about 62 instead of 111.05; in R(400) at W = 10 min, SlotTree's timing pass took 47.0 s against
  a probe pass of 73.4 s (0.64 times), so with the probe pass r would be 7.8 and one core would keep up
  with 19,600 GPUs. Neither verdict changes, since the lines are 1.5 and 2. At W = 30 min the all-models
  r (43.47 COUNT, 111.05 SUM) is above that of the 10 busiest models in E9 (29.97, 57.09); for COUNT the
  timing and probe passes agree (320 s and 352 s). The state memory per GPU falls as G grows
  (16.9 → 7.2 MB); it is computed from the peak RSS, which can stay below the real footprint under memory
  pressure. Part D, on a machine with 192 GB, measures it without memory pressure (12.8 → 11.9 MB).
