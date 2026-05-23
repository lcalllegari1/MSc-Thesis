"""
benchmark/run.py  --  Run the ZKP pipeline across a range of N values and record metrics.

For each N the script:
  1. Patches the compile-time global N in the circuit source and recompiles.
  2. Generates a fresh TSP instance and solves it.
  3. Formats the Prover.toml inputs.
  4. Times: nargo execute (witness), bb prove, bb verify.
  5. Records: gate count (bb gates), proof size, peak memory (from bb stderr).

Results are written to a CSV one row at a time so a partial run is never lost.

Usage:
    python benchmark/run.py \\
        --circuit circuits/flat_full_pairwise \\
        --ns 5 8 10 15 20 \\
        --runs 3 \\
        --out results/flat_full_pairwise.csv
"""

import sys
import os
import re
import csv
import json
import math
import time
import argparse
import subprocess
from pathlib import Path

# Import pipeline helpers directly so we avoid subprocess overhead
# for the Python-side steps (instance gen, solve, format).
sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline"))
from instance_gen import generate_instance
from solver import solve, cycle_cost
from format_inputs import write_prover_toml, compute_inv_perm, merkle_depth, write_merkle_prover_toml

# Path to the compiled Rust Merkle builder (used for flat_merkle_presence).
# Build it once with:  cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
MERKLE_BUILDER_BIN = Path(__file__).parent / "merkle_builder" / "target" / "release" / "merkle_builder"

