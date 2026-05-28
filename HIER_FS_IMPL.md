# Variant A++ (`hier_fs`) — Implementation Plan

**Status:** Architectural decisions locked in 2026-05-27 after a planning
discussion that surfaced the trade-offs for each design choice. This document
is the single source of truth for the A++ implementation; refer to
`HIERARCHICAL_EXPLAINED.md` §9 for the full theory and soundness argument, to
`VARIANT_A_IMPLEMENTATION.md` for the A blueprint that A++ mirrors, and to
`DESIGN.md` §8 for the engineering log.

**Target:** Hierarchical TSP ZKP with Poseidon2 Merkle commitment **and
partition hidden** via grand-product multiset equality at a Fiat-Shamir
challenge derived in-circuit. K segment sub-circuits + 1 glue circuit produce
K+1 independent UltraHonk proofs bound by verifier-side cross-checks.
Benchmark sizes anchor on the same N ∈ {48, 96, 192, 480}, K ∈ {2, 4, 8}
grid as A, so A vs A++ vs flat_merkle comparisons are direct.

**Variant name everywhere in code, CSV, plots, scripts:** `hier_fs`.
(`++` appears only in supervisor report / thesis prose.)

---

## 1. Locked-in architectural decisions

These were debated during planning and are now fixed. Each row recaps the
chosen option and the reasoning that landed there.

| # | Decision | Locked choice | One-line rationale |
|---|---|---|---|
| D1 | Where the new circuits live | New dirs `circuits/hierarchical_segment_fs/` and `circuits/hierarchical_glue_fs/` (cp from A, then modify) | Keeps A intact for side-by-side benchmarks; matches the doc's "fs" suffix; no risk of regressing A's tests. |
| D2 | Where the Fiat-Shamir binding `X = Poseidon2(c)` is enforced | **In every sub-circuit AND in the glue** (each gets its own G7 / G4 challenge-consistency constraint) | Defense-in-depth: cryptographic binding to `c` in each proof, not relying solely on the verifier's cross-check on X. The K+1 extra Poseidon2 calls are rounding error (~87 gates × K+1). |
| D3 | Hash function shape for the challenge derivation | `X = Poseidon2::hash([c], 1)` (single-input mode) | Textbook FS challenge derivation; sponge padding for `in_len=1` is naturally domain-separated from Merkle compression (`in_len=2`). Rust side needs one extra helper. |
| D4 | Hash function shape for chain step | `h_{j+1} = Poseidon2::hash([h_j, cycle[j] as Field], 2)` | Reuses the exact Merkle compression primitive (already cross-validated). Domain separation is implicit: Merkle inputs are always Poseidon2 outputs (random-looking ~254-bit Fields), chain right-positions are tiny u32 node indices — confusion is computationally impossible. |
| **D5** | `expected_product = ∏(X+j) for j=0..N-1` placement | **In-circuit in the glue (G5)** — no `expected_product` public input, no verifier-side recomputation | Single-layer soundness; verifier has no non-optional cross-check obligation; cost is ~N Field mults (~480 gates at N=480) — still well below A's ~21k-gate glue. Cleaner thesis story: "every soundness claim is enforced by a circuit constraint; verifier cross-checks are equality bookkeeping, not cryptographic obligations." |
| D6 | Defense-in-depth for X | Both circuit-level constraints (D2) AND verifier cross-check on `X` and `c` across K+1 proofs | Two-layer; cross-check catches any bug in how the prover assembled the proofs even if circuit-level constraints are individually satisfied. |
| D7 | Compile-time globals | Sub-circuit: `N, M, DEPTH`. Glue: `N, K, DEPTH`. **No new globals introduced.** | M-sized arrays in subs and K-sized arrays in glue. N still needed in glue for `from*N+to` leaf-index reconstruction AND for the `for j in 0..N` loop in G5. Patcher logic unchanged from A. |
| D8 | Pipeline scripts | New `pipeline/run_hier_fs.py` and `pipeline/verify_hier_fs.py` (sibling files, not flags on the A scripts) | Each variant's harness stays self-contained; no `if variant ==` spaghetti; refactor to a shared module can happen later once both variants work. |
| D9 | Rust builder | Extend existing `pipeline/merkle_builder` with a third mode: `--hierarchical-fs K --out-dir <dir>` | Reuses `MerkleTree::build` / `MerkleTree::proof` / `poseidon2_compress` unchanged; adds chain + grand-product + new Prover.toml writers. One binary, three modes. |
| D10 | Aggregator | Reuse `pipeline/aggregate_hier.py` as-is — it groups by `(n, k, run)` and is variant-name-driven | Just write `variant=hier_fs` rows from run_hier_fs.py; aggregator emits `hier_fs_k{K}` variants for plotting. No code changes needed. |
| D11 | Variant naming | `hier_fs` everywhere in code/CSV/filesystem; `A++` only in prose | Filesystem-safe; mirrors `hier_a` pattern. |

---

## 2. Sub-circuit `hierarchical_segment_fs`

**File:** `circuits/hierarchical_segment_fs/src/main.nr`

### 2.1 Compile-time globals (patched per (N, K) by the harness)

```noir
global N: u32     = 8;     // total nodes in the instance
global M: u32     = 4;     // segment size = N/K
global DEPTH: u32 = 6;     // ceil(log2(N²))
```

Same shape as A's sub-circuit. No K global (a segment knows about itself, not
how many siblings it has).

### 2.2 Function signature

