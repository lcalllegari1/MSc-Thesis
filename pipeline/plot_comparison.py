"""
pipeline/plot_comparison.py -- the full flat-vs-recursion comparison figure.

Flat and recursion sit at the SAME privacy point (perfect hiding, public surface
(root, threshold)) and the SAME verifier surface (one proof).  So this is a
cost / parallelism / memory comparison of two routes to the same statement:
the monolithic prover (flat) vs decompose-into-K-segments-then-recursively-
aggregate (recursion).  This script draws the metric-vs-N panels for that
comparison -- as a grid for inspection, or one file per metric (--separate) for
thesis figures.

CURATED SERIES PER METRIC.  The valuable comparison shows a *different* set of
series on each panel (see HIER_MEASUREMENT_AND_PLOTS.md and the C1-C6 taxonomy):

  metric        | series drawn (per K for recursion)        | the point
  --------------|-------------------------------------------|------------------------
  circuit_size  | flat + aggregate + outer                  | aggregate = flat + ~const outer tax
  prove_s       | flat + aggregate                          | wall-clock (parallel: max-seg+outer)
  peak_mb       | flat + single-seg + outer                 | THE win: per-leaf vs constant outer ceiling vs flat (crossover)
  verify_s      | flat + outer                              | tie (both O(1))
  proof_bytes   | flat + outer                              | tie (both constant)
  acir/witness/compile | flat + aggregate                   | secondary

  ("aggregate" = the recursion_k{K} combined row = segments + outer; "single-seg"
  = the recursion_k{K}_seg per-node row; "outer" = recursion_k{K}_outer.)

DEPLOYMENT.  Time metrics use the PARALLEL / distributed projection (max-segment
+ outer): pass a recursion CSV aggregated with --mode parallel.  Memory and gates
are deployment-independent here (peak is per-process, gates are structural).

INPUT (aggregated CSVs, run.py schema):
  * the flat baseline CSV (e.g. results/flat.csv), and
  * recursion CSV(s) aggregated with `--split-components` (e.g. results/recursive_par.csv),
    which carry the recursion_k{K}, _seg and _outer variant rows.
Pass them all to --csv (they are concatenated, like plot.py).

PALETTE.  Colour keyed by K (so flat sits apart in black, and a K's series share a
hue); marker/linestyle keyed by component (aggregate o-solid, seg s-dashed, outer
^-dotted) -- the same scheme as plot_recursion_lines.py.

Usage:
    PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
    # grid for inspection:
    $PY pipeline/plot_comparison.py \\
        --csv results/flat.csv results/recursive_par.csv \\
        --out plots/flat_vs_recursion

    # thesis figures (one vector file per metric, no suptitle):
    $PY pipeline/plot_comparison.py \\
        --csv results/flat.csv results/recursive_par.csv \\
        --out plots/flat_vs_recursion --separate --format pdf --no-title \\
        --metrics circuit_size prove_s peak_mb verify_s proof_bytes

    # restrict to K in {2,4}:
    $PY pipeline/plot_comparison.py --csv results/flat.csv results/recursive_par.csv \\
        --out plots/cmp_k24 --k 2 4
"""

import argparse
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# plot.py + the recursion palette live alongside; reuse their machinery.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot as P                                   # noqa: E402
from plot_recursion_lines import parse_variant, COMPONENT_STYLE, _color_for_k  # noqa: E402

# ── Curated series per metric ─────────────────────────────────────────────────
# role -> recursion component (parse_variant's component field)
ROLE_TO_COMPONENT = {"aggregate": "combined", "seg": "seg", "outer": "outer"}
METRIC_ROLES = {
    "circuit_size": ["aggregate", "outer"],
    "acir_opcodes": ["aggregate"],
    "compile_s":    ["aggregate"],
    "witness_s":    ["aggregate"],
    "prove_s":      ["aggregate"],
    "verify_s":     ["outer"],
    "proof_bytes":  ["outer"],
    "peak_mb":      ["seg", "outer"],
}
DEFAULT_METRICS = ["circuit_size", "prove_s", "peak_mb", "verify_s", "proof_bytes"]
_COMP_RANK = {"combined": 0, "seg": 1, "outer": 2, "glue": 3}


# ── Combined palette: flat in black, recursion keyed by K + component ──────────
def combined_style(variant: str) -> dict:
    if variant.startswith("flat"):
        return {"color": "#111111", "marker": "o", "ls": "-", "ecolor": "#9ca3af"}
    k, component, _mode = parse_variant(variant)
    color = _color_for_k(k)
    if color is None:                       # unknown variant -> plot.py's hash
        return P._orig_stable_style(variant)
    marker, ls = COMPONENT_STYLE.get(component, ("o", "-"))
    rgb    = mcolors.to_rgb(color)
    ecolor = mcolors.to_hex(tuple(c * 0.5 + 0.5 for c in rgb))
    return {"color": color, "marker": marker, "ls": ls, "ecolor": ecolor}


def combined_display(variant: str) -> str:
    if variant.startswith("flat"):
        return P.DISPLAY_NAMES.get(variant, "flat (" + variant.replace("flat_", "") + ")")
    k, component, mode = parse_variant(variant)
    if k is None:
        return P.DISPLAY_NAMES.get(variant, variant)
    head = "1-seg" if k == 1 else f"K={k}"
    label = head if component == "combined" else f"{head} {component}"
    if mode:
        label += f" ({mode})"
    return label


def select_variants(metric, all_variants, flat_variant, ks):
    """The curated series for one metric: flat first, then recursion by (K, component)."""
    comps = {ROLE_TO_COMPONENT[r] for r in METRIC_ROLES[metric]}
    chosen = []
    if flat_variant and flat_variant in all_variants:
        chosen.append((-1, -1, flat_variant))
    for v in all_variants:
        if v.startswith("flat"):
            continue
        k, component, _mode = parse_variant(v)
        if k is None or component not in comps:
            continue
        if ks and k not in ks:
            continue
        chosen.append((k, _COMP_RANK.get(component, 9), v))
    return [v for _, _, v in sorted(chosen)]


