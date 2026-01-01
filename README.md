# Artifact: Trend Aggregation with Adjacent-Event Comparison Predicates

This archive accompanies the anonymous DASFAA 2027 submission. It contains the
C++ engine (our slot tree and our C++ re-implementation of the GRETA / Cogra
per-predecessor evaluation, all in one binary), the correctness gates, the
pre-registered experiment protocols, the raw timing logs behind every number in
the paper, and the data preparation scripts.

## Names in the paper and in the logs

The paper and the experiment logs name the same configurations differently. Every log,
script and report in this archive uses the log names.

| In the paper | In the logs (`--arm`, column `arm`) | What it is |
|---|---|---|
| GRETA-C++ | `OPP` | Our C++ re-implementation of GRETA's runtime (for this query class also Cogra's event-grained aggregator): per-pane vertex trees, one addition per (predecessor, shared window) pair |
| SlotTree | `M` | The slot tree with the cost-based granularity selector (c = 2) |
| per-window trees | `A1` | Ablation: every open window owns its own search tree with plain subtree sums |
| eager deletion | `A2` | Ablation: expired events are deleted one by one at the pane boundary where they die, with slot recomputation along the path |
| always index | `A4` | Ablation: every group always uses the slot tree (no selector) |
| size threshold | `A5` | Ablation: the selector's cost rule is replaced by a group-size rule (switch to the tree at 32 live events, back to the scan below 16) |

Two further names: **v1 / v2** are the two engine versions (below); `hold` / `dev` in the logs
are the test and development parts of a stream.

## Pre-registration

The protocols and pass/fail criteria (`exp/*/README.md`, also repeated verbatim at the
top of each `compare_*.py`, which checks that the two copies are identical) were
committed before the runs and are kept exactly as committed, so they are in Chinese;
only commit identifiers, references to the internal version history and internal
document names were replaced by `<commit>` / `<internal>` for anonymity.
**`PREREGISTRATION.md` is an English translation** of every pass/fail criterion, made
after the runs for this archive, with the outcome of each criterion (held / failed)
and the report that judges it. The Chinese text is the authoritative version.

## Layout

Section, table and figure numbers refer to the submitted paper (Sec. 5 is Experiments).

| Directory | What | Paper |
|---|---|---|
| `exp/m1-trend-index/` | First engine version, GRETA / Cogra re-implementation (`OPP` arm), brute-force oracle `brute_m1.py`, MVP run | Sec. 5.1 Setup (the competitor reproduces GRETA's and Cogra's shapes) |
| `exp/e1-main/` | Final engine v1 (`src/trend.cpp`), gates `tests/run_tests.sh`, main table + ablations + memory on the seven benchmark streams | Sec. 5.1 Measurement and Protocol; Sec. 5.3 Published Benchmarks: High-Rate Streams; Sec. 5.5 Ablations; Sec. 5.6 Sparse Streams; Sec. 5.7 Limitations (memory); Tables 1, 2 and 4 |
| `exp/e2-sweep/` | Window-size sweep and selectivity sweep (uses the E1 binary) | Sec. 5.4 Where the Gain Comes From; Fig. 4 |
| `exp/e4-lowfreq/` | Tuning of the selector constant c on development data; medium/low-frequency test | Sec. 4 The Granularity Selector; Sec. 5.6 Sparse Streams and the Selector |
| `exp/e5-synth/` | Synthetic streams up to 10⁶ events per window: generator `gen_e5.py` (seeded, byte-reproducible), three attribute distributions, k, number of groups, bursts; descriptive (no criterion) | Sec. 5.4, paragraph Synthetic streams; gray in Fig. 4(a) |
| `exp/e6-latency/` | Per-event processing time (quantiles, pauses at pane boundaries) on four benchmark test streams; descriptive | Sec. 5.7 Limitations (compaction stall on the benchmarks) |
| `exp/e7-platform/` | Second platform: the 18 high-rate test settings plus Porto and METR-LA re-run on an Intel i9-14900K, Ubuntu 24.04, g++ 13.3; descriptive | Sec. 5.3 (second platform) |
| `exp/e8-inpane/` | Engine v2 (`src/trend.cpp`): the selector also checks inside a pane (below); re-runs of the `M` and `A2` arms of E1, E2, E5, E6 and E7, merged logs `handoff/*_v2.tsv` | Sec. 5.1 Protocol (the one change after a result); every SlotTree and eager-deletion number of the benchmark streams |
| `exp/e9-aiinfra/` | Two GPU-cluster telemetry streams never used during development: power draw of labelled deep-learning training jobs (MIT Supercloud) and time to first token of an LLM serving platform (Chutes); SlotTree vs. GRETA-C++ with the v2 engine, pre-registered criterion K5 | Sec. 5.2 AI-Infrastructure Telemetry; Tables 1–2; stars in Fig. 4(a); the counts in Fig. 1 |
| `exp/e10-aiinfra-scale/` | Telemetry at cluster scale, v2 engine: replay of G GPUs reporting at once, built from E9's GPU power stream by `prep_e10_replay.py` (pre-registered K6); all 48 models of the same Chutes period (K7); per-event latency on both telemetry streams; both telemetry streams and the six replays re-run on the second platform (Part D, descriptive) | Sec. 5.2 (all models, Cluster replay with Table 3, per-event times, second platform); Sec. 5.7 Limitations (state per GPU, slow events on the telemetry) |
| `exp/e11-synth-1e6/` | Two synthetic settings with 10⁶ events per window (random walk, k = 1 and k = 6) on which GRETA-C++ is run to completion; E5's time limit had skipped GRETA-C++ at this size. Added after the main experiments, descriptive (no criterion) | Sec. 5.4, paragraph Synthetic streams |
| `exp/e12-platform-diag/` | Diagnosis on the second platform: one replay (25 GPUs) re-timed unpinned, pinned to a performance core, pinned to an efficiency core, and with huge pages for malloc. Added after the main experiments, descriptive (reading rules committed before the run) | Sec. 5.1 Measurement (address translation) |
| `paper/figures/table_main.tex` | The full per-setting table (every stream × AGG × W: n, T_GRETA, T_SlotTree, r, memory) behind Table 2; not in the paper's main text | Table 2 |
| `exp/t20-trend-headroom/prep_t20.py` | First-stage preparation of WPI / PAMAP2 / Nasdaq / bus data | data |

