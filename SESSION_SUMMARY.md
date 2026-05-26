# TSP ZKP Project — Session Summary
## Last updated: 2026-05-26

---

## Research Question

**Reframed 2026-05-23, sharpened 2026-05-26.** Originally: *"at what N does hierarchical ZKP outperform flat?"* Gate-count analysis on 2026-05-23 showed this framing pre-supposes a single dimension of "outperform" that does not exist. The 2026-05-26 session sharpened the reframe further: the variants don't compete on cost because they don't prove the same statement.

> **Zero-knowledge proofs for TSP are best understood as a *family* of cryptographic statements, distinguished by what part of the input (cost matrix, partition, segment endpoints, per-segment costs) is private vs public to the verifier. Each variant in this thesis is the natural proof design for a specific point in that family. The structural reason no single variant universally dominates is a dualism between optimisation and ZK proving: hierarchical decomposition imposes a constraint in optimisation (good — search shrinks) and weakens a constraint in ZK (bad — soundness must be restored by O(N) glue work). The NP asymmetry between finding and checking holds, but the way the two respond to decomposition is itself asymmetric: classical decomposition gives optimisation an algorithmic speedup; in ZK it gives only embarrassingly-parallel speedup, and only at the cost of partition disclosure.**

The flat baseline characterisation (N≈175 crossover between flat_full and flat_merkle) stands unchanged — that comparison is meaningful because both prove the same statement. Hierarchical variants are now reported not as competitors to flat_merkle but as the natural proof designs for distinct use-case classes. See "Variant-as-Statement Reframe" and "Use-Case Mapping" sections below.

### What the thesis explicitly does NOT claim

NP asymmetry is *not* violated. Verification remains polynomial-time (often sublinear). The thesis claims the more specific structural fact that *hierarchical decomposition* — a technique that exploits NP asymmetry in classical optimisation by pruning the search space — does not transfer to ZK proving for problems with non-local constraints. This is a refinement of how NP asymmetry interacts with proof-system design, not a counterexample to it.

---

## Stack

- **Noir** v1.0.0-beta.20 + **Barretenberg UltraHonk** `bb v5.0.0-nightly.20260324`
- Compile-time global `N: u32` and `DEPTH: u32`; each value of N needs a separate compiled circuit
- **Python pipeline** (`conda env: zk-tsp`): instance generation, TSP solver (nearest-neighbour + 2-opt), input formatting, benchmarking harness, complexity analysis
- **Rust**: Poseidon2 cross-validation binary + Merkle tree builder (`pipeline/merkle_builder/`)
- All Python commands via: `conda run -n zk-tsp python3`

---

## What the Circuit Proves

"I know a Hamiltonian cycle on a complete weighted graph of N nodes, where edge costs are committed to by a Poseidon2 Merkle root (or passed as N² public inputs), and the total cycle cost ≤ threshold T."

**Public inputs (flat-full variants):** `cost_matrix: [u64; N*N]`, `threshold: u64`
**Public inputs (flat-merkle variant):** `root: Field`, `threshold: u64`
**Private witness (all variants):** `cycle: [u32; N]`, plus variant-specific auxiliary witnesses

---

## Circuit Variants — Implementation Status

| Variant | Permutation check | Circuit | Tests | Benchmarks |
|---|---|---|---|---|
| `flat_full_pairwise` | vᵢ ≠ vⱼ via modular inverse for all i≠j | ✓ | ✓ | ✓ to N=500 |
| `flat_full_sort` | Sort cycle, assert equals [0..N-1] | ✓ | ✓ | ✓ to N=500 |
| `flat_full_invperm` | Explicit inverse-permutation witness | ✓ | ✓ | partial (small N) |
| `flat_full_presence` | Mutable bool array `seen[N]` | ✓ | ✓ | partial (small N) |
| `flat_merkle_presence` | Mutable bool array `seen[N]` + Merkle proofs | ✓ | ✓ | ✓ to N=500 |

**Pending benchmarks:** flat_full_invperm and flat_full_presence need full runs to N=500 to complete the permutation overhead analysis.

### Four-group structure (all variants)

- **GROUP 1**: range check (`cycle[i] < N`)
- **GROUP 2**: permutation check (variant-specific)
- **GROUP 3**: edge cost verification + accumulation
- **GROUP 4**: threshold check (`total_cost <= threshold`)

### Type rationale (documented in supervisor report)

- `u32` for cycle indices: cheap 32-bit range check; works as array index type
- `u64` for edge costs and threshold: native 64-bit accumulation; avoids Field overflow risk
- `Field` for Merkle siblings and intermediate hashes: Poseidon2 operates natively in the field
- `bool` for path_bits: zero-cost conditional in circuit; no range check needed

---

## Empirical Complexity Fits

### Flat-full gate counts (from `pipeline/analyze_complexity.py`)

```
pairwise:  8.25N² + 14.4N  + 2829   R²=1.000
sort:      7.25N² + 26.5N  + 2829   R²=1.000
invperm:   7.25N² + 20.4N  + 2831   R²=1.000
presence:  7.25N² + 25.0N  + 2837   R²=1.000
```

The 7.25 N² coefficient is identical for sort/invperm/presence — it comes entirely from GROUP 3 cost matrix ROM lookups, not the permutation check. The permutation variants only differ in the linear coefficient.

### Benchmark results from `results/500.csv` (pairwise, sort, merkle at N=5..500)

**Proving time:**
- flat_full: ∝ N^1.84 empirically (consistent with O(N²) gates × sub-linear prover scaling)
- flat_merkle: ∝ N^0.92 — sub-linear in N (key selling point)

**Memory (peak_mb):**
- flat_full: ∝ N^1.75
- flat_merkle: ∝ N^1.06 — nearly linear

**Verification time:**
- flat_full: grows O(N²) in practice — verifier must hash all N² public inputs before checking; the "O(1) SNARK verification" claim applies to proof-checking computation only, not public input processing
- flat_merkle: truly O(1) — only 2 public inputs (root, threshold)

**Proof size:** constant **14,656 bytes** for all variants at all N (UltraHonk property)

---

## Key Technical Findings

### Finding 1: Empirical crossover at N≈175 (theory with correct gate cost predicts same)