# ── CSV column order ──────────────────────────────────────────────────────────
FIELDNAMES = [
    "variant",       # circuit directory name, e.g. flat_full_pairwise
    "n",             # number of nodes
    "run",           # run index (1-based) within this N
    "circuit_size",  # UltraHonk gate count (from bb gates)
    "acir_opcodes",  # ACIR opcode count (from bb gates)
    "compile_s",     # nargo compile wall time (seconds)
    "witness_s",     # nargo execute wall time (seconds)
    "prove_s",       # bb prove wall time (seconds)
    "verify_s",      # bb verify wall time (seconds)
    "proof_bytes",   # size of the proof file in bytes
    "peak_mb",       # peak memory during bb prove (MiB, from bb stderr)
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_cmd(cmd, cwd=None):
    """Run a command, return (elapsed_seconds, stdout, stderr, returncode)."""
    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    elapsed = time.perf_counter() - t0
    return elapsed, result.stdout, result.stderr, result.returncode


def parse_peak_mb(stderr):
    """
    Extract the peak memory reported by bb from its stderr output.
    bb prints lines like:  'CircuitProve: ... (mem: 25.54 MiB)'
    We take the maximum across all such checkpoints as the peak for that call.
    """
    values = [float(m) for m in re.findall(r"mem: ([\d.]+) MiB", stderr)]
    return max(values) if values else float("nan")


def parse_gates(stdout):
    """
    Parse acir_opcodes and circuit_size from the JSON printed by bb gates.
    Returns (acir_opcodes, circuit_size) as integers.
    """
    data = json.loads(stdout)
    fn = data["functions"][0]
    return fn["acir_opcodes"], fn["circuit_size"]


def set_circuit_n(circuit_dir, n):
    """
    Patch compile-time globals in src/main.nr for benchmark run at size N.

    Always patches:  global N: u32 = <n>;
    Also patches (if present):  global DEPTH: u32 = <depth>;
      DEPTH is used by flat_merkle_presence to set the Merkle tree depth.
      Its value is ceil(log2(n*n)), matching the Rust merkle_builder formula.
      Other circuits do not have a DEPTH global, so the substitution is a no-op.
    """
    src = Path(circuit_dir) / "src" / "main.nr"
    text = src.read_text()

    updated = re.sub(
        r"^global N: u32 = \d+;",
        f"global N: u32 = {n};",
        text,
        flags=re.MULTILINE,
    )
    # Patch DEPTH if the circuit declares it (merkle variants only).
    if re.search(r"^global DEPTH: u32 = \d+;", updated, flags=re.MULTILINE):
        depth = merkle_depth(n)
        updated = re.sub(
            r"^global DEPTH: u32 = \d+;",
            f"global DEPTH: u32 = {depth};",
            updated,
            flags=re.MULTILINE,
        )
    src.write_text(updated)


def circuit_name(circuit_dir):
    """Read the circuit name from Nargo.toml."""
    for line in (Path(circuit_dir) / "Nargo.toml").read_text().splitlines():
        if line.startswith("name"):
            return line.split("=")[1].strip().strip('"')
    raise ValueError(f"No 'name' field found in {circuit_dir}/Nargo.toml")


def make_prover_inputs(instance, path, multiplier=1.1, variant=""):
    """
    Build the dict of circuit inputs from a solved instance.
    Mirrors the logic in format_inputs.py without touching the filesystem.

    If "invperm" is in `variant`, the inverse permutation is computed and
    included so write_prover_toml will emit it as an additional private witness.
    """
    matrix = instance["matrix"]
    n = len(path)
    flat_matrix = [matrix[i][j] for i in range(n) for j in range(n)]
    cost = cycle_cost(matrix, path)
    threshold = math.ceil(cost * multiplier)
    result = {
        "n": n,
        "cost": cost,
        "threshold": threshold,
        "cycle": path,
        "flat_matrix": flat_matrix,
    }
    if "invperm" in variant:
        result["inv_perm"] = compute_inv_perm(path)
    return result


# ── Main benchmark loop ───────────────────────────────────────────────────────

def benchmark(circuit_dir, ns, runs, out_csv, seed):
    circuit_dir = Path(circuit_dir).resolve()
    name = circuit_name(circuit_dir)
    variant = circuit_dir.name

    # Write CSV header only when creating a new file.
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_csv.exists()

    with open(out_csv, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()

        for n in ns:
            print(f"\n[N={n}] patching and compiling...")

            # ── Step 1: patch N and compile (once per N) ─────────────────────
            set_circuit_n(circuit_dir, n)
            compile_s, _, compile_err, rc = run_cmd(["nargo", "compile"], cwd=circuit_dir)

            if rc != 0:
                print(f"  ERROR: compile failed for N={n}:\n{compile_err}")
                continue
            print(f"  compile: {compile_s:.2f}s")

            # ── Step 2: pre-compute the verification key (once per N) ────────
            # Not timed as a metric; it is a one-time setup cost per circuit.
            run_cmd(
                ["bb", "write_vk",
                 "-b", f"target/{name}.json",
                 "-o", "target/vk"],
                cwd=circuit_dir,
            )

            # ── Step 3: gate count (once per N, deterministic) ───────────────
            _, gates_out, _, _ = run_cmd(
                ["bb", "gates", "-b", f"target/{name}.json"],
                cwd=circuit_dir,
            )
            acir_opcodes, circuit_size = parse_gates(gates_out)
            print(f"  gates: circuit_size={circuit_size}, acir_opcodes={acir_opcodes}")

            # ── Steps 4-8: repeated for each run ─────────────────────────────
            for run_idx in range(1, runs + 1):
                print(f"  run {run_idx}/{runs} ...", end=" ", flush=True)

                # Use a different seed per run so each run measures a different
                # instance, not just timing noise on the same one.
                instance_seed = seed + (n * 1000) + run_idx
                instance = generate_instance(n, seed=instance_seed)
                path = solve(instance["matrix"])
                inputs = make_prover_inputs(instance, path, variant=variant)

                # Write Prover.toml inside the circuit directory.
                # Merkle variants delegate to the Rust builder (which computes
                # the tree, root, siblings, and path bits).  All other variants
                # use the Python formatter.
                if "merkle" in variant:
                    if not MERKLE_BUILDER_BIN.exists():
                        raise FileNotFoundError(
                            f"merkle_builder binary not found at {MERKLE_BUILDER_BIN}.\n"
                            "Build it first:\n"
                            "  cargo build --release "
                            "--manifest-path pipeline/merkle_builder/Cargo.toml"
                        )
                    write_merkle_prover_toml(inputs, circuit_dir / "Prover.toml", MERKLE_BUILDER_BIN)
                else:
                    write_prover_toml(inputs, circuit_dir / "Prover.toml")

                # Witness generation
                witness_s, _, witness_err, rc = run_cmd(
                    ["nargo", "execute"], cwd=circuit_dir
                )
                if rc != 0:
                    print(f"FAILED (witness)\n{witness_err}")
                    continue

                # Prove
                prove_s, _, prove_err, rc = run_cmd(
                    ["bb", "prove",
                     "-b", f"target/{name}.json",
                     "-w", f"target/{name}.gz",
                     "-k", "target/vk/vk",
                     "-o", "target/proof"],
                    cwd=circuit_dir,
                )
                if rc != 0:
                    print(f"FAILED (prove)\n{prove_err}")
                    continue
                peak_mb = parse_peak_mb(prove_err)

                # Verify
                verify_s, _, _, rc = run_cmd(
                    ["bb", "verify",
                     "-k", "target/vk/vk",
                     "-p", "target/proof/proof",
                     "-i", "target/proof/public_inputs"],
                    cwd=circuit_dir,
                )
                if rc != 0:
                    print("FAILED (verify)")
                    continue

                # Proof file size
                proof_bytes = (circuit_dir / "target" / "proof" / "proof").stat().st_size

                print(
                    f"witness={witness_s:.2f}s  "
                    f"prove={prove_s:.2f}s  "
                    f"verify={verify_s:.2f}s  "
                    f"mem={peak_mb:.1f}MB  "
                    f"proof={proof_bytes}B"
                )

                writer.writerow({
                    "variant":      variant,
                    "n":            n,
                    "run":          run_idx,
                    "circuit_size": circuit_size,
                    "acir_opcodes": acir_opcodes,
                    "compile_s":    round(compile_s, 4),
                    "witness_s":    round(witness_s, 4),
                    "prove_s":      round(prove_s, 4),
                    "verify_s":     round(verify_s, 4),
                    "proof_bytes":  proof_bytes,
                    "peak_mb":      round(peak_mb, 3),
                })
                # Flush after every row so a Ctrl-C doesn't lose data.
                csvfile.flush()

    print(f"\nDone. Results written to {out_csv}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark a ZKP TSP circuit across N values.")
    parser.add_argument(
        "--circuit", required=True,
        help="Path to the circuit directory (e.g. circuits/flat_full_pairwise)",
    )
    parser.add_argument(
        "--ns", nargs="+", type=int, required=True,
        help="List of N values to benchmark, e.g. --ns 5 8 10 15 20",
    )
    parser.add_argument(
        "--runs", type=int, default=3,
        help="Number of independent runs per N value (default: 3)",
    )
    parser.add_argument(
        "--out", required=True,
        help="Output CSV path, e.g. results/flat_full_pairwise.csv",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Base random seed; each run uses seed + n*1000 + run_index (default: 42)",
    )
    args = parser.parse_args()

    benchmark(args.circuit, args.ns, args.runs, args.out, args.seed)


if __name__ == "__main__":
    main()
