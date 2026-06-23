"""
pipeline/verify_composite_plain_product.py — Variant A++ hierarchical verifier.

A++ produces K+1 independent UltraHonk proofs (K sub-proofs of
circuits/composite_plain_product_segment + 1 glue proof of composite_plain_product_glue) bound by
verifier-side cross-checks.  This tool runs `bb verify` K+1 times, then parses each
proof's public-input dump and runs the equality cross-checks that bind the proofs
into one coherent statement.

Difference from Variant A's verify_composite_plain_sort.py:
  * No `all_sorted_nodes` chunk check (sorted_nodes is gone — partition is hidden).
  * Adds cross-checks on the grand product P_i and the chain anchors h_in/h_out, and
    on the shared Fiat-Shamir values c and X.
  * NO field arithmetic.  Under HIER_FS_IMPL D5 = Option B the partition RHS
    prod_j(X+j) is computed in-circuit (glue G5), so the verifier never recomputes
    any product — all cross-checks are pure Field-equality bookkeeping.

Public-inputs file format (emitted by `bb prove`):
  - Concatenation of 32-byte big-endian field elements, one per declared public
    input, in function-signature order.

Sub-circuit declaration order (length 9):
  [0] start_node  [1] end_node  [2] partial_cost  [3] root
  [4] P_i  [5] h_in_i  [6] h_out_i  [7] c  [8] X

Glue declaration order (length 6K+4):
  [0..K)        starts          [K..2K)      ends
  [2K..3K)      partial_costs   [3K]         threshold     [3K+1] root
  [3K+2..4K+2)  P_is            [4K+2..5K+2) h_ins         [5K+2..6K+2) h_outs
  [6K+2]        c               [6K+3]       X

Layout of <proof_dir>:
  <proof_dir>/sub_0/{proof, public_inputs}  ...  sub_{K-1}/  glue/

Usage:
    python pipeline/verify_composite_plain_product.py --proof-dir <dir> --n 8 --k 2 \
        --sub-vk  circuits/composite_plain_product_segment/target/vk/vk \
        --glue-vk circuits/composite_plain_product_glue/target/vk/vk
"""

import argparse
import subprocess
import sys
from pathlib import Path


# ── Field-element parsing ─────────────────────────────────────────────────────

CHUNK = 32  # bytes per Field element in the public_inputs dump


def parse_public_inputs(path: Path) -> list[int]:
    """Read a public_inputs file and return its Field elements as Python ints."""
    data = path.read_bytes()
    if len(data) % CHUNK != 0:
        raise ValueError(
            f"public_inputs file {path} has size {len(data)} not divisible by {CHUNK}"
        )
    return [int.from_bytes(data[i:i + CHUNK], "big") for i in range(0, len(data), CHUNK)]


def parse_sub_fs_public(values: list[int]) -> dict:
    """Decompose a sub-circuit public-inputs vector.  Expected length: 9."""
    if len(values) != 9:
        raise ValueError(
            f"sub-circuit public_inputs has {len(values)} elements, expected 9"
        )
    return {
        "start_node":   values[0],
        "end_node":     values[1],
        "partial_cost": values[2],
        "root":         values[3],
        "P_i":          values[4],
        "h_in_i":       values[5],
        "h_out_i":      values[6],
        "c":            values[7],
        "X":            values[8],
    }


def parse_glue_fs_public(values: list[int], k: int) -> dict:
    """Decompose a glue public-inputs vector.  Expected length: 6K+4."""
    expected = 6 * k + 4
    if len(values) != expected:
        raise ValueError(
            f"glue public_inputs has {len(values)} elements, expected {expected} (6K+4 with K={k})"
        )
    off = 0
    starts        = values[off:off + k]; off += k
    ends          = values[off:off + k]; off += k
    partial_costs = values[off:off + k]; off += k
    threshold     = values[off];         off += 1
    root          = values[off];         off += 1
    p_is          = values[off:off + k]; off += k
    h_ins         = values[off:off + k]; off += k
    h_outs        = values[off:off + k]; off += k
    c             = values[off];         off += 1
    x             = values[off];         off += 1
    return {
        "starts":        starts,
        "ends":          ends,
        "partial_costs": partial_costs,
        "threshold":     threshold,
        "root":          root,
        "P_is":          p_is,
        "h_ins":         h_ins,
        "h_outs":        h_outs,
        "c":             c,
        "X":             x,
    }


# ── bb verify wrapper ─────────────────────────────────────────────────────────

