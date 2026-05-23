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

## 8. Hierarchical Approach (future)

Deferred. Will be designed after the flat circuit is complete and benchmarked.
The expected design: split the n-node cycle into k segments of size s = n/k,
prove each segment independently, combine via a lightweight stitching circuit.
See top-level README for the crossover-point research question.

---

## Progress

- [x] Instance generation (Python): `pipeline/instance_gen.py`
- [x] Visualization: `pipeline/visualize.py`
- [x] Solver (nearest-neighbour + 2-opt): `pipeline/solver.py`
- [x] Flat circuit — Flat-Full, Perm-Pairwise
- [x] Flat circuit — Flat-Full, Perm-Sort
- [x] Flat circuit — Flat-Full, Perm-InvPerm
- [x] Flat circuit — Flat-Full, Perm-Presence
- [x] Benchmarking harness: `pipeline/run.py`
- [x] Flat circuit — Flat-Merkle, Perm-Presence
- [ ] Hierarchical circuit
