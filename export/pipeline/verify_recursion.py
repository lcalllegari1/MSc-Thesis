"""
pipeline/verify_recursion.py — Recursion variant verifier.

The recursion variant collapses the K+1 independent proofs of the hierarchical
family into ONE outer proof (circuits/recursion).  The outer circuit recursively
verifies the K hierarchical_segment_fs (A++) proofs in-circuit and re-runs the
glue logic on their now-trusted-but-private public inputs, so the entire binding
that verify_hier_fs.py does externally is folded inside the proof.

Therefore this verifier is the PHOTO-NEGATIVE of verify_hier_fs.py:

  * verify_hier_fs.py: K+1 `bb verify` calls + ~6K+3 Field-equality cross-checks
    (the verifier-side binding tax).
  * verify_recursion.py: exactly ONE `bb verify`, ZERO cross-checks.  The binding
    moved into the circuit, so there is nothing left to cross-check externally.
    Public surface is just (root, threshold) — same as flat_merkle.

This script asserts that emptiness on purpose: it is the operational proof that
the O(K) verifier symptom of the binding tax is gone.

PRIVACY / ZK ASSERTION (load-bearing).  "Perfect hiding" requires the OUTER proof
to be a ZK proof: the K segments' public inputs (P_i, endpoints, chain anchors)
are taken as WITNESS by the outer circuit, so only a ZK outer proof keeps them off
the public surface.  Confirmed empirically (bb 5.0.0-nightly.20260324): default
`bb prove` emits a 458-field / 14656-byte ZK proof; `-no-zk` emits 410 fields.
We assert the 14656-byte length here so a future bb default flip to non-ZK fails
loudly instead of silently breaking the hiding claim.

Outer public-inputs declaration order (length 2):
  [0] root        [1] threshold

Layout of <proof-dir>:
  <proof-dir>/{proof, public_inputs}

Usage:
    python pipeline/verify_recursion.py --proof-dir <dir> \
        --vk circuits/recursion/target/vk/vk
"""

import argparse
import subprocess
import sys
from pathlib import Path


CHUNK = 32            # bytes per Field element in the public_inputs dump
ZK_PROOF_BYTES = 14656  # 458 fields x 32 bytes = the ZK UltraHonk proof length


def parse_public_inputs(path: Path) -> list[int]:
    """Read a public_inputs file and return its Field elements as Python ints."""
    data = path.read_bytes()
    if len(data) % CHUNK != 0:
        raise ValueError(
            f"public_inputs file {path} has size {len(data)} not divisible by {CHUNK}"
        )
    return [int.from_bytes(data[i:i + CHUNK], "big") for i in range(0, len(data), CHUNK)]


def assert_zk_proof(proof_path: Path) -> bool:
    """Assert the outer proof is a ZK proof (length-based guard).  See module docstring."""
    size = proof_path.stat().st_size
    if size != ZK_PROOF_BYTES:
        print(
            f"  [FAIL] outer proof is {size} bytes, expected {ZK_PROOF_BYTES} "
            f"(458 ZK fields). A non-ZK proof ({410 * CHUNK} bytes) would leak the "
            f"segment witnesses — refusing to certify the hiding claim."
        )
        return False
    return True


def bb_verify(vk_path: Path, proof_dir: Path) -> bool:
    """Run `bb verify` on the single outer proof and return True on success."""
    result = subprocess.run(
        ["bb", "verify", "-k", str(vk_path),
         "-p", str(proof_dir / "proof"), "-i", str(proof_dir / "public_inputs")],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [FAIL] bb verify on outer proof:\n{result.stderr.strip()}")
        return False
    return True


def verify_recursion(proof_dir: Path, vk: Path) -> int:
    """Verify the recursion variant: one bb verify, no cross-checks.  0 ok / 1 fail."""
    print("verify_recursion: single-proof verification (binding is in-circuit)")
    print(f"  proof-dir: {proof_dir}")

    # ── Step 1: ZK-length guard (the hiding claim's load-bearing assumption) ──
    print("  [1/3] ZK-proof length guard ...")
    if not assert_zk_proof(proof_dir / "proof"):
        print("FAILED: outer proof is not the expected ZK length")
        return 1
    print(f"    outer proof is {ZK_PROOF_BYTES} bytes (ZK): OK")

    # ── Step 2: the single bb verify (vs K+1 in the hierarchical family) ─────
    print("  [2/3] bb verify x 1 ...")
    if not bb_verify(vk, proof_dir):
        print("FAILED: bb verify rejected the outer proof")
        return 1
    print("    outer: OK")

    # ── Step 3: confirm the public surface is exactly (root, threshold) ──────
    # There are NO cross-checks: the binding the hierarchical verifier performs
    # externally is enforced in-circuit here, so the only thing left to inspect is
    # that the public surface carries no partition information.
    print("  [3/3] public-surface check (NO cross-checks — binding is in-circuit) ...")
    pub = parse_public_inputs(proof_dir / "public_inputs")
    if len(pub) != 2:
        print(f"FAILED: outer public surface has {len(pub)} fields, expected 2 "
              f"(root, threshold) — extra fields would leak partition info")
        return 1
    root, threshold = pub
    print(f"    public surface = (root, threshold) only: OK")
    print(f"    root:      {hex(root)}")
    print(f"    threshold: {threshold}")
    print("ACCEPTED (1 verify, 0 cross-checks — O(K) binding tax removed)")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Verify the recursion-variant TSP ZKP (one bb verify, no cross-checks)."
    )
    ap.add_argument("--proof-dir", required=True, type=Path,
                    help="Directory containing the outer proof + public_inputs files")
    ap.add_argument("--vk", required=True, type=Path, help="Path to the outer-circuit VK")
    args = ap.parse_args()

    sys.exit(verify_recursion(args.proof_dir, args.vk))


if __name__ == "__main__":
    main()
