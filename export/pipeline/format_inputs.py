"""
format_inputs.py — Generate Prover.toml for the flat TSP ZKP circuits.

Takes an instance JSON (from instance_gen.py) and a path JSON (from solver.py)
and writes the Prover.toml that nargo expects as witness input.

Prover.toml layout (monolithic_study variants):
  cycle        = ["v0", ..., "v_{N-1}"]              # private: node visit order
  [inv_perm    = ["p0", ..., "p_{N-1}"]  ]           # private: only for monolithic_study_invperm
  cost_matrix  = ["c00", ..., "c_{N-1,N-1}"]         # public: flat N×N costs
  threshold    = "T"                                  # public: cost upper bound

Prover.toml layout (monolithic_study_committed_presence):
  Written by the Rust merkle_builder binary (see pipeline/merkle_builder/).
  Contains: cycle, edge_costs, siblings, path_bits (private),
            root, threshold (public).

All integer values are decimal strings — Noir's TOML parser expects quoted
integers for u32 and u64 fields.  Field values use "0x<hex>" strings.
Bool values (path_bits) are unquoted true/false.

Public inputs also go in Prover.toml (nargo uses it for full witness generation).
The verifier's public_inputs file is extracted automatically by bb prove.

Variant detection:
  If "invperm" appears in the --out path (or the variant parameter), the
  inverse permutation is computed and written as an additional private witness.
  If "committed" appears in the variant name, write_merkle_prover_toml() must be
  used instead; it delegates to the Rust merkle_builder binary.
"""

import json
import math
import argparse
import os
import subprocess


def compute_inv_perm(cycle):
    """
    Compute the inverse permutation of cycle in O(N).
    Returns inv such that inv[v] = i  where  cycle[i] == v.
    Assumes cycle is a valid permutation of {0, ..., N-1}.
    """
    inv = [0] * len(cycle)
    for i, v in enumerate(cycle):
        inv[v] = i
    return inv


def cycle_cost(matrix, path):
    """Total cost of the Hamiltonian cycle including the return edge."""
    n = len(path)
    return sum(matrix[path[i]][path[(i + 1) % n]] for i in range(n))


def format_inputs(instance_path, path_path, multiplier=1.1, variant=""):
    """
    Load instance and path, compute the threshold, and return the dict of
    circuit inputs ready for serialisation to Prover.toml.

    The threshold is set to ceil(actual_cost * multiplier).  Using a value
    slightly above the true cost (default: 10% slack) means:
      - The proof succeeds  (cost <= threshold is satisfiable)
      - The threshold check is non-trivial  (a random cycle would likely fail)

    If "invperm" is found in `variant`, the inverse permutation is computed
    and included in the returned dict so write_prover_toml will emit it.
    """
    with open(instance_path) as f:
        instance = json.load(f)
    with open(path_path) as f:
        path = json.load(f)

    matrix = instance["matrix"]
    n = len(path)
    assert n == instance["metadata"]["n"], "path length must equal instance n"

    # Flatten the N×N cost matrix in row-major order for the circuit's 1-D array.
    flat_matrix = [matrix[i][j] for i in range(n) for j in range(n)]

    # Threshold: actual cycle cost * multiplier, rounded up.
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


def write_prover_toml(inputs, out_path):
    """
    Write Prover.toml with the circuit inputs.

    Noir expects:
      - Arrays as  key = ["v1", "v2", ...]  (quoted decimal strings)
      - Scalars as  key = "value"
    """
    lines = []

    # Private: cycle (array of u32)
    cycle_str = ", ".join(f'"{v}"' for v in inputs["cycle"])
    lines.append(f"# Private witness: node visit order (Hamiltonian cycle)")
    lines.append(f"cycle = [{cycle_str}]")
    lines.append("")

    # Private: inv_perm (array of u32) — only for monolithic_study_invperm
    if "inv_perm" in inputs:
        inv_str = ", ".join(f'"{v}"' for v in inputs["inv_perm"])
        lines.append(f"# Private witness: inverse permutation  (inv_perm[v] = position of node v in cycle)")
        lines.append(f"inv_perm = [{inv_str}]")
        lines.append("")

    # Public: flattened cost matrix (array of u64)
    matrix_str = ", ".join(f'"{v}"' for v in inputs["flat_matrix"])
    lines.append(f"# Public input: N×N cost matrix, flattened row-major")
    lines.append(f"cost_matrix = [{matrix_str}]")
    lines.append("")

    # Public: threshold (u64)
    lines.append(f"# Public input: cycle cost upper bound")
    lines.append(f"# (actual cost = {inputs['cost']}, threshold = {inputs['threshold']})")
    lines.append(f'threshold = "{inputs["threshold"]}"')

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def merkle_depth(n):
    """
    DEPTH for the Poseidon2 Merkle tree over N^2 leaves: ceil(log2(N^2)).

    Equivalent to the Rust computation:
      n_padded = (n*n).next_power_of_two()
      depth    = n_padded.trailing_zeros()

    Both return the same value for all n >= 2.  For n=1: returns 0 (single-leaf
    tree; the root IS the leaf, no siblings).

    Examples: n=5->5, n=8->6, n=10->7, n=20->9, n=50->12, n=100->14.
    """
    n_sq = n * n
    if n_sq <= 1:
        return 0
    return (n_sq - 1).bit_length()


def write_merkle_prover_toml(inputs, out_path, builder_bin, tree_cache=None):
    """
    Write Prover.toml for monolithic_study_committed_presence by calling the Rust merkle_builder.

    The binary reads a JSON payload from stdin:
      { n, flat_matrix, cycle, threshold, cost }
    and writes the full Prover.toml (cycle, edge_costs, siblings, path_bits,
    root, threshold) directly to `out_path`.

    `inputs` must contain: n, flat_matrix, cycle, threshold, cost.
    `builder_bin` is the path to the compiled merkle_builder binary.
    `tree_cache`, if given, is passed as --tree-cache so the Poseidon2 tree is
    built once per instance and reused (see pipeline/instance_cache.py).

    Raises RuntimeError if the binary exits non-zero.
    """
    payload = json.dumps({
        "n":           inputs["n"],
        "flat_matrix": inputs["flat_matrix"],
        "cycle":       inputs["cycle"],
        "threshold":   inputs["threshold"],
        "cost":        inputs["cost"],
    })
    cmd = [str(builder_bin), "--out", str(out_path)]
    if tree_cache is not None:
        cmd += ["--tree-cache", str(tree_cache)]
    result = subprocess.run(
        cmd,
        input=payload,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"merkle_builder failed (exit {result.returncode}):\n{result.stderr}"
        )


def main():
    parser = argparse.ArgumentParser(description="Format ZKP circuit inputs from TSP instance.")
    parser.add_argument("--instance", required=True, help="instance.json from instance_gen.py")
    parser.add_argument("--path",     required=True, help="path.json from solver.py")
    parser.add_argument("--out",      required=True, help="Output Prover.toml path")
    parser.add_argument("--multiplier", type=float, default=1.1,
                        help="Threshold = actual_cost * multiplier (default: 1.1)")
    args = parser.parse_args()

    # Detect variant from the output path so callers don't need an extra flag.
    # e.g. --out circuits/monolithic_study_invperm/Prover.toml  →  variant contains "invperm"
    variant = args.out
    inputs = format_inputs(args.instance, args.path, args.multiplier, variant=variant)
    write_prover_toml(inputs, args.out)

    print(f"n={inputs['n']}  cost={inputs['cost']}  threshold={inputs['threshold']}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
