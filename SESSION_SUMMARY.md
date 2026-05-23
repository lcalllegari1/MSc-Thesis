# TSP ZKP Project — Session Summary
## Last updated: 2026-05-22

---

## Research Question

At what graph size N does a **hierarchical ZKP** approach (splitting the Hamiltonian cycle into sub-segments proved independently) outperform a **flat ZKP** approach? The project builds toward a crossover-point measurement.

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

## Supervisor Report: `supervisor_report_draft.md`

File exists at `/home/callexyz/Desktop/plsgod/supervisor_report_draft.md`. Complete plain-text structured report, sections:

- §1 Overview and Research Question
- §2 Problem Formulation (what we prove, public vs private, why threshold)
- §3 Design Choices:
  - 3.1 Proof system (Noir + UltraHonk justification)
  - 3.2 Circuit structure (four groups + type rationale)
  - 3.3 Matrix representation (flat-full vs flat-Merkle)
  - 3.4 Permutation strategies (table of 4 variants)
  - 3.5 Hash function (Poseidon2)
  - 3.6 Design alternatives considered and rejected (GROUP 1, GROUP 3 flat-full, GROUP 3 flat-Merkle, GROUP 4)
- §4 Flat-Merkle Variant: Implementation in Detail:
  - 4.1–4.4: overview, tree design, data pipeline, GROUP 3 Noir circuit
  - 4.5: Eight-node walk-through (N=8, DEPTH=6, full Prover.toml excerpt)
  - 4.6: Four-node walk-through (N=4, DEPTH=4, complete tree, full Prover.toml)
- §5 Flat Circuit Benchmarks (5.1–5.5)
- §6 Key Findings (5 named findings)
- §7 Cross-Domain Perspective (clustered TSP heuristics vs hierarchical ZKP)
- §8 Next Steps

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
supervisor_report_draft.md                      ✓ (complete, all 8 sections)
HOWTO.md                                        ✓
DESIGN.md                                       ✓
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
[ ] full permutation variant benchmarks (invperm, presence to N=500)
[ ] analyze_complexity.py figures generated from results/500.csv
[ ] Hierarchical circuit
```

---

## Next Steps (priority order)

1. **Run `analyze_complexity.py` on `results/500.csv`** to generate actual figures for the supervisor report. Use `--merkle-csv results/500.csv` flag.

2. **Benchmark flat_full_invperm and flat_full_presence to N=500** to complete the permutation overhead comparison and fill the missing entries in the supervisor report benchmarks section.

3. **Send supervisor_report_draft.md to supervisor** after figures are integrated.

4. **Implement hierarchical circuit** — the main remaining thesis work:
   - Decompose N-node problem into K sub-problems of size M=N/K
   - Each sub-tour proved independently; glue circuit connects sub-tours
   - Expected O(M²) per sub-prover + O(K) glue; for K=√N → O(N) total
   - Flat benchmarks give the per-sub-tour baseline for comparison

5. **Optional type optimization**: change `edge_costs: [u64; N]` → `[Field; N]` in flat_merkle_presence (~1% gate savings, safe because Merkle constrains range). Not urgent.

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