- flat_full_sort vs flat_merkle_presence crossover is empirically at **N≈175**
- Theory (old): using ~264 gates/Poseidon2 call predicted crossover at N≈695
- Theory (corrected): UltraHonk with Plookup costs ~**87 gates/Poseidon2 call** (Plookup lookup tables amortize the S-box cost from ~264 arithmetic gates to ~87)
- Substituting 87 into the crossover formula gives **N≈175 — exact match with data**

### Finding 2: Poseidon2 gate cost

| Source | Gates/call |
|---|---|
| Literature (arithmetic gates) | ~264 |
| UltraHonk empirical (with Plookup) | ~87 |

This ~3× discrepancy explains the crossover shift. The finding is broadly applicable to anyone benchmarking Noir circuits with hash-heavy workloads.

### Finding 3: ACIR opcode count is a misleading metric for cross-variant comparison

- Poseidon2 = 1 ACIR opcode but ~87 gates
- Public u64 = 1 ACIR opcode but ~7.25 gates
- ACIR crossover (N≈30) is misleading; gate-count crossover (N≈175) is the correct metric

### Finding 4: Boolean presence array is optimal among flat-full permutation variants

Theoretically and empirically: same N² coefficient as sort/invperm, lowest constant. No extra witness, no ROM, only RAM.

### Finding 5: Proof size is constant across all variants and all N (14,656 bytes)

UltraHonk property. Verification cost is also essentially constant for flat_merkle.

### Finding 6: Hierarchical Merkle does not reduce total gate count *(analytical, 2026-05-23)*

Total cost: `(N + K) × DEPTH × 87 + O(N)`, strictly larger than flat_merkle's `N × DEPTH × 87 + O(N)`. At N=500, K=4 the overhead is ~1.5%. The K boundary Merkle proofs and the O(N) partition check in the glue exactly absorb any per-segment saving. Every cycle edge requires one Merkle proof regardless of how the cycle is partitioned.

### Finding 7: Hierarchical flat_full saves gates by disclosing the partition *(analytical, 2026-05-23)*

Each sub-circuit takes its M×M sub-matrix as public input → total public-input cost `O(N²) → O(N²/K)`. Beats flat_merkle at K ≥ 3 for N=500 and continues to fall linearly with K. Currency paid: verifier learns which M nodes belong to which segment (privacy that flat_merkle preserves).

### Finding 8: Hierarchical decomposition gives embarrassingly-parallel, not algorithmic, speedup *(analytical, 2026-05-23, sharpened 2026-05-26)*

Although hierarchical Merkle does not reduce total gates, the K sub-proofs are independent. With K parallel workers, wall-clock proving time ≈ `proving_time(N/K) + glue` → roughly K-fold speedup. Per-prover peak memory ≈ `memory(N/K)` → ~K-fold reduction per process. **Total work summed across the K workers stays the same** — the parallelism is embarrassingly parallel, not algorithmic. This distinction matters for the cross-domain comparison with classical TSP heuristics: classical hierarchical decomposition genuinely shrinks the search space (algorithmic win); hierarchical ZK does not (only embarrassingly-parallel win). At large N, single-machine memory exhaustion is the binding constraint and hierarchical becomes "the only feasible design." Hierarchical ZK is a **scaling strategy**, never an algorithmic improvement.

### Finding 10 (added 2026-05-26): Variants prove different statements, not different cost designs

The variants we initially compared on cost are in fact proving different statements about the same TSP instance. Flat Merkle proves "∃ Hamiltonian cycle with cost ≤ T against committed matrix." Variant A adds "...that respects this disclosed partition." Variant A++ adds "...that decomposes into K segments with disclosed endpoints and per-segment costs, the segments themselves hidden." Variant B adds "...with these disclosed M×M sub-matrices." Each is strictly more specific than flat_merkle. The privacy loss is *content of the statement*, not a bug. Variants proving different statements cannot be totally ordered — the absence of a single best design is a structural consequence of the reframe.

### Finding 11 (added 2026-05-26): Each variant has a natural use case class

- **flat_merkle**: generic baseline; logistics SLA audit or ESG reporting where only cycle privacy matters and partition is not part of the audit.
- **Variant A**: multi-team / multi-region accountability where the partition is operational (delivery zones, team assignments). Per-segment partial_costs are accountability artifacts. Disclosure is intentional.
- **Variant A++**: same scaling benefits as A but partition hidden. For competitively sensitive partitions.
- **Variant B**: public-matrix scenarios (smart-city fleet routing on OSM, public benchmarks) where matrix privacy is irrelevant and total prover cost binds.

---

## ACIR Opcodes vs UltraHonk Gates Reference

| Operation | ~Gates |
|---|---|
| ACIR Arithmetic opcode | ~1 |
| ACIR MemoryOp (ROM) | ~1–2 |
| ACIR MemoryOp (RAM) | ~3–5 |
| u32 range check (32-bit) | ~8 (Plookup 4-bit chunks) |
| u64 range check (64-bit) | ~16 (Plookup 4-bit chunks) |
| u64 public input | ~7.25 (range + encoding) |
| Poseidon2::hash([l,r], 2) | ~87 (UltraHonk + Plookup empirical) |
| u64 addition | ~1 |

---

## Merkle Variant: flat_merkle_presence

### Merkle tree design

- **Leaves**: flat cost matrix `leaf[from*N + to]` = cost of directed edge from→to
- **Padding**: leaves padded to next power of 2 (`n_padded = 2^ceil(log2(N²))`)
- **DEPTH** = `ceil(log2(N²))` — examples: N=4→DEPTH=4, N=5→DEPTH=5, N=50→DEPTH=12, N=500→DEPTH=18
- **Indexing**: 1-indexed array; leaves at positions `[n_padded .. 2*n_padded-1]`; node `i`'s children are `2i` (left) and `2i+1` (right); parent of `j` is `j/2`
- **Compression**: `parent = Poseidon2::hash([left_child, right_child], 2)`
- **Path bits**: LSB-first encoding; `path_bits[d]=true` means current node is right child at level d; `leaf_idx = Σ path_bits[d]·2^d`
- **Leaf index check** (soundness-critical): GROUP 3 reconstructs `leaf_idx` from `path_bits` and asserts it equals `from*N + to`. Without this, prover could substitute a proof for a different leaf.

