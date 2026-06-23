"""
pipeline/verify_hier_c.py — Variant committed-A hierarchical verifier.

committed-A produces K+1 independent UltraHonk proofs (K sub-proofs of
circuits/hierarchical_segment_c + 1 glue proof of hierarchical_glue_c) bound by
verifier-side cross-checks.  This tool runs `bb verify` K+1 times, then parses each
proof's public-input dump and runs the cross-checks.

Difference from Variant A's verify_hier.py: the per-segment values
(sorted_nodes/start/end/partial_cost) are no longer public — they are folded into
a single blinded commitment C_i (the partition sort happens in-circuit over the
now-witnessed nodes).  So the cross-check collapses to two equalities on opaque
field elements:
  * same `root` across all K+1 proofs,
  * glue.C_is[i] == sub_i.C_i for each segment i.
There is no Fiat-Shamir `X` (that is Variant committed-A++'s mechanism).

Sub-circuit declaration order (length 2):       [0] root  [1] C_i
Glue declaration order (length 2+K): [0] root  [1] threshold  [2..2+K) C_is

Layout of <proof_dir>:
  <proof_dir>/sub_0/{proof, public_inputs}  ...  sub_{K-1}/  glue/

Usage:
    python pipeline/verify_hier_c.py --proof-dir <dir> --n 8 --k 2 \
        --sub-vk  circuits/hierarchical_segment_c/target/vk/vk \
        --glue-vk circuits/hierarchical_glue_c/target/vk/vk
"""

import argparse
import subprocess
import sys
from pathlib import Path


CHUNK = 32  # bytes per Field element in the public_inputs dump


def parse_public_inputs(path: Path) -> list[int]:
    """Read a public_inputs file and return its Field elements as Python ints."""
    data = path.read_bytes()
    if len(data) % CHUNK != 0:
        raise ValueError(
            f"public_inputs file {path} has size {len(data)} not divisible by {CHUNK}"
        )
    return [int.from_bytes(data[i:i + CHUNK], "big") for i in range(0, len(data), CHUNK)]


def parse_sub_c_public(values: list[int]) -> dict:
    """Decompose a sub-circuit public-inputs vector.  Expected length: 2."""
    if len(values) != 2:
        raise ValueError(
            f"sub-circuit public_inputs has {len(values)} elements, expected 2"
        )
    return {"root": values[0], "C_i": values[1]}


def parse_glue_c_public(values: list[int], k: int) -> dict:
    """Decompose a glue public-inputs vector.  Expected length: 2+K."""
    expected = 2 + k
    if len(values) != expected:
        raise ValueError(
            f"glue public_inputs has {len(values)} elements, expected {expected} (2+K with K={k})"
        )
    return {"root": values[0], "threshold": values[1], "C_is": values[2:2 + k]}


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


def cross_check(subs: list[dict], glue: dict, k: int) -> list[str]:
    """Return a list of human-readable error messages.  Empty means all pass."""
    errors = []

    def h(v):
        return hex(v)

    for i, s in enumerate(subs):
        if s["root"] != glue["root"]:
            errors.append(
                f"root mismatch: sub_{i}.root != glue.root "
                f"({h(s['root'])} vs {h(glue['root'])})"
            )
    for i, s in enumerate(subs):
        if glue["C_is"][i] != s["C_i"]:
            errors.append(
                f"C_i mismatch at segment {i}: glue.C_is[{i}] = {h(glue['C_is'][i])}, "
                f"sub_{i}.C_i = {h(s['C_i'])}"
            )
    return errors


def verify_hier_c(proof_dir: Path, n: int, k: int, sub_vk: Path, glue_vk: Path) -> int:
    """Run K+1 bb verify calls and the cross-checks.  0 on success, 1 on failure."""
    if n % k != 0:
        print(f"ERROR: N={n} not divisible by K={k}")
        return 1
    m = n // k

    print(f"verify_hier_c: N={n} K={k} M={m}")
    print(f"  proof-dir: {proof_dir}")

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

    print("  [2/2] cross-checks ...")
    subs = [
        parse_sub_c_public(parse_public_inputs(proof_dir / f"sub_{i}" / "public_inputs"))
        for i in range(k)
    ]
    glue = parse_glue_c_public(
        parse_public_inputs(proof_dir / "glue" / "public_inputs"), k
    )

    errors = cross_check(subs, glue, k)
    if errors:
        print("FAILED: cross-checks rejected the proof set")
        for e in errors:
            print(f"    - {e}")
        return 1

    print("    same root across all K+1 proofs: OK")
    print("    glue.C_is[i] == sub_i.C_i (commitment binding): OK")
    print(f"  threshold (from glue): {glue['threshold']}")
    print("    (partition, endpoints, per-segment costs: HIDDEN inside the blinded C_i)")
    print("ACCEPTED")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Verify Variant committed-A hierarchical TSP ZKP (K+1 proofs + cross-checks)."
    )
    ap.add_argument("--proof-dir", required=True, type=Path,
                    help="Directory containing sub_i/ and glue/ proof+public_inputs files")
    ap.add_argument("--n", required=True, type=int, help="Total nodes in the instance")
    ap.add_argument("--k", required=True, type=int, help="Number of segments (>= 2)")
    ap.add_argument("--sub-vk", required=True, type=Path, help="Path to the sub-circuit VK")
    ap.add_argument("--glue-vk", required=True, type=Path, help="Path to the glue circuit VK")
    args = ap.parse_args()

    sys.exit(verify_hier_c(args.proof_dir, args.n, args.k, args.sub_vk, args.glue_vk))


if __name__ == "__main__":
    main()
