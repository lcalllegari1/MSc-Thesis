"""
tests/correctness/test_hierarchical_a.py

Soundness tests for Variant A (hierarchical TSP, Merkle commitment).
Mirrors the structure of test_flat_merkle_presence.py.

Variant A produces K+1 independent UltraHonk proofs (K sub-proofs of
circuits/hierarchical_segment + 1 glue proof of circuits/hierarchical_glue),
bound by verifier-side cross-checks in pipeline/verify_hier.py.

Test categories (filled incrementally):
  - Valid baseline (must pass: nargo execute K+1 times, bb prove K+1 times,
    verify_hier.py accepts).
  - INVALID (hierarchical-unique) GLUE G2:  segment-overlap — node appears in
    two segments.  Glue's partition check `sort(all_sorted_nodes) == [0..N-1]`
    must reject during `nargo execute` on the glue.
  - INVALID (hierarchical-unique) CROSS-CHECK:  mix sub-proofs from one
    valid cycle with a glue proof from a DIFFERENT valid cycle through the
    same matrix.  Each bb verify accepts (UltraHonk does commit public
    inputs in the FS transcript, so the simpler "tamper the public_inputs
    file" approach fails at bb verify — see below).  Only the verifier
    cross-check on starts/ends catches the inconsistency.
  - INVALID SUB G5 (cost binding): partial_cost != sum(internal edge_costs).
  - INVALID GLUE G3 (boundary Merkle): tampered boundary cost.

A sound implementation must reject every INVALID case.

Initial scope: N=8, K=2, M=4, DEPTH=6.  The source circuits ship at these
sizes; the harness patches N, K, M, DEPTH for larger sweeps later.

Usage:
    python tests/correctness/test_hierarchical_a.py
    (run from project root; conda env zk-tsp;
     the Rust merkle_builder is built on demand if not yet compiled).
"""

import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).parent.parent.parent
SUB_DIR       = PROJECT_ROOT / "circuits" / "hierarchical_segment"
GLUE_DIR      = PROJECT_ROOT / "circuits" / "hierarchical_glue"
SUB_NAME      = "hierarchical_segment"
GLUE_NAME     = "hierarchical_glue"
BUILDER_BIN   = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
CARGO_TOML    = PROJECT_ROOT / "pipeline" / "merkle_builder" / "Cargo.toml"
VERIFY_HIER   = PROJECT_ROOT / "pipeline" / "verify_hier.py"

# Per-test working area.  Cleaned between cases.
WORK_DIR      = Path("/tmp/test_hier_a")


# ── Circuit-size parameterisation (N, K, M, DEPTH) ────────────────────────────

def merkle_depth(n):
    """Match pipeline/format_inputs.py: ceil(log2(n*n)).  Returns 0 for n<=1."""
    return (n * n - 1).bit_length() if n * n > 1 else 0


def _patch_globals(src_path: Path, **values):
    """Patch `global NAME: u32 = NUMBER;` lines for the given globals."""
    text = src_path.read_text()
    for name, value in values.items():
        text = re.sub(
            rf"^global {name}: u32\s*=\s*\d+;",
            f"global {name}: u32 = {value};",
            text, flags=re.MULTILINE,
        )
    src_path.write_text(text)


def configure_circuits(n, k):
    """Patch and recompile both circuits for the given (N, K).  M = N/K."""
    if n % k != 0:
        raise ValueError(f"N={n} must be divisible by K={k}")
    m     = n // k
    depth = merkle_depth(n)
    _patch_globals(SUB_DIR  / "src" / "main.nr", N=n, M=m, DEPTH=depth)
    _patch_globals(GLUE_DIR / "src" / "main.nr", N=n, K=k, DEPTH=depth)
    compile_circuits()


# ── Builder bootstrap ─────────────────────────────────────────────────────────

