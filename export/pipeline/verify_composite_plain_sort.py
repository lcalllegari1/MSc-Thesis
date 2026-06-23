"""
pipeline/verify_composite_plain_sort.py — Variant A hierarchical verifier.

What this tool does, and why it exists:
  `bb verify` confirms each of the K+1 UltraHonk proofs is internally consistent
  with the public inputs it declares.  It does NOT check that those K+1 proofs
  refer to the same instance.  Without cross-checks, a malicious prover could
  produce K+1 individually-valid proofs about K+1 different "universes" (same
  circuit shapes, different data).

  This script does both: runs `bb verify` K+1 times, then parses each proof's
  public-input dump and runs the four cross-checks that bind the proofs
  together:

    1. All K+1 proofs declare the same `root`.
    2. glue.all_sorted_nodes[i*M..(i+1)*M] == sub_i.sorted_nodes  for each i.
    3. glue.starts[i]        == sub_i.start_node                   for each i.
       glue.ends[i]          == sub_i.end_node                     for each i.
       glue.partial_costs[i] == sub_i.partial_cost                 for each i.

Public-inputs file format (emitted by `bb prove`):
  - Concatenation of 32-byte big-endian field elements.
  - One element per declared public-input slot, in function-signature order.
  - u32 / u64 / bool values are zero-padded into the low bytes of a Field.

Sub-circuit declaration order (sorted_nodes[M], start_node, end_node,
partial_cost, root) yields M + 3 + 1 = M + 4 field elements per sub-proof.

Glue declaration order (all_sorted_nodes[N], starts[K], ends[K],
partial_costs[K], threshold, root) yields N + 3K + 2 field elements.

Layout of <proof_dir>:
  <proof_dir>/sub_0/{proof, public_inputs}
  ...
  <proof_dir>/sub_{K-1}/{proof, public_inputs}
  <proof_dir>/glue/{proof, public_inputs}
  <proof_dir>/sub_vk/vk            # shared VK for the sub-circuit
  <proof_dir>/glue_vk/vk           # VK for the glue circuit

Usage:
    python pipeline/verify_composite_plain_sort.py --proof-dir <dir> --n 8 --k 2
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


def parse_sub_public(values: list[int], m: int) -> dict:
    """
    Decompose a sub-circuit public-inputs vector into named fields.
    Expected length: M + 4  (sorted_nodes[M], start, end, partial_cost, root).
    """
    expected = m + 4
    if len(values) != expected:
        raise ValueError(
            f"sub-circuit public_inputs has {len(values)} elements, expected {expected} (M+4 with M={m})"
        )
    return {
        "sorted_nodes": values[0:m],
        "start_node":   values[m],
        "end_node":     values[m + 1],
        "partial_cost": values[m + 2],
        "root":         values[m + 3],
    }


def parse_glue_public(values: list[int], n: int, k: int) -> dict:
    """
    Decompose a glue public-inputs vector into named fields.
    Expected length: N + 3K + 2
      (all_sorted_nodes[N], starts[K], ends[K], partial_costs[K], threshold, root).
    """
    expected = n + 3 * k + 2
    if len(values) != expected:
        raise ValueError(
            f"glue public_inputs has {len(values)} elements, expected {expected} (N+3K+2 with N={n}, K={k})"
        )
    off = 0
    all_sorted_nodes = values[off:off + n]; off += n
    starts           = values[off:off + k]; off += k
    ends             = values[off:off + k]; off += k
    partial_costs    = values[off:off + k]; off += k
    threshold        = values[off];         off += 1
    root             = values[off];         off += 1
    return {
        "all_sorted_nodes": all_sorted_nodes,
        "starts":           starts,
        "ends":             ends,
        "partial_costs":    partial_costs,
        "threshold":        threshold,
        "root":             root,
    }


# ── bb verify wrapper ─────────────────────────────────────────────────────────

def bb_verify(vk_path: Path, proof_dir: Path) -> bool:
    """Run `bb verify` and return True on success, False on failure."""
    proof    = proof_dir / "proof"
    pub_in   = proof_dir / "public_inputs"
    result = subprocess.run(
        ["bb", "verify", "-k", str(vk_path), "-p", str(proof), "-i", str(pub_in)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [FAIL] bb verify on {proof_dir.name}:\n{result.stderr.strip()}")
        return False
    return True


# ── Cross-checks ──────────────────────────────────────────────────────────────

def cross_check(subs: list[dict], glue: dict, n: int, k: int, m: int) -> list[str]:
    """
    Return a list of human-readable error messages.  Empty list means all
    cross-checks pass.
    """
    errors = []

    # 1. Same root across all K+1 proofs.
    for i, s in enumerate(subs):
        if s["root"] != glue["root"]:
            errors.append(
                f"root mismatch: sub_{i}.root != glue.root "
                f"({hex(s['root'])} vs {hex(glue['root'])})"
            )

    # 2. all_sorted_nodes chunks match per-segment sorted_nodes.
    for i, s in enumerate(subs):
        chunk = glue["all_sorted_nodes"][i * m:(i + 1) * m]
        if chunk != s["sorted_nodes"]:
            errors.append(
                f"sorted_nodes mismatch at segment {i}: "
                f"glue.all_sorted_nodes[{i*m}..{(i+1)*m}] = {chunk}, "
                f"sub_{i}.sorted_nodes = {s['sorted_nodes']}"
            )

    # 3. starts, ends, partial_costs match.
    for i, s in enumerate(subs):
        if glue["starts"][i] != s["start_node"]:
            errors.append(
                f"start mismatch at segment {i}: "
                f"glue.starts[{i}] = {glue['starts'][i]}, "
                f"sub_{i}.start_node = {s['start_node']}"
            )
        if glue["ends"][i] != s["end_node"]:
            errors.append(
                f"end mismatch at segment {i}: "
                f"glue.ends[{i}] = {glue['ends'][i]}, "
                f"sub_{i}.end_node = {s['end_node']}"
            )
        if glue["partial_costs"][i] != s["partial_cost"]:
            errors.append(
                f"partial_cost mismatch at segment {i}: "
                f"glue.partial_costs[{i}] = {glue['partial_costs'][i]}, "
                f"sub_{i}.partial_cost = {s['partial_cost']}"
            )

    return errors


# ── Driver ────────────────────────────────────────────────────────────────────

def verify_hier(proof_dir: Path, n: int, k: int, sub_vk: Path, glue_vk: Path) -> int:
    """
    Run K+1 bb verify calls and the cross-checks.  Returns 0 on success,
    1 on any failure (verify or cross-check).
    """
    if n % k != 0:
        print(f"ERROR: N={n} not divisible by K={k}")
        return 1
    m = n // k

    print(f"verify_hier: N={n} K={k} M={m}")
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
        parse_sub_public(
            parse_public_inputs(proof_dir / f"sub_{i}" / "public_inputs"),
            m,
        )
        for i in range(k)
    ]
    glue = parse_glue_public(
        parse_public_inputs(proof_dir / "glue" / "public_inputs"),
        n, k,
    )

    errors = cross_check(subs, glue, n, k, m)
    if errors:
        print("FAILED: cross-checks rejected the proof set")
        for e in errors:
            print(f"    - {e}")
        return 1

    print("    same root across all K+1 proofs: OK")
    print("    all_sorted_nodes chunks == sub_i.sorted_nodes: OK")
    print("    starts/ends/partial_costs match sub_i values:  OK")
    print(f"  threshold (from glue): {glue['threshold']}")
    print(f"  total cost (sum of partial_costs): {sum(glue['partial_costs'])} (+ boundary, not in glue public inputs)")
    print("ACCEPTED")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Verify Variant A hierarchical TSP ZKP (K+1 proofs + cross-checks)."
    )
    ap.add_argument("--proof-dir", required=True, type=Path,
                    help="Directory containing sub_i/ and glue/ proof+public_inputs files")
    ap.add_argument("--n", required=True, type=int, help="Total nodes in the instance")
    ap.add_argument("--k", required=True, type=int, help="Number of segments (>= 2)")
    ap.add_argument("--sub-vk", required=True, type=Path, help="Path to the sub-circuit VK")
    ap.add_argument("--glue-vk", required=True, type=Path, help="Path to the glue VK")
    args = ap.parse_args()

    sys.exit(verify_hier(args.proof_dir, args.n, args.k, args.sub_vk, args.glue_vk))


if __name__ == "__main__":
    main()
