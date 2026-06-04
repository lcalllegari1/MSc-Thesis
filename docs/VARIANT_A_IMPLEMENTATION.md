# Variant A — Implementation Plan

**Status:** Architecture and design decisions settled in sessions through
2026-05-26. This document is the single source of truth for implementation;
refer to `HIERARCHICAL_EXPLAINED.md` §8 for the full theory and soundness
arguments, and to `DESIGN.md` / `SESSION_SUMMARY.md` for engineering history.

**Target:** Hierarchical TSP ZKP with Poseidon2 Merkle commitment, partition
public. K segment sub-circuits + 1 glue circuit producing K+1 independent
UltraHonk proofs bound by verifier-side cross-checks. Benchmark sizes:
N ∈ {48, 96, 192, 480}, K ∈ {2, 4, 8}; N=480 anchors comparison against
flat_merkle's N=500 (~4% mismatch).

---

## 1. Architectural decisions (final)

| # | Decision | Pick | Rationale |
|---|---|---|---|
| 1 | Sub-circuit G2 | `sort_via` + element-wise equality with `sorted_nodes`. **No strict-ascending check.** | Sort equality binds `sorted_nodes` to the cycle_segment's sorted multiset. Glue G2 (`sort(all_sorted_nodes) == [0..N-1]`) enforces global multiset = {0..N-1}, which transitively forbids per-segment duplicates. Strict-ascending is redundant. |
| 2 | Merkle builder | Extend `pipeline/merkle_builder` with `--hierarchical K --out-dir <dir>` flag. One binary, two modes. | Single source of truth for MerkleTree code. Lowest risk to existing flat benchmarks. |
| 3 | Verifier tool | Python `pipeline/verify_hier.py`. | Matches existing pipeline style. Reads each proof's `public_inputs` file, parses, runs cross-checks. |
| 4 | First target | **N=8, K=2** for correctness (reference values in `HIERARCHICAL_EXPLAINED.md` §8.9). Then N=48, K=2 for a non-toy gate-count sanity check. Then parameterise K and sweep. | M=4 is non-degenerate (4! = 24 orderings to permute interior over). Reference values fully documented. |
| 5 | Negative tests | Two first: (a) glue G2 (overlapping segments); (b) verifier cross-check (mismatched start_node). Expand to four (+ sub G5 cost binding, + glue G3 boundary Merkle) before final benchmarks. | (a) and (b) are unique to the hierarchical architecture and must be tested first; (c) and (d) are inherited from flat_merkle's existing tests. |
| 6 | Compile-time globals | Sub-circuit: `N, M, DEPTH`. Glue: `N, K, M, DEPTH`. | Sub-circuit doesn't need K — one compile per `(N, M, DEPTH)` tuple serves all K with the same M. |
| 7 | Splitter | **Trivial slice always**: ZK segments are consecutive M-length slices of whatever tour the solver produces. Decoupled from solver. The clustered-solver integration is a separate solver feature; the ZK pipeline is agnostic to which solver produced the tour. | Keeps two concerns separate; matches how the codebase currently treats the solver. |

---

## 2. Sub-circuit `hierarchical_segment`

**File:** `circuits/hierarchical_segment/src/main.nr`

### 2.1 Compile-time globals (patched per (N, K) by the harness)

```noir
global N: u32     = 8;     // total nodes in instance
global M: u32     = 4;     // segment size = N/K
global DEPTH: u32 = 6;     // ceil(log2(N²))
```

### 2.2 Function signature

```noir
use poseidon::poseidon2::Poseidon2;

fn main(
    // ─ PRIVATE ──────────────────────────────────────────────────────
    cycle_segment: [u32; M],
    edge_costs:    [u64; M - 1],
    siblings:      [Field; (M - 1) * DEPTH],
    path_bits:     [bool;  (M - 1) * DEPTH],

    // ─ PUBLIC ───────────────────────────────────────────────────────
    sorted_nodes:  pub [u32; M],
    start_node:    pub u32,
    end_node:      pub u32,
    partial_cost:  pub u64,
    root:          pub Field,
) {
    // G1 — Range
    for i in 0..M {
        assert(cycle_segment[i] < N, "node index out of range");
    }

    // G2 — Permutation (sort equality only; distinctness via glue G2)
    let sorted = cycle_segment.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..M {
        assert(sorted[i] == sorted_nodes[i], "sorted_nodes mismatch");
    }

    // G3 — Endpoints
    assert(start_node == cycle_segment[0], "start_node mismatch");
    assert(end_node   == cycle_segment[M - 1], "end_node mismatch");

    // G4 — Internal Merkle (M-1 edges) + accumulate
    let mut sum: u64 = 0;
    for i in 0..(M - 1) {
        let from = cycle_segment[i];
        let to   = cycle_segment[i + 1];
        let expected_idx: u32 = from * N + to;

        // Leaf-index reconstruction (LSB-first)
        let mut reconstructed: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if path_bits[i * DEPTH + d] {
                reconstructed += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed == expected_idx, "leaf index mismatch");

        // Hash chain to root
        let mut current: Field = edge_costs[i] as Field;
        for d in 0..DEPTH {
            let sib = siblings[i * DEPTH + d];
            let (left, right) = if path_bits[i * DEPTH + d] {
                (sib, current)
            } else {
                (current, sib)
            };
            current = Poseidon2::hash([left, right], 2);
        }
        assert(current == root, "merkle proof mismatch");

        sum += edge_costs[i];
    }

    // G5 — Cost binding
    assert(sum == partial_cost, "partial_cost mismatch");
}
```

