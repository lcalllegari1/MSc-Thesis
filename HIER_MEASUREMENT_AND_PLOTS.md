# Hierarchical Benchmark — Measurement Semantics & Plot Taxonomy

*Consolidated reference for (1) **how** the hierarchical metrics are measured and
what each number means depending on the harness/aggregator flags, (2) what the
**concurrent** vs **isolated** runs each legitimately state, and (3) a **taxonomy
of plot types** for comparing flat vs hierarchical across every dimension.
Captured 2026-05-31. Companion to `FIGURES_AND_METRICS.md` (analysis-design menu)
and `ISOLATION_BENCHMARK.md` (the K× measurement protocol).*

---

## 1. The measurement pipeline (two stages)

Hierarchical metrics are produced in two stages; you must know both to interpret a
number.

### Stage 1 — raw harness (`pipeline/run_hier*.py`): per-segment rows

For each `(N, K, run)` cell the harness emits **K+1 rows** — one per circuit:
`sub_0 … sub_{K-1}` (the K segment proofs) plus `glue` (the binding proof). Schema:
`run_hier.py:76-91`. **Every row holds the metrics for that one circuit only** —
these are *per-segment* (and per-glue) measurements, not yet combined.

The K+1 proofs are produced by K+1 worker processes (`parallel_prove_all`,
`run_hier.py:269`), each running `nargo execute && bb prove` in its own shadow
directory so they don't race on output files.

### Stage 2 — aggregator (`pipeline/aggregate_hier.py`): one cumulative row

This collapses the K+1 per-segment rows into **one `{variant}_k{K}` row per cell**,
matching the flat `run.py` schema so it plots side-by-side with flat. The collapse
rule **differs per metric** (`aggregate_hier.py:101-170`) — that rule is the whole
story.

### The two independent knobs

| Knob | Stage | Controls | Effect |
|---|---|---|---|
| `--isolated` | 1 (harness) | **how time is measured** | provers run **sequentially / solo** (each alone) vs the default **concurrent** (K+1 contending on one box). Tags the variant `<base>_iso`. |
| `--mode parallel\|total` | 2 (aggregator) | **how rows collapse** | time metrics aggregate by **max** (parallel wall-clock) vs **sum** (total CPU work). |

**Critical subtlety** (`ISOLATION_BENCHMARK.md` §1): under the **default concurrent**
harness, the per-segment `prove_s`/`witness_s` are measured *under K+1-way CPU
contention* — inflated. So `--mode parallel` on a *concurrent* run is a
**projection** of the K× speedup, not a measurement. `--isolated` removes the
confound: each prover gets the whole machine, so its solo `prove_s` is the genuine
per-node time in the distributed model.

---

## 2. Per-metric semantics (per-segment value → cumulative value)

| Metric | Kind | Per-segment (raw row) | Cumulative (aggregated) | Knob? |
|---|---|---|---|---|
| `circuit_size` | structural | gate count of one circuit (subs identical) | **K·sub + glue** | none |
| `acir_opcodes` | structural | opcode count of one circuit | **K·sub + glue** | none |
| `compile_s` | structural | compile time of sub / glue binary | **sub + glue** (K subs reuse one binary) | none |
| `witness_s` | runtime | that prover's `nargo execute` time (contended / solo) | **max** (`parallel`) or **sum** (`total`) | both |
| `prove_s` | runtime | that prover's `bb prove` time (contended / solo) | **max** = parallel wall-clock; **sum** = total CPU work | both |
| `verify_s` | runtime | serial `bb verify` of that one proof (never contended) | **sum over K+1 + `verify_hier_s`** cross-check | `mode` n/a |
| `proof_bytes` | size | size of that one proof file | **sum** of all K+1 proofs (verifier download) | none |
| `peak_mb` | runtime | peak RSS of that one `bb prove` (**per-process → NOT contention-inflated**) | **max** over K+1 (largest single-node footprint) | none |

Aggregation code: `aggregate_hier.py:135-148`. Notes per metric:

