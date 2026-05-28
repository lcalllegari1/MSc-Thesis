"""
tests/recursion_micro/run_recursion_a.py -- A-INNER recursion micro-experiment.

This is the deliberate duplicate of run_recursion.py for the **Variant A** inner
sub-circuit (circuits/hierarchical_segment), kept fully separate so the two
recursive designs can be compared head-to-head (see compare_inner.py and
Recursive_inner_circuit_choice_explained.md).

Difference from the A++ driver (run_recursion.py):
  * Inner circuit:  hierarchical_segment (Variant A) instead of *_fs.
  * Builder mode:   merkle_builder --hierarchical K  (not --hierarchical-fs).
  * A sub_pub:      M+4 fields [sorted_nodes[M], start, end, partial_cost, root]
                    (vs A++'s fixed 9), so the recursive verifier absorbs an
                    O(M) public surface.
  * Outer glue:     SORT-based partition (sort(all_nodes) == [0..N-1]) -- no
                    Fiat-Shamir / grand product / hash chain.
  * Outer circuits: exp1_single_segment_a / exp2_k_segments_a.
  * CSV default:    results/recursion_a_micro.csv  (same schema as the A++ one).

Everything else (three-phase pipeline, ZK recursive flavor -t noir-recursive,
per-process timing, snapshot/restore of the shared segment circuit) mirrors
run_recursion.py exactly.

Usage:
    python tests/recursion_micro/run_recursion_a.py --exp 2 --n 48 --k 2 --runs 1 \\
        --out results/recursion_a_micro.csv
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
HERE         = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
SUB_DIR      = PROJECT_ROOT / "circuits" / "hierarchical_segment"   # Variant A inner
SUB_NAME     = "hierarchical_segment"
EXP1_DIR     = HERE / "exp1_single_segment_a"
EXP1_NAME    = "rec_exp1_single_segment_a"
EXP2_DIR     = HERE / "exp2_k_segments_a"
EXP2_NAME    = "rec_exp2_k_segments_a"
BUILDER_BIN  = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
SCRATCH_ROOT = Path("/tmp/recursion_micro_a")

sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
from instance_gen import generate_instance
from solver       import solve, cycle_cost

FIELDNAMES = [
    "exp", "n", "k", "m", "depth",
    "run",
    "role",         # "inner_segment" or "outer_recursive"
    "circuit",
    "gates", "acir",
    "compile_s", "witness_s", "prove_s", "verify_s",
    "proof_bytes", "peak_mb",
]


# ── Shell helpers ───────────────────────────────────────────────────────────--

def run_cmd(cmd, cwd=None, check=True):
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
    return "[" + ", ".join(f'"{v}"' for v in hexvals) + "]"


def _int_array(ints):
    return "[" + ", ".join(f'"{int(v)}"' for v in ints) + "]"


def _bool_array(bools):
    return "[" + ", ".join("true" if b else "false" for b in bools) + "]"


# ── Inner segment proving (Variant A, ZK recursive flavor) ────────────────────

def configure_segment(n, k):
    """Patch + compile the Variant A inner for (N, M, DEPTH); write recursive ZK VK."""
    m, depth = n // k, merkle_depth(n)
    patch_globals(SUB_DIR / "src" / "main.nr", N=n, M=m, DEPTH=depth)
    compile_s, _, _, _ = run_cmd(["nargo", "compile"], cwd=SUB_DIR)
    run_cmd(["bb", "write_vk", "-b", f"target/{SUB_NAME}.json",
             "-t", "noir-recursive", "-o", "target/vk"], cwd=SUB_DIR)
    run_cmd(["bb", "write_vk", "-b", f"target/{SUB_NAME}.json",
             "-t", "noir-recursive", "--output_format", "json", "-o", "target/vk_json"], cwd=SUB_DIR)
    _, gates_out, _, _ = run_cmd(["bb", "gates", "-b", f"target/{SUB_NAME}.json"], cwd=SUB_DIR)
    acir, size = parse_gates(gates_out)
    vk = json.loads((SUB_DIR / "target" / "vk_json" / "vk.json").read_text())
    return {"m": m, "depth": depth, "compile_s": compile_s,
            "gates": size, "acir": acir, "vk_fields": vk["vk"], "key_hash": vk["hash"]}


def build_tomls(n, k, instance, cycle, out_dir, multiplier=1.1):
    """merkle_builder --hierarchical K -> out_dir/{sub_0..,glue}/Prover.toml."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    matrix = instance["matrix"]
    cost = cycle_cost(matrix, cycle)
    payload = json.dumps({
        "n": n, "k": k,
        "flat_matrix": [matrix[i][j] for i in range(n) for j in range(n)],
        "cycle": cycle, "cost": cost, "threshold": math.ceil(cost * multiplier),
    })
    r = subprocess.run([str(BUILDER_BIN), "--hierarchical", str(k), "--out-dir", str(out_dir)],
                       input=payload, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"merkle_builder failed:\n{r.stderr}")


def prove_segment(seg_idx, tomls_dir, proof_dir, expected_pub_len):
    """Copy sub_<seg> Prover.toml into the segment dir, witness, ZK-recursive prove."""
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
    assert len(pub) == expected_pub_len, f"expected {expected_pub_len} public inputs, got {len(pub)}"
    return {"proof": proof, "pub": pub,
            "witness_s": witness_s, "prove_s": prove_s, "peak_mb": parse_peak_mb(prove_err)}


# ── Outer Prover.toml assembly (A inner) ──────────────────────────────────────

