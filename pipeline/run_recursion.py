"""
pipeline/run_recursion.py -- recursion variant benchmark harness.

Two modes (selected with --exp):

  --exp 2   THE VARIANT.  Recursively verify ALL K segments of a K-way split AND
            fold in the full glue logic (outer circuit = circuits/recursion,
            generic over K).  A complete recursive proof of the K-segment TSP,
            exposing only (root, threshold) -- the perfect-hiding endpoint of the
            frontier, the equal-ground recursive counterpart of Variant A++ at the
            same K.  Cost scales ~K (one ~700k-gate verifier each).

  --exp 1   DIAGNOSTIC (off-frontier).  Recursively verify ONE
            hierarchical_segment_fs proof (outer circuit =
            tests/recursion_micro/exp1_single_segment).  Measures the per-segment
            recursion overhead in isolation; NOT a complete TSP statement, so keep
            its aggregated row (recursion_1seg) off the frontier figures.

Both reuse the UNMODIFIED hierarchical_segment_fs circuit as the inner (the *plain*
A++ segment -- recursion already hides the partition as witness, so committing it
would be redundant); the only difference from the A++ benchmark is the proving
flavor (-t noir-recursive, ZK, verified in-circuit by verify_honk_proof /
UltraHonkZKProof length 458).

PARALLELISM / DEPLOYMENT MODEL.  The K inner proofs are produced sequentially in
the shared segment dir -- so each recorded inner prove_s is a SOLO (uncontended)
time, i.e. already the per-node "isolated" measurement.  The outer always follows
the inners (it consumes their proofs), a SERIAL tail.  aggregate_recursion.py then
derives BOTH deployment models from this one measurement: --mode parallel =
max(inner)+outer (inners on K nodes), --mode total = sum(inner)+outer (one box).
No concurrent inner proving is needed; the solo times already feed both.

What it does per (N, K, run):
  1. Patch + compile hierarchical_segment_fs for (N, M=N/K, DEPTH); write its
     RECURSIVE ZK verification key (bb write_vk -t noir-recursive); record inner
     `bb gates`.
  2. Generate a TSP instance, solve it, and build the K+1 Prover.tomls via
     merkle_builder --hierarchical-fs K.
  3. Prove the needed segment(s) with `bb prove -t noir-recursive --output_format
     json --verify`, capturing proof (458) / public_inputs (9) / VK (115) fields.
  4. Assemble the outer Prover.toml (Exp 2 also reads the glue toml for the
     boundary-edge witness + threshold).
  5. Compile the outer circuit, record `bb gates` (THE recursion cost), run
     `nargo execute` (satisfiability), and -- unless --skip-prove -- `bb prove`
     (wall time + peak memory) and `bb verify` (verify time).

The hierarchical_segment_fs source globals are snapshotted and RESTORED at the
end so the shared A++ circuit is left untouched.

CSV columns (one row per measured circuit):
    exp n k m depth run role circuit gates acir compile_s witness_s prove_s
    verify_s proof_bytes peak_mb
(Feed this raw CSV to pipeline/aggregate_recursion.py to get plot.py-compatible
rows comparable with flat_* and hier_* results.)

Smoke usage (small; validates the harness):
    /home/callexyz/anaconda3/envs/zk-tsp/bin/python \\
        pipeline/run_recursion.py --exp 2 --n 8 --k 2 --runs 1 \\
        --out results/recursion.csv

The inner segment size barely affects the recursion overhead (the in-circuit
verifier checks a fixed-size proof), so small N already gives a representative
outer gate count.  Sweep larger N at your leisure.
"""

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE         = Path(__file__).resolve().parent          # pipeline/
PROJECT_ROOT = HERE.parent
SUB_DIR      = PROJECT_ROOT / "circuits" / "hierarchical_segment_fs"
SUB_NAME     = "hierarchical_segment_fs"
# exp 1 is the off-frontier single-segment DIAGNOSTIC; its outer circuit stays in tests/.
EXP1_DIR     = PROJECT_ROOT / "tests" / "recursion_micro" / "exp1_single_segment"
EXP1_NAME    = "rec_exp1_single_segment"
# exp 2 is THE recursion variant; its outer circuit lives in circuits/recursion.
EXP2_DIR     = PROJECT_ROOT / "circuits" / "recursion"
EXP2_NAME    = "recursion"
BUILDER_BIN  = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
SCRATCH_ROOT = Path("/tmp/recursion_run")

