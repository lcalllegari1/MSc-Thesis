# TSP ZKP Project — Session Summary
## Last updated: 2026-05-27

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

### Finding 12 (added 2026-05-27): `peak_mb` is per-prover maximum, not total concurrent RAM

`aggregate_hier.py` computes `peak_mb = max(...)` over K+1 workers — the single heaviest prover process peak, not the sum. At N=480:

| K | Sub peak | Glue peak | Reported peak | Bottleneck |
|---|---|---|---|---|
| 2 | ~551 MB | ~159 MB | ~551 MB | sub-circuit |
| 4 | ~285 MB | ~159 MB | ~285 MB | sub-circuit |
| 8 | ~152 MB | ~159 MB | ~159 MB | **glue** |

At K≥8 (N=480), the glue becomes the heaviest single worker because its G2 partition check sorts `all_sorted_nodes[N]` — N elements regardless of K. This is an **O(N) memory floor** that prevents further reduction even as K grows. Variant A++ replaces O(N) sort with O(K) grand product; its glue memory floor should be substantially lower.

Correct thesis claim: "sub-circuit per-prover peak scales as flat_merkle/K; glue is an O(N) memory floor; at K≥8 (N=480) the glue becomes the bottleneck prover, so reported peak stops decreasing with K."

### Finding 13 (added 2026-05-27): Total single-machine concurrent RAM exceeds flat for all K

Total RAM across all K+1 concurrent workers ≈ K×sub_peak + glue_peak. At N=480:
- K=2: ~1262 MB vs flat_merkle ~1078 MB (+17%)
- K=4: ~1299 MB vs flat_merkle (+20%)
- K=8: ~1375 MB vs flat_merkle (+28%)

Total concurrent RAM grows with K on a single machine. The memory benefit of hierarchical requires distributed infrastructure (each prover on separate hardware). Same structural issue as prove time. Thesis must separate two mental models:
1. **Per-prover / distributed**: sub-circuit peak ≈ flat/K; Variant A glue O(N) floor ≈ 159 MB constant
2. **Single-machine total**: always exceeds flat; not the valid comparison mode for the memory benefit claim

### Finding 14 (added 2026-05-27): Single-machine `prove_s` is contended; K× speedup requires isolation to confirm

`bb prove` is multi-threaded. K+1 concurrent prover processes share available CPU threads, each obtaining approximately 1/(K+1) of capacity. This contention overhead grows superlinearly with K. Observed benchmark: hierarchical prove_s > flat_merkle for all K at N=480, which is expected and does not falsify the K× speedup claim.

The K× speedup claim is theoretical — estimated from circuit_size ratios (sub_size ≈ flat/K → isolated prove_s ≈ flat/K) — and not directly measured. An isolation benchmark (run one sub-circuit through full prove pipeline without parallel siblings) is needed to empirically validate it. This is the immediate next step after the full benchmark sweep.

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
circuits/hierarchical_segment/src/main.nr       ✓ (Variant A sub, 2026-05-27)
circuits/hierarchical_glue/src/main.nr          ✓ (Variant A glue, 2026-05-27)
pipeline/analyze_complexity.py                  ✓ updated (merkle support, crossover figure)
pipeline/merkle_builder/src/main.rs             ✓ extended with --hierarchical K mode (2026-05-27)
pipeline/verify_hier.py                         ✓ Variant A K+1 bb verify + cross-checks (2026-05-27)
pipeline/run_hier.py                            ✓ Variant A benchmark harness w/ K shadow dirs (2026-05-27)
results/500.csv                                 ✓ (pairwise, sort, merkle; N=5..500; 5 runs each)
results/hier_a.csv                              ✗ (run_hier.py ready; sweep is user-triggered)
tests/hash_compat/                              ✓ (Rust+Noir cross-validation, full pass)
tests/correctness/test_hierarchical_a.py        ✓ 6 tests pass (2026-05-27)
supervisor_report_draft.md                      ✓ (1295 lines; updated 2026-05-23)
VARIANT_A_IMPLEMENTATION.md                     ✓ (followed during 2026-05-27 implementation)
HOWTO.md                                        ✓ Variant A workflow added (2026-05-27)
DESIGN.md                                       ✓ Variant A marked done (2026-05-27)
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
[x] Hierarchical circuit — Variant A (Merkle, sorted nodes public — baseline) (2026-05-27)
    [x] hierarchical_segment + hierarchical_glue circuits
    [x] merkle_builder --hierarchical K mode
    [x] verify_hier.py (K+1 bb verify + 4 cross-checks)
    [x] run_hier.py (K-shadow parallel benchmark harness)
    [x] test_hierarchical_a.py (6 tests: valid + 4 negatives + N=48 K=4 sanity)
[ ] full permutation variant benchmarks (invperm, presence to N=500)
[ ] analyze_complexity.py figures generated from results/500.csv
[ ] Discuss reframing with supervisor
[ ] Variant A full benchmark sweep into results/hier_a.csv (harness ready, user-triggered)
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
4. **Isolation benchmark** (1 day): run a single sub-circuit through the full prove pipeline (`nargo execute` + `bb prove` + `bb verify`) without parallel siblings. Measure prove_s and peak_mb for one sub at N=480 across K ∈ {2,4,8}. This empirically validates the theoretical K× speedup estimated from circuit_size ratios and is required before the thesis can claim the speedup is real rather than inferred. Compare against flat_merkle prove_s at N=480.

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
- **UltraHonk commits public inputs in the Fiat-Shamir transcript** — `bb verify` rejects any tampering of the `public_inputs` file post-hoc. The Variant A cross-check defends against a *different* attack: two independently-valid proof sets (sharing the same Merkle root) mixed together, e.g. sub-proofs from cycle A + glue proof from cycle B. Each `bb verify` accepts; only the verifier's `glue.starts[i] == sub_i.start_node` check catches the inconsistency. This sharpens the plan's original test-2 scenario (2026-05-27).
- **Nargo walks up looking for the outermost `Nargo.toml`** when resolving project root — shadow dirs placed *inside* the project tree (e.g. `circuits/hierarchical_segment/.runs/sub_i/`) get treated as a sub-project of the parent and `nargo execute` writes to the parent's `target/`, causing K parallel workers to race. Solution: host shadows outside the tree (e.g. `/tmp/hier_a_shadows/`) (2026-05-27).
- **Compiled `target/<name>.json` embeds absolute paths** to source files in its `file_map` field — copying a `.json` to a new dir and running `nargo execute` makes nargo follow the embedded paths back to the original project. Each shadow must `nargo compile` from its own copied `src/` (~0.2s amortized per cell). VKs are bytecode-derived and survive cross-shadow reuse (2026-05-27).
- **Variant A sub-circuit doesn't need a strict-ascending check** on `sorted_nodes` — per-segment distinctness is enforced *transitively* by the glue's `sort(all_sorted_nodes) == [0..N-1]`. A duplicate inside one segment surfaces as a duplicate in the concatenation and is caught there. Saves M-1 comparison gates per sub-proof at zero soundness cost (`HIERARCHICAL_EXPLAINED.md` §8.2.G2).
- **Variant A++ uses in-circuit Fiat-Shamir** via a hash chain over the cycle (`c = h_N` where `h_{j+1} = Poseidon2(h_j, cycle[j])`, `X = Poseidon2(c)`). The chain is enforced jointly: sub-circuits assert `h_out_i = chain(h_in_i, segment)`, glue asserts `h_outs[i] == h_ins[i+1]` and `h_outs[K-1] == c`. This binds `X` to the cycle unforgeably without requiring multi-round prover-verifier interaction.
- **Variant A++ has a sequential prelude** for hash-chain precomputation (N native Poseidon2 calls), but this is ~100µs at N=500 — negligible vs proving time. K-fold parallelism benefit is preserved after the prelude.
- **Naive fixed-X grand product is unsound** — if the prover knows `X` before committing to segments, they can search for fake partitions whose product matches at that specific `X`. Soundness requires `X` derived AFTER prover commits, hence the in-circuit Fiat-Shamir construction in A++.
- **Variants prove different statements, not different costs** (2026-05-26) — flat_merkle proves "∃ cycle ≤ T"; A proves "∃ partition-respecting cycle ≤ T"; A++ adds "with K-segment decomposition + hidden segments"; B adds "with disclosed sub-matrices". They cannot be totally ordered on cost because they are not the same proposition. The "crossover" framing was wrong because it implicitly assumed they were.
- **NP asymmetry is not violated, but its transfer under decomposition fails** (2026-05-26) — classical hierarchical decomposition exploits NP asymmetry by trading verification overhead for search reduction. In ZK there is no search to reduce, so the verification overhead is paid without compensating saving. The asymmetry persists; the strategy that exploits it does not.
- **Algorithmic vs embarrassingly-parallel speedup** (2026-05-26) — classical hierarchical TSP gives algorithmic speedup (total work decreases super-polynomially). Hierarchical ZK gives only embarrassingly-parallel speedup (total work stays the same, but distributes across K machines). Conflating these is the source of much practitioner confusion about ZK scaling.
- **Verifier-side cross-checks bind the K+1 independent proofs** (2026-05-26) — `bb verify` only confirms one proof is internally consistent with its declared public inputs. Without verifier-side equality checks across proofs (same root, glue's all_sorted_nodes = concat of sub-proofs' sorted_nodes, starts/ends/partial_costs agree), a malicious prover could produce K+1 individually-valid proofs about K+1 different universes. The cross-checks are O(N) trivial equality at the verifier and are non-optional.
- **Commitment requires an external trust anchor** (2026-05-26) — a Merkle commitment with no real-world binding is useless: the prover can commit to whatever fictitious matrix makes their proof trivial. Standard anchors: authority signature, trusted oracle, cross-attestation, public timestamping, decommitment-on-dispute. The cryptographic commitment does one job (binding the prover across proofs); the trust anchor does a separate job (binding the matrix to reality).
- **Matrix-private vs matrix-public regimes are different problems** (2026-05-26) — matrix-private: Merkle root provides privacy AND integrity. Matrix-public: Merkle root provides integrity only (still useful — prevents the prover from using a different matrix). Variant A is appropriate for matrix-private; A++ is appropriate when matrix is public AND partition is sensitive; B is appropriate when matrix is public AND partition non-sensitive.
- **`peak_mb` is per-prover max, not total concurrent RAM** (2026-05-27) — `aggregate_hier.py` line: `peak_mb = max(float(r["peak_mb"]) for r in all_rows)`. Total single-machine RAM = K×sub_peak + glue_peak, always exceeds flat_merkle for all K. The memory benefit (sub-circuit peak ≈ flat/K) is only realised in a distributed model where each prover runs on separate hardware. Thesis must state this explicitly.
- **Glue has an O(N) memory floor regardless of K** (2026-05-27) — the glue's G2 sort over `all_sorted_nodes[N]` loads N elements whether K=2 or K=8. At N=480, K=8: glue peak ≈ 159 MB, sub peak ≈ 152 MB — glue becomes the bottleneck and the reported `peak_mb` stops decreasing. Variant A++ fixes this by replacing O(N) sort with O(K) grand product; measure its glue peak explicitly.
- **prove_s benchmarks reflect single-machine CPU contention, not isolated prover performance** (2026-05-27) — K+1 concurrent `bb prove` processes each get ~1/(K+1) of available threads. Observed prove_s > flat for all K is expected and consistent with the K× speedup being real in a distributed setting. Run isolation benchmark (single sub-circuit, no siblings) to empirically validate the theoretical K× estimate from circuit_size ratios.

