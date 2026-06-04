# Figures & Metrics — Analysis Dimensions for the Thesis

*Reference note locking in the metrics, plot types, and axis choices worth using
when the write-up / figure-design phase starts. Captured 2026-05-31 from the
plotting-tooling discussion. Nothing here is implemented beyond what "Current
tooling" lists; the rest is a menu to decide from, with rationale.*

---

## 0. Current tooling (the starting point)

- **Harness CSV columns** (per `run.py` / `run_hier*.py`): `variant, n, run,
  circuit_size, acir_opcodes, compile_s, witness_s, prove_s, verify_s, proof_bytes,
  peak_mb`.
- **`pipeline/aggregate_hier.py`** — collapses the K+1-rows-per-cell hierarchical
  CSVs into one `{variant}_k{K}` row per cell. `--mode parallel` (max over provers =
  ideal one-node-per-segment wall-clock) vs `--mode total` (sum = total CPU work).
  Variant-agnostic (works for `hier_a/fs/c/cfs`).
- **`pipeline/plot.py`** — mean±std lines, one per variant; `_linear` + `_loglog`.
  Default grid = all **8** metrics. Args: `--metrics`, `--variants` (fnmatch),
  `--min-n`/`--max-n`, `--separate`, `--format png|pdf|svg`, `--legend
  outside|inside|none`, `--no-title`, `--title`, `--dpi`. Stable per-variant palette
  keyed by name; `STYLE_OVERRIDES` / `DISPLAY_NAMES` dicts for curation.
- **`pipeline/make_frontier.py`** — one-shot `aggregate_hier → plot`; `--aggregate`
  raw hier CSVs, `--include` flat/recursion CSVs, `--mode parallel|total|both`,
  forwards all plot flags.

Everything below is **not yet built** unless it says "(current)".

---

## 1. Metrics worth plotting

### 1.1 Raw columns (current)
| Metric | Story it tells |
|---|---|
| `circuit_size` (current) | Headline total proving work; the cost axis. |
| `acir_opcodes` (current) | Backend-independent logical complexity (pre-arithmetization). |
| `prove_s` (current) | Parallelism axis (max = parallel, sum = total via aggregator modes). |
| `witness_s` (current) | Non-proving per-prover overhead; check it stays small even as the committed glue re-folds N nodes. |
| `verify_s` (current) | K+1 bb-verify + cross-check — the **O(K) verifier symptom** of the binding tax. |
| `proof_bytes` (current) | Verifier download; the other O(K) symptom. Sharp committed-* (grows ~K) vs recursion (1 proof). |
| `peak_mb` (current) | Distributed-hardware benefit; drops ~1/K. |
| `compile_s` (current) | Minor, one-time. |

### 1.2 Derived metrics (compute in a small script or annotate in text — no new harness columns)
| Derived metric | Formula | Why it matters |
|---|---|---|
| **Arithmetization expansion** | `circuit_size / acir_opcodes` | Isolates "gate-heavy logic" from "more logic". committed-* show a higher ratio (Poseidon folds lower expensively) → the commitment cost made legible and backend-independent. |
| **Total-work conservation** | `K·sub + glue` vs flat | Turns the dualism result into a metric: decomposition redistributes, not reduces. (Aggregator already sums it; just co-plot flat.) |
| **Parallel speedup** | `flat.prove_s / hier.prove_s(parallel)` | Parallelism claim as a curve vs K (ideal = K). |
| **Memory reduction** | `flat.peak_mb / hier.peak_mb` | Distributed-hardware claim as a curve vs K (ideal = K). |
| **Verifier amortization** | `proof_bytes`, `verify_s` vs K | The O(K) binding-tax symptom; committed-* (∝K) vs recursion (flat) at equal privacy. |
| **Privacy class** | ordinal: disclosed / computational / structural | Not a harness output — a per-variant annotation. It is what makes the frontier a *frontier* and not a cost plot. |

---

## 2. Plot types (beyond line-vs-N)

Line-vs-N is right for **scaling**. The **frontier story wants other geometry:**