# Pipeline helpers (instance gen + solver).
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
from instance_gen   import generate_instance
from solver         import solve, cycle_cost
from instance_cache import get_instance_and_cycle

FIELDNAMES = [
    "exp", "n", "k", "m", "depth",
    "run",          # 1-based run index for this (exp, n, k) cell
    "role",         # "inner_segment" or "outer_recursive"
    "circuit",
    "gates",        # UltraHonk gate count (bb gates circuit_size)
    "acir",         # ACIR opcode count
    "compile_s",
    "witness_s",    # nargo execute wall time
    "prove_s",      # bb prove wall time
    "verify_s",     # bb verify wall time
    "proof_bytes",
    "peak_mb",      # peak mem during bb prove
]


# ── Shell helpers ───────────────────────────────────────────────────────────--

def run_cmd(cmd, cwd=None, check=True):
    """Run a subprocess; return (elapsed_s, stdout, stderr, rc).  Raise on failure if check."""
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    elapsed = time.perf_counter() - t0
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed ({' '.join(map(str, cmd))}):\n{r.stderr}\n{r.stdout}")
    return elapsed, r.stdout, r.stderr, r.returncode


def parse_peak_mb(stderr):
    vals = [float(m) for m in re.findall(r"mem: ([\d.]+) MiB", stderr)]
    return max(vals) if vals else float("nan")


def parse_gates(stdout):
    """Return (acir_opcodes, circuit_size) from `bb gates --output_format json`."""
    data = json.loads(stdout)
    fn = data["functions"][0]
    return fn["acir_opcodes"], fn["circuit_size"]


def merkle_depth(n):
    return (n * n - 1).bit_length() if n * n > 1 else 0


def patch_globals(src_path: Path, **values):
    text = src_path.read_text()
    for name, value in values.items():
        text = re.sub(
            rf"^global {name}: u32\s*=\s*\d+;",
            f"global {name}: u32 = {value};",
            text, flags=re.MULTILINE,
        )
    src_path.write_text(text)


# ── TOML emit helpers ─────────────────────────────────────────────────────────

def _field_array(hexvals):
    """hexvals already include the 0x prefix (from bb json / glue toml)."""
    return "[" + ", ".join(f'"{v}"' for v in hexvals) + "]"


def _int_array(ints):
    return "[" + ", ".join(f'"{int(v)}"' for v in ints) + "]"


def _bool_array(bools):
    return "[" + ", ".join("true" if b else "false" for b in bools) + "]"


# ── Inner segment proving (ZK recursive flavor) ───────────────────────────────

def configure_segment(n, k):
    """Patch + compile the inner segment for (N, M, DEPTH); write recursive ZK VK."""
    m, depth = n // k, merkle_depth(n)
    patch_globals(SUB_DIR / "src" / "main.nr", N=n, M=m, DEPTH=depth)
    compile_s, _, _, _ = run_cmd(["nargo", "compile"], cwd=SUB_DIR)
    # Recursive ZK verification key (binary, for `bb prove -k`) + JSON (vk fields + hash).
    run_cmd(["bb", "write_vk", "-b", f"target/{SUB_NAME}.json",
             "-t", "noir-recursive", "-o", "target/vk"], cwd=SUB_DIR)
    run_cmd(["bb", "write_vk", "-b", f"target/{SUB_NAME}.json",
             "-t", "noir-recursive", "--output_format", "json", "-o", "target/vk_json"], cwd=SUB_DIR)
    _, gates_out, _, _ = run_cmd(["bb", "gates", "-b", f"target/{SUB_NAME}.json"], cwd=SUB_DIR)
    acir, size = parse_gates(gates_out)
    vk = json.loads((SUB_DIR / "target" / "vk_json" / "vk.json").read_text())
    return {"m": m, "depth": depth, "compile_s": compile_s,
            "gates": size, "acir": acir, "vk_fields": vk["vk"], "key_hash": vk["hash"]}


