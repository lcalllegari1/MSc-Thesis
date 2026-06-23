"""
tests/correctness/test_composite_committed_product.py

Soundness tests for Variant committed-A++ (hierarchical TSP, Merkle commitment,
partition HIDDEN behind a blinded Poseidon2 commitment C_i; grand-product
multiset equality + in-circuit Fiat-Shamir underneath).
Mirrors test_composite_plain_product.py; adapts the negative tests to the committed
public surface (the per-segment scalars are no longer public, so per-field
tampering of P_i / h_in / partial_cost now surfaces at the commitment check).

committed-A++ produces K+1 independent UltraHonk proofs (K sub-proofs of
circuits/composite_committed_product_segment + 1 glue proof of composite_committed_product_glue), bound
by verifier-side cross-checks in pipeline/verify_composite_committed_product.py (same root + X across
K+1, and glue.C_is[i] == sub_i.C_i).

Test list:
  1. baseline                 -- reference N=8 K=2 instance passes end to end.
  2. glue_commitment (NEW)    -- tamper a witnessed glue value (partial_costs[0])
                                 keeping the public C_is; glue G0 rejects.
  3. sub_commitment (NEW)     -- tamper sub_0's public C_i; sub G8 rejects.
  4. boundary_merkle (inh.)   -- tamper glue.boundary_costs[0]; glue G6 rejects.
  5. partition_overlap (inh.) -- node 3 in both segments; glue G5 grand-product
                                 rejects via Schwartz-Zippel at the FS challenge X.
  6. cross_check (NEW)        -- mix sub-proofs from cycle A with glue from cycle B;
                                 verify_composite_committed_product rejects (X and C_i mismatch).
  7. sanity_N48_K4            -- witness-only at a larger size.

Note vs A++: A++'s "bad P_i" and "broken chain" tamper-tests targeted *public*
witness values; in committed-A++ those values are folded into C_i, so tampering
any one of them breaks the commitment recompute (G0/G8) instead -- which is what
tests 2/3 exercise.  Their soundness is preserved, just relocated.

Usage:
    python tests/correctness/test_composite_committed_product.py
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
PROJECT_ROOT   = Path(__file__).parent.parent.parent
SUB_DIR        = PROJECT_ROOT / "circuits" / "composite_committed_product_segment"
GLUE_DIR       = PROJECT_ROOT / "circuits" / "composite_committed_product_glue"
SUB_NAME       = "composite_committed_product_segment"
GLUE_NAME      = "composite_committed_product_glue"
BUILDER_BIN    = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
CARGO_TOML     = PROJECT_ROOT / "pipeline" / "merkle_builder" / "Cargo.toml"
VERIFY_HIER    = PROJECT_ROOT / "pipeline" / "verify_composite_committed_product.py"
BUILDER_FLAG   = "--composite-committed-product"

WORK_DIR       = Path("/tmp/test_composite_committed_product")

# A clearly-wrong small Field value used for scalar tampers.
WRONG_FIELD = "0x0000000000000000000000000000000000000000000000000000000000000002"


# ── Circuit-size parameterisation ─────────────────────────────────────────────

def merkle_depth(n):
    return (n * n - 1).bit_length() if n * n > 1 else 0


def _patch_globals(src_path: Path, **values):
    text = src_path.read_text()
    for name, value in values.items():
        text = re.sub(
            rf"^global {name}: u32\s*=\s*\d+;",
            f"global {name}: u32 = {value};",
            text, flags=re.MULTILINE,
        )
    src_path.write_text(text)


def configure_circuits(n, k):
    """Patch and recompile both circuits for (N, K).  M = N/K."""
    if n % k != 0:
        raise ValueError(f"N={n} must be divisible by K={k}")
    m     = n // k
    depth = merkle_depth(n)
    _patch_globals(SUB_DIR  / "src" / "main.nr", N=n, M=m, DEPTH=depth)
    _patch_globals(GLUE_DIR / "src" / "main.nr", N=n, K=k, DEPTH=depth)
    compile_circuits()


def ensure_builder():
    if BUILDER_BIN.exists():
        return
    print("  [build] merkle_builder not found; building...")
    r = subprocess.run(
        ["cargo", "build", "--release", "--quiet", "--manifest-path", str(CARGO_TOML)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Failed to build merkle_builder:\n{r.stderr}")


def compile_circuits():
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

def build_tomls(n, k, flat_matrix, cycle, threshold, cost, out_dir):
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    payload = json.dumps({
        "n": n, "flat_matrix": flat_matrix, "cycle": cycle,
        "threshold": threshold, "cost": cost,
    })
    r = subprocess.run(
        [str(BUILDER_BIN), BUILDER_FLAG, str(k), "--out-dir", str(out_dir)],
        input=payload, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"merkle_builder failed (exit {r.returncode}):\n{r.stderr}")
    return out_dir


# ── Witness & proof runners ───────────────────────────────────────────────────

def run_sub_witness(seg_idx, hier_dir):
    shutil.copy(Path(hier_dir) / f"sub_{seg_idx}" / "Prover.toml", SUB_DIR / "Prover.toml")
    r = subprocess.run(["nargo", "execute"], cwd=SUB_DIR, capture_output=True, text=True)
    return r.returncode, r.stderr


def run_glue_witness(hier_dir):
    shutil.copy(Path(hier_dir) / "glue" / "Prover.toml", GLUE_DIR / "Prover.toml")
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


def run_verify(proof_dir, n, k):
    r = subprocess.run(
        ["python3", str(VERIFY_HIER),
         "--proof-dir", str(proof_dir), "--n", str(n), "--k", str(k),
         "--sub-vk", str(SUB_DIR / "target" / "vk" / "vk"),
         "--glue-vk", str(GLUE_DIR / "target" / "vk" / "vk")],
        capture_output=True, text=True,
    )
    return r.returncode, (r.stdout + r.stderr)


# ── Reference instance (N=8 K=2 M=4) ──────────────────────────────────────────

def reference_instance():
    n = 8
    flat = [0] * (n * n)
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8), (2, 7, 15),
        (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),
    ]
    for f, t, c in edges:
        flat[f * n + t] = c
    return {"n": n, "k": 2, "flat_matrix": flat,
            "cycle": [0, 5, 3, 2, 7, 4, 1, 6], "cost": 92, "threshold": 100}


# ── TOML tamperers ────────────────────────────────────────────────────────────

def tamper_scalar(path: Path, key: str, new_value: str):
    text = path.read_text()
    new = re.subn(rf'^{re.escape(key)}\s*=\s*"[^"]*"',
                  f'{key} = "{new_value}"', text, count=1, flags=re.MULTILINE)
    if new[1] == 0:
        raise ValueError(f"scalar key {key!r} not found in {path}")
    path.write_text(new[0])


def tamper_array_entry(path: Path, key: str, idx: int, new_value: str):
    text = path.read_text()
    m = re.search(rf'^{re.escape(key)}\s*=\s*\[([^\]]*)\]', text, flags=re.MULTILINE)
    if not m:
        raise ValueError(f"array key {key!r} not found in {path}")
    elements = [e.strip().strip('"') for e in m.group(1).split(",")]
    elements[idx] = new_value
    new_array = ", ".join(f'"{e}"' for e in elements)
    path.write_text(text[:m.start()] + f"{key} = [{new_array}]" + text[m.end():])


# ── Tests ─────────────────────────────────────────────────────────────────────

def assert_baseline_passes():
    inst = reference_instance()
    hier_dir  = WORK_DIR / "ref" / "tomls"
    proof_dir = WORK_DIR / "ref" / "proofs"
    if proof_dir.exists():
        shutil.rmtree(proof_dir)
    build_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                inst["threshold"], inst["cost"], hier_dir)
    for i in range(inst["k"]):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] VALID baseline: sub_{i} witness failed:\n{err.strip()}"); return False
        rc, err = run_sub_prove(i, proof_dir)
        if rc != 0:
            print(f"  [FAIL] VALID baseline: sub_{i} prove failed:\n{err.strip()}"); return False
    rc, err = run_glue_witness(hier_dir)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: glue witness failed:\n{err.strip()}"); return False
    rc, err = run_glue_prove(proof_dir)
    if rc != 0:
        print(f"  [FAIL] VALID baseline: glue prove failed:\n{err.strip()}"); return False
    rc, out = run_verify(proof_dir, inst["n"], inst["k"])
    if rc != 0:
        print(f"  [FAIL] VALID baseline: verify_composite_committed_product rejected:\n{out.strip()}"); return False
    print("  [OK  ] VALID   reference instance: K+1 proofs + cross-checks all pass")
    return True


def assert_glue_commitment_binding_rejected():
    """Glue G0: tamper a witnessed glue value (partial_costs[0]) keeping C_is."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "glue_commit" / "tomls"
    build_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                inst["threshold"], inst["cost"], hier_dir)
    tamper_array_entry(hier_dir / "glue" / "Prover.toml", "partial_costs", 0, "999999")
    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID glue commitment: glue accepted tampered witness (BUG: G0 hole)"); return False
    if "commitment" not in err and "Failed" not in err:
        print(f"  [WARN] INVALID glue commitment: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID glue commitment: glue G0 rejected tampered hidden value")
    return True