---

## Session Findings — 2026-05-27

*Distilled findings from the 2026-05-27 session (benchmark interpretation, thesis framing, related work, future work, writing guidance). Raw transcript not retained.*

### Benchmark interpretation

The full Variant A benchmark sweep (`results/hier_a.csv`) was completed and analyzed. The key interpretive finding is that the benchmarks measure single-machine contended performance, whereas the thesis claims are about distributed per-prover performance. Both are valid metrics but must be clearly labelled.

**Prove time:** `prove_s` in the CSV is single-machine contended wall-clock (K+1 processes sharing all CPU threads). It shows hierarchical worse than flat_merkle for all K at N=480. The theoretical K× speedup per sub-prover (estimated from circuit_size ratios: sub/flat ≈ 1/K) is not directly measured. An isolation benchmark is pending.

**Memory:** `peak_mb` = max single worker (see Finding 12). The glue's O(N) memory floor becomes the reported peak at K≥8, N=480 (glue 159 MB > sub 152 MB). Total single-machine RAM exceeds flat for all K (see Finding 13).

**Table of three mental models (all metrics):**

| Model | prove_s | peak_mb |
|---|---|---|
| Single-machine contended (CSV) | K+1 processes sharing 1 machine; worse than flat | max(K subs, glue); glue floor O(N) |
| Per-prover isolated (theoretical) | ≈ flat/K; not yet measured | ≈ flat/K per sub; glue floor O(N) constant |
| Total system (sum) | ≈ flat (same total work; embarrassingly parallel) | K×sub + glue; exceeds flat |

### Thesis framing

**Thesis sufficiency:** The work is defensible as MSc-level because:
- 7 circuits implemented from scratch in an unfamiliar domain (Noir, Barretenberg, UltraHonk)
- Honest negative result with a structural explanation (dualism between optimisation and ZK constraint space)
- The dualism principle is known in the ZK literature (it motivates Nova/folding), but the TSP-specific empirical quantification and the frontier framing — showing each variant as the natural proof design for a distinct statement — are original contributions
- Must cite Nova's motivation section (Kothapalli–Setty–Tzialla 2021), which describes the same principle abstractly; the thesis provides the concrete instantiation

**Refined research question:**
> This thesis investigates the design space of zero-knowledge proofs for knowledge of a bounded-cost Hamiltonian cycle, characterising how hierarchical proof constructions trade privacy disclosure (partition, endpoints, per-segment costs) against proving efficiency (circuit size, per-prover time, per-prover memory), and identifies the structural reason no single design universally dominates — a dualism between optimisation and ZK constraint space arising from the non-local nature of the Hamiltonian-cycle constraint.

### Related work structure

Three-ring model (each ring is a class of citable related work):
1. **Same problem, different approach** — prior ZKP constructions for graph problems (graph colouring, Hamiltonian cycle existence). Used as baselines and as motivation for why TSP is harder (the cost bound makes it a search problem, not just an existential statement).
2. **Same approach, different problem** — hierarchical proof systems: Nova (Kothapalli 2021), SuperNova, ProtoStar, and folding-based decomposition. These motivate the frontier framing — they are the correct tool for locally-factoring problems; TSP is the negative-example complement.
3. **Pieces of our approach** — Poseidon2 (Grassi et al.), UltraHonk (Aztec), Merkle commitments in ZK, grand-product multiset arguments (Bayer–Groth, Gabizon–Williamson), Fiat-Shamir in IVC. Each piece has a canonical citation; the thesis shows how to assemble them for this specific application.

### Future work framing principles

Future work should sound structurally motivated, not lazy:
- **Framing that works:** "X requires Y infrastructure; establishing Y is a thesis-sized project in itself and shares dependencies with Z field. The design space explored here is the natural precursor."
- **Framing that sounds lazy:** "We could also benchmark X" or "Future work includes implementing Y."
- **The three strongest future work items** (in descending order of payoff vs effort):
  1. Folding-scheme variant (Nova/ProtoStar): replaces K+1 independent proofs with one accumulated proof; directly tests whether dualism is intrinsic to TSP or an artefact of UltraHonk's proof structure. High payoff, requires new arithmetisation.
  2. Isolation benchmark (next week): run one sub-circuit without parallel siblings to empirically validate the K× speedup claim. Low effort, directly strengthens a central claim.
  3. Variant A++ implementation: completes the privacy/cost frontier; tests whether grand-product + Fiat-Shamir eliminates the O(N) glue memory floor as predicted.

### Writing guidance (captured 2026-05-27)

- **Argument architecture:** structure each chapter as: claim → model → derivation → measurement → agreement/discrepancy. Never state a number without the derivation that predicts it.
- **Derive, don't just cite:** for gate count crossovers, the Poseidon2 cost correction (264→87), the memory floor, write out the arithmetic explicitly. These short derivations are the thesis's original intellectual content.
- **First principles on the dualism:** don't say "hierarchical ZK is harder." Derive it: decomposition weakens the global distinctness constraint, which must be restored by O(N) glue work; this restoration cost exactly cancels any per-segment saving; QED no total-gate benefit.
- **Precision about proof systems:** UltraHonk is a *proof of knowledge* (extracts witness); it is a *SNARK argument* (computational soundness, not information-theoretic). Say "argument" not "proof" when the distinction matters.
- **What to leave as a black box:** the UltraHonk internals (SRS, commitment scheme, polynomial IOP) can be cited-and-used without full derivation. The ZK-relevant circuit-level properties (gate count, proof size, verification time) are what the thesis measures; the internal mechanism is standard and citable.
- **Negative results need the same rigour as positive ones:** "we measured X and found Y > flat" is not a negative result; "we measured X, predicted Y from circuit_size ratios, found Y_measured >> Y_predicted due to mechanism Z" is.

---

## Session Transcript — 2026-05-26: Hierarchical Design Discussion

*Raw transcript of the session that produced the variant-as-statement reframe, the use-case mapping, and the NP-asymmetry-under-decomposition argument. The settled outputs of this session are in `HIERARCHICAL_EXPLAINED.md`, `VARIANT_A_IMPLEMENTATION.md`, and `supervisor_report_draft.md §7–§8`. This transcript is kept as a thought-process record.*

╭─── Claude Code v2.1.150 ─────────────────────────────────────────────────────╮
│                                                    │ Tips for getting        │
│               Welcome back Leonardo!               │ started                 │
│                                                    │ Run /init to create a … │
│                       ▐▛███▜▌                      │ ─────────────────────── │
│                      ▝▜█████▛▘                     │ What's new              │
│                        ▘▘ ▝▝                       │ Internal infrastructur… │
│   Opus 4.7 · Claude Pro · callexyz1@gmail.com's    │ `/usage` now shows a p… │
│   Organization                                     │ `/diff` detail view ca… │
│                  ~/Desktop/plsgod                  │ /release-notes for more │
╰──────────────────────────────────────────────────────────────────────────────╯

❯ /model claude-opus-4-7                                                        
  ⎿  Set model to Opus 4.7 for this session

❯ Read @SESSION_SUMMARY.md and the current directory to familiarize with the    
  project, the codebase and the style. Then let's start discussing the details  
  of the next steps and of the implementation of the hierarchical approach in   
  the different variants we're considering.                                     
  ⎿  Read SESSION_SUMMARY.md (558 lines)

  Read 7 files, listed 3 directories, recalled 4 memories (ctrl+o to expand)

