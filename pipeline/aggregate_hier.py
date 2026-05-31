"""
pipeline/aggregate_hier.py -- Convert raw hierarchical-benchmark CSV (K+1 rows
per cell) into a plot.py-compatible CSV (one row per (N, K, run)).

run_hier.py (Variant A) and run_hier_fs.py (Variant A++) both emit K+1 rows per
(N, K, run) cell -- one row per circuit: sub_0, sub_1, ..., sub_{K-1}, glue.
plot.py expects one row per (variant, N) data point with the standard run.py
schema, so this script aggregates the K+1 rows into a single per-(K) variant row.

Variant-aware: the output variant base is taken from the raw CSV's `variant`
column, so the SAME script handles every hierarchical variant with no flags:
  results/hier_a.csv    -> rows tagged  hier_a_k{K}     (Variant A)
  results/hier_fs.csv   -> rows tagged  hier_fs_k{K}    (Variant A++)
  results/hier_c.csv    -> rows tagged  hier_c_k{K}     (Variant committed-A)
  results/hier_cfs.csv  -> rows tagged  hier_cfs_k{K}   (Variant committed-A++)
(See "Variant naming" below.)

Aggregation rules
-----------------

  metric         | rule          | rationale
  ---------------|---------------|----------------------------------------------
  circuit_size   | K*sub + glue  | "total proving work in gates" for the cell
  acir_opcodes   | K*sub + glue  | same logic
  compile_s      | sub + glue    | one sub-circuit compile + one glue compile
                 |               | per cell (the K segment proofs reuse one
                 |               | compiled binary)
  witness_s      | max OR sum    | "parallel wall-clock" (max) vs "total CPU
                 |               |  work" (sum) -- selected via --mode
  prove_s        | max OR sum    | same
  verify_s       | sum + xcheck  | bb verify runs serially K+1 times; add the
                 |               |  off-circuit verify_hier_s for cross-checks
  proof_bytes    | sum           | the K+1 proofs delivered to the verifier
  peak_mb        | max           | peak across the K+1 parallel provers (= max
                 |               |  single-prover memory)

Modes
-----

  --mode parallel  (default) -- prove_s and witness_s use MAX, projecting the
                                ideal K+1-way parallel wall-clock under the
                                observed CPU contention.  Most directly
                                comparable with flat_*.prove_s.

  --mode total              -- prove_s and witness_s use SUM, giving total CPU
                                work spent proving.  Comparable with the
                                hypothetical "if you had to prove serially"
                                cost.

Variant naming
--------------

The output variant column is `{base}_k{K}` where `{base}` is read from the raw
CSV's `variant` column (`hier_a` or `hier_fs`) -- one variant per K value,
regardless of --mode, so a parallel and a total aggregation of the same input
share variant names.  Pass --mode-in-name to disambiguate as
`{base}_k{K}_{mode}` when both modes appear in the same combined CSV.

Schema written
--------------

Matches pipeline/run.py exactly:
  variant, n, run, circuit_size, acir_opcodes, compile_s,
  witness_s, prove_s, verify_s, proof_bytes, peak_mb

Usage
-----

  # Aggregate a hier run with parallel wall-clock projection.
  python pipeline/aggregate_hier.py \\
      --in  results/hier_a.csv \\
      --out results/hier_a_parallel.csv \\
      --mode parallel

  # Same data, total CPU work.
  python pipeline/aggregate_hier.py \\
      --in  results/hier_a.csv \\
      --out results/hier_a_total.csv \\
      --mode total

  # Plot side-by-side with the existing flat baseline.
  python pipeline/plot.py \\
      --csv results/500.csv results/hier_a_parallel.csv \\
      --out plots/flat_vs_hier_a
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path


OUTPUT_FIELDNAMES = [
    "variant", "n", "run",
    "circuit_size", "acir_opcodes",
    "compile_s", "witness_s", "prove_s", "verify_s",
    "proof_bytes", "peak_mb",
]


def aggregate(rows, mode, include_mode_in_name):
    """
    Group raw hier_a rows by (n, k, run); emit one aggregated dict per group.
    """
    grouped = defaultdict(list)
    for row in rows:
        n   = int(row["n"])
        k   = int(row["k"])
        run = int(row["run"])
        grouped[(n, k, run)].append(row)

    out = []
    for (n, k, run), group in sorted(grouped.items()):
        subs = [r for r in group if r["circuit"].startswith("sub_")]
        glue = next((r for r in group if r["circuit"] == "glue"), None)

        if len(subs) != k or glue is None:
            print(f"  [warn] N={n} K={k} run={run}: have {len(subs)} sub rows + "
                  f"glue={glue is not None}, expected {k} sub + 1 glue.  Skipping.")
            continue

        # Structural metrics (per-circuit constants; subs are identical).
        sub_size      = int(subs[0]["circuit_size"])
        sub_acir      = int(subs[0]["acir_opcodes"])
        sub_compile_s = float(subs[0]["compile_s"])
        glue_size      = int(glue["circuit_size"])
        glue_acir      = int(glue["acir_opcodes"])
        glue_compile_s = float(glue["compile_s"])

        # Runtime metrics (per-row observed values).
        all_rows = subs + [glue]
        witness_vals = [float(r["witness_s"]) for r in all_rows]
        prove_vals   = [float(r["prove_s"])   for r in all_rows]

        if mode == "parallel":
            witness_s = max(witness_vals)
            prove_s   = max(prove_vals)
        else:  # "total"
            witness_s = sum(witness_vals)
            prove_s   = sum(prove_vals)

        # bb verify is always serial; add the off-circuit cross-check time.
        verify_s = sum(float(r["verify_s"]) for r in all_rows)
        verify_hier_s = float(subs[0].get("verify_hier_s", "0") or "0")
        verify_s += verify_hier_s

        proof_bytes = sum(int(r["proof_bytes"]) for r in all_rows)
        peak_mb     = max(float(r["peak_mb"])   for r in all_rows)

        # Variant base comes from the raw CSV's `variant` column, so the same
        # aggregator serves Variant A (hier_a) and A++ (hier_fs) unchanged:
        # hier_a -> hier_a_k{K}, hier_fs -> hier_fs_k{K}.
        base = subs[0].get("variant", "hier_a") or "hier_a"
        variant = f"{base}_k{k}"
        if include_mode_in_name:
            variant += f"_{mode}"

        out.append({
            "variant":      variant,
            "n":            n,
            "run":          run,
            "circuit_size": k * sub_size + glue_size,
            "acir_opcodes": k * sub_acir + glue_acir,
            "compile_s":    round(sub_compile_s + glue_compile_s, 4),
            "witness_s":    round(witness_s, 4),
            "prove_s":      round(prove_s,   4),
            "verify_s":     round(verify_s,  4),
            "proof_bytes":  proof_bytes,
            "peak_mb":      round(peak_mb, 3),
        })

    return out


def main():
    ap = argparse.ArgumentParser(
        description="Aggregate raw hier_a CSV into a plot.py-compatible CSV."
    )
    ap.add_argument("--in", dest="inp", required=True, type=Path,
                    help="Input CSV from pipeline/run_hier.py")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output CSV path")
    ap.add_argument("--mode", choices=["parallel", "total"], default="parallel",
                    help="Aggregation mode for witness_s/prove_s (default: parallel)")
    ap.add_argument("--mode-in-name", action="store_true",
                    help="Append _<mode> to the variant column "
                         "(e.g. hier_a_k4_parallel) so both modes can be "
                         "plotted in the same figure")
    args = ap.parse_args()

    with open(args.inp, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"No rows in {args.inp}")
        return

    aggregated = aggregate(rows, args.mode, args.mode_in_name)
    if not aggregated:
        print("No cells survived aggregation (see warnings above).")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
        w.writeheader()
        w.writerows(aggregated)

    ns = sorted({r["n"] for r in aggregated})
    ks = sorted({int(r["variant"].split("_k")[1].split("_")[0]) for r in aggregated})
    print(f"Input  : {args.inp}  ({len(rows)} rows)")
    print(f"Output : {args.out}  ({len(aggregated)} rows, "
          f"variants={sorted({r['variant'] for r in aggregated})})")
    print(f"  N values: {ns}")
    print(f"  K values: {ks}")
    print(f"  mode    : {args.mode}")


if __name__ == "__main__":
    main()