def bb_verify(vk_path: Path, proof_dir: Path) -> bool:
    """Run `bb verify` and return True on success, False on failure."""
    proof  = proof_dir / "proof"
    pub_in = proof_dir / "public_inputs"
    result = subprocess.run(
        ["bb", "verify", "-k", str(vk_path), "-p", str(proof), "-i", str(pub_in)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [FAIL] bb verify on {proof_dir.name}:\n{result.stderr.strip()}")
        return False
    return True


# ── Cross-checks ──────────────────────────────────────────────────────────────

def cross_check(subs: list[dict], glue: dict, k: int) -> list[str]:
    """Return a list of human-readable error messages.  Empty means all pass."""
    errors = []

    def h(v):  # short hex for messages
        return hex(v)

    # 1-3. Same root / c / X across all K+1 proofs.
    for shared in ("root", "c", "X"):
        for i, s in enumerate(subs):
            if s[shared] != glue[shared]:
                errors.append(
                    f"{shared} mismatch: sub_{i}.{shared} != glue.{shared} "
                    f"({h(s[shared])} vs {h(glue[shared])})"
                )

    # 4-9. Per-segment field equalities between glue arrays and sub scalars.
    pairs = [
        ("starts",        "start_node"),
        ("ends",          "end_node"),
        ("partial_costs", "partial_cost"),
        ("P_is",          "P_i"),
        ("h_ins",         "h_in_i"),
        ("h_outs",        "h_out_i"),
    ]
    for glue_key, sub_key in pairs:
        for i, s in enumerate(subs):
            if glue[glue_key][i] != s[sub_key]:
                errors.append(
                    f"{glue_key} mismatch at segment {i}: "
                    f"glue.{glue_key}[{i}] = {h(glue[glue_key][i])}, "
                    f"sub_{i}.{sub_key} = {h(s[sub_key])}"
                )

    return errors


# ── Driver ────────────────────────────────────────────────────────────────────

def verify_composite_plain_product(proof_dir: Path, n: int, k: int, sub_vk: Path, glue_vk: Path) -> int:
    """Run K+1 bb verify calls and the cross-checks.  0 on success, 1 on failure."""
    if n % k != 0:
        print(f"ERROR: N={n} not divisible by K={k}")
        return 1
    m = n // k

    print(f"verify_composite_plain_product: N={n} K={k} M={m}")
    print(f"  proof-dir: {proof_dir}")

    # ── Step 1: bb verify on all K+1 proofs ──────────────────────────────────
    print("  [1/2] bb verify x (K+1) ...")
    all_ok = True
    for i in range(k):
        ok = bb_verify(sub_vk, proof_dir / f"sub_{i}")
        print(f"    sub_{i}: {'OK' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    ok = bb_verify(glue_vk, proof_dir / "glue")
    print(f"    glue:  {'OK' if ok else 'FAIL'}")
    all_ok = all_ok and ok
    if not all_ok:
        print("FAILED: bb verify rejected at least one proof")
        return 1

    # ── Step 2: parse public_inputs and cross-check ──────────────────────────
    print("  [2/2] cross-checks ...")
    subs = [
        parse_sub_fs_public(parse_public_inputs(proof_dir / f"sub_{i}" / "public_inputs"))
        for i in range(k)
    ]
    glue = parse_glue_fs_public(
        parse_public_inputs(proof_dir / "glue" / "public_inputs"), k
    )

    errors = cross_check(subs, glue, k)
    if errors:
        print("FAILED: cross-checks rejected the proof set")
        for e in errors:
            print(f"    - {e}")
        return 1

    print("    same root across all K+1 proofs: OK")
    print("    same c (cycle commitment) across all K+1 proofs: OK")
    print("    same X (FS challenge) across all K+1 proofs: OK")
    print("    starts/ends/partial_costs match sub_i values: OK")
    print("    P_is / h_ins / h_outs match sub_i values: OK")
    print(f"  threshold (from glue): {glue['threshold']}")
    print(f"  total internal cost (sum of partial_costs): {sum(glue['partial_costs'])} (+ boundary, private)")
    print("ACCEPTED")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Verify Variant A++ hierarchical TSP ZKP (K+1 proofs + cross-checks)."
    )
    ap.add_argument("--proof-dir", required=True, type=Path,
                    help="Directory containing sub_i/ and glue/ proof+public_inputs files")
    ap.add_argument("--n", required=True, type=int, help="Total nodes in the instance")
    ap.add_argument("--k", required=True, type=int, help="Number of segments (>= 2)")
    ap.add_argument("--sub-vk", required=True, type=Path, help="Path to the sub-circuit VK")
    ap.add_argument("--glue-vk", required=True, type=Path, help="Path to the glue circuit VK")
    args = ap.parse_args()

    sys.exit(verify_composite_plain_product(args.proof_dir, args.n, args.k, args.sub_vk, args.glue_vk))


if __name__ == "__main__":
    main()
