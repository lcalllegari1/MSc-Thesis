"""
pipeline/plot.py  --  Plot benchmarking results from a CSV produced by run.py
(or pipeline/aggregate_hier.py / aggregate_recursion.py).

Reads one or more CSVs, groups rows by (variant, N), computes mean +/- std across
runs, and produces a metric-per-panel figure -- one line per variant.  By default
all selected metrics are drawn in a single adaptive grid; --separate writes each
panel to its own file.  Two scales are always produced: linear and log-log.

Usage:
    # Single variant (one line):
    python pipeline/plot.py --csv results/flat_full_pairwise.csv \\
                            --out plots/flat_full_pairwise

    # Several CSVs merged (flat baseline + aggregated hierarchical runs):
    python pipeline/plot.py --csv results/500.csv results/hier_a_parallel.csv \\
                            --out plots/flat_vs_hier_a

    # Restrict the plotted size range (use a big CSV, plot only up to N=192):
    python pipeline/plot.py --csv results/all.csv --out plots/small --max-n 192

    # Only some variants (exact names or fnmatch globs):
    python pipeline/plot.py --csv results/all.csv --out plots/committed \\
                            --variants 'hier_c_k*' 'hier_cfs_k*' flat_merkle_presence

    # One file per metric (thesis figures), as vector PDFs without a suptitle:
    python pipeline/plot.py --csv results/all.csv --out plots/frontier \\
                            --separate --format pdf --no-title \\
                            --metrics circuit_size prove_s peak_mb proof_bytes

Outputs:
    grid (default):   <out>_linear.<fmt>            <out>_loglog.<fmt>
    --separate:       <out>_<metric>_linear.<fmt>   <out>_<metric>_loglog.<fmt>

Options:
    --csv       One or more CSV files (concatenated; 'variant' column = line).  [required]
    --out       Output path prefix, without extension.                          [required]
    --metrics   Which metrics to plot (default: ALL EIGHT — circuit_size
                acir_opcodes prove_s witness_s verify_s proof_bytes peak_mb
                compile_s).  Pass a subset to focus a figure.
    --variants  Variant names or fnmatch globs to include (default: all).
    --min-n     Drop rows with N below this value.
    --max-n     Drop rows with N above this value (adaptively window a big CSV).
    --separate  Write one file per metric instead of a single grid.
    --format    Output image format: png (default), pdf, or svg (pdf/svg = vector).
    --legend    Legend placement: outside (default, shared below), inside
                (on a panel), or none.
    --no-title  Omit the figure suptitle (use the LaTeX caption instead).
    --title     Figure suptitle; defaults to the first CSV's filename stem.
    --dpi       Raster DPI for png (default: 150; ignored for vector formats).

Per-variant colours/markers are STABLE across figures (keyed by variant name), so
a variant looks the same in every plot regardless of which others are shown.  To
curate the final thesis figures, edit two module-level dicts near the top:
  STYLE_OVERRIDES  -- pin a variant to a colour slot, e.g. {"recursion_k4": 6}
  DISPLAY_NAMES    -- relabel a variant in legends, e.g. {"hier_cfs_k4": "committed-A++ (K=4)"}
Both are empty (identity) by default.
"""

import argparse
import csv
import fnmatch
import hashlib
import math
from collections import defaultdict
from pathlib import Path
from matplotlib.lines import Line2D

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.colors as mcolors

# ── Metric registry: csv_column -> (y-axis label, panel title) ───────────────
# Selectable via --metrics; DEFAULT_METRICS preserves the historical 2x3 grid.
METRICS = {
    "circuit_size": ("UltraHonk gates", "Circuit size (gates)"),
    "acir_opcodes": ("ACIR opcodes",    "ACIR opcodes (pre-arithmetization)"),
    "compile_s":    ("Time (s)",        "Compile time"),
    "witness_s":    ("Time (s)",        "Witness-generation time"),
    "prove_s":      ("Time (s)",        "Prove time"),
    "verify_s":     ("Time (s)",        "Verify time"),
    "proof_bytes":  ("Bytes",           "Proof size"),
    "peak_mb":      ("Memory (MiB)",    "Peak memory (prove)"),
}
# Default grid shows all eight metrics (3x3, one cell left blank).
DEFAULT_METRICS = ["circuit_size", "acir_opcodes", "prove_s", "witness_s",
                   "verify_s", "proof_bytes", "peak_mb", "compile_s"]