```noir
use poseidon::poseidon2::Poseidon2;

fn main(
    // ─ PRIVATE ─────────────────────────────────────────────────
    cycle_segment: [u32; M],
    edge_costs:    [u64; M - 1],
    siblings:      [Field; (M - 1) * DEPTH],
    path_bits:     [bool;  (M - 1) * DEPTH],

    // ─ PUBLIC ──────────────────────────────────────────────────
    // Geometry / cost (kept from A).
    start_node:    pub u32,
    end_node:      pub u32,
    partial_cost:  pub u64,
    root:          pub Field,
    // FS / grand-product additions (A++ only).
    P_i:           pub Field,   // grand product ∏(X + cycle_segment[j])
    h_in_i:        pub Field,   // chain value entering this segment
    h_out_i:       pub Field,   // chain value leaving this segment
    c:             pub Field,   // chain terminal (= h_N, same across all proofs)
    X:             pub Field,   // Fiat-Shamir challenge = Poseidon2::hash([c], 1)
) {
    // G1 — Range
    for i in 0..M {
        assert(cycle_segment[i] < N, "node index out of range");
    }

    // G2 — Endpoints (no sort-based G2 anymore; grand product handles permutation)
    assert(start_node == cycle_segment[0],     "start_node mismatch");
    assert(end_node   == cycle_segment[M - 1], "end_node mismatch");

    // G3 — Internal Merkle (identical idiom to A's G4): M-1 edges, accumulate
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

    // G4 — Cost binding
    assert(sum == partial_cost, "partial_cost mismatch");

    // G5 — Hash chain link (NEW)
    // Fold M cycle_segment values into the chain starting from h_in_i.
    // M Poseidon2 calls per sub-circuit. Result must equal h_out_i.
    let mut h: Field = h_in_i;
    for j in 0..M {
        h = Poseidon2::hash([h, cycle_segment[j] as Field], 2);
    }
    assert(h == h_out_i, "chain link mismatch");

    // G6 — Grand product (NEW)
    // Compute ∏(X + cycle_segment[j]) step by step in-circuit.
    // M Field multiplications per sub-circuit.
    let mut prod: Field = 1;
    for j in 0..M {
        prod = prod * (X + cycle_segment[j] as Field);
    }
    assert(prod == P_i, "P_i mismatch");

    // G7 — Challenge consistency (NEW; in-circuit FS binding)
    // X must be the Poseidon2 hash of c. Each sub-circuit asserts this
    // independently of the glue (defense-in-depth, D2).
    let x_expected: Field = Poseidon2::hash([c], 1);
    assert(X == x_expected, "X != Poseidon2(c)");
}
```

### 2.3 Public-input declaration order (load-bearing for verify_hier_fs.py)

The parser in `verify_hier_fs.py` reads `public_inputs` as 32-byte big-endian
Field chunks in **function-signature order** (Noir matches by name during
witness generation but `bb prove` writes public inputs in signature order).
Lock this in once and don't reorder:

```
sub_public_inputs (length M + 4 + 5 = M + 9):
  [0]              start_node   (u32)
  [1]              end_node     (u32)
  [2]              partial_cost (u64)
  [3]              root         (Field)
  [4]              P_i          (Field)
  [5]              h_in_i       (Field)
  [6]              h_out_i      (Field)
  [7]              c            (Field)
  [8]              X            (Field)
```

Wait — that's 9 elements, not M+9. **The sub-circuit's public-input pool is
constant in M** (no `sorted_nodes[M]` anymore). This is one of A++'s wins:
`O(M) → O(1)` per sub-circuit.

### 2.4 Constraint groups summary

| Group | Constraint | Cost (gates, approx) | Inherited from A? |
|---|---|---|---|
| G1 | Range: `cycle_segment[i] < N` for i ∈ [0, M) | M × 8 | yes |
| G2 | Endpoints: `start_node == cycle_segment[0]`, `end_node == cycle_segment[M-1]` | 2 | yes (was G3) |
| G3 | Internal Merkle (M-1 edges): leaf-idx reconstruction + hash chain | `(M-1) · DEPTH · ~87` Poseidon2 | yes (was G4) |
| G4 | Cost binding: `sum(edge_costs) == partial_cost` | M-1 adds + 1 eq | yes (was G5) |
| G5 | Chain link: fold M cycle values from h_in to h_out via Poseidon2 | `M · ~87` Poseidon2 | **NEW** |
| G6 | Grand product: ∏(X + cycle_segment[j]) == P_i | M Field mults | **NEW** |
| G7 | Challenge consistency: X == Poseidon2([c], 1) | 1 Poseidon2 (~87) | **NEW** |

### 2.5 Gate count estimate

At N = 480, K = 4 (M = 120, DEPTH = 18):

- G1: 120 × 8 ≈ 960
- G2: 2
- G3 (Merkle): 119 × 18 × 87 ≈ 186,354
- G4: 120
- G5 (chain): 120 × 87 ≈ 10,440
- G6 (grand product): 120 mults ≈ 120
- G7: 87
- **Total ≈ 198,000 gates**

Compared to A's sub-circuit at the same (N, K) (~186,000): **+12,000 gates ≈
+6.4%**, matching the doc's ~5.5% claim within rounding. The chain (G5)
dominates the overhead — grand-product mults are nearly free.

---

## 3. Glue circuit `hierarchical_glue_fs`

**File:** `circuits/hierarchical_glue_fs/src/main.nr`

### 3.1 Compile-time globals

```noir
global N: u32     = 8;
global K: u32     = 2;
global DEPTH: u32 = 6;
```

Same shape as A's glue (no M needed — chunks are indexed by K).

### 3.2 Function signature

