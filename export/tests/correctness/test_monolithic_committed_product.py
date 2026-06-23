"""
tests/correctness/test_monolithic_committed_product.py

Soundness tests for circuits/monolithic_committed_product.

Each test case writes a Prover.toml (via the Rust merkle_builder, or a dummy for
cases caught before GROUP 3), runs `nargo execute`, and asserts the exit code
matches expectation (0 = pass, non-zero = fail).

The circuit enforces three constraint groups (NO explicit range check -- the
grand product subsumes it):
  GROUP 2  permutation:  in-circuit Fiat-Shamir X = Poseidon2([c],1) over the
           cycle hash chain, then prod_i (X+cycle[i]) == prod_j (X+j).
           Equal iff {cycle} == {0,...,N-1} as multisets (every node once, all
           in range).  Runs BEFORE the Merkle group.
  GROUP 3  Merkle proof: per edge -- path_bits encode cycle[i]*N+cycle[(i+1)%N],
           and hashing edge_costs[i] up DEPTH siblings equals root.
  GROUP 4  threshold:    total_cost <= threshold.

This is the grand-product counterpart of test_monolithic_committed_sort/presence: GROUP 3
and GROUP 4 are identical, only the permutation mechanism differs.  The headline
GROUP 2 case is a REAL-Merkle non-permutation (e.g. [0,1,0,1]): every edge is a
valid committed leaf so GROUP 3 PASSES, isolating the grand product as the sole
check that rejects the non-permutation -- the soundness property of the gadget.

Usage:
    python tests/correctness/test_monolithic_committed_product.py
    (run from project root with the zk-tsp conda env active; the Rust
     merkle_builder must be compiled --
       cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml)
"""

import sys
import re
import subprocess
import math
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).parent.parent.parent
CIRCUIT_DIR   = PROJECT_ROOT / "circuits" / "monolithic_committed_product"
PROVER_TOML   = CIRCUIT_DIR / "Prover.toml"
BUILDER_BIN   = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
CARGO_TOML    = PROJECT_ROOT / "pipeline" / "merkle_builder" / "Cargo.toml"

sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
from format_inputs import merkle_depth, write_merkle_prover_toml
from instance_gen  import generate_instance
from solver        import solve, cycle_cost


# ── Builder bootstrap ─────────────────────────────────────────────────────────