### 2.3 Gate count estimate

- **G1:** M · ~8 ≈ 8M (u32 range checks)
- **G2:** `sort_via` ≈ 2M ROM lookups (check_shuffle) + M ordering + M equality ≈ 4M
- **G3:** 2 equality assertions
- **G4:** `(M-1) · DEPTH · 87` Poseidon2 gates + `(M-1) · DEPTH` cheap leaf-bit ops
- **G5:** M-1 additions + 1 equality

At N=480, K=4 (M=120, DEPTH=18): ~119 · 18 · 87 ≈ **186,000 gates per sub-circuit**, dominated by G4 Poseidon2.

---

## 3. Glue circuit `hierarchical_glue`

**File:** `circuits/hierarchical_glue/src/main.nr`

### 3.1 Compile-time globals

```noir
global N: u32     = 8;
global K: u32     = 2;
global M: u32     = 4;   // = N/K
global DEPTH: u32 = 6;
```

### 3.2 Function signature

```noir
use poseidon::poseidon2::Poseidon2;

fn main(
    // ─ PRIVATE ──────────────────────────────────────────────────────
    boundary_costs:     [u64; K],
    boundary_siblings:  [Field; K * DEPTH],
    boundary_path_bits: [bool;  K * DEPTH],

    // ─ PUBLIC ───────────────────────────────────────────────────────
    all_sorted_nodes:   pub [u32; N],
    starts:             pub [u32; K],
    ends:               pub [u32; K],
    partial_costs:      pub [u64; K],
    threshold:          pub u64,
    root:               pub Field,
) {
    // G1 (structural): boundary edges = ends[i] → starts[(i+1) % K]

    // G2 — Partition: sort(all_sorted_nodes) == [0..N-1]
    let sorted = all_sorted_nodes.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..N {
        assert(sorted[i] == i as u32, "partition does not cover {0..N-1}");
    }

    // G3 — Boundary Merkle (K edges) + accumulate
    let mut boundary_sum: u64 = 0;
    for i in 0..K {
        let from = ends[i];
        let to   = starts[(i + 1) % K];
        let expected_idx: u32 = from * N + to;

        // Leaf-index reconstruction
        let mut reconstructed: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if boundary_path_bits[i * DEPTH + d] {
                reconstructed += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed == expected_idx, "boundary leaf index mismatch");

        // Hash chain to root
        let mut current: Field = boundary_costs[i] as Field;
        for d in 0..DEPTH {
            let sib = boundary_siblings[i * DEPTH + d];
            let (left, right) = if boundary_path_bits[i * DEPTH + d] {
                (sib, current)
            } else {
                (current, sib)
            };
            current = Poseidon2::hash([left, right], 2);
        }
        assert(current == root, "boundary merkle proof mismatch");

        boundary_sum += boundary_costs[i];
    }

    // G4 — Threshold
    let mut total: u64 = 0;
    for i in 0..K {
        total += partial_costs[i];
    }
    total += boundary_sum;
    assert(total <= threshold, "cycle cost exceeds threshold");
}
```

### 3.3 Gate count estimate

