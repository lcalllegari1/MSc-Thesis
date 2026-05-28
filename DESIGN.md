# TSP ZKP — Design Log

This document records design decisions, alternatives considered, and rationale.
It is updated incrementally as the project evolves.

---

## Problem Statement

Prove in zero knowledge that a prover knows a Hamiltonian cycle on a complete
weighted graph G with total cost ≤ threshold T, without revealing which cycle.

**Public inputs:** cost matrix (or a commitment to it), threshold T  
**Private witness:** cycle (ordered sequence of n node indices)

---

## 1. Hamiltonian Path vs. Cycle

**Decision: Hamiltonian cycle** (n edges, returns to start node).

- Standard TSP formulation
- Path stored as [v₀, v₁, …, v_{n-1}]; the closing edge v_{n-1}→v₀ is implicit
- Cost = Σᵢ cost(vᵢ, v_{(i+1) mod n}) over n edges

Rejected: Hamiltonian path (n-1 edges). Simpler circuit but not standard TSP.

---

## 2. Cost Matrix Representation

Two variants will be benchmarked:

| Variant | Matrix representation | Circuit public inputs |
|---|---|---|
| **Flat-Full** | All n² edge costs passed as public inputs | n² field elements |
| **Flat-Merkle** | Merkle commitment; prover supplies per-edge proofs | 1 field element (root) |

**Starting point: Flat-Full** — simplest to implement, no hash alignment needed.
The Merkle variant is added as a second flat variant for comparison.

**Merkle hash choice:** Poseidon2 (`Poseidon2::hash([l, r], 2)` from the Noir poseidon library).
Poseidon2 is ZK-friendly (~264 gates per call vs ~28k for SHA-256).
Cross-validated between Rust (`bn254_blackbox_solver`) and Noir in `tests/hash_compat/`.

**Merkle root computation:** off-circuit in the Rust `pipeline/merkle_builder/` binary.
The binary reads a JSON payload (matrix + cycle) from stdin and writes Prover.toml
with all Merkle witnesses (edge_costs, siblings, path_bits, root).
Python only orchestrates; all Poseidon2 hashing is in Rust or Noir.

**Soundness design for flat_merkle_presence:**
  The circuit enforces two independent checks per edge in GROUP 3:
  (a) Leaf index check — path_bits must reconstruct to exactly cycle[i]*N+cycle[(i+1)%N].
      Without this, a prover could substitute a proof for a different leaf.
  (b) Merkle hash check — hashing edge_costs[i] through the siblings must equal root.
      Poseidon2 collision resistance prevents forging the hash chain.
  Together these bind each edge cost to the committed matrix entry.

**Why not leaf domain-separation (hash(leaf_idx, cost) as leaf):**
  With the explicit leaf index check, domain-separation is redundant.
  Removing it saves N Poseidon2 calls per proof and keeps the GROUP 3 cost
  model clean: exactly N*DEPTH hash calls, where DEPTH = ceil(log2(N^2)).

---

## 3. Permutation Check (proving all n nodes visited exactly once)

Multiple approaches will be benchmarked as sub-variants of the flat circuit:

| Variant | Approach | Constraint count |
|---|---|---|
| **Perm-Pairwise** | Check vᵢ ≠ vⱼ for all i≠j via modular inverse | O(N²) |
| **Perm-Sort** | Sort path, assert equals [0,…,N-1] | ~3N (N-1 ordering checks + ~2N ROM via check_shuffle) |
| **Perm-InvPerm** | Explicit inverse-permutation witness; N range checks + N ROM lookups | 2N; GROUP 1 subsumed |
| **Perm-Presence** | Mutable boolean mark array `seen`; assert `seen[cycle[i]] == false` then set true | ~4N (N init + N range + N RAM reads + N RAM writes); GROUP 1 explicit; no extra witness |

We start with Perm-Pairwise (simplest to write correctly), then add the others.
Having three variants directly shows how the permutation check dominates scaling.

---

## 4. ZKP Framework

**Decision: Noir + Barretenberg (UltraHonk backend)**

- nargo 1.0.0-beta.20 / bb 5.0.0-nightly.20260324
- Noir is a high-level DSL; circuits compile to ACIR then proven by bb
- UltraHonk supports lookup tables (efficient for dynamic array indexing)
- No trusted setup per circuit (universal SRS)

Rejected: arkworks (too low-level for a 3-6 month timeline starting from scratch).  
Rejected: Halo2 (API complexity not justified before needing native recursion).

---

## 5. Solver

**Decision: Nearest-neighbour + 2-opt (pure Python/numpy)**

Rationale: OR-Tools 9.15 removed `pywraprouting`; path quality is irrelevant
for ZKP benchmarking since we only need a *valid* cycle, not an optimal one.