def ensure_builder():
    if BUILDER_BIN.exists():
        return
    print("  [build] merkle_builder not found; building (first build fetches git deps)...")
    result = subprocess.run(
        ["cargo", "build", "--release", "--quiet", "--manifest-path", str(CARGO_TOML)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to build merkle_builder:\n{result.stderr}")
    print("  [build] Done.")


# ── Circuit compilation ────────────────────────────────────────────────────────

def set_circuit_n(n):
    """Patch global N and global DEPTH in the circuit source and recompile."""
    depth = merkle_depth(n)
    src = CIRCUIT_DIR / "src" / "main.nr"
    text = src.read_text()
    text = re.sub(r"^global N: u32 = \d+;",     f"global N: u32 = {n};",     text, flags=re.MULTILINE)
    text = re.sub(r"^global DEPTH: u32 = \d+;", f"global DEPTH: u32 = {depth};", text, flags=re.MULTILINE)
    src.write_text(text)
    result = subprocess.run(["nargo", "compile"], cwd=CIRCUIT_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"nargo compile failed for N={n}:\n{result.stderr}")


# ── Witness runner ─────────────────────────────────────────────────────────────

def run_witness():
    result = subprocess.run(["nargo", "execute"], cwd=CIRCUIT_DIR, capture_output=True, text=True)
    return result.returncode, result.stderr


def assert_valid(label):
    rc, err = run_witness()
    marker = "OK  " if rc == 0 else "FAIL"
    print(f"  [{marker}] VALID   {label}")
    if rc != 0:
        print(f"         Unexpected failure:\n{err.strip()}")
    return rc == 0


def assert_invalid(label):
    rc, err = run_witness()
    caught = rc != 0
    marker = "OK  " if caught else "FAIL"
    print(f"  [{marker}] INVALID {label}")
    if not caught:
        print(f"         BUG: invalid witness was accepted (soundness hole)")
    return caught


# ── Input helpers ──────────────────────────────────────────────────────────────

def make_inputs(n, cycle, matrix=None, threshold_slack=0.1):
    if matrix is None:
        matrix = [[0 if i == j else 1 for j in range(n)] for i in range(n)]
    flat = [matrix[i][j] for i in range(n) for j in range(n)]
    try:
        cost = sum(matrix[cycle[i]][cycle[(i + 1) % n]] for i in range(n))
        threshold = math.ceil(cost * (1 + threshold_slack))
    except (IndexError, TypeError):
        cost = 0
        threshold = 1
    return {"n": n, "cost": cost, "threshold": threshold, "cycle": cycle, "flat_matrix": flat}


def write_valid_toml(n, cycle, matrix=None, threshold_slack=0.1):
    """Generate a Prover.toml using the Rust builder.  Works for any cycle whose
    entries are < N (incl. non-permutations like [0,1,0,1]): every edge is a real
    committed leaf, so GROUP 3 passes and only GROUP 2 can reject."""
    inputs = make_inputs(n, cycle, matrix, threshold_slack)
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    return inputs


def write_dummy_toml(n, cycle, depth, threshold=1):
    """All-zero Merkle fields; used for non-permutation cycles the grand product
    (GROUP 2) rejects before the Merkle group is reached."""
    n_total = n * depth
    lines = []
    lines.append("# Private witness: node visit order (Hamiltonian cycle)")
    lines.append("cycle = [{}]".format(", ".join(f'"{v}"' for v in cycle)))
    lines.append("")
    lines.append("# Private witness: cost of each cycle edge (dummy zeros)")
    lines.append("edge_costs = [{}]".format(", ".join('"0"' for _ in range(n))))
    lines.append("")
    lines.append("# Private witness: Merkle siblings (dummy zeros)")
    zero_field = '"0x' + "0" * 64 + '"'
    lines.append("siblings = [{}]".format(", ".join(zero_field for _ in range(n_total))))
    lines.append("")
    lines.append("# Private witness: path direction bits (dummy false)")
    lines.append("path_bits = [{}]".format(", ".join("false" for _ in range(n_total))))
    lines.append("")
    lines.append("# Public input: Merkle root (dummy zero)")
    lines.append('root = "0x' + "0" * 64 + '"')
    lines.append("")
    lines.append("# Public input: threshold (dummy)")
    lines.append(f'threshold = "{threshold}"')
    lines.append("")
    PROVER_TOML.write_text("\n".join(lines))


# ── Tampering helpers (GROUP 3/4, shared with the sort variant) ────────────────

def tamper_edge_cost(index, delta=999_999):
    text = PROVER_TOML.read_text()
    m = re.search(r'edge_costs = \[([^\]]*)\]', text)
    if not m:
        raise ValueError("edge_costs not found in Prover.toml")
    elements = [e.strip().strip('"') for e in m.group(1).split(",")]
    elements[index] = str(int(elements[index]) + delta)
    new_array = ", ".join(f'"{e}"' for e in elements)
    text = text[:m.start()] + f"edge_costs = [{new_array}]" + text[m.end():]
    PROVER_TOML.write_text(text)


def tamper_path_bit(edge_index, depth_index):
    text = PROVER_TOML.read_text()
    m = re.search(r'path_bits = \[([^\]]*)\]', text)
    if not m:
        raise ValueError("path_bits not found in Prover.toml")
    elements = [e.strip() for e in m.group(1).split(",")]
    flat_idx = edge_index * (len(elements) // _current_n) + depth_index
    elements[flat_idx] = "false" if elements[flat_idx] == "true" else "true"
    new_array = ", ".join(elements)
    text = text[:m.start()] + f"path_bits = [{new_array}]" + text[m.end():]
    PROVER_TOML.write_text(text)


def tamper_root(new_root_hex="0" * 64):
    text = PROVER_TOML.read_text()
    text = re.sub(r'root = "0x[0-9a-f]+"', f'root = "0x{new_root_hex}"', text)
    PROVER_TOML.write_text(text)


_current_n = 4


# ── Test suites ───────────────────────────────────────────────────────────────

def run_tests(n, perm_cycles, non_perm_real, seeds):
    """Generic suite for a given N.  `perm_cycles` are valid permutations,
    `non_perm_real` are real-Merkle non-permutations (GROUP-2-isolating)."""
    global _current_n
    _current_n = n
    depth = merkle_depth(n)
    print(f"\n=== N={n} (DEPTH={depth}) ===")
    set_circuit_n(n)
    results = []
    identity = list(range(n))

    # ── VALID ────────────────────────────────────────────────────────────────
    for cyc in perm_cycles:
        write_valid_toml(n, cyc)
        results.append(assert_valid(f"permutation {cyc}"))

    inputs = make_inputs(n, identity)
    inputs["threshold"] = inputs["cost"]
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_valid("threshold == cost (tight)"))

    for s in seeds:
        inst = generate_instance(n, seed=s)
        path = solve(inst["matrix"])
        flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
        cost = cycle_cost(inst["matrix"], path)
        write_merkle_prover_toml(
            {"n": n, "cost": cost, "threshold": math.ceil(cost * 1.1),
             "cycle": path, "flat_matrix": flat}, PROVER_TOML, BUILDER_BIN)
        results.append(assert_valid(f"random real instance (seed={s})"))

    # ── INVALID GROUP 2 -- grand product rejects non-permutations ────────────
    # (a) HEADLINE: real Merkle proofs (GROUP 3 passes) -> only the grand product
    #     can catch the non-permutation.
    for cyc in non_perm_real:
        write_valid_toml(n, cyc)
        results.append(assert_invalid(f"real-Merkle non-permutation {cyc} (GROUP 2 only)"))

    # (b) out-of-range and duplicates via dummy Merkle (caught at GROUP 2 early).
    oor = identity[:-1] + [n]
    write_dummy_toml(n, oor, depth)
    results.append(assert_invalid(f"out-of-range node {oor}"))

    oor2 = identity[:-1] + [99]
    write_dummy_toml(n, oor2, depth)
    results.append(assert_invalid(f"far out-of-range node {oor2}"))

    dup = [0] + identity[:-1]  # repeats 0, drops the last node
    write_dummy_toml(n, dup, depth)
    results.append(assert_invalid(f"duplicate node {dup}"))

    allsame = [2] * n
    write_dummy_toml(n, allsame, depth)
    results.append(assert_invalid(f"all same node {allsame}"))

    # ── INVALID GROUP 3 -- Merkle binding ────────────────────────────────────
    write_valid_toml(n, identity)
    tamper_edge_cost(0)
    results.append(assert_invalid("tampered edge_costs[0] (Merkle mismatch)"))

    write_valid_toml(n, identity)
    tamper_path_bit(edge_index=0, depth_index=0)
    results.append(assert_invalid("flipped path_bits[edge 0, level 0] (wrong leaf index)"))

    write_valid_toml(n, identity)
    tamper_root("1" + "0" * 63)
    results.append(assert_invalid("wrong root (valid proofs, different matrix)"))

    # ── INVALID GROUP 4 -- threshold ─────────────────────────────────────────
    inputs = make_inputs(n, identity)
    inputs["threshold"] = max(0, inputs["cost"] - 1)
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_invalid("threshold = cost - 1 (too tight)"))

    inputs["threshold"] = 0
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_invalid("threshold = 0"))

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: circuits/monolithic_committed_product")
    print("=" * 56)
    ensure_builder()

    all_results = []
    # N=4: [0,1,0,1] is the clean GROUP-2-isolating non-permutation (all edges real).
    all_results += run_tests(4, perm_cycles=[[0, 1, 2, 3], [2, 0, 3, 1]],
                             non_perm_real=[[0, 1, 0, 1], [0, 1, 2, 0]], seeds=[7])
    # N=6: more permutation variety.
    all_results += run_tests(6, perm_cycles=[[0, 1, 2, 3, 4, 5], [3, 1, 5, 0, 4, 2]],
                             non_perm_real=[[0, 1, 2, 0, 4, 5]], seeds=[1, 42])

    passed = sum(all_results)
    total  = len(all_results)
    print(f"\n{'=' * 56}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("SOME TESTS FAILED — review output above.")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