Each experiment directory has: `README.md` (protocol, pass/fail criteria where the
experiment has them, deviations, results), `prep_*.py` (data preparation), `run_*.sh`
(timing runs), `handoff/*.tsv` (raw per-run timing logs), `compare_*.py` (turns logs into
`report_*.txt`), and `report_*.txt` (the reports cited by the paper).

**Second platform.** E7, the v2 re-run of its `M` arm (`exp/e8-inpane/run_e7v2.sh`) and Part D of
E10 run on a separate Linux workstation through a remote-run wrapper. The archive keeps the timing
loops (`run_e7.sh`, `run_e7v2.sh`, `run_e10.sh`), the machine record (`relay/*_machine.txt`: CPU,
compiler, load), the gate output (`relay/*_gate.txt`), the timing log (`relay/*_run.txt`), the logs
and the reports. The wrapper scripts, their self-tests, the data-shipping helper and the job-status
files (`ws_e7.sh`, `ws_e8.sh`, `ws_e10.sh`, `tests/e2e_relay.sh`, `pack_e7.py`, `relay/*_env.txt`,
`relay/*_status.txt`, `relay/*_log_tail.txt`) are left out because they record machine-specific
paths and accounts; the experiment READMEs still mention them. Part D of E10 also keeps the
workstation's data-download record and its own copy of the report (`relay/platform_data.txt`,
`relay/platform_report.txt`, identical to `report_e10.txt`); its timings are `handoff/e10_ws_*.tsv`.

**Engine v1 and v2.** `exp/e1-main/src/trend.cpp` is v1: the selector decides scan vs. index
only at pane boundaries. `exp/e8-inpane/src/trend.cpp` is v2, identical except that in scan mode
it also compares the pane's running averages every 1,024 events and switches to the index at once
when the switch rule holds (`--inpane 0` gives back v1; `python3 -I exp/e8-inpane/tests/diff_v1.py`
lists the diff). Only the two arms that use the cost rule, `M` and `A2`, change; `OPP`, `A1`, `A4`,
`A5` are the same code. The paper reports v2: the `M` and `A2` rows were re-timed with v2 and
merged with the unchanged v1 rows of the other arms into `exp/e8-inpane/handoff/e1_times_v2.tsv`,
`e2_times_v2.tsv`, and so on, which have exactly the columns of the v1 logs. The v1 logs and reports
in `exp/e1-main/`, `exp/e2-sweep/`, `exp/e4-lowfreq/`, `exp/e5-synth/`, `exp/e6-latency/` and
`exp/e7-platform/` are kept as committed before the fix.
`exp/e8-inpane/report_e8.txt` re-judges the pre-registered criteria on the v2 logs next to v1;
`report_e1_v2.txt`, `report_e2_v2.txt`, `report_e5_v2.txt`, `report_e6_v2.txt` and `report_e7_v2.txt`
are the reports of the original comparison scripts on the v2 logs. All of them are produced by
`python3 -I exp/e8-inpane/compare_e8.py`, which reads the v1 logs of every experiment above and the v2 logs.