---

## 6. Circuit Parameterization

Noir requires array sizes to be `comptime`. Each value of n needs a separate
compiled circuit. The benchmark harness loops: for each n → `nargo compile` →
run k instances → measure.

---

## 7. Benchmarking Plan

Metrics captured per (approach, n, run):
- Constraint count (from `bb gates`)
- Proving time (wall clock)
- Peak memory during proving (`/usr/bin/time -v`)
- Proof size (bytes)
- Verification time (wall clock)

Instance sizes: n ∈ {5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100}

---

## 8. Hierarchical Approach — Three Variants on a Privacy ↔ Cost Frontier

**Reframed 2026-05-26.** The original "find the crossover" framing was abandoned during
hierarchical planning when gate-count analysis showed there is no crossover to find:
the variants do not prove the same statement, so they cannot be compared on a single
cost axis. The implementation programme is now three hierarchical variants that span
the privacy / cost frontier, each the natural design for a distinct use-case class.

### Each variant proves a different statement

| Variant | Statement |
|---|---|
| flat_merkle | "∃ Hamiltonian cycle on N nodes, cost ≤ T, against committed root" |
| **A** — Merkle, sorted nodes public | "...that respects this disclosed partition" |
| **A++** — Merkle, grand product + in-circuit Fiat-Shamir | "...that decomposes into K segments with disclosed endpoints, segments themselves hidden" |
| **B** — flat_full, sub-matrix public | "...with disclosed M×M sub-matrices and disclosed partition" |

A and A++ keep the cost matrix private (committed via Merkle root). B exposes
per-segment sub-matrices. None of the three Pareto-dominates the others; each occupies
a distinct point on the (gates, parallelism, memory, privacy) frontier.

### Architecture common to all three variants

- **Sub-circuit + glue, independent proofs (not recursive).** Each variant produces K+1
  independent UltraHonk proofs. The verifier runs `bb verify` K+1 times and additionally
  checks that the public-input fields the proofs claim to share actually agree (same
  root, glue's `all_sorted_nodes` = concat of sub-proofs' `sorted_nodes`, etc.).
  Verifier-side cost is O(N) trivial equality, negligible.
- **K starts at 2 hardcoded** for the first end-to-end run; parameterised as
  compile-time global immediately after.
- **N divisible by lcm(K) under test.** Benchmarks use N ∈ {48, 96, 192, 480} for
  K ∈ {2, 4, 8}. N=480 is the comparison anchor against flat_merkle's N=500 (~4% off).
- **Glue shared between A and B**, with sort-based partition + K boundary Merkle proofs.
  A++ has its own glue with grand-product partition check.

### Sub-circuit interface (shared by A and B, extended by A++)

```
Public inputs:
  root          : Field
  sorted_nodes  : [u32; M]   // segment node set, sorted ascending (A and B)
  start_node    : u32
  end_node      : u32
  partial_cost  : u64
  -- A++ adds: (P_i, h_in_i, h_out_i, c, X) and removes sorted_nodes
```

### Glue interface (Variant A and B)

```
Public inputs:
  root                 : Field
  threshold            : u64
  all_sorted_nodes     : [u32; N]    // concat of K sub-proofs' sorted_nodes
  starts               : [u32; K]
  ends                 : [u32; K]
  partial_costs        : [u64; K]
Private witness:
  boundary_costs       : [u64; K]
  boundary_siblings    : [Field; K*DEPTH]
  boundary_path_bits   : [bool;  K*DEPTH]
```

