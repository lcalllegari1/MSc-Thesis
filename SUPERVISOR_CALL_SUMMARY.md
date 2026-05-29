# Supervisor Call — Summary of Variants, Results & Design Justifications

*Prepared 2026-05-29. Numbers are from the committed CSVs in `results/`; anchor
size is **N=480** (compared against flat baseline at N=500, ~4% off).*

---

## 1. The one-sentence framing

> We do **not** prove the same statement four times and look for a crossover.
> Each variant proves a **different** statement and sits at a **different point**
> on a (privacy ↔ cost ↔ parallelism) frontier. The story is the *shape of that
> frontier*, not a single winner.

The structural reason there's no crossover: hierarchical decomposition **adds** a
constraint to optimisation (shrinks the search) but **weakens** a constraint in ZK
(soundness must be bought back by O(N) glue work). There is no search to prune in
ZK, so decomposition is pure overhead **unless** it is spent on (a) disclosing
structure to the verifier, or (b) parallel work-sharing. That's the dualism thread
that ties every result together.

---

## 2. What each variant proves & what it leaks

| Variant | Statement proven | Public surface | Partition privacy |
|---|---|---|---|
| **flat_merkle** (baseline) | ∃ Ham. cycle, cost ≤ T, vs committed `root` | `root, T` | Perfect — nothing leaks |
| **A** (Merkle, sorted nodes public) | …decomposed into K segments, **node sets disclosed** | `root, T`, per-seg `sorted_nodes[M]`, endpoints | None (partition public) |
| **A++** (Merkle, grand-product + in-circuit Fiat-Shamir) | …K segments, endpoints disclosed, **node sets hidden** | `root, T`, per-seg `P_i`, endpoints, chain anchors | **Computational** (P_i is a multiset oracle ~C(N,M); anchors an ordering oracle) |
| **Recursion** (in-circuit verify of K A++ proofs) | identical to A++ statement, **all intermediates hidden** | `root, T` only | **Perfect** — back to flat_merkle's surface |
| **B** (flat_full, sub-matrix public) | …with disclosed M×M sub-matrices | sub-matrices + partition | None (most disclosure) | *not yet implemented* |

**The arc to tell:** flat (perfect hiding, monolithic) → A (full disclosure, cheap
glue) → A++ (hide the node sets, pay a cheaper glue) → recursion (hide *everything*
again, pay a large aggregation tax). Recursion is the **perfect-hiding successor of
A++**, which is why the inner proof is deliberately the A++ segment (see §5).

---

## 3. Headline results (N=480)

### 3.1 Gate counts (circuit_size)

| | per-segment sub | glue | total (K subs + glue) |
|---|---|---|---|
| flat_merkle (N=500) | — | — | **782,837** (monolithic) |
| A, K=2 | 377,552 | 14,822 | 769,926 |
| A, K=4 | 189,422 | 17,934 | 775,622 |
| A, K=8 | 95,357 | 24,158 | 787,014 |
| A++, K=2 | 390,773 | **6,987** | 788,533 |
| A++, K=4 | 196,073 | **10,109** | 794,401 |
| A++, K=8 | 98,723 | **16,353** | 806,137 |
| **Recursion, K=2** | (inner ≈ A++ sub) | — | **2,256,796** |
| **Recursion, K=4** | | — | **3,796,121** |

- **Total work is conserved** across flat/A/A++ (~0.77–0.81 M gates) — decomposition
  doesn't reduce total work, it **redistributes** it (the dualism point made concrete).
- **Per-segment sub scales ~1/K** — this is the parallelism lever (377k → 95k as K: 2→8).
- **A++ glue is far cheaper than A's glue** (6,987 vs 14,822 at K=2): grand-product
  partition is **O(K)** vs A's sort-based partition **O(N)**.
- **A++ sub is ~+3.5% over A** (390k vs 377k) — the Fiat-Shamir / grand-product machinery
  in each segment. Net: A++ trades a tiny per-segment cost for a much cheaper glue **and**
  partition hiding.
- **Recursion costs ~K × 704k extra**: each in-circuit proof verification is **≈704,363
  gates and is essentially constant** (704,363 at N=8 *and* N=480 — see `recursion_micro_single.csv`).
  This is the "non-native field arithmetic" tax that dwarfs the actual TSP logic.

### 3.2 Prove time & per-prover memory (N=480, isolated/parallel view)

| | prove_s (per prover) | peak_mb (per prover) |
|---|---|---|
| flat_merkle (N=500) | ~12.0 | 1,078 |
| A, K=2 / K=4 / K=8 | 12.9 / 15.3 / 15.5 | 551 / 285 / 160 |
| A++, K=2 / K=4 / K=8 | 12.7 / 13.8 / 15.2 | 566 / 313 / 160 |
| Recursion, K=2 / K=4 | 26.1 / 45.3 | 2,069 / 4,125 |

- **Per-prover memory drops ~1/K** for A/A++ (551 → 160 MB) — the distributed-hardware
  benefit: one segment fits on a much smaller node than the monolithic 1,078 MB.
- **A++ glue memory is dramatically lower than A's**: 31 MB vs 159 MB at K=2. A's glue
  has an **O(N) memory floor** (~159 MB) because it sorts `all_sorted_nodes[N]`; A++'s
  O(K) grand product removes that floor. At K=8 A's glue (160 MB) becomes the reported peak.