### Soundness argument for GROUP 3

1. `root` is a public input — unalterable by prover
2. Poseidon2 collision resistance: cannot invert to forge a leaf
3. Leaf index check: path bits must reconstruct to exactly `cycle[i]*N + cycle[(i+1)%N]`

Together (2) and (3) force `edge_costs[i] == cost_matrix[cycle[i]][cycle[(i+1)%N]]`.

### Data pipeline (5 stages)

1. Instance generator → cost matrix (N×N)
2. TSP solver → Hamiltonian cycle + edge costs
3. Merkle tree builder (Rust, `pipeline/merkle_builder/`) → root, N sibling arrays, N path_bits arrays
4. Prover.toml formatter → write all fields flat row-major
5. nargo execute + bb prove/verify

### `(i+1) % N` in GROUP 3

Both `i` and `N` are compile-time known during unrolling; the modulo is resolved at compile time. No runtime modulo gate is emitted.

---

## Merkle Walk-through Examples (in supervisor_report_draft.md)

### N=4 (DEPTH=4, n_padded=16)

Cycle: [0, 1, 2, 3], costs: [5, 3, 7, 4], total=19, threshold=25

| Edge | leaf idx | tree node | path_bits (LSB-first) |
|---|---|---|---|
| 0→1 | 1 | 17 | [1,0,0,0] |
| 1→2 | 6 | 22 | [0,1,1,0] |
| 2→3 | 11 | 27 | [1,1,0,1] |
| 3→0 | 12 | 28 | [0,0,1,1] |

### N=8 (DEPTH=6, n_padded=64)

Cycle: [0,1,2,3,4,5,6,7], costs: [10,12,8,15,11,9,14,13], total=92, threshold=100
- Edge 0→1: leaf=1, tree node=65, path_bits=[1,0,0,0,0,0]
- Sibling path: 65→32→16→8→4→2→1 with siblings [64,33,17,9,5,3]

---

## Field Type Optimization Analysis (session 2026-05-22)

The Noir docs recommend `Field` over `u32`/`u64` for proving efficiency (integer types add implicit range checks). Analysis for our circuits:

| Variable | Change | Safe? | Savings at N=500 | Verdict |
|---|---|---|---|---|
| `edge_costs: [u64; N]` | → `[Field; N]` in flat_merkle | Yes — Merkle proof constrains range | ~8,000 gates (~1%) | Worth doing; modest |
| `cycle: [u32; N]` | → `[Field; N]` | Blocked — array indexing requires integer type | 0 (compiler forces cast back) | Not worth it |
| `total_cost: u64`, `threshold: pub u64` | → `Field` | No — comparison constraint cost identical; u64 provides overflow safety | 0 | Not worth it |

**Key insight**: For `flat_merkle_presence`, the Merkle proof is doing the range-bounding work that the `u64` type system would otherwise provide — making the type change safe in this specific variant but not in flat_full variants. This is a non-obvious soundness argument worth a paragraph in the implementation section.

**Bottom line**: ~1% gate savings from `edge_costs` change only. Dominant cost is Poseidon2 (N×DEPTH×87 gates = 783,000 gates at N=500). Type changes won't visibly shift benchmark curves.

---

## Hierarchical Design — Conceptual Framework (session 2026-05-23)

### The dualism (central conceptual finding)

> Hierarchical decomposition **adds** a structural constraint in optimisation and **weakens** a soundness constraint in zero-knowledge proving. Same operation, opposite direction in constraint space, opposite effect on cost.

- **Optimisation:** decomposition imposes "tour respects partition," shrinking search space from N! to ~K·((N/K)!)·K!. Speedup paid for in solution quality (approximation error).
- **ZK proving:** decomposition weakens "every node visited exactly once globally" to K local checks. Unsound on its own (cheating prover could place node v in two segments). Restoration requires O(N) partition check in glue + K boundary Merkle proofs — this addition exactly cancels the per-segment saving.
- **Root cause:** the NP asymmetry between *finding* and *checking*. Hierarchical decomposition is a search-pruning trick; ZK does no search.
- **Sharpened framing (2026-05-26):** NP asymmetry holds; what fails is its transfer under decomposition. Classical hierarchical decomposition exploits the asymmetry by trading verification overhead for search reduction — a win because reducing exponential search by polynomial overhead is always worth it. In ZK, the trade has nothing to redeem on the search side (the prover already has the witness), so the verification overhead is paid without any compensating saving. The asymmetry persists; the strategy that exploits it does not transfer.

### Related insights

- **Approximation has no ZK analogue** — partial verification is not partial proof, it's no proof. The quality/speed trade-off of heuristic optimisation doesn't port.
- **Constraints have flipped sign across the two domains** — adding a constraint makes optimisation cheaper, makes ZK more expensive.
- **Hierarchical ZK works well only for locally-factoring problems** — Circuit-SAT yes (Halo/Nova/ProtoStar work over it), Hamiltonian-cycle no. TSP is a worst-case problem class for hierarchical ZK.
- **The ZK verifier cannot iteratively assist the prover** — no guess-and-check dynamic, so metaheuristic-style speedups don't apply.
- **Folding schemes (Nova, ProtoStar, SuperNova) are the natural escape** — sidestep per-recursion verifier overhead with a constant-cost folding step. Out of scope for this thesis but the natural continuation.
- **The negative result is itself a positive contribution** — there is a widespread informal belief that "hierarchical = obviously better" by analogy to optimisation. Showing rigorously why this analogy fails for TSP corrects a real misconception.

### Three hierarchical variants planned

| Variant | Privacy | Total gates vs flat_merkle | Glue partition cost | Soundness basis |
|---|---|---|---|---|
| **A** — Merkle, sorted nodes public | partition revealed (segment node sets) | same (~+1.5%) | O(N) sort | unconditional |
| **A++** — Merkle, grand product + cycle-hash Fiat-Shamir | interior nodes hidden (only K endpoints revealed) | ~+5.5% over A (M Poseidon2/sub-circuit for hash chain) | O(K) multiplications | full Fiat-Shamir (~2^-254) |
| **B** — flat_full, sub-matrix public per segment | partition + per-segment sub-matrices revealed | O(N²/K), beats flat_merkle at K≥3 (N=500) | O(K) (boundary Merkle only) | unconditional |