A++'s glue replaces `all_sorted_nodes` with `(P_is[K], h_ins[K], h_outs[K], c, X,
expected_product)` and the sort-based partition check with the grand-product check.

### The structural reason no single variant universally dominates

Hierarchical decomposition adds a constraint in optimisation (good — search shrinks)
and weakens a constraint in ZK (bad — soundness must be restored by O(N) glue work).
The NP asymmetry between finding and checking holds, but the strategy that exploits it
in classical optimisation (trading verification overhead for search-space pruning)
does not transfer to ZK because there is no search to prune. Decomposition in ZK
becomes pure overhead unless it is used to disclose structure to the verifier (Variant
A, B) or to enable parallel work-sharing (all three) — neither of which is an
algorithmic improvement.

See `supervisor_report_draft.md` §7 for the full dualism argument and §7.7 for the
variant-to-use-case mapping.

### Benchmark interpretation (added 2026-05-27)

The Variant A full benchmark sweep completed. Two metrics require careful interpretation
before citing in the thesis.

**`prove_s` — single-machine contended, not isolated per-prover:**
`bb prove` is multi-threaded; K+1 concurrent processes each obtain ~1/(K+1) of available
threads. Observed prove_s > flat_merkle for all K at N=480 is expected and consistent
with the K× speedup being real under a distributed (dedicated-hardware) model. The K×
speedup is estimated from circuit_size ratios:
  sub_size ≈ flat_merkle_size / K  →  isolated prove_s ≈ flat_merkle_prove_s / K
This estimate is not yet directly measured. Pending: isolation benchmark (run one sub-
circuit without parallel siblings).

**`peak_mb` — per-prover maximum, not total concurrent RAM:**
`aggregate_hier.py` computes `peak_mb = max(float(r["peak_mb"]) for r in all_rows)`.
This is the single heaviest worker process peak, representing the minimum hardware
requirement for any one prover node. At N=480:

| K | Sub peak | Glue peak | Reported peak | Notes |
|---|---|---|---|---|
| 2 | ~551 MB | ~159 MB | ~551 MB | sub dominates |
| 4 | ~285 MB | ~159 MB | ~285 MB | sub dominates |
| 8 | ~152 MB | ~159 MB | ~159 MB | glue dominates |

**Glue memory floor:** the glue's G2 partition check sorts `all_sorted_nodes[N]` — N
elements regardless of K. This creates an O(N) memory floor (~159 MB at N=480) below
which the reported `peak_mb` cannot fall. At K≥8, the glue becomes the reported peak.
Variant A++ replaces O(N) sort with O(K) grand product; its glue memory should be
substantially lower and must be measured explicitly.

**Total single-machine concurrent RAM** = K×sub_peak + glue_peak, always exceeds
flat_merkle for all K (K=4, N=480: ~1299 MB vs ~1078 MB). The distributed memory
benefit (sub-circuit peak ≈ flat/K) requires one prover node per circuit.

Three mental models to keep distinct in the thesis:

| | prove_s | peak_mb |
|---|---|---|
| Single-machine contended (CSV) | > flat; contention overhead | max(K subs, glue); glue O(N) floor |
| Per-prover isolated (theoretical / pending) | ≈ flat/K | ≈ flat/K per sub; glue floor constant |
| Total system | ≈ flat (same work, distributed) | K×sub + glue; > flat |

---

## Progress

### Flat baseline (complete)

- [x] Instance generation (Python): `pipeline/instance_gen.py`
- [x] Visualization: `pipeline/visualize.py`
- [x] Solver (nearest-neighbour + 2-opt): `pipeline/solver.py`
- [x] Flat circuit — Flat-Full, Perm-Pairwise
- [x] Flat circuit — Flat-Full, Perm-Sort
- [x] Flat circuit — Flat-Full, Perm-InvPerm
- [x] Flat circuit — Flat-Full, Perm-Presence
- [x] Benchmarking harness: `pipeline/run.py`
- [x] Flat circuit — Flat-Merkle, Perm-Presence
- [x] Hash compatibility test: `tests/hash_compat/`
- [x] Git repo initialised
- [x] Thesis reframing (2026-05-23, sharpened 2026-05-26) + supervisor report updated

### Pending baseline housekeeping

- [ ] Benchmarks for flat_full_invperm and flat_full_presence to N=500
- [ ] Figures generated from `results/500.csv` via `analyze_complexity.py`

### Hierarchical implementation programme

- [x] Variant A — Merkle, sorted nodes public (2026-05-27)
    - [x] Sub-circuit `circuits/hierarchical_segment` (G1..G5)
    - [x] Glue circuit `circuits/hierarchical_glue` (G2..G4; G1 is structural-only)
    - [x] `pipeline/merkle_builder` extended with `--hierarchical K --out-dir`
    - [x] `pipeline/verify_hier.py` — K+1 `bb verify` + 4 cross-checks
    - [x] `pipeline/run_hier.py` — K-shadow parallel benchmark harness
    - [x] `tests/correctness/test_hierarchical_a.py` — 6 tests (1 valid + 4 negatives + 1 sanity at N=48 K=4)
    - [x] Full benchmark sweep into `results/hier_a.csv` (completed 2026-05-27; N∈{48,96,192,480}, K∈{2,4,8})
    - [ ] Isolation benchmark: run single sub-circuit without parallel siblings to empirically validate K× speedup claim
- [ ] Variant A++ — Merkle, grand product + in-circuit Fiat-Shamir
- [ ] Variant B — flat_full, sub-matrix public
- [ ] Frontier figure: (total gates, parallel wall-clock, per-prover memory, privacy bits) for all variants
- [ ] Integration with clustered TSP solver (B-side, partitioned routing) for combined-pipeline analysis

### Future / out of scope

- Folding-scheme variant (Nova/ProtoStar) — the natural continuation
- True recursive composition of K+1 proofs into one (verifier-side overhead reduction)
- Hash commitment for sorted node sets (alternative to A++ for partition hiding)
