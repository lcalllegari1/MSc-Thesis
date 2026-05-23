# TSP ZKP Project — Session Summary
## Last updated: 2026-05-23

---

## Research Question

**Reframed 2026-05-23.** Originally: *"at what N does hierarchical ZKP outperform flat?"* Gate-count analysis during hierarchical planning revealed this question pre-supposes a single dimension of "outperform" that does not exist in practice. Reframed to:

> How do hierarchical ZKP designs for TSP trade off **total cost, parallel proving time, per-prover memory, and verifier-side privacy** against the flat baseline, and what is the structural reason these axes do not collapse into a single crossover point?

The flat baseline characterisation (N≈175 crossover between flat_full and flat_merkle) stands unchanged. Hierarchical variants will be reported as points on a privacy / cost / parallelism frontier, not as competitors to be ranked on a single axis. See the new "Hierarchical Design — Conceptual Framework" section below for the structural argument (the optimisation-vs-ZK dualism) that motivated the reframing.

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

### Finding 8: The genuine hierarchical wins are parallel wall-clock and per-prover memory *(analytical, 2026-05-23)*

Although hierarchical Merkle does not reduce total gates, the K sub-proofs are independent. With K parallel workers, wall-clock proving time ≈ `proving_time(N/K) + glue` → roughly K-fold speedup. Per-prover peak memory ≈ `memory(N/K)` → ~K-fold reduction per process. At large N, single-machine memory exhaustion is the binding constraint and hierarchical becomes "the only feasible design" rather than "a faster design." This reframes hierarchical ZK from an optimisation strategy to a **scaling strategy**.

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

### Design decisions for sub-circuit + glue (all settled this session)

- **Real glue circuit** (Noir), not a Python verification script — end-to-end ZK story.
- **Public sorted node set**, not ordered cycle — preserves in-segment visit order privacy at no extra cost (sort-based permutation check produces sorted array as byproduct).
- **Boundary edges verified in glue**, not in sub-circuit — sub-circuit treats segment as a standalone instance; glue takes responsibility for stitching.
- **K=2 hardcoded first**, parameterise K as compile-time global afterward.
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

File at `/home/callexyz/Desktop/plsgod/supervisor_report_draft.md` (1295 lines). Complete plain-text structured report, **updated 2026-05-23 with thesis reframing**.

### 2026-05-23 updates

- **§1** — research question reframed from single crossover to multi-axis frontier; mentions the dualism upfront and points to §7
- **§6** — Findings 6–8 added (hierarchical Merkle no-gain in gates; flat_full saves gates by disclosing partition; parallelism/memory as real wins)
- **§7** — full rewrite. Title changed to "Cross-Domain Perspective: A Structural Dualism." Old version had the dualism backwards (claimed ZK decomposition "preserves exact soundness" and "stitching is O(k) and small" — both misleading). New version has six subsections:
  - 7.1 Optimisation: decomposition adds a constraint, shrinks search
  - 7.2 ZK proving: decomposition weakens a constraint, forces glue restoration
  - 7.3 Why the dualism exists (NP asymmetry + four corollaries)
  - 7.4 Implications for the experimental programme
  - 7.5 Folding schemes as a future direction
  - 7.6 Combined-pipeline synthesis with heuristic optimisation
- **§8** — two-variant implementation programme (Merkle + flat_full), frontier-mapping deliverable, folding schemes as future work

### Full section list

- §1 Overview and Research Question (reframed)
- §2 Problem Formulation (what we prove, public vs private, why threshold)
- §3 Design Choices:
  - 3.1 Proof system (Noir + UltraHonk justification)
  - 3.2 Circuit structure (four groups + type rationale)
  - 3.3 Matrix representation (flat-full vs flat-Merkle)
  - 3.4 Permutation strategies (table of 4 variants)
  - 3.5 Hash function (Poseidon2)
  - 3.6 Design alternatives considered and rejected
- §4 Flat-Merkle Variant: Implementation in Detail (4.1–4.6 including walk-throughs at N=4 and N=8)
- §5 Flat Circuit Benchmarks (5.1–5.5)
- §6 Key Findings (8 findings, expanded from 5)
- §7 Cross-Domain Perspective: A Structural Dualism (7.1–7.6, rewritten)
- §8 Next Steps (two-variant programme)

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
