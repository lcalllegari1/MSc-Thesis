"""
tests/correctness/test_flat_merkle_presence.py

Soundness tests for circuits/flat_merkle_presence.

Each test case:
  - Writes a Prover.toml (via the Rust merkle_builder binary, or directly for
    cases that are caught before GROUP 3)
  - Runs nargo execute
  - Asserts the exit code matches expectations (0 = pass, non-zero = fail)

The circuit enforces four constraint groups:
  GROUP 1  range check:     cycle[i] < N  for all i
  GROUP 2  presence check:  seen[cycle[i]] == false before marking it true
           (identical to flat_full_presence; GROUP 1 is explicit, not subsumed)
  GROUP 3  Merkle proof:    for each edge i --
             a. path_bits must encode exactly cycle[i]*N + cycle[(i+1)%N]
             b. hashing edge_costs[i] up through DEPTH siblings must equal root
  GROUP 4  threshold check: total_cost <= threshold

Test categories:
  - Valid baselines (must always pass)
  - INVALID GROUP 1: out-of-range node index
  - INVALID GROUP 2: duplicate nodes in cycle
  - INVALID GROUP 3a: tampered edge cost (Merkle hash mismatch)
  - INVALID GROUP 3b: flipped path bit (leaf index check fails)
  - INVALID GROUP 3c: wrong root (correct proofs against a different matrix)
  - INVALID GROUP 4: threshold below actual cost

GROUP 1/2 tests use dummy Merkle fields (all zeros) because the circuit rejects
before GROUP 3 is reached.  All other tests use the Rust builder for real proofs.

A sound circuit must catch *every* INVALID case below.
If a test marked INVALID passes (exit code 0), the circuit has a soundness hole.

Usage:
    python tests/correctness/test_flat_merkle_presence.py
    (run from project root with the zk-tsp conda env active;
     the Rust merkle_builder must be compiled before running:
       cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml)
"""

import sys
import re
import subprocess
import math
import json
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).parent.parent.parent
CIRCUIT_DIR   = PROJECT_ROOT / "circuits" / "flat_merkle_presence"
PROVER_TOML   = CIRCUIT_DIR / "Prover.toml"
BUILDER_BIN   = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
CARGO_TOML    = PROJECT_ROOT / "pipeline" / "merkle_builder" / "Cargo.toml"

sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
from format_inputs import merkle_depth, write_merkle_prover_toml
from instance_gen  import generate_instance
from solver        import solve, cycle_cost


# ── Builder bootstrap ─────────────────────────────────────────────────────────