def assert_sub_commitment_rejected():
    """Sub G8: tamper sub_0's public C_i so it != fold(r, ...)."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "sub_commit" / "tomls"
    build_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                inst["threshold"], inst["cost"], hier_dir)
    tamper_scalar(hier_dir / "sub_0" / "Prover.toml", "C_i", WRONG_FIELD)
    rc, err = run_sub_witness(0, hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID sub commitment: sub_0 accepted tampered C_i (BUG: G8 hole)"); return False
    if "commitment" not in err and "Failed" not in err:
        print(f"  [WARN] INVALID sub commitment: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID sub commitment: sub G8 rejected tampered C_i")
    return True


def assert_boundary_merkle_rejected():
    """Glue G6: tamper glue.boundary_costs[0]; hash chain != root."""
    inst = reference_instance()
    hier_dir = WORK_DIR / "boundary_merkle" / "tomls"
    build_tomls(inst["n"], inst["k"], inst["flat_matrix"], inst["cycle"],
                inst["threshold"], inst["cost"], hier_dir)
    tamper_array_entry(hier_dir / "glue" / "Prover.toml", "boundary_costs", 0, "5")
    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID boundary Merkle: glue accepted tampered boundary cost (BUG)"); return False
    if "Merkle" not in err and "Failed" not in err:
        print(f"  [WARN] INVALID boundary Merkle: rejected but error unclear:\n{err.strip()}")
    print("  [OK  ] INVALID boundary Merkle: glue G6 rejected tampered boundary cost")
    return True


def assert_partition_overlap_rejected():
    """Glue G5: node 3 in both segments, 7 dropped; grand product != prod(X+j)."""
    n, k = 8, 2
    flat = [0] * (n * n)
    cheat_edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8),
        (3, 4,  7), (4, 1,  9), (1, 6, 14),
        (2, 3,  5), (6, 0, 13),
    ]
    for f, t, c in cheat_edges:
        flat[f * n + t] = c
    cheat_cycle = [0, 5, 3, 2, 3, 4, 1, 6]
    hier_dir = WORK_DIR / "overlap" / "tomls"
    build_tomls(n, k, flat, cheat_cycle, threshold=999,
                cost=sum(c for _, _, c in cheat_edges), out_dir=hier_dir)
    for i in range(k):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] INVALID overlap: sub_{i} unexpectedly rejected:\n{err.strip()}"); return False
    rc, err = run_glue_witness(hier_dir)
    if rc == 0:
        print("  [FAIL] INVALID overlap: glue accepted overlapping partition (BUG: G5 hole)"); return False
    if "grand-product" not in err and "Failed" not in err:
        print(f"  [WARN] INVALID overlap: rejected but error doesn't mention grand-product:\n{err.strip()}")
    print("  [OK  ] INVALID overlap: glue G5 grand-product rejected the overlapping partition")
    return True


def assert_cross_check_rejected():
    """
    Verifier cross-check: two valid proof sets through the SAME matrix but
    DIFFERENT cycles (-> different c -> different X, and different commitments).
    Mix sub_0+sub_1 from set A with glue from set B.  Each bb verify accepts;
    verify_composite_committed_product rejects because sub_i.X != glue.X (and C_i mismatch).
    """
    n, k = 8, 2
    flat = [0] * (n * n)
    edges = [
        (0, 5, 10), (5, 3, 12), (3, 2,  8),
        (2, 7, 15), (7, 4, 11), (4, 1,  9), (1, 6, 14), (6, 0, 13),
        (2, 4,  1), (6, 7,  1), (7, 0,  1),
    ]
    for f, t, c in edges:
        flat[f * n + t] = c

    cycle_a = [0, 5, 3, 2, 7, 4, 1, 6]
    set_a_tomls  = WORK_DIR / "xcheck" / "set_a" / "tomls"
    set_a_proofs = WORK_DIR / "xcheck" / "set_a" / "proofs"
    if set_a_proofs.exists(): shutil.rmtree(set_a_proofs)
    build_tomls(n, k, flat, cycle_a, threshold=200, cost=92, out_dir=set_a_tomls)
    for i in range(k):
        rc, err = run_sub_witness(i, set_a_tomls)
        if rc != 0: raise RuntimeError(f"set A sub_{i} witness failed:\n{err}")
        rc, err = run_sub_prove(i, set_a_proofs)
        if rc != 0: raise RuntimeError(f"set A sub_{i} prove failed:\n{err}")

    cycle_b = [0, 5, 3, 2, 4, 1, 6, 7]
    cost_b  = 10 + 12 + 8 + 1 + 9 + 14 + 1 + 1
    set_b_tomls  = WORK_DIR / "xcheck" / "set_b" / "tomls"
    set_b_proofs = WORK_DIR / "xcheck" / "set_b" / "proofs"
    if set_b_proofs.exists(): shutil.rmtree(set_b_proofs)
    build_tomls(n, k, flat, cycle_b, threshold=200, cost=cost_b, out_dir=set_b_tomls)
    rc, err = run_glue_witness(set_b_tomls)
    if rc != 0: raise RuntimeError(f"set B glue witness failed:\n{err}")
    rc, err = run_glue_prove(set_b_proofs)
    if rc != 0: raise RuntimeError(f"set B glue prove failed:\n{err}")

    mixed = WORK_DIR / "xcheck" / "mixed"
    if mixed.exists(): shutil.rmtree(mixed)
    for sub in ("sub_0", "sub_1"):
        (mixed / sub).mkdir(parents=True)
    (mixed / "glue").mkdir(parents=True)
    for name in ("proof", "public_inputs"):
        shutil.copy(set_a_proofs / "sub_0" / name, mixed / "sub_0" / name)
        shutil.copy(set_a_proofs / "sub_1" / name, mixed / "sub_1" / name)
        shutil.copy(set_b_proofs / "glue"  / name, mixed / "glue"  / name)

    rc, out = run_verify(mixed, n, k)
    if rc == 0:
        print("  [FAIL] INVALID cross-check: verify_composite_committed_product accepted mixed proofs (BUG)")
        print(out); return False
    if "cross-checks rejected" not in out:
        print("  [WARN] INVALID cross-check: rejected, but not via the cross-check step."); print(out)
    print("  [OK  ] INVALID cross-check: verify_composite_committed_product rejected mixed-cycle proof set")
    return True


def assert_baseline_witness_passes_at(n, k):
    cycle = list(range(n))
    flat  = [0] * (n * n)
    cost  = 0
    for i in range(n):
        c = (i + 1) * 3
        flat[cycle[i] * n + cycle[(i + 1) % n]] = c
        cost += c
    hier_dir = WORK_DIR / f"n{n}_k{k}" / "tomls"
    build_tomls(n, k, flat, cycle, threshold=math.ceil(cost * 1.1), cost=cost, out_dir=hier_dir)
    for i in range(k):
        rc, err = run_sub_witness(i, hier_dir)
        if rc != 0:
            print(f"  [FAIL] VALID N={n} K={k}: sub_{i} witness failed:\n{err.strip()}"); return False
    rc, err = run_glue_witness(hier_dir)
    if rc != 0:
        print(f"  [FAIL] VALID N={n} K={k}: glue witness failed:\n{err.strip()}"); return False
    print(f"  [OK  ] VALID   N={n} K={k} M={n//k}: K+1 witnesses all generated")
    return True


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Soundness tests: Variant committed-A++ (hidden partition via blinded commitment)")
    print("=" * 64)
    ensure_builder()
    results = []

    print("\n--- Reference instance (N=8 K=2 M=4) ---")
    print("  [setup] configuring circuits for N=8 K=2 ...")
    configure_circuits(8, 2)
    results.append(assert_baseline_passes())

    print("\n--- Negative test: glue commitment binding (G0) ---")
    results.append(assert_glue_commitment_binding_rejected())

    print("\n--- Negative test: sub commitment binding (G8) ---")
    results.append(assert_sub_commitment_rejected())

    print("\n--- Negative test: boundary Merkle (inherited) ---")
    results.append(assert_boundary_merkle_rejected())

    print("\n--- Negative test: partition overlap (Schwartz-Zippel) ---")
    results.append(assert_partition_overlap_rejected())

    print("\n--- Negative test: verifier cross-check (cycle binding) ---")
    results.append(assert_cross_check_rejected())

    print("\n--- Sanity check: N=48 K=4 (witness only) ---")
    print("  [setup] configuring circuits for N=48 K=4 ...")
    configure_circuits(48, 4)
    results.append(assert_baseline_witness_passes_at(48, 4))

    passed, total = sum(results), len(results)
    print(f"\n{'=' * 64}\nResults: {passed}/{total} passed")
    if passed < total:
        print("SOME TESTS FAILED"); sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
