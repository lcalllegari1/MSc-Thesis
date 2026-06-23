"""
pipeline/plot_composite_recursive_modes.py -- recursion-only PARALLEL vs TOTAL gap.

Motivation figure for the recursion-alone section: it shows that the parallel
(distributed) and total (single-machine) wall-clock are CLOSE -- because the
serial outer dominates and only the cheap segment phase parallelizes (Amdahl).
Visualising the small gap is what justifies carrying the *total* (single-machine)
number into the apples-to-apples comparison with flat (flat is single-machine
too), rather than the optimistic parallel projection.

Only TIME metrics (prove_s, witness_s) differ between modes -- gates are
structural and memory is per-process max, so their gap is zero by construction;
this script therefore restricts to the time metrics.

Mode is NOT a column in the CSV.  Rather than aggregate twice with
--mode-in-name, this reads the RAW recursion CSV (run_composite_recursive.py output) and
derives BOTH modes itself, per (N, K, run):

    parallel = max(inner segments) + outer      (K nodes, distributed)
    total    = sum(inner segments) + outer      (one machine, sequential)

For each K it draws the two lines (same hue, parallel solid / total dashed) and
shades the gap between them.  Grid by default; --separate for thesis figures.

Usage:
    PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
    $PY pipeline/plot_composite_recursive_modes.py --csv results/recursive_raw.csv \\
        --out plots/recursion_modes
    # one metric, K in {2,8}, vector:
    $PY pipeline/plot_composite_recursive_modes.py --csv results/recursive_raw.csv \\
        --out plots/recursion_modes --metrics prove_s --k 2 8 \\
        --separate --format pdf --no-title
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plot_composite_recursive_lines import _color_for_k  # K-aware palette (shared)

# metric -> (raw column, panel title, y label)
METRICS = {
    "prove_s":   ("prove_s",   "Prove time",                "Time (s)"),
    "witness_s": ("witness_s", "Witness-generation time",   "Time (s)"),
}
DEFAULT_METRICS = ["prove_s"]


def _f(s):
    return None if s in (None, "", "nan", "NaN") else float(s)


def load(paths, exp):
    """Raw CSV -> data[(n,k)][metric][mode] = [per-run combined values]."""
    cell = defaultdict(lambda: {"inner": defaultdict(list), "outer": {}})
    for p in paths:
        with open(p, newline="") as f:
            for r in csv.DictReader(f):
                if int(r["exp"]) != exp:
                    continue
                key = (int(r["n"]), int(r["k"]), int(r["run"]))
                if r["role"] == "inner_segment":
                    for m, (col, _, _) in METRICS.items():
                        v = _f(r[col])
                        if v is not None:
                            cell[key]["inner"][m].append(v)
                elif r["role"] == "outer_recursive":
                    for m, (col, _, _) in METRICS.items():
                        cell[key]["outer"][m] = _f(r[col])

    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for (n, k, _run), g in cell.items():
        for m in METRICS:
            inner = g["inner"].get(m, [])
            outer = g["outer"].get(m)
            if not inner or outer is None:
                continue
            data[(n, k)][m]["parallel"].append(max(inner) + outer)
            data[(n, k)][m]["total"].append(sum(inner) + outer)
    return data


def _mean(vals):
    return float(np.mean(vals)) if vals else float("nan")


def draw(ax, data, metric, ks, loglog):
    drew = False
    for k in ks:
        ns = sorted(n for (n, kk) in data if kk == k and metric in data[(n, kk)])
        if not ns:
            continue
        color = _color_for_k(k) or "#374151"
        x   = np.array(ns, dtype=float)
        par = np.array([_mean(data[(n, k)][metric]["parallel"]) for n in ns])
        tot = np.array([_mean(data[(n, k)][metric]["total"])    for n in ns])
        ax.fill_between(x, par, tot, color=color, alpha=0.13, zorder=1)
        ax.plot(x, par, color=color, ls="-",  marker="o", ms=5, lw=1.7,
                label=f"K={k} parallel (max+outer)", zorder=3)
        ax.plot(x, tot, color=color, ls="--", marker="X", ms=6, lw=1.7,
                markerfacecolor="white", label=f"K={k} total (sum+outer)", zorder=3)
        drew = True
    if not drew:
        return False
    if loglog:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.set_title(METRICS[metric][1], fontsize=11, fontweight="bold")
    ax.set_xlabel("N (nodes)", fontsize=9)
    ax.set_ylabel(METRICS[metric][2], fontsize=9)
    ax.grid(True, ls="--", alpha=0.4)
    ax.legend(fontsize=7.5, framealpha=0.9, loc="best")
    return True


def print_ratios(data, ks):
    print("parallel/total ratio (closer to 1 = parallelism helps less):")
    for k in ks:
        ns = sorted(n for (n, kk) in data if kk == k and "prove_s" in data[(n, kk)])
        for n in ns:
            par = _mean(data[(n, k)]["prove_s"]["parallel"])
            tot = _mean(data[(n, k)]["prove_s"]["total"])
            if tot:
                print(f"  K={k} N={n:>5}: parallel={par:7.2f}s total={tot:7.2f}s  P/T={par/tot:.2f}")


def main():
    ap = argparse.ArgumentParser(description="Recursion-only parallel-vs-total gap (raw CSV in).")
    ap.add_argument("--csv", nargs="+", required=True, help="Raw recursion CSV(s).")
    ap.add_argument("--out", required=True, help="Output path prefix (no extension).")
    ap.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS,
                    choices=list(METRICS.keys()), metavar="METRIC",
                    help=f"Time metrics to plot (default: {' '.join(DEFAULT_METRICS)}).")
    ap.add_argument("--k", type=int, nargs="+", default=None,
                    help="Restrict to these K values (default: all present).")
    ap.add_argument("--exp", type=int, default=2)
    ap.add_argument("--separate", action="store_true", help="One file per metric.")
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    data = load([Path(p) for p in args.csv], args.exp)
    if not data:
        print(f"No rows for exp={args.exp}.")
        return
    ks = sorted({k for (_n, k) in data} if not args.k else set(args.k) & {k for (_n, k) in data})
    print(f"exp={args.exp}; K values: {ks}")
    print_ratios(data, ks)

    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    show_title = not args.no_title

    def save(fig, suffix):
        path = out_prefix.parent / f"{out_prefix.name}{suffix}.{args.format}"
        fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved {path}")

    if args.separate:
        for metric in args.metrics:
            for scale, loglog in (("linear", False), ("loglog", True)):
                fig, ax = plt.subplots(1, 1, figsize=(6.4, 4.6))
                drew = draw(ax, data, metric, ks, loglog)
                if show_title:
                    fig.suptitle(f"Recursion: parallel vs total — {METRICS[metric][1]} ({scale})",
                                 fontsize=12, fontweight="bold")
                fig.tight_layout(rect=[0, 0, 1, 0.96] if show_title else None)
                save(fig, f"_{metric}_{scale}") if drew else plt.close(fig)
    else:
        for scale, loglog in (("linear", False), ("loglog", True)):
            n = len(args.metrics)
            ncols = min(2, n)
            nrows = math.ceil(n / ncols)
            fig, axes = plt.subplots(nrows, ncols, figsize=(6.2 * ncols, 4.5 * nrows),
                                     squeeze=False)
            if show_title:
                fig.suptitle(f"Recursion: parallel vs total ({scale})",
                             fontsize=13, fontweight="bold")
            flat_axes = list(axes.flat)
            for ax, metric in zip(flat_axes, args.metrics):
                if not draw(ax, data, metric, ks, loglog):
                    ax.set_visible(False)
            for ax in flat_axes[n:]:
                ax.set_visible(False)
            fig.tight_layout(rect=[0, 0, 1, 0.96] if show_title else None)
            save(fig, f"_{scale}")


if __name__ == "__main__":
    main()