# ── Per-variant visual style generation ──────────────────────────────────────
# Styles are assigned by a STABLE key derived from the variant *name*, so a given
# variant keeps the same colour/marker/linestyle across every figure, regardless
# of which other variants are present (otherwise an index-based scheme would
# recolour a variant whenever the plotted subset changes).
_COLORS = [
    "#1d4ed8", "#b45309", "#047857", "#7c3aed", "#be185d", "#0e7490",
    "#b91c1c", "#4d7c0f", "#c2410c", "#1e40af", "#6d28d9", "#0f766e",
]
_MARKERS    = ["o", "s", "^", "D", "v", "p", "P", "X", "*", "h"]
_LINESTYLES = ["-", "--", "-.", ":"]

# ── Customisation hooks (edit these for the final thesis figures) ─────────────
# Pin a variant to a specific colour slot (int index into _COLORS) so curated
# figures use intended colours; the marker/linestyle are then taken from the same
# slot deterministically.  Empty => everything is auto-styled by the stable name
# hash below.  For the thesis, pin the families you compare so colours never clash,
# e.g.:
#   STYLE_OVERRIDES = {
#       "flat_merkle_presence": 0, "hier_a_k4": 2, "hier_fs_k4": 3,
#       "hier_c_k4": 4, "hier_cfs_k4": 5, "recursion_k4": 6,
#   }
STYLE_OVERRIDES: dict[str, int] = {}

# Map raw variant names (as they appear in the CSV 'variant' column) to the label
# shown in legends.  Identity for now (legend shows the raw name); fill in for the
# thesis, e.g. {"hier_cfs_k4": "committed-A++ (K=4)"}.
DISPLAY_NAMES: dict[str, str] = {}


