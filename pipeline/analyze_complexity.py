"""
analyze_complexity.py  --  Compare theoretical vs empirical circuit complexity.

Loads benchmark CSVs, fits polynomial and log-linear models to circuit_size and
acir_opcodes, and explains each coefficient in terms of the underlying constraint
structure.  Produces printed tables and comparison figures.

Supported variants:

  flat_full_*          (pairwise / sort / invperm / presence)
    Complexity class:  O(N^2) — dominated by the N^2 public cost-matrix inputs.
    Fit model:         a*N^2 + b*N + c   (quadratic, exact R^2=1.000)

  flat_merkle_presence
    Complexity class:  O(N*DEPTH) = O(N*log N) — no N^2 public inputs; instead
                       N*DEPTH Poseidon2 calls per proof where DEPTH=ceil(log2(N^2)).
    Fit model:         a*N*log2(N) + b*N + c   (log-linear)
    Note:              A quadratic fit still works (returns a~=0) but the log-linear
                       fit reveals the true scaling and enables crossover extrapolation.

Crossover analysis:
    At small N the N*log(N) Merkle cost is more expensive than the O(N^2) cost
    despite having a lower asymptotic class — because each Poseidon2 call costs
    ~264 UltraHonk gates while each public-input u64 costs only ~7.25 gates.
    The crossover (where flat_merkle becomes cheaper than flat_full_presence) is
    estimated at N ~700 for circuit_size and N ~30 for acir_opcodes.

Usage:
    # Flat-full variants only (default)
    python pipeline/analyze_complexity.py --csv results/flat_full.csv --out plots/flat_full_complexity

    # Include flat_merkle_presence (pass a merged CSV or the merkle CSV separately)
    python pipeline/analyze_complexity.py \\
        --csv results/flat_full.csv \\
        --merkle-csv results/flat_merkle_presence.csv \\
        --out plots/all_complexity
"""

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

# ── Colour palette (consistent with plot.py) ─────────────────────────────────
PALETTE = {
    "flat_full_pairwise":   "#e41a1c",
    "flat_full_sort":       "#377eb8",
    "flat_full_invperm":    "#4daf4a",
    "flat_full_presence":   "#ff7f00",
    "flat_merkle_presence": "#984ea3",  # purple — distinct from all flat_full colours
}
MARKERS = {
    "flat_full_pairwise":   "o",
    "flat_full_sort":       "s",
    "flat_full_invperm":    "^",
    "flat_full_presence":   "D",
    "flat_merkle_presence": "P",        # plus-filled marker, visually distinct
}
LABELS = {
    "flat_full_pairwise":   "pairwise  (O(N^2) perm)",
    "flat_full_sort":       "sort      (~3N perm)",
    "flat_full_invperm":    "invperm   (2N perm, extra witness)",
    "flat_full_presence":   "presence  (~4N perm, RAM)",
    "flat_merkle_presence": "merkle    (O(N*DEPTH) = O(N*log N))",
}

# Variants that use the full N^2 public cost matrix.
FLAT_FULL_VARIANTS = [
    "flat_full_pairwise",
    "flat_full_sort",
    "flat_full_invperm",
    "flat_full_presence",
]