● I've got the picture. Here's where I think the discussion needs to land before
   any code is written — the SESSION_SUMMARY pins down the five constraint
  groups and the public/private interfaces, but several architectural decisions
  are still implicit. Let me surface them in priority order.

  Where I think we are

  Settled: glue is a real Noir circuit, sorted_nodes public for A, boundary
  edges in glue, K=2 first then parameterise, sub-circuit/glue interfaces
  sketched. Variant order is A → A++ → B.

  What I want to discuss before writing the first main.nr:

  1. Sub-proof / glue composition — the biggest unstated decision

  The SESSION_SUMMARY says "real glue circuit, not Python verification," which I
   read as ruling out a Python-side aggregator. But there are still two very
  different architectures it could mean:

  - (i) Independent-proofs model. K sub-proofs + 1 glue proof are produced as a
  tuple. They share public-input fields — e.g. sub_proof_i.sorted_nodes is the
  same vector that appears as glue.all_sorted_nodes[i*M..(i+1)*M]. The verifier
  runs bb verify K+1 times and checks the public-input fields agree. No
  recursion.
  - (ii) Recursive model. Glue circuit invokes UltraHonk's recursive verifier on
   each of the K sub-proofs as a circuit gadget. Output is one final proof.

  (i) is dramatically simpler to implement in Noir and gives K-fold parallelism
  naturally. (ii) is more elegant for the verifier story (one proof) but adds
  tens of thousands of gates to the glue and pulls in UltraHonk recursion
  plumbing we haven't touched yet. The supervisor report's parallel-wall-clock
  story works fine under (i); (ii) is more of a "folding-schemes adjacent"
  story.

  My recommendation: (i), and we explicitly call out in §8 that "true recursion"
   is a future extension. This keeps us out of the rabbit hole feedback-focus
  warns about, and keeps the glue circuit small enough that its gate count is
  dominated by the K boundary Merkle proofs, which is what the frontier figure
  actually wants to show.

  2. K = 2 is a degenerate first case

  The summary says K=2 first. But at K=2 the parallelism story is unconvincing
  (2× speedup), the per-prover memory story is unconvincing (50% reduction), and
   the glue has only 2 boundary edges — barely exercising the boundary-Merkle
  code path. K=2 is fine for correctness but for the benchmark figure we'll want
   K ∈ {2, 4, 8}.

  I'd suggest treating K=2 as a one-shot debugging instance and going to a
  compile-time-parameterised K immediately after the first end-to-end run works
  at K=2, N=8. Otherwise we write the parameterisation twice.

  3. Redundancy in A's public inputs

  Cross-checking the interfaces: sub-circuit i publishes sorted_nodes[M], and
  glue publishes all_sorted_nodes[N] which is just the concatenation. That's K·M
   = N elements appearing twice in the public-input pool. Under model (i) above,
   the verifier can construct all_sorted_nodes by concatenation — no need for
  the glue to take it as a public input. Saves N×7.25 gates from the glue.

  This is small but worth getting right early because A++ has the same shape
  with (P_i, h_in, h_out) per sub-circuit, and the analogous saving is only ~3K
  Field elements, much smaller. The pattern matters more than the count.

  4. What does the supervisor narrative need from the splitter?

  The solver-side hierarchical_split.py could either:
  - (a) Any partition — e.g. cycle[0..M], cycle[M..2M], .... Trivial. Proof
  correctness doesn't care.
  - (b) Geographically clustered partition — run a clustering pre-pass, route
  within clusters, stitch. This is what gives the cross-domain "decomposition
  shrinks search space" story teeth, but it's solver work, not ZK work.

  The ZK proof works under either. But §7.6 of the supervisor report
  ("combined-pipeline synthesis") is much more interesting if we have (b),
  because then the hierarchical proof matches a hierarchical solver and we can
  talk about end-to-end pipelines. Question for you: do you want to do (b) in
  this thesis, or defer it as "future work" and stick with (a)?

  5. Negative tests — the partition-check soundness one

  For A, the negative test that matters most is: two segments with overlapping
  node sets. The glue's sort-based partition check should reject. Easy to
  construct: take a valid cycle, swap one node in segment 0 with a node already
  in segment 1, regenerate proofs. The witnesses will be locally valid (each
  segment is internally a Hamiltonian path) but the global multiset will have a
  duplicate and a missing node.

  For A++ the same construction is more interesting: the grand product would
  also reject (because Schwartz-Zippel at random X), so we get a soundness
  sanity check on the Fiat-Shamir machinery. Worth including from day one.

  ---
  Where do you want to start the discussion? My instinct is to lock in (1) first
   since it determines whether we're writing a small glue circuit or a
  recursive-verifier-heavy one, and then talk through whether to defer (4).

✻ Cooked for 1m 40s

※ recap: Goal: design the hierarchical TSP ZKP variants (A, A++, B) before coding. We surfaced five open design questions; the most consequential is whether the glue circuit recursively verifies sub-proofs or just shares public inputs with K independent proofs. Next: you pick that composition model. (disable recaps in /config)

❯ Addressing 4, I already have a b) solver, that uses clusters for local        
  optimization and then performs optimized stiching of cluster tours into a     
  global tour, so we don't have to worry about that, I only need to integrate   
  it into the codebase, and I will do that last. For 2., yes let's consider     
  your approach of varying K. For 1. Let's start with the simple (i), then      
  we'll see the result and assess whether to provide (ii) as an additional      
  benchmark, to show the cost of recursion. The problem with 3 is that it has a 
   wrong assumption. The nodes are not necessarily a ordered partition, which   
  means simply concatenating them will not give a global ordering, but simply a 
   concatenation of locally ordered segments. How do we deal with that? And are 
   there other things to consider or clarify?                                   

● You're right — concatenating per-segment sorted arrays gives [3,7,12,18 | 
  1,5,9,14,20 | ...], which is a multiset expressed as a sequence, not a
  sortable list, and the glue would have to sort it in-circuit anyway. Withdraw
  point 3.

  How to deal with the partition-check for A

  A few options, ordered from "most boring" to "reinventing A++":

  (i) Just take all_sorted_nodes[N] as a glue public input. Verifier-side, check
   glue.all_sorted_nodes[i*M..(i+1)*M] == sub_proof_i.sorted_nodes for each i.
  Glue then runs sort_via over all N values and asserts == [0..N-1]. The N
  public-input cost (≈ 7.25 N gates from u32 encoding) is paid by the glue.

  (ii) Have each sub-circuit publish hash(sorted_nodes) instead of the array; 
  pass arrays as private witness to the glue. Saves N×7.25 public-input gates,
  costs ~M·K Poseidon2 calls = N×87 gates in the glue to re-derive the
  commitments, plus K verifier-side checks. Strictly worse on gates.

  (iii) Multiset commitment via grand product with a fixed challenge. This is
  A++ minus the Fiat-Shamir part. Unsound on its own.

  My take: (i) is correct for A. The whole point of having A separate from A++
  is that A pays the O(N) cost honestly and A++ shows you can compress it down
  to O(K) Field elements with the Fiat-Shamir machinery. If we optimise A, we
  collapse the privacy/cost frontier we're trying to map. Keep A boring on
  purpose.

  One small refinement: the glue's all_sorted_nodes can be marked private if we
  still want the verifier to learn the partition. Currently the partition is
  leaked via the per-sub-proof sorted_nodes publications anyway, so making it
  public in the glue too is just convenience — no extra leakage. Default to
  public so the verifier doesn't need a separate concatenation step.

  Other things worth pinning down before coding

  A. N % K == 0 discipline. For benchmarks at N ∈ {50, 100, 200, 500} and K ∈
  {2, 4, 8}, 50 isn't divisible by 8, 100 isn't either, etc. Two ways out: (a)
  pick N divisible by lcm(2,4,8)=8 — e.g. {48, 96, 192, 480}; (b) allow
  non-uniform segments (last segment slightly larger). Option (a) is cleaner for
   benchmark presentation but breaks comparability with the existing
  flat-circuit results/500.csv row at N=500. I'd vote (a) with one extra
  benchmark row at N=480 specifically for hierarchical so the comparison to flat
   is "close enough." Or simpler: just commit to K ∈ {2, 4} and pick {48, 96,
  200, 480} so everything divides cleanly by 4.

  B. The Merkle builder needs to be extended for per-segment proofs. Currently
  pipeline/merkle_builder/ produces one Prover.toml with N edge proofs. For
  hierarchical, we need to slice this: segment i gets M-1 internal-edge proofs +
   the global root. The glue gets K boundary-edge proofs. Same tree, same root —
   just different proof selections. Probably easiest: add a --segments K flag
  that emits K+1 Prover.tomls instead of one. Not infrastructure-y in a bad way;
   it's the minimal extension.

  C. The hash chain in A++ is over cycle order, not sorted order. I want to make
   sure this is obvious: sub-circuit i privately folds cycle_segment[0..M]
  (cycle order) into the chain, producing h_out_i. The grand product P_i = ∏(X +
   cycle_segment[j]) is order-independent (commutative product), so it gives the
   multiset. The chain gives the ordering. Together they pin down a Hamiltonian
  cycle. The two roles are separate and complementary — worth a sentence in the
  supervisor report so the reader doesn't conflate them.

  D. Boundary self-loops in the glue are auto-prevented. If the partition check
  passes (the union is exactly {0..N-1}), then ends[i] and starts[(i+1)%K] are
  in different segments, hence different nodes. So no explicit ends[i] != 
  starts[(i+1)%K] assertion is needed; the partition check subsumes it. Just
  noting so we don't add a redundant constraint.

  E. Glue is shared between A and B; A++ needs its own glue. A and B differ in
  sub-circuit body (Merkle proofs vs sub-matrix ROM lookups) but the glue is
  identical for both — sort-based partition + K boundary Merkle proofs +
  threshold sum. A++'s glue replaces the sort with the grand-product check. So
  we'll end up with two glue circuits: hierarchical_glue (shared by A and B) and
   hierarchical_glue_fs (for A++).

  F. Variant ordering revisited. Given (E), the natural implementation order
  might actually be A → B → A++, not A → A++ → B. After A works, B reuses the
  glue and only needs a different sub-circuit body — cheap second variant. Then
  A++ is the bigger sub-circuit + new glue change. Want to commit to this order,
   or stick with A → A++ → B from the summary?

  ---
  Want me to start sketching the A sub-circuit and glue file structure, or are
  there more things to discuss first?