def _panel(ax, metric, summaries_m, loglog):
    """Draw one curated metric panel (reusing plot.py) with its own legend."""
    drew = P._draw_panel(ax, metric, summaries_m, loglog)
    if drew:
        handles = P._legend_handles(summaries_m)
        ax.legend(handles=handles, fontsize=7.5, framealpha=0.9, loc="best")
    return drew


def main():
    ap = argparse.ArgumentParser(description="Full flat-vs-recursion comparison figure.")
    ap.add_argument("--csv", nargs="+", required=True,
                    help="Aggregated CSVs: the flat baseline + recursion --split-components CSV(s).")
    ap.add_argument("--out", required=True, help="Output path prefix (no extension).")
    ap.add_argument("--metrics", nargs="+", default=DEFAULT_METRICS,
                    choices=list(METRIC_ROLES.keys()), metavar="METRIC",
                    help=f"Metrics to plot (default: {' '.join(DEFAULT_METRICS)}).")
    ap.add_argument("--flat-variant", default="flat_merkle_sort",
                    help="Which flat variant is the baseline line (default: flat_merkle_sort).")
    ap.add_argument("--k", type=int, nargs="+", default=None,
                    help="Restrict to these recursion K values (default: all present).")
    ap.add_argument("--match-n", action="store_true",
                    help="Clip the flat baseline to only the N values where recursion is "
                         "also defined (the recursion sweep is sparser), so the lines span "
                         "the same N.")
    ap.add_argument("--min-n", type=int, default=None)
    ap.add_argument("--max-n", type=int, default=None)
    ap.add_argument("--separate", action="store_true",
                    help="One file per metric (thesis figures) instead of a grid.")
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    ap.add_argument("--no-title", action="store_true", help="Omit the figure suptitle.")
    ap.add_argument("--title", default=None, help="Figure title (default: 'flat vs recursion').")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    # Patch plot.py's style + label hooks for the combined palette.
    P._orig_stable_style = P._stable_style
    P._stable_style = combined_style
    P._display = combined_display

    csv_paths = [Path(p) for p in args.csv]
    _order, raw = P.load_csv(csv_paths, args.metrics, min_n=args.min_n, max_n=args.max_n)
    if not raw:
        print("No data after filtering.")
        return

    all_variants = list(raw.keys())
    flat_variant = args.flat_variant
    if flat_variant not in raw:
        fallback = next((v for v in all_variants if v.startswith("flat")), None)
        print(f"[warn] flat baseline '{flat_variant}' not in data; "
              f"{'using ' + fallback if fallback else 'no flat line'}.")
        flat_variant = fallback

    # --match-n: clip the flat baseline to the N values the recursion sweep covers
    # (recursion uses a sparser N set), respecting any --k restriction.
    if args.match_n and flat_variant:
        rec_ns = {n for v in all_variants if parse_variant(v)[0] is not None
                  and (not args.k or parse_variant(v)[0] in args.k)
                  for n in raw[v]}
        raw[flat_variant] = {n: raw[flat_variant][n]
                             for n in raw[flat_variant] if n in rec_ns}
        print(f"--match-n: flat baseline clipped to N={sorted(rec_ns)}")

    # Pre-summarise every variant once (means/stds dicts over the chosen metrics).
    summ = {v: P.summarise(raw[v], args.metrics) for v in all_variants}

    def summaries_for(metric):
        return [(v, *summ[v]) for v in select_variants(metric, all_variants, flat_variant, args.k)]

    out_prefix = Path(args.out)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    show_title = not args.no_title
    title = args.title or "flat vs recursion"

    def save(fig, suffix):
        path = out_prefix.parent / f"{out_prefix.name}{suffix}.{args.format}"
        fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved {path}")

    ks_present = sorted({parse_variant(v)[0] for v in all_variants
                         if parse_variant(v)[0] not in (None,)})
    print(f"Flat baseline: {flat_variant}; recursion K present: {ks_present}; "
          f"metrics: {args.metrics}")

    if args.separate:
        for metric in args.metrics:
            sm = summaries_for(metric)
            for scale, loglog in (("linear", False), ("loglog", True)):
                fig, ax = plt.subplots(1, 1, figsize=(6.4, 4.6))
                drew = _panel(ax, metric, sm, loglog)
                if show_title:
                    fig.suptitle(f"{title} — {P.METRICS[metric][1]} ({scale})",
                                 fontsize=12, fontweight="bold")
                fig.tight_layout(rect=[0, 0, 1, 0.96] if show_title else None)
                if drew:
                    save(fig, f"_{metric}_{scale}")
                else:
                    plt.close(fig)
    else:
        for scale, loglog in (("linear", False), ("loglog", True)):
            n = len(args.metrics)
            ncols = min(3, n)
            nrows = math.ceil(n / ncols)
            fig, axes = plt.subplots(nrows, ncols, figsize=(4.9 * ncols, 4.1 * nrows),
                                     squeeze=False)
            if show_title:
                fig.suptitle(f"{title} — {scale}", fontsize=14, fontweight="bold")
            flat_axes = list(axes.flat)
            for ax, metric in zip(flat_axes, args.metrics):
                if not _panel(ax, metric, summaries_for(metric), loglog):
                    ax.set_visible(False)
            for ax in flat_axes[n:]:
                ax.set_visible(False)
            fig.tight_layout(rect=[0, 0, 1, 0.96] if show_title else None)
            save(fig, f"_{scale}")


if __name__ == "__main__":
    main()