```noir
use poseidon::poseidon2::Poseidon2;

fn main(
    // ─ PRIVATE ─────────────────────────────────────────────────
    boundary_costs:     [u64; K],
    boundary_siblings:  [Field; K * DEPTH],
    boundary_path_bits: [bool;  K * DEPTH],

    // ─ PUBLIC ──────────────────────────────────────────────────
    // Geometry / cost (kept from A; sorted_nodes-concat array gone).
    starts:        pub [u32; K],
    ends:          pub [u32; K],
    partial_costs: pub [u64; K],
    threshold:     pub u64,
    root:          pub Field,
    // FS / grand-product additions.
    P_is:          pub [Field; K],
    h_ins:         pub [Field; K],
    h_outs:        pub [Field; K],
    c:             pub Field,
    X:             pub Field,
) {
    // G1 — Chain init
    assert(h_ins[0] == 0, "chain must start from 0");

    // G2 — Chain stitching (K-1 equalities; trivially handles K=2)
    for i in 0..(K - 1) {
        assert(h_ins[i + 1] == h_outs[i], "chain not continuous");
    }

    // G3 — Chain terminal
    assert(h_outs[K - 1] == c, "chain does not terminate at c");

    // G4 — Challenge consistency (independent in-circuit FS binding;
    // defense-in-depth alongside each sub-circuit's G7)
    let x_expected: Field = Poseidon2::hash([c], 1);
    assert(X == x_expected, "X != Poseidon2(c)");

    // G5 — Grand-product partition (in-circuit, no expected_product input).
    // LHS: product of K sub-proofs' P_i values.
    let mut lhs: Field = 1;
    for i in 0..K {
        lhs = lhs * P_is[i];
    }
    // RHS: ∏(X + j) for j = 0..N-1.
    let mut rhs: Field = 1;
    for j in 0..N {
        rhs = rhs * (X + j as Field);
    }
    assert(lhs == rhs, "grand-product partition mismatch");

    // G6 — Boundary Merkle (K edges); identical idiom to A's G3
    let mut boundary_sum: u64 = 0;
    for i in 0..K {
        let from = ends[i];
        let to   = starts[(i + 1) % K];
        let expected_idx: u32 = from * N + to;

        let mut reconstructed: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if boundary_path_bits[i * DEPTH + d] {
                reconstructed += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed == expected_idx, "boundary leaf index mismatch");

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

    // G7 — Threshold (identical to A's G4)
    let mut total: u64 = 0;
    for i in 0..K {
        total += partial_costs[i];
    }
    total += boundary_sum;
    assert(total <= threshold, "cycle cost exceeds threshold");
}
```

### 3.3 Public-input declaration order

```
glue_public_inputs (length 3K + 2 + 3K + 2 = 6K + 4):
  [0..K)         starts          (u32 × K)
  [K..2K)        ends            (u32 × K)
  [2K..3K)       partial_costs   (u64 × K)
  [3K]           threshold       (u64)
  [3K + 1]       root            (Field)
  [3K+2..4K+2)   P_is            (Field × K)
  [4K+2..5K+2)   h_ins           (Field × K)
  [5K+2..6K+2)   h_outs          (Field × K)
  [6K + 2]       c               (Field)
  [6K + 3]       X               (Field)
```

At N=480, K=4: 6·4 + 4 = **28 elements** — down from A's glue (N + 3K + 2 =
494) by ~17×.

### 3.4 Constraint groups summary