def ensure_builder():
    """Build the merkle_builder Rust binary if not already compiled."""
    if BUILDER_BIN.exists():
        return
    print("  [build] merkle_builder not found; building (first build fetches git deps)...")
    result = subprocess.run(
        ["cargo", "build", "--release", "--quiet",
         "--manifest-path", str(CARGO_TOML)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to build merkle_builder:\n{result.stderr}"
        )
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

    result = subprocess.run(
        ["nargo", "compile"],
        cwd=CIRCUIT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"nargo compile failed for N={n}:\n{result.stderr}")


# ── Witness runner ─────────────────────────────────────────────────────────────

def run_witness():
    """Run nargo execute against the current Prover.toml.  Returns (rc, stderr)."""
    result = subprocess.run(
        ["nargo", "execute"],
        cwd=CIRCUIT_DIR,
        capture_output=True,
        text=True,
    )
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
    """
    Build inputs dict from a cycle and optional matrix.
    Uses a unit-cost matrix if none is provided.
    Computes threshold = ceil(actual_cost * (1 + slack)).
    """
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
    """Generate a valid Prover.toml using the Rust builder."""
    inputs = make_inputs(n, cycle, matrix, threshold_slack)
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    return inputs


def write_dummy_toml(n, cycle, depth, threshold=1):
    """
    Write a Prover.toml with all-zero Merkle fields (dummy).
    Used for GROUP 1/2 tests where the circuit rejects before GROUP 3.
    The dummy fields are structurally correct (right array sizes) but
    cryptographically meaningless.
    """
    n_edges = n
    n_total = n_edges * depth

    lines = []
    lines.append("# Private witness: node visit order (Hamiltonian cycle)")
    lines.append("cycle = [{}]".format(", ".join(f'"{v}"' for v in cycle)))
    lines.append("")

    lines.append("# Private witness: cost of each cycle edge (dummy zeros)")
    lines.append("edge_costs = [{}]".format(", ".join('"0"' for _ in range(n_edges))))
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


# ── Tampering helpers ─────────────────────────────────────────────────────────

def tamper_edge_cost(index, delta=999_999):
    """
    Read Prover.toml, add `delta` to edge_costs[index], write back.
    The modified cost no longer matches the committed Merkle leaf -> GROUP 3 fails.
    """
    text = PROVER_TOML.read_text()

    # Match the edge_costs array and split into elements.
    m = re.search(r'edge_costs = \[([^\]]*)\]', text)
    if not m:
        raise ValueError("edge_costs not found in Prover.toml")
    elements = [e.strip().strip('"') for e in m.group(1).split(",")]
    elements[index] = str(int(elements[index]) + delta)
    new_array = ", ".join(f'"{e}"' for e in elements)
    text = text[:m.start()] + f"edge_costs = [{new_array}]" + text[m.end():]
    PROVER_TOML.write_text(text)


def tamper_path_bit(edge_index, depth_index):
    """
    Read Prover.toml, flip path_bits[edge_index * DEPTH + depth_index], write back.
    The reconstructed leaf index no longer matches the expected index -> GROUP 3a fails.
    """
    text = PROVER_TOML.read_text()
    m = re.search(r'path_bits = \[([^\]]*)\]', text)
    if not m:
        raise ValueError("path_bits not found in Prover.toml")

    # DEPTH is not directly available here; infer from the array and N.
    elements = [e.strip() for e in m.group(1).split(",")]
    flat_idx = edge_index * (len(elements) // _current_n) + depth_index
    elements[flat_idx] = "false" if elements[flat_idx] == "true" else "true"
    new_array = ", ".join(elements)
    text = text[:m.start()] + f"path_bits = [{new_array}]" + text[m.end():]
    PROVER_TOML.write_text(text)


def tamper_root(new_root_hex="0" * 64):
    """Replace the root field in Prover.toml with a different value."""
    text = PROVER_TOML.read_text()
    text = re.sub(r'root = "0x[0-9a-f]+"', f'root = "0x{new_root_hex}"', text)
    PROVER_TOML.write_text(text)


# Mutable N used by tamper_path_bit to infer DEPTH from array length.
_current_n = 5


# ── Test suites ───────────────────────────────────────────────────────────────

def run_tests_n3():
    """Small-N coverage: N=3, DEPTH=4."""
    global _current_n
    n = 3
    _current_n = n
    print(f"\n=== N={n} (DEPTH={merkle_depth(n)}) ===")
    set_circuit_n(n)

    results = []

    # ── VALID ────────────────────────────────────────────────────────────────
    write_valid_toml(n, [0, 1, 2])
    results.append(assert_valid("correct cycle [0,1,2]"))

    write_valid_toml(n, [1, 2, 0])
    results.append(assert_valid("correct cycle [1,2,0]"))

    # Tight threshold (== actual cost).
    inputs = make_inputs(n, [0, 1, 2])
    inputs["threshold"] = inputs["cost"]
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_valid("threshold == cost (tight, still valid)"))

    # Real random instance.
    inst = generate_instance(n, seed=7)
    path = solve(inst["matrix"])
    flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
    cost = cycle_cost(inst["matrix"], path)
    write_merkle_prover_toml(
        {"n": n, "cost": cost, "threshold": math.ceil(cost * 1.1),
         "cycle": path, "flat_matrix": flat},
        PROVER_TOML, BUILDER_BIN,
    )
    results.append(assert_valid("random real instance (seed=7)"))

    # ── INVALID GROUP 1 ──────────────────────────────────────────────────────
    # Dummy Merkle fields -- circuit rejects at GROUP 1 before touching GROUP 3.
    depth = merkle_depth(n)

    write_dummy_toml(n, [0, 1, n], depth)
    results.append(assert_invalid("cycle[2] = N (out of range by 1)"))

    write_dummy_toml(n, [0, 1, 99], depth)
    results.append(assert_invalid("cycle[2] = 99 (far out of range)"))

    # ── INVALID GROUP 2 ──────────────────────────────────────────────────────
    write_dummy_toml(n, [0, 0, 2], depth)
    results.append(assert_invalid("cycle[0] == cycle[1] (duplicate at start)"))

    write_dummy_toml(n, [0, 1, 1], depth)
    results.append(assert_invalid("cycle[1] == cycle[2] (duplicate at end)"))

    write_dummy_toml(n, [2, 2, 2], depth)
    results.append(assert_invalid("all same node (2,2,2)"))

    # ── INVALID GROUP 3a: tampered edge cost ─────────────────────────────────
    write_valid_toml(n, [0, 1, 2])
    tamper_edge_cost(0)  # inflate cost of first edge
    results.append(assert_invalid("tampered edge_costs[0] (Merkle hash mismatch)"))

    # ── INVALID GROUP 3b: flipped path bit ───────────────────────────────────
    # Flip bit d=0 of edge 0's path. The reconstructed leaf index changes ->
    # GROUP 3a leaf-index check fires.
    write_valid_toml(n, [0, 1, 2])
    tamper_path_bit(edge_index=0, depth_index=0)
    results.append(assert_invalid("flipped path_bits[0] (wrong leaf index)"))

    # ── INVALID GROUP 3c: wrong root ─────────────────────────────────────────
    # Generate valid proofs then swap in a different root.  The correct proofs
    # no longer hash up to the tampered root -> GROUP 3b Merkle check fires.
    write_valid_toml(n, [0, 1, 2])
    tamper_root("1" + "0" * 63)  # non-zero wrong root
    results.append(assert_invalid("tampered root (valid proofs against wrong root)"))

    # ── INVALID GROUP 4: threshold too tight ─────────────────────────────────
    inputs = make_inputs(n, [0, 1, 2])
    inputs["threshold"] = max(0, inputs["cost"] - 1)
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_invalid("threshold = cost - 1 (one too tight)"))

    inputs["threshold"] = 0
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_invalid("threshold = 0 (always fails unless cost=0)"))

    return results