- **G2:** `sort_via` over N elements ≈ 4N gates (same as flat_full_sort's permutation check)
- **G3:** `K · DEPTH · 87` Poseidon2 gates + cheap leaf-bit ops
- **G4:** K + 1 additions + 1 u64 comparison (~16 gates)

At N=480, K=4: 4N ≈ 1,920 (G2) + 4 · 18 · 87 ≈ 6,264 (G3) ≈ **~8,000 gates**. Glue is small; sub-circuit cost dominates.

---

## 4. Merkle builder extension

**File:** `pipeline/merkle_builder/src/main.rs` (extended)

### 4.1 New flag

```
--hierarchical K --out-dir <dir>
```

When given, builds the same Poseidon2 tree but emits K+1 Prover.toml files
into `<dir>`:

```
<dir>/sub_0/Prover.toml
<dir>/sub_1/Prover.toml
...
<dir>/sub_{K-1}/Prover.toml
<dir>/glue/Prover.toml
```

(Each sub_i.toml lives in its own subdirectory so it can be moved into the
corresponding circuit's working directory by the harness.)

### 4.2 Input JSON (same as flat mode + `k` field)

```json
{
  "n":           8,
  "k":           2,
  "flat_matrix": [...],          // N² entries
  "cycle":       [0,5,3,2,7,4,1,6],
  "threshold":   100,
  "cost":        92
}
```

### 4.3 sub_i.toml content

- **Private:**
  - `cycle_segment = cycle[i*M..(i+1)*M]`
  - `edge_costs` (M-1 internal-edge costs)
  - `siblings`, `path_bits` for the M-1 internal-edge Merkle proofs
- **Public:**
  - `sorted_nodes = sorted(cycle_segment)`
  - `start_node = cycle_segment[0]`
  - `end_node = cycle_segment[M-1]`
  - `partial_cost = sum(edge_costs)`
  - `root`

### 4.4 glue.toml content

- **Private:**
  - `boundary_costs` (K boundary-edge costs)
  - `boundary_siblings`, `boundary_path_bits` for K boundary-edge Merkle proofs
- **Public:**
  - `all_sorted_nodes` = concat of K `sorted_nodes` (not globally sorted yet)
  - `starts[K]`, `ends[K]`, `partial_costs[K]`
  - `threshold`
  - `root`

### 4.5 Implementation note

Reuse existing `MerkleTree::build` and `MerkleTree::proof` unchanged. The only
new logic is:
- Split `cycle` into K segments
- Compute K boundary edges (`cycle[(i+1)*M - 1] → cycle[((i+1)*M) % N]`)
- Extract per-segment and boundary Merkle proofs by calling `tree.proof(leaf_idx)`
- Write K+1 Prover.toml files

Estimated effort: ~80 lines added; existing flat mode unchanged.

---

## 5. Verifier cross-check tool `pipeline/verify_hier.py`

### 5.1 Purpose

`bb verify` alone confirms each proof is internally consistent. The
cross-checks bind the K+1 *separate* proofs into one coherent statement. This
script does both: runs `bb verify × (K+1)` then parses the public-input dumps
and runs the cross-checks.

### 5.2 Inputs

- Directory containing K+1 (proof, public_inputs) pairs
- K, N (or read from a sidecar JSON written by run_hier.py)

### 5.3 Algorithm

1. For each of the K+1 proofs: run `bb verify`; exit 1 on any failure.
2. Parse each public_inputs file into a list of field-encoded values, mapping
   to the declared public-input variables in the function signature order.
3. Run cross-checks:
   - All K+1 proofs declare the same `root`.
   - For each `i in 0..K`:
     - `glue.all_sorted_nodes[i*M..(i+1)*M] == sub_i.sorted_nodes`
     - `glue.starts[i] == sub_i.start_node`
     - `glue.ends[i] == sub_i.end_node`
     - `glue.partial_costs[i] == sub_i.partial_cost`
4. Exit 0 if all pass; exit 1 with a clear message on first failure.

### 5.4 Public-input parsing

`bb prove` writes public inputs as a sequence of 32-byte big-endian field
elements in declaration order. The parser:
- Reads the file as binary
- Splits into 32-byte chunks
- Decodes each chunk to a hex string
- Maps to the named variables using the known schema (K, N → array lengths)

### 5.5 Usage

```bash
python pipeline/verify_hier.py \
    --proof-dir <dir> \
    --k 2 \
    --n 8
```

---

## 6. File structure to create

```
circuits/
  hierarchical_segment/
    Nargo.toml                    # depends on poseidon = v0.3.0
    src/main.nr                   # as in §2

  hierarchical_glue/
    Nargo.toml
    src/main.nr                   # as in §3

pipeline/
  merkle_builder/src/main.rs      # extended (§4)
  verify_hier.py                  # new (§5)
  run_hier.py                     # new (benchmark harness — mirrors run.py)

tests/correctness/
  test_hierarchical_a.py          # new (positive + 2-4 negative tests)
```

---

## 7. Implementation order (step-by-step)

1. **Sub-circuit skeleton** — `circuits/hierarchical_segment/src/main.nr` at
   N=8, M=4, DEPTH=6. Compile with `nargo compile`. Run `nargo info` to
   confirm gate count is sane (~5k–10k at this size).
2. **Glue skeleton** — `circuits/hierarchical_glue/src/main.nr` at N=8, K=2,
   M=4, DEPTH=6. Compile.
3. **Merkle builder extension** — Add `--hierarchical K --out-dir <dir>` mode
   to `pipeline/merkle_builder/src/main.rs`. Use the §8 reference values to
   manually validate Prover.toml output.
4. **First end-to-end proof** — Use the reference instance from §8. Run
   `nargo execute` on each of the 3 circuits. Then `bb prove` × 3. Confirm
   `bb verify` succeeds for all three.
5. **Verifier cross-check tool** — Write `pipeline/verify_hier.py`. Confirm
   all cross-checks pass on the reference instance.
6. **Negative test 1 (segment overlap)** — Modify the reference instance to
   put node 3 in both segments. Confirm glue G2 rejects (i.e., `bb prove` on
   the glue fails to satisfy the constraints, or `nargo execute` errors).
7. **Negative test 2 (cross-check)** — Generate valid proofs, then perturb
   `glue.public_inputs` so `glue.starts[1] != sub_1.start_node`. Confirm each
   `bb verify` still passes individually but `verify_hier.py` rejects.
8. **Parameterise K** — Move K from hardcoded global to harness-patchable.
   First sweep at K=4 with N=48 (M=12).
9. **Negative tests 3 (cost binding) and 4 (boundary Merkle)** — Add for
   completeness before final benchmark sweep.
10. **Benchmark harness `run_hier.py`** — Sweep N ∈ {48, 96, 192, 480},
    K ∈ {2, 4, 8}, runs per cell as in run.py. Times K+1 separate `bb prove`
    calls; for parallel-prover claims, report `max(sub_prove_s, glue_prove_s)`
    plus the sum for "total CPU work" comparison.
11. **Record results** — `results/hier_a.csv` with columns: variant=hier_a,
    n, k, m, depth, circuit (sub/glue), run, circuit_size, acir_opcodes,
    compile_s, witness_s, prove_s, verify_s, proof_bytes, peak_mb.

---

## 8. First end-to-end reference values (N=8, K=2, M=4, DEPTH=6)

From `HIERARCHICAL_EXPLAINED.md` §8.9. Use these to validate the
merkle_builder extension and the first proof run.

**Cycle:** `0 → 5 → 3 → 2 → 7 → 4 → 1 → 6 → 0`

**Required matrix entries** (other entries can be arbitrary; the cost matrix
is N²=64 entries, of which only these 8 are constrained by this instance):

| Edge | Cost | Role |
|---|---|---|
| 0 → 5 | 10 | seg 0 internal |
| 5 → 3 | 12 | seg 0 internal |
| 3 → 2 |  8 | seg 0 internal |
| 2 → 7 | 15 | boundary (seg 0 → seg 1) |
| 7 → 4 | 11 | seg 1 internal |
| 4 → 1 |  9 | seg 1 internal |
| 1 → 6 | 14 | seg 1 internal |
| 6 → 0 | 13 | boundary (seg 1 → seg 0) |

**Total cost:** 92. **Threshold:** 100 (cost · 1.087 ≈ 100, matches the
existing format_inputs.py 1.1× multiplier convention).

**Sub-proof 0:** `cycle_segment=[0,5,3,2]`, `sorted_nodes=[0,2,3,5]`,
`start=0`, `end=2`, `partial_cost=30`. Internal Merkle proofs at leaves
0·8+5=**5**, 5·8+3=**43**, 3·8+2=**26** with values 10, 12, 8.

**Sub-proof 1:** `cycle_segment=[7,4,1,6]`, `sorted_nodes=[1,4,6,7]`,
`start=7`, `end=6`, `partial_cost=34`. Internal Merkle proofs at leaves
7·8+4=**60**, 4·8+1=**33**, 1·8+6=**14** with values 11, 9, 14.

**Glue:** `all_sorted_nodes=[0,2,3,5,1,4,6,7]`, `starts=[0,7]`, `ends=[2,6]`,
`partial_costs=[30,34]`. Boundary Merkle proofs at leaves 2·8+7=**23** (value
15) and 6·8+0=**48** (value 13). Threshold sum: 30+34+15+13 = **92 ≤ 100** ✓.

Verifier cross-checks all pass with the values above.

---

## 9. Negative test plan

All four tests share the same N=8, K=2 setup; each perturbs one input.

| Test | Perturbation | Expected rejection point | Validates |
|---|---|---|---|
| **1. Segment overlap** *(hierarchical-unique)* | Replace sub_1's `cycle_segment[2]=1` with `3` (node 3 now in both segments); adjust `sorted_nodes` to match | Glue G2: `sort(all_sorted_nodes) != [0..7]` | Global distinctness across K sub-proofs |
| **2. Cross-check mismatch** *(hierarchical-unique)* | Generate valid proofs, then edit `glue.public_inputs` to change `glue.starts[1]` from 7 to 0; each `bb verify` still passes since the inner glue witness used `starts[1]=7` and was internally consistent — but the public-input file presented to the verifier claims 0 | `verify_hier.py`: `glue.starts[1] != sub_1.start_node` | Inter-proof binding via cross-checks |
| **3. Cost binding** *(inherited from flat_merkle)* | Set sub_0's `partial_cost = 20` (real sum is 30) | Sub_0 G5: `30 == 20` fails during `nargo execute` | Per-segment cost honesty |
| **4. Boundary Merkle** *(inherited from flat_merkle)* | Set glue's `boundary_costs[0] = 5` (real cost is 15) | Glue G3 Merkle hash chain ≠ root | Boundary edge soundness |

Tests 1 and 2 must pass before first benchmark. Tests 3 and 4 added before
final benchmark sweep.

---

## 10. Pointers to existing code

| What | Where | Why |
|---|---|---|
| Merkle proof pattern (leaf-index reconstruction + hash chain) | `circuits/flat_merkle_presence/src/main.nr` (GROUP 3) | Sub G4 and Glue G3 use the identical idiom |
| `sort_via` + equality pattern | `circuits/flat_full_sort/src/main.nr` (GROUP 2) | Sub G2 and Glue G2 are structurally identical to this, just with different equality targets |
| Poseidon2 Merkle tree construction (Rust) | `pipeline/merkle_builder/src/main.rs` | Reuse `MerkleTree::build` and `MerkleTree::proof` unchanged; add the K-segment splitting logic on top |
| Per-proof Prover.toml writer | `pipeline/merkle_builder/src/main.rs` (`write_prover_toml`) | Generalise by parameterising on the field list; emit K+1 files instead of one |
| Benchmark harness structure | `pipeline/run.py` | Copy structure for `run_hier.py`; extend `set_circuit_n` to `set_circuit_n_k` |
| Negative-test idiom | `tests/correctness/test_flat_merkle_presence.py` | Mirror for `test_hierarchical_a.py` |

---

## 11. Soundness invariants (for self-check during implementation)

After a successful run of all K+1 proofs + cross-checks, the verifier has
established:

1. There exists a Hamiltonian path of M distinct nodes within each segment
   from `start_node_i` to `end_node_i`, with internal cost sum
   `partial_cost_i`, against the matrix committed by `root`. *(sub G1+G2+G3+G4+G5)*
2. The K segments' node sets partition `{0..N-1}` exactly. *(glue G2)*
3. The K boundary edges connect segment endpoints with costs bound to the
   committed matrix. *(glue G3)*
4. Total cycle cost ≤ threshold. *(glue G4)*
5. The K+1 proofs are talking about the same instance (same root, same
   per-segment endpoints, same per-segment costs, consistent partition).
   *(verifier cross-checks)*

Together: a Hamiltonian cycle on N nodes with all N edge costs bound to the
committed matrix and total cost ≤ threshold.

---

## 12. Out of scope for Variant A

- **Variant B** (flat-full sub-matrix as public): shares the glue circuit
  with A; only the sub-circuit body changes (Merkle proofs → ROM lookup into
  public sub_matrix). Estimated ~3 work-days after A is working.
- **Variant A++** (grand product + in-circuit Fiat-Shamir): different sub-
  circuit (adds 3 constraint groups), different glue (replaces sort with
  grand-product check). Estimated ~1 work-week.
- **Clustered-solver integration**: pure solver work. Output is just a
  `cycle` array fed to merkle_builder. The ZK pipeline is agnostic.
- **Frontier figure** across A, A++, B, flat_merkle.
- **Recursive composition** of K+1 proofs into one (replacing verifier cross-
  checks with in-circuit verification): explicitly future work.

---

## 13. Reference documents

- `HIERARCHICAL_EXPLAINED.md` §8 — full Variant A theory (variables, constraint
  groups with counterexamples, soundness chain, privacy, worked examples)
- `DESIGN.md` §8 — engineering decisions log
- `SESSION_SUMMARY.md` — chronological session notes
- `supervisor_report_draft.md` §8 — three-variant programme
- `HOWTO.md` — `nargo` / `bb` invocation reference