- **Pareto / scatter at fixed N** (e.g. N=480): x = total gates (or verifier cost),
  y = parallel wall-clock (or per-prover memory), **marker/colour = privacy class**,
  one point per variant. *This is the frontier* — shows domination and the Pareto
  front directly. The "pick-two triangle" reads naturally here, not as lines.
  **(Proposed headline figure.)**
- **Grouped bar charts** at fixed N for `proof_bytes` / `verify_s` / `peak_mb` across
  variants × K — cleaner than lines when N is held and K/variant is the comparison.
- **Stacked bars** for `circuit_size` = sub-share vs glue-share (and, for committed-*,
  the commitment-fold share) — visualizes *where* the gates go and the binding tax.
- **Heatmap** over the (N, K) grid, one metric per variant — good for appendix sweeps.
- **Slopegraph / ladder diagram** for the privacy progression
  (B → A → A++ → committed → recursion) with cost annotations — schematic, the
  chapter's spine, not data.
- **Ratio-to-baseline lines** (everything ÷ flat) — flattens the y-range so relative
  overheads/speedups are readable where absolute curves overlap.

Suggested headline set: **one Pareto scatter at N=480** + the existing scaling lines
as support + a stacked-bar gate-decomposition.

---

## 3. Axis combinations (X ≠ N)

| X axis | Held fixed | What it surfaces |
|---|---|---|
| **K** | N | The parallelism/memory/verifier story — per-prover gates & `peak_mb` fall ~1/K while `proof_bytes`/`verify_s` rise ~K. N-on-X hides this; K-on-X is where A/A++/committed-* differ. |
| **total gates / Y = wall-clock or memory** | N | The Pareto/frontier view (see §2). |
| **privacy (ordinal) / Y = cost** | N | The literal "privacy ladder vs cost" plot; the equal-privacy slice becomes a vertical line. |
| **M = N/K** (segment size) | — | Segment-size-is-the-real-knob view; supports the recursion inner-choice argument (A++ O(1) surface vs A O(M)). |
| **N** (current) | K, variant | Scaling / complexity exponents (log-log slopes). |

---

## 4. Proposed tooling upgrades (decide at thesis time)

- **`--x {n,k,m}` in `plot.py`** — draw K-on-X and M-on-X views from the same
  aggregated CSVs without new data. Low-risk, high-value for §3.
- **`frontier_scatter.py`** (or a `--mode scatter` in `plot.py`) — Pareto scatter at a
  fixed N, privacy encoded as marker style. *Open question: standalone script vs a
  plot.py mode.*
- **Stacked-bar gate-decomposition** helper (sub vs glue vs commitment-fold shares).
- **Derived-metric pass** — a tiny script emitting the §1.2 columns
  (expansion ratio, speedup, memory-reduction, ratio-to-baseline) into a CSV that the
  existing plotters consume.

---

## 5. Open decisions to settle before drawing final figures

1. **Headline frontier figure**: Pareto scatter at N=480 (recommended) vs the
   multi-panel triangle vs both.
2. **Privacy encoding** in figures: ordinal marker style vs annotated bits vs both.
3. **`--x` axis additions**: implement `k`/`m` or keep N-only + bespoke scripts.
4. **Scatter as standalone script vs plot.py mode.**
5. **Curated palette + display names**: fill `STYLE_OVERRIDES` / `DISPLAY_NAMES` once
   the final variant naming is fixed (pin the flagship families so colours never
   clash; relabel `hier_cfs_k4` → "committed-A++ (K=4)" etc.).
6. **Which metrics go in the body vs appendix** (8-panel grid is analysis-grade;
   thesis body likely wants 3–4 curated panels + the scatter).

---

*Related: `FRONTIER_REFRAME.md` (frontier framing, privacy ladder), `Thesis_Outline.md`
Ch 10 §10.5a (frontier figure plan), `HOWTO.md` (current plotting commands),
`HIERARCHICAL_EXPLAINED.md` §9b/§14.5 (variant privacy classes).*