## Requirements

- C++20 compiler. The paper's numbers were measured with Apple clang 21.0.0,
  `-O2 -std=c++20`, single thread, Apple M4, macOS; the second platform (E7, Part D of E10) used
  g++ 13.3.0 with the same flags on an Intel i9-14900K under Ubuntu 24.04. Override the
  compiler with `make CXX=g++` (the Makefiles default to `/usr/bin/clang++`).
- Python 3.8+ standard library only (no packages), except `exp/e9-aiinfra/prep_e9_llm.py` and
  `exp/e10-aiinfra-scale/prep_e10_llm_all.py`, which read Parquet with pyarrow and numpy (versions in
  `exp/e9-aiinfra/requirements.txt`).
- bash. The `run_*.sh` scripts log the machine with macOS tools (`sysctl`, `pmset`,
  `/usr/bin/clang++ --version`); on Linux, put stub `sysctl` and `pmset`
  executables on `PATH` and make sure `/usr/bin/clang++` exists, or simply skip
  `run_*.sh` and call `out/trend` directly as shown in the scripts.
- Scripts call `git rev-parse` to stamp logs; outside a git checkout this prints a
  harmless warning.

## 1. Regenerate every reported number from the shipped logs (no data, about a minute)

```bash
python3 -I exp/m1-trend-index/compare_m1.py hold
python3 -I exp/e1-main/compare_e1.py
python3 -I exp/e2-sweep/compare_e2.py
python3 -I exp/e4-lowfreq/compare_e4.py dev && python3 -I exp/e4-lowfreq/compare_e4.py hold
python3 -I exp/e5-synth/compare_e5.py
python3 -I exp/e6-latency/compare_e6.py
python3 -I exp/e7-platform/compare_e7.py
python3 -I exp/e8-inpane/compare_e8.py     # v2: report_e8.txt and report_e1_v2 ... report_e7_v2.txt
python3 -I exp/e9-aiinfra/compare_e9.py
python3 -I exp/e10-aiinfra-scale/compare_e10.py   # also rewrites handoff/e10_replay.tsv
python3 -I exp/e11-synth-1e6/compare_e11.py
python3 -I exp/e12-platform-diag/compare_e12.py
```

Each command rewrites the `report_*.txt` next to it from `handoff/*.tsv`; the
result is identical to the shipped report (checked when this archive was built).
Two kinds of lines need the prepared data or generator output of Sec. 3 and are printed as
`—` or `None` (or left out) without them: the median events per group and window of the real
streams, and the generator record at the end of the E5 reports (written by `gen_e5.py` into
`exp/e5-synth/logs/gen.txt` when the synthetic streams are generated).
In `exp/e1-main/report_e1.txt`, `K1` is the main-table criterion
(median r = T_OPP / T_M over the 18 high-frequency hold-out rows) and `K3` the
selector-overhead criterion. In `exp/e9-aiinfra/report_e9.txt`, `K5` is judged once per telemetry stream
(every setting with n ≥ 106 has r ≥ 1.5, and at least one has r ≥ 2). In
`exp/e10-aiinfra-scale/report_e10.txt`, `K6` (cluster replay, once per window size) and `K7` (all models)
use the same two lines. `PREREGISTRATION.md` lists every criterion with its verdict.

## 2. Build and run the correctness gates

```bash
make -C exp/e1-main            # -> exp/e1-main/out/trend
python3 -I exp/e1-main/brute_e1.py gate exp/e1-main/out/trend 300
```

The second command is gate (a)+(c) on synthetic streams: every arm configuration
(including the selectivity predicate of E2) against a brute-force enumeration of
all trends, plus per-event scan cost against brute force. It needs no data and
must report 0 mismatches. The full gate, which adds part (b) (on every real
dataset, the first 2,000 events per group, every arm equals `OPP` window by
window), is `bash exp/e1-main/tests/run_tests.sh` after the data of Sec. 3 is
prepared. `python3 -I exp/e1-main/tests/diff_opp.py` shows that the `OPP` code
path is unchanged from the M1 version.

For v2:

