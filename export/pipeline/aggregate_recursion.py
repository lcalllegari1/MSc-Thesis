"""
pipeline/aggregate_recursion.py -- Convert raw recursion micro-experiment CSV
(pipeline/run_recursion.py output) into a plot.py-compatible CSV
(one row per (exp, N, run)), so recursion sits on the same axes as flat_* and
the aggregated hier_* variants.

This is the recursion analogue of pipeline/aggregate_hier.py.  The raw CSV has
one row per measured circuit: the inner segment proof(s) (role=inner_segment)
plus the single outer recursive proof (role=outer_recursive).  plot.py wants one
row per (variant, N) data point in the run.py schema, so we fold each
(exp, N, run) cell's rows into one.

Aggregation rules (per cell)
----------------------------

  metric         | rule                       | rationale
  ---------------|----------------------------|------------------------------------
  circuit_size   | sum(inner) + outer         | total proving work in gates (the
                 |                            |  outer dominates: ~1.47M vs ~2x28k)
  acir_opcodes   | sum(inner) + outer         | same logic
  compile_s      | inner(one) + outer         | the K inner proofs reuse one compiled
                 |                            |  segment binary; + one outer compile
  witness_s      | innerstep + outer          | innerstep = max (parallel) or sum
  prove_s        | innerstep + outer          |  (total) across the inner proofs;
                 |                            |  the outer ALWAYS follows them (it
                 |                            |  consumes their proofs), hence "+".
  verify_s       | outer only                 | the verifier checks exactly ONE
                 |                            |  proof -- recursion's whole point;
                 |                            |  the cross-checks are now in-circuit
  proof_bytes    | outer only                 | exactly one proof is delivered
  peak_mb        | max(K inner peaks, outer)  | "per-prover peak": the heaviest single
                 |                            |  bb prove process across all K+1 ops

Compared with aggregate_hier.py this makes recursion's profile explicit: high
single-proof circuit_size / prove_s / peak_mb, but a *single* tiny verify_s and a
*constant* proof_bytes -- the perfect-hiding corner's wins and costs.

peak_mb in detail
-----------------
Each raw `peak_mb` is the peak RSS of ONE `bb prove` process (from bb's stderr).
We take the MAX over the K inner-segment peaks AND the outer peak -- i.e. the
heaviest single proving step ("per-prover peak"), the same metric
aggregate_hier.py uses (so recursion and A++ compare apples-to-apples).  This is
*exact* for sequential inner proving: the outer consumes the inner proofs as data
(not live processes), so only one prover is ever resident at a time and the
machine peak-over-time IS the max of the individual peaks.  It under-counts only
the case where K inner provers run CONCURRENTLY and their resident memory sums
above the outer -- i.e. only if sum(K inner peaks) > outer.  In every measured
cell the outer dominates by 4-14x (worst: N=480 K=4, sum inner 1.17 GB vs outer
4.1 GB), so max-of-individual and the parallel-aware max(sum inner, outer)
coincide; the reported number is the outer's and is correct under both
schedulings.  If an inner ever did exceed the outer it WOULD be reported (inner
peaks are in the max); only the concurrent-sum-of-inners case is not modelled.

Modes
-----
  --mode parallel  (default) -- innerstep = MAX (ideal K-way parallel inner
                                proving), then + outer.  Most comparable with the
                                hier_*_par aggregation.
  --mode total              -- innerstep = SUM (total inner CPU work), then + outer.

Variant naming
--------------
  exp 1 -> "{label}_1seg"   (single-segment recursion cost; a DIAGNOSTIC --
                             its verify_s/proof_bytes describe verifying one
                             segment proof, not a complete TSP statement)
  exp 2 -> "{label}_k{K}"   (the complete recursive proof of the K-cycle; the
                             row to overlay with flat_merkle / hier_fs_k{K})
`label` defaults to "recursion".  The raw recursion CSV has no `variant` column
(only `exp`), so --label is how the inner MECHANISM is recorded: aggregate the
sort-inner and product-inner sweeps with DIFFERENT labels (e.g. recursion_sort,
recursion_gp) or they collide on the same recursion_k{K} name when plotted
together.  Pass --mode-in-name to also append _<mode> (e.g. recursion_k2_parallel).

Component split (--split-components)
------------------------------------
With --split-components the combined row is still emitted, plus THREE extra rows
per cell so the inner cost and the outer cost draw as separate lines (never one
collapsed max):

  {label}_k{K}_seg_node   PER-NODE / WORST CASE: one inner segment -- gates = one
                          inner, prove/witness = MAX over the K inners (worst
                          node), peak = max.  Mode-independent; does NOT sum to
                          combined.
  {label}_k{K}_seg_total  DECOMPOSITION: the inner phase -- gates = sum(inner),
                          prove/witness = max (parallel) / sum (total), peak =
                          max.  Sums to combined with _outer.
  {label}_k{K}_outer      the OUTER recursive proof alone (its own gates, prove,
                          verify, proof_bytes, peak).

Inner proofs are consumed by the outer, not delivered to the verifier, so the
two segment rows carry no verify_s / proof_bytes.

Honesty note: there is deliberately NO "_glue" row.  Recursion fuses the glue
logic into the outer circuit together with the K in-circuit verifications, which
dominate it (~704k gates each vs ~63k total glue at K=2); the glue is not a
separately measured artifact.  The whole outer IS the binding layer -- the
recursion analogue of the hierarchical glue + verifier binding tax -- so the
split is segments vs outer.  The two rows sum back to the combined row.
plot.py needs no change: each is a distinct `variant` (select with --variants
'*_seg' '*_outer').

Schema written (matches pipeline/run.py exactly)
------------------------------------------------
  variant, n, run, circuit_size, acir_opcodes, compile_s,
  witness_s, prove_s, verify_s, proof_bytes, peak_mb

Usage
-----
  python pipeline/aggregate_recursion.py \\
      --in  results/recursion.csv \\
      --out results/recursion_par.csv \\
      --mode parallel

  # Overlay with the flat baseline and A++ at K=2 (the K=2 frontier figure):
  python pipeline/plot.py \\
      --csv results/500.csv results/hier_fs_par.csv results/recursion_par.csv \\
      --out plots/frontier_k2
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


def _fnum(s):
    """Parse a CSV float cell; return None for blank / nan (e.g. --skip-prove rows)."""
    if s is None or s in ("", "nan", "NaN"):
        return None
    return float(s)


def _fmt(x):
    """Render an aggregated number for CSV; blank when unavailable."""
    return "" if x is None else round(x, 4)


def _rrow(variant, n, run, csize, acir, compile_s,
          witness_s, prove_s, verify_s, proof_bytes, peak_mb):
    """Assemble one output row dict; None metrics render blank (e.g. --skip-prove)."""
    return {
        "variant":      variant,
        "n":            n,
        "run":          run,
        "circuit_size": csize,
        "acir_opcodes": acir,
        "compile_s":    round(compile_s, 4),
        "witness_s":    _fmt(witness_s),
        "prove_s":      _fmt(prove_s),
        "verify_s":     _fmt(verify_s),
        "proof_bytes":  proof_bytes,
        "peak_mb":      _fmt(peak_mb),
    }


def aggregate(rows, mode, include_mode_in_name, split_components=False,
              label="recursion"):
    grouped = defaultdict(list)
    for row in rows:
        key = (int(row["exp"]), int(row["n"]), int(row["k"]), int(row["run"]))
        grouped[key].append(row)

    out = []
    for (exp, n, k, run), group in sorted(grouped.items()):
        inners = [r for r in group if r["role"] == "inner_segment"]
        outer  = next((r for r in group if r["role"] == "outer_recursive"), None)

        expected_inner = 1 if exp == 1 else k
        if len(inners) != expected_inner or outer is None:
            print(f"  [warn] exp={exp} N={n} K={k} run={run}: have {len(inners)} inner rows + "
                  f"outer={outer is not None}, expected {expected_inner} inner + 1 outer.  Skipping.")
            continue

        # Structural metrics. Inner segments share one compiled binary, so compile
        # is counted once (not per segment).
        inner_size = sum(int(r["gates"]) for r in inners)
        inner_acir = sum(int(r["acir"])  for r in inners)
        inner_compile = float(inners[0]["compile_s"])
        outer_size = int(outer["gates"])
        outer_acir = int(outer["acir"])
        outer_compile = float(outer["compile_s"])

        # Runtime metrics. The outer proof always follows the inner proofs (it
        # consumes them), so prove/witness = inner-step + outer regardless of mode;
        # mode only changes whether the inner step is parallel (max) or total (sum).
        inner_witness = [_fnum(r["witness_s"]) for r in inners]
        inner_prove   = [_fnum(r["prove_s"])   for r in inners]
        innerstep = (lambda v: max(v)) if mode == "parallel" else (lambda v: sum(v))

        def _combine(inner_vals, outer_val):
            iv = [x for x in inner_vals if x is not None]
            if not iv and outer_val is None:
                return None
            return (innerstep(iv) if iv else 0.0) + (outer_val or 0.0)

        witness_s = _combine(inner_witness, _fnum(outer["witness_s"]))
        prove_s   = _combine(inner_prove,   _fnum(outer["prove_s"]))

        # Verifier checks exactly the ONE outer proof; cross-checks are in-circuit.
        verify_s    = _fnum(outer["verify_s"])
        proof_bytes = int(outer["proof_bytes"]) if outer["proof_bytes"] not in ("", None) else 0

        inner_peak = [_fnum(r["peak_mb"]) for r in inners]
        outer_peak = _fnum(outer["peak_mb"])
        peaks = [x for x in inner_peak + [outer_peak] if x is not None]
        peak_mb = max(peaks) if peaks else None

        base = f"{label}_1seg" if exp == 1 else f"{label}_k{k}"

        def _name(suffix):
            v = base + suffix
            return v + f"_{mode}" if include_mode_in_name else v

        # Combined row (unchanged): segments + outer folded into one data point.
        out.append(_rrow(
            _name(""), n, run,
            inner_size + outer_size, inner_acir + outer_acir,
            inner_compile + outer_compile,
            witness_s, prove_s, verify_s, proof_bytes, peak_mb))

        # Optional component rows: the inner SEGMENTS vs the OUTER proof as
        # separate data points.  Note (honesty): recursion has no separable glue
        # -- the glue logic is fused into the outer alongside the K in-circuit
        # verifications, which dominate it -- so the binding component here is the
        # whole outer ("_outer"), NOT a "glue" row.  The outer is the recursion
        # analogue of the hierarchical binding tax.  Inner proofs are consumed by
        # the outer (not delivered to the final verifier), so the segment row
        # carries no verify_s / proof_bytes.  These sum back to the combined row
        # (gates add; peak and parallel prove/witness are the max).
        if split_components:
            iv_w = [x for x in inner_witness if x is not None]
            iv_p = [x for x in inner_prove   if x is not None]
            ip   = [x for x in inner_peak    if x is not None]
            # Single inner segment (the K inners are identical M-sized circuits).
            one_inner_size = int(inners[0]["gates"])
            one_inner_acir = int(inners[0]["acir"])
            # _seg_node: PER-NODE / WORST CASE -- one inner segment.  gates = one
            # inner, time = MAX over the K inners (worst node), peak = max.  Inner
            # proofs are consumed by the outer (never delivered), so no verify/bytes.
            out.append(_rrow(
                _name("_seg_node"), n, run,
                one_inner_size, one_inner_acir, inner_compile,
                max(iv_w) if iv_w else None,
                max(iv_p) if iv_p else None,
                None, "", max(ip) if ip else None))
            # _seg_total: DECOMPOSITION -- the inner phase (gates = sum(inner),
            # time = max (parallel) / sum (total)).  Sums to combined with _outer.
            out.append(_rrow(
                _name("_seg_total"), n, run,
                inner_size, inner_acir, inner_compile,
                innerstep(iv_w) if iv_w else None,
                innerstep(iv_p) if iv_p else None,
                None, "", max(ip) if ip else None))
            out.append(_rrow(
                _name("_outer"), n, run,
                outer_size, outer_acir, outer_compile,
                _fnum(outer["witness_s"]), _fnum(outer["prove_s"]),
                _fnum(outer["verify_s"]), proof_bytes, outer_peak))

    return out


def main():
    ap = argparse.ArgumentParser(
        description="Aggregate raw recursion CSV into a plot.py-compatible CSV.")
    ap.add_argument("--in", dest="inp", required=True, type=Path,
                    help="Input CSV from pipeline/run_recursion.py")
    ap.add_argument("--out", required=True, type=Path, help="Output CSV path")
    ap.add_argument("--mode", choices=["parallel", "total"], default="parallel",
                    help="Inner-proof aggregation: max (parallel) or sum (total) (default: parallel)")
    ap.add_argument("--mode-in-name", action="store_true",
                    help="Append _<mode> to the variant column so both modes can share a figure")
    ap.add_argument("--label", default="recursion",
                    help="Variant-name base (default: 'recursion' -> recursion_k{K}). "
                         "Set per inner mechanism so sort- and product-inner recursion "
                         "do NOT collide when plotted together, e.g. --label recursion_sort "
                         "-> recursion_sort_k{K}, --label recursion_gp -> recursion_gp_k{K}.")
    ap.add_argument("--split-components", action="store_true",
                    help="Additionally emit per-cell SEGMENT and OUTER rows "
                         "(recursion_k{K}_seg and _outer) alongside the combined "
                         "row, so plot.py can draw inner segments and the outer "
                         "proof as separate lines (select with --variants '*_seg' "
                         "/ '*_outer').  NB: recursion has no separable glue -- the "
                         "binding component is the whole outer.  Combined row kept.")
    args = ap.parse_args()

    with open(args.inp, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f"No rows in {args.inp}")
        return

    aggregated = aggregate(rows, args.mode, args.mode_in_name, args.split_components,
                           label=args.label)
    if not aggregated:
        print("No cells survived aggregation (see warnings above).")
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
        w.writeheader()
        w.writerows(aggregated)

    ns = sorted({r["n"] for r in aggregated})
    print(f"Input  : {args.inp}  ({len(rows)} rows)")
    print(f"Output : {args.out}  ({len(aggregated)} rows, "
          f"variants={sorted({r['variant'] for r in aggregated})})")
    print(f"  N values: {ns}")
    print(f"  mode    : {args.mode}")


if __name__ == "__main__":
    main()