def ensure_builder():
    """Build the merkle_builder Rust binary if not yet compiled."""
    if BUILDER_BIN.exists():
        return
    print("  [build] merkle_builder not found; building...")
    result = subprocess.run(
        ["cargo", "build", "--release", "--quiet",
         "--manifest-path", str(CARGO_TOML)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to build merkle_builder:\n{result.stderr}")


# ── Compile both circuits (sub + glue) at N=8 K=2 ────────────────────────────

def compile_circuits():
    """Compile both circuits and write the verification keys.  Idempotent."""
    for cdir, cname in [(SUB_DIR, SUB_NAME), (GLUE_DIR, GLUE_NAME)]:
        r = subprocess.run(["nargo", "compile"], cwd=cdir, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"nargo compile failed in {cdir}:\n{r.stderr}")
        r = subprocess.run(
            ["bb", "write_vk", "-b", f"target/{cname}.json", "-o", "target/vk"],
            cwd=cdir, capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"bb write_vk failed in {cdir}:\n{r.stderr}")


# ── Builder driver ────────────────────────────────────────────────────────────

def build_hier_tomls(n, k, flat_matrix, cycle, threshold, cost, out_dir):
    """
    Run merkle_builder --hierarchical K --out-dir.  Writes K+1 Prover.tomls.
    Returns the out_dir path on success.
    """
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    payload = json.dumps({
        "n": n, "flat_matrix": flat_matrix, "cycle": cycle,
        "threshold": threshold, "cost": cost,
    })
    r = subprocess.run(
        [str(BUILDER_BIN), "--hierarchical", str(k), "--out-dir", str(out_dir)],
        input=payload, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"merkle_builder failed (exit {r.returncode}):\n{r.stderr}")
    return out_dir


# ── Witness & proof runners ───────────────────────────────────────────────────

def run_sub_witness(seg_idx, hier_dir):
    """Copy sub_<i>/Prover.toml into the sub-circuit dir and run nargo execute.
    Returns (rc, stderr)."""
    src = Path(hier_dir) / f"sub_{seg_idx}" / "Prover.toml"
    shutil.copy(src, SUB_DIR / "Prover.toml")
    r = subprocess.run(["nargo", "execute"], cwd=SUB_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr


def run_glue_witness(hier_dir):
    """Same for the glue circuit."""
    src = Path(hier_dir) / "glue" / "Prover.toml"
    shutil.copy(src, GLUE_DIR / "Prover.toml")
    r = subprocess.run(["nargo", "execute"], cwd=GLUE_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr


def run_sub_prove(seg_idx, proof_dir):
    """Run bb prove on the sub-circuit (assumes witness already generated).
    Saves proof+public_inputs into proof_dir/sub_<i>/."""
    out = Path(proof_dir) / f"sub_{seg_idx}"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["bb", "prove",
         "-b", f"target/{SUB_NAME}.json",
         "-w", f"target/{SUB_NAME}.gz",
         "-k", "target/vk/vk",
         "-o", str(out.resolve())],
        cwd=SUB_DIR, capture_output=True, text=True,
    )
    return r.returncode, r.stderr


def run_glue_prove(proof_dir):
    out = Path(proof_dir) / "glue"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["bb", "prove",
         "-b", f"target/{GLUE_NAME}.json",
         "-w", f"target/{GLUE_NAME}.gz",
         "-k", "target/vk/vk",
         "-o", str(out.resolve())],
        cwd=GLUE_DIR, capture_output=True, text=True,
    )
    return r.returncode, r.stderr


def run_verify_hier(proof_dir, n, k):
    """Run verify_hier.py; return (rc, combined_output)."""
    r = subprocess.run(
        ["python3", str(VERIFY_HIER),
         "--proof-dir", str(proof_dir),
         "--n", str(n), "--k", str(k),
         "--sub-vk", str(SUB_DIR / "target" / "vk" / "vk"),
         "--glue-vk", str(GLUE_DIR / "target" / "vk" / "vk")],
        capture_output=True, text=True,
    )
    return r.returncode, (r.stdout + r.stderr)


# ── Reference instance (HIERARCHICAL_EXPLAINED.md §8.9, N=8 K=2 M=4) ─────────

def reference_instance():
    """The N=8, K=2 instance with documented cycle and 8 edge costs."""
    n = 8
    flat = [0] * (n * n)
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8), (2, 7, 15),
        (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),
    ]
    for f, t, c in edges:
        flat[f * n + t] = c
    return {
        "n": n, "k": 2,
        "flat_matrix": flat,
        "cycle": [0, 5, 3, 2, 7, 4, 1, 6],
        "cost": 92, "threshold": 100,
    }