```bash
make -C exp/e8-inpane          # -> exp/e8-inpane/out/trend
python3 -I exp/e8-inpane/tests/gate_e8.py exp/e8-inpane/out/trend 300
```

runs the same synthetic gates with extra configurations that make the in-pane switch fire on small
streams (it imports the E1 gate scripts). `bash exp/e8-inpane/tests/run_tests.sh` adds the real-data
parts and checks that v2 with `--inpane 0` makes the same decisions as v1.

For the telemetry streams of E9, `bash exp/e9-aiinfra/run_e9.sh gate` (after their data is prepared, Sec. 3)
compares the v2 engine (`OPP`, `M`, and three more configurations) with the recurrence of
`exp/e1-main/brute_e1.py` on the first 2,000 events of every group, window by window.
For E10, `bash exp/e10-aiinfra-scale/run_e10.sh gate` does the same on the 100-GPU replay stream and on
the all-models stream (`tests/gate_e10.py`, which calls the E9 gate).

## 3. Data

All data is public; nothing is redistributed here. Download into the paths below
(relative to this archive), then run the preparation scripts.

| Dataset | Source | Place at | Prepare |
|---|---|---|---|
| WPI stock trades | `davis.wpi.edu/datasets/Stock_Trace_Data/stock_data/`, the 10 `TimeAndSales_*.txt` files (8.8 MB) | `exp/t20-trend-headroom/data/wpi/` | step A |
| PAMAP2 | UCI ML Repository dataset 231 zip (688 MB), saved as `pamap2.zip` | `exp/t20-trend-headroom/data/pamap2/` | step A |
| Nasdaq minute bars, Dublin bus | Gloria repository (github.com/LeiMa0324/Gloria), `src/main/resources/stock/GloriaVSHamletWorkload/Nasdaq_bursty_20.csv` and `src/main/resources/bus/bus_stream.csv` | `exp/t20-trend-headroom/data/gloria/` | step A |
| Binance aggTrades 2025-10-01 | `data.binance.vision/data/spot/daily/aggTrades/<PAIR>/<PAIR>-aggTrades-2025-10-01.zip` for BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT | `exp/e1-main/data/raw/binance/` | step B |
| Porto taxi | UCI dataset 339 zip; extract `train.csv` from the inner `train.csv.zip` | `exp/e1-main/data/raw/porto/x/train.csv` | step B |
| METR-LA | Zenodo record 5146275, `METR-LA.csv` | `exp/e1-main/data/raw/metrla/` | step B |
| Intel Berkeley Lab | `db.csail.mit.edu/labdata/data.txt.gz` | `exp/e4-lowfreq/data/raw/intel/` | step C |
| MIT Supercloud GPU traces | `mit-supercloud-dataset.s3.us-west-2.amazonaws.com/datacenter-challenge/202201/`: `labelled_jobids.csv` and the 15 files under `gpu/` listed in `exp/e9-aiinfra/handoff/e9_files_gpu.txt` (125 MB) | `exp/e9-aiinfra/data/raw/` | step D |
| Chutes LLM serving trace | Hugging Face dataset `harvardMadsys/chutes_metadata`, `data/trace/train-00000-of-00045.parquet` (2.2 GB) | `exp/e9-aiinfra/data/raw/llm/` | step D |

SHA-256 of the downloaded files are listed in `exp/e1-main/README.md` Sec. 3
(Binance, Porto, METR-LA), `exp/e4-lowfreq/README.md` Sec. 3 (Intel Lab),
`exp/e9-aiinfra/handoff/e9_files_gpu.txt` (GPU traces) and `exp/e9-aiinfra/handoff/e9_slice_llm.txt` (Chutes).
The MIT Supercloud data is licensed CC BY-NC-ND 4.0 and may not be redistributed, so this archive ships only
the file list and the download script; `prep_e9_gpu.py fetch` downloads exactly the listed files over anonymous
HTTPS and checks their sizes, and `build` checks their SHA-256. The Chutes trace is CC BY 4.0.
The synthetic streams of E5 need no download: `run_e5.sh` generates them with `gen_e5.py`. E10 needs no
download either: its replay streams are cut from E9's GPU power stream, and its all-models stream is read
from the same Chutes shard (step E).