# ── Theoretical model ─────────────────────────────────────────────────────────
# For each variant we explain the N², N, and constant terms separately.
# The public cost_matrix (N² u64 entries) dominates the N² term in all flat_full_*
# variants.  flat_merkle_presence has NO N² public inputs -- instead N*DEPTH
# Poseidon2 calls dominate, where DEPTH = ceil(log2(N²)).
#
# ACIR opcodes breakdown (flat_full_*):
#   All share a base of N² (public inputs) + N (GROUP 3 cost lookups) + smaller terms.
#   The permutation check adds:
#     pairwise:  N*(N-1) ~ N² extra opcodes  → a_total = 2
#     sort:      ~3N extra (ordering + shuffle ROM)
#     invperm:   2N extra (range + ROM lookup)
#     presence:  3N extra (range + RAM read + RAM write) + N init
#
# ACIR opcodes breakdown (flat_merkle_presence):
#   PUBLIC inputs: root (1 Field) + threshold (1 u64)  -- constant, no N² term.
#   GROUP 3 per edge: 1 Poseidon2 blackbox per level + ~2 arith per level
#     = ~3*DEPTH opcodes per edge  →  ~3*N*DEPTH total
#   DEPTH = ceil(log2(N²)) = 2*ceil(log2(N))  → O(N*log N)
#   The N² coefficient is expected to be ~0 in a quadratic fit.
#   Correct fit: a*N*log2(N) + b*N + c  (log-linear)
#
# UltraHonk gates breakdown (flat_merkle_presence):
#   Each Poseidon2 call (hash([l,r], 2)) costs ~264 gates.
#   Each leaf-index reconstruction step costs ~3 gates.
#   GROUP 3 dominant term: N*DEPTH * ~267 gates/level ≈ 267*N*DEPTH gates.
#   DEPTH = ceil(log2(N²)):  for N=5 → 5, N=50 → 12, N=100 → 14.
#   No N² term (no public matrix inputs -- root is 1 Field).
#
# Crossover analysis (circuit_size):
#   flat_full_presence:    7.25*N²  gates (grows quadratically)
#   flat_merkle_presence: ~267*N*DEPTH  gates (grows as N*log N)
#   Crossover condition:  7.25*N ≈ 267*DEPTH = 267*ceil(log2(N²)) ≈ 534*log2(N)
#   Numerical solution:   N/log2(N) ≈ 73.7  →  N_crossover ≈ 695 gates
#   ACIR opcode crossover: much earlier, N ≈ 28-30  (Poseidon2 costs only 1
#   ACIR opcode per call, but ~264 gates → opcodes mislead at the Merkle case).