def assemble_exp1(seg, vk_fields, key_hash, m):
    """exp1_a outer: one A proof + its M+4 public inputs; expose root = pub[M+3]."""
    lines = [
        "# Auto-generated by run_recursion_a.py (exp 1, A inner) -- do not edit by hand\n",
        f"verification_key = {_field_array(vk_fields)}",
        f'key_hash         = "{key_hash}"',
        f"proof            = {_field_array(seg['proof'])}",
        f"sub_pub          = {_field_array(seg['pub'])}",
        f'root             = "{seg["pub"][m + 3]}"',
    ]
    return "\n".join(lines) + "\n"


def assemble_exp2(segs, vk_fields, key_hash, tomls_dir, m):
    """exp2_a outer (any K): K A-proofs (2D arrays) + sort-partition witness + boundary."""
    glue = tomllib.loads((tomls_dir / "glue" / "Prover.toml").read_text())
    # Derive per-segment values from the verified A sub_pub vectors (consistent by construction).
    #   sub_pub layout: [sorted_nodes[0..M], start(M), end(M+1), partial_cost(M+2), root(M+3)]
    starts        = [int(s["pub"][m], 16)     for s in segs]
    ends          = [int(s["pub"][m + 1], 16) for s in segs]
    partial_costs = [int(s["pub"][m + 2], 16) for s in segs]
    root          = segs[0]["pub"][m + 3]
    # all_nodes = concatenation of each segment's sorted_nodes chunk (length N = K*M).
    all_nodes = [int(s["pub"][j], 16) for s in segs for j in range(m)]
    proofs_2d   = "[" + ", ".join(_field_array(s["proof"]) for s in segs) + "]"
    sub_pubs_2d = "[" + ", ".join(_field_array(s["pub"])   for s in segs) + "]"
    lines = [
        "# Auto-generated by run_recursion_a.py (exp 2, A inner) -- do not edit by hand\n",
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
        f"all_nodes     = {_int_array(all_nodes)}",
        f'root      = "{root}"',
        f'threshold = "{int(glue["threshold"])}"',
    ]
    return "\n".join(lines) + "\n"


# ── Outer measurement ─────────────────────────────────────────────────────────

def measure_outer(outer_dir, outer_name, skip_prove):
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
        verify_s, _, _, _ = run_cmd(
            ["bb", "verify", "-k", "target/vk/vk",
             "-p", str(proof_dir / "proof"), "-i", str(proof_dir / "public_inputs")], cwd=outer_dir)

    return {"gates": size, "acir": acir, "compile_s": compile_s, "witness_s": witness_s,
            "prove_s": prove_s, "verify_s": verify_s, "proof_bytes": proof_bytes, "peak_mb": peak_mb}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="A-inner recursion micro-experiment driver (ZK, noir-recursive).")
    ap.add_argument("--exp", type=int, choices=[1, 2], required=True)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--k", type=int, default=2, help="Segments K (>= 2); default 2.")
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
    sub_snapshot = sub_src.read_text()
    sub_toml = SUB_DIR / "Prover.toml"
    sub_toml_snapshot = sub_toml.read_text() if sub_toml.exists() else None
    outer_src = outer_dir / "src" / "main.nr"  # patched per (N,K) below; restore after
    outer_snapshot = outer_src.read_text()
    try:
        with open(out_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()

            print(f"[exp {args.exp} A-inner] N={n} K={k} M={m} DEPTH={depth}: compiling A segment + recursive VK ...")
            seg_meta = configure_segment(n, k)
            print(f"  inner A segment: gates={seg_meta['gates']} acir={seg_meta['acir']}")

            # Outer globals: exp1_a needs M (sub_pub length); exp2_a needs N,K,M,DEPTH.
            if args.exp == 1:
                patch_globals(outer_dir / "src" / "main.nr", M=m)
            else:
                patch_globals(outer_dir / "src" / "main.nr", N=n, K=k, M=m, DEPTH=depth)

            for run_idx in range(1, args.runs + 1):
                print(f"  run {run_idx}/{args.runs}: instance + solve + build tomls ...", flush=True)
                instance = generate_instance(n, seed=args.seed + n * 1000 + k * 100 + run_idx)
                cycle    = solve(instance["matrix"])
                cell     = SCRATCH_ROOT / f"exp{args.exp}_n{n}_k{k}_run{run_idx}"
                tomls    = cell / "tomls"
                build_tomls(n, k, instance, cycle, tomls)

                print("  proving inner A segment(s) (bb prove -t noir-recursive, ZK) ...", flush=True)
                if args.exp == 1:
                    seg0 = prove_segment(0, tomls, cell / "proof_0", m + 4)
                    (outer_dir / "Prover.toml").write_text(
                        assemble_exp1(seg0, seg_meta["vk_fields"], seg_meta["key_hash"], m))
                    inner_rows = [("sub_0", seg0)]
                else:
                    segs = [prove_segment(i, tomls, cell / f"proof_{i}", m + 4) for i in range(k)]
                    (outer_dir / "Prover.toml").write_text(
                        assemble_exp2(segs, seg_meta["vk_fields"], seg_meta["key_hash"], tomls, m))
                    inner_rows = [(f"sub_{i}", segs[i]) for i in range(k)]

                print(f"  measuring outer recursive circuit ({outer_name}) ...", flush=True)
                outer = measure_outer(outer_dir, outer_name, args.skip_prove)

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
        sub_src.write_text(sub_snapshot)
        if sub_toml_snapshot is not None:
            sub_toml.write_text(sub_toml_snapshot)
        outer_src.write_text(outer_snapshot)  # restore outer circuit globals to committed default

    print(f"\nDone. Results appended to {out_csv}")


if __name__ == "__main__":
    main()
