"""
tests/recursion_micro/compare_inner.py -- head-to-head A++ vs A inner recursion.

Runs BOTH recursion variants on the SAME instance and reports the per-metric
difference for the outer (recursive) proof:

  * A++ inner -- run_recursion.py     -> hierarchical_segment_fs, grand-product +
                                         Fiat-Shamir partition, O(1) public surface
  * A   inner -- run_recursion_a.py   -> hierarchical_segment,    sort partition,
                                         O(M) public surface

Both drivers derive their TSP instance from the SAME seed formula
(seed + N*1000 + K*100 + run), so passing one --seed here gives both variants the
*identical* instance, cycle, and segmentation -- a true ceteris-paribus
comparison.  The headline is the **outer gate delta**: the O(M) public-input
absorption cost argued in Recursive_inner_circuit_choice_explained.md.  Proof
size and verify time should come out ~identical (both deliver one ZK proof and
expose only root[,threshold]).

Usage:
    python tests/recursion_micro/compare_inner.py --n 48 --k 2 --exp 2 --runs 1
    #   --skip-prove  : compare gate counts only (fast; skips both heavy outers)
    #   --keep-csv DIR: also write the two raw CSVs and a combined diff CSV there

Run with the zk-tsp python (the drivers need numpy):
    /home/callexyz/anaconda3/envs/zk-tsp/bin/python tests/recursion_micro/compare_inner.py ...
"""

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRIVER_FS = HERE / "run_recursion.py"      # A++ inner
DRIVER_A  = HERE / "run_recursion_a.py"    # A inner


def run_driver(driver, exp, n, k, runs, seed, skip_prove, out_csv):
    """Invoke a recursion driver as a subprocess; raise on failure."""
    cmd = [sys.executable, str(driver), "--exp", str(exp), "--n", str(n),
           "--k", str(k), "--runs", str(runs), "--seed", str(seed), "--out", str(out_csv)]
    if skip_prove:
        cmd.append("--skip-prove")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"driver failed: {' '.join(cmd)}\n{r.stderr}\n{r.stdout}")


def _avg(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) not in ("", None)]
    return sum(vals) / len(vals) if vals else None


def load_cell(csv_path, exp, n, k):
    """Return (outer_row_means, inner_row_means) dicts for the (exp,n,k) cell."""
    rows = [r for r in csv.DictReader(open(csv_path))
            if int(r["exp"]) == exp and int(r["n"]) == n and int(r["k"]) == k]
    outer = [r for r in rows if r["role"] == "outer_recursive"]
    inner = [r for r in rows if r["role"] == "inner_segment"]
    metrics = ["gates", "acir", "witness_s", "prove_s", "verify_s", "proof_bytes", "peak_mb"]
    return ({m: _avg(outer, m) for m in metrics},
            {m: _avg(inner, m) for m in metrics})


def _fmt(x):
    if x is None:
        return "-"
    return f"{x:.4g}" if isinstance(x, float) and x != int(x) else f"{int(x)}"


def _delta(a, b):
    if a is None or b is None:
        return "-", "-"
    d = b - a
    pct = (d / a * 100) if a != 0 else float("inf")
    sign = "+" if d >= 0 else ""
    return f"{sign}{_fmt(d)}", (f"{sign}{pct:.1f}%" if a != 0 else "-")