✻ Cogitated for 1m 46s

❯ Let's recap all 3 variants and how they work + how they differ. Then let's    
  dive deep into A, explaining the logic and how it works, and adding also a    
  practical example to make it more concrete (small numerical example). We can  
  take multiples of 8 for simplicity in point A.                                

● Locking in: benchmarks at N ∈ {48, 96, 192, 480}, K ∈ {2, 4, 8}, M = N/K. All
  divisible cleanly. The N=480 row is the comparison anchor against
  flat_merkle's N=500 (~4% off, close enough for the frontier figure).

  ---
  Recap: the three variants

  All three share the same skeleton:
  - K sub-proofs each proving a Hamiltonian path of M = N/K nodes is internally
  consistent
  - 1 glue proof that stitches the K paths into a Hamiltonian cycle on N nodes
  - K+1 independent proofs (model (i)) — verifier runs bb verify K+1 times and
  cross-checks shared public-input fields

  What they prove is the same statement: "I know a Hamiltonian cycle on N nodes
  with total cost ≤ T against a committed cost matrix." They differ in how the 
  cost matrix is exposed and how the partition check is enforced in the glue.

  Axis: Cost matrix access
  A (Merkle, sorted public): Poseidon2 Merkle root only
  A++ (Merkle, grand-product FS): Same as A
  B (flat_full, sub-matrix public): M×M sub-matrix is public input per
    sub-circuit; root only used for boundary edges in glue
  ────────────────────────────────────────
  Axis: Internal edges in sub-circuit
  A (Merkle, sorted public): M-1 Merkle proofs
  A++ (Merkle, grand-product FS): M-1 Merkle proofs
  B (flat_full, sub-matrix public): M-1 ROM lookups (cheap)
  ────────────────────────────────────────
  Axis: Sub-circuit publishes
  A (Merkle, sorted public): sorted_nodes[M], start, end, partial_cost
  A++ (Merkle, grand-product FS): (P_i, h_in, h_out) + start, end, partial_cost
  B (flat_full, sub-matrix public): Same as A
  ────────────────────────────────────────
  Axis: Glue partition check
  A (Merkle, sorted public): sort N concatenated values, == [0..N-1]
  A++ (Merkle, grand-product FS): grand product ∏P_i == ∏(X+j) with X =
    Poseidon2(c)
  B (flat_full, sub-matrix public): Same as A
  ────────────────────────────────────────
  Axis: Boundary edges in glue
  A (Merkle, sorted public): K Merkle proofs
  A++ (Merkle, grand-product FS): K Merkle proofs
  B (flat_full, sub-matrix public): K Merkle proofs
  ────────────────────────────────────────
  Axis: Verifier learns
  A (Merkle, sorted public): partition, endpoints, per-segment costs
  A++ (Merkle, grand-product FS): endpoints, per-segment costs, Field aggregates

    (interior hidden)
  B (flat_full, sub-matrix public): partition, per-segment sub-matrices,
    endpoints, per-segment costs
  ────────────────────────────────────────
  Axis: Total gates vs flat_merkle
  A (Merkle, sorted public): ~same (+1.5%)
  A++ (Merkle, grand-product FS): ~+5.5% over A
  B (flat_full, sub-matrix public): beats flat_merkle at K ≥ 3, N=500
  ────────────────────────────────────────
  Axis: Soundness
  A (Merkle, sorted public): unconditional
  A++ (Merkle, grand-product FS): Fiat-Shamir + Schwartz-Zippel (~2⁻²⁵⁴)
  B (flat_full, sub-matrix public): unconditional
  ────────────────────────────────────────
  Axis: Glue shared with
  A (Merkle, sorted public): B
  A++ (Merkle, grand-product FS): (its own)
  B (flat_full, sub-matrix public): A

  The frontier this paints: B is gates-optimal but privacy-worst. A++ is
  privacy-optimal among the Merkle-based options. A is the boring middle ground
  that exists as the baseline both extremes are measured against. None
  Pareto-dominates the others — that's the thesis claim.

  ---
  Variant A — deep dive

  Architecture

  Sub-circuit hierarchical_segment (one compile, instantiated K times):

  Public inputs:
    root:          Field             // shared global Merkle root over N*N cost
  matrix
    sorted_nodes:  [u32; M]          // segment's node set, ascending
    start_node:    u32               // first node in cycle order
    end_node:      u32               // last node in cycle order
    partial_cost:  u64               // sum of M-1 internal edge costs

  Private witness:
    cycle_segment: [u32; M]          // segment in cycle order (NOT sorted)
    edge_costs:    [u64; M-1]        // internal edge costs
    siblings:      [Field; (M-1)*DEPTH]
    path_bits:     [bool;  (M-1)*DEPTH]

  Five constraint groups:
  - G1 Range: every cycle_segment[i] < N
  - G2 Permutation: sort(cycle_segment) == sorted_nodes — so the
  publicly-published sorted_nodes is forced to be the actual sorted multiset of
  cycle_segment
  - G3 Endpoints: start_node == cycle_segment[0], end_node == cycle_segment[M-1]
  - G4 Internal Merkle: for each i in 0..M-1, verify the Merkle proof for leaf
  index cycle_segment[i] * N + cycle_segment[i+1] with leaf value edge_costs[i],
   against root
  - G5 Cost binding: sum(edge_costs) == partial_cost

  Glue circuit hierarchical_glue (one compile per (N, K)):

  Public inputs:
    root:              Field
    threshold:         u64
    all_sorted_nodes:  [u32; N]      // concatenation of K sub-circuits'
  sorted_nodes
    starts:            [u32; K]
    ends:              [u32; K]
    partial_costs:     [u64; K]

  Private witness:
    boundary_costs:        [u64; K]
    boundary_siblings:     [Field; K*DEPTH]
    boundary_path_bits:    [bool;  K*DEPTH]

  Four constraint groups:
  - G1 (no constraints, structural): boundary edges defined as ends[i] → 
  starts[(i+1) % K]
  - G2 Partition: sort(all_sorted_nodes) == [0, 1, ..., N-1]
  - G3 Boundary Merkle: for each i in 0..K, verify Merkle proof for leaf index
  ends[i] * N + starts[(i+1)%K] with leaf value boundary_costs[i], against root
  - G4 Threshold: sum(partial_costs) + sum(boundary_costs) <= threshold

  Verifier-side cross-checks (after bb verify succeeds on all K+1 proofs):
  - All K+1 proofs share the same root value
  - glue.all_sorted_nodes[i*M..(i+1)*M] == sub_proof_i.sorted_nodes for each i
  - glue.starts[i] == sub_proof_i.start_node, same for ends and partial_costs

  Why this is sound

  Three facts compose:

  1. Each sub-proof guarantees a Hamiltonian path of M distinct (G2) nodes
  within range (G1), starting at start_node and ending at end_node (G3), with
  M-1 internal edges whose costs are bound to the committed matrix (G4), summing
   to partial_cost (G5).
  2. The glue guarantees the K segment node sets partition {0..N-1} exactly (G2
  — sorted concatenation equals identity), and the K boundary edges are bound to
   the committed matrix (G3), with total cost ≤ threshold (G4).
  3. Verifier cross-checks force the glue and sub-proofs to refer to the same
  sorted_nodes, starts, ends, partial_costs, and root.

  Together: there exists a Hamiltonian cycle on N nodes (K paths + K stitching
  edges = N edges total, partition is a permutation of {0..N-1}) with all N edge
   costs bound to the committed cost matrix and total cost ≤ T.

  Boundary self-loops (ends[i] == starts[(i+1)%K]) are auto-prevented: if the
  partition is exact, ends and starts of different segments are in different
  segment sets, so the values differ.

  Worked example: N = 8, K = 2, M = 4, DEPTH = 6

  Take cycle 0 → 5 → 3 → 2 → 7 → 4 → 1 → 6 → 0 with these edge costs:

  ┌──────┬──────┬────────────────┐
  │ Edge │ Cost │      Role      │
  ├──────┼──────┼────────────────┤
  │ 0→5  │ 10   │ seg 0 internal │
  ├──────┼──────┼────────────────┤
  │ 5→3  │ 12   │ seg 0 internal │
  ├──────┼──────┼────────────────┤
  │ 3→2  │ 8    │ seg 0 internal │
  ├──────┼──────┼────────────────┤
  │ 2→7  │ 15   │ boundary       │
  ├──────┼──────┼────────────────┤
  │ 7→4  │ 11   │ seg 1 internal │
  ├──────┼──────┼────────────────┤
  │ 4→1  │ 9    │ seg 1 internal │
  ├──────┼──────┼────────────────┤
  │ 1→6  │ 14   │ seg 1 internal │
  ├──────┼──────┼────────────────┤
  │ 6→0  │ 13   │ boundary       │
  └──────┴──────┴────────────────┘

  Total = 92. Threshold = 100.

  Sub-circuit 0 (segment 0 = cycle indices 0..3)

  ┌─────────────────────────┬──────────────┐
  │        Quantity         │    Value     │
  ├─────────────────────────┼──────────────┤
  │ cycle_segment (private) │ [0, 5, 3, 2] │
  ├─────────────────────────┼──────────────┤
  │ sorted_nodes (public)   │ [0, 2, 3, 5] │
  ├─────────────────────────┼──────────────┤
  │ start_node (public)     │ 0            │
  ├─────────────────────────┼──────────────┤
  │ end_node (public)       │ 2            │
  ├─────────────────────────┼──────────────┤
  │ edge_costs (private)    │ [10, 12, 8]  │
  ├─────────────────────────┼──────────────┤
  │ partial_cost (public)   │ 30           │
  └─────────────────────────┴──────────────┘

  Inside the sub-circuit:
  - G1: 0<8, 5<8, 3<8, 2<8 ✓
  - G2: sort([0,5,3,2]) = [0,2,3,5] == sorted_nodes ✓
  - G3: start_node=0=cycle_segment[0] ✓; end_node=2=cycle_segment[3] ✓
  - G4: three Merkle proofs:
    - Edge 0→5: leaf index = 0·8+5 = 5, leaf value 10, path_bits = LSB(5,6) =
  [1,0,1,0,0,0]
    - Edge 5→3: leaf index = 5·8+3 = 43, leaf value 12, path_bits = LSB(43,6) =
  [1,1,0,1,0,1]
    - Edge 3→2: leaf index = 3·8+2 = 26, leaf value 8, path_bits = LSB(26,6) =
  [0,1,0,1,1,0]
  Each hashes upward 6 levels and must equal root.
  - G5: 10+12+8 = 30 = partial_cost ✓

  Sub-circuit 1 (segment 1 = cycle indices 4..7)

  ┌─────────────────────────┬──────────────┐
  │        Quantity         │    Value     │
  ├─────────────────────────┼──────────────┤
  │ cycle_segment (private) │ [7, 4, 1, 6] │
  ├─────────────────────────┼──────────────┤
  │ sorted_nodes (public)   │ [1, 4, 6, 7] │
  ├─────────────────────────┼──────────────┤
  │ start_node (public)     │ 7            │
  ├─────────────────────────┼──────────────┤
  │ end_node (public)       │ 6            │
  ├─────────────────────────┼──────────────┤
  │ edge_costs (private)    │ [11, 9, 14]  │
  ├─────────────────────────┼──────────────┤
  │ partial_cost (public)   │ 34           │
  └─────────────────────────┴──────────────┘

  Mirror structure. G4 proves leaves at indices 7·8+4=60, 4·8+1=33, 1·8+6=14,
  leaf values 11, 9, 14.

  Glue

  ┌───────────────────────────┬────────────────────┐
  │         Quantity          │       Value        │
  ├───────────────────────────┼────────────────────┤
  │ all_sorted_nodes (public) │ [0,2,3,5, 1,4,6,7] │
  ├───────────────────────────┼────────────────────┤
  │ starts (public)           │ [0, 7]             │
  ├───────────────────────────┼────────────────────┤
  │ ends (public)             │ [2, 6]             │
  ├───────────────────────────┼────────────────────┤
  │ partial_costs (public)    │ [30, 34]           │
  ├───────────────────────────┼────────────────────┤
  │ boundary_costs (private)  │ [15, 13]           │
  ├───────────────────────────┼────────────────────┤
  │ threshold (public)        │ 100                │
  └───────────────────────────┴────────────────────┘

  Inside the glue:
  - G2 Partition: sort([0,2,3,5,1,4,6,7]) = [0,1,2,3,4,5,6,7] = [0..7] ✓
  - G3 Boundary Merkle:
    - Boundary 0: ends[0]→starts[1] = 2→7, leaf index 2·8+7 = 23, leaf value 15,
   path_bits = LSB(23,6) = [1,1,1,0,1,0]
    - Boundary 1: ends[1]→starts[0] = 6→0, leaf index 6·8+0 = 48, leaf value 13,
   path_bits = LSB(48,6) = [0,0,0,0,1,1]
  - G4 Threshold: 30 + 34 + 15 + 13 = 92 ≤ 100 ✓

  What the verifier does

  Runs bb verify three times (sub_0, sub_1, glue). All succeed. Then checks:
  - All three proofs declare the same root
  - glue.all_sorted_nodes[0..4] == [0,2,3,5] == sub_0.sorted_nodes ✓
  - glue.all_sorted_nodes[4..8] == [1,4,6,7] == sub_1.sorted_nodes ✓
  - glue.starts == [sub_0.start_node, sub_1.start_node] == [0, 7] ✓
  - glue.ends == [sub_0.end_node, sub_1.end_node] == [2, 6] ✓
  - glue.partial_costs == [30, 34] ✓

  All checks pass → the verifier accepts.

  What an attacker can't get away with

  - Putting node 3 in both segments? Partition check fails (3 appears twice in
  all_sorted_nodes; sort doesn't equal [0..7]).
  - Faking edge 0→5's cost as 5 instead of 10? Merkle proof in G4 of sub-circuit
   0 won't hash to root (Poseidon2 collision resistance).
  - Using a proof for leaf 4 instead of leaf 5? Leaf index check inside G4's
  Merkle verification (path_bits reconstructed to leaf index) fails.
  - Lying about partial_cost = 20 instead of 30? G5 of sub-circuit fails.
  - Saying ends[0]=3 in glue but end_node=2 in sub_0? Verifier-side cross-check
  fails — proofs would individually verify but the cross-check rejects.

  ---
  Want me to do the same for B next, or for A++? B is the cheaper second variant
   (reuses glue logic, simpler sub-circuit body) so it'd be a quick comparison;
  A++ is the more conceptually involved one.

✻ Churned for 1m 50s

※ recap: We're designing three hierarchical ZKP variants (A, A++, B) for TSP and just finished a deep dive on Variant A with an N=8, K=2 worked example. Next: walk through Variant B or A++ in the same way. (disable recaps in /config)

❯ So the checks after the bb verify are in order to ensure the glue proof       
  actually refers to the sub-circuits and not to some random but consistent     
  thing? And also, what does this mean in terms of privacy for the prover and   
  the cycle with the cost? What is the leakage due to public info being used    
  for the sub-circuits and the glue? Because if we leak too much to the extend  
  one can reverse-engineer the path, then the zero-knowledge proof is not so    
  much zero-knowledge. Let's focus on this for variant A, and understand it     
  deeply.                                                                       

● Question 1: yes, the cross-checks bind the proofs

  Exactly right. Each bb verify only confirms that one proof is internally
  consistent with its declared public inputs. The K+1 proofs are otherwise
  unrelated cryptographic objects — UltraHonk has no mechanism to link them.
  Without verifier-side cross-checks, a malicious prover could produce:

  - sub_proof_0: a perfectly valid path on {0,2,3,5}, partial_cost 30, root R
  - sub_proof_1: a perfectly valid path on {1,4,6,7}, partial_cost 34, root R
  - glue: a perfectly valid stitching with starts=[9,11] and
  partial_costs=[100,100], root R

  All three pass bb verify individually. But they describe three different
  "universes" — the glue's partial_costs don't agree with the sub-proofs', etc.
  The cross-checks force one coherent universe.

  So the security argument is: each Noir circuit guarantees a local truth, and
  the verifier-side equality checks compose those local truths into a global
  truth. This is the explicit alternative to recursive verification: instead of
  one circuit verifying another, the verifier (a human or a tiny script) does
  the bookkeeping.

  A practical implication: the "verifier" in this design is no longer just bb 
  verify; it's bb verify × (K+1) plus a public-input cross-check routine. The
  cross-check is O(N) cheap arithmetic at the verifier — negligible compared to
  proof verification.

  ---
  Question 2: privacy in Variant A — the careful version

  You're putting your finger on the central tension in this whole frontier. Let
  me separate two things that often get conflated:

  (a) The cryptographic ZK property. UltraHonk's zero-knowledge guarantee says:
  the verifier learns nothing about the private witness beyond what's already
  implied by the public inputs. This holds for every individual proof in our K+1
   tuple. In that strict sense, Variant A is "as zero-knowledge as ZK-SNARKs
  get."

  (b) What the public inputs themselves reveal. This is a design choice, not a
  property of the proof system. ZK doesn't protect you from publishing too much
  in the public inputs. If you stick the entire cycle in the public input, the
  proof is still "zero-knowledge" in sense (a) — there's just nothing left to
  hide.

  The interesting question is (b). Let's walk through it for A precisely.

  Exactly what the verifier sees, in the N=8 example

  Public, across all proofs:
  - root (one Field element — commits the 8×8 cost matrix; reveals nothing about
   entries)
  - threshold = 100
  - Partition with endpoints: segment 0 is the set {0,2,3,5} traversed from 0 to
   2; segment 1 is {1,4,6,7} traversed from 7 to 6
  - Cost decomposition: partial_costs = [30, 34], so segment-internal sums are
  exposed

  Private, never revealed:
  - The interior order within each segment (was it 0→5→3→2 or 0→3→5→2?)
  - Individual edge costs (we know 30 = three costs summing to 30, not which
  edges have which weight)
  - Boundary edge costs (we know they exist between 2→7 and 6→0, but not their
  values 15 and 13)
  - All other matrix entries

  What can the verifier deduce?

  Deduction 1: The macro skeleton of the cycle is exposed

  The verifier knows the cycle has shape:

  0  →  ?  →  ?  →  2  →  7  →  ?  →  ?  →  6  →  0
  └─────────┬────────┘   └─────────┬────────┘   ↑
         segment 0              segment 1    boundary
         interior is              interior is   2→7 and
         perm of {3,5}            perm of {1,4} 6→0 are
                                                fixed

  The two ? pairs are the interior nodes of each segment, in some unknown order.

  Deduction 2: The cycle is one of [(M-2)!]^K candidates

  For N=8, K=2, M=4: each segment has M-2=2 interior positions, so (2!)² = 4
  candidate cycles consistent with the verifier's view:

  - 0→3→5→2→7→1→4→6→0
  - 0→3→5→2→7→4→1→6→0
  - 0→5→3→2→7→1→4→6→0
  - 0→5→3→2→7→4→1→6→0 ← the real one

  Starting point: (N-1)! = 5040 possible Hamiltonian cycles on 8 nodes. After
  seeing A's public inputs: 4 remaining. The verifier has gained log₂(5040/4) ≈
  10.3 bits of cycle information.

  For N=480, K=4, M=120: candidates left = (118!)^4. Out of 479! total. Bits
  leaked ≈ log₂(479!) − log₂((118!)^4). Order of magnitude: ~800 bits leaked out
   of ~4000 bits total entropy. So 20% of the cycle's entropy is gone.

  Deduction 3: Cost matrix entries stay hidden (modulo aggregate constraints)

  partial_cost_0 = 30 reveals: the sum of three matrix entries (one of
  {M[0,3],M[0,5]}, one of {M[3,5],M[3,2],M[5,3],M[5,2]}, one of {M[3,2],M[5,2]})
   equals 30. That's a linear constraint over a subset of entries, but doesn't
  pin any single one down.

  Individual entries remain behind the Merkle root.

  When does this leakage matter?

  Threat model 1: Cost matrix is private to the prover.

  The verifier doesn't know any matrix entries; they only see the root. Even
  with the macro skeleton revealed, they can't compute the cost of any specific
  cycle — they can't test candidates against the cost matrix. The leakage is
  purely structural (partition + endpoints). For a logistics use case where the
  cost matrix is the prover's proprietary pricing, A is probably fine.

  Threat model 2: Cost matrix is public knowledge.

  The verifier knows the matrix entries (e.g., physical distances on a known
  map). Now the verifier can:
  - Enumerate the [(M-2)!]^K candidate cycles
  - Compute each one's total cost from the known matrix
  - Filter to candidates whose per-segment internal sums match partial_costs[i]
  exactly

  That filtering is extremely sharp. Each partial_cost_i is a u64 sum — matching
   exactly is a strong constraint. In practice the verifier often recovers the
  actual cycle uniquely.

  So under threat model 2, A is barely zero-knowledge in any practical sense.
  The proof confirms a fact (cycle exists, cost ≤ T) the verifier could already
  verify by inspection of the few remaining candidates.

  Threat model 3: Cost matrix has structure the verifier knows partially.

  E.g., the verifier knows it's a triangle-inequality metric or knows certain
  entries (some city pairs are zero distance). This is the messy middle case.
  The leakage is somewhere between (1) and (2), and depends on what auxiliary
  information the verifier has.

  The honest framing of A's privacy

  A leaks the partition and the macro skeleton of the cycle. It does not leak:
  - Individual matrix entries
  - The interior ordering of each segment

  This is enough leakage that under "verifier knows the matrix" threat models, A
   is much weaker than flat_merkle (which leaks nothing about the cycle at all).
   It's still ZK in the cryptographic sense — UltraHonk does its job — but the
  design choice of what goes in the public inputs is the privacy story, not the
  proof system.

  How A++ fixes this

  A++'s improvement is precise: it removes sorted_nodes[M] from each
  sub-circuit's public output and replaces it with the Field element P_i = ∏(X +
   v_j). The grand product is a commutative aggregate — it commits to the
  multiset without revealing individual elements. The Fiat-Shamir construction
  ensures the verifier can't search for fake multisets.

  After A++:
  - Verifier still learns: K endpoints, K partial_costs, K (P_i, h_in, h_out)
  triples
  - Verifier no longer learns: which nodes are in which segment

  So the candidate-cycle count for A++ at N=8, K=2 jumps from 4 back up to
  something close to (N-1)! (with only the boundary edges and partial cost sums
  constraining it).

  That ~5.5% gate overhead is what privacy costs in this construction. The
  frontier is real.

  ---
  This is exactly the analysis I'd want in §7 / §6 of the supervisor report next
   to "Findings 6–8" — it makes the dualism concrete by quantifying what each
  variant exposes.

  Want me to walk through A++ next with the same depth, focusing on (i) what the
   grand product actually proves and (ii) how the Fiat-Shamir chain prevents the
   prover from gaming X? Or would you rather do B first?