def build_tomls(n, k, instance, cycle, out_dir, tree_cache=None, multiplier=1.1):
    """merkle_builder --hierarchical-fs K -> out_dir/{sub_0..,glue}/Prover.toml."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    matrix = instance["matrix"]
    cost = cycle_cost(matrix, cycle)
    payload = json.dumps({
        "n": n, "k": k,
        "flat_matrix": [matrix[i][j] for i in range(n) for j in range(n)],
        "cycle": cycle, "cost": cost, "threshold": math.ceil(cost * multiplier),
    })
    cmd = [str(BUILDER_BIN), "--hierarchical-fs", str(k), "--out-dir", str(out_dir)]
    if tree_cache is not None:
        cmd += ["--tree-cache", str(tree_cache)]
    r = subprocess.run(cmd, input=payload, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"merkle_builder failed:\n{r.stderr}")


def prove_segment(seg_idx, tomls_dir, proof_dir):
    """Copy sub_<seg> Prover.toml into the segment dir, witness, and ZK-recursive prove.

    Returns dict with proof(458)/public_inputs(9) field lists and inner timings.
    Segments are proved sequentially in the shared SUB_DIR (no race)."""
    shutil.copy(tomls_dir / f"sub_{seg_idx}" / "Prover.toml", SUB_DIR / "Prover.toml")
    witness_s, _, _, _ = run_cmd(["nargo", "execute"], cwd=SUB_DIR)
    if proof_dir.exists():
        shutil.rmtree(proof_dir)
    proof_dir.mkdir(parents=True)
    prove_s, _, prove_err, _ = run_cmd(
        ["bb", "prove", "-b", f"target/{SUB_NAME}.json", "-w", f"target/{SUB_NAME}.gz",
         "-k", "target/vk/vk", "-t", "noir-recursive",
         "--output_format", "json", "--verify", "-o", str(proof_dir)], cwd=SUB_DIR)
    proof = json.loads((proof_dir / "proof.json").read_text())["proof"]
    pub   = json.loads((proof_dir / "public_inputs.json").read_text())["public_inputs"]
    assert len(proof) == 458, f"expected 458 ZK proof fields, got {len(proof)}"
    assert len(pub)   == 9,   f"expected 9 segment public inputs, got {len(pub)}"
    return {"proof": proof, "pub": pub,
            "witness_s": witness_s, "prove_s": prove_s, "peak_mb": parse_peak_mb(prove_err)}


# ── Outer Prover.toml assembly ────────────────────────────────────────────────

def assemble_exp1(seg, vk_fields, key_hash):
    """Outer Prover.toml for exp1: one proof + its 9 public inputs; expose root = pub[3]."""
    lines = [
        "# Auto-generated by run_recursion.py (exp 1) -- do not edit by hand\n",
        f"verification_key = {_field_array(vk_fields)}",
        f'key_hash         = "{key_hash}"',
        f"proof            = {_field_array(seg['proof'])}",
        f"sub_pub          = {_field_array(seg['pub'])}",
        f'root             = "{seg["pub"][3]}"',
    ]
    return "\n".join(lines) + "\n"


def assemble_exp2(segs, vk_fields, key_hash, tomls_dir):
    """Outer Prover.toml for exp2 (any K): K proofs (2D arrays) + boundary witness + threshold."""
    glue = tomllib.loads((tomls_dir / "glue" / "Prover.toml").read_text())
    # Integer mirrors derived from the verified sub_pub fields (consistency by construction).
    starts        = [int(s["pub"][0], 16) for s in segs]
    ends          = [int(s["pub"][1], 16) for s in segs]
    partial_costs = [int(s["pub"][2], 16) for s in segs]
    root          = segs[0]["pub"][3]
    proofs_2d   = "[" + ", ".join(_field_array(s["proof"]) for s in segs) + "]"
    sub_pubs_2d = "[" + ", ".join(_field_array(s["pub"])   for s in segs) + "]"
    lines = [
        "# Auto-generated by run_recursion.py (exp 2) -- do not edit by hand\n",
        f"sub_vk   = {_field_array(vk_fields)}",
        f'key_hash = "{key_hash}"',
        f"proofs   = {proofs_2d}",
        f"sub_pubs = {sub_pubs_2d}",
        f"boundary_costs     = {_int_array(glue['boundary_costs'])}",
        f"boundary_siblings  = {_field_array(glue['boundary_siblings'])}",
        f"boundary_path_bits = {_bool_array(glue['boundary_path_bits'])}",
        f"starts        = {_int_array(starts)}",
        f"ends          = {_int_array(ends)}",
        f"partial_costs = {_int_array(partial_costs)}",
        f'root      = "{root}"',
        f'threshold = "{int(glue["threshold"])}"',
    ]
    return "\n".join(lines) + "\n"


# ── Outer measurement ─────────────────────────────────────────────────────────

def measure_outer(outer_dir, outer_name, skip_prove):
    """Compile outer, record gates, witness, (optionally) prove + verify."""
    compile_s, _, _, _ = run_cmd(["nargo", "compile"], cwd=outer_dir)
    _, gates_out, _, _ = run_cmd(["bb", "gates", "-b", f"target/{outer_name}.json"], cwd=outer_dir)
    acir, size = parse_gates(gates_out)
    witness_s, _, _, _ = run_cmd(["nargo", "execute"], cwd=outer_dir)

    prove_s = verify_s = float("nan")
    proof_bytes = 0
    peak_mb = float("nan")
    if not skip_prove:
        run_cmd(["bb", "write_vk", "-b", f"target/{outer_name}.json", "-o", "target/vk"], cwd=outer_dir)
        proof_dir = outer_dir / "target" / "proof"
        if proof_dir.exists():
            shutil.rmtree(proof_dir)
        proof_dir.mkdir(parents=True)
        prove_s, _, prove_err, _ = run_cmd(
            ["bb", "prove", "-b", f"target/{outer_name}.json", "-w", f"target/{outer_name}.gz",
             "-k", "target/vk/vk", "-o", str(proof_dir)], cwd=outer_dir)
        peak_mb = parse_peak_mb(prove_err)
        pf = proof_dir / "proof"
        proof_bytes = pf.stat().st_size if pf.exists() else 0
        # ZK guard: the outer proof MUST be ZK (the sub_pubs witness is hidden only
        # by a ZK outer proof).  Default `bb prove` is ZK = 458 fields = 14656 bytes;
        # a non-ZK proof (410 fields / 13120 bytes) would silently leak the partition.
        if proof_bytes not in (0, 14656):
            raise RuntimeError(
                f"outer proof is {proof_bytes} bytes, expected 14656 (458 ZK fields). "
                f"bb's default prove may have stopped being ZK -- the recursion hiding "
                f"claim is void until this is fixed (pass an explicit ZK verifier_target)."
            )
        verify_s, _, _, _ = run_cmd(
            ["bb", "verify", "-k", "target/vk/vk",
             "-p", str(proof_dir / "proof"), "-i", str(proof_dir / "public_inputs")], cwd=outer_dir)

    return {"gates": size, "acir": acir, "compile_s": compile_s, "witness_s": witness_s,
            "prove_s": prove_s, "verify_s": verify_s, "proof_bytes": proof_bytes, "peak_mb": peak_mb}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Recursion variant benchmark harness (ZK, noir-recursive).")
    ap.add_argument("--exp", type=int, choices=[1, 2], default=2,
                    help="2 = the recursion variant (default); 1 = single-segment DIAGNOSTIC (off-frontier).")
    ap.add_argument("--n", type=int, default=8, help="Total nodes N (default 8).")
    ap.add_argument("--k", type=int, default=2,
                    help="Segments K (>= 2; for exp 2 the outer verifies all K proofs; default 2).")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", required=True, help="CSV output path.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-prove", action="store_true",
                    help="Only compile/gates/execute the outer; skip the heavy bb prove + verify.")
    args = ap.parse_args()

    if args.k < 2:
        sys.exit(f"K must be >= 2 (got {args.k})")
    if args.n % args.k != 0:
        sys.exit(f"N={args.n} must be divisible by K={args.k}")
    if not BUILDER_BIN.exists():
        sys.exit("merkle_builder not built. Run:\n  cargo build --release "
                 "--manifest-path pipeline/merkle_builder/Cargo.toml")

    outer_dir, outer_name = (EXP1_DIR, EXP1_NAME) if args.exp == 1 else (EXP2_DIR, EXP2_NAME)
    n, k, m, depth = args.n, args.k, args.n // args.k, merkle_depth(args.n)

    out_csv = Path(args.out)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_csv.exists()

    sub_src = SUB_DIR / "src" / "main.nr"
    sub_snapshot = sub_src.read_text()  # restore the shared A++ circuit afterwards
    sub_toml = SUB_DIR / "Prover.toml"  # the driver overwrites this with segment witnesses
    sub_toml_snapshot = sub_toml.read_text() if sub_toml.exists() else None
    outer_src = outer_dir / "src" / "main.nr"  # patched per (N,K) below; restore after
    outer_snapshot = outer_src.read_text()
    try:
        with open(out_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()

            print(f"[exp {args.exp}] N={n} K={k} M={m} DEPTH={depth}: compiling inner segment + recursive VK ...")
            seg_meta = configure_segment(n, k)
            print(f"  inner segment: gates={seg_meta['gates']} acir={seg_meta['acir']}")

            if args.exp == 2:
                patch_globals(outer_dir / "src" / "main.nr", N=n, K=k, DEPTH=depth)

            # One canonical instance per N, shared across runs (and with every
            # other variant at this N via the same (N, seed) cache key).
            instance, cycle, tree_cache = get_instance_and_cycle(n, args.seed)

            for run_idx in range(1, args.runs + 1):
                print(f"  run {run_idx}/{args.runs}: build tomls ...", flush=True)
                cell     = SCRATCH_ROOT / f"exp{args.exp}_n{n}_k{k}_run{run_idx}"
                tomls    = cell / "tomls"
                build_tomls(n, k, instance, cycle, tomls, tree_cache)

                print("  proving inner segment(s) (bb prove -t noir-recursive, ZK) ...", flush=True)
                if args.exp == 1:
                    seg0 = prove_segment(0, tomls, cell / "proof_0")
                    (outer_dir / "Prover.toml").write_text(assemble_exp1(seg0, seg_meta["vk_fields"], seg_meta["key_hash"]))
                    inner_rows = [("sub_0", seg0)]
                else:
                    segs = [prove_segment(i, tomls, cell / f"proof_{i}") for i in range(k)]
                    (outer_dir / "Prover.toml").write_text(
                        assemble_exp2(segs, seg_meta["vk_fields"], seg_meta["key_hash"], tomls))
                    inner_rows = [(f"sub_{i}", segs[i]) for i in range(k)]

                print(f"  measuring outer recursive circuit ({outer_name}) ...", flush=True)
                outer = measure_outer(outer_dir, outer_name, args.skip_prove)

                # one row per inner segment proof
                for cname, seg in inner_rows:
                    writer.writerow({
                        "exp": args.exp, "n": n, "k": k, "m": m, "depth": depth,
                        "run": run_idx,
                        "role": "inner_segment", "circuit": cname,
                        "gates": seg_meta["gates"], "acir": seg_meta["acir"],
                        "compile_s": round(seg_meta["compile_s"], 4),
                        "witness_s": round(seg["witness_s"], 4), "prove_s": round(seg["prove_s"], 4),
                        "verify_s": "", "proof_bytes": "", "peak_mb": round(seg["peak_mb"], 3),
                    })
                # the outer recursive circuit row
                writer.writerow({
                    "exp": args.exp, "n": n, "k": k, "m": m, "depth": depth,
                    "run": run_idx,
                    "role": "outer_recursive", "circuit": outer_name,
                    "gates": outer["gates"], "acir": outer["acir"],
                    "compile_s": round(outer["compile_s"], 4),
                    "witness_s": round(outer["witness_s"], 4),
                    "prove_s": "" if math.isnan(outer["prove_s"]) else round(outer["prove_s"], 4),
                    "verify_s": "" if math.isnan(outer["verify_s"]) else round(outer["verify_s"], 4),
                    "proof_bytes": outer["proof_bytes"],
                    "peak_mb": "" if math.isnan(outer["peak_mb"]) else round(outer["peak_mb"], 3),
                })
                f.flush()

                pv = "skipped" if args.skip_prove else f"{outer['prove_s']:.2f}s, peak {outer['peak_mb']:.0f} MiB"
                print(f"  OUTER gates={outer['gates']}  witness={outer['witness_s']:.2f}s  prove={pv}")
    finally:
        sub_src.write_text(sub_snapshot)  # leave the shared A++ segment circuit untouched
        if sub_toml_snapshot is not None:
            sub_toml.write_text(sub_toml_snapshot)  # restore the original Prover.toml too
        outer_src.write_text(outer_snapshot)  # restore outer circuit globals to committed default

    print(f"\nDone. Results appended to {out_csv}")


if __name__ == "__main__":
    main()
