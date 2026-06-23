"""
pipeline/plot_recursion_stack.py -- recursion-specific component bar charts.

The generic line-plotter (pipeline/plot.py) answers "how does metric X scale with
N"; this script answers a different question -- "for the recursion variant, WHERE
does the cost go (segments vs the aggregating outer), and how does the per-node
parallel cost compare to the cumulative single-machine cost".  It is the rendering
behind HIER_MEASUREMENT_AND_PLOTS.md section E (composition family) for recursion.

Input is the RAW recursion CSV (pipeline/run_recursion.py output: one row per
measured circuit, role in {inner_segment, outer_recursive}), NOT the aggregated
CSV.  We read the per-segment rows directly because the chart needs BOTH the
single-segment value and the cumulative-over-K value, and the aggregator's _seg
row conflates them (its circuit_size is cumulative but its peak_mb is the single
max).  Reading raw keeps every per-metric rule explicit and correct here.

Chart design (metric-aware -- a naive 3-layer single|cumulative|outer bar is
wrong: single is a 1/K SUBSET of cumulative, so stacking both double-counts the
inner work; and memory peaks do not sum across phases that never co-reside):

  * ADDITIVE metrics (circuit_size, acir_opcodes, prove_s, witness_s):
    2-layer STACK that genuinely sums to a total --
        bottom = cumulative segments (sum over the K inner proofs)
        top    = outer recursive proof
    plus a thin COMPANION bar = single segment (the per-node / ideal-parallel
    value, ~= max over the K identical segments).  For time the stack height is
    the single-machine total CPU (sum_inner + outer) while the companion shows the
    parallel leaf cost; for gates it is the total proving work K*sub + outer.

  * peak_mb -> GROUPED bars, NEVER stacked.  Peak memory is max-not-sum: under
    recursion's sequential flow only one prover is resident at a time (the outer
    consumes the inner proofs as data after they have exited), so the machine peak
    is max(single-segment, outer) ~= outer.  We draw single-segment vs outer side
    by side.  --include-concurrent-mem adds a faint "sum over K segments"
    hypothetical bar (only realized if all K inner provers ran CONCURRENTLY, which
    recursion does not do) for completeness.

  * OUTER-ONLY metrics (verify_s, proof_bytes): a single bar per N -- the verifier
    checks exactly one proof and one proof is delivered, so the segments contribute
    nothing here (recursion's O(1) verifier win).

K is fixed per figure (--k); recursion is generic over K and mixing K on one
per-N axis would be ambiguous.  Run once per K if you want several.

Usage:
    PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
    $PY pipeline/plot_recursion_stack.py --csv results/recursion.csv \\
        --k 2 --out plots/recursion_components

    # pick metrics / format / fixed exp:
    $PY pipeline/plot_recursion_stack.py --csv results/recursion.csv --k 2 \\
        --metrics circuit_size prove_s peak_mb verify_s --format pdf --no-title \\
        --out plots/recursion_components

Outputs one file per metric: <out>_<metric>.<fmt>.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Metric registry: cli_name -> (raw CSV column, kind, y-axis label, title) ──
# kind: "stack" (additive: seg+outer), "grouped" (memory: not summable),
#       "single" (outer-only).
METRICS = {
    "circuit_size": ("gates",       "stack",   "UltraHonk gates",  "Circuit size (gates)"),
    "acir_opcodes": ("acir",        "stack",   "ACIR opcodes",     "ACIR opcodes"),
    "prove_s":      ("prove_s",     "stack",   "Time (s)",         "Prove time"),
    "witness_s":    ("witness_s",   "stack",   "Time (s)",         "Witness-generation time"),
    "peak_mb":      ("peak_mb",     "grouped", "Memory (MiB)",     "Peak memory (prove)"),
    "verify_s":     ("verify_s",    "single",  "Time (s)",         "Verify time (outer only)"),
    "proof_bytes":  ("proof_bytes", "single",  "Bytes",            "Proof size (outer only)"),
}
DEFAULT_METRICS = ["circuit_size", "prove_s", "peak_mb"]

# ── Colours ───────────────────────────────────────────────────────────────────
C_SEG    = "#1d4ed8"  # cumulative segments (stack bottom)
C_OUTER  = "#b91c1c"  # outer recursive proof (stack top / single)
C_SINGLE = "#60a5fa"  # single segment (per-node companion)
C_CONC   = "#93c5fd"  # hypothetical concurrent-sum memory


def _f(s):
    """Parse a possibly-blank CSV float cell; None if blank/nan."""
    if s is None or s in ("", "nan", "NaN"):
        return None
    return float(s)


def load_components(paths, k, exp):
    """Read raw recursion CSV(s); return {n: {component: {metric_col: [per-run vals]}}}.

    components: 'seg_single' (max over K inner), 'seg_cumulative' (sum over K inner),
    'seg_concurrent' (== cumulative for memory), 'outer'.  Grouped by (n, run) first
    so per-run sums/maxes are correct, then collected per n across runs.
    """
    cols = [m[0] for m in METRICS.values()]
    # cell[(n, run)] = {"inner": [rows], "outer": row}
    cell = defaultdict(lambda: {"inner": [], "outer": None})
    for path in paths:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if int(row["exp"]) != exp or int(row["k"]) != k:
                    continue
                key = (int(row["n"]), int(row["run"]))
                if row["role"] == "inner_segment":
                    cell[key]["inner"].append(row)
                elif row["role"] == "outer_recursive":
                    cell[key]["outer"] = row

    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for (n, _run), g in cell.items():
        inner, outer = g["inner"], g["outer"]
        if not inner or outer is None:
            continue
        for col in cols:
            inner_vals = [_f(r[col]) for r in inner]
            inner_vals = [v for v in inner_vals if v is not None]
            if inner_vals:
                data[n]["seg_single"][col].append(max(inner_vals))
                data[n]["seg_cumulative"][col].append(sum(inner_vals))
            ov = _f(outer[col])
            if ov is not None:
                data[n]["outer"][col].append(ov)
    return data


def _mean_std(data, n, component, col):
    vals = data[n][component].get(col, [])
    if not vals:
        return float("nan"), 0.0
    return float(np.mean(vals)), float(np.std(vals, ddof=0))


def draw_metric(ax, data, ns, metric, include_concurrent_mem):
    col, kind, ylabel, title = METRICS[metric]
    x = np.arange(len(ns))

    if kind == "stack":
        seg = np.array([_mean_std(data, n, "seg_cumulative", col)[0] for n in ns])
        out = np.array([_mean_std(data, n, "outer", col)[0]          for n in ns])
        tot_std = np.array([
            _mean_std(data, n, "seg_cumulative", col)[1] + _mean_std(data, n, "outer", col)[1]
            for n in ns])
        single = np.array([_mean_std(data, n, "seg_single", col)[0] for n in ns])

        w = 0.34
        ax.bar(x - 0.19, seg, w, color=C_SEG,   label="K segments (Σ, cumulative)")
        ax.bar(x - 0.19, out, w, bottom=seg, color=C_OUTER,
               label="outer (aggregation)")
        ax.errorbar(x - 0.19, seg + out, yerr=tot_std, fmt="none",
                    ecolor="#222", elinewidth=1.0, capsize=3)
        ax.bar(x + 0.23, single, 0.18, color=C_SINGLE,
               label="1 segment (per-node / parallel)")

    elif kind == "grouped":
        single = np.array([_mean_std(data, n, "seg_single", col)[0] for n in ns])
        s_std  = np.array([_mean_std(data, n, "seg_single", col)[1] for n in ns])
        out    = np.array([_mean_std(data, n, "outer", col)[0]      for n in ns])
        o_std  = np.array([_mean_std(data, n, "outer", col)[1]      for n in ns])

        if include_concurrent_mem:
            conc = np.array([_mean_std(data, n, "seg_cumulative", col)[0] for n in ns])
            w = 0.26
            ax.bar(x - w, single, w, yerr=s_std, capsize=3, color=C_SINGLE,
                   label="1 segment (per node)")
            ax.bar(x, conc, w, color=C_CONC,
                   label="Σ segments (concurrent — hypothetical)")
            ax.bar(x + w, out, w, yerr=o_std, capsize=3, color=C_OUTER, label="outer")
        else:
            w = 0.38
            ax.bar(x - w / 2, single, w, yerr=s_std, capsize=3, color=C_SINGLE,
                   label="1 segment (per node)")
            ax.bar(x + w / 2, out, w, yerr=o_std, capsize=3, color=C_OUTER, label="outer")

    else:  # single (outer-only)
        out   = np.array([_mean_std(data, n, "outer", col)[0] for n in ns])
        o_std = np.array([_mean_std(data, n, "outer", col)[1] for n in ns])
        ax.bar(x, out, 0.5, yerr=o_std, capsize=3, color=C_OUTER, label="outer (only)")

    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel("N (nodes)", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in ns])
    ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.ticklabel_format(axis="y", style="plain")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    ax.legend(fontsize=8, framealpha=0.9)


def main():
    ap = argparse.ArgumentParser(description="Recursion component bar charts (raw CSV in).")
    ap.add_argument("--csv", nargs="+", required=True, help="Raw recursion CSV(s).")
    ap.add_argument("--out", required=True, help="Output path prefix (no extension).")
    ap.add_argument("--k", type=int, required=True, help="Fixed K to plot (e.g. 2).")
    ap.add_argument("--exp", type=int, default=2, help="Experiment (default 2 = the variant).")
    ap.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS,
                    choices=list(METRICS.keys()), metavar="METRIC",
                    help=f"Metrics to plot (default: {' '.join(DEFAULT_METRICS)}).")
    ap.add_argument("--include-concurrent-mem", action="store_true",
                    help="Add the (hypothetical) Σ-segments concurrent memory bar to peak_mb.")
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    ap.add_argument("--no-title", action="store_true", help="Omit the figure suptitle.")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    paths = [Path(p) for p in args.csv]
    data = load_components(paths, args.k, args.exp)
    ns = sorted(data.keys())
    if not ns:
        print(f"No rows for exp={args.exp} k={args.k} in {args.csv}.")
        return
    print(f"K={args.k} exp={args.exp}; N values: {ns}")

    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for metric in args.metrics:
        fig, ax = plt.subplots(1, 1, figsize=(max(6.0, 1.1 * len(ns) + 3), 4.6))
        draw_metric(ax, data, ns, metric, args.include_concurrent_mem)
        if not args.no_title:
            fig.suptitle(f"Recursion components — {METRICS[metric][3]} (K={args.k})",
                         fontsize=12, fontweight="bold")
        fig.tight_layout(rect=[0, 0, 1, 0.96] if not args.no_title else None)
        path = out_prefix.parent / f"{out_prefix.name}_{metric}.{args.format}"
        fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
