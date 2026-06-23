"""
tests/correctness/test_monolithic_study_pairwise.py

Soundness tests for circuits/monolithic_study_pairwise.

Each test case:
  - Writes a Prover.toml with specific inputs (valid or deliberately broken)
  - Runs nargo execute
  - Asserts the exit code matches expectations (0 = pass, non-zero = fail)

The circuit under test enforces four constraint groups:
  GROUP 1  node index range:    cycle[i] < N
  GROUP 2  pairwise distinct:   cycle[i] != cycle[j] for all i != j
  GROUP 3  cost computation:    sum of edge costs along cycle
  GROUP 4  threshold check:     total_cost <= threshold

A sound circuit must catch *every* case below. If a test marked INVALID
passes (exit code 0), the circuit has a soundness hole.

Usage:
    python tests/correctness/test_monolithic_study_pairwise.py
    (run from project root with the zk-tsp conda env active)
"""

import sys
import os
import subprocess
import math
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent
CIRCUIT_DIR  = PROJECT_ROOT / "circuits" / "monolithic_study_pairwise"
PROVER_TOML  = CIRCUIT_DIR / "Prover.toml"

# Add pipeline to path so we can reuse write_prover_toml
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
    """
    Write Prover.toml with `inputs` and run nargo execute.
    Returns (returncode, stderr).
    """
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
    status = "PASS" if rc == 0 else "FAIL"
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
    """Build a clean inputs dict. If matrix is None, use identity (zero diagonal, 1 elsewhere).

    For INVALID test cases where cycle contains out-of-range indices, the Python
    matrix lookup would raise IndexError before the circuit runs. We catch that and
    fall back to threshold=1 — the circuit will reject at GROUP 1 or GROUP 2 regardless.
    """
    if matrix is None:
        # Simple matrix: all edges cost 1, self-loops cost 0
        matrix = [[0 if i == j else 1 for j in range(n)] for i in range(n)]
    flat = [matrix[i][j] for i in range(n) for j in range(n)]
    try:
        cost = sum(matrix[cycle[i]][cycle[(i + 1) % n]] for i in range(n))
        threshold = math.ceil(cost * (1 + threshold_slack))
    except IndexError:
        # Out-of-range node index: dummy values are fine — the circuit rejects at GROUP 1.
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

    # Baseline: a correct cycle on a uniform-cost graph
    valid_cycle = [0, 1, 2, 3, 4]
    results.append(assert_valid(make_inputs(n, valid_cycle), "correct cycle [0,1,2,3,4]"))

    # Different valid permutation
    results.append(assert_valid(make_inputs(n, [2, 0, 4, 1, 3]), "correct cycle [2,0,4,1,3]"))

    # Threshold exactly equal to cost (tight bound)
    inputs = make_inputs(n, valid_cycle, threshold_slack=0.0)
    inputs["threshold"] = inputs["cost"]   # threshold == cost, still valid
    results.append(assert_valid(inputs, "threshold == cost (tight, still valid)"))

    # Random real instance
    inst = generate_instance(n, seed=1)
    path = solve(inst["matrix"])
    flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
    cost = cycle_cost(inst["matrix"], path)
    inputs_real = {
        "n": n, "cost": cost,
        "threshold": math.ceil(cost * 1.1),
        "cycle": path, "flat_matrix": flat,
    }
    results.append(assert_valid(inputs_real, "random real instance (seed=1)"))

    # ── INVALID cases — GROUP 1: range check ────────────────────────────────

    # One index equals N (out of bounds by 1)
    bad = [0, 1, 2, 3, n]   # index n is out of range
    inputs = make_inputs(n, bad)
    results.append(assert_invalid(inputs, "cycle[4] = N (out of range by 1)"))

    # One index far out of range
    bad = [0, 1, 2, 3, 99]
    inputs = make_inputs(n, bad)
    results.append(assert_invalid(inputs, "cycle[4] = 99 (far out of range)"))

    # ── INVALID cases — GROUP 2: pairwise distinctness ───────────────────────

    # One duplicate at the start
    dup = [0, 0, 2, 3, 4]
    results.append(assert_invalid(make_inputs(n, dup), "cycle[0] == cycle[1] (duplicate)"))

    # Duplicate at the end
    dup = [0, 1, 2, 3, 3]
    results.append(assert_invalid(make_inputs(n, dup), "cycle[3] == cycle[4] (duplicate at end)"))

    # All same node
    dup = [2, 2, 2, 2, 2]
    results.append(assert_invalid(make_inputs(n, dup), "all same node (2,2,2,2,2)"))

    # ── INVALID cases — GROUP 4: threshold check ─────────────────────────────

    # Threshold set to cost - 1 (one below actual)
    inputs = make_inputs(n, valid_cycle)
    inputs["threshold"] = inputs["cost"] - 1
    results.append(assert_invalid(inputs, "threshold = cost - 1 (one too tight)"))

    # Threshold set to 0
    inputs = make_inputs(n, valid_cycle)
    inputs["threshold"] = 0
    results.append(assert_invalid(inputs, "threshold = 0 (always fails unless cost=0)"))

    # ── INVALID cases — GROUP 3+4: tampered matrix ───────────────────────────

    # Tamper one edge on the cycle path to inflate actual cost above threshold
    inputs = make_inputs(n, valid_cycle)
    flat = list(inputs["flat_matrix"])
    # Edge 0->1 is at flat index 0*5+1 = 1; multiply its cost by 1000
    flat[1] = flat[1] * 1000 + 1000
    inputs["flat_matrix"] = flat
    # threshold was set for the original (cheap) matrix, so real cost now >> threshold
    results.append(assert_invalid(inputs, "tampered edge cost inflates cycle above threshold"))

    return results


def run_tests_n1():
    """Edge case: N=1, single-node trivial cycle."""
    n = 1
    print(f"\n=== N={n} (edge case) ===")
    set_circuit_n(n)

    results = []

    # Only valid cycle for N=1 is [0]
    matrix = [[0]]
    inputs = {
        "n": 1, "cost": 0, "threshold": 0,
        "cycle": [0], "flat_matrix": [0],
    }
    results.append(assert_valid(inputs, "trivial single-node cycle [0]"))

    return results


def run_tests_n3():
    """Small-N exhaustive-ish coverage."""
    n = 3
    print(f"\n=== N={n} ===")
    set_circuit_n(n)

    results = []

    results.append(assert_valid(make_inputs(n, [0, 1, 2]), "valid [0,1,2]"))
    results.append(assert_valid(make_inputs(n, [1, 0, 2]), "valid [1,0,2]"))

    # GROUP 2: just two nodes in a 3-cycle — duplicate
    results.append(assert_invalid(make_inputs(n, [0, 1, 1]), "duplicate [0,1,1]"))
    results.append(assert_invalid(make_inputs(n, [0, 0, 0]), "all same [0,0,0]"))

    # GROUP 1: out of range
    results.append(assert_invalid(make_inputs(n, [0, 1, 3]), "index 3 out of range for N=3"))

    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: circuits/monolithic_study_pairwise")
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