- **`circuit_size` / `acir_opcodes` = K·sub + glue** is the *total proving work*; it
  proves the **dualism / total-work-conservation** result (decomposition
  redistributes gates, doesn't reduce them). Co-plot against flat to show
  `K·sub + glue ≳ flat` = the binding tax in gates.
- **`prove_s`** is the headline parallelism axis. The meaningful K× number is
  `--isolated` harness + `--mode parallel`. See §3.
- **`verify_s`** and **`proof_bytes`** grow ~O(K) — the verifier-side **binding tax**
  (committed-* ∝ K; recursion stays flat at a single proof).
- **`peak_mb`** falls ~1/K vs flat and is a *genuine measurement even on the
  concurrent harness* (per-process), so it needs no `--isolated`.

### 2.1 Recursion — a third measurement profile

The recursion micro-experiment (`tests/recursion_micro/`, aggregated by
`pipeline/aggregate_recursion.py`) emits the same `run.py` schema, so it co-plots
with flat and hier — but its aggregation rules differ, encoding a different corner:

| Metric | Recursion rule | Consequence |
|---|---|---|
| `circuit_size` / `acir_opcodes` | **sum(inner) + outer** | the **outer dominates** (~1.47M–3M+ gates) — the in-circuit-verification premium |
| `prove_s` / `witness_s` | innerstep (max/sum) **+ outer** | the outer is a **serial tail AFTER** the inners (it consumes their proofs) — *not* concurrent like the hier glue, so **no clean K×** |
| `verify_s` | **outer only** | the verifier checks **one** proof → **O(1), constant in K** (like flat) |
| `proof_bytes` | **outer only** | **one** proof delivered → **constant in K** |
| `peak_mb` | max(K inner peaks, outer) | outer dominates 4–14× → high single-prover memory |

So the three approaches occupy three distinct corners:

| | per-node prover cost | parallelism | verifier cost (bytes / `verify_s`) | memory |
|---|---|---|---|---|
| **flat** | high (monolith) | none | O(1), one proof | full |
| **hierarchical** | low (~1/K) | ~K× | **O(K)** — binding tax | ~1/K |
| **recursion** | **very high** (outer) | leaf-only + serial outer tail | **O(1)** — buys it back | high (outer) |

**Comparability rule:** compare at the **equal-privacy slice** — `recursion_k{K}` vs
`hier_fs_k{K}` (A++) vs `flat_merkle_presence` — because recursion's inner *is* the
A++ segment. Only **exp 2** (`recursion_k{K}`) is a complete TSP statement; **exp 1**
(`recursion_1seg`) is a single-segment diagnostic — keep it off the frontier.

---

## 3. Concurrent vs isolated — what each run legitimately states

These are **two distinct deployment questions**, not two estimates of one number.

| Run | Deployment modelled | Directly comparable to |
|---|---|---|
| `--isolated` + `--mode parallel` (max) | **K+1 separate nodes** (distributed) | an idealized cluster; needs the "imagine K machines" reframe; *compute-only upper bound* |
| **concurrent** (default) + `--mode parallel` (max) | **one machine, all K+1 jobs at once** | **flat and the recursion experiment directly** — they are *all* single-machine |

### 3.1 Isolated = the "real parallel" / distributed claim

Run the K+1 provers **sequentially** so each `prove_s` is a **solo** time, then:

- `--mode parallel` (max over the K+1 solo rows = `max(T_sub, T_glue)`) → **deployment
  model (a)**: glue proves concurrently on a (K+1)-th node. Because `T_glue < T_sub`
  at thesis sizes, `max ≈ T_sub`, so the **per-node figure is effectively the
  sub-circuit time** — but the principled quantity is `max(sub, glue)`, not "the sub
  row" literally.
- `--mode total` (sum of solo times) → **model (b)**: K nodes, glue runs after a node
  frees → conservative bound.

Both are now **measured**, not projected. Speedup = `flat.prove_s / hier(parallel)`,
ideal = K. Label it **compute-only** (ignores network/coordination) ⇒ an upper bound.

### 3.2 Concurrent = the honest single-machine baseline (also meaningful)

Don't call it "parallel speedup" — call it what it measures: the **single-machine
wall-clock of the decomposed job**. It states four useful things:

1. **It's apples-to-apples with the rest of the thesis.** Flat and the recursion
   micro-experiment are single-machine; the concurrent hierarchical run is on that
   *same box under the same conditions*, so `max(prove_s)` (≈ the harness's recorded
   `_wall_total_s`, `run_hier.py:313`) compares to `flat.prove_s` with **no
   projection and no reframe**.
2. **It yields the negative result that motivates the distributed model.** `bb prove`
   already saturates all cores with one prover, so K+1 concurrent provers just
   time-slice the same cores; total work `K·sub + glue ≳ flat` ⇒ **no wall-clock
   speedup on one box** (a small penalty = the binding tax). The K× win only appears
   when you provision K real nodes. The concurrent-vs-isolated pair *is* the
   "hardware-conditional win" argument, made visual.
3. **The concurrent/isolated ratio quantifies the oversubscription penalty** —
   measured evidence that co-locating provers doesn't work and you need separate
   nodes.
4. **Memory still works under concurrency** (`peak_mb` is per-process):
   `max(peak_mb)` = per-node footprint (distributed claim, ~1/K); `sum(peak_mb)` =
   the RAM to co-locate them on one box (a single-machine cost vs `flat.peak_mb`).

**Caveat:** `--mode total` (sum) on a **concurrent** run does *not* give clean total
CPU work — summing contention-inflated times overcounts. For total CPU work use
**`--isolated` + `--mode total`**. The concurrent run's trustworthy time output is
**`max`** (single-machine wall-clock), not the sum.

### 3.3 Recommendation

Report **both**, explicitly labelled, in the same figure (the `<base>_iso` tag keeps
them distinct):

- **concurrent, `max`** → "single-machine wall-clock" — co-plot with flat + recursion;
  delivers the dualism cost and the honest "no speedup on one box" finding.
- **isolated, `max`** → "distributed wall-clock (one node/segment)" — the K× speedup
  curve vs the ideal-K reference; compute-only upper bound.

---

## 4. Which metrics carry the flat-vs-hierarchical comparison

The flat harness (`run.py`) emits the same schema for a single monolithic N-node
proof, so after aggregation every metric is directly comparable.

**Primary (the frontier trade-off):**

1. **`prove_s` (parallel)** — the parallelism win. Derived **speedup =
   `flat.prove_s / hier.prove_s`**, ideal K. Trustworthy only from an `--isolated`
   run; flag the concurrent number as a single-machine baseline, not a speedup.
2. **`peak_mb`** — the distributed-hardware win. Derived **memory-reduction =
   `flat.peak_mb / hier.peak_mb`**, ideal K. Valid even from the concurrent harness.
3. **`circuit_size` = K·sub + glue vs flat** — the dualism cost (total work
   conserved/grown). Stack into sub-share vs glue-share to show *where* the gates go.
4. **`verify_s`** and **`proof_bytes`** — the O(K) binding tax on the verifier; where
   hierarchical *loses* to flat and recursion. Essential for an honest Pareto.

**Secondary / supporting:**

5. **`acir_opcodes`** + derived **arithmetization-expansion** (`circuit_size /
   acir_opcodes`) — isolates the commitment cost of committed-* backend-independently.
6. **`witness_s`** — sanity check that non-proving overhead stays small.
7. **`compile_s`** — minor, one-time.

**Non-harness annotation that makes it a *frontier*, not a cost plot:**

8. **Privacy class** (ordinal: disclosed / computational / structural) — a per-variant
   label. Without it the story is just "flat is cheaper"; with it the point is
   hierarchical buys parallelism + memory at a privacy/verifier cost flat can't match
   at equal privacy.

---

## 5. Plot taxonomy

Organized by **the question each plot answers** — the same data wants different
geometry depending on which dimension you isolate. Dimensions in play: **N** (size),
**K** (decomposition), **M = N/K** (segment size), **variant family**, **privacy
class** (ordinal), **deployment** (concurrent vs isolated), and the **8 metrics +
derived**.

### A. Scaling family — X = N (how cost grows)

- **A1. Line, metric vs N, one line/variant — log-log.** The canonical complexity
  plot: **slope = empirical complexity exponent** (e.g. `prove_s ~ N^a`). Reveals
  whether hierarchical changes the *exponent* or just the *constant* vs flat. Log-log
  because everything is power-law.
- **A2. Same, linear.** Companion to A1: shows *absolute* magnitudes and the crossover
  N where variants overtake — which log-log flattens. Body usually wants linear,
  appendix gets log-log.
- **A3. Ratio-to-baseline (metric ÷ flat) vs N.** Flattens the y-range so small and
  large overheads are both readable when absolute curves overlap. Shows whether the
  overhead/speedup is asymptotically constant or growing.

### B. Decomposition family — X = K, N fixed (the parallelism / binding-tax story)

*The most important family, and the one that N-on-X plots hide — at fixed N, sweeping
K is where A / A++ / committed-* diverge.*

- **B1. Line, per-prover metric vs K.** Plot the falling curves (`circuit_size/K`,
  `peak_mb`, `prove_s` ~1/K) **together with** the rising ones (`proof_bytes`,
  `verify_s` ~K). One figure = the binding-tax trade-off at a glance.
- **B2. Speedup vs K with ideal-K reference.** Y = `flat.prove_s / hier.prove_s`,
  diagonal `y=K` = ideal. **Two series: isolated (real distributed speedup) and
  concurrent (≈1×, no speedup).** Gap between them = the hardware-conditional-win
  argument; gap to the diagonal = sub-linear-prover + glue overhead.
- **B3. Memory-reduction vs K with ideal-K reference.** Y = `flat.peak_mb /
  hier.peak_mb`. Honest even from the concurrent run (per-process memory) → the
  cleanest *measured* distributed-hardware curve.

### C. Segment-size family — X = M = N/K (the real knob)

- **C1. Per-prover metric vs M, collapsing all (N,K) with equal M.** Reframes the knob
  as "how big is each segment" — what the prover node actually experiences. Supports
  the recursion-inner-circuit argument: A++ has an **O(1)** public surface per segment
  vs A's **O(M)**, so their curves vs M have different slopes. Equal-M points from
  different (N,K) landing together ⇒ per-prover cost is governed by M alone.

### D. Frontier family — axes are cost-vs-cost, N held (the headline)

- **D1. Pareto scatter at fixed N** (e.g. N=480). X = total gates (or verifier cost),
  Y = parallel wall-clock (or per-prover memory), **marker/color = privacy class**,
  one point/variant. *This is the frontier figure* — shows domination + the Pareto
  front; the pick-two triangle reads naturally here as a scatter.
- **D2. Bubble chart (4 dims).** Same scatter + a third metric as **marker size**
  (e.g. X = `proof_bytes`, Y = prover wall-clock, size = `peak_mb`, color = privacy).
  One-panel summary; reserve for the few flagship variants to avoid clutter.

### E. Composition family — stacked, where the cost goes

- **E1. Stacked bar of `circuit_size` = sub-share vs glue-share** (vs commitment-fold
  share for committed-*), per variant and per K. **Localizes the binding tax**: the
  glue/commitment fraction grows with K — the gate-level mechanism behind the
  verifier-cost rise. More legible than subtracting two line curves.
- **E2. Stacked bar of total CPU work** (`--mode total`, isolated), `prove_s` summed.
  Shows redistribution-not-reduction (dualism) as composition. Use total mode (sum),
  not parallel.

### F. Categorical family — X = variant (or variant × K), N fixed

- **F1. Grouped bar charts at fixed N for `proof_bytes` / `verify_s` / `peak_mb`.**
  When N is held and the comparison is across variants/K, bars beat lines: discrete
  categories, no spurious interpolation, exact magnitudes. Right tool for the
  verifier-side "committed-* pay ∝K, recursion pays flat" message.

### G. Grid / dense-sweep family (appendix)

- **G1. Heatmap over the (N, K) grid**, one metric per variant, color = value. Spots
  anomalies and shows the full sweep; appendix-grade.
- **G2. Small-multiples / faceted 8-metric panel** (current `plot.py` default grid).
  The analysis dashboard — all metrics, all variants, one screen. Working analysis +
  appendix; body pulls 3–4 curated panels from it.

### H. Schematic / conceptual family (the chapter spine, not data)

- **H1. Slopegraph / privacy ladder.** The ordinal progression flat-B → A → A++ →
  committed → recursion on one axis with cost annotations per rung. Communicates *why*
  the frontier is a frontier.
- **H2. Pick-two triangle / radar per variant.** Three axes — privacy, parallelism,
  verifier-economy — each variant a filled polygon. Instant intuition for "you get two
  corners, not three." Small radars side by side for the flagship variants.

### I. Distribution / robustness family

- **I1. Mean ± std bands** on the line plots (`plot.py` already does this). Essential
  whenever a speedup is claimed — shows the runs aren't noise.
- **I2. Box / violin per variant at fixed N for `prove_s`.** When reporting a *median*
  isolated speedup, shows the run-to-run spread behind it; defends against "you
  cherry-picked a fast run" (prove time is scheduler-sensitive).

### J. Three-way family — flat vs hierarchical vs recursive

*Most A–I plots accept recursion as just another variant series (same schema after
`aggregate_recursion.py`), but these framings exist **specifically** to surface the
three-corner trade-off. Plot the equal-privacy slice: `flat_merkle_presence`,
`hier_fs_k{K}`, `recursion_k{K}`.*

- **J1. Verifier-cost vs K, all three overlaid** (`proof_bytes` and `verify_s`). Flat
  = a single point; hierarchical = a line **rising ∝K** (binding tax); recursion = a
  **flat horizontal line** (O(1)). The single plot that justifies recursion's
  existence — it spends prover gates to flatten exactly the curve hierarchical
  inflates. (Specialization of B1/F1; the three-way overlay *is* the point.)
- **J2. Three-corner Pareto scatter** at fixed N (specialization of D1). X = verifier
  cost (`proof_bytes` or `verify_s`), Y = total prover gates (`circuit_size`) or
  per-node `peak_mb`, **marker = approach family** (flat / hier / recursion),
  **color = privacy class**. The three families form three **non-dominated regions** →
  a genuine 3-way Pareto front. *The headline three-way figure.*
- **J3. Frontier-walk / trade path.** Connect flat → hier(K) → recursion in
  (verifier-cost, prover-cost) space with annotated arrows: *"decompose → pay verifier
  O(K)"* then *"recurse → buy back the verifier, pay prover gates."* Instantiates the
  pick-two triangle with **real data** — the chapter's spine made quantitative.
- **J4. Speedup vs K with recursion's serial tail** (overlay on B2). Recursion speedup
  = `flat.prove_s / (max(inner) + outer)`; the outer is a **serial, K-growing tail**,
  so recursion's curve **caps and degrades** while hierarchical climbs toward ideal-K.
  Visual honesty: recursion trades parallelism for verifier economy.
- **J5. Stacked gate-decomposition across all three** (extend E1). Flat = one
  monolithic bar; hier = K·sub + small glue; recursion = K·inner + **dominant outer**.
  Side by side, the outer's dominance vs the glue's small share is the visual punchline
  of *where the perfect-hiding cost lives*.
- **J6. Grouped bars at fixed N, three families × verifier metric** (extend F1). The
  cleanest categorical three-way view of `proof_bytes` / `verify_s` / `peak_mb`.

### Suggested body figure set

**J2** (three-corner Pareto, headline) + **J1** (verifier-cost vs K) + **B2 / J4**
(speedup vs K with recursion's tail + memory) + **A1** (log-log scaling) + **J5 / E1**
(gate-decomposition stacked, all three) + **H1 / H2** (privacy ladder + pick-two
triangle). Everything else → appendix / working analysis.

---

## 6. Tooling map

| Need | Tool |
|---|---|
| produce raw K+1-row hier CSV (contended) | `pipeline/run_hier*.py` |
| produce raw K+1-row hier CSV (solo per-node) | `pipeline/run_hier*.py --isolated` |
| collapse to one row/cell, parallel wall-clock | `aggregate_hier.py --mode parallel` |
| collapse to one row/cell, total CPU work | `aggregate_hier.py --mode total` |
| produce raw recursion CSV (inner + outer rows) | `tests/recursion_micro/run_recursion.py` |
| collapse recursion to one row/cell (outer-only verifier metrics) | `pipeline/aggregate_recursion.py --mode parallel\|total` |
| one-shot aggregate + plot frontier (flat + hier + recursion) | `pipeline/make_frontier.py` |
| line plots (A1–A3, B1, I1), grid (G2) | `pipeline/plot.py` (`--metrics`, `--variants`, `--min-n/--max-n`, `--separate`) |
| Pareto scatter (D1/D2), bars (F1), stacked (E1), heatmap (G1), radar (H2) | **not yet built** — see `FIGURES_AND_METRICS.md` §4 proposed upgrades |

---

## 7. The proper comparison outline — where to start, in what order, why

A comparison run in the wrong order produces plots that can't be trusted or read.
The order below is a **funnel**: each phase is a precondition for the next, moving
from *deterministic → noisy*, *like-with-like → across-class*, *single-axis →
synthesis*, *honest baseline → idealized claim*, and always *wins paired with
costs*. Do not jump to the frontier scatter (the payoff) before the axes that feed
it are each understood in isolation.

### Ordering principles (why this order)

1. **Validity before value.** A speedup measured on an unverified or inconsistent
   proof is noise. Gate the whole comparison on correctness first.
2. **Like-with-like before across-class.** Compare at a fixed **privacy class** first
   (the equal-privacy slice); only then bring in other rungs. Mixing privacy classes
   silently compares apples to oranges.
3. **Deterministic before noisy.** Gate counts are exact and reproducible and they
   *explain* the timing (prove_s and peak_mb track gates). Settle the structural story
   before touching scheduler-sensitive wall-clock.
4. **Honest baseline before idealized claim.** The single-machine (concurrent) reality
   needs no reframe and anchors the reader; the distributed (isolated) K× is then
   clearly the "if you provision K nodes" upper bound, not an oversold headline.
5. **Wins paired with costs.** Never present parallelism/memory without the verifier
   tax in the same breath — otherwise it reads as a free lunch and collapses under the
   first objection.

### Cross-approach order (which pairs first)

- **First pair — `flat_merkle_presence` vs `hier_fs_k{K}` (A++)**, equal privacy. The
  cleanest 1-vs-1: it isolates **decomposition alone**, nothing else changing.
- **Then add `recursion_k{K}`** (exp 2) — introduces the buy-back corner and turns the
  two-way trade into the three-corner frontier.
- **Then the ladder rungs** — Variant A (`hier_a`), committed-A/A++ (`hier_c/cfs`) as
  ablation/gradient points showing the privacy ladder; secondary, not the spine.
- **Full-disclosure flat (`flat_full_*`)** is the cheap, no-privacy *floor*; the
  within-flat encoding study (presence / sort / pairwise / invperm) is a sub-study, not
  the main frontier.

### The phases

**Phase 0 — Lock the frame (no plots yet).**
Pin the **equal-privacy slice**, the **anchor N** (largest reliably measured, e.g.
480) and the **K set** (2, 4, 8). Confirm **correctness gating**: `xchecks_ok == 1`,
all proves OK, `bb verify` passes for every cell. Inventory which runs you have —
**concurrent** (contended, already in `results/*_par`) vs **isolated** (must be run on
an idle box). *Why first:* §0 decisions silently determine whether every later number
is comparable.

**Phase 1 — Structural baseline: `circuit_size`, `acir_opcodes` (deterministic).**
At the anchor N, compare **K·sub + glue** (hier) vs **flat** vs **sum(inner) + outer**
(recursion). Establish the **dualism / total-work-conservation** result and the
**binding tax in gates** here, where the numbers are exact. Add the
**arithmetization-expansion** ratio. *How:* **A1** (log-log scaling → exponents),
**E1 / J5** (stacked: where the gates go). *Expected:* hier total ≳ flat
(redistribution, not reduction); recursion's outer dominates (perfect-hiding premium).
This frames everything downstream.

**Phase 2 — Per-node structural reduction: `circuit_size / K`, the M knob.**
Show the **per-prover** gate count falls **~1/K** — the structural fact that *enables*
the parallelism and memory wins. *Why here:* still noiseless, and it's the causal
bridge from "total work grew" (Phase 1) to "yet each node does less," stated before any
clock is read. *How:* **B1** (per-prover metric vs K), **C1** (vs M = N/K).

**Phase 3 — Single-machine runtime: `prove_s` (concurrent max), `peak_mb`, `witness_s`.**
Compare flat vs **hier (concurrent `max`)** vs recursion on the **same one box**.
*Why before isolated:* no reframe needed, directly comparable to flat and recursion
(all single-machine), and it delivers the honest **"no wall-clock speedup on one box"**
result plus the **`peak_mb` ~1/K** drop (real even under contention). *How:* **A1/A2**
(scaling), **B3** (memory-reduction vs K, valid concurrently). *Expected:* concurrent
wall-clock ≈ flat (small binding-tax penalty); memory ~1/K.

**Phase 4 — Distributed runtime: the K× speedup (`--isolated`).**
On an **idle** machine, run `--isolated`, aggregate `--mode parallel` (model a) and
`--mode total` (model b). Plot **speedup vs K** against the ideal-K diagonal.
*Why after Phase 3:* the reader already knows the single-machine truth, so the K× reads
as the **distributed upper bound** (compute-only), not an overclaim. *How:* **B2**
(speedup vs K + ideal line), **J4** (overlay recursion's serial outer tail). *Expected:*
hier approaches ~K with a sub-linear gap; recursion **caps/degrades** (serial outer).

**Phase 5 — Verifier-side cost (the tax): `verify_s`, `proof_bytes`.**
Now bring in what the Phase 3–4 wins are *paid with*: flat **O(1)** vs hier **O(K)** vs
recursion **O(1)**. *Why paired here, not earlier:* the tax is the counterweight that
makes it a trade; recursion's reason-for-being (buying the tax back) only lands once
the hier O(K) growth is on screen. *How:* **J1** (verifier-cost vs K overlay), **J6**
(grouped bars at fixed N).

**Phase 6 — Synthesize: the frontier.**
With every axis understood, draw the **three-corner Pareto** and the **frontier-walk**.
*Why last:* the scatter compresses all dimensions and only reads correctly after each
has been seen alone — this is the payoff figure, not the opening one. *How:* **J2 / D1**
(Pareto, headline), **J3** (frontier-walk with "decompose → recurse" arrows),
**H1 / H2** (privacy ladder + pick-two triangle).

**Phase 7 — Robustness & honesty pass.**
Defend the claims already made: **I1** (mean ± std bands), **I2** (box/violin behind any
median speedup), and the stated threats — compute-only upper bound, one core-count
class, contention confound, exp 1 excluded as a non-statement. *Why last:* it hardens
conclusions that now exist; doing it earlier defends nothing.

### One-line summary of the path

> Lock the frame → prove it in gates (deterministic) → show per-node shrinks →
> measure the honest one-box reality → then the distributed K× → pay it back with the
> verifier tax → synthesize the frontier → harden with robustness.

---

*Related: `FIGURES_AND_METRICS.md` (analysis-design menu, derived metrics),
`ISOLATION_BENCHMARK.md` (K× measurement protocol, deployment models a/b),
`FRONTIER_REFRAME.md` (pick-two triangle, privacy ladder), `HOWTO.md` (commands),
`HIERARCHICAL_EXPLAINED.md` §9b/§14 (variant privacy classes).*