All three share architecture: K segment sub-circuits + 1 glue circuit. They differ in (a) cost-matrix exposure and (b) partition-check mechanism. Variant A++ is the privacy-optimal point on the Merkle branch; Variant B is the gates-optimal point on the privacy-disclosing branch. A is the simple baseline that A++ refines.

### Variant-as-Statement Reframe (session 2026-05-26)

Each variant proves a strictly different cryptographic statement:

| Variant | Statement |
|---|---|
| flat_merkle | "∃ Hamiltonian cycle on N nodes, cost ≤ T, against committed root" |
| **A** | "...that respects this disclosed partition and visits each segment start_i → end_i with internal cost sum partial_cost_i" |
| **A++** | "...that decomposes into K segments of M nodes with disclosed endpoints, disclosed per-segment cost sums, and segments bound by Field-valued aggregates (P_i, h_in, h_out)" |
| **B** | "...with root used only for boundary edges and disclosed M×M sub-matrices for internal edges; partition disclosed" |

**Implication:** the variants are not alternative optimisations of the same proof. They are alternative proofs of *different statements*. The "crossover" framing was wrong because variants proving different statements cannot be totally ordered.

### Use-Case ↔ Variant Mapping (session 2026-05-26)

| Variant | Natural use cases | Why this variant |
|---|---|---|
| flat_merkle | Logistics SLA audit (matrix private, only root visible); generic "private cycle on private graph" | Maximum privacy; only existence statement needed |
| **A** | Multi-team SLA accountability; cross-org cost-sharing; regulated zoning where partition is operational; ESG reporting by region | Partition disclosure is *operationally required*; per-segment partial_costs are accountability artifacts; parallelism corresponds to operational units |
| **A++** | Same scenarios as A but partition is competitively sensitive; maximum-privacy hierarchical option | Recovers most of flat_merkle's privacy while keeping A's parallelism. Costs ~5.5% extra sub-circuit gates |
| **B** | Smart-city fleet routing on public road networks; TSPLIB benchmark verification; non-sensitive matrix + binding gate-cost constraint | Matrix is public anyway, so sub-matrix disclosure is free in privacy terms and saves substantially in gates |
| (folding — future) | Same as A++ but verifier overhead is the binding constraint | Out of scope; UltraHonk baseline is what folding designs would need to beat |

### Commitment Trust Mechanisms (session 2026-05-26)

Merkle commitment to the cost matrix only has meaning if there is an external trust anchor — otherwise the prover commits to a self-serving fictitious matrix. The thesis takes no position on which anchor is appropriate (application-level choice), but documents the standard candidates:

| Trust mechanism | How it binds the commitment | Example |
|---|---|---|
| **Authority signature** | Trusted third party signs the root | Regulator signs operator's quarterly cost matrix; SLA proofs work against signed root |
| **Trusted oracle** | Neutral data provider publishes signed roots | City data provider publishes signed Merkle root of pairwise travel times monthly |
| **Cross-attestation** | Multiple stakeholders co-commit | Two organisations sharing a logistics network sign the joint root |
| **Public timestamping** | Root anchored to append-only ledger before any proofs | Operator publishes root to blockchain or transparency log at known time |
| **Decommitment-on-dispute** | Matrix opened to court/arbitrator under legal process | Root is the binding artifact in normal operation; underlying matrix is disclosed only on dispute |

**Two distinct functions of the commitment depending on regime:**
- *Matrix-private regime:* the commitment provides **privacy** (verifier holds only root, learns no entries) AND **integrity** (prover bound to one matrix across proofs). Useful for proprietary cost data.
- *Matrix-public regime:* the commitment provides **integrity only** (verifier hashes the public matrix and checks root matches). No privacy work done. Still useful — prevents prover from sneakily using a different matrix.

### Privacy analysis for Variant A (session 2026-05-26)

At the worked example N=8, K=2, M=4:
- Verifier sees: partition {0,2,3,5} | {1,4,6,7}, endpoints (0→2, 7→6), partial_costs (30, 34), threshold 100.
- Candidate cycles remaining: (M-2)!^K = 2!² = 4. Out of (N-1)! = 5040.
- Bits leaked: log₂(5040/4) ≈ 10.3.

For general N, K, M: bits leaked ≈ `log₂((N-1)!) − K·log₂((M-2)!)`. At N=480, K=4: ~800 bits leaked out of ~4000 total cycle entropy.

**Threat model dependence:**
- *Matrix private to prover:* leakage is purely structural (partition + macro skeleton). No filtering possible. Variant A appropriate.
- *Matrix public to verifier:* verifier can compute candidate cycle costs and filter against partial_costs. For small N may uniquely identify the cycle; for large N candidate count remains too large to enumerate. Variant A still useful but materially weaker than under matrix-private regime — this is where A++ pays for itself.

### Design decisions for sub-circuit + glue (settled 2026-05-23, augmented 2026-05-26)

- **Real glue circuit** (Noir), not a Python verification script — end-to-end ZK story.
- **Independent sub-proofs + glue, not recursive composition** (settled 2026-05-26). K+1 independent UltraHonk proofs; verifier runs `bb verify` K+1 times AND checks shared public-input fields agree across proofs (same root; glue's all_sorted_nodes = concat of sub-proofs' sorted_nodes; starts/ends/partial_costs agree). Recursive composition deferred to future work alongside folding. Cross-checks are O(N) trivial equality at verifier — negligible.
- **N divisible by lcm(K)** (settled 2026-05-26). Benchmarks use N ∈ {48, 96, 192, 480} so K ∈ {2, 4, 8} all give integer M. N=480 is the comparison anchor against flat_merkle's N=500 (~4% off).
- **Public sorted node set**, not ordered cycle — preserves in-segment visit order privacy at no extra cost (sort-based permutation check produces sorted array as byproduct).
- **Boundary edges verified in glue**, not in sub-circuit — sub-circuit treats segment as a standalone instance; glue takes responsibility for stitching.
- **K=2 hardcoded first**, parameterise K as compile-time global immediately after.
- **Glue shared between A and B**; A++ has its own glue.
- Sub-circuit groups (analogous to flat circuits):
  - GROUP 1: range check (`cycle[i] < N`)
  - GROUP 2: sort-based permutation check, assert `sort(cycle) == sorted_nodes` (public output)
  - GROUP 3: endpoint binding (`start_node == cycle[0]`, `end_node == cycle[M-1]`)
  - GROUP 4: M-1 Merkle proofs for internal edges (same logic as flat_merkle GROUP 3)
  - GROUP 5: cost binding (`sum(edge_costs) == partial_cost`)
