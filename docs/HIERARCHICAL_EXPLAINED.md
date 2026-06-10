# Hierarchical TSP ZKP — Variants Explained

> **Reading note (2026-06-10).** The §-numbers in this doc are its **own internal**
> numbering, not thesis chapters. Where it cites thesis chapters it uses the old
> 12-chapter scheme — translate: old Ch 8 → new §5.1–5.4 · old Ch 9 → new §5.5–5.10 ·
> old Ch 10 → new Ch 6 (see `Thesis_Outline.md` §N). Any "projected" parallelism caveat
> is stale: the isolation sweeps landed (`ISOLATION_BENCHMARK.md` status banner).

**Self-contained reference for Variants plain-sort, plain-product, and B.**

This document consolidates the conceptual and structural understanding of the three
hierarchical variants developed in this thesis. It assumes familiarity with the flat
baseline (`flat_full_*` and `flat_merkle_presence` circuits) — see
`archive/supervisor_report_draft.md` §3–§5 for that material.

The intent is to be a reference: read straight through to understand all three
variants; jump to a section to look up a specific construction; use the worked
examples (N=8, K=2 for all three variants on the same cycle) to compare side by side.

---

## Table of contents

1. [Why hierarchical, and what stays the same](#1-why-hierarchical-and-what-stays-the-same)
2. [Shared architecture](#2-shared-architecture)
3. [The variant-as-statement reframe](#3-the-variant-as-statement-reframe)
4. [The optimisation-ZK dualism and NP asymmetry](#4-the-optimisation-zk-dualism-and-np-asymmetry)
5. [Commitment trust mechanisms](#5-commitment-trust-mechanisms)
6. [Threat models](#6-threat-models)
7. [Cryptographic building blocks: Schwartz-Zippel and Fiat-Shamir](#7-cryptographic-building-blocks-schwartz-zippel-and-fiat-shamir)
8. [plain-sort — Merkle, partition public](#8-variant-a--merkle-partition-public)
9. [plain-product — Merkle, grand product + in-circuit Fiat-Shamir](#9-variant-a--merkle-grand-product--in-circuit-fiat-shamir)
9b. [Variants committed-sort / committed-product — closing the partition leak](#9b-variants-committed-a--committed-a--closing-the-partition-leak)
10. [Variant B — flat-full, sub-matrices public](#10-variant-b--flat-full-sub-matrices-public)
11. [The proof workflow (applies to all variants)](#11-the-proof-workflow-applies-to-all-variants)
12. [Side-by-side comparison](#12-side-by-side-comparison)
13. [Use-case mapping](#13-use-case-mapping)
14. [Privacy analysis — quantitative bounds](#14-privacy-analysis--quantitative-bounds)
15. [Implementation considerations](#15-implementation-considerations)
16. [Common gotchas and security pitfalls](#16-common-gotchas-and-security-pitfalls)
17. [Glossary](#17-glossary)
18. [Related documents](#18-related-documents)

---

## 1. Why hierarchical, and what stays the same

In the flat baseline a single Noir circuit proves "I know a Hamiltonian cycle on N
nodes against this committed cost matrix with cost ≤ T." For large N the prover
must (a) hold the whole circuit in memory and (b) compute the whole proof on one
machine. Both are binding constraints around N ≈ 500–1000 in practice.

Hierarchical decomposition splits the proof:

- The cycle is partitioned into **K segments of M = N/K consecutive cycle positions**.
- Each segment is proved by an independent **sub-circuit**, in parallel.
- A small **glue circuit** stitches the K sub-proofs into one global statement.

This gives K-fold parallel speedup and ~K-fold per-prover memory reduction. It does
**not** reduce total gates — see `supervisor_report_draft.md` §7 for the structural
"dualism" argument explaining why. Hierarchical ZK is a **scaling strategy**, not an
algorithmic optimisation.

What stays the same across all hierarchical variants:

- The TSP statement (Hamiltonian cycle, total cost ≤ T)
- The cost matrix commitment (Poseidon2 Merkle root over the flat N² matrix)
- The Poseidon2 hash function
- The independent-proofs composition model (K+1 separate UltraHonk proofs, verifier
  cross-checks shared public-input fields)
- N divisibility discipline (N ∈ {48, 96, 192, 480} for K ∈ {2, 4, 8})
- The TSP solver (the cycle is found before any proving begins)

What changes between variants:

- **plain-sort**: simple Merkle baseline, segment partition publicly disclosed
- **plain-product**: same Merkle backbone, partition hidden via grand-product +
  in-circuit Fiat-Shamir
- **Variant B**: flat-full sub-circuits, segment sub-matrices publicly disclosed,
  cheaper gates but more privacy disclosure

---

## 2. Shared architecture

### 2.1 Independent proofs, not recursive composition

All three variants produce **K+1 independent UltraHonk proofs**: K sub-proofs (one per
segment) plus one glue proof. The proofs are bound together at the *verifier* layer,
not in-circuit:

- Each `bb verify` call confirms that *one* proof is internally consistent with the
  public inputs it declares.
- The verifier then runs **cross-checks** on the shared public-input fields across
  proofs — same `root`, glue's `starts`/`ends`/`partial_costs` match the corresponding
  sub-proof publications, etc.

Without the cross-checks, a malicious prover could produce K+1 individually-valid
proofs about K+1 different "universes" — same circuit shapes, different witnesses.
The cross-checks pin down a single coherent statement.

The alternative — recursive verification (the glue circuit verifying the K sub-proofs
inside the circuit) — is deferred to future work alongside folding schemes.

### 2.2 Roles of the sub-circuit and the glue

The sub-circuit, in all variants, proves the same kind of local fact:

> "I know a Hamiltonian *path* of M nodes from `start_node` to `end_node`, with the
> M-1 internal edges bound to the cost matrix in some variant-specific way, with the
> sum of those costs equal to `partial_cost`."

The glue, in all variants, proves the same kind of stitching fact:

> "The K paths fit together into a Hamiltonian cycle: the K boundary edges connect
> the segment endpoints (bound to the cost matrix via Merkle), and the K segment
> node sets partition {0..N-1} (checked in some variant-specific way), and the total
> cost is ≤ T."

plain-sort and Variant B share the **same glue circuit**: sort-based partition check
on K·M = N concatenated node values, K boundary Merkle proofs, sum-threshold check.
plain-product has its own glue (`hierarchical_glue_fs`) with a grand-product partition
check instead of sort.

### 2.3 N divisibility discipline

Benchmarks use N ∈ {48, 96, 192, 480} so all values of K under test (2, 4, 8) yield
integer M. N=480 is the comparison anchor against the existing flat_merkle benchmark
at N=500 (~4% mismatch).

### 2.4 K starts at 2 hardcoded for correctness, then parameterised

Initial implementation hardcodes K=2 for the first working end-to-end run; immediately
after, K becomes a compile-time global. Benchmarks then sweep K ∈ {2, 4, 8}.

### 2.5 Where node-distinctness is enforced — "segment binds, glue enforces"

A natural question: **what stops a prover from putting a duplicate node inside a
segment** (e.g. `cycle_segment = [3, 3, 5, 7]`)? The answer is the single most
important structural decision shared by every hierarchical variant, so it is stated
here once as a principle rather than re-derived per variant.

**Duplicates are *allowed* at the segment level and *refused* globally in the glue.**
This is deliberate and is the only correct place to enforce the constraint, because
"each node is visited exactly once" is **inherently global**: a segment sees only its
own M nodes, so no per-segment check can ever rule out node 3 appearing in segment 0
*and* in segment 1. The work is therefore split as:

- **Segment binds.** The sub-circuit's only obligation is to *truthfully* tie its
  public summary to its actual private nodes — so the glue operates on honest data. In
  plain-sort this is `sort(cycle_segment) == sorted_nodes`
  (`hierarchical_segment` G2); in plain-product it is the grand product
  `∏ⱼ (X + cycle_segment[j]) == P_i` (`hierarchical_segment_fs` G6). Without this
  binding a prover could declare a clean summary while secretly proving a
  duplicate-containing internal path — so the binding is **not optional**, even though
  the *enforcement* lives elsewhere.
- **Glue enforces.** Exactly one global check catches every duplicate — whether
  intra-segment or cross-segment — because any repeat means some value of `{0..N-1}` is
  necessarily missing from the N node slots:
  - plain-sort / B: `sort(all_sorted_nodes) == [0..N-1]` (the sort-based partition,
    `hierarchical_glue` G2, §8.4.G2).
  - plain-product: `∏ᵢ Pᵢ == ∏_{j=0..N-1}(X + j)` (the grand-product multiset equality,
    `hierarchical_glue_fs` G5, §9.1 / §7).

**Why not also check distinctness inside the segment?** Because it is *redundant*. A
per-segment strict-ascending / uniqueness check is necessary-but-not-sufficient (it
cannot see cross-segment overlap), so you would *still* need the global check, and the
global check already subsumes it. Adding it spends `K·(M−1)` comparison gates that
catch nothing new — which is exactly why plain-sort's sub-circuit deliberately **omits**
the strict-ascending check (§8.2.G2).

**Which global mechanism is best.** Both global checks are correct; they sit at
different points on the privacy/cost frontier:

| Mechanism | Public surface / segment | Partition privacy | Glue cost (N=480, K=4) | Soundness |
|---|---|---|---|---|
| Sort (plain-sort/B) | O(M) — the whole `sorted_nodes` | **disclosed** (verifier sees every node set) | ~21k gates (O(N) in-circuit sort) | unconditional |
| Grand product (plain-product) | O(1) — one Field `Pᵢ` | **hidden** (partition never revealed) | ~6.9k gates (~N cheap field mults) | Schwartz–Zippel, error ≤ N/2²⁵⁴ |

The **grand product (plain-product) is the preferred construction** whenever privacy and a small
public surface matter — which is this thesis's direction — dominating the sort on
public-input size, partition privacy, *and* glue gate count. Its only costs are the
Fiat-Shamir plumbing (the chain terminal `c` → challenge `X = Poseidon2([c])`,
`hierarchical_glue_fs` G1–G4) and a *probabilistic* soundness error. The sort is
simpler and unconditional, so it remains the right **baseline / disclosed** rung.

**Load-bearing caveat (plain-product).** The grand-product argument is sound only if `X` is
unforgeable *before* the prover commits the `Pᵢ` — otherwise the prover could grind a
fake partition whose products happen to match at a known `X` (§7.3). That is the entire
purpose of binding `X` to the full-cycle chain terminal `c` (§7.5, sub G7 + glue G4).
When auditing "refuse in the glue," this Fiat-Shamir binding is the assumption the whole
global check rests on.

---

## 3. The variant-as-statement reframe

A central conceptual point: the three hierarchical variants do **not** prove the
same statement as flat_merkle. They prove strictly more specific statements, with
additional structure exposed to the verifier.

| Variant | Statement proved |
|---|---|
| flat_merkle | "∃ Hamiltonian cycle on N nodes with cost ≤ T against the matrix committed by `root`." |
| **A** | "...that **respects the disclosed partition** (segment_0, …, segment_{K-1}) and visits each segment in cycle order start_i → … → end_i with internal cost sum partial_cost_i." |
| **plain-product** | "...that **decomposes into K segments of M nodes with disclosed endpoints (start_i, end_i) and disclosed per-segment cost sums partial_cost_i**, the segments themselves bound by the disclosed Field-valued aggregates (P_i, h_in_i, h_out_i)." |
| **B** | "...with `root` for boundary edges and **disclosed M×M sub-matrices** for internal edges, that respects the disclosed partition and segment endpoints with disclosed per-segment cost sums." |

The privacy loss in each variant is **not a bug to be minimised; it is the content of
the statement being proved**. Variants proving different statements cannot be totally
ordered on cost — which is why the original "crossover" framing was a category error.

---

## 4. The optimisation-ZK dualism and NP asymmetry

This is the central conceptual finding of the thesis: hierarchical decomposition is
a strict win in classical optimisation but at best neutral in zero-knowledge proving,
and this asymmetry has a structural explanation tied to how the NP asymmetry between
finding and checking responds to decomposition.

### 4.1 The dualism stated

> Hierarchical decomposition **adds** a structural constraint in optimisation and
> **weakens** a soundness constraint in zero-knowledge proving. Same operation,
> opposite direction in constraint space, opposite effect on cost.

### 4.2 Optimisation: decomposition shrinks the search space

In classical TSP heuristics, splitting an N-node tour into K clusters of M = N/K
nodes each imposes "the tour respects this partition." This added constraint shrinks
the search space from N! permutations to roughly K · (M!) · K! permutations — the K
intra-cluster orderings plus the K! orderings of cluster representatives — a
super-polynomial reduction.

The trade-off is approximation error: tours violating the partition are excluded, so
the best partition-respecting tour may be worse than the unconstrained optimum. For
optimisation this trade is a strict win: reducing exponential search by accepting
polynomial approximation error is almost always worthwhile.

### 4.3 ZK proving: decomposition weakens a constraint, forcing glue restoration

In zero-knowledge proving, splitting the N-node Hamiltonian-cycle proof into K
segment proofs weakens "every node visited exactly once globally" into K local
checks "every node visited exactly once within this segment."

The weakened form is **unsound**: a cheating prover could place node v in two
segments and pass every local check. The global property is no longer enforced.
Restoration requires one of three things:

- Disclosing the partition publicly (plain-sort), so the verifier can check it directly
- A grand-product check at a random challenge X (plain-product), costing O(K) but
  requiring the additional Fiat-Shamir machinery
- Disclosing per-segment sub-matrices (Variant B), so the verifier knows the
  partition by inference from the cost data

Whichever path is taken, the restoration cost cancels the per-segment saving:
hierarchical Merkle (plain-sort) has the same total gate count as flat Merkle plus a small
overhead, with the K boundary Merkle proofs and the O(N) partition check in the
glue exactly absorbing the per-segment savings. See `supervisor_report_draft.md` §7
Finding 6 for the gate-count algebra.

### 4.4 NP asymmetry under decomposition

The standard NP asymmetry — finding is exponentially hard, checking is polynomial
— holds in both classical and ZK settings. What is **not** preserved is the way
each side responds to decomposition:

> Hierarchical decomposition exploits NP asymmetry by trading verification work for
> a dramatic reduction in search work. In classical optimisation this trade is a
> strict win, because reducing exponential search by a polynomial verification
> overhead is always worth it. In ZK proving, the trade has nothing to redeem on the
> search side — the prover already has the witness — so the verification overhead
> is paid without any compensating saving. The asymmetry persists; the strategy
> that exploits it does not transfer.

This is **not** a violation of NP asymmetry. Verification remains polynomial-time
(often sublinear or constant for ZK verification). What fails is that *hierarchical
decomposition*, a particular technique built atop NP asymmetry, does not transfer
to ZK for problems with non-local constraints.

### 4.5 Algorithmic vs embarrassingly-parallel speedup

This is one of the most important practical distinctions in the thesis, and the
source of considerable confusion when ZK practitioners discuss "scaling":

- Classical hierarchical TSP gives **algorithmic** speedup: total work decreases
  super-polynomially as K grows. The search space genuinely shrinks; even a single
  processor benefits.
- Hierarchical ZK gives only **embarrassingly-parallel** speedup: total work stays
  roughly constant (Finding 6), but it can be distributed across K machines.

These are different things. Conflating them leads to overclaims like "ZK rollups
scale better with recursion" (true for locally-factoring problems) being misapplied
to graph problems where the constraint structure breaks the decomposition. The wins
of hierarchical ZK for TSP are real (memory, wall-clock under parallel proving),
but they are **scaling-strategy** wins, not algorithmic wins.

### 4.6 Corollaries

Several useful corollaries follow from the dualism:

- **Approximation has no ZK analogue.** Heuristic optimisation can trade quality
  for speed because a near-optimal tour is still useful. ZK has no equivalent — a
  partially verified cycle is no proof at all. Hierarchical's quality/speed
  trade-off does not port to ZK.

- **Constraints have flipped sign across the two domains.** Adding a constraint in
  optimisation makes the problem cheaper (smaller search). Adding a constraint in
  ZK makes the proof more expensive (more assertions). The word "constraint"
  denotes opposing economic forces in the two contexts.

- **Hierarchical ZK works well only for locally-factoring problems.** Circuit-SAT
  factors locally (each gate is independently checkable), and recursive proof
  systems (Halo, Nova, ProtoStar) work well over circuit-SAT because the global
  property *is* the conjunction of local properties. Hamiltonian-cycle is the
  opposite extreme — "visit every node exactly once" is intrinsically global and
  refuses to factor. TSP is a worst-case problem class for hierarchical ZK.

- **The ZK verifier cannot iteratively assist the prover.** Optimisation's
  guess-and-check dynamic, where the checker accepts/rejects with useful feedback,
  has no ZK analogue — the verifier is single-shot.

### 4.7 A predictive heuristic for proof-system design

Given a new problem class, before reaching for hierarchical or recursive ZK, ask:
*does this problem factor locally?*

- If **yes**: hierarchical/recursive ZK is a good fit; folding schemes will pay off.
  Examples: state-transition proofs, batched arithmetic, ZK rollups.
- If **no**: hierarchical ZK is at best a scaling strategy (memory, wall-clock) and
  never an algorithmic improvement; the search-side wins of classical decomposition
  will not appear. Examples: TSP, k-clique, graph colouring, Hamiltonian-cycle.

This heuristic explains why ZK rollups (locally-factoring state transitions) benefit
massively from recursive composition while ZK graph-routing applications (non-local
Hamiltonian-cycle constraint) do not.

---

## 5. Commitment trust mechanisms

Throughout this document, the Merkle root committing to the cost matrix is
referenced as a public input. But a Merkle commitment is only meaningful if
anchored to a real-world fact the prover cannot retroactively change. Without an
external trust anchor, the prover commits to whatever fictitious matrix makes their
proof trivial. This section enumerates the standard trust anchors and how they
apply to the variants.

### 5.1 The general principle

A practical ZK deployment consists of two layers:

- **Cryptographic layer**: the proof certifies a statement about a committed input
  (the matrix).
- **Trust layer**: an external mechanism binds the committed input to reality.

The proof system handles the first layer rigorously. The trust layer is
application-specific and is **not** automatically provided by the proof system.
Omitting it is the most common practical attack on ZK applications: the prover
commits to a self-serving matrix and proves trivially against it.

### 5.2 The five standard trust mechanisms

| Mechanism | How it binds the commitment | Concrete example |
|---|---|---|
| **Authority signature** | A trusted third party (regulator, certifier, auditor) signs the root | A logistics regulator certifies the operator's quarterly cost matrix; the signed root is the binding artifact, and SLA proofs work against it throughout the quarter. |
| **Trusted oracle** | A neutral data provider publishes signed roots over reference data | A city data provider publishes a signed Merkle root of pairwise travel times monthly; any party proves route properties against the oracle's data. |
| **Cross-attestation** | Multiple stakeholders co-commit | Two organisations sharing a logistics network sign the joint root; either can prove their leg meets agreed bounds without revealing the network to outsiders. |
| **Public timestamping** | The root is anchored to an append-only public ledger before any proofs are produced | The operator publishes the root to a blockchain or transparency log at time T₀; proofs produced later are bound to that pre-committed matrix. |
| **Decommitment-on-dispute** | The matrix is opened to a court/arbitrator if a dispute arises | The root is the binding artifact in ordinary operation; the underlying matrix is disclosed only under legal process. |

### 5.3 Two regimes, two different jobs for the commitment

The role of the Merkle commitment differs by the prover/verifier threat model:

**Matrix-private regime** (verifier holds only the root):
- The commitment provides **privacy**: verifier cannot read matrix entries.
- The commitment provides **integrity**: prover is bound to one matrix across all proofs against this root.
- The external trust anchor binds the committed matrix to a real-world fact.
- Applies to Variants plain-sort, plain-product, and to flat_merkle.

**Matrix-public regime** (verifier knows the matrix independently):
- The commitment provides **integrity only**: verifier hashes their own copy of the matrix and confirms it matches the root declared in the proof.
- Privacy is no longer a function of the commitment (matrix is already known).
- The external trust anchor still matters for cross-party agreement on which matrix is "the" matrix.
- Applies to Variant B and to any variant deployed in a public-data context.

### 5.4 Commonly-overlooked failure modes

- **Self-signed roots with no external anchor.** The prover signs their own root
  and supplies the signature. This is effectively no trust anchor — the prover can
  sign whatever they like.
- **Roots committed after proofs are produced.** Temporal ordering matters: the
  root must be fixed *before* proofs against it are accepted. Otherwise the prover
  can pick a root after seeing what they need to prove.
- **No mechanism to detect changing the matrix between commitments.** Applications
  requiring multiple commitments over time (e.g., quarterly matrices) need
  temporal binding (timestamping, signed dates) — otherwise the prover can swap
  matrices retroactively.

### 5.5 What this thesis assumes

This thesis takes no specific position on which trust mechanism to use — that is an
application-level choice. The proof designs are agnostic to the trust mechanism.
What the thesis assumes is that *some* mechanism is in place; the commitment is
treated as a binding artifact, and the soundness arguments are made relative to
that assumption.

---

## 6. Threat models

This section makes the security assumptions of each variant explicit. ZK proofs
make sense only relative to a defined threat model; the bullet points here are the
assumptions implicit in every "this is sound" claim throughout the document.

### 6.1 Adversary capabilities — the cheating-prover model

The standard ZK threat model is a **malicious prover** with polynomial-time
computation, attempting to convince a verifier of a false statement.

The prover may:
- Choose any witness (private inputs).
- Compute anything the proof system allows in polynomial time.
- Have access to all public information including the cost matrix root, the proof
  system parameters, and previously published proofs.

The prover may **not**:
- Break Poseidon2 (preimage resistance, collision resistance).
- Solve the discrete logarithm problem (UltraHonk's underlying security assumption).
- Distinguish Poseidon2 outputs from uniformly random field elements in the random
  oracle sense (relevant for plain-product).

The **verifier is honest**: they follow the protocol correctly. They may be curious
— they will learn whatever the public inputs reveal — but they do not deviate from
the verification procedure.

### 6.2 What the proof system guarantees

For all variants, UltraHonk + the circuit constraints guarantee:

- **Completeness**: an honest prover with a valid witness produces a proof that
  always verifies.
- **Knowledge soundness**: a successful verification implies the prover knows a
  witness satisfying the circuit constraints, except with cryptographically
  negligible probability. For plain-sort and B this is unconditional (modulo Merkle /
  Plookup soundness assumptions). For plain-product this includes the Fiat-Shamir /
  Schwartz-Zippel error of ~N / 2²⁵⁴.
- **Zero-knowledge**: the verifier learns nothing about the private witness beyond
  what is implied by the public inputs.

### 6.3 What the proof system does NOT guarantee

These limitations are properties of *any* ZK system, not specific to this thesis.
Listing them explicitly avoids overclaiming:

- **Input validity.** The proof system does not verify that the committed cost
  matrix corresponds to a real-world fact. The external trust anchor (§5) handles
  this.
- **Cycle uniqueness.** The proof shows a cycle exists, not that it is unique.
  The prover may know multiple cycles meeting the threshold; the proof identifies
  none of them.
- **Optimality.** The proof shows cost ≤ T, not that no cheaper cycle exists.
  Proving optimality would require universally quantifying over all N! cycles —
  not expressible as a standard SNARK statement.
- **Freshness.** The proof system does not bind to a particular time. Replay
  attacks require external mitigation (nonces, signed timestamps, etc.).
- **Side channels and metadata leakage.** Timing, memory access patterns, network
  metadata. These are out of scope but acknowledged.

### 6.4 Per-variant threat model nuances

**plain-sort** — unconditional soundness given Poseidon2 + Plookup correctness. The
cheating-prover model captures all relevant attacks. Verifier sees the partition
by design; this is a privacy property, not a soundness property.

**plain-product** — soundness is in the **random oracle model** (Fiat-Shamir
assumes Poseidon2 behaves as a random oracle). The soundness error is bounded by
~N / 2²⁵⁴ from Schwartz-Zippel at the unforgeable challenge X. Reduction to
standard assumptions (collision resistance, preimage resistance) is the same as
for any Fiat-Shamir-transformed protocol.

**Variant B** — soundness is **conditional on the matrix-public assumption**: the
verifier must independently know the cost matrix and check that each sub_matrix
matches the corresponding slice. Without this check, B's sub-circuits accept
arbitrary sub-matrices. The "matrix-public" assumption is therefore load-bearing
for soundness, not just for the use case framing.

### 6.5 The verifier's responsibilities

The verifier's role is more involved in hierarchical proofs than in flat proofs.
Concretely:

| Step | All variants | plain-product only | B only |
|---|---|---|---|
| Run `bb verify` on each proof | K+1 calls | K+1 calls | K+1 calls |
| Compute `expected_product` | — | O(N) field mults | — |
| Hash own matrix copy and check root | — | — | Required |
| Check sub_matrix against own matrix | — | — | O(K · M²) |
| Cross-check shared public inputs | O(N) equalities | O(N) equalities | O(N) equalities |

In all cases the verifier work is **far less** than running a single sub-prover.
Verifier complexity remains polylogarithmic in N for the `bb verify` portion, with
O(N) or O(N²/K) native-code post-processing for the variant-specific checks.

### 6.6 Honest-verifier zero-knowledge — the formal property

UltraHonk's zero-knowledge property is *honest-verifier zero-knowledge*: a
simulator can produce indistinguishable transcripts for any valid public input
without knowing the witness. This is the cryptographic guarantee. What the public
inputs reveal is a *design choice* mapped per variant in §§8.7, 9.11, 10.8 and
§14.

---

## 7. Cryptographic building blocks: Schwartz-Zippel and Fiat-Shamir

plain-product uses two cryptographic constructions that the other variants do not:
the Schwartz-Zippel lemma (for multiset equality at a random evaluation point) and
the Fiat-Shamir transform (for binding the evaluation point to a prior commitment).
This section explains both from scratch. Readers comfortable with these can skip
to §9.

### 7.1 The grand product as a multiset commitment

For a multiset S = {s_1, ..., s_M} of field elements, define:

```
P_S(X) = ∏_{i=1..M} (X + s_i)
```

This is a polynomial in X of degree M. Its roots are exactly -s_1, ..., -s_M
(counted with multiplicity), so the polynomial uniquely determines the multiset
and vice versa.

**Key property:** Two multisets S and T are equal iff `P_S(X) = P_T(X)` as
polynomials (all coefficients equal).

### 7.2 The Schwartz-Zippel lemma

Comparing polynomials symbolically is expensive (it requires expanding them
fully). The Schwartz-Zippel lemma gives a probabilistic alternative.

> **Schwartz-Zippel:** Let P be a non-zero polynomial of degree at most d in n
> variables over a field 𝔽 of size q. If r is sampled uniformly from 𝔽^n, then
> `Pr[P(r) = 0] ≤ d / q`.

For our single-variable case: if P and Q are distinct polynomials of degree at
most d in X, and X is sampled uniformly from 𝔽 of size q, then:

```
Pr[ P(X) = Q(X)  |  P ≠ Q ]  ≤  d / q
```

For Noir's BN254 field with q ≈ 2²⁵⁴ and our degree d = N, the soundness error is
~N / 2²⁵⁴ — negligible.

**This is the load-bearing reduction in plain-product.** Instead of checking polynomial
equality (which would require N field multiplications inside the circuit to
expand the polynomials), the verifier checks equality at a single random point X.
If the polynomials are distinct, the check fails with overwhelming probability.

### 7.3 The trap with predictable X

The Schwartz-Zippel guarantee depends on X being sampled **after** the prover
commits to the polynomials. If X is fixed beforehand, the attack is feasible:

**Concrete attack scenario** (against plain-product with imaginary fixed X):
- The prover wants to use a fake partition (e.g., put node 3 in two segments and
  omit node 7).
- The honest `expected_product` at, say, X = 5, N = 8 is:
  ```
  expected_product = (5+0)(5+1)(5+2)(5+3)(5+4)(5+5)(5+6)(5+7)
                   = 5·6·7·8·9·10·11·12 = 19,958,400
  ```
- The prover searches for a fake partition whose grand products multiply to this
  exact value. Since `expected_product` is a fixed integer (or field element),
  this is a factoring-like problem over the chosen field.
- Over a 254-bit field with many possible segment values, this admits many
  solutions; the prover finds one in polynomial time and wins.

**Conclusion:** X must be sampled *after* the prover's commitment is fixed.

### 7.4 The Fiat-Shamir transform — interactive to non-interactive

In the interactive version of an plain-product-style protocol:

```
PROVER                                  VERIFIER
 1. Commit to cycle (send c)             
 ─────────────────────────────────────►  
                                          2. Sample random X ∈ 𝔽
                                          
 ◄─────────────────────────────────────  
 3. Produce ZK proofs at this X          
 ─────────────────────────────────────►  
                                          4. Verify proofs + grand-product check
```

The middle round is the key: the prover commits to the cycle *before* learning
X. The Fiat-Shamir transform replaces step 2 with:

```
X = H(c)
```

where H is a hash function modelled as a random oracle. The prover does both
sides; the verifier replays the same hash computation to recover X.

**Why this preserves soundness:** by the random oracle assumption, H(c) is
indistinguishable from uniformly random given any c the prover did not pre-commit
to. The prover cannot grind X without grinding c, and c is committed to a fixed
cycle (next subsection).

### 7.5 The chain construction in plain-product

The "commitment" in plain-product is the cycle itself, captured via a Poseidon2 hash chain:

```
h_0     = 0
h_{j+1} = Poseidon2(h_j, cycle[j])     for j = 0..N-1
c       = h_N                          // commitment to the cycle in cycle order
X       = Poseidon2(c)                 // challenge derived from commitment
```

**Why a chain, not a single hash of the cycle?** Because the cycle is split across
K sub-circuits. Each sub-circuit only sees its own segment. A chain naturally
distributes the commitment work across sub-circuits: each sub-circuit folds M
values into the chain (M Poseidon2 calls) and exports `h_in`/`h_out` to be
stitched by the glue.

**Why over the cycle in cycle order, not over sorted segment multisets?** Two
reasons:

- The boundary edges depend on cycle order, not just multiset. The chain in cycle
  order binds *all* cycle positions, including the start/end of each segment.
- Per-segment work distribution is natural for cycle-order chaining; each segment
  owns M consecutive cycle positions.

**Why doesn't the chain leak the cycle?** Because c is a Poseidon2 output and
Poseidon2 is preimage-resistant. The verifier sees c (a 254-bit field element)
but cannot invert it to recover the cycle. Intermediate chain values h_i are
similarly Poseidon2 outputs — preimage-resistant.

### 7.6 Putting it together — the plain-product soundness picture

plain-product's soundness relies on the conjunction of:

- **Hash chain correctness**: each sub-circuit computes h_out = chain(h_in,
  segment) honestly. Enforced by sub-circuit G5.
- **Chain stitching**: the K chain pieces fit together into one continuous
  evaluation. Enforced by glue G1-G3.
- **Challenge derivation**: X = Poseidon2(c) consistently across all proofs.
  Enforced by sub-circuits' G7 + glue's G4.
- **Per-segment grand product correctness**: each P_i = ∏(X + cycle_segment[j])
  honestly. Enforced by sub-circuit G6.
- **Global grand-product equality**: ∏ P_i = expected_product. Enforced by glue
  G5 with verifier-supplied/checked expected_product.

A cheating prover faces a circular trap:

- To get a favourable X, they would need to control c.
- To control c, they would need to find a chain preimage.
- Poseidon2 is preimage-resistant: this is infeasible.
- The prover can only induce X by selecting a cycle, and X is then determined.
- For the chosen cycle, the multiset is fixed; the grand-product equality holds
  iff the multiset partitions {0..N-1} (with soundness error N / 2²⁵⁴).

This is the same pattern used inside recursive SNARKs (outer circuit derives
challenges from inner-proof commitments via Fiat-Shamir). plain-product applies it at the
application level rather than recursively, avoiding the per-recursion
verifier-circuit overhead.

---

## 8. plain-sort — Merkle, partition public

This section is the canonical reference for plain-sort. It explains each variable
(what it is, why it exists, and why it is public or private), each constraint
group (what it checks and what it protects against, with concrete
counterexamples), and walks through the protocol end-to-end on a small example.

### 8.1 Sub-circuit `hierarchical_segment` — variables explained

**Compile-time globals.** The sub-circuit needs three globals; it does *not*
need `K`, because a sub-circuit only knows about its own segment.

| Global | Why it must exist |
|---|---|
| `N: u32` | Total nodes in the TSP instance. Required for the Merkle leaf-index calculation `from*N + to` in G4 and for the range bound in G1. |
| `M: u32` | Segment size = N/K. Sets the array sizes for `cycle_segment`, `sorted_nodes`, `edge_costs`. |
| `DEPTH: u32` | `⌈log₂(N²)⌉`. Length of each Merkle proof's sibling and path-bit array. Depends only on N (single global tree over the N² matrix). |

Consequence for the compile schedule: one sub-circuit compile per `(N, M, DEPTH)`
tuple, not per `(N, K, M, DEPTH)`. The harness can reuse the same sub-circuit
binary for all values of K that share `M = N/K`.

**Public inputs.** These are what the verifier sees, and they jointly define
what plain-sort discloses.

| Var | Type | Role | Why public |
|---|---|---|---|
| `root` | `Field` | Poseidon2 Merkle root of the N² cost matrix. G4's hash chains target it. | Binds the proof to the committed matrix (anchored externally — §5). All K+1 proofs must declare the same root; the verifier's first cross-check is this equality. |
| `sorted_nodes` | `[u32; M]` | The segment's node set, strictly ascending. | The glue's partition check operates on the concatenation of all K segments' `sorted_nodes`. Publishing sorted (rather than cycle-order) preserves in-segment visit-order privacy at zero extra cost — the verifier learns *which* nodes are in this segment but not *in what order* they were visited. |
| `start_node` | `u32` | The first node in cycle order, `cycle_segment[0]`. | The glue computes boundary edges as `ends[i] → starts[(i+1) % K]`. Both endpoints must be visible to the glue. Also part of plain-sort's intentional disclosure: the verifier sees the K start/end pairs. |
| `end_node` | `u32` | The last node in cycle order, `cycle_segment[M-1]`. | Symmetric to `start_node`. |
| `partial_cost` | `u64` | Sum of the M-1 internal edge costs in this segment. | The glue's threshold check sums `Σ partial_costs + Σ boundary_costs ≤ T`. Without the sub-circuit publishing its aggregate, the glue would have to re-verify all internal edges, defeating the decomposition. Per-segment cost is also an accountability artifact in plain-sort's natural use cases (multi-team SLA, regional ESG reporting). |

**Private witness.** These are what the prover holds; they are what ZK protects.

| Var | Type | Role | Why private |
|---|---|---|---|
| `cycle_segment` | `[u32; M]` | The segment's nodes in actual visit order. | Hiding the visit order is plain-sort's privacy guarantee. If `cycle_segment` were public, plain-sort would leak `(M-2)!` extra orderings per segment — i.e., it would expose the full cycle, defeating the purpose. |
| `edge_costs` | `[u64; M-1]` | `edge_costs[i] = cost_matrix[cycle_segment[i]][cycle_segment[i+1]]` for each internal edge. | Per-edge costs reveal cost-matrix structure (commercially sensitive in logistics, competitive in routing). Only the aggregate `partial_cost` is published. The values must be in the witness so G4 can hash them up the Merkle tree. |
| `siblings` | `[Field; (M-1)·DEPTH]` | Merkle siblings for each internal-edge proof, flat row-major. | Pure proof scaffolding — not part of the statement. Making them public would massively bloat the public-input pool without serving any verification purpose. |
| `path_bits` | `[bool; (M-1)·DEPTH]` | LSB-first leaf-index encoding for each internal-edge proof: `leaf_idx = Σ path_bits[d]·2^d`. | The leaf index `from*N + to` directly encodes which cycle edge is being looked up — making it public would expose the cycle order. Keeping `path_bits` private + the in-circuit leaf-index reconstruction in G4 (a) binds them to the correct leaf without revealing the leaf index to the verifier and (b) blocks the proof-substitution attack (see G4 below). |

### 8.2 Sub-circuit constraint groups (five) — with counterexamples

Each group is described as: *what it checks*, *what it protects against*, and
*a concrete attack that succeeds without it*.

#### G1 — Range: `cycle_segment[i] < N`

**Checks.** Every node in the segment is a valid node index in `[0, N)`.

**Protects against.** Out-of-range indices that (a) overflow `u32` in
`from*N + to` at large N (at N=500, `from*500` overflows once `from ≥ 2³²/500 ≈
8.6M`) or (b) point into the padded zero zone of the Merkle tree.

**Counterexample.** At N=8, prover supplies `cycle_segment = [9999, 9998, 9997,
9996]`, `sorted_nodes = [9996, 9997, 9998, 9999]` (strictly ascending → G2
passes; G3 endpoint check passes if `start_node = 9999`, `end_node = 9996`). G4
would compute `expected_idx = 9999·8 + 9998 = 79990`. The leaf-index check
catches this in the end (`path_bits` length 6 reconstructs to ≤ 63), but only
after expensive Merkle hashing. At large N, the u32 multiplication overflow
makes G1 genuinely necessary rather than just defense-in-depth.

#### G2 — Permutation: `sort(cycle_segment) == sorted_nodes`

**Checks.** `sorted_nodes` is exactly the sorted multiset of `cycle_segment`
(via Noir's `sort_via` producing a non-decreasing output, then per-element
equality).

**Protects against.** Prover decoupling what they actually visited
(`cycle_segment`) from what they publish (`sorted_nodes`).

**Counterexample (multiset mismatch).** Real visit order is `[0, 5, 3, 2]`, but
the prover publishes `sorted_nodes = [1, 4, 6, 7]` to pretend this is some
other segment. `sort([0,5,3,2]) = [0,2,3,5] ≠ [1,4,6,7]` → rejected.

**Note: no strict-ascending check is needed.** A naive design would also
assert `sorted_nodes[i+1] > sorted_nodes[i]` to enforce distinctness within
the segment. But that check is **redundant** given the glue's G2: if a
segment had a duplicate (e.g., `cycle_segment = [3, 3, 5, 7]`), then
`sorted_nodes` would also have that duplicate (`[3, 3, 5, 7]`), the
concatenation `all_sorted_nodes` would contain it, and the glue's
`sort(all_sorted_nodes) == [0..N-1]` would fail (3 appears twice → ≠
`[0..N-1]`). Per-segment distinctness is enforced **transitively** by global
partition + the sort-equality binding here. Dropping the strict-ascending
check saves M-1 comparison gates per sub-circuit at zero soundness cost.

#### G3 — Endpoints: `start_node == cycle_segment[0]`, `end_node == cycle_segment[M-1]`

**Checks.** The published endpoints match the actual segment endpoints in cycle
order.

**Protects against.** Prover lying about endpoints so the glue computes boundary
edges that connect to fake nodes.

**Counterexample.** Real segment is `[0, 5, 3, 2]`. Prover wants the boundary
out of this segment to be `4 → 7` because `cost(4,7)` is cheaper than
`cost(2,7)`. Without G3, the prover publishes `end_node = 4` (a node not even
in this segment); the glue happily Merkle-verifies `cost(4,7)` against the real
root and accepts a cycle that doesn't exist. G3 forces `end_node =
cycle_segment[3] = 2` → rejected.

#### G4 — Internal Merkle (per internal edge i in 0..M-2)

**Checks.** Two things per edge:
- **Leaf-index reconstruction.** `path_bits[i*DEPTH..(i+1)*DEPTH]` decode
  LSB-first to exactly `cycle_segment[i] * N + cycle_segment[i+1]`.
- **Hash chain to root.** Starting from `edge_costs[i]` cast to `Field`, the
  prover walks up DEPTH levels using siblings and path-bits; the final hash
  equals `root`.

**Protects against.** Two distinct attacks.

**(a) Forging cost out of nothing.** Counterexample: prover supplies
`edge_costs[0] = 1` with garbage siblings. The hash chain reaches a Field
value ≠ root with overwhelming probability by Poseidon2 collision resistance →
rejected.

**(b) Proof substitution for a cheaper leaf.** Counterexample at N=8: real
`cost[0][5] = 10`, but `cost[7][1] = 2`. Prover claims edge 0→5 has cost 2 and
supplies the *genuine* Merkle proof for leaf `7·8+1 = 57` (value 2 is really
there). Without the leaf-index check, the hash chain reaches root → accepted.
The leaf-index check forces `path_bits` to reconstruct to `0·8+5 = 5`, but the
path_bits for leaf 57 reconstruct to 57. 57 ≠ 5 → rejected.

The leaf-index check is the load-bearing soundness check in G4. Without it,
the Merkle proof attests "this value is *somewhere* in the tree" rather than
"this value is at *the right place*."

#### G5 — Cost binding: `sum(edge_costs) == partial_cost`

**Checks.** The published per-segment cost is exactly the sum of the M-1
internal edge costs.

**Protects against.** Prover under-reporting per-segment cost so the global
threshold sum (in the glue) appears smaller than the true cost.

**Counterexample.** Real internal costs `[10, 12, 8]` sum to 30. Prover
publishes `partial_cost = 20` to fit comfortably under threshold. G5 forces
`20 == 30` → rejected.

### 8.3 Glue circuit `hierarchical_glue` — variables explained

**Compile-time globals.** The glue knows all four — N, K, M, DEPTH — because
it handles K-element arrays.

**Public inputs.**

| Var | Type | Role | Why public |
|---|---|---|---|
| `root` | `Field` | Same as in sub-circuits. | Verifier cross-checks all K+1 proofs declare the same root. |
| `threshold` | `u64` | Public upper bound T on total cycle cost. | The headline claim of the proof. |
| `all_sorted_nodes` | `[u32; N]` | Concatenation of the K sub-proofs' `sorted_nodes` arrays. **Note:** not yet globally sorted — K locally-sorted chunks juxtaposed. | The glue sorts in-circuit (G2) and asserts the result equals `[0..N-1]` (partition check). The verifier cross-checks each chunk equals the corresponding sub-proof's `sorted_nodes`. |
| `starts` | `[u32; K]` | The K segment-start nodes in segment order. | Boundary edges `ends[i] → starts[(i+1)%K]` use these. Cross-checked against each sub-proof's `start_node`. |
| `ends` | `[u32; K]` | The K segment-end nodes. | Same; "from" side of each boundary. |
| `partial_costs` | `[u64; K]` | Per-segment cost aggregates from the K sub-proofs. | Glue G4 sums them with `boundary_costs` to check against `threshold`. Cross-checked against each sub-proof's `partial_cost`. |

**Private witness.**

| Var | Type | Role | Why private |
|---|---|---|---|
| `boundary_costs` | `[u64; K]` | The K stitching-edge costs. | Same justification as `edge_costs` — per-edge values are sensitive; only the threshold sum needs them. |
| `boundary_siblings` | `[Field; K·DEPTH]` | Merkle siblings for the K boundary-edge proofs. | Proof scaffolding. |
| `boundary_path_bits` | `[bool; K·DEPTH]` | LSB-first leaf-index encoding for boundary-edge proofs. | The encoded index `ends[i]*N + starts[(i+1)%K]` is technically derivable from public `starts`/`ends`, so this is "private for consistency" rather than "private because secret." Treating it as witness keeps the boundary-edge proof shape identical to the internal-edge proofs. |

### 8.4 Glue constraint groups (four) — with counterexamples

#### G1 — Structural: boundary edges defined as `ends[i] → starts[(i+1) % K]`

No constraint emitted; this is just the indexing convention used by G3 and G4.
The wrap-around at `i = K-1` closes the cycle.

#### G2 — Partition: `sort(all_sorted_nodes) == [0, 1, ..., N-1]`

**Checks.** The K segments' node sets exactly partition `{0..N-1}` — no node
in two segments, no node missing.

**Protects against.** (a) Two segments overlapping on a node; (b) a node never
being visited.

**Counterexample (overlap).** Real partition should be `{0,2,3,5} | {1,4,6,7}`.
Cheating prover puts node 3 in both segments and omits node 4: sub_0 publishes
`sorted_nodes = [0,2,3,5]`, sub_1 publishes `[1,3,6,7]`. Each sub-proof is
internally valid (each is a 4-node Hamiltonian path on distinct nodes —
sub-circuit G2 passes per segment). The glue's `all_sorted_nodes =
[0,2,3,5,1,3,6,7]`. Sort = `[0,1,2,3,3,5,6,7] ≠ [0..7]` → G2 rejects.

This is the load-bearing **global**-distinctness check. The sub-circuit's G2
only enforces distinctness within one segment; only the glue G2 enforces it
across segments. Without the glue G2, K individually-valid sub-proofs about K
non-disjoint segments would pass.

#### G3 — Boundary Merkle (per boundary i in 0..K-1)

Same construction as sub-circuit G4 (leaf-index reconstruction + Poseidon2
hash chain to root), applied to the K boundary edges `ends[i] →
starts[(i+1)%K]`. Protects against forged boundary costs (Poseidon2 collision
resistance) and proof substitution for cheaper boundary edges (leaf-index
check). Same two counterexamples as sub-circuit G4.

#### G4 — Threshold: `Σ partial_costs + Σ boundary_costs ≤ threshold`

**Checks.** The full cycle's total cost is at most T.

**Protects against.** Accepting a too-expensive cycle. The fundamental cost
statement of the proof.

**Counterexample.** True cycle cost is 110, threshold is 100. Even with every
other check passing (each partial_cost honest by G5; each boundary_cost honest
by G3), the sum 110 > 100 → rejected.

### 8.5 Verifier cross-checks (after `bb verify` succeeds on all K+1 proofs)

`bb verify` alone confirms each proof is internally consistent with its
declared public inputs. The cross-checks bind the K+1 *separate* proofs into a
single coherent statement.

- All K+1 proofs declare the same `root`.
- `glue.all_sorted_nodes[i*M..(i+1)*M] == sub_proof_i.sorted_nodes` for each i.
- `glue.starts[i] == sub_proof_i.start_node`; same for `ends` and
  `partial_costs`.

Without these cross-checks, a malicious prover could produce K+1
individually-valid proofs about K+1 different "universes" — same circuit
shapes, different segment data. See §16 for a fuller treatment of this
pitfall.

### 8.6 Soundness chain

1. **Internal edge costs bound to root.** Each sub-circuit's G4 forces edge
   costs to be the committed-matrix values via Poseidon2 collision resistance
   + the leaf-index check (same argument as `flat_merkle_presence`).
2. **`partial_cost` bound to internal edges.** G5 in each sub-circuit.
3. **Each segment is internally a Hamiltonian path on M distinct nodes.**
   Sub-circuit G1 + G2 + G3.
4. **Sub-proofs and glue refer to the same instance.** Verifier cross-checks
   ensure `partial_costs[i] == sub_proof_i.partial_cost`, etc.
5. **Partition is exact.** Glue G2: sort of K·M concatenated values equals
   `[0..N-1]` — unique up to multiset equality.
6. **Boundary edges bound to root.** Glue G3.
7. **Total cost is bounded.** Glue G4.

Together these say: there exists a Hamiltonian cycle on N nodes (K paths + K
stitching edges = N edges; partition is a permutation of {0..N-1}) with all N
edge costs bound to the committed cost matrix and total cost ≤ T.

### 8.7 Privacy

Verifier learns:
- **Partition** (which nodes ∈ which segment, exactly)
- K endpoints (start, end of each segment)
- K per-segment cost sums

Verifier does **not** learn:
- Interior visit order within each segment (the `(M-2)!` orderings hidden per
  segment)
- Individual edge costs (only sums)
- Boundary edge costs (only their contribution to the threshold sum)
- Any cost matrix entries beyond what those aggregates constrain

### 8.8 End-to-end protocol flow — small worked example at N=6, K=2, M=3

Small enough to do by hand. M=3 means 2 internal edges per segment and 2
boundary edges total = 6 edges in the cycle (correct for an N=6 Hamiltonian
cycle).

**Setup.**
- N=6, K=2, M=3, threshold T=60. Merkle tree: 36 leaves padded to 64, DEPTH=6.
- Solver-produced cycle: `0 → 3 → 5 → 1 → 4 → 2 → 0`. Total cost 53 ≤ 60 ✓.
- Relevant cost-matrix entries: `cost[0][3]=8`, `cost[3][5]=6`, `cost[5][1]=12`,
  `cost[1][4]=7`, `cost[4][2]=9`, `cost[2][0]=11`.

**Phase 1 — Solve (prover, native).** Nearest-neighbour + 2-opt on the 6×6
matrix produces `cycle = [0, 3, 5, 1, 4, 2]` with cost 53.

**Phase 2 — Build Merkle tree (prover, native; cacheable per matrix).** Flatten
the 6×6 matrix to 36 u64 leaves, pad to 64 with zeros, build the Poseidon2 tree
bottom-up. Output: a single Field root R.

**Phase 3 — Split cycle into K segments (prover, native).** Segment 0 =
`cycle[0..3] = [0, 3, 5]`. Segment 1 = `cycle[3..6] = [1, 4, 2]`. Boundary edges
(derived from segment endpoints): `5 → 1` between segments (cost 12) and
`2 → 0` wrap-around (cost 11).

**Phase 4 — Emit K+1 Prover.toml files (prover, native — Rust merkle_builder
extension).**

*`sub_0/Prover.toml`:*
- Private: `cycle_segment = [0,3,5]`; `edge_costs = [8, 6]` for edges 0→3
  (leaf 0·6+3 = 3) and 3→5 (leaf 3·6+5 = 23); 12 siblings + 12 path_bits.
- Public: `sorted_nodes = [0,3,5]`, `start_node = 0`, `end_node = 5`,
  `partial_cost = 14`, `root = R`.

*`sub_1/Prover.toml`:*
- Private: `cycle_segment = [1,4,2]`; `edge_costs = [7, 9]` for edges 1→4
  (leaf 10) and 4→2 (leaf 26); 12 siblings + 12 path_bits.
- Public: `sorted_nodes = [1,2,4]`, `start_node = 1`, `end_node = 2`,
  `partial_cost = 16`, `root = R`.

*`glue/Prover.toml`:*
- Private: `boundary_costs = [12, 11]` for edges 5→1 (leaf 31) and 2→0
  (leaf 12); 12 siblings + 12 path_bits.
- Public: `root = R`, `threshold = 60`, `all_sorted_nodes = [0,3,5,1,2,4]`
  *(concatenation — not yet globally sorted)*, `starts = [0,1]`,
  `ends = [5,2]`, `partial_costs = [14,16]`.

**Phase 5 — Witness generation (prover, K+1-way parallel).** `nargo execute`
on each circuit produces three `.gz` witness files.

**Phase 6 — Proof generation (prover, K+1-way parallel).** `bb prove` on each
witness produces three 14,656-byte proofs plus their `public_inputs` dumps.
Total ~44 KB delivered to the verifier.

**Phase 7 — Verification.**

*7.1 — Internal verification via `bb verify` × 3.* Each proof is internally
consistent with its declared public inputs.

Inside `glue` (verified by `bb verify`):
- G2 Partition: `sort([0,3,5,1,2,4]) = [0,1,2,3,4,5]` = `[0..5]` ✓
- G3 Boundary Merkle: leaves 31 (value 12) and 12 (value 11) hash to R ✓
- G4 Threshold: `14+16+12+11 = 53 ≤ 60` ✓

Inside each sub-circuit (verified by `bb verify`):
- G1 Range, G2 Permutation+ascending, G3 Endpoints, G4 Internal Merkle, G5
  Cost binding all hold under the supplied witness.

*7.2 — Cross-checks (`pipeline/verify_hier.py`).* The script reads each
proof's `public_inputs` dump and compares:

| Check | Values | Pass? |
|---|---|---|
| Same `root` across all three proofs | R == R == R | ✓ |
| `glue.all_sorted_nodes[0..3] == sub_0.sorted_nodes` | `[0,3,5] == [0,3,5]` | ✓ |
| `glue.all_sorted_nodes[3..6] == sub_1.sorted_nodes` | `[1,2,4] == [1,2,4]` | ✓ |
| `glue.starts == [sub_0.start_node, sub_1.start_node]` | `[0,1] == [0,1]` | ✓ |
| `glue.ends == [sub_0.end_node, sub_1.end_node]` | `[5,2] == [5,2]` | ✓ |
| `glue.partial_costs == [sub_0.partial_cost, sub_1.partial_cost]` | `[14,16] == [14,16]` | ✓ |

All cross-checks pass → **verifier accepts.**

The verifier has learned the partition `{0,3,5} | {1,2,4}`, the endpoints
`(0,5)` and `(1,2)`, the per-segment costs 14 and 16, and that the proven
cycle satisfies the threshold T=60. They have *not* learned the interior visit
order (here degenerate because M=3 has only one interior position; at M ≥ 4
the `(M-2)!` interior orderings are genuinely hidden), individual edge costs,
boundary edge costs, or any other cost matrix entries.

### 8.9 Worked example: N = 8, K = 2, M = 4, DEPTH = 6 (illustrates privacy)

A larger worked example, focused on what the verifier can deduce about the
cycle.

Cycle 0 → 5 → 3 → 2 → 7 → 4 → 1 → 6 → 0, costs (10, 12, 8, 15, 11, 9, 14, 13),
total 92, threshold 100. Boundary edges are 2→7 (cost 15) and 6→0 (cost 13).

**Sub-circuit 0:** `cycle_segment=[0,5,3,2]`, `sorted_nodes=[0,2,3,5]`,
`start=0`, `end=2`, `partial_cost=30`. G4 verifies three Merkle proofs at
leaves 5, 43, 26 with values 10, 12, 8.

**Sub-circuit 1:** `cycle_segment=[7,4,1,6]`, `sorted_nodes=[1,4,6,7]`,
`start=7`, `end=6`, `partial_cost=34`. G4 verifies three Merkle proofs at
leaves 60, 33, 14 with values 11, 9, 14.

**Glue:** `all_sorted_nodes=[0,2,3,5,1,4,6,7]`, `starts=[0,7]`, `ends=[2,6]`,
`partial_costs=[30,34]`, `boundary_costs=[15,13]`. G2 sorts to `[0..7]` ✓.
G3 verifies boundary Merkle proofs at leaves 23 (value 15) and 48 (value 13).
G4: `30+34+15+13 = 92 ≤ 100` ✓.

**Verifier candidate count.** The verifier knows the partition exactly and
knows each segment goes from a specific start to a specific end. The interior
of each segment is some ordering of M-2 = 2 nodes: 2! = 2 orderings per
segment, (2!)² = **4 candidate cycles** out of (N-1)! = 5040. Bits leaked
≈ log₂(5040/4) ≈ 10.3.

---

## 9. plain-product — Merkle, grand product + in-circuit Fiat-Shamir

plain-product achieves the same parallelism and per-prover memory benefits as plain-sort but **hides the
partition**. The mechanism is a multiset-equality argument via grand product
combined with an in-circuit Fiat-Shamir construction.

### 9.1 The mathematical trick — grand product as a multiset commitment

For a multiset S = {s_1, ..., s_M} of Field elements, the polynomial

```
P_S(X) = ∏_{i=1..M} (X + s_i)
```

uniquely identifies S as a multiset (its roots are exactly -s_i with multiplicity).

By Schwartz-Zippel, if S ≠ T as multisets, then for X sampled uniformly from a field
of size q ≈ 2²⁵⁴, `Pr[P_S(X) = P_T(X)] ≤ M / q` — negligible.

**Using this for partition checking.** The K segments partition `{0..N-1}` iff their
multiset union equals `{0..N-1}`. Equivalently:

```
∏_{i=0..K-1} P_{S_i}(X) = ∏_{j=0..N-1} (X + j)         (as polynomials)
```

Each sub-circuit publishes `P_i = ∏(X + cycle_segment_i[j])` as a single Field
element. The glue checks that the product of K Field elements equals
`expected_product = ∏(X + j)` (verifier-supplied, verifier-checked).

### 9.2 Why X must be unpredictable to the prover

If X is fixed before the prover chooses segments, they can search for fake
partitions whose products multiply to `expected_product` at that specific X. Soundness
requires X to be sampled **after** the prover commits.

### 9.3 The in-circuit Fiat-Shamir construction

The "commitment" is the cycle itself, captured via a Poseidon2 hash chain:

```
h_0     = 0
h_{j+1} = Poseidon2(h_j, cycle[j])     for j = 0..N-1
c       = h_N                          // commitment to the cycle in cycle order
X       = Poseidon2(c)                 // challenge
```

The chain is split across sub-circuits: each sub-circuit i takes `h_in_i` as input
(the chain value at the start of its segment), folds its M segment values in cycle
order, and outputs `h_out_i` (the chain value at the end of its segment).

The glue stitches:
- `h_ins[0] == 0` (chain init)
- `h_ins[i+1] == h_outs[i]` (chain continuity)
- `h_outs[K-1] == c` (chain terminal)

Once these are enforced, c is the unique chain value of the unique cycle the prover
claims to know, and X = Poseidon2(c) is unforgeably derived from c. The prover
cannot grind X without committing to a different cycle.

### 9.4 Why chain over cycle order, not over segment multisets

Two reasons:

1. **Boundary edge binding.** The boundary edges (`ends[i] → starts[(i+1) % K]`)
   depend on cycle order, not just multiset. Chaining over the cycle binds all cycle
   positions, including the start/end of each segment.
2. **Per-segment work distribution.** Each segment owns M consecutive cycle positions
   and can do its own M Poseidon2 calls in parallel.

The chain in cycle order does **not** leak the cycle: c is a Poseidon2 image; the
chain values h_i are intermediate Poseidon2 outputs; all preimage-resistant.

### 9.5 Sub-circuit interface

```
Public inputs:
  root:          Field
  start_node:    u32
  end_node:      u32
  partial_cost:  u64
  P_i:           Field          // grand product ∏(X + cycle_segment[j])
  h_in_i:        Field          // chain value at segment start
  h_out_i:       Field          // chain value at segment end
  c:             Field          // full-cycle chain terminal
  X:             Field          // Fiat-Shamir challenge

Private witness:
  cycle_segment: [u32; M]
  edge_costs:    [u64; M-1]
  siblings:      [Field; (M-1)*DEPTH]
  path_bits:     [bool;  (M-1)*DEPTH]
```

The change from plain-sort: `sorted_nodes[M]` is gone; in its place are five Field elements
`(P_i, h_in_i, h_out_i, c, X)`. Public-input pool shrinks from O(M) to O(1).

### 9.6 Sub-circuit constraint groups (seven)

- **G1 Range.** `cycle_segment[i] < N`.
- **G2 Endpoints.** `start_node == cycle_segment[0]`, `end_node == cycle_segment[M-1]`.
- **G3 Internal Merkle.** Same as plain-sort's G4.
- **G4 Cost binding.** `sum(edge_costs) == partial_cost`.
- **G5 Hash chain link.** Fold cycle_segment values through Poseidon2 starting from
  `h_in_i`; assert result equals `h_out_i`. M Poseidon2 calls.
- **G6 Grand product.** Compute `∏(X + cycle_segment[j])` step by step in-circuit;
  assert result equals `P_i`. M field multiplications.
- **G7 Challenge consistency.** `X == Poseidon2(c)`. One Poseidon2 call.

(No sort-based permutation check; the grand product handles it globally.)

### 9.7 Glue interface

```
Public inputs:
  root:              Field
  threshold:         u64
  starts:            [u32; K]
  ends:              [u32; K]
  partial_costs:     [u64; K]
  P_is:              [Field; K]
  h_ins:             [Field; K]
  h_outs:            [Field; K]
  c:                 Field
  X:                 Field
  expected_product:  Field         // verifier-supplied and independently checked

Private witness:
  boundary_costs:        [u64; K]
  boundary_siblings:     [Field; K*DEPTH]
  boundary_path_bits:    [bool;  K*DEPTH]
```

### 9.8 Glue constraint groups (seven)

- **G1 Chain init.** `h_ins[0] == 0`.
- **G2 Chain stitching.** `h_ins[i+1] == h_outs[i]` for i = 0..K-2.
- **G3 Chain terminal.** `h_outs[K-1] == c`.
- **G4 Challenge consistency.** `X == Poseidon2(c)`. One Poseidon2 call.
- **G5 Grand-product partition.** `∏ P_is == expected_product`. K-1 multiplications.
- **G6 Boundary Merkle.** Same as plain-sort's glue G3.
- **G7 Threshold.** Same as plain-sort's glue G4.

### 9.9 The role of `expected_product`

There are two sound ways to enforce the RHS of the partition check
`∏ P_i == ∏_{j=0..N-1}(X + j)`:

- **Option A (verifier-supplied).** `expected_product` is a public input to the
  glue; the verifier independently computes `∏(X + j)` for j = 0..N-1 (O(N) native
  multiplications) and confirms it matches the declared value. This shifts the O(N)
  work to the cheap verifier side but makes the verifier carry a non-optional
  cryptographic obligation (it *must* recompute, or soundness is lost).

- **Option B (in-circuit) — AS BUILT.** The glue computes `∏(X + j)` itself in a
  `for j in 0..N` loop (G5 RHS); there is **no** `expected_product` public input.
  Cost is ~N cheap field multiplications in-circuit (~N gates), still far below plain-sort's
  O(N) sort. The verifier then does *no field arithmetic at all* — every soundness
  claim is a circuit constraint, and the verifier's cross-checks are pure
  Field-equality bookkeeping.

**The implementation (`circuits/hierarchical_glue_fs`, `pipeline/verify_hier_fs.py`,
2026-05-28) uses Option B** — see `HIER_FS_IMPL.md` D5. The interface in §9.7 and
the soundness link in §9.10 below are written for Option A; under the as-built
Option B, drop the `expected_product` public input and read "verifier-supplied/
checked expected_product" as "in-circuit `∏(X+j)` loop". Both are sound; Option B
gives the cleaner thesis story ("the verifier has no cryptographic obligation").

### 9.10 Soundness chain — eight links

1. **Edge costs bound to root.** Internal edges via sub-circuit G3, boundary edges
   via glue G6 — both via Poseidon2 collision resistance + leaf-index check.
2. **Each P_i faithful to its private cycle_segment.** Sub-circuit G6 forces the
   product computation step by step.
3. **Each hash chain piece faithful to its cycle_segment.** Sub-circuit G5.
4. **Chain stitches into one continuous evaluation over the global cycle.** Glue G1,
   G2, G3 force c = chain over the full cycle in cycle order. Poseidon2 collision
   resistance: distinct cycles produce distinct c with overwhelming probability.
5. **X unforgeably bound to c.** Glue G4 + sub-circuits' G7. Poseidon2 is one-way:
   the prover cannot find c' ≠ c with Poseidon2(c') = X.
6. **Grand-product equality forces partition exactness.** Glue G5 +
   verifier-supplied/checked expected_product. By Schwartz-Zippel at the
   unforgeable random-looking X, ∏ P_i = ∏(X+j) for j=0..N-1 iff the multiset
   union of segments equals `{0..N-1}` (except with probability N / 2²⁵⁴).
7. **Cycle closes via boundary edges.** Partition exactness + glue G6 imply the K
   boundary edges connect distinct nodes (no segment overlap).
8. **Total cost bounded.** Glue G7.

### 9.11 Privacy

Verifier learns directly: K endpoints; K per-segment cost sums; Field-valued
aggregates (P_i, h_in_i, h_out_i, c, X). Verifier does **not** learn directly: the
partition; interior order within each segment; individual edge costs; boundary edge
costs.

**Important caveat — plain-product hides the partition *computationally*, not
information-theoretically.** An earlier framing claimed the Field aggregates "leak no
information about the witness." That is too strong. Two of the public aggregates are
not one-way under plain-product's threat model — they are *confirmation oracles* that let a
verifier who is willing to do bounded search recover exactly the data plain-sort publishes for
free. The hiding is real, but it rests on the search being infeasible, i.e. on a work
factor, not on missing information.

**Oracle 1 — `P_i` reveals the segment multiset (work ≈ C(N, M)).** The grand product
`P_i = ∏_{j}(X + cycle_segment_i[j])` is a *polynomial evaluation at a public point X*,
not a one-way hash. Because the partition constraint forces each segment to be a
size-M subset of the public set {0..N-1}, a verifier can enumerate candidate subsets
`S ⊆ {0..N-1}, |S| = M`, compute `∏_{v∈S}(X + v)`, and accept the unique `S` whose
product equals `P_i`. That recovers the segment's node multiset — precisely what
plain-sort discloses as `sorted_nodes`. The cost is ≈ C(N, M) field multiplications per
segment (a meet-in-the-middle subset-product attack can do better, but C(N, M) is the
naive ceiling).

**Oracle 2 — the chain anchors reveal interior order (work ≈ (M-2)!).** Both ends of
each segment's hash chain are public: `h_in_i`, `h_out_i`, and the endpoints
`start_i = cycle[i·M]`, `end_i = cycle[(i+1)·M − 1]`. The chain step
`h_{j+1} = Poseidon2(h_j, cycle[j])` takes only public-domain inputs (h-values that are
now known, plus node indices in [0, N)). So once Oracle 1 has fixed the segment's
multiset, the verifier brute-forces the (M-2)! interior orderings, recomputes the chain
from `h_in_i`, and accepts the unique ordering that reproduces `h_out_i`. The published
anchors turn an information-theoretic ambiguity into a checkable guess.

`c` and `X` add nothing further: `c` is the terminal of the same chain, and `X =
Poseidon2(c)` is deterministic from it. The privacy-relevant leakage is fully captured
by Oracles 1 and 2.

**Why the anchors must be public — the price of non-recursion.** `h_in_i` / `h_out_i`
are public *because* plain-product is K+1 independent proofs bound by off-circuit verifier
cross-checks (§2.1). The verifier can only confirm chain continuity
(`h_ins[i+1] == h_outs[i]`) and the terminal (`h_outs[K-1] == c`) by comparing values
that appear in *separate* proofs, which requires them to be public inputs. A recursive
construction — where an outer circuit verifies the K inner proofs and stitches the
chain in-circuit — would keep the anchors private and restore information-theoretic
hiding of the ordering. So this leak is a direct, measurable cost of avoiding recursion
(the architecture choice in §2.1), and belongs on the frontier story rather than being
a flaw: plain-product buys parallelism + low per-prover memory + non-recursive simplicity, and
pays for it in computational (not unconditional) partition hiding.

**Net effect.** For the thesis benchmark sizes the work factors are astronomically
infeasible — at N=480, K=2 (M=240): C(480, 240) ≈ 2⁴⁷⁵ and (M-2)! ≈ (238)! — so the
partition is hidden in any practical sense. At toy sizes the oracles are cheap
(N=8, M=4: C(8,4)=70, (M-2)!=2), so the "24 candidate cycles" of §9.13 collapses to a
unique recovered cycle in milliseconds. Read §9.13's candidate count as the *work
factor to break hiding*, not as residual information-theoretic uncertainty. See §14.2
for the quantitative restatement.

### 9.12 Cost overhead vs plain-sort

- Per sub-circuit: M extra Poseidon2 calls (G5) + M extra field multiplications (G6)
  + 1 extra Poseidon2 call (G7). For N=500, K=4 (M=125, DEPTH=18): ~5.5% more gates
  than plain-sort's sub-circuit.
- Glue: O(N) sort replaced by K-1 multiplications + 1 Poseidon2. Net savings in glue.
- Public input pool: O(M) shrinks to O(1) per sub-circuit; O(N) shrinks to O(K) in
  glue. Net savings.

Total: ~5.5% overhead at N=500. Privacy gain: ~N · log(K) → ~2K · log(N) bits leaked.

### 9.13 Worked example: N = 8, K = 2, M = 4, DEPTH = 6

Same cycle as plain-sort's example. Off-circuit, the prover computes:

- Hash chain: h_0 = 0; h_1 = Poseidon2(0, 0); ...; h_8 = Poseidon2(h_7, 6) = c
- Chain anchors: h_in_0 = 0, h_out_0 = h_4; h_in_1 = h_4, h_out_1 = h_8 = c
- X = Poseidon2(c)
- P_0 = (X+0)(X+5)(X+3)(X+2), P_1 = (X+7)(X+4)(X+1)(X+6)
- expected_product = ∏(X+j) for j=0..7 = P_0 · P_1 (identity holds because the
  multisets partition exactly)

Sub-circuits and glue verify all constraint groups (see §9.6 and §9.8). Verifier
runs `bb verify × 3`, then cross-checks (same root, same c, same X across all
proofs; glue's chain anchors match sub-proofs' h_out values; verifier independently
recomputes expected_product and checks it matches the glue's value).

**Verifier candidate count:** verifier knows endpoints (0→...→2, 7→...→6) but not
which nodes are in which segment. Interior nodes {1,3,4,5} split into two pairs: 6
ways; each pair has 2! orderings: 4 orderings. Total **24 candidate cycles** out of
5040 — much closer to flat_merkle's privacy than plain-sort's 4 candidates.

**Caveat (see §9.11, §14.2):** these 24 are a *work factor*, not residual
information-theoretic uncertainty. At this toy size the public `P_i` (factor over
C(8,4)=70 subsets) and chain anchors (brute-force 2!=2 orderings) let the verifier
confirm the unique real cycle essentially instantly. plain-product's partition hiding is
computational and only meaningful at large N; do not read "24 candidates" as
unconditional ambiguity.

---

## 9b. Variants committed-sort / committed-product — closing the partition leak

Variants plain-sort and plain-product are the **diagnosis**: plain-sort discloses the partition outright; plain-product
hides the node multisets but only behind *confirmation oracles* (§9.11) — `P_i`
factors over C(N,M) subset-products and the public chain anchors brute-force over
(M-2)! orderings. The committed variants are the **cure**: they keep plain-sort's and plain-product's
mechanisms (sort / grand-product) and their parallelism, but move every
per-segment value behind a single **blinded Poseidon2 commitment**, so a bounded
verifier can no longer confirm a guessed partition. This is the "commitment fix"
of `FRONTIER_REFRAME.md` (F6).

### 9b.1 The move

Each sub-circuit, instead of exposing its per-segment scalars in the clear,
publishes one hiding commitment

```
C_i = fold(r_i, [v_1, .., v_m])      where  fold(acc, x) = Poseidon2([acc, x], 2)
```

seeded by a uniformly-sampled blinding scalar `r_i` (the prover's secret). The
glue takes the values **and their openings `r_i`** as private witness, recomputes
each `C_i` and asserts it equals the public `C_is[i]` (constraint **G0**), then
runs all partition / boundary / threshold logic on the now-trusted witnessed
values. The verifier's cross-check collapses to comparing opaque field elements:
the shared `root` (and `X` for committed-product), plus `glue.C_is[i] == sub_i.C_i`.
Because the commitments are blinded, this bookkeeping is automatically
zero-knowledge.

`fold` uses only the 2-input `Poseidon2::hash([l, r], 2)` already cross-validated
against the Rust builder in `tests/hash_compat/`; no new hashing primitive is
introduced. Hiding rests on Poseidon2 as a random oracle (a guessed value-tuple
cannot be confirmed without `r_i`); binding rests on its collision resistance (a
commitment opens to essentially one tuple).

### 9b.2 committed-product (the cure for plain-product)

`circuits/hierarchical_segment_cfs` + `hierarchical_glue_cfs`. The sub folds the
plain-product aggregates `[P_i, h_in_i, h_out_i, start, end, partial_cost]` into `C_i`;
`h_in_i` and `r` become private witness. **Public surface: `{root, X, C_i}`**
(sub) / **`{root, threshold, X, C_is}`** (glue). Two consequences:

- **The sub's G7 (`X == Poseidon2(c)`) is dropped.** committed-product has no public
  `c`; the X↔c binding lives only in the glue (G4), and the chain↔nodes binding is
  re-established by the sub's chain-link (G5) plus the commitment equality. `X`
  itself stays public: it is a one-way hash of the now-private `c`, leaks nothing,
  and is the single global challenge every sub needs to compute `P_i`.
- **The distributed structure is preserved.** Each sub still computes its `P_i`
  (O(M)); the glue still multiplies K products against the in-circuit RHS
  `∏(X+j)`. The commitment adds only K aggregate-folds (6 hashes each, O(K) total)
  to the glue — so committed-product keeps plain-product's O(K)-flavoured glue advantage.

Both §9.11 oracles close: `P_i` and the anchors are inside `C_i` (private), so the
multiset is no longer factorable and the interior order is pure witness
(information-theoretically hidden, as in plain-sort).

### 9b.3 committed-sort (the cure for plain-sort)

`circuits/hierarchical_segment_c` + `hierarchical_glue_c`. The sub folds
`[cycle_segment…, partial_cost]` into `C_i`; the per-segment sort (plain plain-sort's G2) is
**dropped** — the glue owns the partition. **Public surface: `{root, C_i}`** (sub)
/ **`{root, threshold, C_is}`** (glue); no Fiat-Shamir, no `X`. The glue witnesses
all K segments' nodes (flat `[u32; N]`), recomputes each `C_i` (G0), runs the same
**O(N) sort** partition check (`sort(all_nodes) == [0..N-1]`) over the witnessed
nodes, and derives the boundary endpoints `start_i = all_nodes[i·M]`,
`end_i = all_nodes[i·M+M-1]` from them (so the glue needs the `M` global). The sort
also forces every node into `[0,N)`, so no separate range check is needed in the
glue.

### 9b.4 Privacy class and the honest ceiling

Both committed variants hide the multiset **computationally** (on Poseidon2) and
the interior order **information-theoretically** (it is pure witness). The honest
residual versus flat/recursion: they still publish **K commitments**, so they
**reveal K** (the segment count), and hiding rests on the commitment scheme. That
places committed-* exactly **one assumption below** flat and recursion, which make
the partition *structurally absent* from the public surface (§F10). The payoff:
committed-* reach near-flat privacy **without recursion's ≈704k×K aggregation
tax**, keeping the per-segment parallelism and low per-prover memory. The only
stitching-tax symptom they retain is the O(K) verifier (K+1 proofs, K commitments) —
the symptom that only recursion (in-circuit) or folding (deferred) removes.

The optional unconditional upgrade is **Pedersen** commitments (unconditional
content hiding, at the cost of in-circuit curve operations and only *computational*
binding); it is left as an analytical point — Poseidon matches the stack and gives
computational hiding cheaply.

### 9b.5 The equal-privacy finding (committed-sort ≡ committed-product in privacy)

Under full equalization the two committed variants reach the **same privacy
class** — multiset computational, interior order information-theoretic, reveal K.
They differ only in **glue cost and mechanism**:

- committed-sort: O(N) sort **plus** an O(N) commitment fold (the glue re-folds all N
  nodes), so its glue carries the heavier O(N) work;
- committed-product: distributed grand-product (each sub folds its own O(M) into `P_i`)
  with only an O(K) aggregate commitment fold in the glue.

This is the equal-privacy restatement of the F7 result ("plain-sort is not dominated by
plain-product"): once privacy is held constant, the plain-sort-vs-plain-product contrast is purely a
glue-cost / critical-path comparison — plain-product's aggregate commitment is the more
glue-efficient design, while committed-sort is simpler (deterministic, no
Schwartz–Zippel error term).

### 9b.6 Cost

The commitment adds, per sub, `m` (committed-sort) or `6` (committed-product) extra
Poseidon2 calls, and, in the glue, the K commitment recomputes. At the toy size
N=8, K=2 (where the Merkle tree is tiny) the measured circuit-size overhead versus
the uncommitted variant is modest — committed-product ≈ +7% sub / +22% glue over plain-product,
committed-sort within a comparable band over plain-sort. Because the overhead is a fixed
Poseidon2 count while the dominant cost (internal-edge Merkle proofs) grows with
DEPTH, the *relative* overhead shrinks at thesis sizes (N≤480). The full
`results/hier_c.csv` / `results/hier_cfs.csv` sweeps (run with
`pipeline/run_hier_c.py` / `run_hier_cfs.py`) place the exact numbers on the
frontier.

### 9b.7 Soundness

Inherited from plain-sort / plain-product: internal/boundary Merkle bind costs to `root`; the sort
(committed-sort) / grand-product at the unforgeable in-circuit `X` (committed-product)
enforces the exact partition; the threshold check bounds total cost. **New:** the
commitment binding (sub **G8**, glue **G0**) ties the hidden per-segment values to
the public `C_i` — a prover cannot present one set of values to the sub and a
different set to the glue without breaking Poseidon2 binding, and cannot tamper a
witnessed value while keeping `C_i` without the recompute failing. Both directions
are exercised by `tests/correctness/test_hierarchical_{c,cfs}.py` (sub-G8 and
glue-G0 tamper tests, plus a verifier cross-check that rejects mixed proof sets).

### 9b.8 Implementation pointers

| | committed-sort | committed-product |
|---|---|---|
| sub / glue circuits | `hierarchical_segment_c` / `hierarchical_glue_c` | `hierarchical_segment_cfs` / `hierarchical_glue_cfs` |
| builder mode | `merkle_builder --hierarchical-c K` | `merkle_builder --hierarchical-cfs K` |
| verifier | `pipeline/verify_hier_c.py` | `pipeline/verify_hier_cfs.py` |
| benchmark harness | `pipeline/run_hier_c.py` (CSV `hier_c`) | `pipeline/run_hier_cfs.py` (CSV `hier_cfs`) |
| correctness test | `tests/correctness/test_hierarchical_c.py` | `tests/correctness/test_hierarchical_cfs.py` |

`pipeline/aggregate_hier.py` consumes both raw CSVs unchanged, emitting
`hier_c_k{K}` / `hier_cfs_k{K}` rows for `plot.py`.

---

## 10. Variant B — flat-full, sub-matrices public

B replaces plain-sort's Merkle proofs for internal edges with cheap ROM lookups into a
segment-local sub-matrix that is exposed as a public input. The boundary edges still
use the global Merkle root (unchanged glue).

### 10.1 The design move

In plain-sort, each internal edge costs DEPTH × ~87 ≈ 1500 gates (Merkle proof). In B, each
internal edge costs ~1 gate (ROM lookup), but the M × M sub-matrix is paid for in
public-input encoding (M² × ~7.25 gates per sub-circuit).

Total cost across K sub-circuits: K · M² · 7.25 = (N²/K) · 7.25 gates. Beats
flat_merkle's N · DEPTH · 87 gates for K ≥ 3 at N = 500.

### 10.2 The indexing nuance

The sub_matrix is indexed by **sorted positions** 0..M-1 (so
`sub_matrix[i*M + j] = cost(sorted_nodes[i], sorted_nodes[j])`). The cycle_segment
is in **cycle order**, so to look up the cost of `cycle_segment[i] →
cycle_segment[i+1]` the sub-circuit needs to map each cycle-order node to its
sorted position.

Private witness `cycle_pos: [u32; M]`: `cycle_pos[i]` = sorted position of
`cycle_segment[i]`. The circuit binds it via `sorted_nodes[cycle_pos[i]] ==
cycle_segment[i]`, then uses cycle_pos to index sub_matrix.

### 10.3 Sub-circuit interface

```
Public inputs:
  root:          Field          // integrity anchor (verifier hashes their copy)
  sorted_nodes:  [u32; M]
  start_node:    u32
  end_node:      u32
  partial_cost:  u64
  sub_matrix:    [u64; M*M]     // segment cost slice, sorted-position indexed

Private witness:
  cycle_segment: [u32; M]
  cycle_pos:     [u32; M]
```

No Merkle witnesses in the sub-circuit's private inputs (those are only in the
glue's private inputs for boundary edges).

### 10.4 Sub-circuit constraint groups (six)

- **G1 Range.** `cycle_segment[i] < N`.
- **G2 Permutation.** `sort(cycle_segment) == sorted_nodes`. Same as plain-sort.
- **G3 Endpoints.** Same as plain-sort.
- **G4 cycle_pos binding.** For each i: `sorted_nodes[cycle_pos[i]] == cycle_segment[i]`.
- **G5 Edge lookup.** For each i in 0..M-2: `edge_cost[i] = sub_matrix[cycle_pos[i] *
  M + cycle_pos[i+1]]`; accumulate.
- **G6 Cost binding.** `sum(edge_cost) == partial_cost`.

### 10.5 Glue — exactly plain-sort's glue

Unchanged. Sort-based partition check, K boundary Merkle proofs against root,
sum-threshold check. The glue does not know or care whether sub-circuits used Merkle
or sub_matrix.

### 10.6 Verifier checks specific to B

Beyond the cross-checks shared with plain-sort, the B verifier additionally:

1. **Hashes their own copy of the public matrix** into a Poseidon2 Merkle root
   `R_v`.
2. **Confirms all K+1 proofs declare `root == R_v`.**
3. **For each sub-proof i**, looks up the slice of the known matrix at positions
   `sorted_nodes_i × sorted_nodes_i` and checks element-wise equality with
   `sub_matrix_i`. O(K · M²) = O(N²/K) native equality checks. Cheap.

Without these checks, the prover could supply a fake sub_matrix with lower costs.
**B's soundness is conditional on the verifier knowing the matrix** — which is
exactly why B is restricted to the matrix-public regime.

### 10.7 Soundness chain

1. **Verifier knows the matrix** (use-case assumption).
2. **Verifier hashes matrix → R_v; checks all proofs declare root == R_v.**
3. **Verifier checks each sub_matrix matches the corresponding slice of the matrix.**
4. **cycle_pos bound to actual sorted positions** (G4).
5. **Edge costs bound to verified sub_matrix entries** (G5).
6. **partial_cost bound to sum of edges** (G6).
7. **Partition exact** (glue G2).
8. **Boundary edges bound to root** (glue G3, Merkle).
9. **Total cost bounded** (glue G4).

### 10.8 Privacy

Verifier learns: partition; K endpoints; K per-segment cost sums; **K M × M
sub-matrices**.

In the **matrix-public regime** (B's intended use): the sub-matrices are
informationally redundant — the verifier already knows the matrix. Marginal
disclosure vs plain-sort is zero.

In the matrix-private regime: B is unusable (it would expose proprietary cost data).
plain-sort and plain-product are the variants for that regime.

### 10.9 Cost comparison at N = 500

| Variant | Approx total gates | Notes |
|---|---|---|
| flat_merkle | ~783k | Baseline |
| plain-sort | ~795k | +1.5% over flat_merkle |
| plain-product | ~840k | +5.5% over plain-sort |
| Variant B (K=4) | ~460k | -41% vs flat_merkle |
| Variant B (K=3) | ~605k | -23% |
| Variant B (K=2) | ~906k | +16% (loses to flat_merkle at K=2) |

B becomes attractive at K ≥ 3 and gets better with K.

### 10.10 Worked example: N = 8, K = 2, M = 4

Same cycle and costs. The 8 × 8 cost matrix is public (let cycle edges have the
values listed above; other entries arbitrary but known).

**Sub-circuit 0:** cycle_segment=[0,5,3,2], sorted_nodes=[0,2,3,5],
cycle_pos=[0,3,2,1], sub_matrix = 4×4 slice on rows × cols {0,2,3,5}, partial_cost=30.

Edge lookups:
- 0→5: sub_matrix[cycle_pos[0]·4 + cycle_pos[1]] = sub_matrix[0·4+3] = M[0,5] = 10
- 5→3: sub_matrix[cycle_pos[1]·4 + cycle_pos[2]] = sub_matrix[3·4+2] = M[5,3] = 12
- 3→2: sub_matrix[cycle_pos[2]·4 + cycle_pos[3]] = sub_matrix[2·4+1] = M[3,2] = 8

Sum = 30 ✓.

**Sub-circuit 1:** cycle_segment=[7,4,1,6], sorted_nodes=[1,4,6,7],
cycle_pos=[3,1,0,2], sub_matrix = 4×4 slice on rows × cols {1,4,6,7}, partial_cost=34.

Edge lookups: 11 + 9 + 14 = 34 ✓.

**Glue:** identical to plain-sort's glue at N=8, K=2 (boundary Merkle proofs at leaves 23
and 48 with costs 15 and 13, partition sort, threshold check).

**B-specific verifier steps:**
1. Hash public 8 × 8 matrix → R_v.
2. Confirm root = R_v in all proofs.
3. Check sub_matrix_0 matches the {0,2,3,5} × {0,2,3,5} slice of the public matrix.
4. Check sub_matrix_1 matches the {1,4,6,7} × {1,4,6,7} slice.

If all checks pass: accept.

---

## 11. The proof workflow (applies to all variants)

The five-phase workflow below applies to plain-sort, plain-product, and B with variant-specific
differences noted inline.

### Phase 1 — Off-circuit setup (Prover, sequential, native code)

1. **Solve TSP.** Obtain a Hamiltonian cycle with cost ≤ T.
2. **Split into K segments.** Cycle indices [0..M), [M..2M), ..., [(K-1)M..N).
3. **Build per-segment data:**
   - All variants: `sorted_nodes_i`, `start_node_i`, `end_node_i`, `partial_cost_i`.
   - A: Merkle proofs for M-1 internal edges per segment, against the global root.
   - plain-product: additionally compute the hash chain `h_0=0, h_{j+1}=Poseidon2(h_j,
     cycle[j])`, extract `c = h_N`, `X = Poseidon2(c)`, per-segment `P_i = ∏(X +
     cycle_segment[j])`, `expected_product = ∏(X+j)` for j=0..N-1.
   - B: extract per-segment sub_matrix (M × M slice of global matrix); compute
     `cycle_pos` (sorted position of each cycle_segment value).
4. **Build glue data:** K boundary edge Merkle proofs (against global root, same for
   all variants).

### Phase 2 — Witness generation (Prover, K+1-way parallel)

5. **Format K+1 Prover.toml files** (K sub-circuits + 1 glue).
6. **Run `nargo execute`** on each circuit to generate the witness.

### Phase 3 — Proof generation (Prover, K+1-way parallel)

7. **Run `bb prove`** on each witness. Wall-clock ≈ max(sub-circuit proving time,
   glue proving time) ≈ time to prove a single sub-circuit of size N/K.

### Phase 4 — Delivery

8. **Send K+1 proofs (each 14,656 bytes) + public-input dump** to the verifier.

### Phase 5 — Verification (Verifier)

9. **Run `bb verify`** on each of the K+1 proofs.
10. **plain-product only:** Independently compute `expected_product_v = ∏(X + j)` for j=0..N-1
    from the publicly visible X.
11. **B only:** Hash the publicly-known cost matrix to get R_v; check all proofs
    declare `root == R_v`; for each sub-proof verify sub_matrix matches the matrix
    slice indicated by sorted_nodes.
12. **All variants:** Cross-check shared public-input fields across proofs:
    - Same root across all K+1 proofs.
    - **A**: glue's `all_sorted_nodes` is the concatenation of sub-proofs'
      `sorted_nodes`.
    - **plain-product**: same c and X across all proofs; `glue.h_ins[i+1] == sub_proof_i.h_out`;
      `glue.expected_product == expected_product_v`.
    - **B**: same as plain-sort (B and plain-sort share the glue).
    - All variants: starts, ends, partial_costs match between glue and sub-proofs.
13. **Accept** iff all checks pass.

---

## 12. Side-by-side comparison

| Aspect | flat_merkle | plain-sort | plain-product | B |
|---|---|---|---|---|
| Single proof or K+1? | Single | K+1 | K+1 | K+1 |
| Cost matrix exposure | None (root only) | None | None | M × M sub-matrices public |
| Partition exposure | None | Full | None | Full |
| Endpoints exposure | N/A | K pairs | K pairs | K pairs |
| Per-segment cost sums | N/A | K | K | K |
| Total gates @ N=500 | ~783k | ~795k (+1.5%) | ~840k (+7%) | ~460k @ K=4 (-41%) |
| Total proving time @ N=500 | ~10 min | ~10 min × 1/K parallel | ~+5.5% over plain-sort | ~half of plain-sort |
| Per-prover memory @ N=500 | Full ~32 GB | ~32 GB / K per process | Same as plain-sort | Lower than plain-sort (no Merkle witnesses) |
| Verifier work | O(1) | O(K) cross-checks | O(N) for expected_product + O(K) cross-checks | O(N²/K) sub_matrix check |
| Soundness type | Unconditional | Unconditional | Fiat-Shamir + Schwartz-Zippel (~2⁻²⁵⁴) | Unconditional given matrix-public assumption |
| Glue circuit | N/A | Sort + K Merkle + threshold | Grand product + chain stitching + K Merkle + threshold | Same as plain-sort |

Candidate cycles consistent with the verifier's view at N=8, K=2:

| Variant | Candidate cycles | Bits of cycle entropy leaked |
|---|---|---|
| flat_merkle | 5040 ((N-1)!) | 0 |
| plain-sort | 4 | ~10.3 bits |
| plain-product | 24 | ~7.7 bits |
| B (matrix public) | 24 to 4 depending on cost-matrix structure | similar to plain-sort |

---

## 13. Use-case mapping

Each variant has a natural class of real-world applications:

| Variant | Natural use cases | Why this variant |
|---|---|---|
| **flat_merkle** | Generic baseline; logistics SLA audit (matrix private, verifier sees only root); ESG reporting where only cycle privacy matters | Maximum privacy; only existence statement needed; single-machine prover sufficient. |
| **A** | Multi-team / multi-region accountability where the partition is operational (delivery zones, team assignments); cross-organisation cost sharing; regulated zoning | Partition disclosure is operationally required; per-segment partial_costs are accountability artifacts; parallelism maps to operational units. |
| **plain-product** | Same scenarios as plain-sort but the specific partition is competitively sensitive (delivery route grouping reveals customer-cluster structure); maximum-privacy hierarchical option | Recovers most of flat_merkle's privacy while keeping plain-sort's parallelism and per-prover memory benefits. Costs ~5.5% extra sub-circuit gates. |
| **B** | Smart-city fleet routing on public road networks; verification against TSPLIB benchmark instances; matrix non-sensitive and total prover cost is binding | Matrix is public anyway; sub_matrix exposure costs nothing in privacy; ~K-fold gate savings vs plain-sort. |
| (folding — future) | Same as plain-product but verifier-side overhead is the binding constraint | UltraHonk baseline established here is what folding designs would need to beat. |

---

## 14. Privacy analysis — quantitative bounds

### 14.1 plain-sort

At general (N, K, M=N/K), the verifier knows the exact partition and endpoints, so
each segment's interior is some permutation of M-2 nodes (start and end fixed). Total
candidate cycles:

```
|candidate cycles| = (M-2)!^K
```

Bits leaked vs total cycle entropy:

```
bits_leaked_A = log₂((N-1)!) - K · log₂((M-2)!)
```

At N=8, K=2: 4 candidates, 10.3 bits leaked.
At N=480, K=4: ~10⁸⁰⁰ candidates remaining (still unenumerable), ~800 bits leaked
out of ~4032 total — ~20% of cycle entropy lost.

### 14.2 plain-product

Verifier knows endpoints only; partition is hidden. For each way of partitioning the
N-K endpoint-free nodes into K interior sets of size M-2, the cycle has
`(M-2)!^K` orderings. Total candidates *consistent with the public endpoints alone*:

```
|candidate cycles| = C(N-K, K-1 fixed interior sizes) · (M-2)!^K
```

(roughly — exact form depends on whether endpoints are distinguishable across
segments).

At N=8, K=2: 6 partitions × 4 orderings = 24 candidates.
At N=480, K=4: much higher candidate count than plain-sort, close to but smaller than (N-1)!.

**This candidate count is a work factor, not residual information-theoretic
uncertainty.** Unlike plain-sort — where the verifier *cannot* tell which of the
`(M-2)!^K` interior orderings is real even with unbounded compute, because nothing
public distinguishes them — plain-product publishes confirmation oracles (§9.11) that let a
verifier *check* a guessed cycle and find the unique true one. Concretely the
break cost is:

```
work_to_recover_partition  ≈  Σ_i C(N, M)        (Oracle 1: factor each P_i)
work_to_recover_ordering   ≈  Σ_i (M-2)!         (Oracle 2: chain-anchor brute force)
```

So plain-product's *information-theoretic* leakage to an unbounded verifier is the full cycle
(the public transcript determines it uniquely); its *computational* leakage to a
bounded verifier is ~0 as long as `C(N,M)` and `(M-2)!` are infeasible.

| (N, K) | M | C(N, M) | (M-2)! | plain-product hiding |
|---|---|---|---|---|
| 8, 2   | 4   | 70           | 2          | none (toy: breaks in ms) |
| 48, 4  | 12  | ~1.7·10⁹     | ~3.6·10⁶   | weak–moderate |
| 480, 2 | 240 | ~2⁴⁷⁵        | (238)!     | infeasible to break |
| 480, 4 | 120 | ~2³⁵⁰        | (118)!     | infeasible to break |

The contrast with plain-sort is the honest framing for the thesis: **A leaks the partition
unconditionally but cheaply to state; plain-product leaks it to no bounded verifier but to an
unbounded one. The dividing line is compute, and the public chain anchors + P_i are
what put the line there** — itself a consequence of the non-recursive K+1-proof
architecture (§9.11, §2.1). A recursive variant would move plain-product's hiding from
computational back to information-theoretic for the interior order.

### 14.3 Variant B in the matrix-public regime

When the matrix is public, the verifier can compute the cost of every candidate
cycle and filter against the published `partial_costs`. For a generic matrix, the
filter is sharp enough to uniquely identify the partition. In the worst case, B's
candidate count collapses to plain-sort's (4 candidates at N=8, K=2).

So B's effective privacy *under its intended threat model* is similar to plain-sort's. The
sub_matrix disclosure is the cost in privacy bits when measured against
flat_merkle, not against A.

### 14.4 Variants committed-sort / committed-product

The committed variants remove the *confirmation oracles* that made plain-product's leakage a
mere work factor (§14.2). With the per-segment values folded into a blinded
commitment, a verifier can no longer *check* a guessed cycle against the public
transcript: there is no `P_i` to factor and no anchor to brute-force, and the
commitment cannot be reproduced without the secret blinding `r_i`. So the
candidate count stops being a "work factor to confirm the unique true cycle" and
becomes genuine residual ambiguity again — bounded only by the commitment scheme.

| | recovers multiset? | recovers interior order? |
|---|---|---|
| plain-sort | published (`sorted_nodes`) | hidden info-theoretically, `(M-2)!^K` |
| plain-product | **confirmable**, work ≈ Σ C(N,M) | **confirmable**, work ≈ Σ (M-2)! |
| **committed-sort / committed-product** | hidden; needs breaking Poseidon2 hiding | hidden info-theoretically, `(M-2)!^K` |
| recursion / flat | absent from public surface | absent from public surface |

committed-sort and committed-product sit at the **same** rung: multiset hidden
*computationally* (Poseidon2), interior order hidden *information-theoretically*,
with the segment count K revealed by the K published commitments. The information
that plain-product leaked to an unbounded verifier (the full cycle, via the transcript) is,
for the committed variants, leaked only to an adversary who breaks the commitment
— i.e. nothing is determined by the public transcript alone beyond K and the
aggregate threshold.

### 14.5 The privacy ladder (assumption-decreasing)

Reading the family as one progression makes the privacy axis monotone:

```
B  →  plain-sort  →  plain-product  →  committed-sort / committed-product  →  recursion / folding / flat
disclose   disclose   confirmation-       computational hiding,      partition
sub-matrix  partition   oracle leak         reveals K (Poseidon)      structurally
+ partition (multiset)  (work factor)                                 absent
```

Two distinct hiding *mechanisms* span the ladder: **"don't put it there"**
(plain-sort discloses; recursion/flat make it structurally absent — assumption-free) versus
**"commit to hide it"** (committed-* — one cryptographic assumption). plain-product is the
honest in-between: it *looks* hidden but is only a search away. The committed
variants are the smallest change that turns plain-product's "search away" into "one
assumption away", and recursion is what turns "one assumption away" into
"assumption-free" — at the ≈704k×K cost quantified in
`project_recursion_experiment` / the recursion micro-benchmarks.

---

## 15. Implementation considerations

This section consolidates the practical decisions and constraints that shape how
the three variants get implemented. They are settled choices, not open questions.

### 15.1 Architectural commitments (recap)

- **Independent proofs + glue, not recursive composition.** K+1 UltraHonk proofs
  bound by verifier-side cross-checks. Recursive verification deferred to future
  work alongside folding schemes.
- **K starts at 2 hardcoded for correctness, then parameterised.** First end-to-end
  run uses K=2 with a hardcoded compile-time global; immediately after, K becomes
  a compile-time parameter that the harness can patch.
- **Glue shared between plain-sort and B.** Both use the same sort-based partition check
  and K boundary Merkle proofs. plain-product has its own glue with the grand-product check.
- **Sub-circuits publish sorted node sets** (plain-sort and B) **or Field-valued aggregates**
  (plain-product), not the cycle-order segment. In all three this preserves in-segment
  visit-order privacy at zero extra cost.

### 15.2 Implementation order vs presentation order

The implementation order chosen for this thesis is **plain-sort → B → plain-product**:

- plain-sort first: simplest, establishes the K+1-proof harness, the Merkle-builder
  extensions, the cross-check verifier.
- B second: reuses plain-sort's glue verbatim; only the sub-circuit body changes
  (Merkle → ROM lookup). The cheaper second variant.
- plain-product third: most conceptual machinery (hash chain, Fiat-Shamir, grand product);
  builds on plain-sort's sub-circuit by adding G5-G7 and removing G2.

The presentation order in this document is **plain-sort → plain-product → B**, which is the
conceptual progression (simple baseline → privacy refinement → gate optimisation).
Easier to explain the dualism through the variants in conceptual order, even
though they get built in implementation order.

### 15.3 Compile-time globals and per-(N, K) recompilation

Noir requires array sizes to be `comptime`. Each (N, K, DEPTH) tuple requires its
own compiled circuit. The benchmark harness patches the source files:

```
global N: u32 = <n>;
global K: u32 = <k>;
global M: u32 = <n/k>;
global DEPTH: u32 = <ceil(log2(n*n))>;
```

then runs `nargo compile` before each benchmark cell. The compile time itself is
small compared to proving but non-zero (~seconds for large N).

### 15.4 N divisibility discipline

N % K must equal 0 (uniform segment sizes) under the current design. Benchmark
N values are chosen accordingly:

| N | divisible by | M at K=2 | M at K=4 | M at K=8 |
|---|---|---|---|---|
| 48  | 2,3,4,6,8 | 24  | 12  | 6   |
| 96  | 2,3,4,6,8 | 48  | 24  | 12  |
| 192 | 2,3,4,6,8 | 96  | 48  | 24  |
| 480 | 2,3,4,5,6,8 | 240 | 120 | 60 |

N=480 is the comparison anchor against flat_merkle's N=500 benchmark (~4%
mismatch — close enough for the frontier figure).

Non-uniform segment sizes (e.g., for N=500 at K=3: M=167, M=167, M=166) are
possible but require a more complex sub-circuit interface and are deferred.

### 15.5 The Merkle tree builder, extended for hierarchical

The existing `pipeline/merkle_builder/` (Rust) builds a single Poseidon2 Merkle
tree over the global N² matrix and emits one Prover.toml for the flat circuit.
For hierarchical proofs the builder is extended:

- Build the tree once over the global N² matrix (single tree, single root).
- Extract M-1 internal-edge Merkle proofs per segment (K subsets of edges, each
  using DEPTH siblings and DEPTH path bits).
- Extract K boundary-edge Merkle proofs for the glue.
- Emit K+1 Prover.toml files (one per sub-circuit + one for glue).

plain-product additionally needs the hash-chain values (h_0, h_1, ..., h_N), the
challenge X, the per-segment grand products P_i, and the expected_product. These
are computed by extending the Rust builder with native Poseidon2 calls + field
arithmetic.

### 15.6 Per-prover orchestration

Each of the K+1 proofs is generated independently:

```
# in parallel across K worker machines:
for i in 0..K:
    nargo execute --witness sub_i.gz --prover sub_i_prover.toml
    bb prove --witness sub_i.gz --output sub_i.proof

# can run in parallel with sub-circuits if a K+1th machine is available,
# or sequentially after them:
nargo execute --witness glue.gz --prover glue_prover.toml
bb prove --witness glue.gz --output glue.proof
```

The K sub-circuits and the glue can all run simultaneously if K+1 machines are
available. Wall-clock time ≈ max(sub-circuit proving time at M=N/K, glue proving
time). Glue is small (K-related operations only) so sub-circuit time dominates.

### 15.7 Verifier orchestration

The verifier:
1. Loads K+1 proofs and the per-proof public-input dumps.
2. Runs `bb verify` on each proof.
3. Runs the variant-specific post-processing:
   - A: no extra computation; just cross-checks.
   - plain-product: compute `expected_product_v = ∏(X+j)` natively; cross-checks.
   - B: hash own matrix copy to get R_v; check all roots match R_v; check each
     sub_matrix matches the expected matrix slice; cross-checks.

Verifier work is dominated by the K+1 `bb verify` calls (~milliseconds each) plus
O(N) (plain-sort, plain-product) or O(N²/K) (B) native post-processing. Total verifier time is
roughly 10× faster than flat_full verification at the same N (which has O(N²)
public-input processing).

### 15.8 Estimated implementation effort

From the supervisor report's planning section:

- plain-sort: ~1 work-week (sub-circuit, glue, pipeline, tests, gate-count
  sanity check at small N).
- Variant B: ~3 work-days (sub-circuit body differs from plain-sort; glue + pipeline
  reused).
- plain-product: ~1 work-week (sub-circuit additions for chain + grand product +
  challenge; new glue with grand-product check; pipeline extensions for chain
  precomputation; negative-test design for Fiat-Shamir).
- Combined benchmarks + frontier figure: ~1 work-week.

Total: ~3 work-weeks for the three-variant programme.

---

## 16. Common gotchas and security pitfalls

**`bb verify` alone is not sufficient for hierarchical proofs.** Each `bb verify`
confirms internal consistency of one proof. The verifier-side cross-checks (step 12
in §11) are non-optional: without them, K+1 individually-valid proofs about K+1
different universes pass.

**The Merkle commitment is only meaningful if anchored externally.** A Poseidon2
root with no trust anchor lets the prover pick whatever matrix makes their proof
trivial. Standard anchors: authority signature, trusted oracle, cross-attestation,
public timestamping, decommitment-on-dispute. See supervisor report §2.2.

**plain-product's soundness rests on Fiat-Shamir + Schwartz-Zippel + Poseidon2 collision
resistance.** Distinct from plain-sort and B which have unconditional soundness. The
soundness error is ~N · 2⁻²⁵⁴ — negligible but technically non-zero.

**Naive fixed-X grand product is unsound.** If the prover knew X before committing
to segments, they could craft fake partitions with matching products. The in-circuit
Fiat-Shamir construction (chain + Poseidon2) is essential, not optional.

**plain-product has a sequential prelude** for hash chain precomputation: N native
Poseidon2 calls, ~100 µs at N=500. Doesn't affect parallel proving wall-clock
meaningfully.

**Boundary self-loops auto-prevented.** If the partition check passes (the union is
exactly {0..N-1}), then ends[i] and starts[(i+1)%K] are in different segments,
hence different nodes. No explicit assertion needed.

**Sub-circuit publishes sorted node sets, not the cycle-order segment.** In plain-sort and B
this preserves in-segment visit-order privacy at zero extra cost (the sort-based
permutation check produces a sorted array as a byproduct).

**B is unusable in the matrix-private regime.** Without an independent verifier copy
of the matrix to check sub_matrix against, B's sub-circuits accept arbitrary
sub-matrices. The "matrix-public" assumption is load-bearing for soundness, not just
for the use case framing.

**N divisibility matters.** N % K must equal 0 for the current implementation
(segments of equal size). Benchmark N values are chosen accordingly: {48, 96, 192,
480}. Mixing arbitrary N with arbitrary K requires non-uniform segment sizes —
deferred work.

**Hierarchical does not save total gates** (plain-sort, plain-product vs flat_merkle). The wins are
parallel wall-clock and per-prover memory. B is the exception, saving total gates
by trading matrix privacy.

**ACIR opcode count is a misleading proxy for gate-level cost** (a general lesson
from the flat baseline, applies here too). Compare circuits on UltraHonk gate counts,
not on ACIR opcodes. The hierarchical variants have similar ACIR opcode counts but
very different gate counts.

---

## 17. Glossary

Quick reference for symbols and terms used throughout this document.

| Term | Definition |
|---|---|
| **N** | Number of nodes in the TSP instance (graph size) |
| **K** | Number of segments in the hierarchical decomposition |
| **M** | Number of nodes per segment, M = N/K |
| **DEPTH** | Depth of the Poseidon2 Merkle tree over the N² cost matrix, ⌈log₂(N²)⌉ |
| **T** | Threshold; the public upper bound on cycle cost |
| **root** | Poseidon2 Merkle root of the flat N² cost matrix (public input across all proofs) |
| **cycle** | The Hamiltonian cycle; a permutation of {0..N-1} representing visit order (private witness) |
| **segment** | A consecutive subsequence of M cycle positions; one of K decomposition pieces |
| **cycle_segment** | The segment in cycle order; private witness of each sub-circuit |
| **sorted_nodes** | The segment's node set in ascending order; public output of plain-sort and B sub-circuits |
| **start_node, end_node** | First and last nodes of a segment in cycle order; public outputs |
| **partial_cost** | Sum of M-1 internal edge costs for a segment; public output |
| **boundary_cost** | Cost of an edge connecting one segment to the next; private witness of the glue |
| **sub-circuit** | One of the K Noir circuits that proves a segment is a Hamiltonian path |
| **glue** | The single Noir circuit that stitches the K sub-proofs into a Hamiltonian cycle |
| **all_sorted_nodes** | Concatenation of K sub-proofs' sorted_nodes (public input of plain-sort's and B's glue) |
| **P_i** | *(plain-product only)* Grand product ∏(X + cycle_segment[j]) for segment i; public output |
| **c** | *(plain-product only)* Poseidon2 chain commitment to the full cycle in cycle order |
| **X** | *(plain-product only)* Fiat-Shamir challenge, X = Poseidon2(c) |
| **h_in_i, h_out_i** | *(plain-product only)* Chain values at the start and end of segment i |
| **expected_product** | *(plain-product only)* ∏(X + j) for j = 0..N-1; supplied by prover, checked by verifier |
| **sub_matrix** | *(B only)* M × M sub-matrix of the cost matrix on the segment's nodes; public input |
| **cycle_pos** | *(B only)* Private witness mapping cycle-order positions to sorted-order positions |
| **Hamiltonian cycle** | A cycle visiting every node exactly once and returning to start |
| **Hamiltonian path** | A path visiting every node exactly once (no return edge); each segment is one |
| **Poseidon2** | ZK-friendly sponge hash function; ~87 gates/call in UltraHonk with Plookup |
| **Merkle commitment** | Tree of Poseidon2 hashes over the flattened matrix; root commits to all entries |
| **leaf-index check** | Soundness-critical constraint: path_bits must reconstruct to the expected leaf index |
| **Plookup** | UltraHonk's lookup-table argument; reduces Poseidon2 from ~264 to ~87 gates per call |
| **Schwartz-Zippel** | Lemma: distinct polynomials of degree d agree at a random point with probability ≤ d/q |
| **Fiat-Shamir** | Transform replacing interactive verifier challenges with hash-derived values |
| **Random oracle model** | Idealisation in which hash function outputs are treated as uniformly random |
| **Honest-verifier ZK** | Verifier learns nothing beyond what public inputs imply, given honest verifier |
| **Knowledge soundness** | Successful proof implies prover knows a valid witness, except w/ negligible probability |
| **Soundness error** | Probability that a cheating prover succeeds; ~N/2²⁵⁴ for plain-product; negligible/unconditional for plain-sort, B |
| **Cross-check** | Verifier-side check that K+1 proofs agree on shared public-input fields |
| **UltraHonk** | The Barretenberg-backend SNARK system used in this thesis |
| **ACIR** | Abstract Circuit Intermediate Representation; Noir's pre-backend IR |
| **circuit_size** | UltraHonk gate count (the meaningful cost measure for comparison) |
| **acir_opcodes** | ACIR opcode count; *misleading* as a proxy for gate-level cost (see Finding 4) |

---

## 18. Related documents

- `supervisor_report_draft.md` — full thesis progress report, including the
  optimisation-ZK dualism argument (§7) and the variant-as-statement reframe (§7.7).
- `SESSION_SUMMARY.md` — chronological session notes, findings, design decisions.
- `DESIGN.md` — engineering log: implementation plan, parameter choices,
  architectural commitments.
- `Thesis_Outline.md` — outline of the final thesis document with chapter structure
  and drafting order.
- Circuit source code (when implemented):
  - `circuits/hierarchical_segment/` — plain-sort sub-circuit
  - `circuits/hierarchical_glue/` — plain-sort and B glue (shared)
  - `circuits/hierarchical_segment_fs/` — plain-product sub-circuit
  - `circuits/hierarchical_glue_fs/` — plain-product glue
  - `circuits/hierarchical_segment_full/` — Variant B sub-circuit