✻ Cogitated for 1m 50s

❯ So we need a way to sell variant A so that it becomes still somehow valuable  
  in some usecase. And the we can raise its problems for coming up with other   
  variants and possibly recursion. The problem is that having the matrix        
  private means that the verifier has to trust the commitment? And what use     
  case does that represent? I don't find a realistic one. And the case in which 
   the matrix is public, then we lose almost all privacy, and at that point the 
   commitment is only about passing less input rather than revealing less. This 
   gives "accountability and trust" because the root can be checked by both     
  parties by knowing the matrix, but then as said the verifier practically      
  learns the full cycle, meaning it could check it without K+1 proofs. So we    
  need to find a way to justify the choice and the process, also wrt to the     
  flat approach we've been considering.                                         

● You're identifying the central marketing problem for A, and I think you're
  roughly right — but slightly overstating the case in one direction. Let me
  sharpen both points and then propose how to actually frame A so it earns its
  place.

  The matrix-private threat model: you're right, weak for TSP

  I tried this on too. The candidate use cases all wobble:

  - Auditor pattern: prover commits to matrix M once, regulator never sees M but
   checks "your routes stay within your committed prices." Sort of works, but
  the regulator has to trust that the committed matrix is legitimate — otherwise
   the prover commits to fake-cheap prices and proves trivially. So the
  commitment needs out-of-band binding (signed by a tax authority, anchored to
  an exchange rate, …). At that point, the ZK part is doing thin work.
  - Cross-time consistency: same root across multiple proofs lets the verifier
  confirm "same matrix used in proofs from January and July." Real, but a small
  win.
  - Sealed-bid markets: closer to a real use case, but pretty niche and not
  specifically about TSP.

  I agree: there's no killer matrix-private TSP application. The matrix-private
  framing is mostly an artifact of how flat_merkle was sold (and even there, the
   sales pitch is shakier than usual ZK papers make it sound).

  The matrix-public threat model: you're overstating the leakage

  This is where I'd push back gently. You said "verifier practically learns the
  full cycle, meaning it could check it without K+1 proofs." That's true at N=8
  — yes, 4 candidate cycles, you can enumerate. It's not true at N=480, K=4.
  Number of candidate cycles remaining: (118!)^4 ≈ 10^800. The partial_cost
  constraint trims this, but for typical cost matrices, the number of
  (118-permutations summing to a specific value) is still ~10^180 or so. The
  verifier cannot enumerate this space.

  So even under "matrix is public," A still proves something the verifier can't
  otherwise verify by inspection: it proves cryptographically that one of those 
  10^180 cycles per segment exists and is short, without disclosing which. The
  leakage is real (partition + macro skeleton) but it's not "the full cycle."

  That said — and this is the deeper point you're after — the type of leakage is
   structural: the verifier learns the shape of the cycle (partition +
  endpoints) but not its detail. Whether that's acceptable depends entirely on
  whether the shape itself is sensitive.

  The reframe: A proves a different statement than flat_merkle

  I think the way to honestly sell A is not as "flat_merkle with parallelism and
   some privacy cost" — that's a losing trade if there's no parallelism story
  strong enough to outweigh the privacy loss. Instead, A is best understood as
  proving a different statement:

  ┌─────────────┬────────────────────────────────────────────────────────────┐
  │   Variant   │                         Statement                          │
  ├─────────────┼────────────────────────────────────────────────────────────┤
  │ flat_merkle │ "∃ Hamiltonian cycle with cost ≤ T against committed M"    │
  ├─────────────┼────────────────────────────────────────────────────────────┤
  │ A           │ "∃ Hamiltonian cycle with cost ≤ T against committed M     │
  │             │ that respects partition P, where P is disclosed"           │
  ├─────────────┼────────────────────────────────────────────────────────────┤
  │             │ "∃ Hamiltonian cycle with cost ≤ T against committed M     │
  │ A++         │ that decomposes into K segments of size M, where the       │
  │             │ segments themselves are hidden"                            │
  ├─────────────┼────────────────────────────────────────────────────────────┤
  │             │ "∃ Hamiltonian cycle with cost ≤ T against committed M,    │
  │ B           │ where segment-local sub-matrices and partition are         │
  │             │ disclosed"                                                 │
  └─────────────┴────────────────────────────────────────────────────────────┘

  Under this framing, A's partition disclosure is part of the statement being 
  proved, not a privacy leak. The natural use cases are where the partition is
  already a real-world constraint:

  - Regulated zoning: each delivery driver must stay within their assigned zone.
   The verifier (regulator) requires the cycle to respect the zone partition.
  They want to see partition compliance. A's disclosure is intentional.
  - Multi-team SLAs: team A handles nodes {0,2,3,5}, team B handles {1,4,6,7}.
  Proving total cost ≤ T for the combined route, with each team's contribution
  accountable, is exactly what A's partial_costs give you.
  - Cross-organisational logistics: two companies share a route. Each commits to
   their leg's cost (partial_cost_i is their responsibility). The partition is
  operational; the leg costs are accountability artifacts; the per-edge detail
  stays private.
  - Routing audits with privacy-preserving aggregates: "show me the total cost
  broke down by region without revealing the within-region paths."

  In all of these, the verifier wants the partition and per-segment cost to be
  public. A is the right variant.

  A++ then becomes "same problem class, but with partition hidden" — the use
  case shifts to scenarios where the K-fold split is operationally meaningful
  (e.g., for parallelism) but the specific partition shouldn't be disclosed
  (e.g., the partition reveals competitive structure).

  B is the variant for "I don't care about hiding the matrix because it's public
   anyway; minimise prover cost."

  The flat-vs-hierarchical narrative this enables

  With this reframe, the thesis narrative becomes much cleaner than "crossover
  point":

  1. flat_full: simplest, no commitment scheme. Matrix exposure cost is O(N²).
  Use when N is small.
  2. flat_merkle: matrix committed, proves the basic existence statement, single
   prover. Use when N is moderate and matrix should stay private.
  3. A: proves a richer statement (partition-respecting cycle). Use when N is
  large enough that parallel proving / per-prover memory matters, AND the
  partition is a natural operational constraint.
  4. A++: same parallelism/memory wins as A, but for use cases where the
  partition is sensitive. Costs ~5.5% extra gates.
  5. B: gate-optimal hierarchical, for use cases where the cost matrix is
  non-sensitive (public maps, distances).
  6. Recursion / folding (future): collapse K+1 proofs into one for
  verifier-side overhead reasons. Out of scope.

  Each variant has a natural use case, not just a position on a frontier. The
  frontier figure remains accurate, but the prose around it becomes: "different
  applications of TSP ZK have different privacy requirements; this thesis maps
  the design space and explains why no single point dominates."

  What this means for the dualism / thesis core

  The dualism finding becomes even sharper under this reframe: hierarchical
  decomposition in ZK isn't a free optimisation; it's a commitment to a richer 
  statement. Optimisation decomposition is also a richer statement (the
  heuristic restricts the solution space), but optimisation benefits from richer
   statements (smaller search) while ZK is neutral or harmed by them (the prover
   has to do additional work to discharge the extra structure).

  That's the cleaner version of "constraints flip sign across the two domains,"
  and it directly justifies why we have three variants rather than one: each is
  the right design for a different statement-of-interest, none is universally
  best.

  ---
  Does this reframe sit right? If yes, we should probably edit §1 and §7 of the
  supervisor report to match — the current draft still has some "A is a baseline
   measured against flat_merkle" language that this reframe replaces with "A
  proves a partition-respecting cycle, which is a different statement". Want me
  to draft those edits, or keep going with A++ next?