| Group | Constraint | Cost (gates, approx) | Inherited from A? |
|---|---|---|---|
| G1 | Chain init: `h_ins[0] == 0` | 1 | NEW |
| G2 | Chain stitching: K-1 equalities | K-1 | NEW |
| G3 | Chain terminal: `h_outs[K-1] == c` | 1 | NEW |
| G4 | Challenge consistency: `X == Poseidon2([c], 1)` | ~87 | NEW |
| G5 | Grand product: `∏ P_is == ∏(X + j)` | (K-1) + (N-1) mults | NEW (replaces A's G2 sort) |
| G6 | Boundary Merkle (K edges) | `K · DEPTH · ~87` | yes (was G3) |
| G7 | Threshold | ~16 | yes (was G4) |

### 3.5 Gate count estimate

At N = 480, K = 4, DEPTH = 18:

- G1+G2+G3: ~5
- G4: 87
- G5: 480 - 1 + 4 - 1 ≈ 482 mults
- G6: 4 × 18 × 87 ≈ 6,264
- G7: ~16
- **Total ≈ 6,900 gates**

Compared to A's glue at same (N, K): ~21,000 → **~6,900 gates (-67%)**. The
glue gets dramatically smaller. The two big wins:
- O(N) sort gone → ~1,920 gates saved (G2 in A)
- O(N) `all_sorted_nodes` public input pool gone → significant prover memory
  saved (the O(N) memory floor at the glue, ~159 MB at N=480, should drop
  substantially — this is the headline empirical claim to validate)

The in-circuit `expected_product` loop (G5 RHS) costs ~480 gates — a net
win because it replaces the public-input encoding cost and the sort cost.

---

## 4. Rust builder extension

**File:** `pipeline/merkle_builder/src/main.rs` (extended)

### 4.1 New CLI mode

```
merkle_builder --hierarchical-fs K --out-dir <dir> < input.json
```

Input JSON schema is unchanged from `--hierarchical`:
```json
{
  "n": 8, "flat_matrix": [...], "cycle": [0,5,3,2,7,4,1,6],
  "threshold": 100, "cost": 92
}
```

Output:
```
<dir>/sub_0/Prover.toml
<dir>/sub_1/Prover.toml
...
<dir>/sub_{K-1}/Prover.toml
<dir>/glue/Prover.toml
```

### 4.2 New computations beyond `--hierarchical`

After building the Merkle tree (reuse `MerkleTree::build` and
`MerkleTree::proof` unchanged):

1. **Hash chain** over `cycle[0..N]`:
   ```
   let mut h = vec![FieldElement::zero(); N + 1];
   h[0] = FieldElement::zero();
   for j in 0..N {
       h[j + 1] = poseidon2_compress(h[j], FieldElement::from(cycle[j] as u128));
   }
   let c = h[N];
   ```
   `poseidon2_compress` already exists and matches Noir's `Poseidon2::hash([l, r], 2)`.

2. **Challenge** `X = Poseidon2::hash([c], 1)`:
   ```
   fn poseidon2_hash_single(x: FieldElement) -> FieldElement {
       // Matches Noir's Poseidon2::hash([c], in_len=1).
       // Sponge IV for in_len=1: iv = 1 * 2^64.
       // State = [c, 0, 0, iv]; permutation; output state[0].
       let iv = FieldElement::from(1u128 * (1u128 << 64));
       let state = vec![x, FieldElement::zero(), FieldElement::zero(), iv];
       poseidon2_permutation(&state).expect("permutation")[0]
   }
   let X = poseidon2_hash_single(c);
   ```
   **CRITICAL:** Cross-validate this against Noir's `Poseidon2::hash([c], 1)`
   via the hash-compat test (step 2 in §10) **before** writing the rest. The
   `iv = in_len * 2^64` convention is documented in Poseidon2 but worth a
   direct check.

3. **Per-segment grand products** `P_i = ∏(X + cycle_segment_i[j])`:
   ```
   for seg in 0..K {
       let mut p = FieldElement::one();
       for j in 0..M {
           p = p * (X + FieldElement::from(cycle[seg*M + j] as u128));
       }
       p_is.push(p);
   }
   ```

4. **Chain anchors per segment**:
   ```
   h_in[seg]  = h[seg * M]
   h_out[seg] = h[(seg + 1) * M]
   // Invariant: h_in[0] == 0 and h_out[K-1] == c
   ```

5. **(NOT computed in builder for option B):** `expected_product`. The
   builder doesn't need to compute or emit it — it's enforced in the glue
   circuit's G5 loop.

### 4.3 New Prover.toml writers

Two new functions, mirroring `write_sub_prover_toml` and
`write_glue_prover_toml` from the A code path:

- `write_sub_fs_prover_toml(out_path, seg_idx, cycle_segment, edge_costs,
   siblings_flat, path_bits_flat, start_node, end_node, partial_cost, root,
   p_i, h_in, h_out, c, x)`
- `write_glue_fs_prover_toml(out_path, boundary_costs, boundary_siblings,
   boundary_path_bits, starts, ends, partial_costs, threshold, cost, root,
   p_is, h_ins, h_outs, c, x)`

Reuse the same TOML-format conventions: u32/u64 as quoted decimals, Field as
`"0x<64-hex>"`, bool as unquoted `true`/`false`. Keep the commented headers
explaining each field — match the A files' style for consistency and
auditability.

### 4.4 Implementation note

The existing `run_hierarchical` is ~100 lines. `run_hierarchical_fs` will
share ~80% of it (segment splitting, boundary edge proof extraction,
Prover.toml dispatch). Either factor out a shared helper or accept the
duplication — the latter is fine and matches how A and B will both reuse
the same Merkle code with variant-specific append logic.

### 4.5 Unit tests to add in `tests/` module

- `chain_terminal_matches_independent_recomputation` — build a 3-node cycle,
  compute h_3 two ways (sequential chain vs direct), assert equal.
- `grand_product_partition_identity` — given any cycle that's a permutation
  of {0..N-1}, assert `∏ P_i == ∏(X+j)` natively. (Sanity-check the math.)

---

## 5. Verifier `pipeline/verify_hier_fs.py`

### 5.1 Purpose

Same role as `verify_hier.py`: runs `bb verify` × (K+1), parses the K+1
public-input dumps, runs cross-checks that bind the proofs together.

Under D5 = Option B (in-circuit), **the verifier does no field arithmetic at
all**. All soundness is enforced in-circuit. The cross-checks are pure
Field-equality bookkeeping.

### 5.2 Cross-check schema

Given K sub-proofs and 1 glue proof:

| # | Check | What it catches |
|---|---|---|
| 1 | All K+1 declare same `root` | K+1 proofs about K+1 different matrices |
| 2 | All K+1 declare same `c` | K+1 proofs about different cycles |
| 3 | All K+1 declare same `X` | Cross-consistency of FS challenge |
| 4 | For each i: `glue.starts[i] == sub_i.start_node` | Endpoint substitution attack |
| 5 | For each i: `glue.ends[i] == sub_i.end_node` | Same |
| 6 | For each i: `glue.partial_costs[i] == sub_i.partial_cost` | Cost-sum tampering across the K+1 boundary |
| 7 | For each i: `glue.P_is[i] == sub_i.P_i` | Grand-product input substitution |
| 8 | For each i: `glue.h_ins[i] == sub_i.h_in_i` | Chain-anchor tampering |
| 9 | For each i: `glue.h_outs[i] == sub_i.h_out_i` | Same |

**No `all_sorted_nodes` chunk check** (sorted_nodes is gone). **No native
expected_product recomputation** (in-circuit under Option B).

Total: ~6K+3 equality checks. Trivial.

### 5.3 Public-input parsing

Same parser as A's `verify_hier.py`: read `public_inputs` as 32-byte
big-endian chunks. Map to named fields using the declaration order from
§2.3 and §3.3.

```python
def parse_sub_fs_public(values: list[int]) -> dict:
    # Expected length: 9
    assert len(values) == 9
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
    expected = 6 * k + 4
    assert len(values) == expected
    off = 0
    starts        = values[off:off+k]; off += k
    ends          = values[off:off+k]; off += k
    partial_costs = values[off:off+k]; off += k
    threshold     = values[off];       off += 1
    root          = values[off];       off += 1
    p_is          = values[off:off+k]; off += k
    h_ins         = values[off:off+k]; off += k
    h_outs        = values[off:off+k]; off += k
    c             = values[off];       off += 1
    x             = values[off];       off += 1
    return { ... }
```

### 5.4 CLI

```bash
python pipeline/verify_hier_fs.py \
    --proof-dir <dir> \
    --n 8 --k 2 \
    --sub-vk  circuits/hierarchical_segment_fs/target/vk/vk \
    --glue-vk circuits/hierarchical_glue_fs/target/vk/vk
```

Mirrors `verify_hier.py` exactly.

---

## 6. Benchmark harness `pipeline/run_hier_fs.py`

Mirror `pipeline/run_hier.py` structurally. The differences are mechanical:

| Item | Change |
|---|---|
| `SUB_DIR`, `GLUE_DIR` | Point to `hierarchical_segment_fs` / `hierarchical_glue_fs` |
| `SUB_NAME`, `GLUE_NAME` | `hierarchical_segment_fs`, `hierarchical_glue_fs` |
| `SHADOW_ROOT` | `/tmp/hier_fs_shadows` (don't collide with A's) |
| `write_inputs_json` | Unchanged — same JSON schema |
| `build_hier_tomls` | Call `merkle_builder --hierarchical-fs K --out-dir <dir>` |
| `run_verify_hier` | Call `verify_hier_fs.py` instead |
| CSV `variant` column | `hier_fs` instead of `hier_a` |
| Cell scratch dir | `/tmp/run_hier_fs/...` |

CSV schema is identical to `run_hier.py`'s (K+1 rows per cell), so the
aggregator works without modification.

### 6.1 Sweep grid

Same as A for direct comparability:
```
--ns 48 96 192 480
--ks 2 4 8
--runs 3
--out results/hier_fs.csv
```

### 6.2 Performance expectations (to validate)

| Metric | vs A | Justification |
|---|---|---|
| Sub-circuit `circuit_size` | +5-6% | M chain Poseidon2 + 1 challenge Poseidon2 |
| Sub-circuit `prove_s` | +5-6% (single-machine isolated) | Linear in circuit_size |
| Sub-circuit `peak_mb` | comparable, maybe slightly higher | Proportional to circuit_size |
| Glue `circuit_size` | -65% | O(N) sort → O(N) Field mults; smaller public-input pool |
| Glue `peak_mb` | substantially lower | The O(N) sort was the cause of the ~159 MB floor at N=480; Field mults don't have that footprint |
| Wall-clock parallel | comparable | Sub-circuit still dominates; +5% on the bottleneck |
| Total CPU work | +5% | Same logic |
| Cross-check `verify_hier_fs_s` | similar | Same cross-check loop; no expected_product native recomputation |

The glue memory drop is the **headline empirical claim** to validate. If
A++'s glue peak_mb falls below A's by a significant margin (say, sub-100 MB
at N=480, K=8), that strengthens the "A++ for memory-constrained provers"
thesis-level case.

---

## 7. Aggregator + plots

### 7.1 `pipeline/aggregate_hier.py`

**No code changes needed.** The aggregator groups by (n, k, run) and writes
`variant=hier_<X>_k{K}` rows where `<X>` comes from the raw CSV. Just feed
it `results/hier_fs.csv` and it will emit `hier_fs_k2`, `hier_fs_k4`,
`hier_fs_k8` rows.

```bash
# parallel wall-clock projection
python pipeline/aggregate_hier.py \
    --in  results/hier_fs.csv \
    --out results/hier_fs_par.csv \
    --mode parallel

# total CPU work
python pipeline/aggregate_hier.py \
    --in  results/hier_fs.csv \
    --out results/hier_fs_tot.csv \
    --mode total
```

### 7.2 Plots

Use existing `pipeline/plot.py` to overlay:
```bash
python pipeline/plot.py \
    --csv results/500.csv results/hier_a_par.csv results/hier_fs_par.csv \
    --out plots/flat_vs_hier_a_vs_hier_fs
```

This is the **frontier figure** the thesis needs: flat_merkle, A, A++ on the
same axes for circuit_size, prove_s, peak_mb across N.

---

## 8. Test plan

**File:** `tests/correctness/test_hierarchical_fs.py`

Mirror `tests/correctness/test_hierarchical_a.py` structurally; replace
test cases with A++-specific ones.

### 8.1 Test list

| # | Name | Perturbation | Expected rejection | Validates |
|---|---|---|---|---|
| 1 | `baseline` | none — reference instance N=8, K=2 | none (passes) | Positive baseline |
| 2 | `cost_binding` (inherited) | tamper `sub_0.partial_cost` 30 → 99 | sub G4 during `nargo execute` | Per-segment cost honesty |
| 3 | `boundary_merkle` (inherited) | tamper `glue.boundary_costs[0]` 15 → 5 | glue G6 during `nargo execute` | Boundary edge soundness |
| 4 | `cross_check_c` (NEW, FS-specific) | mix `sub_0`, `sub_1` from cycle A with `glue` from cycle B (same matrix) | `verify_hier_fs.py` cross-check on `c` (and `X` transitively) | Inter-proof cycle binding via chain commitment |
| 5 | `bad_P_i` (NEW) | tamper sub_0's Prover.toml `P_i` to a different Field value | sub G6 during `nargo execute` | Per-segment grand-product faithfulness |
| 6 | `broken_chain` (NEW) | edit glue Prover.toml `h_ins[1]` ≠ `sub_0.h_out` | glue G2 during `nargo execute` | Cross-segment chain continuity |
| 7 | `partition_overlap_fs` (FS analogue of A's overlap) | construct cycle where node 3 appears in both segments; valid edges in matrix | glue G5 during `nargo execute` (∏ P_i ≠ ∏(X+j) at the chain-derived X — Schwartz-Zippel fires) | The grand-product partition check (replaces A's sort partition) |
| 8 | `sanity_N48_K4` | witness-only at N=48, K=4 | none | Patched circuits accept valid witnesses at larger sizes |

Test #7 is the direct analogue of A's "segment overlap" test. The
mechanism is different (grand product vs sort) but the perturbation and
expected outcome are the same. **Document in the test comments that test #7
"only fails because Schwartz-Zippel applies at the unforgeable X" — this is
the empirical demonstration of the FS / grand-product soundness.**

### 8.2 Documentation-only soundness arguments (no test code)

The following attacks are interesting to discuss in the thesis but
**cannot** be implemented as code tests (they would require breaking
Poseidon2):

- **Fixed-X grand-product attack:** if X were chosen before the prover
  committed, the prover could construct fake partitions whose products
  agree at that X. The in-circuit FS construction prevents this.
- **Grinding for a Schwartz-Zippel collision:** the prover tries many cycles
  until one whose chain-derived X happens to land in the ~N-element
  "polynomials agree" bad set. Cost ≈ 2²⁵⁴/N Poseidon2 evaluations.
  Infeasible.

These should appear as comments in the test file pointing to
HIERARCHICAL_EXPLAINED.md §9.10 and supervisor_report_draft.md §7.

---

## 9. Hash-compat test extension

**File:** `tests/hash_compat/noir/src/main.nr` (or a sibling)

Add a test case for `Poseidon2::hash([c], 1)` — the single-input mode that
A++ uses for challenge derivation. The existing test only covers
`Poseidon2::hash([l, r], 2)`.

### 9.1 What to validate

Two cross-checks between Rust and Noir:

1. **Chain step shape:** `Poseidon2::hash([h, node], 2)`. Already covered
   by the existing test (`in_len=2` is the same shape as Merkle
   compression). **Reuse the existing test; no new code.**
2. **Challenge shape:** `Poseidon2::hash([c], 1)`. Add a new test case
   that:
   - In Rust: computes `poseidon2_hash_single(c)` per §4.2 step 2.
   - In Noir: a circuit with public input `expected` and private input `c`,
     asserts `Poseidon2::hash([c], 1) == expected`.
   - Shell harness pipes the Rust output into Noir's Prover.toml.

This MUST PASS before writing the A++ circuits — `Poseidon2::hash([c], 1)`
is the FS-binding load-bearing hash and any Rust/Noir drift kills A++
soundness silently.

### 9.2 Construction reference

For the sponge `Poseidon2::hash(input, in_len)`:
- IV: `iv = in_len * 2^64`
- Initial state (4 elements for BN254 Poseidon2): `[s0, s1, s2, iv]`
- Absorb: for j < in_len, `state[j % RATE] += input[j]` (RATE=3 for BN254
  Poseidon2 with t=4)
- After absorbing `in_len` elements, run the permutation once
- Output: `state[0]`

For `in_len=1`: absorb 1 element into `state[0]`, then permute, then output
`state[0]`. So:
```
state = [input[0], 0, 0, 1 * 2^64]
state = poseidon2_permutation(state)
output = state[0]
```

Lock this construction down via the hash-compat test before relying on it.

---

## 10. Implementation order

This is the order of operations. Each step has a clear acceptance criterion
before moving on.

| Step | What | Acceptance |
|---|---|---|
| 1 | **Reference values (Rust scratch / hand computation).** At N=8, K=2, cycle `[0,5,3,2,7,4,1,6]`, compute h_0..h_8, c, X, P_0, P_1 using the same Poseidon2 instantiation. Verify `P_0 · P_1 == ∏(X+j) for j=0..7` natively. Document the values in this file as a reference table (see §11 — to be filled in during implementation). | The grand-product identity holds for the reference instance. |
| 2 | **Hash-compat extension** for `Poseidon2::hash([c], 1)`. | Noir circuit accepts Rust-computed expected; test passes. |
| 3 | **Sub-circuit skeleton** `hierarchical_segment_fs/src/main.nr` at N=8, M=4, DEPTH=6. `nargo compile`; `bb gates` reports circuit_size ~5-10× larger than at the smallest A scale, dominated by G3 Merkle. | Compiles; gate count sane. |
| 4 | **Glue skeleton** `hierarchical_glue_fs/src/main.nr` at N=8, K=2, DEPTH=6. | Compiles. |
| 5 | **Rust builder extension** `--hierarchical-fs K --out-dir <dir>`. Validate against reference values from step 1 (Prover.toml fields should match). | Manual diff against step 1 reference table. |
| 6 | **First end-to-end run** with the reference instance: `nargo execute × 3`, `bb prove × 3`, `bb verify × 3`. | All 3 proofs verify. |
| 7 | **Verifier `verify_hier_fs.py`.** Cross-check schema from §5.2. | Reference instance passes all 6K+3 checks. |
| 8 | **Negative tests** from §8.1 (#2-#7). | All 6 negative tests reject at the expected point. |
| 9 | **Witness-only sanity at N=48, K=4.** | Patched circuits accept valid witnesses. |
| 10 | **Benchmark harness `run_hier_fs.py`.** Sweep N ∈ {48, 96, 192, 480}, K ∈ {2, 4, 8}. | `results/hier_fs.csv` populated; cross-check passes every cell. |
| 11 | **Aggregate + plot.** | `plots/hier_fs_*.png` written; visually overlay with hier_a and flat_merkle. |
| 12 | **Update `DESIGN.md` §8 progress section.** Move A++ from `[ ]` to `[x]`. | Done. |

Estimated effort: ~1 work-week per the doc's §15.8 estimate. The risky bit
is step 2 (hash compat); everything else is mechanical mirroring of A.

---

## 11. Reference values for the N=8, K=2 instance

**Populated 2026-05-28 (step 1).** Computed by
`tests/hash_compat/rust/src/main.rs` and cross-validated against Noir's
Poseidon2 by `tests/hash_compat/run_test.sh` (both the `[c],1` challenge and
the `[l,r],2` chain step pass). Use the same cycle and edge costs as A's
reference (HIERARCHICAL_EXPLAINED.md §8.9):

- Cycle: `[0, 5, 3, 2, 7, 4, 1, 6]`
- Internal edges (sub_0): 0→5=10, 5→3=12, 3→2=8 (partial_cost=30)
- Internal edges (sub_1): 7→4=11, 4→1=9, 1→6=14 (partial_cost=34)
- Boundary edges: 2→7=15, 6→0=13
- Threshold: 100, total: 92

Chain step is `h_{j+1} = Poseidon2::hash([h_j, cycle[j]], 2)` (iv = 2·2⁶⁴);
challenge is `X = Poseidon2::hash([c], 1)` (iv = 1·2⁶⁴). All values are
32-byte BN254 Field elements, big-endian hex.

```
h_0 = 0x0000000000000000000000000000000000000000000000000000000000000000
h_1 = 0x0b63a53787021a4a962a452c2921b3663aff1ffd8d5510540f8e659e782956f1   Poseidon2(h_0, 0)
h_2 = 0x263a6cc67fee2d0034d79b9070dbbceba5d6679924a0d3d60b45fe862e73fdd1   Poseidon2(h_1, 5)
h_3 = 0x292d067fc20bb50c82c858b471fa3e27beaa10d41cddde3ae7920ea50ede0401   Poseidon2(h_2, 3)
h_4 = 0x249b4bd9b262e23c79d1aa87fa77ea200b5622cef472355bb916564bfe320736   Poseidon2(h_3, 2)  (= h_out_0 = h_in_1)
h_5 = 0x261eb5d6843cb6119129a24aba9490f25583feed479c3763777b1b10be9048d3   Poseidon2(h_4, 7)
h_6 = 0x14cfe2c68776101103e4e00dcbb81fb9bfbf41e666cd2033404e19af7c3e5221   Poseidon2(h_5, 4)
h_7 = 0x1ecf5809ae7642460382108b850d9b31cf3524f65f79eab60e1f3f8a4374b2d2   Poseidon2(h_6, 1)
h_8 = 0x0b43032bbf000f5e35ff8ed6e316b29b58cbd33fe56e2d87ea7dc0588bce59db   Poseidon2(h_7, 6)  (= c)

c   = h_8 = 0x0b43032bbf000f5e35ff8ed6e316b29b58cbd33fe56e2d87ea7dc0588bce59db
X   = Poseidon2([c],1) = 0x031e267ebb904211df3ac4071c17daaa5331665123fe92fdac6b35c9267d1d5a

Per-segment chain anchors:
  sub_0: h_in_0 = h_0 = 0x000...000,   h_out_0 = h_4 = 0x249b4bd9...320736
  sub_1: h_in_1 = h_4 = 0x249b4bd9..., h_out_1 = h_8 = c = 0x0b43032b...ce59db

Grand products (at the X above):
  P_0 = (X+0)(X+5)(X+3)(X+2) = 0x1ab912e08827d1ec7d509e737a01b329b94f2a8fd8486dbe2fe0a156546872b0
  P_1 = (X+7)(X+4)(X+1)(X+6) = 0x27555d776a871e918bc3410b36524a62b78434d551d99764921b2fbfb2a8cbe2
  expected_product = prod_(j=0..7)(X+j) = 0x24b8308221e78905073209a6c773f3126e3f41671213bc03c4c1d3bf9cf3d79c

Identity P_0 * P_1 == expected_product:  OK (verified natively in Rust)
```

The grand-product identity holds because `{0,5,3,2} ∪ {7,4,1,6} = {0..7}` —
that is the partition exactness that A++ enforces non-trivially at large N.

**Caveat on what step 1 validates.** The native identity `P_0·P_1 ==
∏(X+j)` is a *polynomial identity in X* — it holds for any X when the
segment multisets tile `{0..7}`, so it does **not** by itself confirm that X
was derived correctly. The challenge derivation is validated separately by
the single-input hash-compat assertion (`tests/hash_compat`, step 2) and is
re-checked in-circuit by sub-circuit G7 / glue G4 during `nargo execute`.

---

## 12. Soundness invariants (for self-check during implementation)

After a successful run of K+1 proofs + cross-checks, the verifier has
established:

1. **Internal edges bound to root.** Each sub-circuit's G3 enforces M-1
   Merkle proofs against `root`. Poseidon2 collision resistance + leaf-idx
   check binds `edge_costs[i]` to the committed matrix entry.
2. **Boundary edges bound to root.** Glue's G6 enforces K Merkle proofs.
   Same primitives.
3. **Per-segment cost honest.** sub G4 forces `sum(edge_costs) == partial_cost`.
4. **Endpoints bound.** sub G2 forces `start_node`, `end_node` to be the
   actual first/last cycle_segment entries.
5. **Each P_i faithful to its private cycle_segment.** sub G6.
6. **Chain link per segment faithful.** sub G5.
7. **Chain stitches into one global cycle commitment.** glue G1, G2, G3
   force `c` to be the chain over the full cycle in cycle order.
   Poseidon2 collision resistance → distinct cycles produce distinct c.
8. **X unforgeably bound to c.** Each sub's G7 and glue's G4 (defense in
   depth) + verifier cross-check on (c, X). Random oracle: prover cannot
   find c' ≠ c with Poseidon2(c') = X.
9. **Partition exact.** Glue G5: `∏ P_is == ∏(X+j) for j=0..N-1` (in-circuit
   under Option B). By Schwartz-Zippel at the unforgeable X, multiset of
   segments = {0..N-1} except with probability N/2²⁵⁴.
10. **Cycle closes.** Partition exactness + glue G6 imply boundary edges
    connect distinct segments — no self-loops, no broken closures.
11. **Total cost bounded.** Glue G7.

Together: a Hamiltonian cycle on N nodes, all N edge costs bound to the
committed matrix, total cost ≤ threshold, partition hidden modulo
endpoints, soundness error ≤ N · 2⁻²⁵⁴.

---

## 13. Things to watch out for

These are issues that surfaced during planning and could bite during
implementation. Keep them in mind:

### 13.1 The chain is over cycle ORDER, not multiset

Two cycles with the same node multiset but different orderings produce
different `c`, hence different `X`, hence different `P_i`. The chain is
what gives Fiat-Shamir its commitment temporality. **Don't be tempted to
"optimise" by chaining over sorted segments** — that would make X
predictable to the prover (sorted segments don't depend on cycle order, so
the prover could pick X first and adapt the cycle).

### 13.2 `h_in_0 = 0` is non-negotiable

Glue G1 enforces this. If `sub_0` got to choose `h_in_0`, the prover could
grind on starting values to find a useful `c`. The constant `0` is the
only thing that ties the chain to "the prover starts from a fixed point."

### 13.3 G7 in subs is NOT redundant despite the cross-check

Both layers (in-circuit + cross-check) work together. Cross-check ensures
all proofs share the same X; G7 in subs ensures that shared X is actually
`Poseidon2(c)` — without it, a prover could publish a sub-proof with a
self-chosen X that satisfies G6 vacuously, and only the verifier's
software check would catch it. Cryptographic > software for soundness.

### 13.4 The chain step direction matters

`h_{j+1} = Poseidon2(h_j, cycle[j])` — `h_j` is the LEFT input, node index
is the RIGHT input. This matches `poseidon2_compress(left, right)` in the
existing Rust code. Be consistent or the Rust and Noir computations
diverge silently.

### 13.5 `Poseidon2::hash([c], 1)` is different from `Poseidon2::hash([c, 0], 2)`

The sponge's IV depends on `in_len`, and the padding/absorption pattern
differs. Don't substitute one for the other. The hash-compat test in step
2 of the implementation order validates this.

### 13.6 Field arithmetic in the Rust builder

`acir::FieldElement` supports `+`, `*`, and `==`. The grand-product loop
uses these directly. No need to import an external arkworks dependency.

### 13.7 Glue's N global

N is still needed in the glue (boundary Merkle's `from*N+to` AND the new
`for j in 0..N` loop in G5). Patcher logic from A works unchanged. M is
NOT needed in the glue (no per-segment iteration in glue).

### 13.8 K=2 special-cases

The chain-stitching loop `for i in 0..(K-1)` iterates once at K=2 (only
one stitch: `h_ins[1] == h_outs[0]`). The chain terminal check
`h_outs[K-1] == c` becomes `h_outs[1] == c`. The grand product `∏ P_is`
becomes `P_is[0] * P_is[1]`. All natural.

### 13.9 Shadow dir collision with A

`/tmp/hier_a_shadows` is A's. Use `/tmp/hier_fs_shadows` for A++ to allow
running both harnesses simultaneously if desired.

### 13.10 Cross-checking c across proofs is the key new check

This is the analogue of A's "same root" check. Without it, K+1 proofs
could be about K+1 different cycles (each chain-valid but distinct).
verify_hier_fs.py must enforce this.

### 13.11 Don't compute `expected_product` natively in the verifier

Under D5 = Option B, this is in-circuit. The Python verifier has no
`expected_product` to recompute. Don't add the loop "just in case."

### 13.12 The 87 gates/Poseidon2 figure

This is the UltraHonk + Plookup figure, established for the flat baseline.
Verify it still holds for A++'s Poseidon2 usage at first compile — Noir's
Poseidon2 library is the same, and `bb gates` will report the actual
count. If it differs significantly (say, ±20%), investigate before
proceeding to benchmarks.

### 13.13 Memory floor expectation

A's glue had an O(N) sort that created a ~159 MB peak_mb floor at N=480.
A++'s glue has no O(N) sort — only O(N) Field mults in a tight loop.
**Expected glue peak_mb at N=480, K=4: substantially below 100 MB.** If
not, investigate (it might mean the in-circuit `for j in 0..N` loop has
unexpected memory overhead).

### 13.14 A++ privacy is computational, not information-theoretic

When writing up or presenting A++, do **not** claim the public Field
aggregates "hide the partition" unconditionally. They don't. Two public
values are confirmation oracles (full argument in
`HIERARCHICAL_EXPLAINED.md` §9.11 and the work-factor table in §14.2):

- **`P_i` leaks the segment multiset** at ≈ C(N, M) work: `P_i = ∏(X +
  node)` is a polynomial evaluation at the *public* X, so a verifier can
  enumerate size-M subsets of {0..N-1} and find the one whose product
  matches — recovering exactly what Variant A prints as `sorted_nodes`.
- **The chain anchors `h_in_i, h_out_i` leak interior order** at ≈ (M-2)!
  work: both ends of each segment's chain are public and the chain step
  consumes only public-domain inputs (node indices), so the interior
  ordering is a checkable brute-force.

The anchors are public **because** the architecture is K+1 independent
proofs + off-circuit cross-checks (D6, §5.2): the verifier can only stitch
`h_ins[i+1] == h_outs[i]` and `h_outs[K-1] == c` across separate proofs if
those values are public inputs. Recursion would keep them private. Frame
this as the measurable price of non-recursion on the frontier, not as a
defect. It does not affect any gate-count / memory / timing benchmark —
only the privacy claim's wording.

---

## 14. Updates to other documents (deferred)

These can wait until A++ is implemented and benchmarked:

- `DESIGN.md` §8 — add A++ checklist (mirror A's), update memory floor
  table with A++ measurements.
- `HIERARCHICAL_EXPLAINED.md` §9.9 — note that under this implementation
  `expected_product` is in-circuit (the doc currently says
  "verifier-supplied"). Both are valid; document the engineering choice.
- `supervisor_report_draft.md` §7-§8 — fold A++ empirical numbers in.

---

## 15. Reference documents

- `HIERARCHICAL_EXPLAINED.md` §9 — full Variant A++ theory (grand product
  as multiset commitment, Fiat-Shamir construction, soundness chain,
  privacy bounds, worked example)
- `VARIANT_A_IMPLEMENTATION.md` — the A blueprint; A++ mirrors its
  structure and tooling
- `DESIGN.md` §8 — engineering decisions log; benchmark interpretation
  notes
- `SESSION_SUMMARY.md` — chronological session notes
- `supervisor_report_draft.md` §7 — dualism argument; §7.6-7.7 mapping
  A/A++/B to use cases
- `HOWTO.md` — `nargo` / `bb` invocation reference
- `tests/hash_compat/` — Poseidon2 cross-validation pattern

---

## 16. Out of scope for A++

- **Variant B** (flat-full sub-matrix public): separate from A++; shares
  A's glue, not A++'s. Estimated ~3 work-days after A++ is working.
- **Recursive composition** of K+1 proofs into one (replacing verifier
  cross-checks with in-circuit verification): explicitly future work.
- **Folding-scheme variant** (Nova/ProtoStar): natural continuation,
  out-of-thesis-scope.
- **Mixed-size segments** (N not divisible by K): not supported; benchmark
  N choices are picked to satisfy `N % K == 0` for K ∈ {2, 4, 8}.
- **Hash commitment for sorted node sets** (alternative partition-hiding
  mechanism): noted in DESIGN.md as future direction; A++ is the chosen
  partition-hiding mechanism.