# ── Test runner helpers ───────────────────────────────────────────────────────

def assert_baseline_passes():
    """Build proofs for the reference instance and confirm verify_hier accepts."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "ref" / "tomls"
    proof_dir = WORK_DIR / "ref" / "proofs"
    if proof_dir.exists():
        shutil.rmtree(proof_dir)

    build_hier_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                     inst["threshold"], inst["cost"], hier_dir)

    # K sub-proofs.
    for i in range(inst["k"]):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] VALID baseline: sub_{i} witness failed:\n{err.strip()}")
            return False
        rc, err = run_sub_prove(i, proof_dir)
        if rc != 0:
            print(f"  [FAIL] VALID baseline: sub_{i} prove failed:\n{err.strip()}")
            return False

    # Glue.
    rc, err = run_glue_witness(hier_dir)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: glue witness failed:\n{err.strip()}")
        return False
    rc, err = run_glue_prove(proof_dir)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: glue prove failed:\n{err.strip()}")
        return False

    # Cross-check verifier.
    rc, out = run_verify_hier(proof_dir, inst["n"], inst["k"])
    if rc != 0:
        print(f"  [FAIL] VALID baseline: verify_hier rejected:\n{out.strip()}")
        return False

    print("  [OK  ] VALID   reference instance: K+1 proofs + cross-checks all pass")
    return True


def assert_overlap_rejected():
    """
    Negative test 1 (hierarchical-unique): node 3 in both segments.
    Cheating cycle [0,5,3,2,3,4,1,6] -- node 3 appears in sub_0 and sub_1;
    node 7 is dropped entirely.  Both sub-proofs are individually valid
    (each segment is a 4-node path on distinct-within-segment nodes), but
    the glue's G2 partition check must reject during nargo execute because
    sort([0,2,3,5,1,3,4,6]) = [0,1,2,3,3,4,5,6] != [0..7] (3 twice, 5 and 7
    missing).
    """
    n, k = 8, 2
    # Doctored matrix: include all 8 edges of the cheating cycle.
    # Edges needed: 0->5, 5->3, 3->2 (sub_0 internal),
    #               3->4, 4->1, 1->6 (sub_1 internal),
    #               2->3 (boundary 0->1), 6->0 (boundary 1->0).
    flat = [0] * (n * n)
    cheat_edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8),
        (3, 4,  7), (4, 1,  9), (1, 6, 14),
        (2, 3,  5), (6, 0, 13),
    ]
    for f, t, c in cheat_edges:
        flat[f * n + t] = c

    cheat_cycle = [0, 5, 3, 2, 3, 4, 1, 6]
    cost_sum = sum(c for _, _, c in cheat_edges)

    hier_dir = WORK_DIR / "overlap" / "tomls"
    build_hier_tomls(n, k, flat, cheat_cycle, threshold=999, cost=cost_sum,
                     out_dir=hier_dir)

    # Each sub-proof witness should still succeed -- they don't know about overlap.
    for i in range(k):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] INVALID overlap: sub_{i} unexpectedly rejected witness:")
            print(f"         {err.strip()}")
            return False

    # Glue witness must reject (partition check fires).
    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID overlap: glue accepted witness (BUG: soundness hole in glue G2)")
        return False
    if "partition" not in err and "Failed constraint" not in err:
        # Either error message is acceptable; just sanity-check it's not some
        # other unrelated failure.
        print(f"  [WARN] INVALID overlap: glue rejected but error doesn't mention partition:\n{err.strip()}")
    print("  [OK  ] INVALID overlap: glue G2 partition check rejected the cheating cycle")
    return True


# ── TOML tamperers (post-hoc modifications to a Prover.toml) ────────────────

def tamper_toml_scalar(path: Path, key: str, new_value: str):
    """Replace `<key> = "<old>"` with `<key> = "<new>"` in a Prover.toml."""
    text = path.read_text()
    pattern = rf'^{re.escape(key)}\s*=\s*"[^"]*"'
    new = re.subn(pattern, f'{key} = "{new_value}"', text, count=1, flags=re.MULTILINE)
    if new[1] == 0:
        raise ValueError(f"scalar key {key!r} not found in {path}")
    path.write_text(new[0])


def tamper_toml_array_entry(path: Path, key: str, idx: int, new_value: str):
    """In `<key> = ["v0", "v1", ...]`, replace element idx with new_value."""
    text = path.read_text()
    m = re.search(rf'^{re.escape(key)}\s*=\s*\[([^\]]*)\]', text, flags=re.MULTILINE)
    if not m:
        raise ValueError(f"array key {key!r} not found in {path}")
    elements = [e.strip().strip('"') for e in m.group(1).split(",")]
    elements[idx] = new_value
    new_array = ", ".join(f'"{e}"' for e in elements)
    text = text[:m.start()] + f"{key} = [{new_array}]" + text[m.end():]
    path.write_text(text)


def assert_cost_binding_rejected():
    """
    Negative test 3 (inherited from flat_merkle): sub G5 cost binding.
    Tamper sub_0's partial_cost from 30 to 99.  Real sum of internal edge
    costs is 30, so G5's `sum == partial_cost` assertion must fail during
    `nargo execute`.
    """
    inst = reference_instance()
    hier_dir = WORK_DIR / "cost_bind" / "tomls"
    build_hier_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                     inst["threshold"], inst["cost"], hier_dir)
    # Tamper sub_0.partial_cost: 30 -> 99.
    tamper_toml_scalar(hier_dir / "sub_0" / "Prover.toml", "partial_cost", "99")

    rc, err = run_sub_witness(0, hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID cost binding: sub_0 accepted tampered partial_cost (BUG)")
        return False
    if "partial_cost" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID cost binding: rejected but error doesn't mention partial_cost:\n{err.strip()}")
    print("  [OK  ] INVALID cost binding: sub G5 rejected mismatched partial_cost")
    return True


def assert_boundary_merkle_rejected():
    """
    Negative test 4 (inherited from flat_merkle): glue G3 boundary Merkle.
    Tamper glue.boundary_costs[0] from 15 to 5.  The hash chain over a
    different leaf value yields a different Merkle root, so G3's
    `current == root` assertion must fail during `nargo execute`.
    """
    inst = reference_instance()
    hier_dir = WORK_DIR / "boundary_merkle" / "tomls"
    build_hier_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                     inst["threshold"], inst["cost"], hier_dir)
    # Tamper glue.boundary_costs[0]: 15 -> 5.
    tamper_toml_array_entry(hier_dir / "glue" / "Prover.toml",
                            "boundary_costs", 0, "5")

    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID boundary Merkle: glue accepted tampered boundary cost (BUG)")
        return False
    if "Merkle" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID boundary Merkle: rejected but error doesn't mention Merkle:\n{err.strip()}")
    print("  [OK  ] INVALID boundary Merkle: glue G3 rejected tampered boundary cost")
    return True


def assert_baseline_witness_passes_at(n, k):
    """
    Witness-only sanity check at (N, K) other than (8, 2).  Builds a synthetic
    instance with a trivial cycle [0, 1, ..., N-1] through a matrix where only
    those N cycle edges have nonzero cost.  Runs `nargo execute` on K sub-
    circuits + glue.  No bb prove — purpose is to confirm patched circuits
    still accept valid witnesses at larger sizes, not to benchmark.

    Synthetic over solver-generated keeps this script's dependencies to the
    Python stdlib (no numpy needed in the test runner's env).
    """
    cycle = list(range(n))                          # 0 -> 1 -> 2 -> ... -> N-1 -> 0
    flat  = [0] * (n * n)
    cost  = 0
    for i in range(n):
        c = (i + 1) * 3                              # arbitrary positive cost per edge
        flat[cycle[i] * n + cycle[(i + 1) % n]] = c
        cost += c

    hier_dir = WORK_DIR / f"n{n}_k{k}" / "tomls"
    build_hier_tomls(n, k, flat, cycle,
                     threshold=math.ceil(cost * 1.1), cost=cost,
                     out_dir=hier_dir)

    for i in range(k):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] VALID N={n} K={k}: sub_{i} witness failed:\n{err.strip()}")
            return False
    rc, err = run_glue_witness(hier_dir)
    if rc != 0:
        print(f"  [FAIL] VALID N={n} K={k}: glue witness failed:\n{err.strip()}")
        return False
    print(f"  [OK  ] VALID   N={n} K={k} M={n//k}: K+1 witnesses all generated")
    return True


def assert_cross_check_rejected():
    """
    Negative test 2 (hierarchical-unique): two valid proof sets, mixed.

    Both sets share the SAME matrix (same root).  Set A's cycle is the
    reference [0,5,3,2,7,4,1,6]; Set B's cycle is [0,5,3,2,4,1,6,7] (same
    sub_0 segment, different sub_1 segment).  The attacker submits:
        sub_0  := from Set A  (=Set B; segments identical)
        sub_1  := from Set A  (start_node = 7)
        glue   := from Set B  (starts = [0, 4]; declares sub_1 starts at 4)

    Each proof is internally consistent and bb verify accepts all three.
    The cross-check `glue.starts[1] == sub_1.start_node` (4 vs 7) catches
    the inconsistency.  Without it, the verifier would believe a cycle that
    no single prover ever actually executed.
    """
    n, k = 8, 2

    # Shared matrix: a superset of edges needed by both cycles.
    # Set A uses: 0->5, 5->3, 3->2, 2->7, 7->4, 4->1, 1->6, 6->0 (the documented ref).
    # Set B uses: 0->5, 5->3, 3->2, 2->4, 4->1, 1->6, 6->7, 7->0.
    # Both sets share 0->5, 5->3, 3->2, 4->1, 1->6.  Extras: 2->7, 7->4, 6->0
    # (Set A only) and 2->4, 6->7, 7->0 (Set B only).
    flat = [0] * (n * n)
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8),
        (2, 7, 15), (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),  # set A
        (2, 4,  1), (6, 7,  1), (7, 0,  1),                            # set B extras
    ]
    for f, t, c in edges:
        flat[f * n + t] = c

    # --- Set A: build proofs for [0,5,3,2,7,4,1,6] ---------------------------
    cycle_a = [0, 5, 3, 2, 7, 4, 1, 6]
    cost_a  = 92
    set_a_tomls  = WORK_DIR / "xcheck" / "set_a" / "tomls"
    set_a_proofs = WORK_DIR / "xcheck" / "set_a" / "proofs"
    if set_a_proofs.exists(): shutil.rmtree(set_a_proofs)
    build_hier_tomls(n, k, flat, cycle_a, threshold=200, cost=cost_a, out_dir=set_a_tomls)
    for i in range(k):
        rc, err = run_sub_witness(i, set_a_tomls)
        if rc != 0: raise RuntimeError(f"set A sub_{i} witness failed:\n{err}")
        rc, err = run_sub_prove(i, set_a_proofs)
        if rc != 0: raise RuntimeError(f"set A sub_{i} prove failed:\n{err}")
    rc, err = run_glue_witness(set_a_tomls)
    if rc != 0: raise RuntimeError(f"set A glue witness failed:\n{err}")
    rc, err = run_glue_prove(set_a_proofs)
    if rc != 0: raise RuntimeError(f"set A glue prove failed:\n{err}")

    # --- Set B: build proofs for [0,5,3,2,4,1,6,7] ---------------------------
    cycle_b = [0, 5, 3, 2, 4, 1, 6, 7]
    cost_b  = 10 + 12 + 8 + 1 + 9 + 14 + 1 + 1  # 56
    set_b_tomls  = WORK_DIR / "xcheck" / "set_b" / "tomls"
    set_b_proofs = WORK_DIR / "xcheck" / "set_b" / "proofs"
    if set_b_proofs.exists(): shutil.rmtree(set_b_proofs)
    build_hier_tomls(n, k, flat, cycle_b, threshold=200, cost=cost_b, out_dir=set_b_tomls)
    rc, err = run_glue_witness(set_b_tomls)
    if rc != 0: raise RuntimeError(f"set B glue witness failed:\n{err}")
    rc, err = run_glue_prove(set_b_proofs)
    if rc != 0: raise RuntimeError(f"set B glue prove failed:\n{err}")

    # --- Mix: sub_0+sub_1 from A, glue from B ------------------------------
    mixed = WORK_DIR / "xcheck" / "mixed"
    if mixed.exists(): shutil.rmtree(mixed)
    (mixed / "sub_0").mkdir(parents=True)
    (mixed / "sub_1").mkdir(parents=True)
    (mixed / "glue").mkdir(parents=True)
    for name in ("proof", "public_inputs"):
        shutil.copy(set_a_proofs / "sub_0" / name, mixed / "sub_0" / name)
        shutil.copy(set_a_proofs / "sub_1" / name, mixed / "sub_1" / name)
        shutil.copy(set_b_proofs / "glue"  / name, mixed / "glue"  / name)

    # --- Verify ---------------------------------------------------------------
    rc, out = run_verify_hier(mixed, n, k)
    if rc == 0:
        print("  [FAIL] INVALID cross-check: verify_hier accepted mixed proofs (BUG)")
        print(out)
        return False

    # Confirm rejection came from the cross-check, not bb verify.
    if "cross-checks rejected" not in out:
        print("  [WARN] INVALID cross-check: rejected, but not via cross-check step.")
        print(out)
        # Still counts as "rejected" — but we'd want to know why.
    if "start mismatch at segment 1" not in out:
        print("  [WARN] INVALID cross-check: rejected but error doesn't pinpoint starts[1].")
        print(out)
    print("  [OK  ] INVALID cross-check: verify_hier rejected the mixed-cycle proof set")
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: Variant A (hierarchical TSP, Merkle commitment)")
    print("=" * 64)

    ensure_builder()

    results = []

    print("\n--- Reference instance (N=8 K=2 M=4) ---")
    print("  [setup] configuring circuits for N=8 K=2 ...")
    configure_circuits(8, 2)
    results.append(assert_baseline_passes())

    print("\n--- Negative test 1: segment overlap (hierarchical-unique) ---")
    results.append(assert_overlap_rejected())

    print("\n--- Negative test 2: cross-check mismatch (hierarchical-unique) ---")
    results.append(assert_cross_check_rejected())

    print("\n--- Negative test 3: cost binding (inherited from flat_merkle) ---")
    results.append(assert_cost_binding_rejected())

    print("\n--- Negative test 4: boundary Merkle (inherited from flat_merkle) ---")
    results.append(assert_boundary_merkle_rejected())

    print("\n--- Sanity check: N=48 K=4 (witness only) ---")
    print("  [setup] configuring circuits for N=48 K=4 ...")
    configure_circuits(48, 4)
    results.append(assert_baseline_witness_passes_at(48, 4))

    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 64}\nResults: {passed}/{total} passed")
    if passed < total:
        print("SOME TESTS FAILED")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