- **Recursion is expensive**: the outer prover holds K in-circuit verifiers → ~2.1 GB (K=2),
  ~4.1 GB (K=4), and ~26–45 s. This is the price of perfect hiding via aggregation.

> ⚠️ **Caveat to state up front:** these `prove_s`/`peak_mb` are the **per-prover
> isolated** view (`*_par.csv`). On a single contended machine, K+1 concurrent provers
> share threads, so wall-clock is higher (`*_tot.csv`: A K=8 N=480 ≈ 128 s total). The
> K× speedup is the **distributed** (one-node-per-segment) model and is currently
> *estimated from circuit-size ratios* — a true isolation benchmark is still pending.

---

## 4. Design-choice justifications (per variant)

**flat_merkle baseline.** Merkle-commit the cost matrix (Poseidon2, ZK-friendly ~264
gates/call) so the public surface is just `root` — perfect hiding, the gold standard
the others are measured against. Permutation via `Perm-Presence` (mutable seen[]).

**Variant A — why disclose the node sets?** It's the *natural* design when the
use-case genuinely wants a disclosed partition (e.g. "prove each region was routed").
Cheapest to reason about; glue is a deterministic sort + K boundary Merkle proofs.
Its drawback (public node sets) is exactly what A++ removes.

**Variant A++ — why grand-product + in-circuit Fiat-Shamir?** To hide each segment's
node *set* while still proving the K segments form a genuine partition of {0..N-1}.
We check `∏ P_i == ∏ (X+j)` (Schwartz-Zippel) instead of sorting the union. Two wins:
(1) partition check is **O(K)** not O(N) → cheaper, lower-memory glue with no O(N)
floor; (2) **Fiat-Shamir challenge X is derived in-circuit** (Poseidon2 of the hash
chain), so the verifier does **no field arithmetic** — it only checks field equalities.
Privacy is now *computational* (P_i is a multiset oracle), not information-theoretic —
that's the honest limitation of the non-recursive architecture.

**Recursion — why, and why an A++ inner?** Recursion verifies the K segment proofs
*in-circuit*; their public inputs become **witness of the outer circuit**, so the
final verifier sees only `root, T` → **perfect hiding restored**. On choosing the inner:

- **Not for privacy** — recursion hides the partition regardless of inner choice, so
  "I used A++ because it hides" would be wrong.
- **(a) Controlled comparison:** using the *exact* A++ segment means the measured
  delta between the A++ row and the recursion row is **purely the aggregation cost**,
  no confounds.
- **(b) O(1) public surface:** the recursive verifier must absorb the inner's public
  inputs in-circuit, a cost linear in their count. A++ exposes **9 fields regardless of M**;
  an A inner would expose **M+4 = O(N/K)** (244 at N=480, K=2). A++ keeps the outer
  **segment-size-independent** — visible as the **flat ~704k-gate** per-verify cost.

We also built the **A-inner variant** to quantify this (`compare_inner.py`): at N=48,
K=2 the inner public-input count is **9 (A++) vs 28 (A)**, and the outer gate counts
are near-identical there (1,473,357 vs 1,475,164) — the O(M) penalty only opens up at
large N, exactly as argued.

---

## 5. Talking points / likely supervisor questions

- **"Did decomposition make anything cheaper?"** No — *total* gates are conserved
  (~0.78 M across flat/A/A++). What changes is *distribution*: per-prover gates and
  memory drop ~1/K. That's the whole point of the dualism argument.
- **"Is the K× speedup real?"** Real under a distributed model (one node per segment),
  estimated from circuit-size ratios. On one contended machine it's slower. **Honest
  gap: the isolation benchmark is still pending** — flag it as next step.
- **"What's A++ actually buying over A?"** Hidden node sets + an O(K) (vs O(N)) glue
  that removes the ~159 MB memory floor, at the cost of ~+3.5% per-segment gates and a
  downgrade from information-theoretic to computational partition hiding.
- **"Why is recursion 3× the gates?"** Each in-circuit proof verification is ~704k gates
  of non-native field arithmetic, ~constant in N, dominating everything; the TSP glue is
  noise against it. That's the cost of folding K proofs into one perfectly-hiding proof.
- **"Corollary worth saying out loud":** once segments become witness, A++'s Fiat-Shamir
  gadget is no longer needed *for hiding* — an A-style inner with a deterministic sort in
  the outer is arguably the *more natural* recursive design. We keep A++ for the
  controlled comparison and the O(1) surface. (Two routes to the same hidden partition.)

---

## 6. Status & honest gaps

- ✅ flat baseline, Variant A, Variant A++ — implemented, validated (correctness tests
  incl. negatives), full sweeps N∈{48,96,192,480}, K∈{2,4,8}.
- ✅ Recursion — implemented & benchmarked (micro + full), both A++-inner and A-inner.
- ⏳ **A++ full sweep** into `results/hier_fs.csv` exists; isolation benchmark for the
  K× claim is **pending**.
- ⬜ **Variant B** (sub-matrix public) — not yet implemented.
- ⬜ **Frontier figure** combining all variants on (total gates, parallel wall-clock,
  per-prover memory, privacy bits).
- 🔭 Folding (Nova/ProtoStar) — the natural continuation that would remove the ~704k×K
  recursive-verifier tax; out of scope for now.

*Source CSVs: `results/{500,hier_a,hier_a_par,hier_fs,hier_fs_par,recursion_full,
recursion_micro_single}.csv` and `results/recursion_inner_cmp/`.*