def _style_for_index(idx: int) -> dict:
    color  = _COLORS[idx % len(_COLORS)]
    marker = _MARKERS[idx % len(_MARKERS)]
    ls     = _LINESTYLES[(idx // len(_COLORS)) % len(_LINESTYLES)]
    rgb    = mcolors.to_rgb(color)
    ecolor = mcolors.to_hex(tuple(c * 0.5 + 0.5 for c in rgb))
    return {"color": color, "marker": marker, "ls": ls, "ecolor": ecolor}


def _stable_style(variant: str) -> dict:
    """Deterministic style for a variant name (subset-independent).

    Uncurated names are hashed into colour / marker / linestyle from INDEPENDENT
    slices of the digest, so an accidental colour clash between two variants still
    leaves them distinguishable by marker and linestyle (the index-based scheme
    used for STYLE_OVERRIDES correlates the three, which is fine for pinned slots).
    """
    if variant in STYLE_OVERRIDES:
        return _style_for_index(STYLE_OVERRIDES[variant])
    h = int(hashlib.md5(variant.encode()).hexdigest(), 16)
    color  = _COLORS[h % len(_COLORS)]
    marker = _MARKERS[(h // 101) % len(_MARKERS)]
    ls     = _LINESTYLES[(h // 10007) % len(_LINESTYLES)]
    rgb    = mcolors.to_rgb(color)
    ecolor = mcolors.to_hex(tuple(c * 0.5 + 0.5 for c in rgb))
    return {"color": color, "marker": marker, "ls": ls, "ecolor": ecolor}


def _display(variant: str) -> str:
    return DISPLAY_NAMES.get(variant, variant)


# ── Data loading ──────────────────────────────────────────────────────────────

def _variant_selected(variant, patterns):
    """True if variant matches any fnmatch pattern (None/[] => all)."""
    if not patterns:
        return True
    return any(fnmatch.fnmatch(variant, pat) for pat in patterns)


def load_csv(paths, metrics, variant_patterns=None, min_n=None, max_n=None):
    """
    Read benchmark CSVs and return (variant_order, {variant: {n: {metric: [vals]}}}).
    Filters by variant pattern and N range as it reads.
    """
    if isinstance(paths, (str, Path)):
        paths = [paths]

    data, order = {}, []
    for path in paths:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                variant = row["variant"]
                if not _variant_selected(variant, variant_patterns):
                    continue
                n = int(row["n"])
                if min_n is not None and n < min_n:
                    continue
                if max_n is not None and n > max_n:
                    continue

                if variant not in data:
                    data[variant] = defaultdict(lambda: defaultdict(list))
                    order.append(variant)

                for col in metrics:
                    val = row.get(col, "")
                    if val not in ("", "nan"):
                        data[variant][n][col].append(float(val))

    return order, data


def summarise(variant_data, metrics):
    """Convert raw lists to (ns, means, stds) per (n, metric) for one variant."""
    ns = sorted(variant_data.keys())
    means = {col: [] for col in metrics}
    stds  = {col: [] for col in metrics}
    for n in ns:
        for col in metrics:
            vals = variant_data[n][col]
            if vals:
                means[col].append(float(np.mean(vals)))
                stds[col].append(float(np.std(vals, ddof=0)))
            else:
                means[col].append(float("nan"))
                stds[col].append(float("nan"))
    return ns, means, stds


# ── Plotting ──────────────────────────────────────────────────────────────────

def _draw_panel(ax, col, summaries, loglog):
    """Draw one metric panel onto ax.  Returns True if any data was plotted."""
    ylabel, panel_title = METRICS[col]
    has_data = False

    for var_idx, (variant, ns, means, stds) in enumerate(summaries):
        style  = _stable_style(variant)
        ns_arr = np.array(ns, dtype=float)
        ys     = np.array(means[col], dtype=float)
        err    = np.array(stds[col],  dtype=float)

        mask = ~np.isnan(ys)
        x, y, e = ns_arr[mask], ys[mask], err[mask]
        if len(x) == 0:
            continue

        ax.errorbar(
            x, y, yerr=e,
            fmt=f"{style['marker']}{style['ls']}",
            capsize=4, linewidth=1.6, markersize=5,
            color=style["color"], ecolor=style["ecolor"], elinewidth=1.2,
        )
        has_data = True

        if loglog and np.all(x > 0) and np.all(y > 0):
            ax.set_xscale("log")
            ax.set_yscale("log")
            if len(x) >= 2:
                slope = np.polyfit(np.log(x), np.log(y), 1)[0]
                ax.text(
                    0.97, 0.04 + (var_idx % 8) * 0.11,
                    f"slope ~ {slope:.2f}",
                    transform=ax.transAxes, ha="right", va="bottom",
                    fontsize=7.5, color=style["color"],
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor="white", alpha=0.75, edgecolor="none"),
                )
        else:
            ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    if has_data:
        ax.set_title(panel_title, fontsize=10, fontweight="bold")
        ax.set_xlabel("N (nodes)", fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.tick_params(labelsize=8)
        ax.grid(True, linestyle="--", alpha=0.4)
    return has_data


def _legend_handles(summaries):
    return [
        Line2D([0], [0],
               color=_stable_style(variant)["color"],
               marker=_stable_style(variant)["marker"],
               linestyle=_stable_style(variant)["ls"], linewidth=1.6, markersize=5,
               label=_display(variant))
        for (variant, _, _, _) in summaries
    ]


def make_grid_figure(summaries, metrics, title, loglog=False, show_title=True,
                     legend="outside"):
    """One adaptive grid (<=3 cols) with all metrics; one shared legend.

    legend: 'outside' (figure-level, below the grid), 'inside' (on the first
    populated panel), or 'none'.
    """
    n = len(metrics)
    ncols = min(3, n)
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.7 * ncols, 4.0 * nrows),
                             squeeze=False)
    if show_title:
        fig.suptitle(title, fontsize=14, fontweight="bold")

    flat_axes = list(axes.flat)
    first_populated = None
    for ax, col in zip(flat_axes, metrics):
        if _draw_panel(ax, col, summaries, loglog):
            if first_populated is None:
                first_populated = ax
        else:
            ax.set_visible(False)
    for ax in flat_axes[n:]:                 # hide unused cells
        ax.set_visible(False)

    handles = _legend_handles(summaries)
    if legend == "outside":
        fig.legend(handles=handles, loc="lower center",
                   ncol=min(len(summaries), 6), fontsize=9, framealpha=0.9,
                   bbox_to_anchor=(0.5, -0.03))
        fig.tight_layout(rect=[0, 0.05, 1, 1])
    elif legend == "inside" and first_populated is not None:
        first_populated.legend(handles=handles, loc="best", fontsize=8, framealpha=0.9)
        fig.tight_layout()
    else:  # "none"
        fig.tight_layout()
    return fig


def make_panel_figure(summaries, col, title, loglog=False, show_title=True,
                      legend="outside"):
    """A single metric in its own figure (for --separate / thesis figures)."""
    fig, ax = plt.subplots(1, 1, figsize=(6.0, 4.5))
    drew = _draw_panel(ax, col, summaries, loglog)
    if show_title:
        fig.suptitle(title, fontsize=12, fontweight="bold")
    handles = _legend_handles(summaries)
    if not drew or legend == "none":
        fig.tight_layout(rect=[0, 0, 1, 0.97] if show_title else None)
    elif legend == "inside":
        ax.legend(handles=handles, loc="best", fontsize=8, framealpha=0.9)
        fig.tight_layout(rect=[0, 0, 1, 0.97] if show_title else None)
    else:  # "outside" -> below the panel
        fig.legend(handles=handles, loc="lower center", ncol=min(len(summaries), 4),
                   fontsize=8, framealpha=0.9, bbox_to_anchor=(0.5, -0.02))
        fig.tight_layout(rect=[0, 0.08, 1, 0.97 if show_title else 1])
    return fig, drew


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plot ZKP benchmark results.")
    parser.add_argument("--csv", nargs="+", required=True,
                        help="One or more CSV files (run.py / aggregate_*.py)")
    parser.add_argument("--out", required=True, help="Output path prefix (no extension)")
    parser.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS,
                        choices=list(METRICS.keys()), metavar="METRIC",
                        help="Metrics to plot (default: the standard 6-panel set)")
    parser.add_argument("--variants", nargs="+", default=None, metavar="PATTERN",
                        help="Variant names or fnmatch globs to include (default: all)")
    parser.add_argument("--min-n", type=int, default=None, help="Drop N below this")
    parser.add_argument("--max-n", type=int, default=None, help="Drop N above this")
    parser.add_argument("--separate", action="store_true",
                        help="One file per metric instead of a single grid")
    parser.add_argument("--format", default="png", choices=["png", "pdf", "svg"],
                        help="Output format (pdf/svg = vector; default png)")
    parser.add_argument("--legend", choices=["outside", "inside", "none"],
                        default="outside",
                        help="Legend placement: outside (shared, below), inside "
                             "(on a panel), or none (default: outside)")
    parser.add_argument("--no-title", action="store_true",
                        help="Omit the figure suptitle (use the LaTeX caption)")
    parser.add_argument("--title", default=None, help="Figure title (default: first CSV stem)")
    parser.add_argument("--dpi", type=int, default=150, help="Raster DPI for png (default: 150)")
    args = parser.parse_args()

    csv_paths  = [Path(p) for p in args.csv]
    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    fmt        = args.format
    show_title = not args.no_title
    title_base = args.title or csv_paths[0].stem.replace("_", " ")

    variant_order, raw = load_csv(
        csv_paths, args.metrics,
        variant_patterns=args.variants, min_n=args.min_n, max_n=args.max_n,
    )
    if not raw:
        print("No data after filtering "
              f"(variants={args.variants}, min_n={args.min_n}, max_n={args.max_n}).")
        return

    summaries = [(v, *summarise(raw[v], args.metrics)) for v in variant_order]
    ns_all = sorted({n for vdata in raw.values() for n in vdata})
    print(f"Variants : {variant_order}")
    print(f"N values : {ns_all}")
    print(f"Metrics  : {args.metrics}")

    def save(fig, suffix):
        path = out_prefix.parent / f"{out_prefix.name}{suffix}.{fmt}"
        fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved {path}")

    if args.separate:
        for col in args.metrics:
            for scale, loglog in (("linear", False), ("loglog", True)):
                fig, drew = make_panel_figure(
                    summaries, col, f"{title_base} -- {METRICS[col][1]} ({scale})",
                    loglog=loglog, show_title=show_title, legend=args.legend)
                if drew:
                    save(fig, f"_{col}_{scale}")
                else:
                    plt.close(fig)
    else:
        for scale, loglog in (("linear", False), ("loglog", True)):
            fig = make_grid_figure(
                summaries, args.metrics, f"{title_base} -- {scale}",
                loglog=loglog, show_title=show_title, legend=args.legend)
            save(fig, f"_{scale}")


if __name__ == "__main__":
    main()