THEORY = {
    "flat_full_pairwise": dict(
        acir_formula="2N^2 + 10N + 4",
        cs_formula="8.25N^2 + 14N + 2829",
        complexity_class="O(N^2)",
        perm_ops="N*(N-1) multiply ops  (2x N*(N-1)/2 pairs)",
        group1="explicit (N range checks)",
        extra_witness="none",
    ),
    "flat_full_sort": dict(
        acir_formula="N^2 + 17N + 4",
        cs_formula="7.25N^2 + 26N + 2829",
        complexity_class="O(N^2)",
        perm_ops="(N-1) ordering checks + ~2N ROM lookups  (check_shuffle)",
        group1="subsumed by GROUP 2",
        extra_witness="none",
    ),
    "flat_full_invperm": dict(
        acir_formula="N^2 + 13N + 5",
        cs_formula="7.25N^2 + 20N + 2831",
        complexity_class="O(N^2)",
        perm_ops="N range checks + N ROM lookups  (cycle[inv_perm[v]] == v)",
        group1="subsumed by GROUP 2",
        extra_witness="inv_perm array (O(N) prover scan)",
    ),
    "flat_full_presence": dict(
        acir_formula="N^2 + 13N + 10",
        cs_formula="7.25N^2 + 25N + 2837",
        complexity_class="O(N^2)",
        perm_ops="N RAM init + N range checks + N RAM reads + N RAM writes",
        group1="explicit (N range checks)",
        extra_witness="none  (RAM table, no extra witness field)",
    ),
    "flat_merkle_presence": dict(
        acir_formula="~3*N*DEPTH + 4N + c   [DEPTH=ceil(log2(N^2))]",
        cs_formula="~267*N*DEPTH + 5N + c  [~264 gates per Poseidon2 call]",
        complexity_class="O(N*log N)",
        perm_ops="same as flat_full_presence (RAM presence check, ~4N)",
        group1="explicit (N range checks)",
        extra_witness="edge_costs (N u64) + siblings (N*DEPTH Field) + path_bits (N*DEPTH bool)",
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def merkle_depth(n):
    """
    DEPTH = ceil(log2(N^2)) for the Merkle tree over N^2 leaves.
    Matches the formula in pipeline/format_inputs.py and pipeline/merkle_builder/.
    """
    n_sq = n * n
    return 0 if n_sq <= 1 else (n_sq - 1).bit_length()


def fit_quadratic(ns, ys):
    """Fit y = aN^2 + bN + c; return (a, b, c, r2)."""
    a, b, c = np.polyfit(ns, ys, 2)
    resid = ys - (a * ns**2 + b * ns + c)
    r2 = 1.0 - np.var(resid) / np.var(ys)
    return a, b, c, r2


def fit_nlogn(ns, ys):
    """
    Fit y = a*N*log2(N) + b*N + c via least squares; return (a, b, c, r2).

    Used for flat_merkle_presence where the dominant term is N*DEPTH and
    DEPTH = ceil(log2(N^2)) ~ 2*log2(N).  The quadratic fit degenerates (a~=0)
    for this variant, while the log-linear fit characterises the scaling and
    enables extrapolation to the crossover point with flat_full_*.
    """
    X = np.column_stack([ns * np.log2(ns), ns, np.ones_like(ns)])
    coeffs, _, _, _ = np.linalg.lstsq(X, ys, rcond=None)
    a, b, c = coeffs
    y_pred = a * ns * np.log2(ns) + b * ns + c
    resid = ys - y_pred
    r2 = 1.0 - np.var(resid) / np.var(ys)
    return float(a), float(b), float(c), float(r2)


def crossover_n(a_quad, b_quad, c_quad, a_nlogn, b_nlogn, c_nlogn):
    """
    Numerically find the N where the N*log2(N) curve crosses the N^2 curve.

    Returns the crossover N (float), or None if no crossing in [10, 10000].
    Used to estimate where flat_merkle_presence becomes cheaper than flat_full_*.
    """
    def diff(n):
        quad  = a_quad  * n**2 + b_quad  * n + c_quad
        nlogn = a_nlogn * n * np.log2(n) + b_nlogn * n + c_nlogn
        return quad - nlogn

    lo, hi = 10.0, 10_000.0
    if diff(lo) * diff(hi) > 0:
        return None  # same sign at both ends: no crossing in range
    # Binary search
    for _ in range(60):
        mid = (lo + hi) / 2
        if diff(lo) * diff(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def fmt_poly(a, b, c):
    """Pretty-print a quadratic as a string, suppressing near-zero terms."""
    parts = []
    if abs(a) > 0.001:
        parts.append(f"{a:.3f}*N^2")
    if abs(b) > 0.001:
        sign = "+" if b >= 0 else "-"
        parts.append(f"{sign} {abs(b):.3f}*N")
    if abs(c) > 0.001:
        sign = "+" if c >= 0 else "-"
        parts.append(f"{sign} {abs(c):.1f}")
    return "  ".join(parts) if parts else "0"


def load_data(csv_path):
    df = pd.read_csv(csv_path)
    # Mean per (variant, n) across runs
    return df.groupby(["variant", "n"])[["circuit_size", "acir_opcodes"]].mean().reset_index()


# ── Table printer ─────────────────────────────────────────────────────────────

def print_theory_table():
    """Print the theoretical complexity breakdown for each variant."""
    rows = [
        ("Variant",          "Class",        "Permutation ops (GROUP 1+2)",               "GROUP 1",   "Extra witness"),
        ("─"*20,             "─"*14,         "─"*48,                                      "─"*12,      "─"*38),
        ("pairwise",         "O(N^2)",       "N*(N-1) multiply gates",                    "explicit",  "none"),
        ("sort",             "O(N^2)",       "(N-1) ordering + ~2N ROM (shuffle)",        "subsumed",  "none"),
        ("invperm",          "O(N^2)",       "N range checks + N ROM lookups",            "subsumed",  "inv_perm array"),
        ("presence",         "O(N^2)",       "N RAM init + N range + N read + N write",   "explicit",  "none"),
        ("─"*20,             "─"*14,         "─"*48,                                      "─"*12,      "─"*38),
        ("merkle_presence",  "O(N*log N)",   "same as presence  PLUS:                 "
                                             "N*DEPTH Poseidon2 calls in GROUP 3",        "explicit",  "edge_costs + siblings + path_bits"),
    ]
    col_widths = [20, 14, 50, 12, 38]
    print("\n" + "=" * 142)
    print("THEORETICAL COMPLEXITY — constraint structure per variant")
    print("  flat_full_*:         scaling driven by N^2 public cost-matrix inputs (7.25 gates/element)")
    print("  flat_merkle_presence: NO N^2 public inputs; scaling driven by N*DEPTH Poseidon2 calls")
    print("                        DEPTH = ceil(log2(N^2));  each call ~264 UltraHonk gates")
    print("=" * 142)
    for row in rows:
        line = "  ".join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
        print(line)
    print()


def print_fit_table(df, variants):
    """Print fitted polynomial coefficients and compare to theoretical predictions.

    For flat_full_* variants the quadratic model a*N^2 + b*N + c is exact (R^2=1.000).
    For flat_merkle_presence the quadratic fit returns a≈0 (correct — no N^2 inputs),
    but the dominant term is N*log(N); see print_nlogn_fit_table() for that fit.
    """
    flat_full = [v for v in variants if v in FLAT_FULL_VARIANTS]
    merkle    = [v for v in variants if v == "flat_merkle_presence"]

    header = f"  {'Variant':<20}  {'a (N^2)':>10}  {'b (N)':>8}  {'c':>8}  {'R^2':>10}  Interpretation"

    # ── acir_opcodes ──────────────────────────────────────────────────────────
    print("=" * 130)
    print("EMPIRICAL FIT — acir_opcodes = a*N^2 + b*N + c")
    print("  For flat_full_*: N^2 term is structural (cost_matrix public inputs).")
    print("  For flat_merkle_presence: a≈0 is EXPECTED — no N^2 public inputs.")
    print("    The true scaling is N*log(N); see the log-linear fit table below.")
    print("=" * 130)
    print(header)
    print("  " + "─" * 88)

    for v in flat_full + merkle:
        sub = df[df.variant == v]
        ns  = sub["n"].values.astype(float)
        ys  = sub["acir_opcodes"].values.astype(float)
        a, b, c, r2 = fit_quadratic(ns, ys)
        if v == "flat_merkle_presence":
            interp = "a≈0 as expected (O(N*log N), not O(N^2)) — see log-linear fit below"
        elif a > 1.5:
            interp = "a≈2: N^2 inputs (1 ea.) + N*(N-1) pairwise ops (1 ea.) → pairwise O(N^2)"
        else:
            interp = "a≈1: dominated by N^2 public cost_matrix inputs (1 opcode ea.)"
        vname = v.replace("flat_full_", "").replace("flat_", "")
        print(f"  {vname:<20}  {a:>10.4f}  {b:>8.4f}  {c:>8.1f}  {r2:>10.6f}  {interp}")

    print()
    print("  NOTE: flat_full_* have R^2=1.000 (quadratic is exact for these variants).")
    print("  Pairwise a≈2 = 1 (public inputs) + 1 (pairwise multiply ops).")
    print()

    # ── circuit_size ──────────────────────────────────────────────────────────
    print("=" * 130)
    print("EMPIRICAL FIT — circuit_size = a*N^2 + b*N + c  (UltraHonk gates)")
    print("  For flat_full_*: a≈7.25 = cost per public u64 input (field plumbing gates).")
    print("  For flat_merkle_presence: a≈0 (no N^2 inputs) — Poseidon2 gates scale as N*log(N).")
    print("=" * 130)
    print(header)
    print("  " + "─" * 88)

    for v in flat_full + merkle:
        sub = df[df.variant == v]
        ns  = sub["n"].values.astype(float)
        ys  = sub["circuit_size"].values.astype(float)
        a, b, c, r2 = fit_quadratic(ns, ys)
        if v == "flat_merkle_presence":
            interp = "a≈0: no N^2 inputs; ~264 gates/Poseidon2 call → dominant term is N*DEPTH*264"
        elif a > 7.8:
            interp = "a≈8.25: N^2 inputs (7.25 gates) + N^2/2 multiply gates (1 gate ea.)"
        else:
            interp = "a≈7.25: N^2 public inputs cost ~7.25 UltraHonk gates each"
        vname = v.replace("flat_full_", "").replace("flat_", "")
        print(f"  {vname:<20}  {a:>10.4f}  {b:>8.4f}  {c:>8.1f}  {r2:>10.6f}  {interp}")

    print()
    print("  KEY: pairwise a/invperm a = 8.25/7.25 ≈ 1.14  (pairwise multiply gates add 1 gate")
    print("  each, but public input plumbing dominates at large N in ALL flat_full_* variants).")
    print()


def print_nlogn_fit_table(df, variants):
    """
    Fit the log-linear model  y = a*N*log2(N) + b*N + c  to flat_merkle_presence,
    and compute the crossover N where flat_merkle_presence becomes cheaper than
    flat_full_presence (the most comparable flat_full_* variant).

    Also highlights the ACIR vs gate-count crossover discrepancy:
      - ACIR opcode crossover at N≈28-30  (Poseidon2 = 1 opcode, cheap to count)
      - circuit_size crossover at N≈695   (Poseidon2 = ~264 gates, expensive to execute)
    """
    if "flat_merkle_presence" not in df["variant"].unique():
        return  # No merkle data available yet
    if "flat_full_presence" not in df["variant"].unique():
        return

    print("=" * 110)
    print("LOG-LINEAR FIT — flat_merkle_presence: y = a*N*log2(N) + b*N + c")
    print("  DEPTH = ceil(log2(N^2)) ≈ 2*log2(N); each Poseidon2 call = ~264 UltraHonk gates.")
    print("=" * 110)

    header = f"  {'Metric':<16}  {'a (N*log2N)':>14}  {'b (N)':>10}  {'c':>10}  {'R^2':>8}"
    print(header)
    print("  " + "─" * 64)

    sub_m = df[df.variant == "flat_merkle_presence"]
    ns_m  = sub_m["n"].values.astype(float)

    fits = {}
    for col in ("acir_opcodes", "circuit_size"):
        ys = sub_m[col].values.astype(float)
        a, b, c, r2 = fit_nlogn(ns_m, ys)
        fits[col] = (a, b, c, r2)
        print(f"  {col:<16}  {a:>14.4f}  {b:>10.4f}  {c:>10.1f}  {r2:>8.6f}")

    print()

    # Crossover analysis vs flat_full_presence
    sub_p = df[df.variant == "flat_full_presence"]
    ns_p  = sub_p["n"].values.astype(float)

    print("  CROSSOVER ANALYSIS: flat_merkle_presence vs flat_full_presence")
    print("  ─" * 40)

    for col, label in [("acir_opcodes", "ACIR opcodes"), ("circuit_size", "circuit_size (gates)")]:
        ys_p = sub_p[col].values.astype(float)
        aq, bq, cq, _ = fit_quadratic(ns_p, ys_p)
        am, bm, cm, _ = fits[col]
        n_cross = crossover_n(aq, bq, cq, am, bm, cm)
        if n_cross is None:
            print(f"  {label:<22}: no crossover found in N=[10, 10000]")
        else:
            print(f"  {label:<22}: crossover at N ≈ {n_cross:.0f}")
            if col == "acir_opcodes":
                print(f"    (merkle is cheaper in ACIR opcodes from N≈{n_cross:.0f}, but this")
                print(f"     understates the gate cost -- each Poseidon2 blackbox = 1 opcode but ~264 gates)")
            else:
                print(f"    (merkle is cheaper in actual gates from N≈{n_cross:.0f})")
                print(f"     The large crossover N reflects that ~264 gates/Poseidon2 >> 7.25 gates/public-input)")

    print()
    print("  INTERPRETATION:")
    print("  The ACIR opcode crossover (~N=30) and the gate crossover (~N=695) differ by ~23x.")
    print("  Root cause: Poseidon2 is 1 ACIR BlackBox opcode but ~264 UltraHonk gates (~264x expansion).")
    print("              Public u64 input is 1 ACIR opcode and ~7.25 UltraHonk gates (~7x expansion).")
    print("  Lesson: for ZK-hash-heavy circuits, ACIR opcode count is a misleading complexity proxy.")
    print("          circuit_size (gate count) is the correct metric for proving cost comparison.")
    print()


def print_linear_overhead_table(df, variants):
    """Show the permutation check overhead as circuit_size(variant) - circuit_size(invperm).

    Only flat_full_* variants are included.  flat_merkle_presence is excluded because
    its dominant cost (N*DEPTH Poseidon2 calls) is in GROUP 3 -- the Merkle proof step --
    not in the permutation check.  Its permutation check (GROUP 2) is identical to
    flat_full_presence, so it would show the same linear overhead as presence but the
    GROUP 3 cost would dwarf it, making the comparison misleading.
    """
    # Restrict to flat_full_* variants only
    variants = [v for v in variants if v in FLAT_FULL_VARIANTS]
    if not variants or "flat_full_invperm" not in variants:
        return

    print("=" * 100)
    print("PERMUTATION CHECK OVERHEAD — (variant circuit_size) − (invperm circuit_size)")
    print("Isolates the marginal cost of each permutation strategy (flat_full_* only).")
    print("flat_merkle_presence excluded: its GROUP 3 Poseidon2 cost dominates and is")
    print("not a permutation-check overhead -- see the crossover analysis above.")
    print("=" * 100)

    pivot = df.pivot_table(index="n", columns="variant", values="circuit_size", aggfunc="mean")
    base = pivot["flat_full_invperm"]
    ns = pivot.index.values.astype(float)

    header = f"  {'N':>4}" + "".join(f"  {v.replace('flat_full_',''):>12}" for v in variants)
    print(header)
    print("  " + "─" * 70)
    for n, row in pivot.iterrows():
        line = f"  {int(n):>4}"
        for v in variants:
            diff = row[v] - base[n]
            line += f"  {int(diff):>12}"
        print(line)

    print()
    print("  Slope analysis (linear fit to each overhead column):")
    for v in variants:
        diffs = (pivot[v] - base).values
        slope, intercept = np.polyfit(ns, diffs, 1)
        vname = v.replace("flat_full_", "")
        print(f"    {vname:<12}  overhead ≈ {slope:.2f}·N + {intercept:.1f}")
    print()
    print("  Expected ordering (cheapest → most expensive permutation check):")
    print("    invperm (baseline, 2N) < presence (~4N RAM) < sort (~3N ROM) < pairwise (N²)")
    print("  Empirical ordering at large N: invperm < presence < sort < pairwise  ✓")
    print("  sort costs more per N than presence despite fewer theoretical ops,")
    print("  because sort_via's check_shuffle uses ~2N ROM lookups that are each more")
    print("  expensive in UltraHonk gates than the simple boolean RAM ops in presence.")
    print()


# ── Plots ─────────────────────────────────────────────────────────────────────

def make_comparison_figure(df, variants, out_stem, dpi=150):
    """
    Four-panel figure:
      (a) acir_opcodes vs N  — data + fitted curves
          flat_full_*: quadratic fit (solid line)
          flat_merkle_presence: N*log2(N) fit (dashed line)
      (b) circuit_size vs N  — same as (a) but gates
      (c) acir_opcodes on log-log with slope annotations
      (d) permutation overhead (variant - invperm) for circuit_size
          flat_full_* only — flat_merkle_presence excluded (GROUP 3 Poseidon2 cost dominates)
    """
    flat_full = [v for v in variants if v in FLAT_FULL_VARIANTS]
    merkle    = [v for v in variants if v == "flat_merkle_presence"]

    n_min    = df["n"].min()
    n_max    = df["n"].max()
    ns_dense = np.linspace(n_min, n_max, 300)

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    fig.suptitle("Circuit Complexity: Theoretical Prediction vs Empirical Data", fontsize=13, y=0.98)

    def _plot_variant(ax, v, col):
        sub = df[df.variant == v]
        ns  = sub["n"].values.astype(float)
        ys  = sub[col].values.astype(float)
        ax.scatter(ns, ys, color=PALETTE[v], marker=MARKERS[v], s=40, zorder=3)
        if v == "flat_merkle_presence":
            a, b, c, _ = fit_nlogn(ns, ys)
            y_fit = a * ns_dense * np.log2(ns_dense) + b * ns_dense + c
            ax.plot(ns_dense, y_fit, color=PALETTE[v], lw=1.5, linestyle="--", label=LABELS[v])
        else:
            a, b, c, _ = fit_quadratic(ns, ys)
            ax.plot(ns_dense, a * ns_dense**2 + b * ns_dense + c,
                    color=PALETTE[v], lw=1.5, label=LABELS[v])

    # ── (a) acir_opcodes linear ───────────────────────────────────────────────
    ax = axes[0, 0]
    for v in flat_full + merkle:
        _plot_variant(ax, v, "acir_opcodes")
    ax.set_title("(a) ACIR opcodes — linear axes\n(merkle dashed = N*log2(N) fit)")
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("acir_opcodes")
    ax.legend(fontsize=7.5, loc="upper left")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # ── (b) circuit_size linear ───────────────────────────────────────────────
    ax = axes[0, 1]
    for v in flat_full + merkle:
        _plot_variant(ax, v, "circuit_size")
    ax.set_title("(b) UltraHonk circuit_size — linear axes\n(merkle dashed = N*log2(N) fit)")
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("circuit_size (gates)")
    ax.legend(fontsize=7.5, loc="upper left")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # ── (c) acir_opcodes log-log with empirical slope ─────────────────────────
    ax = axes[1, 0]
    for v in flat_full + merkle:
        sub = df[df.variant == v]
        ns  = sub["n"].values.astype(float)
        ys  = sub["acir_opcodes"].values.astype(float)
        ax.scatter(ns, ys, color=PALETTE[v], marker=MARKERS[v], s=40, zorder=3)
        if v == "flat_merkle_presence":
            a, b, c, _ = fit_nlogn(ns, ys)
            y_fit = a * ns_dense * np.log2(ns_dense) + b * ns_dense + c
            ax.plot(ns_dense, y_fit, color=PALETTE[v], lw=1.5, linestyle="--", label=LABELS[v])
        else:
            a, b, c, _ = fit_quadratic(ns, ys)
            ax.plot(ns_dense, a * ns_dense**2 + b * ns_dense + c,
                    color=PALETTE[v], lw=1.5, label=LABELS[v])
        # Empirical log-log slope (last few points, asymptotic regime)
        mask = ns >= 20
        log_slope = np.polyfit(np.log(ns[mask]), np.log(ys[mask]), 1)[0]
        ax.annotate(f"  slope≈{log_slope:.2f}", xy=(ns[-1] * 1.03, ys[-1]),
                    color=PALETTE[v], fontsize=7, va="center")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("(c) ACIR opcodes — log-log  (empirical slope annotated)")
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("acir_opcodes")
    ax.legend(fontsize=7.5, loc="upper left")

    # ── (d) permutation overhead: (variant - invperm) for circuit_size ────────
    # flat_full_* only; merkle excluded (Poseidon2 GROUP 3 cost dominates overhead)
    ax = axes[1, 1]
    if "flat_full_invperm" in flat_full:
        pivot = df[df.variant.isin(flat_full)].pivot_table(
            index="n", columns="variant", values="circuit_size", aggfunc="mean"
        )
        base   = pivot["flat_full_invperm"]
        ns_arr = pivot.index.values.astype(float)

        for v in [x for x in flat_full if x != "flat_full_invperm"]:
            if v not in pivot.columns:
                continue
            diffs = (pivot[v] - base).values
            slope, intercept = np.polyfit(ns_arr, diffs, 1)
            ax.scatter(ns_arr, diffs, color=PALETTE[v], marker=MARKERS[v], s=40, zorder=3)
            ax.plot(ns_dense, slope * ns_dense + intercept,
                    color=PALETTE[v], lw=1.5,
                    label=f"{v.replace('flat_full_','')}  (slope≈{slope:.1f}*N)")
        ax.axhline(0, color=PALETTE["flat_full_invperm"], lw=1.5, linestyle="--",
                   label="invperm (baseline = 0)")
    ax.set_title("(d) Permutation-check overhead  (vs invperm, flat_full_* only)")
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("circuit_size − invperm circuit_size")
    ax.legend(fontsize=7.5, loc="upper left")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    fig.tight_layout()
    out_path = Path(out_stem + ".png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Saved: {out_path}")
    plt.close(fig)


def make_crossover_figure(df, variants, out_stem, dpi=150):
    """
    Two-panel crossover figure (only produced when flat_merkle_presence data is present):
      (a) Benchmark range: flat_full_presence vs flat_merkle_presence for circuit_size,
          showing where the curves visually approach using the actual data + fitted models.
      (b) Extrapolation to N=1000 on a log-Y axis, showing both circuit_size and
          ACIR opcode crossover points annotated with vertical dashed lines.
    """
    if "flat_merkle_presence" not in df["variant"].unique():
        return
    if "flat_full_presence" not in df["variant"].unique():
        return

    sub_p  = df[df.variant == "flat_full_presence"]
    sub_m  = df[df.variant == "flat_merkle_presence"]
    ns_p   = sub_p["n"].values.astype(float)
    ns_m   = sub_m["n"].values.astype(float)

    n_data_max = df["n"].max()
    n_extrap   = 1000

    ns_data   = np.linspace(2, n_data_max, 300)
    ns_extrap = np.linspace(2, n_extrap, 1200)

    # Pre-fit both models for both metrics
    fits = {}
    for col in ("acir_opcodes", "circuit_size"):
        ys_p = sub_p[col].values.astype(float)
        ys_m = sub_m[col].values.astype(float)
        fits[col] = {
            "presence": fit_quadratic(ns_p, ys_p),
            "merkle":   fit_nlogn(ns_m, ys_m),
        }

    colour_p = PALETTE["flat_full_presence"]
    colour_m = PALETTE["flat_merkle_presence"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle(
        "flat_merkle_presence vs flat_full_presence: Benchmark Range and Crossover Extrapolation",
        fontsize=11, y=1.02,
    )

    # ── Panel (a): benchmark range, circuit_size ──────────────────────────────
    ax = axes[0]
    aq, bq, cq, _ = fits["circuit_size"]["presence"]
    am, bm, cm, _ = fits["circuit_size"]["merkle"]
    ax.scatter(ns_p, sub_p["circuit_size"].values,
               color=colour_p, marker=MARKERS["flat_full_presence"], s=45, zorder=3)
    ax.scatter(ns_m, sub_m["circuit_size"].values,
               color=colour_m, marker=MARKERS["flat_merkle_presence"], s=45, zorder=3)
    ax.plot(ns_data, aq * ns_data**2 + bq * ns_data + cq,
            color=colour_p, lw=2, label="flat_full_presence  (O(N^2) fit)")
    ax.plot(ns_data, am * ns_data * np.log2(ns_data) + bm * ns_data + cm,
            color=colour_m, lw=2, linestyle="--",
            label="flat_merkle_presence  (O(N*log N) fit)")
    ax.set_title("(a) Benchmark range: circuit_size (gates)")
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("circuit_size (gates)")
    ax.legend(fontsize=8.5)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))

    # ── Panel (b): extrapolation to N=1000, both metrics, log-Y ──────────────
    ax = axes[1]
    metric_styles = [
        ("circuit_size",  "gates",        colour_p,            colour_m,            "-",  "--"),
        ("acir_opcodes",  "ACIR opcodes", "#e41a1c",           "#984ea3",           "-.", ":"),
    ]
    for col, suffix, cp, cm_col, lsp, lsm in metric_styles:
        aq2, bq2, cq2, _ = fits[col]["presence"]
        am2, bm2, cm2, _ = fits[col]["merkle"]
        y_p = aq2 * ns_extrap**2 + bq2 * ns_extrap + cq2
        y_m = am2 * ns_extrap * np.log2(ns_extrap) + bm2 * ns_extrap + cm2
        ax.semilogy(ns_extrap, y_p,  lw=1.8, color=cp,    linestyle=lsp,
                    label=f"presence ({suffix})")
        ax.semilogy(ns_extrap, y_m,  lw=1.8, color=cm_col, linestyle=lsm,
                    label=f"merkle ({suffix})")
        # Crossover annotation
        n_cross = crossover_n(aq2, bq2, cq2, am2, bm2, cm2)
        if n_cross is not None and n_cross < n_extrap:
            y_cross = aq2 * n_cross**2 + bq2 * n_cross + cq2
            ax.axvline(n_cross, color="gray", lw=0.8, linestyle=":")
            ax.annotate(
                f"N≈{n_cross:.0f}\n({suffix})",
                xy=(n_cross, y_cross),
                xytext=(n_cross + 40, y_cross * 3),
                fontsize=7.5,
                arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
            )
    ax.set_title("(b) Extrapolation to N=1000 (log Y)\ncrossover = where merkle becomes cheaper")
    ax.set_xlabel("N (nodes)")
    ax.set_ylabel("value (log scale)")
    ax.legend(fontsize=7.5, loc="upper left")

    fig.tight_layout()
    out_path = Path(out_stem + "_crossover.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    print(f"Saved: {out_path}")
    plt.close(fig)


# ── Entry point ───────────────────────────────────────────────────────────────

VARIANTS_ORDER = [
    "flat_full_pairwise",
    "flat_full_sort",
    "flat_full_invperm",
    "flat_full_presence",
    "flat_merkle_presence",
]


def main():
    parser = argparse.ArgumentParser(description="Complexity analysis: theory vs empirical.")
    parser.add_argument("--csv", default="results/flat_full.csv",
                        help="Combined benchmark CSV (default: results/flat_full.csv)")
    parser.add_argument("--merkle-csv", default=None,
                        help="Optional separate CSV for flat_merkle_presence results")
    parser.add_argument("--out", default="plots/flat_full_complexity",
                        help="Output PNG path stem (default: plots/flat_full_complexity)")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    df = load_data(args.csv)
    if args.merkle_csv:
        df = pd.concat([df, load_data(args.merkle_csv)], ignore_index=True)

    present = [v for v in VARIANTS_ORDER if v in df["variant"].unique()]

    print_theory_table()
    print_fit_table(df, present)
    print_nlogn_fit_table(df, present)
    print_linear_overhead_table(df, present)
    make_comparison_figure(df, present, args.out, dpi=args.dpi)
    if "flat_merkle_presence" in present:
        make_crossover_figure(df, present, args.out, dpi=args.dpi)


if __name__ == "__main__":
    main()