def main():
    ap = argparse.ArgumentParser(description="Compare A++ vs A inner recursion on the same instance.")
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--exp", type=int, choices=[1, 2], default=2)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-prove", action="store_true")
    ap.add_argument("--keep-csv", type=Path, default=None,
                    help="Directory to keep the two raw CSVs + a combined diff CSV.")
    args = ap.parse_args()

    if args.n % args.k != 0:
        sys.exit(f"N={args.n} must be divisible by K={args.k}")
    m = args.n // args.k

    tmpdir = Path(tempfile.mkdtemp(prefix="cmp_inner_"))
    fs_csv = tmpdir / "fs.csv"
    a_csv  = tmpdir / "a.csv"

    print(f"Running A++ inner (run_recursion.py) on N={args.n} K={args.k} exp={args.exp} seed={args.seed} ...", flush=True)
    run_driver(DRIVER_FS, args.exp, args.n, args.k, args.runs, args.seed, args.skip_prove, fs_csv)
    print(f"Running A   inner (run_recursion_a.py) on the SAME instance ...", flush=True)
    run_driver(DRIVER_A, args.exp, args.n, args.k, args.runs, args.seed, args.skip_prove, a_csv)

    fs_outer, fs_inner = load_cell(fs_csv, args.exp, args.n, args.k)
    a_outer,  a_inner  = load_cell(a_csv,  args.exp, args.n, args.k)

    # Inner public-input surface: A++ is fixed 9; A is M+4.
    fs_pub, a_pub = 9, m + 4

    print(f"\n=== A++ inner vs A inner recursion (exp {args.exp}) -- "
          f"N={args.n} K={args.k} (M={m}), avg of {args.runs} run(s) ===\n")
    hdr = f"{'metric':<22}{'A++ (fs)':>14}{'A (sort)':>14}{'delta (A-A++)':>16}{'delta %':>10}"
    print(hdr)
    print("-" * len(hdr))

    def row(label, av, bv):
        d, pct = _delta(av, bv)
        print(f"{label:<22}{_fmt(av):>14}{_fmt(bv):>14}{d:>16}{pct:>10}")

    row("inner pub inputs", fs_pub, a_pub)
    row("inner seg gates",  fs_inner["gates"], a_inner["gates"])
    print("-" * len(hdr))
    row("outer gates",      fs_outer["gates"], a_outer["gates"])
    row("outer acir",       fs_outer["acir"], a_outer["acir"])
    row("outer witness_s",  fs_outer["witness_s"], a_outer["witness_s"])
    row("outer prove_s",    fs_outer["prove_s"], a_outer["prove_s"])
    row("outer verify_s",   fs_outer["verify_s"], a_outer["verify_s"])
    row("outer proof_bytes", fs_outer["proof_bytes"], a_outer["proof_bytes"])
    row("outer peak_mb",    fs_outer["peak_mb"], a_outer["peak_mb"])

    print("\nReading the headline: 'outer gates' delta is the O(M) public-input "
          "absorption cost of the\nA inner; 'outer proof_bytes' / 'outer verify_s' "
          "should be ~equal (both deliver one ZK proof,\nboth expose only root[,threshold]).")

    if args.keep_csv:
        args.keep_csv.mkdir(parents=True, exist_ok=True)
        shutil.copy(fs_csv, args.keep_csv / "recursion_fs_cmp.csv")
        shutil.copy(a_csv,  args.keep_csv / "recursion_a_cmp.csv")
        diff_path = args.keep_csv / "recursion_inner_diff.csv"
        with open(diff_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["exp", "n", "k", "m", "metric", "a_plus_plus", "a", "delta"])
            pairs = [("inner_pub_inputs", fs_pub, a_pub),
                     ("inner_seg_gates", fs_inner["gates"], a_inner["gates"]),
                     ("outer_gates", fs_outer["gates"], a_outer["gates"]),
                     ("outer_acir", fs_outer["acir"], a_outer["acir"]),
                     ("outer_witness_s", fs_outer["witness_s"], a_outer["witness_s"]),
                     ("outer_prove_s", fs_outer["prove_s"], a_outer["prove_s"]),
                     ("outer_verify_s", fs_outer["verify_s"], a_outer["verify_s"]),
                     ("outer_proof_bytes", fs_outer["proof_bytes"], a_outer["proof_bytes"]),
                     ("outer_peak_mb", fs_outer["peak_mb"], a_outer["peak_mb"])]
            for name, av, bv in pairs:
                delta = (bv - av) if (av is not None and bv is not None) else ""
                w.writerow([args.exp, args.n, args.k, m, name, av, bv, delta])
        print(f"\nKept: {args.keep_csv}/ (recursion_fs_cmp.csv, recursion_a_cmp.csv, recursion_inner_diff.csv)")


if __name__ == "__main__":
    main()