```bash
python3 -I exp/t20-trend-headroom/prep_t20.py exp/t20-trend-headroom/data   # step A
python3 -I exp/m1-trend-index/prep_m1.py                                    # step A (dev / hold-out split)
python3 -I exp/e1-main/prep_e1.py all                                       # step B
python3 -I exp/e4-lowfreq/prep_e4.py                                        # step C
python3 -I exp/e2-sweep/prep_e2.py                                          # selectivity thresholds X (about 5 min)
python3 -I exp/e9-aiinfra/prep_e9_gpu.py list && python3 -I exp/e9-aiinfra/prep_e9_gpu.py fetch \
  && python3 -I exp/e9-aiinfra/prep_e9_gpu.py build                         # step D: GPU power stream
python3 -I exp/e9-aiinfra/prep_e9_llm.py build                              # step D: TTFT stream (needs pyarrow, numpy)
python3 -I exp/e10-aiinfra-scale/prep_e10_replay.py segments && python3 -I exp/e10-aiinfra-scale/prep_e10_replay.py build
                                                                            # step E: replay streams R(25), R(100), R(400)
python3 -I exp/e10-aiinfra-scale/prep_e10_llm_all.py build                  # step E: all 48 models (needs pyarrow, numpy)
```

The SHA-256 of every prepared E10 stream is in `exp/e10-aiinfra-scale/handoff/e10_streams.tsv`; the 61
one-hour segments of the replay are listed in `handoff/e10_segments.tsv`.

Every prepared file has one event per line: `group \t time (integer microseconds) \t integer attribute`.

## 4. Re-run the timing experiments

Run after Sec. 2 and 3; each writes `handoff/*.tsv`, then run the matching
`compare_*.py` from Sec. 1. Times are from the original single-threaded runs.

| Experiment | Commands | Time |
|---|---|---|
| M1 (MVP) | `cd exp/m1-trend-index && make && bash tests/run_tests.sh && mkdir -p logs && bash run_m1.sh tau && bash run_m1.sh shape && bash run_m1.sh dev && bash run_m1.sh hold` | ~40 min |
| E4 (selector constant c, development data) | `bash exp/e4-lowfreq/run_e4.sh gate && bash exp/e4-lowfreq/run_e4.sh dev` | ~3 min |
| E1 (main table, ablations, memory; also the E4 hold-out rows) | `bash exp/e1-main/run_e1.sh gate && bash exp/e1-main/run_e1.sh all` | ~7.5 h |
| E2 (window and selectivity sweeps) | `bash exp/e2-sweep/run_e2.sh w && bash exp/e2-sweep/run_e2.sh sel` | ~5 h |
| E5 (synthetic streams; E1 binary) | `bash exp/e5-synth/run_e5.sh all` | ~3.4 h |
| E6 (per-event latency; E1 binary with `--latency`) | `bash exp/e6-latency/run_e6.sh all` | ~5 min |
| E7 (second platform; E1 binary built with g++) | `make -C exp/e1-main CXX=g++`, then for each of `wpi_hold pamap2_hold porto_hold metrla_hold binance_hold`: `bash exp/e7-platform/run_e7.sh <data> exp/e7-platform/handoff/e7_times.tsv` | ~7 h (Binance 6.4 h) |
| E8 (v2 re-runs of `M` / `A2` for E1, E2, E5, E6; then `python3 -I exp/e8-inpane/merge_e8.py`) | `bash exp/e8-inpane/run_e8.sh e1 && bash exp/e8-inpane/run_e8.sh e2` (and `e5`, `e6`, `opp`; see the script header) | ~1.8 h for e1 + e2 |
| E8 on the second platform (v2 `M` arm of E7) | `make -C exp/e8-inpane CXX=g++`, then per dataset `bash exp/e8-inpane/run_e7v2.sh <data> exp/e8-inpane/handoff/e7_m_v2.tsv` | ~55 min |
| E9 (GPU-cluster telemetry, v2 engine) | `bash exp/e9-aiinfra/run_e9.sh gate && bash exp/e9-aiinfra/run_e9.sh all` | ~2.7 h |
| E10 (cluster replay, all models, telemetry latency; v2 engine) | `bash exp/e10-aiinfra-scale/run_e10.sh gate && bash exp/e10-aiinfra-scale/run_e10.sh all` (`all` = memory baselines, Parts A, B, C) | ~3.4 h (cells whose extrapolated memory exceeds 10 GiB are skipped by rule) |

`bash exp/e1-main/run_e1.sh <data>_<split>` re-runs one dataset only (e.g. `wpi_hold`).
`run_row` in `exp/e1-main/run_e1.sh` shows the exact binary invocation used for
every row (`--arm`, `--c`, `--tau`, `--data`, `--W`, `--s`, `--op`, `--agg`).

## License

Released for review purposes; a public repository with an open-source license will follow publication.
