"""
tests/correctness/test_flat_full_presence.py

Soundness tests for circuits/flat_full_presence.

Each test case:
  - Writes a Prover.toml with specific inputs (valid or deliberately broken)
  - Runs nargo execute
  - Asserts the exit code matches expectations (0 = pass, non-zero = fail)

The circuit under test enforces four constraint groups:
  GROUP 1  range check:   cycle[i] < N  for all i
  GROUP 2  presence check: seen[cycle[i]] == false before marking it true
           (unlike flat_full_sort and flat_full_invperm, GROUP 1 is NOT
           subsumed by GROUP 2 -- both are explicit and run as separate loops)
  GROUP 3  cost computation: sum of edge costs along cycle
  GROUP 4  threshold check:  total_cost <= threshold

Test categories:
  - Valid baselines (must always pass)
  - INVALID GROUP 1: out-of-range node index (caught before GROUP 2 runs)
  - INVALID GROUP 2: duplicate nodes in cycle
  - INVALID GROUP 4: threshold below actual cost
  - INVALID GROUP 3+4: tampered cost matrix inflates cost above threshold
  - Edge cases: N=1 (trivial cycle), N=3 (small graph)

A sound circuit must catch *every* INVALID case below.
If a test marked INVALID passes (exit code 0), the circuit has a soundness hole.

Usage:
    python tests/correctness/test_flat_full_presence.py
    (run from project root with the zk-tsp conda env active)
"""

import sys
import subprocess
import math
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
CIRCUIT_DIR  = PROJECT_ROOT / "circuits" / "flat_full_presence"
PROVER_TOML  = CIRCUIT_DIR / "Prover.toml"

sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
from format_inputs import write_prover_toml
from instance_gen  import generate_instance
from solver        import solve, cycle_cost


# ── Helpers ───────────────────────────────────────────────────────────────────

def set_circuit_n(n):
    """Patch the compile-time N and recompile. Called once per N value."""
    import re
    src = CIRCUIT_DIR / "src" / "main.nr"
    text = src.read_text()
    updated = re.sub(
        r"^global N: u32 = \d+;",
        f"global N: u32 = {n};",
        text,
        flags=re.MULTILINE,
    )
    src.write_text(updated)
    result = subprocess.run(
        ["nargo", "compile"],
        cwd=CIRCUIT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"nargo compile failed for N={n}:\n{result.stderr}")


