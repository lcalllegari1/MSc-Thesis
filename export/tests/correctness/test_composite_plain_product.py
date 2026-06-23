"""
tests/correctness/test_composite_plain_product.py

Soundness tests for Variant A++ (hierarchical TSP, Merkle commitment, partition
HIDDEN via grand-product multiset equality + in-circuit Fiat-Shamir).
Mirrors test_composite_plain_sort.py; replaces A-specific cases with A++ ones.

A++ produces K+1 independent UltraHonk proofs (K sub-proofs of
circuits/composite_plain_product_segment + 1 glue proof of composite_plain_product_glue), bound by
verifier-side cross-checks in pipeline/verify_composite_plain_product.py.

Test list (HIER_FS_IMPL.md sec. 8.1):
  1. baseline               -- reference N=8 K=2 instance passes end to end.
  2. cost_binding (inherit) -- tamper sub_0.partial_cost; sub G4 rejects (execute).
  3. boundary_merkle (inh.) -- tamper glue.boundary_costs[0]; glue G6 rejects.
  4. cross_check_c (NEW)    -- mix sub-proofs from cycle A with glue from cycle B
                               (same matrix); verify_composite_plain_product rejects on c (and X).
  5. bad_P_i (NEW)          -- tamper sub_0.P_i; sub G6 rejects (execute).
  6. broken_chain (NEW)     -- tamper glue.h_ins[1]; glue G2 rejects (execute).
  7. partition_overlap (NEW)-- node 3 in both segments; glue G5 grand-product check
                               rejects via Schwartz-Zippel at the chain-derived X.
  8. sanity_N48_K4          -- witness-only at a larger size.

Soundness arguments NOT testable as code (would require breaking Poseidon2):
  - Fixed-X grand-product attack: if X were chosen before the prover committed, a
    fake partition with matching products could be constructed.  The in-circuit FS
    chain (G5/G7 in subs, G1-G4 in glue) makes X = Poseidon2(c) unforgeable.
  - Grinding for a Schwartz-Zippel collision: ~2^254/N Poseidon2 evals.  Infeasible.
  See HIERARCHICAL_EXPLAINED.md sec. 9.10 / 7.

Test #7 is the A++ analogue of A's segment-overlap test.  The mechanism differs
(grand product vs sort) but the perturbation and outcome match: it only fails
because Schwartz-Zippel applies at the unforgeable X.

Usage:
    python tests/correctness/test_composite_plain_product.py
    (run from project root; conda env zk-tsp; merkle_builder built on demand).
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
SUB_DIR       = PROJECT_ROOT / "circuits" / "composite_plain_product_segment"
GLUE_DIR      = PROJECT_ROOT / "circuits" / "composite_plain_product_glue"
SUB_NAME      = "composite_plain_product_segment"
GLUE_NAME     = "composite_plain_product_glue"
BUILDER_BIN   = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
CARGO_TOML    = PROJECT_ROOT / "pipeline" / "merkle_builder" / "Cargo.toml"
VERIFY_HIER_FS = PROJECT_ROOT / "pipeline" / "verify_composite_plain_product.py"

WORK_DIR      = Path("/tmp/test_composite_plain_product")


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
        ["cargo", "build", "--release", "--quiet", "--manifest-path", str(CARGO_TOML)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to build merkle_builder:\n{result.stderr}")


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

def build_composite_plain_product_tomls(n, k, flat_matrix, cycle, threshold, cost, out_dir):
    """Run merkle_builder --composite-plain-product K --out-dir.  Writes K+1 Prover.tomls."""
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    payload = json.dumps({
        "n": n, "flat_matrix": flat_matrix, "cycle": cycle,
        "threshold": threshold, "cost": cost,
    })
    r = subprocess.run(
        [str(BUILDER_BIN), "--composite-plain-product", str(k), "--out-dir", str(out_dir)],
        input=payload, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"merkle_builder failed (exit {r.returncode}):\n{r.stderr}")
    return out_dir


# ── Witness & proof runners ───────────────────────────────────────────────────

def run_sub_witness(seg_idx, hier_dir):
    src = Path(hier_dir) / f"sub_{seg_idx}" / "Prover.toml"
    shutil.copy(src, SUB_DIR / "Prover.toml")
    r = subprocess.run(["nargo", "execute"], cwd=SUB_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr


def run_glue_witness(hier_dir):
    src = Path(hier_dir) / "glue" / "Prover.toml"
    shutil.copy(src, GLUE_DIR / "Prover.toml")
    r = subprocess.run(["nargo", "execute"], cwd=GLUE_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr


def run_sub_prove(seg_idx, proof_dir):
    out = Path(proof_dir) / f"sub_{seg_idx}"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["bb", "prove", "-b", f"target/{SUB_NAME}.json", "-w", f"target/{SUB_NAME}.gz",
         "-k", "target/vk/vk", "-o", str(out.resolve())],
        cwd=SUB_DIR, capture_output=True, text=True,
    )
    return r.returncode, r.stderr


def run_glue_prove(proof_dir):
    out = Path(proof_dir) / "glue"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["bb", "prove", "-b", f"target/{GLUE_NAME}.json", "-w", f"target/{GLUE_NAME}.gz",
         "-k", "target/vk/vk", "-o", str(out.resolve())],
        cwd=GLUE_DIR, capture_output=True, text=True,
    )
    return r.returncode, r.stderr


def run_verify_composite_plain_product(proof_dir, n, k):
    r = subprocess.run(
        ["python3", str(VERIFY_HIER_FS),
         "--proof-dir", str(proof_dir), "--n", str(n), "--k", str(k),
         "--sub-vk", str(SUB_DIR / "target" / "vk" / "vk"),
         "--glue-vk", str(GLUE_DIR / "target" / "vk" / "vk")],
        capture_output=True, text=True,
    )
    return r.returncode, (r.stdout + r.stderr)


# ── Reference instance (HIERARCHICAL_EXPLAINED.md §8.9 / §9.13, N=8 K=2 M=4) ──

def reference_instance():
    n = 8
    flat = [0] * (n * n)
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8), (2, 7, 15),
        (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),
    ]
    for f, t, c in edges:
        flat[f * n + t] = c
    return {
        "n": n, "k": 2, "flat_matrix": flat,
        "cycle": [0, 5, 3, 2, 7, 4, 1, 6],
        "cost": 92, "threshold": 100,
    }


# ── TOML tamperers ──────────────────────────────────────────────────────────

def tamper_toml_scalar(path: Path, key: str, new_value: str):
    text = path.read_text()
    pattern = rf'^{re.escape(key)}\s*=\s*"[^"]*"'
    new = re.subn(pattern, f'{key} = "{new_value}"', text, count=1, flags=re.MULTILINE)
    if new[1] == 0:
        raise ValueError(f"scalar key {key!r} not found in {path}")
    path.write_text(new[0])


def tamper_toml_array_entry(path: Path, key: str, idx: int, new_value: str):
    text = path.read_text()
    m = re.search(rf'^{re.escape(key)}\s*=\s*\[([^\]]*)\]', text, flags=re.MULTILINE)
    if not m:
        raise ValueError(f"array key {key!r} not found in {path}")
    elements = [e.strip().strip('"') for e in m.group(1).split(",")]
    elements[idx] = new_value
    new_array = ", ".join(f'"{e}"' for e in elements)
    text = text[:m.start()] + f"{key} = [{new_array}]" + text[m.end():]
    path.write_text(text)


# ── Tests ─────────────────────────────────────────────────────────────────────

def assert_baseline_passes():
    """Build proofs for the reference instance; verify_composite_plain_product must accept."""
    inst = reference_instance()
    hier_dir  = WORK_DIR / "ref" / "tomls"
    proof_dir = WORK_DIR / "ref" / "proofs"
    if proof_dir.exists():
        shutil.rmtree(proof_dir)

    build_composite_plain_product_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                        inst["threshold"], inst["cost"], hier_dir)

    for i in range(inst["k"]):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] VALID baseline: sub_{i} witness failed:\n{err.strip()}")
            return False
        rc, err = run_sub_prove(i, proof_dir)
        if rc != 0:
            print(f"  [FAIL] VALID baseline: sub_{i} prove failed:\n{err.strip()}")
            return False

    rc, err = run_glue_witness(hier_dir)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: glue witness failed:\n{err.strip()}")
        return False
    rc, err = run_glue_prove(proof_dir)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: glue prove failed:\n{err.strip()}")
        return False

    rc, out = run_verify_composite_plain_product(proof_dir, inst["n"], inst["k"])
    if rc != 0:
        print(f"  [FAIL] VALID baseline: verify_composite_plain_product rejected:\n{out.strip()}")
        return False
    print("  [OK  ] VALID   reference instance: K+1 proofs + cross-checks all pass")
    return True


def assert_cost_binding_rejected():
    """Sub G4: tamper sub_0.partial_cost 30 -> 99.  Real sum is 30."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "cost_bind" / "tomls"
    build_composite_plain_product_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                        inst["threshold"], inst["cost"], hier_dir)
    tamper_toml_scalar(hier_dir / "sub_0" / "Prover.toml", "partial_cost", "99")

    rc, err = run_sub_witness(0, hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID cost binding: sub_0 accepted tampered partial_cost (BUG)")
        return False
    if "partial_cost" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID cost binding: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID cost binding: sub G4 rejected mismatched partial_cost")
    return True


def assert_boundary_merkle_rejected():
    """Glue G6: tamper glue.boundary_costs[0] 15 -> 5.  Hash chain != root."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "boundary_merkle" / "tomls"
    build_composite_plain_product_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                        inst["threshold"], inst["cost"], hier_dir)
    tamper_toml_array_entry(hier_dir / "glue" / "Prover.toml", "boundary_costs", 0, "5")

    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID boundary Merkle: glue accepted tampered boundary cost (BUG)")
        return False
    if "Merkle" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID boundary Merkle: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID boundary Merkle: glue G6 rejected tampered boundary cost")
    return True


def assert_bad_p_i_rejected():
    """Sub G6: tamper sub_0.P_i.  Real product != tampered value."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "bad_pi" / "tomls"
    build_composite_plain_product_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                        inst["threshold"], inst["cost"], hier_dir)
    # Set P_i to a clearly-wrong small Field value.
    tamper_toml_scalar(hier_dir / "sub_0" / "Prover.toml", "P_i",
                       "0x0000000000000000000000000000000000000000000000000000000000000002")

    rc, err = run_sub_witness(0, hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID bad P_i: sub_0 accepted tampered P_i (BUG: grand-product hole)")
        return False
    if "P_i" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID bad P_i: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID bad P_i: sub G6 rejected tampered grand product")
    return True


def assert_broken_chain_rejected():
    """Glue G2: tamper glue.h_ins[1] so it != h_outs[0].  Chain not continuous."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "broken_chain" / "tomls"
    build_composite_plain_product_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                        inst["threshold"], inst["cost"], hier_dir)
    tamper_toml_array_entry(hier_dir / "glue" / "Prover.toml", "h_ins", 1,
                            "0x0000000000000000000000000000000000000000000000000000000000000002")

    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID broken chain: glue accepted discontinuous chain (BUG)")
        return False
    if "continuous" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID broken chain: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID broken chain: glue G2 rejected discontinuous chain anchor")
    return True


def assert_partition_overlap_rejected():
    """
    Glue G5 (grand product): node 3 in both segments, node 7 dropped.
    Cheating cycle [0,5,3,2,3,4,1,6].  Each sub-proof is individually valid (its
    own G5/G6 hold for its segment), but prod P_is = product over the multiset
    {0,1,2,3,3,4,5,6} which differs as a polynomial from prod_(j=0..7)(X+j).  By
    Schwartz-Zippel at the unforgeable chain-derived X, glue G5 lhs != rhs.
    """
    n, k = 8, 2
    flat = [0] * (n * n)
    cheat_edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8),   # sub_0 internal
        (3, 4,  7), (4, 1,  9), (1, 6, 14),   # sub_1 internal
        (2, 3,  5), (6, 0, 13),               # boundaries 2->3, 6->0
    ]
    for f, t, c in cheat_edges:
        flat[f * n + t] = c
    cheat_cycle = [0, 5, 3, 2, 3, 4, 1, 6]

    hier_dir = WORK_DIR / "overlap" / "tomls"
    build_composite_plain_product_tomls(n, k, flat, cheat_cycle, threshold=999,
                        cost=sum(c for _, _, c in cheat_edges), out_dir=hier_dir)

    # Each sub-proof witness should still succeed (each segment is locally honest).
    for i in range(k):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] INVALID overlap: sub_{i} unexpectedly rejected witness:\n{err.strip()}")
            return False

    # Glue witness must reject at the grand-product partition check.
    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID overlap: glue accepted overlapping partition (BUG: G5 hole)")
        return False
    if "grand-product" not in err and "Failed constraint" not in err:
        print(f"  [WARN] INVALID overlap: rejected but error doesn't mention grand-product:\n{err.strip()}")
    print("  [OK  ] INVALID overlap: glue G5 grand-product check rejected the overlapping partition")
    return True


def assert_cross_check_c_rejected():
    """
    Cross-check on c (NEW; the A++ analogue of A's "same root").  Two valid proof
    sets through the SAME matrix but DIFFERENT cycles -> different chain terminals
    c_a != c_b.  Mix sub_0+sub_1 from set A with glue from set B.  Each bb verify
    accepts; verify_composite_plain_product rejects because sub_i.c (=c_a) != glue.c (=c_b).
    Without this binding, K+1 proofs could describe K+1 different cycles.
    """
    n, k = 8, 2
    flat = [0] * (n * n)
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8),
        (2, 7, 15), (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),  # set A
        (2, 4,  1), (6, 7,  1), (7, 0,  1),                          # set B extras
    ]
    for f, t, c in edges:
        flat[f * n + t] = c

    # Set A: reference cycle.
    cycle_a = [0, 5, 3, 2, 7, 4, 1, 6]
    set_a_tomls  = WORK_DIR / "xcheck" / "set_a" / "tomls"
    set_a_proofs = WORK_DIR / "xcheck" / "set_a" / "proofs"
    if set_a_proofs.exists(): shutil.rmtree(set_a_proofs)
    build_composite_plain_product_tomls(n, k, flat, cycle_a, threshold=200, cost=92, out_dir=set_a_tomls)
    for i in range(k):
        rc, err = run_sub_witness(i, set_a_tomls)
        if rc != 0: raise RuntimeError(f"set A sub_{i} witness failed:\n{err}")
        rc, err = run_sub_prove(i, set_a_proofs)
        if rc != 0: raise RuntimeError(f"set A sub_{i} prove failed:\n{err}")

    # Set B: different cycle (same matrix) -> different c.
    cycle_b = [0, 5, 3, 2, 4, 1, 6, 7]
    cost_b  = 10 + 12 + 8 + 1 + 9 + 14 + 1 + 1  # 56
    set_b_tomls  = WORK_DIR / "xcheck" / "set_b" / "tomls"
    set_b_proofs = WORK_DIR / "xcheck" / "set_b" / "proofs"
    if set_b_proofs.exists(): shutil.rmtree(set_b_proofs)
    build_composite_plain_product_tomls(n, k, flat, cycle_b, threshold=200, cost=cost_b, out_dir=set_b_tomls)
    rc, err = run_glue_witness(set_b_tomls)
    if rc != 0: raise RuntimeError(f"set B glue witness failed:\n{err}")
    rc, err = run_glue_prove(set_b_proofs)
    if rc != 0: raise RuntimeError(f"set B glue prove failed:\n{err}")

    # Mix: subs from A, glue from B.
    mixed = WORK_DIR / "xcheck" / "mixed"
    if mixed.exists(): shutil.rmtree(mixed)
    for sub in ("sub_0", "sub_1"):
        (mixed / sub).mkdir(parents=True)
    (mixed / "glue").mkdir(parents=True)
    for name in ("proof", "public_inputs"):
        shutil.copy(set_a_proofs / "sub_0" / name, mixed / "sub_0" / name)
        shutil.copy(set_a_proofs / "sub_1" / name, mixed / "sub_1" / name)
        shutil.copy(set_b_proofs / "glue"  / name, mixed / "glue"  / name)

    rc, out = run_verify_composite_plain_product(mixed, n, k)
    if rc == 0:
        print("  [FAIL] INVALID cross-check c: verify_composite_plain_product accepted mixed-cycle proofs (BUG)")
        print(out)
        return False
    if "cross-checks rejected" not in out:
        print("  [WARN] INVALID cross-check c: rejected, but not via cross-check step.")
        print(out)
    if "c mismatch" not in out:
        print("  [WARN] INVALID cross-check c: rejected but error doesn't pinpoint c.")
        print(out)
    print("  [OK  ] INVALID cross-check c: verify_composite_plain_product rejected mixed-cycle proof set (c binding)")
    return True


def assert_baseline_witness_passes_at(n, k):
    """Witness-only sanity at (N, K): synthetic cycle [0..N-1], K subs + glue."""
    cycle = list(range(n))
    flat  = [0] * (n * n)
    cost  = 0
    for i in range(n):
        c = (i + 1) * 3
        flat[cycle[i] * n + cycle[(i + 1) % n]] = c
        cost += c

    hier_dir = WORK_DIR / f"n{n}_k{k}" / "tomls"
    build_composite_plain_product_tomls(n, k, flat, cycle, threshold=math.ceil(cost * 1.1), cost=cost,
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


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: Variant A++ (hierarchical TSP, grand product + FS)")
    print("=" * 64)

    ensure_builder()
    results = []

    print("\n--- Reference instance (N=8 K=2 M=4) ---")
    print("  [setup] configuring circuits for N=8 K=2 ...")
    configure_circuits(8, 2)
    results.append(assert_baseline_passes())

    print("\n--- Negative test 2: cost binding (inherited) ---")
    results.append(assert_cost_binding_rejected())

    print("\n--- Negative test 3: boundary Merkle (inherited) ---")
    results.append(assert_boundary_merkle_rejected())

    print("\n--- Negative test 5: bad P_i (grand-product faithfulness) ---")
    results.append(assert_bad_p_i_rejected())

    print("\n--- Negative test 6: broken chain (cross-segment continuity) ---")
    results.append(assert_broken_chain_rejected())

    print("\n--- Negative test 7: partition overlap (Schwartz-Zippel) ---")
    results.append(assert_partition_overlap_rejected())

    print("\n--- Negative test 4: cross-check on c (cycle binding) ---")
    results.append(assert_cross_check_c_rejected())

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