- Glue groups:
  - GROUP 1: connectivity (`ends[i] == starts[(i+1) % K]`)
  - GROUP 2: global partition — sort concatenated K×M = N node outputs, assert == `[0..N-1]`
  - GROUP 3: K boundary Merkle proofs (edges `ends[i] → starts[(i+1)%K]`)
  - GROUP 4: `sum(partial_costs) + sum(boundary_costs) <= threshold`

### Sub-circuit interface

```
Public inputs:
  root:         Field             // shared Merkle root of N×N cost matrix
  sorted_nodes: [u32; M]          // segment's nodes, sorted ascending
  start_node:   u32               // first node of segment in cycle order
  end_node:     u32               // last node of segment in cycle order
  partial_cost: u64               // sum of M-1 internal edge costs

Private witness:
  cycle_segment: [u32; M]              // segment in cycle order
  edge_costs:    [u64; M-1]
  siblings:      [Field; (M-1)*DEPTH]
  path_bits:     [bool;  (M-1)*DEPTH]
```

### Glue interface

```
Public inputs:
  root:             Field
  threshold:        u64
  all_sorted_nodes: [u32; N]      // concatenation of K sub-circuit sorted_nodes
  starts:           [u32; K]
  ends:             [u32; K]
  partial_costs:    [u64; K]

Private witness:
  boundary_costs:        [u64; K]
  boundary_siblings:     [Field; K*DEPTH]
  boundary_path_bits:    [bool;  K*DEPTH]
```

### Variant A++ — Grand product + in-circuit Fiat-Shamir (added 2026-05-23)

**Idea:** replace the O(N) sort-based partition check in the glue with a multiset-equality argument via grand product. Each sub-circuit publishes `P_i = ∏_{v in segment_i}(X + v)`; glue verifies `∏_i P_i = ∏_{j=0}^{N-1}(X + j)`. The challenge `X` must be unpredictable to the prover, enforced by binding `X` to a hash-chain commitment of the global cycle (in-circuit Fiat-Shamir).

**Construction:**

1. Prover computes hash chain over the cycle: `h_0 = 0`, `h_{j+1} = Poseidon2(h_j, cycle[j])`. Set `c = h_N`, `X = Poseidon2(c)`.
2. Each sub-circuit additionally proves:
   - Challenge derivation: `X == Poseidon2(c)`
   - Hash chain link: starting from `h_in_i`, folding the M segment values gives `h_out_i` (M Poseidon2 calls)
   - Grand product: `P_i == ∏(X + cycle_segment[j])` (M multiplications)