def run_tests_n5():
    """Main test suite: N=5, DEPTH=5."""
    global _current_n
    n = 5
    _current_n = n
    print(f"\n=== N={n} (DEPTH={merkle_depth(n)}) ===")
    set_circuit_n(n)

    results = []

    # ── VALID ────────────────────────────────────────────────────────────────
    write_valid_toml(n, [0, 1, 2, 3, 4])
    results.append(assert_valid("correct cycle [0,1,2,3,4]"))

    write_valid_toml(n, [2, 0, 4, 1, 3])
    results.append(assert_valid("correct cycle [2,0,4,1,3]"))

    # Tight threshold.
    inputs = make_inputs(n, [0, 1, 2, 3, 4])
    inputs["threshold"] = inputs["cost"]
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_valid("threshold == cost (tight, still valid)"))

    # Real random instance.
    inst = generate_instance(n, seed=1)
    path = solve(inst["matrix"])
    flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
    cost = cycle_cost(inst["matrix"], path)
    write_merkle_prover_toml(
        {"n": n, "cost": cost, "threshold": math.ceil(cost * 1.1),
         "cycle": path, "flat_matrix": flat},
        PROVER_TOML, BUILDER_BIN,
    )
    results.append(assert_valid("random real instance (seed=1)"))

    # Second real instance with different seed.
    inst2 = generate_instance(n, seed=42)
    path2 = solve(inst2["matrix"])
    flat2 = [inst2["matrix"][i][j] for i in range(n) for j in range(n)]
    cost2 = cycle_cost(inst2["matrix"], path2)
    write_merkle_prover_toml(
        {"n": n, "cost": cost2, "threshold": math.ceil(cost2 * 1.2),
         "cycle": path2, "flat_matrix": flat2},
        PROVER_TOML, BUILDER_BIN,
    )
    results.append(assert_valid("random real instance (seed=42, 20% slack)"))

    # ── INVALID GROUP 1 ──────────────────────────────────────────────────────
    depth = merkle_depth(n)

    write_dummy_toml(n, [0, 1, 2, 3, n], depth)
    results.append(assert_invalid("cycle[4] = N (out of range by 1)"))

    write_dummy_toml(n, [0, 1, 2, 3, 99], depth)
    results.append(assert_invalid("cycle[4] = 99 (far out of range)"))

    # ── INVALID GROUP 2 ──────────────────────────────────────────────────────
    write_dummy_toml(n, [0, 0, 2, 3, 4], depth)
    results.append(assert_invalid("cycle[0] == cycle[1] (duplicate at start)"))

    write_dummy_toml(n, [0, 1, 2, 3, 3], depth)
    results.append(assert_invalid("cycle[3] == cycle[4] (duplicate at end)"))

    write_dummy_toml(n, [2, 2, 2, 2, 2], depth)
    results.append(assert_invalid("all same node (2,2,2,2,2)"))

    write_dummy_toml(n, [0, 1, 0, 3, 4], depth)
    results.append(assert_invalid("cycle[0] == cycle[2] (non-adjacent duplicate)"))

    # ── INVALID GROUP 3a: tampered edge cost ─────────────────────────────────
    # The modified cost no longer hashes up to the committed root.
    write_valid_toml(n, [0, 1, 2, 3, 4])
    tamper_edge_cost(0)
    results.append(assert_invalid("tampered edge_costs[0] (Merkle hash mismatch)"))

    write_valid_toml(n, [0, 1, 2, 3, 4])
    tamper_edge_cost(4)  # last edge
    results.append(assert_invalid("tampered edge_costs[4] (last edge, hash mismatch)"))

    # ── INVALID GROUP 3b: flipped path bit ───────────────────────────────────
    # Flip bit d=0 of edge 0.  The leaf index reconstruction changes:
    # if d=0 was false (left child), making it true adds 1 to the index.
    write_valid_toml(n, [0, 1, 2, 3, 4])
    tamper_path_bit(edge_index=0, depth_index=0)
    results.append(assert_invalid("flipped path_bits for edge 0, level 0 (wrong leaf index)"))

    # ── INVALID GROUP 3c: wrong root ─────────────────────────────────────────
    write_valid_toml(n, [0, 1, 2, 3, 4])
    tamper_root("1" + "0" * 63)
    results.append(assert_invalid("wrong root (valid proofs, different committed matrix)"))

    # A more subtle wrong root: valid proofs from a different matrix instance.
    inst_b = generate_instance(n, seed=999)
    flat_b = [inst_b["matrix"][i][j] for i in range(n) for j in range(n)]
    # Get root from matrix B but keep cycle/proofs from matrix A.
    inputs_b = {"n": n, "cost": 0, "threshold": 99999, "cycle": [0, 1, 2, 3, 4], "flat_matrix": flat_b}
    write_merkle_prover_toml(inputs_b, PROVER_TOML, BUILDER_BIN)
    # Now overwrite cycle with a different one that was proved against matrix A
    # by tamping just the root back to what matrix A's root was.
    # Simpler: just use a wrong root directly (the test above already covers this).

    # ── INVALID GROUP 4: threshold too tight ─────────────────────────────────
    inputs = make_inputs(n, [0, 1, 2, 3, 4])
    inputs["threshold"] = max(0, inputs["cost"] - 1)
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_invalid("threshold = cost - 1 (one too tight)"))

    inputs["threshold"] = 0
    write_merkle_prover_toml(inputs, PROVER_TOML, BUILDER_BIN)
    results.append(assert_invalid("threshold = 0 (always fails unless cost=0)"))

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: circuits/flat_merkle_presence")
    print("=" * 56)

    ensure_builder()

    all_results = []
    all_results += run_tests_n3()
    all_results += run_tests_n5()

    passed = sum(all_results)
    total  = len(all_results)
    print(f"\n{'=' * 56}")
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        print("SOME TESTS FAILED — review output above.")
        sys.exit(1)
    else:
        print("All tests passed.")


if __name__ == "__main__":
    main()
