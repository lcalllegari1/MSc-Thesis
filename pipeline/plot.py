"""
pipeline/plot.py  --  Plot benchmarking results from a CSV produced by run.py.

Reads the CSV, groups rows by (variant, N), computes mean ± std across runs,
and produces a 2×3 subplot figure — one panel per metric, one line per variant.

Two versions are saved: linear scale and log-log scale.

Usage:
    # Single variant (one line):
    python pipeline/plot.py \\
        --csv  results/flat_full_pairwise.csv \\
        --out  plots/flat_full_pairwise

    # Multiple variants in one CSV (one line per variant, distinguished by
    # the 'variant' column written by run.py):
    python pipeline/plot.py \\
        --csv  results/comparison.csv \\
        --out  plots/comparison

    # Produces:
    #   <out>_linear.png   — linear axes, error bars show std across runs
    #   <out>_loglog.png   — log-log axes with per-variant slope annotations

Options:
    --csv   Path to the CSV output from pipeline/run.py  (required)
    --out   Output path prefix, without extension         (required)
    --title Figure suptitle; defaults to the CSV filename stem
    --dpi   Output image DPI (default: 150)
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from matplotlib.lines import Line2D

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Metrics to plot, in subplot order (row-major, 2 rows × 3 cols) ───────────
# Each entry: (csv_column, y-axis label, subplot title)
PANELS = [
    ("circuit_size", "UltraHonk gates", "Circuit size (gates)"),
    ("prove_s",      "Time (s)",        "Prove time"),
    ("verify_s",     "Time (s)",        "Verify time"),
    ("proof_bytes",  "Bytes",           "Proof size"),
    ("peak_mb",      "Memory (MiB)",    "Peak memory (prove)"),
    ("compile_s",    "Time (s)",        "Compile time"),
]

# ── Per-variant visual styles (cycles if more variants than entries) ──────────
STYLES = [
    {"color": "#1d4ed8", "marker": "o", "ecolor": "#93c5fd"},  # blue
    {"color": "#b45309", "marker": "s", "ecolor": "#fcd34d"},  # amber
    {"color": "#047857", "marker": "^", "ecolor": "#6ee7b7"},  # green
    {"color": "#7c3aed", "marker": "D", "ecolor": "#c4b5fd"},  # purple
    {"color": "#be185d", "marker": "v", "ecolor": "#f9a8d4"},  # pink
]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_csv(path):
    """
    Read the benchmark CSV and return:
        { variant: { n: { metric: [value, ...] } } }
    Variants are discovered from the 'variant' column; order of first appearance
    is preserved so the plot legend matches the order data was collected.
    """
    data = {}          # variant -> n -> metric -> [values]
    order = []         # insertion order of variants

    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            variant = row["variant"]
            n = int(row["n"])

            if variant not in data:
                data[variant] = defaultdict(lambda: defaultdict(list))
                order.append(variant)

            for col, _, _ in PANELS:
                val = row.get(col, "")
                if val not in ("", "nan"):
                    data[variant][n][col].append(float(val))

    return order, data


def summarise(variant_data):
    """
    Convert raw lists to (mean, std) per (n, metric) for one variant.
    Returns (ns, means_dict, stds_dict).
    """
    ns = sorted(variant_data.keys())
    means = {col: [] for col, _, _ in PANELS}
    stds  = {col: [] for col, _, _ in PANELS}

    for n in ns:
        for col, _, _ in PANELS:
            vals = variant_data[n][col]
            if vals:
                means[col].append(float(np.mean(vals)))
                stds[col].append(float(np.std(vals, ddof=0)))
            else:
                means[col].append(float("nan"))
                stds[col].append(float("nan"))

    return ns, means, stds


# ── Plotting ──────────────────────────────────────────────────────────────────

def make_figure(variant_summaries, title, loglog=False):
    """
    Build and return a 2×3 matplotlib figure with one line per variant.

    variant_summaries : list of (variant_name, ns, means, stds)
    loglog            : if True, both axes are log-scaled and per-variant
                        empirical slopes are annotated in each panel.
    """
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    for ax, (col, ylabel, panel_title) in zip(axes.flat, PANELS):
        has_data = False

        for var_idx, (variant, ns, means, stds) in enumerate(variant_summaries):
            style  = STYLES[var_idx % len(STYLES)]
            ns_arr = np.array(ns, dtype=float)
            ys     = np.array(means[col], dtype=float)
            err    = np.array(stds[col],  dtype=float)

            mask = ~np.isnan(ys)
            x, y, e = ns_arr[mask], ys[mask], err[mask]

            if len(x) == 0:
                continue

            ax.errorbar(
                x, y,
                yerr=e,
                fmt=f"{style['marker']}-",
                capsize=4,
                linewidth=1.6,
                markersize=5,
                color=style["color"],
                ecolor=style["ecolor"],
                elinewidth=1.2,
            )
            has_data = True

            if loglog and np.all(x > 0) and np.all(y > 0):
                ax.set_xscale("log")
                ax.set_yscale("log")
                if len(x) >= 2:
                    slope = np.polyfit(np.log(x), np.log(y), 1)[0]
                    # Stack slope labels bottom-to-top, one per variant.
                    ax.text(
                        0.97, 0.04 + var_idx * 0.11,
                        f"slope ≈ {slope:.2f}",
                        transform=ax.transAxes,
                        ha="right", va="bottom",
                        fontsize=7.5, color=style["color"],
                        bbox=dict(
                            boxstyle="round,pad=0.2",
                            facecolor="white", alpha=0.75, edgecolor="none",
                        ),
                    )
            else:
                ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

        if not has_data:
            ax.set_visible(False)
            continue

        ax.set_title(panel_title, fontsize=10, fontweight="bold")
        ax.set_xlabel("N (nodes)", fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(True, linestyle="--", alpha=0.4)

    # Single figure-level legend at the bottom, one entry per variant.
    legend_handles = [
        Line2D(
            [0], [0],
            color=STYLES[i % len(STYLES)]["color"],
            marker=STYLES[i % len(STYLES)]["marker"],
            linewidth=1.6, markersize=5,
            label=variant,
        )
        for i, (variant, _, _, _) in enumerate(variant_summaries)
    ]
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=len(legend_handles),
        fontsize=9,
        framealpha=0.9,
        bbox_to_anchor=(0.5, -0.03),
    )

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    return fig


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plot ZKP benchmark results.")
    parser.add_argument("--csv",   required=True, help="CSV from pipeline/run.py")
    parser.add_argument("--out",   required=True, help="Output path prefix (no extension)")
    parser.add_argument("--title", default=None,  help="Figure title (default: CSV stem)")
    parser.add_argument("--dpi",   type=int, default=150, help="Output DPI (default: 150)")
    args = parser.parse_args()

    csv_path   = Path(args.csv)
    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    title = args.title or csv_path.stem.replace("_", " ")

    variant_order, raw = load_csv(csv_path)
    if not raw:
        print(f"No data found in {csv_path}")
        return

    variant_summaries = [
        (v, *summarise(raw[v]))
        for v in variant_order
    ]

    total_rows = sum(
        len(vals)
        for vdata in raw.values()
        for ndata in vdata.values()
        for vals in ndata.values()
        if vals
    )
    ns_all = sorted({n for vdata in raw.values() for n in vdata})
    print(f"Variants : {variant_order}")
    print(f"N values : {ns_all}")
    print(f"Data rows: {total_rows // len(PANELS)}")

    # Linear plot
    fig_lin = make_figure(
        variant_summaries,
        title=f"{title} — linear",
        loglog=False,
    )
    out_lin = out_prefix.parent / (out_prefix.name + "_linear.png")
    fig_lin.savefig(out_lin, dpi=args.dpi, bbox_inches="tight")
    print(f"Saved {out_lin}")

    # Log-log plot
    fig_log = make_figure(
        variant_summaries,
        title=f"{title} — log-log",
        loglog=True,
    )
    out_log = out_prefix.parent / (out_prefix.name + "_loglog.png")
    fig_log.savefig(out_log, dpi=args.dpi, bbox_inches="tight")
    print(f"Saved {out_log}")


if __name__ == "__main__":
    main()
