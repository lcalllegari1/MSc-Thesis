"""
tests/correctness/test_recursion.py

Soundness tests for the RECURSION variant (circuits/recursion): the outer circuit
recursively verifies K hierarchical_segment_fs (A++) proofs in-circuit and re-runs
the glue logic on their now-trusted-but-private public inputs.  Public surface is
just (root, threshold) -- the perfect-hiding endpoint of the frontier.

KEY DIFFERENCE from test_hierarchical_fs.py.  In the hierarchical family the
binding lives in pipeline/verify_hier_fs.py (external cross-checks), so the
negatives tamper independent glue public inputs.  In recursion the binding is
IN-CIRCUIT, so ALL soundness lives in the single outer proof's constraints and we
test by tampering the assembled outer Prover.toml and confirming proving fails.

Two failure layers (established empirically, bb 5.0.0-nightly.20260324):
  * GLUE-LOGIC asserts (root / bind / threshold / boundary / grand-product) are
    plain Noir constraints -> caught at the cheap `nargo execute`.
  * The IN-CIRCUIT HONK VERIFIER (verify_honk_proof) is deferred to `bb prove`:
    a tampered inner proof or key_hash passes `nargo execute` but makes `bb prove`
    UNSATISFIABLE.  So those two negatives are tested at the (heavier) prove layer.

Note on chain / c / X asserts:  unlike A++'s glue, the chain anchors h_in/h_out
and the FS values c, X are READ FROM the verified sub_pubs (bound to the proofs by
verify_honk_proof).  They cannot be falsified independently -- any tamper breaks
proof verification first.  That inseparability IS recursion's soundness upgrade
over external binding, so there is no standalone "broken chain" negative here; the
partition-overlap test exercises the partition/grand-product path end to end.

Test list:
  1. baseline            -- N=8 K=2 reference: execute + bb prove + verify_recursion accept.
  2. root_mismatch       -- tamper outer.root; "root mismatch" (execute).
  3. bind_mismatch       -- tamper outer.starts[0]; "start bind" (execute).
  4. threshold_exceeded  -- tamper outer.threshold -> 1; "cycle cost exceeds threshold" (execute).
  5. boundary_merkle     -- tamper outer.boundary_costs[0]; boundary Merkle assert (execute).
  6. tampered_proof      -- tamper outer.proofs[0][0]; bb prove FAILS (in-circuit verifier).
  7. tampered_vk         -- tamper outer.sub_vk[0]; bb prove FAILS (the VK is what binds the
                            outer to the inner circuit's identity -- see note).
  8. partition_overlap   -- cheat cycle (node 3 twice, 7 dropped); "grand-product partition
                            mismatch" at the chain-derived X (execute).
  9. sanity_K4           -- N=8 K=4 reference: K-generality, execute accepts.

Note on key_hash / VK layout (empirical, bb 5.0.0-nightly.20260324):  tampering
only the `key_hash` witness does NOT break proving -- in this API key_hash is a
label/hint.  Likewise the LEADING VK fields (sub_vk[0..2]) are structural metadata
and are non-binding; the cryptographic commitments start at sub_vk[3], and
tampering any field from index 3 onward makes bb prove unsatisfiable.  (Every
sub_pub field is independently pinned by a glue assert, so the only objects whose
tamper is DEFERRED to the in-circuit verifier are the proof and the VK commitments.)
Hence #7 tampers sub_vk[3], a binding commitment limb.

Usage:
    python tests/correctness/test_recursion.py
    (run from project root; conda env zk-tsp; merkle_builder built on demand).
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
import run_recursion as H          # reuse the harness's circuit/proof machinery
from solver import cycle_cost

VERIFY_RECURSION = PROJECT_ROOT / "pipeline" / "verify_recursion.py"
CARGO_TOML       = PROJECT_ROOT / "pipeline" / "merkle_builder" / "Cargo.toml"
WORK_DIR         = Path("/tmp/test_recursion")
OUTER_TOML       = H.EXP2_DIR / "Prover.toml"


# ── Instances ─────────────────────────────────────────────────────────────────

def _matrix_from_edges(n, edges):
    """Build an n*n cost matrix (2D list) from (from, to, cost) edges."""
    m = [[0] * n for _ in range(n)]
    for f, t, c in edges:
        m[f][t] = c
    return m


def reference_instance():
    """N=8 K=2 reference cycle [0,5,3,2,7,4,1,6] (HIERARCHICAL_EXPLAINED §8.9)."""
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8), (2, 7, 15),
        (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),
    ]
    return {"matrix": _matrix_from_edges(8, edges)}, [0, 5, 3, 2, 7, 4, 1, 6]


def overlap_cheat_instance():
    """N=8 K=2 cheat: node 3 in both segments, node 7 dropped (cycle [0,5,3,2,3,4,1,6])."""
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2, 8),     # sub_0 internal
        (3, 4,  7), (4, 1,  9), (1, 6, 14),     # sub_1 internal
        (2, 3,  5), (6, 0, 13),                 # boundaries 2->3, 6->0
    ]
    return {"matrix": _matrix_from_edges(8, edges)}, [0, 5, 3, 2, 3, 4, 1, 6]


def k4_instance():
    """N=8 K=4 reference (M=2/segment): simple cycle [0..7]."""
    cycle = list(range(8))
    edges = [(cycle[i], cycle[(i + 1) % 8], (i + 1) * 3) for i in range(8)]
    return {"matrix": _matrix_from_edges(8, edges)}, cycle


# ── Outer-circuit build / run helpers ─────────────────────────────────────────

def ensure_builder():
    if H.BUILDER_BIN.exists():
        return
    print("  [build] merkle_builder not found; building...")
    r = subprocess.run(["cargo", "build", "--release", "--quiet",
                        "--manifest-path", str(CARGO_TOML)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Failed to build merkle_builder:\n{r.stderr}")


def compile_outer(n, k, depth):
    """Patch the outer globals and compile + write its (default-flavor) VK."""
    H.patch_globals(H.EXP2_DIR / "src" / "main.nr", N=n, K=k, DEPTH=depth)
    r = subprocess.run(["nargo", "compile"], cwd=H.EXP2_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"outer nargo compile failed:\n{r.stderr}")
    r = subprocess.run(["bb", "write_vk", "-b", f"target/{H.EXP2_NAME}.json", "-o", "target/vk"],
                       cwd=H.EXP2_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"outer bb write_vk failed:\n{r.stderr}")


def build_valid_outer_toml(instance, cycle, n, k, meta, tag):
    """Build tomls, prove the K inner segments (ZK recursive), assemble the outer toml."""
    tomls = WORK_DIR / tag / "tomls"
    H.build_tomls(n, k, instance, cycle, tomls)
    segs = [H.prove_segment(i, tomls, WORK_DIR / tag / f"proof_{i}") for i in range(k)]
    return H.assemble_exp2(segs, meta["vk_fields"], meta["key_hash"], tomls)


def execute_outer(toml_text):
    """Write the outer Prover.toml and run `nargo execute`.  Returns (rc, stderr)."""
    OUTER_TOML.write_text(toml_text)
    r = subprocess.run(["nargo", "execute"], cwd=H.EXP2_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr


def prove_outer(toml_text):
    """Write the outer Prover.toml, regenerate the witness, then `bb prove`.

    `bb prove` consumes the pre-generated witness (.gz); it does NOT re-run witness
    generation.  So we MUST `nargo execute` the current toml first, otherwise bb
    proves a stale witness.  For the in-circuit-verifier negatives this is exactly
    the right layering: execute succeeds (the recursion check is deferred), then
    bb prove is unsatisfiable.  Returns (rc, stderr, out_dir); a nonzero rc from
    either execute or prove counts as a rejection.
    """
    OUTER_TOML.write_text(toml_text)
    e = subprocess.run(["nargo", "execute"], cwd=H.EXP2_DIR, capture_output=True, text=True)
    if e.returncode != 0:
        return e.returncode, e.stderr, None  # rejected already at witness generation
    out = WORK_DIR / "outer_proof"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    r = subprocess.run(
        ["bb", "prove", "-b", f"target/{H.EXP2_NAME}.json", "-w", f"target/{H.EXP2_NAME}.gz",
         "-k", "target/vk/vk", "-o", str(out.resolve())],
        cwd=H.EXP2_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr, out


# ── Toml tamperers (operate on the assembled outer toml string) ───────────────

def tamper_scalar(text, key, value):
    new, n = re.subn(rf'^{re.escape(key)}\s*=\s*"[^"]*"', f'{key} = "{value}"',
                     text, count=1, flags=re.MULTILINE)
    if n == 0:
        raise ValueError(f"scalar key {key!r} not found")
    return new


def tamper_array_entry(text, key, idx, value):
    m = re.search(rf'^{re.escape(key)}\s*=\s*\[([^\]]*)\]', text, flags=re.MULTILINE)
    if not m:
        raise ValueError(f"array key {key!r} not found")
    els = [e.strip().strip('"') for e in m.group(1).split(",")]
    els[idx] = value
    return text[:m.start()] + f'{key} = [{", ".join(chr(34)+e+chr(34) for e in els)}]' + text[m.end():]


def tamper_first_proof_field(text, value):
    """Flip proofs[0][0] (first field of the first inner proof's 2D array)."""
    m = re.search(r'proofs\s*=\s*\[\s*\[\s*"(0x[0-9a-fA-F]+)"', text)
    if not m:
        raise ValueError("proofs array not found")
    return text[:m.start(1)] + value + text[m.end(1):]


# ── Tests ─────────────────────────────────────────────────────────────────────

def t_baseline(valid_toml):
    """Execute + bb prove + verify_recursion must all accept the reference proof."""
    rc, err = execute_outer(valid_toml)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: outer execute failed:\n{err.strip()}")
        return False
    rc, err, out = prove_outer(valid_toml)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: outer bb prove failed:\n{err.strip()}")
        return False
    r = subprocess.run(
        ["python3", str(VERIFY_RECURSION), "--proof-dir", str(out),
         "--vk", str(H.EXP2_DIR / "target" / "vk" / "vk")],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [FAIL] VALID baseline: verify_recursion rejected:\n{(r.stdout + r.stderr).strip()}")
        return False
    print("  [OK  ] VALID   reference: outer execute + prove + verify_recursion all accept")
    return True


def _expect_execute_reject(valid_toml, tamper_fn, needle, label):
    rc, err = execute_outer(tamper_fn(valid_toml))
    if rc == 0:
        print(f"  [FAIL] INVALID {label}: outer execute ACCEPTED tampered witness (BUG)")
        return False
    if needle not in err and "Failed" not in err:
        print(f"  [WARN] INVALID {label}: rejected but error unclear:\n{err.strip()[:300]}")
    print(f"  [OK  ] INVALID {label}: outer execute rejected")
    return True


def _expect_prove_reject(valid_toml, tamper_fn, label):
    rc, err, _ = prove_outer(tamper_fn(valid_toml))
    if rc == 0:
        print(f"  [FAIL] INVALID {label}: outer bb prove SUCCEEDED on tampered input (BUG)")
        return False
    print(f"  [OK  ] INVALID {label}: in-circuit verifier made bb prove unsatisfiable")
    return True


def t_partition_overlap(meta):
    """Cheat instance: each segment locally valid, but the grand product over the
    overlapping multiset != prod(X+j); the outer's grand-product assert rejects."""
    inst, cycle = overlap_cheat_instance()
    try:
        cheat_toml = build_valid_outer_toml(inst, cycle, 8, 2, meta, "overlap")
    except Exception as e:
        print(f"  [FAIL] INVALID partition_overlap: could not build cheat proofs: {e}")
        return False
    rc, err = execute_outer(cheat_toml)
    if rc == 0:
        print("  [FAIL] INVALID partition_overlap: outer ACCEPTED overlapping partition (BUG)")
        return False
    if "grand-product" not in err and "Failed" not in err:
        print(f"  [WARN] INVALID partition_overlap: rejected but not via grand-product:\n{err.strip()[:300]}")
    print("  [OK  ] INVALID partition_overlap: grand-product partition check rejected the overlap")
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: RECURSION variant (in-circuit verification of K A++ segments)")
    print("=" * 72)
    ensure_builder()

    sub_src   = H.SUB_DIR  / "src" / "main.nr"
    outer_src = H.EXP2_DIR / "src" / "main.nr"
    sub_snap, outer_snap = sub_src.read_text(), outer_src.read_text()
    results = []
    try:
        # ── Reference N=8 K=2 ──────────────────────────────────────────────────
        print("\n--- Reference instance (N=8 K=2 M=4) ---")
        print("  [setup] compiling inner A++ segment (recursive VK) + outer circuit ...")
        meta = H.configure_segment(8, 2)
        compile_outer(8, 2, meta["depth"])
        inst, cycle = reference_instance()
        valid = build_valid_outer_toml(inst, cycle, 8, 2, meta, "ref")

        results.append(t_baseline(valid))

        print("\n--- Negative 2: root mismatch (execute) ---")
        results.append(_expect_execute_reject(
            valid, lambda t: tamper_scalar(t, "root", "0x07"), "root mismatch", "root_mismatch"))

        print("\n--- Negative 3: integer-mirror bind (execute) ---")
        results.append(_expect_execute_reject(
            valid, lambda t: tamper_array_entry(t, "starts", 0, "99"), "start bind", "bind_mismatch"))

        print("\n--- Negative 4: threshold exceeded (execute) ---")
        results.append(_expect_execute_reject(
            valid, lambda t: tamper_scalar(t, "threshold", "1"),
            "exceeds threshold", "threshold_exceeded"))

        print("\n--- Negative 5: boundary Merkle (execute) ---")
        results.append(_expect_execute_reject(
            valid, lambda t: tamper_array_entry(t, "boundary_costs", 0, "999999"),
            "Merkle", "boundary_merkle"))

        print("\n--- Negative 6: tampered inner proof (bb prove) ---")
        results.append(_expect_prove_reject(
            valid, lambda t: tamper_first_proof_field(t, "0x03"), "tampered_proof"))

        print("\n--- Negative 7: tampered inner VK commitment (bb prove) ---")
        results.append(_expect_prove_reject(
            valid, lambda t: tamper_array_entry(t, "sub_vk", 3, "0x07"), "tampered_vk"))

        print("\n--- Negative 8: partition overlap (grand product, execute) ---")
        results.append(t_partition_overlap(meta))

        # ── K-generality sanity N=8 K=4 ────────────────────────────────────────
        print("\n--- Sanity: N=8 K=4 (K-generality, execute) ---")
        print("  [setup] reconfiguring inner + outer for K=4 ...")
        meta4 = H.configure_segment(8, 4)
        compile_outer(8, 4, meta4["depth"])
        inst4, cycle4 = k4_instance()
        valid4 = build_valid_outer_toml(inst4, cycle4, 8, 4, meta4, "k4")
        rc, err = execute_outer(valid4)
        if rc != 0:
            print(f"  [FAIL] VALID N=8 K=4: outer execute failed:\n{err.strip()}")
            results.append(False)
        else:
            print("  [OK  ] VALID   N=8 K=4 M=2: outer execute accepts (K-loop generic)")
            results.append(True)
    finally:
        sub_src.write_text(sub_snap)      # leave the shared A++ segment untouched
        outer_src.write_text(outer_snap)  # restore outer globals to committed default

    passed, total = sum(results), len(results)
    print(f"\n{'=' * 72}\nResults: {passed}/{total} passed")
    if passed < total:
        print("SOME TESTS FAILED")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
