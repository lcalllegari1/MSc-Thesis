"""
pipeline/make_frontier.py  --  One-shot: aggregate raw hierarchical CSVs and plot
the frontier in a single command.

Chains pipeline/aggregate_composite.py (K+1-rows-per-cell -> one row per (N,K)) and
pipeline/plot.py.  Raw hierarchical sweeps (composite_plain_sort / composite_plain_product / composite_committed_sort / composite_committed_product)
are passed via --aggregate and run through the aggregator in the chosen mode(s);
already-plot-ready CSVs (the flat baseline results/500.csv, recursion CSVs) are
passed via --include and forwarded as-is.  Every plotting knob of plot.py is
forwarded, so size windows / variant filters / separate-file / vector output all
work through this wrapper.

Each step's exact sub-command is echoed, so the chain is reproducible by hand.

Examples
--------
    # Equal-privacy frontier panel: flat + committed-A/A++ + recursion, parallel.
    python pipeline/make_frontier.py \\
        --aggregate results/composite_committed_sort.csv results/composite_committed_product.csv \\
        --include   results/500.csv results/recursion_full_tot.csv \\
        --out plots/frontier --mode parallel

    # Same data, windowed to N<=192, only the committed variants + flat, as PDFs
    # one-file-per-metric for the thesis:
    python pipeline/make_frontier.py \\
        --aggregate results/composite_committed_sort.csv results/composite_committed_product.csv \\
        --include   results/500.csv \\
        --out plots/frontier_small --mode parallel --max-n 192 \\
        --variants 'composite_committed_sort_k*' 'composite_committed_product_k*' monolithic_study_committed_presence \\
        --separate --format pdf --no-title \\
        --metrics circuit_size prove_s peak_mb proof_bytes

    # Both aggregation modes in one figure (variant names get _parallel/_total).
    python pipeline/make_frontier.py \\
        --aggregate results/composite_committed_sort.csv results/composite_committed_product.csv \\
        --include results/500.csv --out plots/frontier_both --mode both
"""

import argparse
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent
AGGREGATE = PIPELINE / "aggregate_composite.py"
PLOT      = PIPELINE / "plot.py"

# plot.py pass-through flags this wrapper forwards verbatim.
PASSTHROUGH_VALUE = ["--min-n", "--max-n", "--format", "--legend", "--title", "--dpi"]
PASSTHROUGH_LIST  = ["--variants", "--metrics"]
PASSTHROUGH_FLAG  = ["--separate", "--no-title"]


def run(cmd):
    """Echo and run a sub-command; abort on failure."""
    print("  $ " + " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"step failed (exit {r.returncode}): {' '.join(map(str, cmd))}")


def main():
    ap = argparse.ArgumentParser(
        description="Aggregate raw hierarchical CSVs and plot the frontier in one step.")
    ap.add_argument("--aggregate", nargs="*", default=[], type=Path,
                    help="Raw hierarchical CSVs (K+1 rows/cell) to run through aggregate_composite.py")
    ap.add_argument("--include", nargs="*", default=[], type=Path,
                    help="Already-plot-ready CSVs to include as-is (flat baseline, recursion)")
    ap.add_argument("--out", required=True, help="Output path prefix for plot.py (no extension)")
    ap.add_argument("--mode", choices=["parallel", "total", "both"], default="parallel",
                    help="Aggregation mode for prove_s/witness_s (default: parallel)")
    ap.add_argument("--work-dir", type=Path, default=None,
                    help="Where to write intermediate aggregated CSVs (default: <out dir>/_agg)")
    # plot.py pass-through
    ap.add_argument("--min-n", type=int)
    ap.add_argument("--max-n", type=int)
    ap.add_argument("--variants", nargs="+")
    ap.add_argument("--metrics", nargs="+")
    ap.add_argument("--separate", action="store_true")
    ap.add_argument("--format", choices=["png", "pdf", "svg"])
    ap.add_argument("--legend", choices=["outside", "inside", "none"])
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument("--title")
    ap.add_argument("--dpi", type=int)
    args = ap.parse_args()

    if not args.aggregate and not args.include:
        sys.exit("nothing to plot: pass --aggregate and/or --include CSVs")

    out_prefix = Path(args.out)
    work_dir = args.work_dir or (out_prefix.parent / "_agg")
    work_dir.mkdir(parents=True, exist_ok=True)

    modes = ["parallel", "total"] if args.mode == "both" else [args.mode]
    mode_in_name = args.mode == "both"

    # ── Step 1: aggregate each raw hierarchical CSV in each requested mode ──
    plot_csvs = []
    print("[1/2] aggregating raw hierarchical CSVs ...")
    for raw in args.aggregate:
        if not raw.exists():
            sys.exit(f"--aggregate file not found: {raw}")
        for mode in modes:
            out_csv = work_dir / f"{raw.stem}_{mode}.csv"
            cmd = [sys.executable, str(AGGREGATE),
                   "--in", str(raw), "--out", str(out_csv), "--mode", mode]
            if mode_in_name:
                cmd.append("--mode-in-name")
            run(cmd)
            plot_csvs.append(out_csv)

    # Already-plot-ready CSVs go straight in.
    for inc in args.include:
        if not inc.exists():
            sys.exit(f"--include file not found: {inc}")
        plot_csvs.append(inc)

    # ── Step 2: plot ──
    print("[2/2] plotting ...")
    cmd = [sys.executable, str(PLOT), "--csv", *map(str, plot_csvs), "--out", str(out_prefix)]
    # Forward plot.py options that were set.
    for flag in PASSTHROUGH_VALUE:
        val = getattr(args, flag.lstrip("-").replace("-", "_"))
        if val is not None:
            cmd += [flag, str(val)]
    for flag in PASSTHROUGH_LIST:
        val = getattr(args, flag.lstrip("-").replace("-", "_"))
        if val:
            cmd += [flag, *map(str, val)]
    for flag in PASSTHROUGH_FLAG:
        if getattr(args, flag.lstrip("-").replace("-", "_")):
            cmd.append(flag)
    run(cmd)
    print("Done.")


if __name__ == "__main__":
    main()
