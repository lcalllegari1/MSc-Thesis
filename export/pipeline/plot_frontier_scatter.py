"""
pipeline/plot_frontier_scatter.py -- the cost-vs-cost frontier (C7).

The synthesis figure: at a fixed N, plot each variant as a POINT in a 2-D cost
space (one axis = a verifier cost, the other = a prover cost), so the family's
trade-off becomes a Pareto picture. This is where the "binding tax" is visible as
geometry: the tax lives on the verifier (hierarchical → right) or the prover
(recursion → up), flat sits where neither decomposition cost is paid.

Expected corners (default axes x=proof_bytes, y=peak_mb):
  * hierarchical (A/A++/committed) — high verifier (O(K) proofs/bytes), low prover
    memory (small parallel segments) → lower-right.
  * recursion — low verifier (O(1), one proof), high prover memory (the outer) →
    upper-left; the K=2/4/8 points trace a trajectory upward.
  * flat — low verifier, prover memory grows with N (so its y-position rises with
    N; at small N it dominates, at large N the decomposed variants overtake it).

Most informative with the **full family** present (flat + hier_* + recursion); for
just flat+recursion the verifier axis collapses (both O(1)), so pick axes that both
vary (e.g. --x prove_s --y peak_mb).

Input is **aggregated** CSVs (the combined `variant` rows: `monolithic_committed_sort`,
`recursion_k{K}`, `composite_plain_product_k{K}`, `composite_committed_product_k{K}`, ...). Colour = K (shared with
the other recursion plots; flat black); marker = family. Same-family points are
joined by a faint line (the K-trajectory). `--pareto` draws the non-dominated
lower-left front (assumes lower = better on both axes).

Usage:
    PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
    $PY pipeline/plot_frontier_scatter.py \\
        --csv results/flat.csv results/recursive_par.csv results/composite_plain_product_par.csv \\
        --n 96 --out plots/frontier_scatter --pareto

    # flat vs recursion only -> use two varying axes:
    $PY pipeline/plot_frontier_scatter.py --csv results/flat.csv results/recursive_par.csv \\
        --n 1000 --x prove_s --y peak_mb --out plots/frontier_rec
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot as P                                          # noqa: E402
from plot_composite_recursive_lines import parse_variant, _color_for_k  # noqa: E402

METRIC_LABELS = {
    "proof_bytes":  "Proof size (bytes)",
    "verify_s":     "Verify time (s)",
    "peak_mb":      "Peak memory (MiB)",
    "prove_s":      "Prove time (s)",
    "circuit_size": "Circuit size (gates)",
    "witness_s":    "Witness time (s)",
}
# family detection (longest prefixes first) -> (short label, marker)
FAMILY = [
    ("monolithic",                   "monolithic",        "o"),
    ("composite_recursive",          "recursive",         "^"),
    ("composite_committed_product",  "committed-product", "D"),
    ("composite_committed_sort",     "committed-sort",    "P"),
    ("composite_plain_product",      "plain-product",     "s"),
    ("composite_plain_sort",         "plain-sort",        "v"),
]


def family_of(variant):
    for prefix, label, marker in FAMILY:
        if variant.startswith(prefix):
            return label, marker
    return "?", "X"


def main():
    ap = argparse.ArgumentParser(description="Cost-vs-cost frontier scatter (fixed N).")
    ap.add_argument("--csv", nargs="+", required=True, help="Aggregated CSVs (combined rows).")
    ap.add_argument("--out", required=True, help="Output path prefix (no extension).")
    ap.add_argument("--n", type=int, default=None,
                    help="Fixed N (default: max N common to the recursion variants).")
    ap.add_argument("--flat-variant", default="monolithic_committed_sort",
                    help="Which flat variant to plot (default: monolithic_committed_sort).")
    ap.add_argument("--x", default="proof_bytes", choices=list(METRIC_LABELS), help="x-axis metric.")
    ap.add_argument("--y", default="peak_mb", choices=list(METRIC_LABELS), help="y-axis metric.")
    ap.add_argument("--loglog", dest="loglog", action="store_true", default=True)
    ap.add_argument("--linear", dest="loglog", action="store_false", help="Linear axes (default loglog).")
    ap.add_argument("--pareto", action="store_true", help="Draw the lower-left non-dominated front.")
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    metrics = [args.x, args.y]
    _order, raw = P.load_csv([Path(p) for p in args.csv], metrics)
    if not raw:
        print("No data after filtering.")
        return

    # keep combined variant rows (drop _seg / _outer / _glue components); for flat,
    # keep only the chosen baseline so the other flat_* variants don't clutter.
    variants = [v for v in raw
                if (v == args.flat_variant) or
                   (not v.startswith("monolithic") and parse_variant(v)[1] == "combined")]

    # choose N: default = max N present among recursion variants
    if args.n is not None:
        n = args.n
    else:
        rec_ns = [nn for v in variants if v.startswith("composite_recursive") for nn in raw[v]]
        n = max(rec_ns) if rec_ns else max(nn for v in variants for nn in raw[v])

    def val(v, metric):
        ns, means, _ = P.summarise(raw[v], metrics)
        if n in ns:
            x = means[metric][ns.index(n)]
            return None if x != x else x
        return None

    pts = []   # (variant, family, marker, k, x, y)
    for v in variants:
        xv, yv = val(v, args.x), val(v, args.y)
        if xv is None or yv is None:
            continue
        fam, marker = family_of(v)
        k, _comp, _mode = parse_variant(v)
        pts.append((v, fam, marker, k, xv, yv))
    if not pts:
        print(f"No variants have both {args.x} and {args.y} at N={n}.")
        return

    fig, ax = plt.subplots(1, 1, figsize=(7.2, 5.6))
    for _v, fam, marker, k, xv, yv in pts:
        color = _color_for_k(k) or "#111111"
        klab = "" if k is None else (" 1-seg" if k == 1 else f" K{k}")
        ax.scatter([xv], [yv], s=120, marker=marker, color=color,
                   edgecolor="white", linewidth=0.6, zorder=3)
        ax.annotate(f"{fam}{klab}", (xv, yv), textcoords="offset points",
                    xytext=(7, 5), fontsize=8, zorder=4)

    # faint trajectory per family across K (sorted by K)
    by_fam = {}
    for p in pts:
        by_fam.setdefault(p[1], []).append(p)
    for fam, group in by_fam.items():
        g = sorted([p for p in group if p[3] is not None], key=lambda p: p[3])
        if len(g) >= 2:
            ax.plot([p[4] for p in g], [p[5] for p in g],
                    color=_color_for_k(g[0][3]) or "#888", alpha=0.25, lw=1.2, zorder=1)

    if args.pareto:
        # non-dominated front (lower-left = better on both axes)
        srt = sorted(pts, key=lambda p: (p[4], p[5]))
        front, best_y = [], float("inf")
        for p in srt:
            if p[5] <= best_y:
                front.append(p)
                best_y = p[5]
        if len(front) >= 2:
            ax.plot([p[4] for p in front], [p[5] for p in front],
                    color="#444", ls="--", lw=1.3, alpha=0.7, zorder=2, label="Pareto front")

    if args.loglog:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.set_xlabel(METRIC_LABELS[args.x] + "  (verifier-side →)" if args.x in ("proof_bytes", "verify_s")
                  else METRIC_LABELS[args.x], fontsize=10)
    ax.set_ylabel(METRIC_LABELS[args.y] + "  (prover-side ↑)" if args.y in ("peak_mb", "prove_s", "circuit_size")
                  else METRIC_LABELS[args.y], fontsize=10)
    ax.grid(True, which="both", ls="--", alpha=0.35, zorder=0)
    if not args.no_title:
        ax.set_title(f"Cost frontier at N={n}: {METRIC_LABELS[args.x]} vs {METRIC_LABELS[args.y]}",
                     fontsize=11, fontweight="bold")

    # family-marker legend
    fams = {}
    for _v, fam, marker, _k, _x, _y in pts:
        fams[fam] = marker
    handles = [Line2D([0], [0], marker=m, color="#444", linestyle="", markersize=8, label=f)
               for f, m in fams.items()]
    if args.pareto:
        handles.append(Line2D([0], [0], color="#444", ls="--", label="Pareto front"))
    ax.legend(handles=handles, fontsize=8, framealpha=0.9, loc="best",
              title="family (colour = K)")

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    path = out.parent / f"{out.name}.{args.format}"
    fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    labels = [p[1] + ("" if p[3] is None else f"K{p[3]}") for p in pts]
    print(f"Saved {path}  (N={n}, points={labels})")


if __name__ == "__main__":
    main()