def run_witness(inputs):
    """Write Prover.toml with `inputs` and run nargo execute. Returns (rc, stderr)."""
    write_prover_toml(inputs, PROVER_TOML)
    result = subprocess.run(
        ["nargo", "execute"],
        cwd=CIRCUIT_DIR,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stderr


def assert_valid(inputs, label):
    rc, err = run_witness(inputs)
    marker = "OK  " if rc == 0 else "FAIL"
    print(f"  [{marker}] VALID   {label}")
    if rc != 0:
        print(f"         Unexpected failure:\n{err.strip()}")
    return rc == 0


def assert_invalid(inputs, label):
    rc, err = run_witness(inputs)
    caught = rc != 0
    marker = "OK  " if caught else "FAIL"
    print(f"  [{marker}] INVALID {label}")
    if not caught:
        print(f"         BUG: invalid witness was accepted (soundness hole)")
    return caught


def make_inputs(n, cycle, matrix=None, threshold_slack=0.1):
    """
    Build a complete inputs dict for flat_full_presence.

    No extra witness fields -- the circuit takes only cycle, cost_matrix,
    and threshold (unlike flat_full_invperm which also needs inv_perm).

    For INVALID cycles (out-of-range or duplicate nodes), the Python matrix
    lookup may raise IndexError; we catch it and use threshold=1 since the
    circuit will reject at GROUP 1 or GROUP 2 regardless.
    """
    if matrix is None:
        matrix = [[0 if i == j else 1 for j in range(n)] for i in range(n)]
    flat = [matrix[i][j] for i in range(n) for j in range(n)]
    try:
        cost = sum(matrix[cycle[i]][cycle[(i + 1) % n]] for i in range(n))
        threshold = math.ceil(cost * (1 + threshold_slack))
    except IndexError:
        # Out-of-range node index: dummy values are fine -- circuit rejects at GROUP 1.
        cost = 0
        threshold = 1
    return {
        "n": n,
        "cost": cost,
        "threshold": threshold,
        "cycle": cycle,
        "flat_matrix": flat,
    }


# ── Test cases ────────────────────────────────────────────────────────────────

def run_tests_n5():
    n = 5
    print(f"\n=== N={n} ===")
    set_circuit_n(n)

    results = []

    # ── VALID cases ──────────────────────────────────────────────────────────

    valid_cycle = [0, 1, 2, 3, 4]
    results.append(assert_valid(make_inputs(n, valid_cycle), "correct cycle [0,1,2,3,4]"))

    results.append(assert_valid(make_inputs(n, [2, 0, 4, 1, 3]), "correct cycle [2,0,4,1,3]"))

    # Tight threshold (== cost)
    inputs = make_inputs(n, valid_cycle)
    inputs["threshold"] = inputs["cost"]
    results.append(assert_valid(inputs, "threshold == cost (tight, still valid)"))

    # Random real instance
    inst = generate_instance(n, seed=1)
    path = solve(inst["matrix"])
    flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
    cost = cycle_cost(inst["matrix"], path)
    results.append(assert_valid({
        "n": n, "cost": cost,
        "threshold": math.ceil(cost * 1.1),
        "cycle": path,
        "flat_matrix": flat,
    }, "random real instance (seed=1)"))

    # ── INVALID — GROUP 1: out-of-range node index ────────────────────────────
    # GROUP 1 runs as its own loop before GROUP 2, so these are caught at the
    # range assertion before the presence check is even attempted.

    results.append(assert_invalid(
        make_inputs(n, [0, 1, 2, 3, n]),
        "cycle[4] = N (out of range by 1)"))

    results.append(assert_invalid(
        make_inputs(n, [0, 1, 2, 3, 99]),
        "cycle[4] = 99 (far out of range)"))

    # ── INVALID — GROUP 2: duplicate nodes ───────────────────────────────────
    # These pass GROUP 1 (all indices are in range) but fail GROUP 2: the
    # second visit to a repeated node finds seen[cycle[i]] already true.

    results.append(assert_invalid(
        make_inputs(n, [0, 0, 2, 3, 4]),
        "cycle[0] == cycle[1] (duplicate at start)"))

    results.append(assert_invalid(
        make_inputs(n, [0, 1, 2, 3, 3]),
        "cycle[3] == cycle[4] (duplicate at end)"))

    results.append(assert_invalid(
        make_inputs(n, [2, 2, 2, 2, 2]),
        "all same node (2,2,2,2,2)"))

    results.append(assert_invalid(
        make_inputs(n, [0, 1, 0, 3, 4]),
        "cycle[0] == cycle[2] (duplicate at non-adjacent positions)"))

    # ── INVALID — GROUP 4: threshold too tight ───────────────────────────────

    inputs = make_inputs(n, valid_cycle)
    inputs["threshold"] = inputs["cost"] - 1
    results.append(assert_invalid(inputs, "threshold = cost - 1 (one too tight)"))

    inputs = make_inputs(n, valid_cycle)
    inputs["threshold"] = 0
    results.append(assert_invalid(inputs, "threshold = 0 (always fails unless cost=0)"))

    # ── INVALID — GROUP 3+4: tampered cost matrix ────────────────────────────

    inputs = make_inputs(n, valid_cycle)
    flat = list(inputs["flat_matrix"])
    flat[1] = flat[1] * 1000 + 1000   # edge 0->1, flat index 0*5+1 = 1
    inputs["flat_matrix"] = flat
    results.append(assert_invalid(inputs, "tampered edge cost inflates cycle above threshold"))

    return results


def run_tests_n1():
    """Edge case: N=1, single-node trivial cycle."""
    n = 1
    print(f"\n=== N={n} (edge case) ===")
    set_circuit_n(n)

    results = []
    results.append(assert_valid({
        "n": 1, "cost": 0, "threshold": 0,
        "cycle": [0], "flat_matrix": [0],
    }, "trivial single-node cycle [0]"))
    return results


def run_tests_n3():
    """Small-N coverage."""
    n = 3
    print(f"\n=== N={n} ===")
    set_circuit_n(n)

    results = []

    results.append(assert_valid(make_inputs(n, [0, 1, 2]), "valid [0,1,2]"))
    results.append(assert_valid(make_inputs(n, [1, 0, 2]), "valid [1,0,2]"))

    results.append(assert_invalid(make_inputs(n, [0, 1, 1]), "duplicate [0,1,1]"))
    results.append(assert_invalid(make_inputs(n, [0, 0, 0]), "all same [0,0,0]"))
    results.append(assert_invalid(make_inputs(n, [0, 1, 3]), "index 3 out of range for N=3"))

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: circuits/flat_full_presence")
    print("=" * 52)

    all_results = []
    all_results += run_tests_n1()
    all_results += run_tests_n3()
    all_results += run_tests_n5()

    passed = sum(all_results)
    total  = len(all_results)
    print(f"\n{'=' * 52}")
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        print("SOME TESTS FAILED — review output above.")
        sys.exit(1)
    else:
        print("All tests passed.")


if __name__ == "__main__":
    main()