3. Glue circuit additionally proves:
   - Chain init: `h_ins[0] == 0`
   - Chain link: `h_ins[i+1] == h_outs[i]`
   - Chain terminal: `h_outs[K-1] == c`
   - Challenge re-derivation: `X == Poseidon2(c)`
   - Grand product partition: `∏ P_is == expected_product` (verifier recomputes `expected_product = ∏(X+j)` off-circuit, O(N) work — same cost class as flat_merkle's verifier already pays)

**Sub-circuit public-input delta vs A:**
```
ADDED:    c, X, P_i, h_in_i, h_out_i       (5 Field values)
REMOVED:  sorted_nodes[M]                  (M u32 values)
```
Net: O(M) → O(1) per sub-circuit.

**Glue public-input delta vs A:**
```
ADDED:    c, X, P_is[K], h_ins[K], h_outs[K], expected_product
REMOVED:  all_sorted_nodes[N]
```
Net: O(N) → O(K).

**Cost:**
- Per sub-circuit: ~(M+1) Poseidon2 + M multiplications additional ≈ `M × 87` gates. Overhead ratio vs internal Merkle cost: `1/DEPTH ≈ 5.5%` at N=500.
- Glue partition check: O(N) sort → O(K) multiplications. Real win.

**Soundness chain:**
- `X` bound to `c` via Poseidon2 (one-way)
- `c` bound to cycle via hash chain (collision-resistant) enforced jointly by all K sub-circuits + glue
- Prover cannot fake `X` without faking cycle
- Grand product check at unpredictable `X` gives ~`2^-254` soundness (Schwartz-Zippel)

**Parallelism:**
- Sequential prelude: hash chain precomputation (N Poseidon2 in native code, ~100µs at N=500). Negligible.
- After prelude: K sub-provers run fully independently. Parallelism benefit preserved.

**Why "in-circuit Fiat-Shamir":** the same trick is standard inside recursive SNARKs (outer circuit derives challenges from inner-proof commitments via Fiat-Shamir). Here applied at the application level across sub-proofs of the same outer statement. Variant A++ is essentially a non-recursive instantiation of the recursive-Fiat-Shamir pattern, avoiding the per-recursion verifier-circuit overhead.

---

### Privacy analysis (informal bit-leakage)

| Variant | Verifier learns | Bits leaked (informal) |
|---|---|---|
| flat_merkle | nothing | 0 |
| **A** — Hierarchical Merkle, sorted nodes public | partition + endpoints + per-segment costs | ~N log K + K log N |
| **A++** — Hierarchical Merkle, grand product + Fiat-Shamir | only endpoints + per-segment costs + Field aggregates | ~2K log N |
| Hierarchical Merkle, ordered cycle public — REJECTED | full cycle | log(N!) |
| **B** — Hierarchical flat_full | partition + N²/K sub-matrices + endpoints + per-segment costs | substantial |

### Three scope options considered (chose γ, expanded to three variants)

- **α** — recast thesis around wall-clock and memory only, implement Merkle variant only
- **β** — pivot to hierarchical flat_full only, accept privacy loss as feature
- **γ** — implement both Merkle and flat_full variants, frame as design-space exploration *(chosen)*

Variant A++ emerged later in the 2026-05-23 grand-product / Fiat-Shamir discussion and was added to the γ scope: now three variants (A, A++, B) on a clean privacy ↔ cost frontier. Each has a structural reason for being on the frontier (A is the simple baseline, A++ adds Fiat-Shamir-secured grand product for full privacy at small additional cost, B occupies the gate-saving / partition-disclosing end). Shared architecture across variants keeps total work roughly 1.5–2× one-variant cost.

---

## Supervisor Report: `supervisor_report_draft.md`

File at `/home/callexyz/Desktop/plsgod/supervisor_report_draft.md`. Complete plain-text structured report, **updated 2026-05-26 with variant-as-statement reframe**.

### 2026-05-26 updates (over the 2026-05-23 version)

- **§1** — full rewrite. New subsections 1.1–1.4: "Original framing and what we found instead" (variants prove different statements, not different costs), "The reframed thesis" (family of cryptographic statements; NP asymmetry doesn't transfer under decomposition), "Contributions in this reframed form" (4 contributions including the negative result with explanation), and "What this thesis does not claim" (pre-empt NP-asymmetry overclaiming).
- **§2.2** — expanded trust-in-commitment paragraph into a full subsection with the five trust mechanisms table (Authority signature, Trusted oracle, Cross-attestation, Public timestamping, Decommitment-on-dispute) and the matrix-private vs matrix-public regime distinction (privacy + integrity vs integrity-only).
- **§6** — Finding 8 sharpened to distinguish embarrassingly-parallel from algorithmic speedup. New Findings 10 (variants prove different statements) and 11 (each variant has a natural use-case class).
- **§7.3** — rewrote with the NP-asymmetry-under-decomposition framing. Added the new corollary "Algorithmic vs embarrassingly-parallel speedup" and "A predictive heuristic for proof-system design."
- **§7.7** — new subsection. Privacy analysis with worked N=8 example (Variant A leaks 10.3 bits, leaves 4 candidate cycles out of 5040). Variant-as-statement table. Use-case-to-variant mapping with concrete real-world settings.
- **§8** — added "Architectural commitments common to all three variants" subsection: independent sub-proofs + glue (model (i), not recursive); N ∈ {48, 96, 192, 480} for K-divisibility; K=2 hardcoded first then parameterised; glue shared between A and B but A++ has its own. Added worked example N=8, K=2 with all sub-circuit and glue public-input values, plus the verifier cross-checks.

### Full section list (current)

- §1 Overview and Research Question (1.1–1.4, rewritten)
- §2 Problem Formulation (2.1 what we prove, 2.2 public vs private + trust mechanisms, 2.3 threshold rationale)
- §3 Design Choices:
  - 3.1 Proof system (Noir + UltraHonk justification)
  - 3.2 Circuit structure (four groups + type rationale)
  - 3.3 Matrix representation (flat-full vs flat-Merkle)
  - 3.4 Permutation strategies (table of 4 variants)
  - 3.5 Hash function (Poseidon2)
  - 3.6 Design alternatives considered and rejected
- §4 Flat-Merkle Variant: Implementation in Detail (4.1–4.6 including walk-throughs at N=4 and N=8)
- §5 Flat Circuit Benchmarks (5.1–5.5)
- §6 Key Findings (now 11 findings)
- §7 Cross-Domain Perspective: A Structural Dualism (7.1–7.7, dualism + variant-as-statement)
- §8 Next Steps (three-variant programme + architectural commitments + worked example)

---

## `pipeline/analyze_complexity.py` — Current State

Updated this session to handle the Merkle variant:

- **`make_comparison_figure`**: uses `fit_nlogn` (dashed) for flat_merkle, `fit_quadratic` (solid) for flat_full; panel (d) restricted to flat_full only; inner `_plot_variant` helper
- **`make_crossover_figure`** (new): two-panel — benchmark range N≤500 panel (a) and extrapolation to N=1000 with crossover annotations panel (b)
- **`VARIANTS_ORDER`**: now includes `flat_merkle_presence`
- **`main()`**: accepts `--merkle-csv` arg, calls `print_nlogn_fit_table()`, calls `make_crossover_figure()` when Merkle data is present

Import verified: `conda run -n zk-tsp python3 -c "import analyze_complexity"` → OK

**Pending**: run `analyze_complexity.py` on `results/500.csv` to generate actual figures for the supervisor report.

---

## Thesis Defense Outline (session 2026-05-22)

A 30-minute defense structure was drafted:

- **Part 0** (2 min): Hook — one-sentence problem, one diagram, logistics privacy motivation
- **Part 1** (5 min): Background — ZKP in one paragraph, SNARKs and constraint model, TSP as ZKP target
- **Part 2** (4 min): Design space — four groups table, flat-full vs flat-Merkle decision, permutation strategy comparison table
- **Part 3** (10 min): Results — methodology, flat-full findings, flat-Merkle findings, crossover in detail, Poseidon2 gate cost finding, findings summary table
- **Part 4** (4 min): Next steps — hierarchical circuit, cross-domain perspective, open questions
- **Part 5** (2 min): Conclusion — one paragraph, no bullets

Key calibration: technical depth concentrated in Part 3 (exact numbers, crossover formula, Plookup explanation). Background is surface-level. Appendix holds circuit code, walk-through examples, full benchmark tables, merkle_builder implementation.

Backup slides prepared for: scalability to N=10,000 (hierarchical); soundness of Merkle (leaf index check); practical vs academic value; why Noir not Circom/RISC Zero; prover cost vs Dijkstra.

---

## File Inventory

```
circuits/flat_full_pairwise/src/main.nr         ✓
circuits/flat_full_sort/src/main.nr             ✓
circuits/flat_full_invperm/src/main.nr          ✓
circuits/flat_full_presence/src/main.nr         ✓
circuits/flat_merkle_presence/src/main.nr       ✓ (N=500, DEPTH=18 as of last compile)
pipeline/analyze_complexity.py                  ✓ updated (merkle support, crossover figure)
pipeline/merkle_builder/src/main.rs             ✓ (Rust Merkle tree builder)
results/500.csv                                 ✓ (pairwise, sort, merkle; N=5..500; 5 runs each)
tests/hash_compat/                              ✓ (Rust+Noir cross-validation, full pass)
supervisor_report_draft.md                      ✓ (1295 lines; updated 2026-05-23)
HOWTO.md                                        ✓
DESIGN.md                                       ✓
.gitignore                                      ✓ (2026-05-23)
.git/                                           ✓ (2026-05-23, main branch, 1 initial commit, 65 files)
```

---

## DESIGN.md Progress State

```
[x] Instance generation: pipeline/instance_gen.py
[x] Visualization: pipeline/visualize.py
[x] Solver (nearest-neighbour + 2-opt): pipeline/solver.py
[x] flat_full_pairwise
[x] flat_full_sort
[x] flat_full_invperm
[x] flat_full_presence
[x] flat_merkle_presence
[x] Benchmarking harness: pipeline/run.py
[x] Hash compatibility test: tests/hash_compat/
[x] Git repo initialised (2026-05-23, initial commit b4c2c29)
[x] Thesis reframing + supervisor report update (2026-05-23)
[ ] full permutation variant benchmarks (invperm, presence to N=500)
[ ] analyze_complexity.py figures generated from results/500.csv
[ ] Discuss reframing with supervisor
[ ] Hierarchical circuit — Variant A (Merkle, sorted nodes public — baseline)
[ ] Hierarchical circuit — Variant A++ (Merkle, grand product + in-circuit Fiat-Shamir)
[ ] Hierarchical circuit — Variant B (flat_full, gate-saving, partition-disclosing)
[ ] Frontier figure: (gates, parallel wall-clock, per-prover memory, privacy) across all three variants
```

---

## Next Steps (priority order)

### Immediate / housekeeping

1. **Generate figures**: run `analyze_complexity.py` on `results/500.csv` with `--merkle-csv results/500.csv` flag.
2. **Benchmark flat_full_invperm and flat_full_presence to N=500** to fill the permutation overhead comparison.
3. **Discuss reframing with supervisor**. Possibly send updated `supervisor_report_draft.md` along with a short note (a template email draft was sketched this session — see chat history for the structure: lead with finding, propose reframe, scope the new plan, ask for sign-off).

### Hierarchical implementation — Variant A (Merkle, sorted nodes public — baseline)

4. **Sub-circuit**: `circuits/hierarchical_segment/src/main.nr` for K=2, M=N/K. Five constraint groups (see "Hierarchical Design" section above). Globals: `N`, `M`, `DEPTH`.
5. **Glue circuit**: `circuits/hierarchical_glue/src/main.nr` with sort-based partition check + K boundary Merkle proofs. Globals: `N`, `K`, `M=N/K`, `DEPTH`.
6. **Pipeline**: `pipeline/hierarchical_split.py` (split solver cycle into K segments), extend `pipeline/format_inputs.py` for K sub-circuit Prover.tomls + 1 glue Prover.toml. New `pipeline/run_hier.py` orchestrator.
7. **Correctness tests**: at small N=8, K=2. Include a negative test for the glue's partition check (reject when two segments overlap).
8. **Gate-count sanity check**: `nargo info` on both circuits at small N; compare against analytical predictions `M × DEPTH × 87` (sub-circuit) and `K × DEPTH × 87 + O(N)` (glue).
9. **Generalise K** to a compile-time parameter (benchmark K=2, 4, 8).

### Hierarchical implementation — Variant A++ (Merkle, grand product + in-circuit Fiat-Shamir)

10. **Sub-circuit**: `circuits/hierarchical_segment_fs/src/main.nr` — extends Variant A's sub-circuit with hash-chain constraints (M Poseidon2 calls binding segment to chain values `h_in`/`h_out`), challenge-derivation assertion (`X == Poseidon2(c)`), and grand-product computation (`P_i == ∏(X + cycle_segment[j])`). Replaces `sorted_nodes[M]` public output with `(P_i, h_in, h_out)`.
11. **Glue circuit**: `circuits/hierarchical_glue_fs/src/main.nr` — chain stitching (`h_ins[i+1] == h_outs[i]`, `h_ins[0] == 0`, `h_outs[K-1] == c`) + grand-product check (`∏ P_is == expected_product` with verifier supplying `expected_product = ∏(X+j)`) + K boundary Merkle proofs. Replaces O(N) sort with O(K) multiplications.
12. **Pipeline**: extend `pipeline/hierarchical_split.py` to precompute the hash chain values `h_0..h_N`; extend formatter to emit `(c, X, P_i, h_in, h_out)` per sub-circuit and the expected_product in the glue Prover.toml.
13. **Correctness tests**: similar to Variant A, plus negative tests for (a) wrong `X` (sub-circuit should reject if `X != Poseidon2(c)`), (b) forged cycle commitment (glue should reject if chain doesn't terminate at `c`), (c) two segments with identical multisets (grand product would match but partition is wrong — should be caught by chain check rejecting any cycle that doesn't hash to `c`).
14. **Gate-count sanity check**: compare A++ sub-circuit gates vs A (predicted overhead ~5.5% at N=500). Glue partition cost should drop from ~6N to ~K+3K Poseidon2 + K multiplications.

### Hierarchical implementation — Variant B (flat_full, partition-disclosing)

15. **Sub-circuit**: `circuits/hierarchical_segment_full/src/main.nr` — takes M×M sub-matrix as public input. M-1 edge ROM lookups instead of M-1 Merkle proofs.
16. **Glue**: reuses Variant A glue logic for partition + boundary Merkle proofs (the cost matrix is still committed for the boundary edges).
17. **Pipeline + tests**: parallel to Variants A / A++.

### Benchmarks and analysis

18. Run hierarchical benchmarks at N ∈ {50, 100, 200, 500}, K ∈ {2, 4, 8} across all three variants.
19. Generate frontier figure: (total gates, parallel wall-clock, per-prover memory, privacy bits) for all variants. Replaces the originally-planned single crossover figure.
20. Integrate cross-domain comparison with heuristic optimisation results (clustered TSP solver project).

### Future / out of scope for this thesis

- **Folding-scheme variant** (Nova/ProtoStar/SuperNova) — would test whether the dualism is intrinsic to TSP or a property of UltraHonk. Mentioned in supervisor report §7.5 and §8.
- **Hash commitment for partition** (Option B from this session's Q2 discussion) — full privacy preservation in hierarchical Merkle by committing to sorted node sets instead of revealing them.
- **Optional type optimization**: `edge_costs: [u64; N]` → `[Field; N]` in flat_merkle_presence (~1% gate savings, safe because Merkle constrains range). Not urgent.

---

## Important Gotchas

- Noir rejects non-ASCII in comments (`≈`, `²`) — use `~` and `^2`
- `poseidon::` not `dep::poseidon::` (deprecated in nargo 1.0.0-beta.20)
- `(i+1) % N` in Noir GROUP 3 loop is comptime-safe (static array access, no runtime gate)
- `seen: [bool; N] = [false; N]` is part of circuit structure — prover cannot pre-set it
- The N² coefficient in gate counts (7.25) comes from GROUP 3 ROM lookups, not the permutation check
- Poseidon2 costs ~87 gates in UltraHonk (not ~264 from arithmetic-gate literature) due to Plookup
- ACIR opcode crossover (N≈30) is misleading; use gate-count crossover (N≈175)
- Verification time for flat_full grows O(N²) despite "O(1) SNARK" claim — verifier must process N² public inputs
- `circuit_size` in nargo output is UltraHonk gate count; `acir_opcodes` is pre-backend IR — always use `circuit_size` for cross-variant comparison
- Dynamic array access with Field index may not work in Noir; cycle indices must stay `u32`
- **Hierarchical Merkle gives no total-gate-count benefit over flat Merkle** — per-segment savings are exactly cancelled by the O(N) partition check + K boundary Merkle proofs in the glue. The hierarchical wins are parallel wall-clock and per-process memory.
- **Hierarchical flat_full beats flat_merkle in gates at K ≥ 3 for N=500** but discloses the partition publicly. Genuine privacy/cost tradeoff, neither variant Pareto-dominates.
- **The dualism**: hierarchical decomposition *adds* a constraint in optimisation (shrinks search space → cheaper) and *weakens* a constraint in ZK (forces glue restoration → same or worse). Same operation, opposite sign in constraint space. Root cause: NP asymmetry between finding and checking.
- **Sub-circuit publishes `sorted_nodes`, not the ordered `cycle_segment`** — preserves in-segment visit order privacy at zero extra cost (the sort-based perm check produces a sorted array as byproduct).
- **TSP is a worst-case problem class for hierarchical ZK** — the global constraint "visit every node exactly once" intrinsically does not factor locally. Circuit-SAT and other locally-factoring problems are where recursive/folding proof systems shine.
- **Variant A++ uses in-circuit Fiat-Shamir** via a hash chain over the cycle (`c = h_N` where `h_{j+1} = Poseidon2(h_j, cycle[j])`, `X = Poseidon2(c)`). The chain is enforced jointly: sub-circuits assert `h_out_i = chain(h_in_i, segment)`, glue asserts `h_outs[i] == h_ins[i+1]` and `h_outs[K-1] == c`. This binds `X` to the cycle unforgeably without requiring multi-round prover-verifier interaction.
- **Variant A++ has a sequential prelude** for hash-chain precomputation (N native Poseidon2 calls), but this is ~100µs at N=500 — negligible vs proving time. K-fold parallelism benefit is preserved after the prelude.
- **Naive fixed-X grand product is unsound** — if the prover knows `X` before committing to segments, they can search for fake partitions whose product matches at that specific `X`. Soundness requires `X` derived AFTER prover commits, hence the in-circuit Fiat-Shamir construction in A++.
- **Variants prove different statements, not different costs** (2026-05-26) — flat_merkle proves "∃ cycle ≤ T"; A proves "∃ partition-respecting cycle ≤ T"; A++ adds "with K-segment decomposition + hidden segments"; B adds "with disclosed sub-matrices". They cannot be totally ordered on cost because they are not the same proposition. The "crossover" framing was wrong because it implicitly assumed they were.
- **NP asymmetry is not violated, but its transfer under decomposition fails** (2026-05-26) — classical hierarchical decomposition exploits NP asymmetry by trading verification overhead for search reduction. In ZK there is no search to reduce, so the verification overhead is paid without compensating saving. The asymmetry persists; the strategy that exploits it does not.
- **Algorithmic vs embarrassingly-parallel speedup** (2026-05-26) — classical hierarchical TSP gives algorithmic speedup (total work decreases super-polynomially). Hierarchical ZK gives only embarrassingly-parallel speedup (total work stays the same, but distributes across K machines). Conflating these is the source of much practitioner confusion about ZK scaling.
- **Verifier-side cross-checks bind the K+1 independent proofs** (2026-05-26) — `bb verify` only confirms one proof is internally consistent with its declared public inputs. Without verifier-side equality checks across proofs (same root, glue's all_sorted_nodes = concat of sub-proofs' sorted_nodes, starts/ends/partial_costs agree), a malicious prover could produce K+1 individually-valid proofs about K+1 different universes. The cross-checks are O(N) trivial equality at the verifier and are non-optional.
- **Commitment requires an external trust anchor** (2026-05-26) — a Merkle commitment with no real-world binding is useless: the prover can commit to whatever fictitious matrix makes their proof trivial. Standard anchors: authority signature, trusted oracle, cross-attestation, public timestamping, decommitment-on-dispute. The cryptographic commitment does one job (binding the prover across proofs); the trust anchor does a separate job (binding the matrix to reality).
- **Matrix-private vs matrix-public regimes are different problems** (2026-05-26) — matrix-private: Merkle root provides privacy AND integrity. Matrix-public: Merkle root provides integrity only (still useful — prevents the prover from using a different matrix). Variant A is appropriate for matrix-private; A++ is appropriate when matrix is public AND partition is sensitive; B is appropriate when matrix is public AND partition non-sensitive.