✻ Cogitated for 1m 54s

❯ So what would be the main point of the updated thesis, where the main goal is 
   no longer the simple "cross-over" point? And can we state uses cases for     
  both the private and public matrices, explaining how can a verifier or a      
  private matrix scenario introduce trust to the commitment?                    

● The updated thesis main point

  The thesis is no longer answering "when does X beat Y?" — it's answering a
  structural question:

  ▎ TSP-with-privacy is not one problem. It is a family of problems, 
  ▎ distinguished by what part of the input (cost matrix, partition, segment 
  ▎ endpoints, individual costs) is private vs public to the verifier. Each 
  ▎ variant in this thesis is the natural proof design for a specific point in 
  ▎ that family. The structural reason these variants do not collapse to a 
  ▎ single "best" design is the dualism between optimisation and zero-knowledge 
  ▎ proving: hierarchical decomposition imposes a constraint in optimisation 
  ▎ (good) and weakens a constraint in ZK (bad), and the two effects cannot be 
  ▎ made to cancel for TSP because the problem does not factor locally.

  The contributions become:

  1. Empirical characterisation of the flat baseline: 5 circuit variants, fits
  to N=500, the ~87 gates/Poseidon2 finding, the N≈175 flat_full↔flat_merkle
  crossover. This stays valid because flat_full and flat_merkle prove the same 
  statement — their crossover is a meaningful comparison.
  2. The dualism: structural argument for why hierarchical decomposition behaves
   oppositely in optimisation vs ZK. The NP asymmetry as root cause. This is the
   conceptual contribution.
  3. A negative result with explanation: hierarchical Merkle does NOT reduce
  total gate count for TSP. The cancellation isn't accidental — it follows from
  the dualism. Correcting a widespread informal assumption.
  4. A frontier-mapping methodology: three hierarchical variants (A, A++, B) on
  a privacy/cost/parallelism surface, with a clear use-case mapping. None
  Pareto-dominates, by design.
  5. Future-work pointer: folding schemes (Nova/ProtoStar) are the natural
  extension precisely because they sidestep the per-recursion verifier overhead
  that makes recursive verification expensive in our setting. The thesis grounds
   why this is the right next step.

  The crossover figure becomes one panel of the frontier figure rather than the
  climax of the thesis.

  ---
  Use cases by matrix-visibility regime

  Private matrix (verifier sees only the root)

  Trust in the commitment is the load-bearing question here. Without an external
   trust anchor, the prover can commit to a self-serving fictitious matrix and
  prove anything trivially. Real-world trust anchors:

  Trust mechanism: Authority signature
  How it works: A trusted third party signs the root
  Example: A logistics regulator certifies the prover's annual cost matrix; the
    root is signed and notarised. The verifier (auditor, customer) trusts the
    signer, not the prover.
  ────────────────────────────────────────
  Trust mechanism: Trusted oracle
  How it works: A neutral data provider publishes signed roots over its data
  Example: OpenStreetMap or Google publishes a signed Merkle root of pairwise
    travel times for a city, monthly. Any party can prove route properties
    against the oracle's data.
  ────────────────────────────────────────
  Trust mechanism: Cross-attestation
  How it works: Multiple stakeholders co-commit
  Example: Two logistics companies share a network. Each signs the joint cost
    matrix root. Either can later prove "my contribution is within bounds"
    without revealing the matrix to outsiders.
  ────────────────────────────────────────
  Trust mechanism: Public timestamping
  How it works: Root published to a transparency log at a known time
  Example: The prover anchors the root on a blockchain or Certificate
    Transparency log before the proofs are produced. Provides binding-to-time
    without disclosing the matrix.
  ────────────────────────────────────────
  Trust mechanism: Decommitment-on-dispute
  How it works: Matrix opened under legal process
  Example: The committed root is the binding object; the matrix is opened only
  if
    a dispute reaches a court or arbitrator.

  Concrete TSP-with-private-matrix use cases:

  - Logistics SLA auditing: A courier company commits to its proprietary
  delivery-cost matrix quarterly (signed by an industry regulator). Throughout
  the quarter, the company proves to customers/regulators "your route cost ≤ the
   quoted maximum" without revealing the matrix (competitively sensitive) or the
   route (privacy). → flat_merkle or A.
  - ESG / carbon accounting: A fleet operator commits to an emissions-distance
  matrix signed by a third-party sustainability auditor. The operator then
  proves to investors "our routes meet our committed carbon budget" without
  revealing route specifics. → A or A++ (depending on whether the regional
  partition is itself sensitive).
  - Cross-organisation cost-sharing: Two organisations jointly route around a
  shared cost matrix neither wants to disclose externally. Each commits, each
  proves their leg meets its budget. → A's partial_cost per segment is exactly
  the accountability artifact each party needs.

  Public matrix (verifier knows M)

  Here the Merkle commitment isn't doing privacy work — it's doing proof-size
  work (passing log-N data instead of N² entries). The verifier independently
  checks the root against the known matrix. The privacy story is entirely about
  hiding the route.

  Use case: City logistics on public road networks
  Why public matrix: OSM data is public; only the courier's route is sensitive
  Natural variant: A++ (route fully hidden) or A (if delivery districts are
    public)
  ────────────────────────────────────────
  Use case: Public-benchmark TSP solutions
  Why public matrix: Standard TSPLIB instances; the matrix IS the benchmark
  Natural variant: A++ or future recursive variant
  ────────────────────────────────────────
  Use case: Smart-city fleet routing
  Why public matrix: Street network is public infrastructure; individual fleet
    routes are competitively sensitive
  Natural variant: A++ (operator hides full route) or B (gate-optimal when route

    shape is acceptable to reveal)
  ────────────────────────────────────────
  Use case: Public emissions / distance standards
  Why public matrix: Regulator publishes standardised matrix
  Natural variant: A or A++ depending on whether the regulated entity must
  report
    by region

  A subtle point for the matrix-public case: the Merkle commitment now provides
  integrity rather than privacy. The verifier hashes the public matrix
  themselves and checks the root matches — preventing the prover from sneakily
  using a different matrix in the proof. So even in matrix-public scenarios, the
   commitment is doing real work; it's just not privacy work.

  ---
  Variant ↔ use-case map (the table the supervisor report should have)

  Variant: flat_merkle
  Matrix regime: private or public
  What's hidden from verifier: full route
  What's disclosed: nothing
  Natural use cases: "Generic" baseline; single-prover sufficient. Logistics
  SLA,
    ESG audit (when partition isn't reported).
  ────────────────────────────────────────
  Variant: A
  Matrix regime: private or public
  What's hidden from verifier: interior order of each segment
  What's disclosed: partition, endpoints, segment-cost sums
  Natural use cases: Multi-team / multi-region accountability where the
  partition
    IS the audit unit. Cross-org cost-sharing. Regulated zoning.
  ────────────────────────────────────────
  Variant: A++
  Matrix regime: private or public
  What's hidden from verifier: partition AND interior order
  What's disclosed: endpoints, segment-cost sums (in compressed Field form)
  Natural use cases: Same scenarios as A but where the partition itself is
    competitively sensitive. Maximum privacy among hierarchical variants.
  ────────────────────────────────────────
  Variant: B
  Matrix regime: public (or insensitive)
  What's hidden from verifier: full route, but matrix is exposed via
  sub-matrices
  What's disclosed: partition + per-segment sub-matrices
  Natural use cases: Smart-city / open-data fleet routing where matrix is
    non-sensitive and minimising prover cost matters most.
  ────────────────────────────────────────
  Variant: folding (future)
  Matrix regime: any
  What's hidden from verifier: same as A++
  What's disclosed: same as A++
  Natural use cases: When verifier-side overhead (K+1 proofs to check) is the
    binding constraint.

  The frontier figure visualises this: x-axis = privacy bits leaked, y-axis =
  (total gates, parallel wall-clock, or per-prover memory — three panels). The
  three hierarchical variants and the flat baseline appear as distinct points.
  The "best" depends on which use case you're in.

  ---
  The one-paragraph thesis pitch

  ▎ Zero-knowledge proofs for TSP appear superficially to be a single problem, 
  ▎ but separating the problem by what information is private to whom reveals it
  ▎  is a family. Each member of the family has a different natural proof 
  ▎ design. This thesis maps that family for hierarchical ZK proofs of TSP, 
  ▎ characterises the flat baseline empirically, identifies a structural dualism
  ▎  between optimisation and ZK proving that explains why no hierarchical 
  ▎ design is universally best, and shows specifically that hierarchical 
  ▎ decomposition — which is unambiguously beneficial in classical TSP 
  ▎ heuristics — provides no total-gate-count benefit in zero-knowledge proving 
  ▎ without disclosing structural information about the cycle. The thesis 
  ▎ contributions are the empirical characterisation, the dualism argument, the 
  ▎ three-variant frontier mapping, and the negative result with explanation.

  This sells without overclaiming. The negative result is honest; the frontier
  mapping is novel; the dualism is the conceptual hook. It defends as "I mapped
  a design space and explained the structure" rather than "I found a faster
  algorithm" — which is a stronger defense for an MSc thesis because the latter
  is harder to deliver on convincingly.

  ---
  Does this framing land? If yes, the supervisor report §1 and §7 need surgical
  rewrites — I can draft those next. Otherwise we can keep refining the framing
  before touching the document.

✻ Worked for 1m 39s

❯ So the idea here is that NP asymmetry states: Checking much easier than       
  finding. Our thesis aims at proving the opposite when certain conditions on   
  "checking" are required? Is this a good framing? And how to sell that? And    
  what conclusions can one draw from this?                                      

● Your framing is close but not quite accurate, and the inaccuracy is worth
  fixing because it would be the first thing a committee member challenges. Let
  me sharpen it, then talk about how to sell the sharpened version and what it
  actually lets you conclude.

  Refining the framing

  What NP asymmetry actually says: for NP-complete problems, finding a solution
  is (believed to be) exponentially hard while checking a candidate solution is
  polynomial.

  Your proposed framing — "our thesis aims at proving the opposite when certain
  conditions on checking are required" — would mean we're claiming ZK checking
  is harder than finding, which is too strong. Verification of a ZK proof is
  still polynomial (often near-constant). What we're actually showing is more
  subtle:

  ▎ Hierarchical decomposition exploits NP asymmetry to make FINDING easier in 
  ▎ classical optimisation. The same decomposition does NOT make ZK 
  ▎ CHECKING-cost easier for problems with non-local global constraints. The 
  ▎ asymmetry between finding and checking is preserved, but the asymmetry in 
  ▎ how the two respond to decomposition is broken.

  In short: NP asymmetry holds. The thesis is not contradicting it. What the
  thesis is showing is that the techniques that exploit the asymmetry in one 
  direction don't transfer to the other direction. Classical algorithm design
  (the finding side) gets algorithmic speedup from decomposition. ZK proving
  (the checking side) only gets embarrassingly-parallel speedup. For problems
  with non-local constraints like TSP, the two are not symmetric.

  The cleanest one-line version:

  ▎ Hierarchical decomposition gives optimisation an algorithmic speedup, but 
  ▎ gives zero-knowledge proving only an embarrassingly-parallel speedup. For 
  ▎ TSP, this gap is structural and unfixable without changing the proof system.

  How to sell this

  The framing has three things going for it that a committee will recognise as
  research-grade:

  1. It's a structural claim, not a benchmark. It says something true about the
  relationship between two distinct fields (combinatorial optimisation and
  cryptographic proof systems), grounded in the local-vs-global constraint
  structure of NP problems. This is a more durable contribution than "method X
  is N% faster than method Y." Benchmarks rot; structural results don't.

  2. It explains a confusing empirical observation. Practitioners of ZK rollups
  / state-transition proofs do observe massive speedups from recursive
  composition (Nova, ProtoStar, etc.). Practitioners trying to do ZK over graph
  problems don't. There's an implicit confusion in the field about why these two
   stories diverge. The dualism explains it: rollups verify locally-factoring
  computations (each transaction is local); TSP doesn't factor locally. The
  structural reason is the same NP asymmetry argument, applied to a problem
  class where the asymmetry happens to "fight back."

  3. It cleanly delimits future work. Once you have the dualism, you can predict
   which problems will benefit from hierarchical/folding ZK and which won't.
  This is a methodological contribution: it lets the field stop trying
  decomposition tricks on problems where they can't work.

  Selling tactics for the defense:

  - Lead with the negative result. Say upfront: "we set out to find a crossover;
   we found instead a structural reason no crossover exists. This was
  unexpected; here's the explanation." Committees respect honesty about what
  didn't work, especially when accompanied by a structural reason.
  - Anchor on the empirical work. The 5 flat variants + benchmarks + the ~87
  gates/Poseidon2 finding are unambiguously solid. Lead with those; the dualism
  is the interpretation of what was found.
  - Use the field-context framing. Position the thesis as "TSP is a canonical NP
   problem with non-local structure, and hierarchical ZK techniques that work
  for locally-factoring problems do not transfer to it." This positions the
  negative result within an existing conversation in the field (recursive
  SNARKs, folding schemes), rather than as an isolated finding.
  - Don't oversell. Avoid phrases like "we disprove NP asymmetry under certain
  conditions" or "ZK breaks NP asymmetry." These will get torn apart. Say
  instead: "we show that the standard decomposition strategy of classical TSP
  heuristics has no analogue in ZK proving for TSP."

  Conclusions one can draw

  A committee will care about what follows from the structural result. Here are
  the real conclusions:

  1. Problem-class taxonomy for hierarchical ZK. Problems with local constraints
   (Circuit-SAT, state transitions, batched operations) admit
  hierarchical/recursive ZK. Problems with non-local constraints (TSP, graph
  colouring, k-clique, Hamiltonian cycle) do not. This is a usable engineering
  heuristic for anyone designing ZK applications.

  2. Folding schemes are not a free lunch. Nova, ProtoStar, etc. work by
  exploiting local-factoring structure. They don't magically fix the structural
  barrier for non-local problems. The thesis's gate-count baseline becomes the
  floor against which folding schemes would need to compete — and it's not clear
   they could, for TSP specifically. (This is a sharper version of "folding is
  future work" than the supervisor report currently has.)

  3. Privacy-preserving combinatorial optimisation is structurally different 
  from privacy-preserving computation. ZK rollups are about batching local
  operations. Privacy-preserving TSP is about hiding a global structure. The
  proof designs needed are different, and the design space is poorly mapped —
  the thesis's frontier figure is one of few existing data points.

  4. The choice between flat and hierarchical for TSP is not a performance 
  choice; it's a use-case choice. Hierarchical isn't a "faster" proof design —
  it's a different statement (partition-respecting cycle vs any cycle). This
  reframe from "performance crossover" to "use-case selection" applies to other
  graph problems too.

  5. The "hidden cost of decomposition" is a teachable principle. In classical
  algorithm design, decomposition is presented as a strict win. In ZK, it's a
  trade with privacy or with checking work. Articulating this is a
  methodological contribution to how ZK is taught.

  What this means concretely for the thesis document

  Two changes I'd make:

  - §1 (Overview). Replace "we set out to find a crossover" with "we set out to
  characterise the design space of hierarchical TSP ZK proofs; the analysis
  surfaced a structural reason these designs do not collapse to a single optimal
   point. The thesis argues for the structural reason and empirically
  characterises the resulting trade-off space."
  - §7 (Cross-domain perspective). Sharpen the dualism subsection to state
  explicitly: "NP asymmetry holds; the asymmetry in how finding and checking
  respond to decomposition is what fails. Hierarchical decomposition is a
  finding-side speedup that does not transfer to ZK checking for non-local
  problems."

  These are small textual changes but they shift the whole defensive posture
  from "we found that X" to "we explained why the field has been confused about
  X." The latter is much harder to attack.

  ---
  Want me to draft those §1 and §7 edits, or keep the conversation here a bit
  longer before touching the document?

✻ Brewed for 1m 26s