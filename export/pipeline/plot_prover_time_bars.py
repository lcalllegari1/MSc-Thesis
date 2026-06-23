"""
pipeline/plot_prover_time_bars.py -- prover wall-clock as stacked bars.

The per-proof prover wall-clock is **witness + prove** (two serial phases:
`nargo execute` then `bb prove`). At small N witness is a sliver (<1%); at
N=2000-3000 it grows to ~20-30% (see RECURSION_COMPARISON_NOTES.md S11), so this
plot makes it explicit. Even where it's tiny it is drawn, for consistency.

Layout: x-axis = N; at each N a **cluster** of bars for flat, K=2, K=4, K=8; each
bar is a **stack** of `prove` (solid, bottom) + `witness` (hatched, lighter, top).
Stacking is legitimate here -- the two phases are sequential, so they add to the
total prover wall-clock. Colour = variant (flat black, K-palette shared with the
other recursion plots); the hatched upper segment = witness in the same hue.

Input is the **aggregated** CSVs (flat baseline + recursion `aggregate_recursion`
output -- the `recursion_k{K}` combined rows carry `prove_s`/`witness_s` already
combined as innerstep+outer). The deployment (parallel = max-seg+outer / total =
sum-seg+outer) is whichever `--mode` you aggregated the recursion CSV with; pass
the matching one and label it via --title.

Usage:
    PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
    $PY pipeline/plot_prover_time_bars.py \\
        --csv results/flat.csv results/recursive_par.csv \\
        --out plots/prover_time_bars

    # single N (one cluster), vector, K in {2,4,8}:
    $PY pipeline/plot_prover_time_bars.py --csv results/flat.csv results/recursive_par.csv \\
        --out plots/prover_time_n1000 --n 1000 --format pdf --no-title
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot as P                                          # noqa: E402
from plot_recursion_lines import parse_variant, _color_for_k  # noqa: E402

FLAT_COLOR = "#111111"
METRICS = ["prove_s", "witness_s"]


def select_variants(raw, flat_variant, ks):
    """Ordered (variant, label, color): flat first, then recursion_k{K} combined rows."""
    out = []
    if flat_variant and flat_variant in raw:
        out.append((-1, flat_variant, "flat", FLAT_COLOR))
    for v in raw:
        if v.startswith("flat"):
            continue
        k, component, _mode = parse_variant(v)
        if k is None or component != "combined":
            continue
        if ks and k not in ks:
            continue
        out.append((k, v, ("1-seg" if k == 1 else f"K={k}"), _color_for_k(k) or "#374151"))
    out.sort(key=lambda t: t[0])
    return [(v, label, color) for _k, v, label, color in out]


def main():
    ap = argparse.ArgumentParser(description="Prover wall-clock (witness+prove) stacked bars.")
    ap.add_argument("--csv", nargs="+", required=True,
                    help="Aggregated CSVs: flat baseline + recursion (aggregate_recursion) output.")
    ap.add_argument("--out", required=True, help="Output path prefix (no extension).")
    ap.add_argument("--flat-variant", default="flat_merkle_sort")
    ap.add_argument("--k", type=int, nargs="+", default=None,
                    help="Recursion K values to include (default: all present).")
    ap.add_argument("--n", type=int, nargs="+", default=None,
                    help="Restrict to these N (default: all present across the chosen variants).")
    ap.add_argument("--min-n", type=int, default=None)
    ap.add_argument("--max-n", type=int, default=None)
    ap.add_argument("--format", default="png", choices=["png", "pdf", "svg"])
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--title", default="Prover wall-clock (witness + prove)")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    _order, raw = P.load_csv([Path(p) for p in args.csv], METRICS,
                             min_n=args.min_n, max_n=args.max_n)
    if not raw:
        print("No data after filtering.")
        return

    variants = select_variants(raw, args.flat_variant, args.k)
    if not variants:
        print("No variants selected.")
        return

    # per-variant per-N means
    summ = {v: P.summarise(raw[v], METRICS) for v, _, _ in variants}

    def val(v, n, metric):
        ns, means, _ = summ[v]
        if n in ns:
            x = means[metric][ns.index(n)]
            return 0.0 if (x != x) else x   # NaN -> 0
        return None

    # N axis = the RECURSION sweep points (the sparse, intentional set), so every
    # cluster is populated; flat (a denser superset) is clipped to match. Falls
    # back to all N if no recursion variant is selected. --n overrides.
    rec_ns = {n for v, _, _ in variants
              if parse_variant(v)[0] is not None for n in summ[v][0]}
    base = rec_ns or {n for v, _, _ in variants for n in summ[v][0]}
    nset = sorted(n for n in base if not args.n or n in args.n)
    if not nset:
        print("No N values to plot.")
        return

    x = np.arange(len(nset))
    nvar = len(variants)
    w = 0.8 / nvar

    fig, ax = plt.subplots(1, 1, figsize=(max(7.0, 1.4 * len(nset) + 2.5), 5.0))
    for i, (v, label, color) in enumerate(variants):
        prove = np.array([(val(v, n, "prove_s")   or 0.0) for n in nset])
        wit   = np.array([(val(v, n, "witness_s") or 0.0) for n in nset])
        offs = x + (i - (nvar - 1) / 2) * w
        ax.bar(offs, prove, w, color=color, edgecolor="white", linewidth=0.3, zorder=2)
        ax.bar(offs, wit, w, bottom=prove, facecolor=color, alpha=0.40,
               hatch="////", edgecolor=color, linewidth=0.4, zorder=2)

    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in nset])
    ax.set_xlabel("N (nodes)", fontsize=10)
    ax.set_ylabel("Time (s)", fontsize=10)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4, zorder=0)
    if not args.no_title:
        ax.set_title(args.title, fontsize=12, fontweight="bold")

    # legend: variant colours (= prove) + a component key for the hatched witness cap
    handles = [Patch(facecolor=color, label=label) for _v, label, color in variants]
    handles.append(Patch(facecolor="none", edgecolor="#555", hatch="////",
                         label="witness (hatched, on top)"))
    ax.legend(handles=handles, fontsize=8, framealpha=0.9, ncol=min(len(handles), 5),
              loc="upper left")

    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    path = out.parent / f"{out.name}.{args.format}"
    fig.savefig(path, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}  (variants={[l for _v,l,_c in variants]}, N={nset})")


if __name__ == "__main__":
    main()
