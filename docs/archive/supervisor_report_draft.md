> **ARCHIVED (historical).** Flat-phase progress report; predates committed/recursion/stitching-tax and the variant renaming. Superseded by `Thesis_Outline.md`; useful only as a Ch 2/Ch 4 prose source. Uses old variant names (A, A++).

# Zero-Knowledge Proof for TSP: Flat Circuits, Complexity Analysis, and Design Rationale

**Progress Report — May 2026**

> **Note (2026-05-31): this draft predates several later additions and is kept as a
> point-in-time record.** Since it was written, the project added Variants
> **committed-A / committed-A++** (the privacy "cure" — blinded-commitment partition
> hiding), **recursion** as a first-class implemented variant, and the **binding-tax**
> second structural result. For the current state see `FRONTIER_REFRAME.md`,
> `HIERARCHICAL_EXPLAINED.md` §9b/§14.4-5, `DESIGN.md` §9, `NARRATIVE_FRAMING.md`, and
> `MOTIVATION_AND_OBJECTIONS.md`. A full rewrite is deferred to the write-up phase.

---

## 1. Overview and Research Question

This report documents the first phase of the thesis: the design, implementation, and
benchmarking of flat zero-knowledge proof circuits for the Travelling Salesman Problem
(TSP), together with the structural analysis that motivated a reframing of the original
research question.

### 1.1 Original framing and what we found instead

The work was originally framed around a single research question:

> *"At what problem size N does a hierarchical (decomposed) ZKP circuit become cheaper
> than a flat (monolithic) one, and what governs the crossover?"*

Detailed gate-count analysis during the planning of the hierarchical circuit (Section 8)
showed that this framing pre-supposes a single dimension of "cheaper" that does not
exist for this problem. Hierarchical decomposition has no algorithmic-speedup analogue
in ZK proving for TSP — at best it relocates work, at worst it adds glue work
proportional to N — and any actual gate-count saving requires disclosing structural
information about the cycle. There is no crossover to locate, because hierarchical and
flat are not proving the same statement once the privacy semantics are made precise.

What we found instead is that **the variants we initially compared on cost are in fact
proving different statements about the same underlying TSP instance**. Flat Merkle proves
"a Hamiltonian cycle with cost ≤ T exists." Hierarchical Merkle (Variant A, Section 8)
proves "a Hamiltonian cycle with cost ≤ T exists *that respects this disclosed
partition*." These are not different optimisations of the same proof; they are two
distinct cryptographic statements, each natural for a different use case.

### 1.2 The reframed thesis

> **Zero-knowledge proofs for TSP are best understood as a *family* of cryptographic
> statements, distinguished by what part of the input (cost matrix, partition, segment
> endpoints, per-segment costs) is private vs public to the verifier. Each variant in
> this thesis is the natural proof design for a specific point in that family. The
> structural reason no single variant universally dominates is a dualism between
> optimisation and ZK proving: hierarchical decomposition imposes a constraint in
> optimisation (good — search shrinks) and weakens a constraint in ZK (bad — soundness
> must be restored by O(N) glue work). The NP asymmetry between *finding* and *checking*
> holds, but the way the two respond to decomposition is itself asymmetric: classical
> decomposition gives optimisation an algorithmic speedup; in ZK it gives only
> embarrassingly-parallel speedup, and only at the cost of partition disclosure.**

The flat baseline characterisation in this report is unchanged. It establishes a sharp
crossover at N ≈ 175 between matrix-public (`flat_full`) and matrix-committed
(`flat_merkle`) variants — a meaningful comparison because both prove the same
statement. The hierarchical variants will be presented in the next phase not as
competitors against flat_merkle on a single axis but as the natural proof designs for
distinct use-case regimes (Section 7).

### 1.3 Contributions in this reframed form

1. **Empirical characterisation of the flat baseline.** Five circuit variants
   (`flat_full_*` × 4 permutation strategies, plus `flat_merkle_presence`) benchmarked
   to N = 500. Exact circuit-size models, the `~87 gates/Poseidon2-call` finding
   (Section 4.3), and the N ≈ 175 flat_full ↔ flat_merkle crossover (Section 5).

2. **A negative result with structural explanation.** Hierarchical Merkle decomposition
   does **not** reduce total gate count over flat Merkle for TSP. The cancellation is
   not accidental — it follows from the fact that the global "visit every node once"
   constraint must be restored in the glue, exactly cancelling per-segment savings. The
   explanation is the dualism developed in Section 7.

3. **A variant-as-statement reframe.** Three hierarchical variants (A, A++, B) are
   characterised by the *statement* each proves, not by their relative cost. The
   reframe makes the privacy/cost trade-offs explicit rather than implicit, and matches
   each variant to a distinct class of real-world use cases (Section 7.7 and Section 8).

4. **A frontier-mapping methodology** for ZKP design-space exploration over a single
   problem class. The frontier figure replaces the originally-planned single crossover
   figure and is the principal deliverable of the next phase.

5. **A measured recursive-aggregation corner.** The "perfect-hiding via recursion"
   endpoint of the frontier is implemented and benchmarked (not left as analysis):
   an outer circuit verifies the K segment proofs in-circuit and folds in the glue,
   collapsing the public surface back to `(root, threshold)` — flat_merkle's
   information-theoretic hiding. One in-circuit UltraHonk verification costs ~704k
   gates (N-independent); the K-segment proof scales ~K× (~1.47M at K=2, ~3.0M at K=4),
   ~25–45× A++'s total proving work. A head-to-head A-inner vs A++-inner study shows the
   choice of inner barely moves total cost (the verifications dominate) but A++'s O(1)
   public surface keeps the recursive verification segment-size-independent (Section 7.8).

A secondary thread, motivated by parallel work on heuristic TSP solvers, examines the
same decomposition question in two complementary roles — *finding* a solution
(optimisation) and *verifying* one (zero-knowledge proof). Section 7 develops the
structural dualism between these two contexts that explains why hierarchical
decomposition behaves so differently across them, and why the variant-as-statement
framing of the ZK side is intrinsic rather than incidental.

### 1.4 What this thesis does not claim

To pre-empt overclaiming: this thesis does **not** claim to violate NP asymmetry or to
prove ZK checking is harder than finding. NP asymmetry holds in the standard sense
(verification of any ZK proof is polynomial-time, often sublinear or constant). What the
thesis shows is the more specific structural fact that *hierarchical decomposition*, a
technique that exploits NP asymmetry in classical optimisation by pruning the search
space, does not transfer to ZK proving for problems with non-local constraints. This is
a refinement of how NP asymmetry interacts with proof-system design, not a
counterexample to it.

---

## 2. Problem Formulation

### 2.1 What we are proving

Given a complete weighted directed graph G on N nodes with edge costs c(i,j), a prover
claims to know a Hamiltonian cycle — a tour visiting every node exactly once and
returning to the start — with total cost at most a threshold T. The claim is formalised
as:

> **"I know an ordering (v₀, v₁, …, v_{N-1}) of all N nodes such that
> Σᵢ c(vᵢ, v_{(i+1) mod N}) ≤ T."**

This is a statement about existence and cost, not optimality. The ZKP circuit encodes
this claim as a system of arithmetic constraints that can be proven and verified without
revealing the cycle.

### 2.2 What is public and what is private

The privacy semantics differ across circuit variants and must be stated precisely, as
they change what the proof actually guarantees.

In the **flat-full** variants, the entire cost matrix is passed as public inputs. The
verifier knows the full graph. The only secret is the cycle itself. This models a
setting where the graph is shared knowledge (e.g., a public road network) and the
prover only wants to hide their specific route.

In the **flat-Merkle** variant, only a Poseidon2 Merkle root committing to the cost
matrix is public, alongside the threshold T. The verifier does not learn the individual
edge costs. This models a stricter privacy requirement: the graph itself is sensitive
(e.g., a proprietary logistics network), and the verifier is convinced by a
pre-established commitment rather than the raw data.

A key subtlety: for the Merkle commitment to provide a meaningful guarantee, the
verifier must have independently computed or received the root from a trusted source.
If the prover supplies the root themselves with no external binding, they could choose
a matrix convenient for their claimed cycle. The commitment only makes sense when there
is a mechanism that binds the root to a real-world fact the prover cannot retroactively
change.

This thesis takes no position on which mechanism is most appropriate — that is an
application-level choice. The following are the standard candidates, each providing the
binding from a different direction:

| Trust mechanism | How it binds the commitment | Example use |
|---|---|---|
| **Authority signature** | A trusted third party (regulator, certifier) signs the root | Logistics regulator signs the operator's quarterly cost matrix; the operator then proves SLA compliance against the signed root throughout the quarter. |
| **Trusted oracle** | A neutral data provider publishes signed roots over reference data | A city-data provider publishes a signed Merkle root of pairwise travel times monthly. Any party proves route properties against the oracle's data without disclosing routes. |
| **Cross-attestation** | Multiple stakeholders co-commit | Two organisations sharing a logistics network sign the joint root; either can prove their leg meets agreed bounds without revealing the network to outsiders. |
| **Public timestamping** | The root is anchored to an append-only public ledger before any proofs are produced | Operator publishes the root on a transparency log or blockchain at time T₀; proofs produced later are bound to that pre-committed matrix. |
| **Decommitment-on-dispute** | The matrix is opened to a court/arbitrator if a dispute arises | The root is the binding artifact for ordinary operation; the underlying matrix is disclosed only under legal process. |

The same mechanisms apply to the hierarchical variants discussed in Section 7 and
Section 8. In all cases the cryptographic commitment is doing one job (ensuring the
prover cannot change the matrix between commitment and proof); the trust anchor is
doing a separate job (ensuring the committed matrix corresponds to something real).
A proof system that omits the trust-anchor side is not zero-knowledge proving — it is
the prover declaring whatever they like.

A further subtlety, relevant to the public-matrix regime: when the verifier already
knows the matrix (e.g., a public road network), the Merkle root is no longer a privacy
mechanism; it is an *integrity* mechanism. The verifier hashes the public matrix
themselves and checks the root matches, preventing the prover from sneakily using a
different matrix in the proof. The commitment is still doing real work — it is just not
doing privacy work.

### 2.3 Why threshold, not optimality

Proving optimality in zero knowledge would require the prover to assert that no
Hamiltonian cycle with lower cost exists — a universal quantification over all N!
possible cycles. This is not tractable as a ZKP statement. The threshold formulation
(cost ≤ T) is a well-defined existential claim: "I have a solution at least this good."
In practice, T is set by the verifier as an acceptable quality bound, and the prover
demonstrates they can meet it.

---

## 3. Design Choices

### 3.1 Proof system: Noir and UltraHonk (Barretenberg)

The circuit DSL is **Noir** (v1.0.0-beta.20) compiled to ACIR, proved by
**Barretenberg's UltraHonk** backend (bb v5.0.0-nightly.20260324). The key properties
that justify this choice:

- **No per-circuit trusted setup.** UltraHonk uses a universal structured reference
  string; recompiling for a different N does not require a new setup ceremony.
- **Lookup table support (Plookup).** UltraHonk natively supports lookup arguments,
  which dramatically reduce the cost of ZK-friendly hash functions such as Poseidon2
  (see Section 3.5).
- **Constant proof size.** The proof is a fixed set of polynomial commitments regardless
  of circuit size — verified empirically at 14,656 bytes across all N and all variants.
- **Practical tooling.** Noir's type system and standard library (including
  `check_shuffle` and Poseidon2) reduce circuit implementation risk compared to
  lower-level alternatives like Halo2 or arkworks.

The prover complexity is O(C log C) in the number of circuit rows C; the verifier
complexity is O(1) in C but O(P) in the number of public inputs P. The latter point
is consequential and discussed in Section 4.4.

### 3.2 Circuit structure: four constraint groups

All five variants share the same four-group structure. Groups 1, 2, and 4 are identical
across all variants; only Group 3 differs.

- **Group 1 — Range check.** Assert 0 ≤ cycle[i] < N for all i. Prevents out-of-range
  indices from reaching Groups 2 and 3.
- **Group 2 — Permutation check.** Assert the cycle visits every node exactly once.
  Four strategies are benchmarked here; see Section 3.4.
- **Group 3 — Edge cost verification.** Bind each of the N directed edges in the cycle
  to its cost in the committed matrix. In flat-full variants this is a direct lookup
  into the public cost matrix; in the Merkle variant it is a Poseidon2 Merkle proof.
- **Group 4 — Threshold check.** Assert total_cost ≤ T via a u64 comparison (O(64)
  boolean gates, constant in N).

This decomposition makes the cost structure transparent: Groups 1 and 2 contribute
O(N) gates, Group 3 is the dominant term (O(N²) or O(N log N) depending on variant),
and Group 4 is constant.

**Type rationale.** The Noir types used for each input are not arbitrary — each is the
cheapest type that satisfies the constraint it participates in.

- `cycle: [u32; N]` — Node indices are small non-negative integers (0..N-1). Declaring
  them `u32` makes the Group 1 upper-bound check a single cheap comparison per element.
  Using `Field` would work but would add unnecessary prime-field arithmetic; using `u8`
  would restrict N to 255.

- `edge_costs: [u64; N]` — Edge costs accumulate into `total_cost` for the Group 4
  threshold check. Using `u64` keeps accumulation as native 64-bit integer addition
  with no field modular reduction. The threshold comparison (`total_cost <= T`) is a
  native u64 range check costing ~64 boolean gates regardless of N. Using `Field` would
  require a more expensive in-field range decomposition; using `u32` would silently
  overflow for large graphs with high edge weights.

- `siblings: [Field; N * DEPTH]` — Sibling hashes are Poseidon2 outputs, which are
  elements of BN254's prime field. They must be `Field` to be passed directly into
  `Poseidon2::hash`. There is no integer type wide enough to hold a 254-bit field
  element.

- `path_bits: [bool; N * DEPTH]` — Path directions are binary. Declaring them `bool`
  costs zero extra gates for the conditional in Group 3 (the compiler generates a
  selector constraint, not a multiplication).

- `root: pub Field` — Poseidon2 output; must match the type of `siblings`.

- `threshold: pub u64` — Must match `edge_costs` type so the comparison
  `total_cost <= threshold` is a native u64 operation.

### 3.3 Cost matrix representation: flat-full vs flat-Merkle

Two strategies for representing the N×N cost matrix in the circuit:

**Flat-full.** All N² edge costs are passed as public inputs (type `u64`). Group 3 is
a direct indexed lookup: `cost = cost_matrix[cycle[i]][cycle[j]]`. This is simple and
requires no hash infrastructure, but costs ~7.25 UltraHonk gates per public input,
making the dominant term 7.25·N² gates — quadratic in N.

**Flat-Merkle.** The verifier holds a single Poseidon2 Merkle root committing to the
flattened N×N matrix. The prover supplies, for each of the N cycle edges, a Merkle
membership proof: the edge cost (a leaf value) and a path of DEPTH sibling hashes
up to the root. Group 3 verifies each proof and simultaneously checks that the leaf
index encoded in the path bits equals the expected matrix position cycle[i]·N +
cycle[j]. The latter check (the *leaf index check*) is the soundness-critical step:
without it, a prover could substitute a valid Merkle proof for a different leaf
carrying a more convenient cost value.

The Merkle tree depth is DEPTH = ⌈log₂(N²)⌉. Group 3 costs N·DEPTH Poseidon2 hash
calls, giving O(N·log N) total — asymptotically better than flat-full, though the
constant matters (Section 4.3).

The Merkle witnesses (edge costs, sibling hashes, path direction bits) are computed
off-circuit by a dedicated Rust binary that uses the same Poseidon2 implementation as
Barretenberg, ensuring hash compatibility. This was cross-validated explicitly before
benchmarking.

### 3.4 Permutation check strategies (Groups 1+2)

Four strategies are implemented for the flat-full variants. All produce the same
soundness guarantee; they differ only in gate count and witness requirements.

| Strategy | Permutation mechanism | Marginal gates | Extra witness |
|---|---|---|---|
| Pairwise | Assert cycle[i] ≠ cycle[j] for all i≠j via modular inverse | +N·(N-1) | none |
| Sort | Sort cycle, assert equals [0..N-1] via `check_shuffle` | ~3N ROM lookups | none |
| InvPerm | Explicit inverse permutation; assert cycle[inv[v]] = v | ~2N ROM lookups | inv_perm array |
| Presence | Boolean mark array `seen`; assert seen[cycle[i]]=false, set true | ~4N RAM ops | none |

The pairwise strategy is included as an upper-bound baseline. Sort and invperm are the
most gate-efficient O(N) strategies. Presence uses dynamic RAM operations
(UltraHonk lookup tables) and adds no extra witness, making it the pragmatic choice.

Only presence is combined with the Merkle representation, because the permutation check
contributes less than 0.2% of total circuit size in that variant (Section 4.2).

### 3.5 Hash function: Poseidon2

Poseidon2 is a ZK-optimised sponge hash with an algebraic structure designed for
prime-field arithmetic circuits. Its S-box is a low-degree polynomial (x⁵ over BN254),
making each S-box evaluation a small number of multiplication constraints — unlike
SHA-256, which requires ~28,000 gates per call due to bitwise decomposition.

In UltraHonk specifically, Plookup lookup tables reduce the Poseidon2 execution trace
further. The empirical cost is ~87 gate rows per hash call (Section 4.3), versus the
~264 arithmetic gate count commonly cited in the literature. The discrepancy is a
methodological finding of this study and is discussed in Section 5.

### 3.6 Design alternatives considered and rejected

The permutation check strategies (Section 3.4) are explicitly compared because they
represent a genuine design space where the trade-offs are non-trivial. For the remaining
constraint groups, there are also alternatives — but each was ruled out for concrete
reasons. This section records those decisions explicitly, both for transparency and
because a thesis examiner will ask.

**GROUP 1 — Range check: no meaningful alternative.**

The explicit `assert(cycle[i] < N)` loop is the minimum necessary check for pairwise
and presence variants. The only alternative is to fold the range check into GROUP 2:
sort and invperm do this implicitly (sorting forces values into [0,N-1]; invperm's ROM
lookup fails on out-of-range indices), which is why those variants mark GROUP 1 as
"subsumed." For uniformity and explicitness, GROUP 1 is kept as a separate named check
in all variants. The cost is N cheap comparisons — negligible. Relying on implicit array
bounds enforcement in Noir was rejected because the failure mode would be an
unstructured constraint violation rather than a named assertion, making the soundness
argument harder to read and audit.

**GROUP 3 (flat-full) — Direct public input lookup: alternatives all worse.**

Three alternatives were considered:

- *Polynomial encoding.* Represent the cost matrix as a multilinear polynomial and
  evaluate it at `(cycle[i], cycle[j])` in-circuit. This costs O(N) multiplications per
  edge, O(N²) total — same asymptotic order as the public input approach with a larger
  constant and more circuit complexity. No benefit.

- *In-circuit lookup table (Plookup).* Build the N×N matrix as a UltraHonk native
  lookup table. This requires O(N²) table entries — the same total information as public
  inputs — with the overhead of the lookup argument on top. More expensive, not less.

- *Private matrix with off-circuit commitment check.* Make the matrix private and have
  the verifier check an external commitment outside the circuit. This breaks soundness:
  the circuit no longer enforces that the claimed costs match anything the verifier
  agreed on. Not sound.

The direct public input lookup is optimal for the flat-full case. The only legitimate
alternative — replacing the N² public inputs with a compact commitment — is the
flat-Merkle variant, which is a different circuit design, not a different Group 3
implementation.

**GROUP 3 (flat-Merkle) — Poseidon2 Merkle proof: three alternatives considered.**

- *Verkle tree.* A Verkle tree replaces hash-based internal nodes with polynomial
  commitment openings, allowing a single short proof to certify multiple leaves
  simultaneously. This would reduce the dominant cost from O(N·DEPTH) to closer to
  O(N) total, an asymptotic improvement. The reason it was not used: Verkle trees are
  not supported in Noir's standard library, and implementing an in-circuit polynomial
  commitment verifier from scratch is a substantial engineering task with a payoff only
  visible above N ≈ 500, beyond the current benchmark range. It is the right long-term
  direction for large N and is noted as a future extension.

- *Batched multi-opening.* Some polynomial commitment schemes support proving multiple
  openings in a single aggregated proof (e.g., via random linear combination). This
  would similarly reduce the per-edge cost. Same obstacle as Verkle trees: not available
  as a primitive in the current Noir/Barretenberg stack.

- *Leaf domain separation.* Hash `Poseidon2(leaf_idx, cost)` as the leaf value rather
  than storing `cost` directly. This would make the leaf index check in step a
  redundant — the leaf index is baked into the hash, so a proof for the wrong leaf
  produces a different leaf hash and fails automatically. This was considered and
  explicitly rejected: the leaf index check costs only O(DEPTH) cheap arithmetic gates
  and keeps the GROUP 3 cost model clean (exactly N·DEPTH Poseidon2 calls). Adding leaf
  domain separation would add N extra Poseidon2 calls — a ~6–11% overhead depending on
  DEPTH — for no soundness benefit given the explicit check already in place.

**GROUP 4 — Threshold check: one meaningful design choice.**

The only substantive alternative is making `total_cost` a public output rather than
keeping it private and asserting it against the threshold inside the circuit. This would
simplify GROUP 4 to a single public output wire — the verifier checks `total_cost <= T`
themselves, outside the proof — saving ~64 range-check gates.

The reason this was rejected: revealing the exact total cost breaks the privacy
guarantee the Merkle variant is designed to provide. In the target deployment
(a logistics company certifying route quality without disclosing the route), the exact
cost is commercially sensitive information. The verifier learns only the boolean claim
"cost ≤ T", not the actual value. Proving optimality — "no cheaper cycle exists" — would
require universally quantifying over all N! cycles and is not expressible as a standard
SNARK statement. The threshold formulation is therefore both the correct privacy-
preserving choice and the only tractable one.

---

## 4. Flat-Merkle Variant: Implementation in Detail

This section gives a full account of how the flat_merkle_presence circuit works — from
the off-circuit Merkle tree construction through the Rust witness builder to the Noir
constraint groups — and concludes with a concrete eight-node walk-through that traces
every number from the cost matrix to the verified root.

### 4.1 Overview

The Merkle variant replaces the N² public cost-matrix inputs of the flat-full circuits
with a single Poseidon2 Merkle root that commits to the same matrix. The verifier knows
only the root (and the threshold T). For every directed edge in the cycle, the prover
supplies a Merkle membership proof — the edge cost and a chain of DEPTH sibling hashes —
and the circuit verifies each proof against the public root. This shifts the dominant
cost from O(N²) public inputs to O(N·DEPTH) hash calls, where DEPTH = ⌈log₂(N²)⌉.

Three components interact: a Python orchestration layer, a Rust witness builder, and
the Noir circuit. Each handles a distinct step of the pipeline.

### 4.2 Merkle tree design and structure

**Leaf layout.** The N×N cost matrix is flattened row-major into a length-N² array:

    flat_matrix[from * N + to]  =  cost of directed edge from → to

This ordering defines the leaf positions in the Merkle tree. Leaf at position k (0-indexed)
stores the value `flat_matrix[k]` as a BN254 field element.

**Padding.** The Merkle tree requires a number of leaves that is a power of two.
If N² is already a power of two (e.g., N=8, N²=64) no padding is needed. Otherwise
the leaf array is padded with zeros to `n_padded = next_power_of_two(N²)`. Padded
leaves contribute to the tree structure but are never referenced by any Merkle proof
in a valid circuit execution.

**Tree depth.** The number of hashing levels is:

    DEPTH = ⌈log₂(N²)⌉ = (N² − 1).bit_length()    [Python]
          = next_power_of_two(N²).trailing_zeros()   [Rust]

For N=8: DEPTH=6. For N=50: DEPTH=12. For N=500: DEPTH=18. Both formulas give the
same result and are used verbatim in the Python orchestration and Rust builder
respectively, guaranteeing consistency across the pipeline.

**1-indexed array storage.** The tree is stored in a flat array `nodes[1..2·n_padded]`
(index 0 is unused) following the standard heap layout:

    nodes[1]           = root
    nodes[2i], nodes[2i+1]  = left and right children of nodes[i]
    nodes[n_padded .. 2·n_padded − 1]  = leaves (leaf k at nodes[n_padded + k])

**Bottom-up construction.** The tree is built by the Rust builder in a single bottom-up
pass. Leaves are filled directly from `flat_matrix`. Internal nodes are computed
level by level from leaves to root:

    for i in (1 ..= n_padded − 1).rev():
        nodes[i] = Poseidon2([nodes[2i], nodes[2i+1]])

The Poseidon2 call used throughout is `hash([left, right], 2)`, which initialises the
sponge state as `[left, right, 0, iv]` where `iv = 2 · 2⁶⁴` (the UltraHonk domain
separator for two-input hashing), applies one Poseidon2 permutation, and returns
`state[0]`. This matches the `Poseidon2::hash([l, r], 2)` call in the Noir circuit
exactly, ensuring that a root computed off-circuit in Rust verifies on-circuit in Noir.

**Merkle proof extraction.** For an edge from→to with leaf index `k = from·N + to`,
the proof consists of DEPTH (sibling, direction) pairs, extracted by walking from leaf
to root:

    pos = n_padded + k
    for d in 0..DEPTH:
        is_right_child = (pos % 2 == 1)
        sibling        = nodes[pos XOR 1]    // flips the last bit: neighbour in parent
        path_bits[d]   = is_right_child
        siblings[d]    = sibling
        pos            = pos / 2             // move to parent

The path bits use an **LSB-first convention**: `path_bits[d] = true` means the current
node is the right child of its parent at level d. This encoding is chosen so that the
leaf index can be reconstructed by a simple accumulator:

    leaf_idx = Σ  path_bits[d] · 2^d   for d = 0..DEPTH−1

### 4.3 Data pipeline

The pipeline has five stages, illustrated below for the flat-Merkle variant:

```
[1] instance_gen.py
    Generates a random N×N cost matrix and stores it as flat_matrix[0..N²−1].

[2] solver.py
    Runs nearest-neighbour + 2-opt. Returns a Hamiltonian cycle and its total cost.

[3] merkle_builder  (Rust binary)
    Input (stdin):  JSON {n, flat_matrix, cycle, threshold, cost}
    Actions:
      a. Build Merkle tree (n_padded leaves, bottom-up Poseidon2 hashing).
      b. For each of the N cycle edges: extract proof (DEPTH siblings, DEPTH path bits).
      c. Compute root = nodes[1].
    Output (--out path): Prover.toml with all private and public inputs.

[4] nargo compile + nargo execute
    Patches global N and global DEPTH in src/main.nr to match the instance size.
    Recompiles the circuit. Executes with Prover.toml to generate the witness file.

[5] bb prove + bb verify
    Barretenberg reads the witness and circuit to produce a proof.
    Verifier.toml contains only root and threshold (the two public inputs).
    Verification checks the proof against Verifier.toml; no other data is needed.
```

The Prover.toml written by the Rust builder has the following structure (abbreviated):

```toml
# PRIVATE — the cycle
cycle = ["0", "1", "2", ..., "N-1"]

# PRIVATE — cost of each cycle edge (N values)
edge_costs = ["10", "12", ..., "13"]

# PRIVATE — Merkle sibling hashes, flat row-major N×DEPTH
# siblings[i*DEPTH + d] is the sibling at level d for edge i
siblings = ["0x0000...0000", "0x1a3f...c2e1", ...]   # N*DEPTH Field elements

# PRIVATE — Merkle path direction bits, flat row-major N×DEPTH
# path_bits[i*DEPTH + d] = true means edge i is right child at level d
path_bits = [true, false, false, ...]   # N*DEPTH booleans

# PUBLIC — Poseidon2 Merkle root of the full N×N cost matrix
root = "0x2c4a...f810"

# PUBLIC — cost upper bound
threshold = "100"
```

The separation of `siblings` and `path_bits` into flat row-major arrays — rather than
nested arrays — is a design requirement of Noir, which does not support
runtime-determined array dimensions. Both are indexed as `array[i * DEPTH + d]` to
access edge i's depth-d value.

### 4.4 The Noir circuit: GROUP 3 in detail

GROUP 3 is the Merkle proof verification loop. For each edge i in 0..N it performs
three sub-steps in sequence.

**Step a: Leaf index check.**

The path bits supplied by the prover must encode the correct leaf index — otherwise the
prover could supply a valid Merkle proof for a *different* leaf (a leaf with a lower
cost) and pass the hash check while misrepresenting the actual edge cost.

```
expected_idx = cycle[i] * N + cycle[(i+1) % N]

reconstructed_idx = 0
pow2 = 1
for d in 0..DEPTH:
    if path_bits[i*DEPTH + d]:
        reconstructed_idx += pow2
    pow2 *= 2

assert(reconstructed_idx == expected_idx)
```

This forces the path bits to be the binary representation of the expected matrix index.
Combined with the hash check in step b, it binds the proof to exactly the leaf
`flat_matrix[from·N + to]` — neither a different leaf nor a forged leaf.

*Note on `(i+1) % N`.* The closing-edge index `cycle[(i+1) % N]` looks like a runtime
modulo operation, but it is not. Both `i` and `N` are compile-time constants in Noir
(the loop is fully unrolled at compile time), so `% N` is resolved statically. The last
iteration is hardwired to index 0 with no modulo gate in the circuit. This is why the
closing edge `cycle[N-1] → cycle[0]` costs no extra gates relative to any other edge.

**Step b: Merkle path verification.**

The prover's claimed edge cost is hashed upward through DEPTH levels using the supplied
siblings. At each level, the path bit selects whether `current` is the left or right
child of the parent:

```
current = edge_costs[i] as Field

for d in 0..DEPTH:
    sibling = siblings[i*DEPTH + d]
    if path_bits[i*DEPTH + d]:
        (left, right) = (sibling, current)   // current is right child
    else:
        (left, right) = (current, sibling)   // current is left child
    current = Poseidon2::hash([left, right], 2)

assert(current == root)
```

The final value of `current` must equal the public input `root`. Since `root` is fixed
by the verifier and Poseidon2 is collision-resistant, the only way for this assertion
to pass is if `edge_costs[i]` equals the genuine value stored at the leaf identified
by `path_bits` — which step a has already forced to be the correct matrix position.

**Step c: Cost accumulation.**

```
total_cost += edge_costs[i]   // (u64 addition, wrapping-free for realistic costs)
```

After the loop, GROUP 4 asserts `total_cost <= threshold`.

### 4.5 Eight-node walk-through

**The instance.** Consider N=8 with the following Hamiltonian cycle and edge costs.
All matrix entries not appearing in the cycle are set to zero for clarity (they exist
in the committed matrix but no Merkle proof references them in this execution).

    Cycle:  0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → (back to 0)

    Edge costs:
      0→1: 10    1→2: 12    2→3:  8    3→4: 15
      4→5: 11    5→6:  9    6→7: 14    7→0: 13

    Total cost: 10+12+8+15+11+9+14+13 = 92  ≤  threshold T = 100  ✓

**Tree parameters.**

    N=8,  N²=64,  n_padded=64 (64 is already a power of two),  DEPTH=6

The tree has 127 nodes (positions 1..127). Leaves occupy positions 64..127:

    nodes[64 + from·8 + to]  =  flat_matrix[from·8 + to]  as Field

For example: nodes[64]=cost(0,0)=0, nodes[65]=cost(0,1)=10, nodes[74]=cost(1,2)=12.

**Leaf index and path bits for all eight cycle edges.**

The leaf index for edge from→to is `from·8 + to`. The six path bits are the LSB-first
binary digits of that index.

    i   from  to   leaf_idx  tree_node  cost  path_bits [d=0..5]
    ─────────────────────────────────────────────────────────────
    0    0     1       1        65        10   [1,0,0,0,0,0]
    1    1     2      10        74        12   [0,1,0,1,0,0]
    2    2     3      19        83         8   [1,1,0,0,1,0]
    3    3     4      28        92        15   [0,0,1,1,1,0]
    4    4     5      37       101        11   [1,0,1,0,0,1]
    5    5     6      46       110         9   [0,1,1,1,0,1]
    6    6     7      55       119        14   [1,1,1,0,1,1]
    7    7     0      56       120        13   [0,0,0,1,1,1]

Leaf index reconstruction check for edge 0 (leaf_idx=1):
    1·2⁰ + 0·2¹ + 0·2² + 0·2³ + 0·2⁴ + 0·2⁵  =  1  =  0·8 + 1  ✓

**Detailed Merkle proof for edge 0 (i=0, from=0, to=1, cost=10).**

The leaf is at tree node 65. The path to the root traverses six parent steps. At each
step, the sibling node is highlighted; all other subtrees are treated as opaque hashes.

```
                          [1]  ← root
                         /   \
                      [2]   *[3]*  ← sibling at d=5
                     /
                  [4]   *[5]*  ← sibling at d=4
                 /
              [8]   *[9]*  ← sibling at d=3
             /
          [16]  *[17]*  ← sibling at d=2
          /
       [32]  *[33]*  ← sibling at d=1
       /   \
  *[64]*  [65]
  cost(0,0)  cost(0,1)
    = 0        = 10  ← leaf (edge 0→1)
```

Walking from leaf to root, the Rust builder records:

    d=0:  pos=65  (right child, pos%2=1)   sibling=nodes[64]=0   parent=32
    d=1:  pos=32  (left child,  pos%2=0)   sibling=nodes[33]     parent=16
    d=2:  pos=16  (left child,  pos%2=0)   sibling=nodes[17]     parent=8
    d=3:  pos=8   (left child,  pos%2=0)   sibling=nodes[9]      parent=4
    d=4:  pos=4   (left child,  pos%2=0)   sibling=nodes[5]      parent=2
    d=5:  pos=2   (left child,  pos%2=0)   sibling=nodes[3]      parent=1

    path_bits = [true, false, false, false, false, false]
    siblings  = [nodes[64], nodes[33], nodes[17], nodes[9], nodes[5], nodes[3]]
              = [0, H(H(c02,c03),H(c04,c05)), ..., H(subtree_right_half)]
    (where cij denotes flat_matrix[i*8+j] and H denotes one Poseidon2 call)

**The Noir circuit execution for this edge.**

GROUP 3, step a (leaf index check):

    expected_idx = 0·8 + 1 = 1
    reconstructed: pow2=1, d=0 → path_bits=true  → reconstructed=1, pow2=2
                            d=1 → path_bits=false → skip,           pow2=4
                            ... (all false) ...
    assert(1 == 1)  ✓

GROUP 3, step b (Merkle path verification):

    current ← 10 as Field                              // start: raw edge cost
    d=0:  sibling=nodes[64]=0
          path_bits[0]=true  → (left,right)=(0, 10)
          current ← Poseidon2([0, 10])                 // = nodes[32]
    d=1:  sibling=nodes[33]
          path_bits[1]=false → (left,right)=(nodes[32], nodes[33])
          current ← Poseidon2([nodes[32], nodes[33]])  // = nodes[16]
    d=2:  sibling=nodes[17]
          path_bits[2]=false → (left,right)=(nodes[16], nodes[17])
          current ← Poseidon2([nodes[16], nodes[17]])  // = nodes[8]
    d=3:  sibling=nodes[9]
          path_bits[3]=false → (left,right)=(nodes[8],  nodes[9])
          current ← Poseidon2([nodes[8],  nodes[9]])   // = nodes[4]
    d=4:  sibling=nodes[5]
          path_bits[4]=false → (left,right)=(nodes[4],  nodes[5])
          current ← Poseidon2([nodes[4],  nodes[5]])   // = nodes[2]
    d=5:  sibling=nodes[3]
          path_bits[5]=false → (left,right)=(nodes[2],  nodes[3])
          current ← Poseidon2([nodes[2],  nodes[3]])   // = nodes[1] = root
    assert(current == root)  ✓

GROUP 3, step c (cost accumulation):

    total_cost += 10   →  total_cost = 10

The same three steps repeat for edges i=1..7, accumulating costs 12, 8, 15, 11, 9, 14,
13. After the loop:

    GROUP 4:  assert(92 <= 100)  ✓

**Soundness illustration.** Suppose the prover tried to cheat on edge 0 by claiming
cost=2 instead of cost=10, while keeping the same path bits.

- Step b would compute `Poseidon2([0, 2])` at d=0 instead of `Poseidon2([0, 10])`,
  producing a different hash for nodes[32], which would propagate to a wrong root.
  The assertion `current == root` would fail.

Alternatively, suppose the prover tried to supply a valid proof for a *different* leaf —
say leaf_idx=0 (cost(0,0)=0) — to claim a cost of 0 for this edge.

- Step a reconstructs `leaf_idx = 0` from the path bits `[false,false,...,false]`.
  The assertion `reconstructed == expected_idx (=1)` would fail.

Both attack vectors are independently blocked. The leaf index check (step a) and the
hash chain check (step b) together make it infeasible for a prover to misrepresent
any edge cost in the Merkle-committed matrix.

### 4.6 Four-node walk-through

The N=4 case has DEPTH=4 and only 16 leaves, so the entire Merkle tree fits in a single
diagram and every hash level can be traced by hand. It makes a cleaner first read than
the N=8 example; the two examples are deliberately redundant so that N=4 builds
intuition and N=8 confirms the pattern scales.

**The instance.**

    N=4,  cycle: 0 → 1 → 2 → 3 → (back to 0)

    Cost matrix (all entries not in the cycle are zero):

           to:   0    1    2    3
    from:  0: [  0,   5,   0,   0 ]
           1: [  0,   0,   3,   0 ]
           2: [  0,   0,   0,   7 ]
           3: [  4,   0,   0,   0 ]

    Cycle edge costs:  0→1:5,  1→2:3,  2→3:7,  3→0:4
    Total cost: 5+3+7+4 = 19  ≤  threshold T=25  ✓

**Tree parameters.**

    N=4,  N²=16,  n_padded=16  (16=2⁴, no padding needed),  DEPTH=4

The tree has 31 nodes (positions 1..31). Leaves at positions 16..31.
The leaf at position 16+k stores flat_matrix[k] = cost(k/4, k%4).

**Complete Merkle tree.**

Every node is shown. H(a,b) means Poseidon2([a, b], 2).

```
Level 0 (root):
  [1] = H([2],[3])

Level 1:
  [2] = H([4],[5])          [3] = H([6],[7])

Level 2:
  [4] = H([8],[9])    [5] = H([10],[11])    [6] = H([12],[13])    [7] = H([14],[15])

Level 3:
  [8]  = H([16],[17])    [9]  = H([18],[19])
  [10] = H([20],[21])    [11] = H([22],[23])
  [12] = H([24],[25])    [13] = H([26],[27])
  [14] = H([28],[29])    [15] = H([30],[31])

Leaves (level 4):
  [16]=c(0,0)=0   [17]=c(0,1)=5   [18]=c(0,2)=0   [19]=c(0,3)=0
  [20]=c(1,0)=0   [21]=c(1,1)=0   [22]=c(1,2)=3   [23]=c(1,3)=0
  [24]=c(2,0)=0   [25]=c(2,1)=0   [26]=c(2,2)=0   [27]=c(2,3)=7
  [28]=c(3,0)=4   [29]=c(3,1)=0   [30]=c(3,2)=0   [31]=c(3,3)=0
```

The root [1] commits to all 16 entries of the cost matrix. The verifier computes this
root from the agreed matrix and holds it as a public input.

**Leaf indices and path bits for all four cycle edges.**

    i   from  to   leaf_idx  node  cost  path_bits [d=0..3]
    ──────────────────────────────────────────────────────────
    0    0     1       1       17     5   [1,0,0,0]
    1    1     2       6       22     3   [0,1,1,0]
    2    2     3      11       27     7   [1,1,0,1]
    3    3     0      12       28     4   [0,0,1,1]

Path bit check for edge 0 (leaf_idx=1):  1·2⁰ = 1  =  0·4+1  ✓
Path bit check for edge 3 (leaf_idx=12): 0·2⁰+0·2¹+1·2²+1·2³ = 4+8 = 12 = 3·4+0  ✓

**Detailed Merkle proof for edge 0 (i=0, from=0, to=1, cost=5).**

Leaf [17] is the right child of [8], which is itself a left child all the way to the
root.

```
                [1]  root
               /   \
            [2]     [3]  ← sibling at d=3
           /
         [4]   [5]  ← sibling at d=2
        /
      [8]   [9]  ← sibling at d=1
      / \
  [16] [17]  ← leaf for edge 0→1 (cost=5)
   ↑
sibling at d=0
(cost(0,0)=0)
```

Walking leaf→root:

    d=0: pos=17  right child (17%2=1)   sibling=nodes[16]=0       parent→8
    d=1: pos=8   left child  (8%2=0)    sibling=nodes[9]=H(0,0)   parent→4
    d=2: pos=4   left child  (4%2=0)    sibling=nodes[5]=H(H(0,0),H(3,0))  parent→2
    d=3: pos=2   left child  (2%2=0)    sibling=nodes[3]=H(H(H(0,0),H(0,7)),H(H(4,0),H(0,0)))  parent→1

    path_bits = [true, false, false, false]
    siblings  = [nodes[16], nodes[9], nodes[5], nodes[3]]
              = [  0,       H(0,0),  H(H(0,0),H(3,0)),  H(...) ]

What each sibling covers:
- nodes[16]: the single cell c(0,0)=0 — a leaf-level neighbour
- nodes[9]:  the pair c(0,2)=0, c(0,3)=0 — the other two outgoing edges from node 0
- nodes[5]:  all four edges out of node 1: c(1,0)..c(1,3) — an entire row subtree
- nodes[3]:  all eight edges out of nodes 2 and 3 — the entire right half of the tree

**Noir GROUP 3 execution for edge 0 (i=0).**

Step a — leaf index check:

    expected_idx = 0·4 + 1 = 1
    pow2=1, d=0: path_bits=true  → reconstructed += 1 → reconstructed=1,  pow2=2
             d=1: path_bits=false → skip,                                   pow2=4
             d=2: path_bits=false → skip,                                   pow2=8
             d=3: path_bits=false → skip
    assert(1 == 1)  ✓

Step b — Merkle path verification:

    current ← 5 as Field                        ← start: raw edge cost
    d=0:  sibling=0  (nodes[16], cost(0,0))
          path_bits[0]=true  → (left,right)=(0, 5)
          current ← H(0, 5)                     = nodes[8]
    d=1:  sibling=nodes[9]=H(0, 0)
          path_bits[1]=false → (left,right)=(nodes[8], nodes[9])
          current ← H(nodes[8], nodes[9])       = nodes[4]
    d=2:  sibling=nodes[5]=H(H(0,0), H(3,0))
          path_bits[2]=false → (left,right)=(nodes[4], nodes[5])
          current ← H(nodes[4], nodes[5])       = nodes[2]
    d=3:  sibling=nodes[3]=H(H(H(0,0),H(0,7)), H(H(4,0),H(0,0)))
          path_bits[3]=false → (left,right)=(nodes[2], nodes[3])
          current ← H(nodes[2], nodes[3])       = nodes[1]  =  root
    assert(current == root)  ✓

Step c — cost accumulation:  total_cost += 5  →  total_cost = 5

**Detailed Merkle proof for edge 3 (i=3, from=3, to=0, cost=4).**

This edge has a more varied path — two left steps then two right steps — which
illustrates how path bits [0,0,1,1] route a different trajectory through the tree.

Leaf [28] is the left child of [14], which is itself a left child of [7], which is a
right child of [3], which is a right child of [1].

```
      [1]  root
     /   \
  [2]     [3]
          /  \
        [6]  [7]
             /  \
          [14]  [15]  ← sibling at d=1
          /  \
       [28]  [29]     ← sibling at d=0 (cost(3,1)=0)
        ↑
    leaf for edge 3→0 (cost=4)
```

Walking leaf→root:

    d=0: pos=28  left child  (28%2=0)  sibling=nodes[29]=0        parent→14
    d=1: pos=14  left child  (14%2=0)  sibling=nodes[15]=H(0,0)   parent→7
    d=2: pos=7   right child (7%2=1)   sibling=nodes[6]=H(H(0,0),H(0,7))  parent→3
    d=3: pos=3   right child (3%2=1)   sibling=nodes[2]            parent→1

    path_bits = [false, false, true, true]
    siblings  = [nodes[29], nodes[15], nodes[6], nodes[2]]

Step a — leaf index check:

    expected_idx = 3·4 + 0 = 12
    pow2=1, d=0: false → skip,              pow2=2
             d=1: false → skip,              pow2=4
             d=2: true  → reconstructed+=4 → reconstructed=4,   pow2=8
             d=3: true  → reconstructed+=8 → reconstructed=12
    assert(12 == 12)  ✓

Step b — Merkle path verification:

    current ← 4 as Field
    d=0:  sibling=nodes[29]=0
          path_bits[0]=false → (left,right)=(4, 0)
          current ← H(4, 0)                   = nodes[14]
    d=1:  sibling=nodes[15]=H(0, 0)
          path_bits[1]=false → (left,right)=(nodes[14], nodes[15])
          current ← H(nodes[14], nodes[15])   = nodes[7]
    d=2:  sibling=nodes[6]=H(H(0,0), H(0,7))
          path_bits[2]=true  → (left,right)=(nodes[6], nodes[7])
          current ← H(nodes[6], nodes[7])     = nodes[3]
    d=3:  sibling=nodes[2]
          path_bits[3]=true  → (left,right)=(nodes[2], nodes[3])
          current ← H(nodes[2], nodes[3])     = nodes[1]  =  root
    assert(current == root)  ✓

**Completing the proof: all four edges.**

The same three steps (leaf index check, hash chain, accumulate) run for each of the
four cycle edges. After the loop:

    Edge 0 (0→1, cost=5):  total_cost = 5
    Edge 1 (1→2, cost=3):  total_cost = 8
    Edge 2 (2→3, cost=7):  total_cost = 15
    Edge 3 (3→0, cost=4):  total_cost = 19

    GROUP 4:  assert(19 <= 25)  ✓

**The Prover.toml for this instance.**

The Rust builder writes the following file (Field values abbreviated to 6 hex digits
for readability; actual values are 64-hex BN254 field elements):

    cycle      = ["0", "1", "2", "3"]                  # private
    edge_costs = ["5", "3", "7", "4"]                  # private

    # siblings: 4 edges × 4 levels = 16 Field values, row-major
    siblings = [
      "0x000000",           # edge 0, d=0: nodes[16] = c(0,0) = 0
      "0x<H(0,0)>",         # edge 0, d=1: nodes[9]
      "0x<H(H(0,0),H(3,0))>", # edge 0, d=2: nodes[5]
      "0x<H(nodes[6],nodes[7])>",# edge 0, d=3: nodes[3]
      "0x<H(3,0)>",         # edge 1, d=0: nodes[23] = c(1,3) = 0  ... (etc.)
      ...
    ]

    # path_bits: 4 edges × 4 levels = 16 booleans, row-major
    path_bits = [
      true,  false, false, false,   # edge 0 (leaf_idx=1  = 0001)
      false, true,  true,  false,   # edge 1 (leaf_idx=6  = 0110)
      true,  true,  false, true,    # edge 2 (leaf_idx=11 = 1011)
      false, false, true,  true,    # edge 3 (leaf_idx=12 = 1100)
    ]

    root      = "0x<nodes[1]>"   # public
    threshold = "25"              # public

The verifier receives only `root` and `threshold`. The 14 remaining fields are private
— the verifier never sees the cycle, the edge costs, or the Merkle witnesses.

---

## 5. Flat Circuit Benchmarks  *(empirical results)*

Benchmarks were run on N ∈ {5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100, 125,
150, 175, 200, 250, 300, 350, 400, 450, 500}, five independent runs per N. Metrics
captured: circuit size (UltraHonk gate rows), ACIR opcode count, compile time, witness
generation time, proving time, verification time, proof size (bytes), and peak memory.

Three variants were benchmarked: flat_full_pairwise, flat_full_sort, and
flat_merkle_presence. The remaining flat_full variants (invperm, presence) are
implemented and correctness-tested; their benchmarks will be added before the final
report to complete the permutation overhead analysis.

### 5.1 Correctness tests

Each variant has an independent correctness test suite (31 tests for flat_merkle, 20+
for each flat_full variant). Tests cover valid and invalid inputs across all four
constraint groups: range violations (Group 1), duplicate nodes (Group 2), tampered edge
costs and Merkle proofs (Group 3), and threshold violations (Group 4). All test suites
pass.

### 5.2 Circuit size: flat-full variants

The circuit size of flat-full variants is exactly quadratic in N, confirmed by
polynomial regression with R² = 1.000 in all cases.

| Variant | Fit: circuit_size | Coefficient a | Theory |
|---|---|---|---|
| flat_full_pairwise | 8.250·N² + 14.5·N + 2829 | 8.250 | 7.25 + 1.00 = 8.25 ✓ |
| flat_full_sort | 7.250·N² + 26.5·N + 2829 | 7.250 | 7.25 ✓ |

The N² coefficient decomposes cleanly: 7.25 gates per public u64 input (the cost matrix
dominates) plus 1.00 for the pairwise multiply gates in the pairwise variant. The sort
variant's permutation check contributes only to the linear term, confirming that the
cost matrix representation alone drives the quadratic scaling.

At N = 500: pairwise reaches 2,072,578 gates; sort reaches 1,828,579 gates. The
difference (≈14% at N=500) shrinks in proportion as N grows, since both share the
same 7.25·N² base.

[FIGURE 1: Circuit size vs N for all three benchmarked variants, linear axes. Solid
lines = quadratic fit (flat_full), dashed line = N·log N fit (flat_merkle). The
quadratic fits are visually exact.]

### 5.3 Circuit size: flat_merkle and the crossover

The flat_merkle_presence circuit size grows as N·DEPTH, where DEPTH = ⌈log₂(N²)⌉.
A quadratic fit returns a ≈ 0 (as expected — no N² public inputs), while the dominant
term is revealed by computing gates per (N·DEPTH):

| N | DEPTH | gates / (N·DEPTH) |
|---|---|---|
| 50 | 12 | 91.85 |
| 100 | 14 | 88.95 |
| 200 | 16 | 87.67 |
| 350 | 17 | 87.20 |
| 500 | 18 | 86.98 |

The ratio converges to **~87 gates per (edge × Merkle level)** — the empirical
Poseidon2 cost in UltraHonk. This is approximately 3× lower than the ~264 arithmetic
gates per call commonly cited in the ZK-hash literature. The difference is attributable
to UltraHonk's Plookup mechanism: rather than encoding the Poseidon2 S-box as
arithmetic constraints, UltraHonk uses pre-computed lookup tables, reducing the number
of execution trace rows needed.

This discrepancy has a direct consequence for the crossover prediction. Using the
theoretical ~264 gates/call, the predicted crossover between flat_full_sort and
flat_merkle_presence is:

    7.25·N ≈ 264·DEPTH  →  N ≈ 695

Using the empirically measured ~87 gates/call:

    7.25·N ≈ 87·DEPTH  →  N/log₂(N) ≈ 24  →  N ≈ 175

The empirical data confirms the corrected prediction:

| N | flat_full_sort | flat_merkle | Difference |
|---|---|---|---|
| 150 | 169,929 | 198,249 | sort cheaper |
| 175 | 229,497 | 230,817 | **≈ 0 (crossover)** |
| 200 | 298,129 | 280,537 | merkle cheaper |
| 500 | 1,828,579 | 782,837 | merkle 2.3× cheaper |

The crossover occurs at N ≈ 175, squarely within the benchmark range. At N = 500,
flat_merkle is 2.3× smaller in circuit size and therefore faster and cheaper to prove.

[FIGURE 2: Crossover figure — flat_full_sort vs flat_merkle_presence circuit size,
benchmark range N=[5,500] left panel, extrapolation to N=1000 with crossover
annotation right panel.]

### 5.4 Verification time

Verification time is the sharpest differentiator between flat-full and flat-Merkle,
and it reveals a subtlety in the "O(1) verification" claim commonly attributed to
SNARKs.

The O(1) claim applies to the proof-checking computation — verifying a polynomial
evaluation against a constant-size proof. It does not apply to processing public inputs.
The verifier must hash and incorporate every public input before performing the proof
check. With N² public inputs in flat-full variants, verification cost grows with N²
in practice.

| N | flat_full_pairwise | flat_full_sort | flat_merkle |
|---|---|---|---|
| 5 | 0.009 s | 0.009 s | 0.009 s |
| 50 | 0.018 s | 0.018 s | 0.009 s |
| 100 | 0.069 s | 0.070 s | 0.015 s |
| 200 | 0.197 s | 0.203 s | 0.015 s |
| 300 | 0.377 s | 0.377 s | 0.014 s |
| 500 | 0.900 s | 0.897 s | **0.015 s** |

flat_merkle verification is constant at ≈ 15 ms regardless of N, because it has only
two public inputs (root and threshold). flat_full verification reaches ~0.9 s at N=500
— a 60× difference. In any deployment where verification is repeated (multiple verifiers,
frequent auditing), this asymmetry is more significant than the proving-time crossover.

Proof size is constant at **14,656 bytes** for all variants at all N, confirming the
expected UltraHonk property.

[FIGURE 3: Verification time vs N. flat_full variants grow visibly; flat_merkle is a
flat line at ≈ 15 ms across the full range.]

### 5.5 Proving time, memory, and compile time

**Proving time.** Empirically, prove_time ∝ C^0.92 for both flat_full_sort and
flat_merkle_presence, where C is circuit size. UltraHonk theory predicts O(C log C).
The empirical exponent is slightly below linear because log₂(C) grows by only ≈ 1.6×
across the full benchmark range (N = 5 to 500), making the log factor effectively
absorbed into the constant at this scale. Proving time is therefore a reliable proxy
for circuit size across the benchmark range.

At N = 500: flat_full_sort proves in ≈ 21 s; flat_merkle_presence in ≈ 12 s.

**Peak memory.** Memory scales as N^1.75 for flat_full variants (consistent with
quadratic circuit size) and as N^1.06 for flat_merkle (nearly linear, consistent with
O(N log N) circuit size). At N = 500: flat_full_sort requires ≈ 2.6 GB; flat_merkle
requires ≈ 1.1 GB. The quadratic memory growth of flat_full places a practical limit on
how far the range can be extended without hardware changes.

**Compile time.** flat_full_sort compiles in ≈ 2.4 s at N = 500; flat_full_pairwise
takes ≈ 10.3 s. The pairwise compilation overhead reflects the O(N²) constraint
structure, which creates significantly more work for the Noir constraint optimiser.
flat_merkle_presence compiles in ≈ 4.5 s at N = 500.

[FIGURE 4: Proving time and peak memory vs N for all three variants.]

---

## 6. Key Findings

**Finding 1 — Circuit size models are exact for flat-full.**
The theoretical prediction of 7.25·N² gates (from the cost of N² public u64 inputs in
UltraHonk) is confirmed to four decimal places. The quadratic scaling is structurally
determined by the choice to pass the cost matrix as public inputs, not by the
permutation check strategy.

**Finding 2 — Poseidon2 costs ~87 gates/call in UltraHonk, not ~264.**
The commonly cited arithmetic gate count for Poseidon2 (~264) overestimates the actual
UltraHonk execution trace cost by a factor of ~3, because UltraHonk's Plookup mechanism
amortises the S-box evaluations via lookup tables. This has a direct practical
consequence: the crossover between flat-full and flat-Merkle in circuit size occurs at
N ≈ 175 rather than the theoretically predicted N ≈ 695.

**Finding 3 — The empirical crossover is at N ≈ 175.**
flat_merkle_presence becomes cheaper than flat_full_sort in circuit size — and therefore
in proving time and memory — at approximately N = 175. At N = 500, flat_merkle is 2.3×
smaller. This crossover is now empirically established and can serve as a calibration
point for extrapolating the hierarchical-vs-flat crossover.

**Finding 4 — ACIR opcode count is a misleading complexity proxy for hash-heavy circuits.**
The ACIR opcode-level crossover between flat-full and flat-Merkle occurs at N ≈ 30
(Poseidon2 = 1 ACIR BlackBox opcode, same as one public input). The gate-level crossover
is at N ≈ 175. The 6× discrepancy arises because Poseidon2 expands to ~87 gates per
ACIR call while public inputs expand to ~7.25 gates each. Any benchmarking study that
uses ACIR opcode count as a proxy for proving cost in hash-heavy circuits will
systematically misestimate crossover points.

**Finding 5 — Verification time is O(N²) for flat-full, O(1) for flat-Merkle.**
The 60× verification time advantage of flat_merkle at N = 500 (15 ms vs 900 ms) is not
a proving-time effect — it results from the verifier needing to process N² public inputs
in flat-full. For any use case involving repeated verification (multiple verifiers,
auditing at scale), this asymmetry makes the Merkle variant strictly preferable above
N ≈ 50, well before the circuit-size crossover at N ≈ 175.

**Finding 6 — Hierarchical Merkle does not reduce total gate count *(analytical result, planning phase)*.**
Gate-count analysis of the hierarchical Merkle design (K segment sub-circuits plus a
glue circuit) shows the total cost is `(N + K) × DEPTH × 87 + O(N)` — strictly larger
than flat_merkle's `N × DEPTH × 87 + O(N)`. The K boundary Merkle proofs and the O(N)
partition check in the glue exactly absorb any per-segment saving. The dominant Merkle
hashing work is invariant under decomposition: every cycle edge requires one Merkle
proof regardless of how the cycle is partitioned. At N = 500, K = 4 the overhead is
approximately 1.5%. The structural reason this finding holds is developed in Section 7.

**Finding 7 — Hierarchical flat_full saves gates by trading privacy *(analytical result, planning phase)*.**
The flat_full variant's dominant cost is N² public-input encoding (~7.25 gates per
matrix entry). Splitting flat_full hierarchically with K segments, each taking its
M × M sub-matrix as public input, reduces total public-input cost from O(N²) to
O(N²/K). At N = 500 this crosses below flat_merkle at K ≥ 3 and continues to fall
linearly with K. The currency paid is verifier-side disclosure of the partition (which
M nodes belong to which segment) and of the per-segment sub-matrices — privacy that
flat_merkle preserves. Hierarchical flat_full and flat_merkle therefore occupy distinct
points on a privacy ↔ cost frontier and neither dominates the other.

**Finding 8 — Hierarchical decomposition gives embarrassingly-parallel speedup, not
algorithmic speedup.**
Although hierarchical Merkle does not reduce total gates (Finding 6), the K sub-proofs
are independent and can be generated in parallel. With K parallel workers, wall-clock
proving time scales as `proving_time(N/K) + glue` — approximately K-fold speedup.
Per-prover peak memory scales as `memory(N/K)` — a ~K-fold reduction per process.
Crucially, the total work summed across the K workers is *the same* as (or slightly
greater than) a single flat_merkle proof — the parallelism is embarrassingly parallel,
not algorithmic. This distinction matters for the cross-domain comparison with
optimisation: classical hierarchical TSP heuristics provide algorithmic speedup (the
search space genuinely shrinks); hierarchical ZK does not. The benefit is enabling
proofs that would otherwise exhaust a single machine's memory, not making feasible
proofs cheaper in absolute work. This is the operational restatement of the dualism
developed in Section 7.

**Finding 9 — In-circuit Fiat-Shamir restores partition privacy at ~5% gate overhead *(analytical result, planning phase)*.**
A hierarchical Merkle variant using a grand-product partition argument combined with
in-circuit Fiat-Shamir (challenge `X` derived from a hash chain over the cycle, jointly
enforced by the K sub-circuits and the glue) reduces verifier-side bit-leakage from
~N·log K (full partition disclosure of Variant A) to ~2K·log N (only segment endpoints
plus Field-valued aggregates). The sub-circuit pays approximately M additional Poseidon2
calls for the hash-chain binding, which is `~1/DEPTH` of the existing internal Merkle
cost — ~5.5% sub-circuit overhead at N=500. The glue partition check simultaneously
drops from O(N) sort to O(K) multiplications. Soundness rests on standard Fiat-Shamir
and Schwartz-Zippel arguments (~`2^-254` collision probability). This becomes a third
design point — Variant A++ — sitting strictly between Variants A and B on the
privacy ↔ cost frontier.

**Finding 10 — Hierarchical variants are not optimisations of flat_merkle; they prove
different statements *(reframe finding, planning phase)*.**
The crossover framing — "at what N does hierarchical beat flat?" — implicitly assumes
hierarchical and flat are alternative proof designs for the same statement. They are
not. Flat Merkle proves "I know a Hamiltonian cycle with cost ≤ T against the committed
matrix." Variant A proves "I know a Hamiltonian cycle with cost ≤ T against the
committed matrix that respects this disclosed partition." Variant A++ proves "I know a
Hamiltonian cycle with cost ≤ T against the committed matrix that decomposes into K
segments of M nodes each, with the per-segment cost contributions disclosed but the
segments themselves hidden." Variant B proves "... that respects this disclosed
partition, with these disclosed M×M sub-matrices." Each is a strictly more specific
statement than flat_merkle, with extra structure exposed to the verifier. The privacy
loss is therefore not a bug to be minimised; it is the *content* of the statement being
proved. The variant-as-statement reframe makes the privacy/cost trade-off explicit and
matches each variant to a class of use cases (Finding 11, Section 7.7).

**Finding 11 — Each variant has a natural use-case class, and no variant is universally
best.**
The variant-as-statement reframe yields a clean mapping between variants and real-world
scenarios. The full mapping is developed in Section 7.7; the headline pairings:

- **flat_merkle** — generic baseline; logistics SLA auditing or ESG reporting where
  the route is the only secret and the partition is not part of the audit.
- **Variant A** — multi-team / multi-region accountability where the partition itself
  is an operational artifact (delivery zones, team assignments). Disclosure is
  intentional. Parallelism and per-prover memory reduction are operational wins.
- **Variant A++** — same scaling benefits as A but with the partition hidden from the
  verifier. Appropriate when the K-fold decomposition is operationally meaningful but
  the specific partition reveals competitive information.
- **Variant B** — public-matrix scenarios (smart-city fleet routing on OSM data, public
  benchmarks) where matrix privacy is irrelevant and total prover cost is the binding
  constraint.

The "no universally best" property is a *consequence* of the variant-as-statement
reframe (Finding 10): variants proving different statements cannot be totally ordered.

---

## 7. Cross-Domain Perspective: A Structural Dualism

This thesis sits at the intersection of two computational tasks on the same problem
class. A parallel project studied hierarchical (clustered) heuristic solvers for TSP,
where the same decomposition question arises: at what N does splitting the problem into
K clusters of N/K nodes each outperform solving the full N-node instance?

The structural analogy looks tight at first glance — both contexts split a global
problem into local pieces and combine the results. But closer analysis reveals an
asymmetry that runs in opposite directions:

> **Hierarchical decomposition adds a structural constraint in optimisation and weakens
> a soundness constraint in zero-knowledge proving. Same operation, opposite direction
> in constraint space, opposite effect on cost.**

This dualism is the central conceptual finding of the thesis's planning phase. It
explains why Findings 6–8 hold and why the experimental programme is reframed around a
multi-axis frontier rather than a single crossover.

### 7.1 Optimisation: decomposition adds a constraint, shrinks search

In heuristic optimisation, splitting an N-node TSP into K clusters of N/K nodes each
imposes the constraint *"the tour respects this partition"*. Adding the constraint
shrinks the search space from N! orderings (over all permutations of N nodes) to
roughly K · ((N/K)!) · K! orderings (over the K intra-cluster orderings and the K
inter-cluster orderings of cluster representatives). For K = √N this collapses the
search by a super-polynomial factor.

The added constraint is *paid for* by losing access to tours that violate it — the
approximation error of clustered TSP. Speedup and quality loss are two sides of the
same added constraint.

### 7.2 ZK proving: decomposition weakens a constraint, forces glue restoration

In zero-knowledge proving, splitting the N-node Hamiltonian-cycle proof into K segment
proofs weakens the constraint *"every node visited exactly once globally"* to K weaker
constraints *"every node visited exactly once within this segment"*. The weakened
form is unsound: a cheating prover under K independent segment proofs could place node
v in two different segments and pass every local check.

To restore soundness, a global partition check must be added in the glue circuit — sort
the K · M = N segment node outputs and assert they equal `{0,…,N-1}`. This restoration
costs O(N) gates, which precisely cancels the per-segment saving from verifying smaller
permutations. Add K boundary Merkle proofs for the segment-connecting edges, and the
hierarchical Merkle design has the same total gate count as flat Merkle plus a small
overhead — exactly Finding 6.

The contrast is structural:

| | Optimisation | ZK proving |
|---|---|---|
| Cost lives in | Searching a combinatorial space | Re-checking a fixed witness |
| What decomposition does | Adds a constraint, shrinks search space | Weakens a constraint, forces restoration in glue |
| Cost effect | Cheaper (search pruned) | Same or worse (work merely relocated) |
| Currency paid | Solution quality (approximation error) | Verifier privacy (segment partition disclosed) |

### 7.3 Why the dualism exists: NP asymmetry under decomposition

The two domains pay different bills. Optimisation cost is dominated by *searching* over
orderings; ZK cost is dominated by *re-checking* a single witness already known to the
prover. Hierarchical decomposition is a search-pruning trick, and search is precisely
what ZK does not do.

The deeper reason is a refinement of the NP asymmetry between *finding* and *checking*.
The standard statement of NP asymmetry — finding is (believed to be) exponentially
hard, checking is polynomial — holds in both classical and ZK settings. What is *not*
preserved across the two settings is the way each side responds to decomposition:

> **Hierarchical decomposition exploits NP asymmetry by trading verification work for a
> dramatic reduction in search work. In classical optimisation this trade is a strict
> win, because reducing exponential search by a polynomial verification overhead is
> always worth it. In ZK proving, the trade has nothing to redeem on the search side —
> the prover already has the witness — so the verification overhead is paid without any
> compensating saving. The asymmetry persists; the strategy that exploits it does not
> transfer.**

This is not the same as claiming "ZK checking is harder than ZK finding." Verification
remains cheap; what changes is that hierarchical decomposition is no longer a *useful*
strategy in the ZK setting because the search-side savings it produces have no analogue
when the prover is generating a proof from a known witness rather than searching for
one. Decomposition becomes pure overhead in ZK (Finding 6) unless it is also used to
disclose structure to the verifier (Finding 7) or to enable parallel work-sharing
(Finding 8) — neither of which is an algorithmic improvement.

Several corollaries follow from this refined view:

- **Algorithmic vs embarrassingly-parallel speedup.** Classical hierarchical TSP gives
  *algorithmic* speedup: total work decreases super-polynomially as K grows. Hierarchical
  ZK gives only *embarrassingly-parallel* speedup: total work stays roughly constant,
  but it can be distributed across K machines (Finding 8). The two are different things
  and conflating them is the source of much practitioner confusion about ZK scaling.

- **Approximation has no ZK analogue.** Heuristic optimisation can trade quality for
  speed because a near-optimal tour is still useful. ZK has no equivalent — a partially
  verified cycle is simply unverified. Hierarchical's quality/speed trade-off does not
  port to ZK.

- **Constraints have flipped sign across the two domains.** Adding a constraint in
  optimisation makes the problem cheaper (smaller search space); adding a constraint in
  ZK makes the proof more expensive (more assertions). The word "constraint" denotes
  opposing economic forces in the two contexts.

- **Hierarchical ZK works well only for locally-factoring problems.** Circuit-SAT
  factors locally (each gate is independently checkable), and recursive proof systems
  over circuit-SAT (Halo, Nova, ProtoStar) work well precisely because the global
  property *is* the conjunction of local properties. Hamiltonian-cycle is the opposite
  extreme — the constraint "visit every node exactly once" is intrinsically global and
  refuses to factor. TSP is therefore a worst-case problem class for hierarchical ZK,
  which is itself a useful framing for this thesis.

- **The ZK verifier cannot assist the prover.** In optimisation, "guess-and-check" can
  speed search because the checker accepts or rejects with useful feedback. The ZK
  verifier can only output {accept, reject} after a complete proof is generated; it
  cannot iteratively guide the prover. The asymmetric guess/check dynamic that powers
  metaheuristics has no ZK analogue.

- **A predictive heuristic for proof-system design.** Given a new problem class, ask
  first: *does this problem factor locally?* If yes, hierarchical/recursive ZK is a
  good fit and folding schemes will pay off. If no, hierarchical ZK is at best a
  scaling strategy (memory, wall-clock) and never an algorithmic improvement; the
  search-side wins of classical decomposition will not appear.

### 7.4 Implications for the experimental programme

The structural dualism dictates the shape of the next phase. The naive question — "at
what N does hierarchical beat flat?" — pre-supposes that hierarchical is uniformly
better and we need only locate the crossover. The dualism shows this pre-supposition is
unfounded: hierarchical Merkle cannot beat flat Merkle on total gate count, and
hierarchical flat_full can beat it only by surrendering verifier-side privacy. The
genuine benefits live in dimensions the original framing did not measure — parallel
wall-clock time and per-prover memory — and the privacy losses, properly recognised,
are not bugs but content of a stricter statement (Finding 10).

The hierarchical experimental programme is therefore framed as mapping a frontier in
(total gate count, parallel proving time, per-prover memory, verifier privacy) space,
not as locating a crossover on a single axis. Three variants are planned (see
Section 8):

- **Variant A** — Merkle baseline with sorted segment node sets publicly exposed. Simple
  partition check via sort; verifier learns the partition.
- **Variant A++** — Merkle with a grand-product partition check and in-circuit
  Fiat-Shamir (challenge bound to a hash-chain commitment of the global cycle, jointly
  enforced by the K sub-circuits and the glue). Hides interior nodes; verifier learns
  only segment endpoints and Field-valued aggregates. ~5.5% sub-circuit overhead vs A;
  glue partition drops from O(N) to O(K). (See Finding 9.)
- **Variant B** — flat_full with public per-segment sub-matrices. Lowest total gates of
  the three for K ≥ 3, paid for in full partition + sub-matrix disclosure.

Each occupies a distinct point on the privacy ↔ cost frontier with a clear structural
reason for its position, and each is the natural design for a distinct use-case class
(Section 7.7).

**Implementation status and headline empirical result (2026-05-28).** Variants A and
A++ are implemented and benchmarked over the full grid N ∈ {48, 96, 192, 480},
K ∈ {2, 4, 8}, 3 runs per cell; all K+1 cross-checks pass on every cell of both
sweeps. The frontier prediction is confirmed where it matters most — **per-prover
memory**. Variant A's glue carries an O(N) sort whose footprint grows with N; A++
replaces it with an O(N) grand-product loop plus an O(1) public-input pool, and the
measured glue peak memory is essentially flat:

| N (K=8) | A glue peak | A++ glue peak |
|---|---|---|
| 48 | 39 MB | 38 MB |
| 192 | 54 MB | 38 MB |
| 480 | **159 MB** | **42 MB** |

At N=480, A's glue (159 MB) is the per-prover memory ceiling — as large as the
sub-circuit itself; A++'s glue (42 MB) falls well below its sub-circuit (160 MB), so
the ceiling is set by the segment proof alone. This is the concrete "A++ for
memory-constrained provers" result. The sub-circuit overhead from the three added
constraint groups (hash-chain link, grand product, challenge consistency) measures
**+6.7% gates** at N=8 (vs the ~5.5% planning estimate), consistent with the
chain-dominated overhead. Variant B remains unimplemented (see below for whether it
is still worth implementing).

### 7.5 Folding schemes as a future direction

Recent proof systems (Nova, ProtoStar, SuperNova) are explicitly designed to address
the hierarchical / recursive setting. They fold K instances into one with a
constant-cost folding step, sidestepping the per-recursion verifier overhead that
limits naive recursive SNARKs. That overhead is no longer hypothetical here: Section
7.8 *measures* it at ~704k gates per in-circuit UltraHonk verification (~K× for K
segments), so a folding implementation has a concrete number to beat. The gate-count
analysis in this thesis is the UltraHonk baseline any folding-scheme implementation
would need to improve on for TSP. Implementing a folding-scheme variant is out of scope
for this thesis but is the natural continuation: it would test whether the dualism is
intrinsic to the problem class or a property of the proof system in use.

### 7.6 Combined-pipeline synthesis

The empirical results from the heuristic optimisation study — crossover N, quality
degradation curves, cluster size sensitivity — will be presented alongside the ZKP
frontier in a final chapter. The dualism makes a sharp prediction: the two crossover
behaviours differ in direction, not just in magnitude. Joint empirical measurement
tests this prediction and characterises the combined solve-then-prove pipeline when
both decompositions are applied simultaneously.

### 7.7 Privacy analysis and variant-as-statement mapping

This subsection formalises the variant-as-statement reframe (Finding 10) by stating
each variant's cryptographic claim precisely, quantifying what the verifier learns, and
identifying the natural use-case class for each. The presentation here uses Variant A
as the worked example; A++ and B follow the same template with the per-variant
differences indicated.

**Each variant's statement, stated precisely.**

| Variant | Statement proved |
|---|---|
| flat_merkle | "∃ Hamiltonian cycle on N nodes with cost ≤ T against the matrix committed by `root`." |
| **A** | "∃ Hamiltonian cycle on N nodes with cost ≤ T against the matrix committed by `root`, **that respects the disclosed partition (segment_0, …, segment_{K-1}) and visits each segment in cycle order start_i → … → end_i with internal cost sum partial_cost_i**." |
| **A++** | "∃ Hamiltonian cycle on N nodes with cost ≤ T against the matrix committed by `root`, **that decomposes into K segments of M nodes with disclosed endpoints (start_i, end_i) and disclosed per-segment cost sums partial_cost_i**, the segments themselves bound by the disclosed Field-valued aggregates (P_i, h_in_i, h_out_i)." |
| **B** | "∃ Hamiltonian cycle on N nodes with cost ≤ T against `root` for boundary edges and against the disclosed M×M sub-matrices (M_0, …, M_{K-1}) for internal edges, that respects the disclosed partition and segment endpoints with disclosed per-segment cost sums." |

The columns "what the verifier learns beyond cost ≤ T" and "what stays private" follow
directly:

| Variant | Verifier learns | Verifier does not learn |
|---|---|---|
| flat_merkle | Nothing about the cycle | Cycle, individual costs, partition |
| **A** | Partition (which nodes ∈ which segment), K endpoints (start, end), K segment-cost sums | Interior order within each segment, individual edge costs, boundary edge costs |
| **A++** | K endpoint pairs, K segment-cost sums, K Field-valued aggregates (P_i, h_in_i, h_out_i) — these hide the partition **computationally**, not information-theoretically (see the A++ privacy caveat below) | Partition and interior order (computationally; recoverable only at ~C(N,M) and ~(M-2)! work per segment), individual edge costs, boundary costs |
| **B** | Partition, K M×M sub-matrices, K endpoints, K segment-cost sums | Interior order within each segment, individual boundary costs |

**Quantitative privacy bound for Variant A (worked).** Take N = 8, K = 2, M = 4 — the
example used in the implementation walkthrough (Section 8). The verifier observes:

- segment 0 = {0, 2, 3, 5}, start=0, end=2, partial_cost=30
- segment 1 = {1, 4, 6, 7}, start=7, end=6, partial_cost=34
- threshold = 100

The cycle is then known to be of the form `0 → ? → ? → 2 → 7 → ? → ? → 6 → 0`
where each `? → ?` pair is some permutation of two interior nodes. Number of candidates
remaining: (M-2)!^K = 2!² = 4. Total cycles on N=8 = (N-1)! = 5040. Information leaked:
log₂(5040 / 4) ≈ 10.3 bits.

For larger N this scales as `log₂((N-1)!) − K·log₂((M-2)!)`. At N=480, K=4: ~800 bits
leaked out of ~4000 bits of total cycle entropy — roughly 20% of the cycle's entropy.
The candidate set ((118!)^4 ≈ 10^800) remains unenumerable, so Variant A does *not*
reduce the cycle to a brute-force-checkable shortlist for large N. But the structural
information leaked (partition + macro skeleton) can be substantial in absolute terms.

**Threat-model dependence.** Whether Variant A's leakage is acceptable depends on
whether the verifier has independent access to the cost matrix.

- *Matrix private to the prover.* The verifier holds only the Merkle root (the trust
  in which is established by the mechanisms in Section 2.2). The matrix entries are
  hidden, so even with the partition and endpoints known the verifier cannot compute
  candidate cycle costs and cannot filter candidates further. Leakage is purely
  structural (partition + macro skeleton). For logistics SLA auditing or ESG
  reporting against proprietary cost data, this is the operative regime and Variant A
  is appropriate.

- *Matrix public to the verifier.* The verifier can in principle compute the cost of
  each remaining candidate cycle and filter against the partial_costs. For small N this
  may uniquely identify the cycle. For large N the candidate count remains too large to
  enumerate. Variant A is still useful (it provides cryptographic certainty in a search
  space too large to inspect), but its privacy is materially weaker than under the
  matrix-private regime.

The matrix-public regime is the one where Variant A++ pays for itself: by hiding the
partition behind a multiset commitment, A++ removes the filtering vector that "matrix
public + Variant A" provides to the verifier.

**A++ privacy caveat — the hiding is computational, not information-theoretic.** It is
tempting to state that A++'s Field-valued aggregates "leak no information" about node
membership. That is too strong, and worth stating precisely because a supervisor will
probe it. Two of A++'s public aggregates are *confirmation oracles*:

- The grand product `P_i = ∏_j (X + node_j)` is a polynomial evaluation at the *public*
  challenge X, not a one-way hash. Since the partition constraint forces each segment to
  be a size-M subset of {0..N-1}, a verifier can enumerate candidate subsets, evaluate
  the product, and accept the unique match — recovering exactly the segment multiset
  that Variant A discloses for free. Work: ≈ C(N, M) per segment.
- The chain anchors `h_in_i, h_out_i` are public and the chain step consumes only
  public-domain inputs (node indices), so once the multiset is known the interior
  *ordering* is a checkable brute-force. Work: ≈ (M-2)! per segment.

So A++'s information-theoretic leakage to an *unbounded* verifier is the full cycle; its
*computational* leakage to a bounded verifier is ~0 provided C(N,M) and (M-2)! are
infeasible. At the benchmark sizes this is comfortably the case (N=480, K=2:
C(480,240) ≈ 2⁴⁷⁵), so the partition is hidden in any practical sense — but the claim
must be stated as computational hiding with a work factor, not as unconditional secrecy.
Crucially, the anchors are public *because* the architecture is K+1 independent proofs
bound by off-circuit cross-checks: the verifier can only stitch the chain across
separate proofs if the anchors are public inputs. The recursive construction now
implemented (Section 7.8) keeps them private and **restores information-theoretic hiding
of the interior order** — confirmed in practice: the recursive outer proof exposes only
`(root, threshold)`. A++'s computational-hiding boundary is therefore a measurable price
of *avoiding* recursion (and its ~704k×K-gate aggregation cost) — a point on the
frontier, not a defect.

**Natural use-case mapping.** The variant-as-statement framing yields a clean mapping
between variants and applications. None of these is hypothetical — each corresponds to
an existing real-world TSP-with-privacy setting:

| Variant | Natural use cases | Why this variant |
|---|---|---|
| flat_merkle | Logistics SLA audit (matrix private, verifier sees only root); generic "private cycle on private graph" | Maximum privacy; only the existence statement is needed. |
| **A** | Multi-team SLA accountability; cross-org cost-sharing; regulated zoning where the partition is operational; ESG reporting by region | Partition disclosure is *operationally required*. The per-segment partial_costs are accountability artifacts. The K-fold parallelism story is real because the segments correspond to operational units that can prove independently. |
| **A++** | Same operational scenarios as A but where the specific partition is competitively sensitive (e.g., delivery route grouping reveals customer-cluster structure); maximum-privacy hierarchical option | Recovers flat_merkle's partition privacy *computationally* (break work ~C(N,M) / ~(M-2)! per segment — infeasible at thesis sizes) while keeping A's parallelism and **eliminating A's O(N) glue memory floor** (159 MB → 42 MB at N=480, K=8). Costs ~6% more gates in the sub-circuit (measured). |
| **B** | Smart-city fleet routing on public road networks; verification against TSPLIB instances; non-sensitive matrix with binding gate-cost constraint | Matrix is public anyway, so disclosing sub-matrices costs nothing extra in privacy and saves substantially in gates (Finding 7). |
| **recursion** (measured, §7.8) | Same use cases as flat_merkle (maximum/perfect hiding) but where the segment proving must be parallel/streamed, or a single constant-size proof + O(1) verification is required regardless of K | Re-attains flat_merkle's *perfect* hiding (public surface = `root, threshold`) with one ~14.7 KB proof, while keeping segment proving parallelisable. Cost: a monolithic outer of ~704k×K gates (~25–45× A++), per-prover memory ~2–4 GiB. The "perfect hiding is expensive" corner. |
| (folding — future) | Same use cases as recursion but with the per-step verifier overhead removed | Out of scope; the UltraHonk recursion baseline (§7.8, ~704k×K gates) is the concrete number folding-scheme designs would need to beat. |

**Connecting back to the dualism.** Each variant's position on the frontier is a direct
consequence of how it negotiates the dualism. A pays for parallelism with partition
disclosure (the cleanest exchange, but the largest disclosure). A++ recovers partition
privacy *computationally* by paying ~6% additional sub-circuit gates (Poseidon2 chain +
grand product) and, as a bonus, removes A's O(N) glue memory floor (159 MB → 42 MB at
N=480, K=8) — the dualism still applies, but the disclosure-vs-cost ratio is more
favourable. B sacrifices matrix privacy in exchange for gate-count reduction (a
different axis of the same trade). None of the three escapes the dualism — they navigate
it differently.

This is also where the case for *not* implementing folding schemes in this thesis is
strongest: folding would change the verifier-side overhead, not the dualism. The
Pareto-frontier among non-folding designs would shift but its shape (the variant-as-
statement structure) would persist.

### 7.8 Recursive aggregation: the measured perfect-hiding corner

The recursive construction anticipated in Section 7.5 and in the A++ privacy caveat
(7.7) is now **implemented and benchmarked**, not left as analysis. An outer circuit
verifies the K segment proofs *in-circuit* (`std::verify_proof` via Aztec's
`bb_proof_verification`, ZK flavour — `verify_honk_proof`, 458-field proof) and re-runs
the glue logic with the per-segment values read from the verified proofs. Those values
are now **witness** of the outer circuit, so the public surface collapses to
`(root, threshold)` — byte-for-byte flat_merkle's *information-theoretic* hiding, the
endpoint the A++ caveat pointed at. The harness lives in `tests/recursion_micro/`; the
inner is the unmodified A++ sub-circuit (recursion-friendliness is a proving-flavour
choice, not a circuit change), so the comparison against A++ is ceteris paribus.

**What it costs (measured, this machine, UltraHonk).**

| | gates | prove | peak mem | verify | proof |
|---|---|---|---|---|---|
| one in-circuit verification | **704,363** | ~8.6 s | ~1.0 GiB | ~15 ms | 14.7 KB |
| K=2 (verify 2 + glue) | **1,473,357** | ~23 s | ~2.1 GiB | ~15 ms | 14.7 KB |
| K=4 (verify 4 + glue) | **3,008,907** | ~41 s | ~4.1 GiB | ~15 ms | 14.7 KB |

Three structural facts, each measured across N ∈ {48, 96, 192, 480}:

1. **The aggregation overhead is N-independent.** One in-circuit verification is ~704k
   gates regardless of segment size (it checks a fixed-size proof). The outer's own gate
   count is flat in N (1.473M → 1.475M at K=2 across the whole range); the slow growth in
   the *total* is the inner segment proofs, which can be produced in parallel.
2. **It scales ~K×.** K=4 ≈ 4.27× one verification; the glue tax is small (~63k gates at
   K=2, ~191k at K=4). Recursion is therefore **~25× (K=2) to ~45× (K=4) more total
   proving work than A++**, and the gap *widens* with K — the aggregation layer dwarfs
   the TSP logic. This makes the "perfect hiding is expensive" claim quantitative.
3. **The verifier-side win is present-tense.** Recursion delivers *one* ~14.7 KB proof
   with ~15 ms verification *regardless of K*, versus A++'s K+1 proofs plus off-circuit
   cross-checks (proof bytes and verify time grow with K). On these axes recursion is
   already best-tier today (tied with flat_merkle, beating every hierarchical variant).

**Scoped crossover claim (committee-safe).** Recursion is *not* cheaper than the
hierarchical variants on any prover-cost axis at the sizes tested — A++ Pareto-dominates
it on gates, prove time, and per-prover memory at every N (and stays there by raising K).
The defensible crossover is **vs flat_merkle, among perfect-hiding designs, on memory**:
recursion's prover memory *plateaus* (~2.1 GiB at K=2, N-independent), while flat_merkle's
*grows* with N (~1.08 GiB at N=500); extrapolating, flat would exceed recursion's plateau
around N ≈ 1000. So recursion is best framed as *how one scales perfect hiding past where
monolithic flat proving exhausts RAM* — a qualitative privacy/scaling argument, not a
cost win. (Prove-time figures are single-run and noisy; the gate and memory columns are
the robust ones.)

**Inner-circuit choice (A++ vs A).** Inside recursion the partition is hidden regardless
of inner, so A's public node set is no longer a leak — A would let the outer check the
partition by a deterministic sort instead of A++'s grand-product + Fiat-Shamir. A
separate A-inner variant (`exp2_k_segments_a`) and a same-instance comparison
(`compare_inner.py`) quantify the difference: the two designs are within ~1.5% on outer
gates and **identical on the verifier side** (one 14.7 KB proof, ~15 ms verify, perfect
hiding). The one signal is that A++'s outer is flat in N while A's grows by ~22k gates
from N=48→480 — the O(M) public-input absorption of A's M+4-field surface. A++ is used as
the benchmark inner for a controlled comparison with the A++ row and because its O(1)
public surface keeps the recursive verification segment-size-independent; the A-inner
design (deterministic partition, no Fiat-Shamir) is arguably the more natural recursive
construction and is recorded as such. Full rationale:
`Recursive_inner_circuit_choice_explained.md`.

**Frontier placement.** Recursion is the fourth measured corner: flat_merkle (perfect,
monolithic) → A (parallel, partition public) → A++ (parallel, computational hiding) →
recursion (perfect, monolithic, ~K× expensive). It re-attains flat_merkle's perfect
hiding *and* a single constant-size proof while keeping the segment proving
parallelisable — the corner neither flat (monolithic) nor A++ (computational, K+1 proofs)
reaches — at a prover cost that grows with K. Folding (Section 7.5) is the remaining
unimplemented corner that would make this corner cheap; recursion's measured ~704k×K
overhead is precisely the number a folding implementation would aim to remove.

---

## 8. Next Steps

**Immediate (before final flat baseline).**
Run benchmarks for flat_full_invperm and flat_full_presence to complete the permutation
overhead analysis. These are implemented and correctness-tested; the benchmarks take one
afternoon of machine time.

**Architectural commitments common to all three variants (settled during planning).**

- **Independent sub-proofs + glue, not recursive composition.** Each variant produces
  K+1 independent UltraHonk proofs (K sub-proofs, 1 glue). The verifier runs
  `bb verify` K+1 times and *additionally* checks that the public-input fields the
  proofs claim to share actually agree (the same `root` across all proofs, the glue's
  `all_sorted_nodes` equals the concatenation of sub-proofs' `sorted_nodes`, glue's
  `starts/ends/partial_costs` agree with the per-sub-proof publications). This binding
  via shared public inputs replaces what would otherwise be in-circuit recursive
  verification of sub-proofs inside the glue. The verifier-side cost is O(N) trivial
  equality checks, negligible compared to proof verification itself. This independent-
  proofs design is what *exposes* A++'s anchors as public inputs (the
  computational-hiding boundary). The in-circuit recursive alternative is **no longer
  deferred** — it is implemented and benchmarked as the perfect-hiding corner
  (Section 7.8); only folding (Section 7.5) remains future work.
- **Instance sizes divisible by `lcm(K)`.** Benchmarks use N ∈ {48, 96, 192, 480} so all
  values of K under test (2, 4, 8) yield integer M = N/K. N=480 is the comparison
  anchor against the existing flat_merkle benchmarks at N=500 (~4% size mismatch).
- **K starts at 2 hardcoded for correctness, then is parameterised compile-time.**
  Initial implementation hardcodes K=2 for the first working end-to-end run; the
  generalisation to compile-time K is done immediately after.
- **Glue is shared between Variants A and B.** Both use the same sort-based partition
  check and K boundary Merkle proofs. Variant A++ has its own glue
  (`hierarchical_glue_fs`) implementing the grand-product check.
- **Sub-circuits publish sorted node sets (Variants A and B), not the cycle-order
  segment.** This preserves in-segment visit-order privacy at no extra cost.

**Three hierarchical variants, framed by the dualism.**
The hierarchical phase implements three variants chosen to span the privacy ↔ cost
frontier identified in Section 7. All three share the architecture above and differ in
(a) how the cost matrix is exposed and (b) how the global partition is enforced.

- *Variant A — Hierarchical Merkle, sorted nodes public* (`hierarchical_segment` +
  `hierarchical_glue`). The simple baseline: each sub-circuit publishes its sorted
  segment node set; the glue performs a global sort-based partition check on the
  concatenated K × M = N node outputs. Total gate count structurally invariant under K
  (Finding 6); per-process memory and parallel wall-clock both scale as N/K
  (Finding 8). Benchmarks target memory-per-process and parallel wall-clock as primary
  metrics, with total gate count as a control measurement. Verifier learns the
  partition.

- *Variant A++ — Hierarchical Merkle, grand product + in-circuit Fiat-Shamir*
  (`hierarchical_segment_fs` + `hierarchical_glue_fs`). Refines Variant A by replacing
  the O(N) sort-based partition check with a grand-product multiset-equality argument.
  The challenge `X` for the grand product is derived from a Poseidon2 hash chain over
  the global cycle (`c = h_N` where `h_{j+1} = Poseidon2(h_j, cycle[j])`,
  `X = Poseidon2(c)`); the binding is enforced jointly by the K sub-circuits (each
  proving its segment is the corresponding slice of the chain) and by the glue
  (asserting chain stitching and chain terminal equals `c`). Sub-circuit overhead is
  approximately M Poseidon2 calls (measured +6.7% at N=8); the glue's O(N) sort is
  replaced by an in-circuit grand-product loop, eliminating A's O(N) memory floor.
  Soundness rests on standard Fiat-Shamir / Schwartz-Zippel arguments (Finding 9).
  Verifier learns only segment endpoints plus Field-valued aggregates; interior nodes
  hidden *computationally* (the aggregates are confirmation oracles at ~C(N,M) / ~(M-2)!
  work — see §7.7). **Implemented and benchmark-validated (2026-05-28):** end-to-end
  reference proof verifies, an 8-case soundness suite passes (including a
  Schwartz-Zippel partition-overlap rejection), and the full sweep confirms the
  glue-memory result above. Engineering choice: the partition RHS `∏(X+j)` is computed
  in-circuit (no `expected_product` public input), so the verifier performs no field
  arithmetic — every soundness claim is a circuit constraint.

- *Variant B — Hierarchical flat_full, sub-matrices public* (sub-circuit takes its
  M × M sub-matrix as public input, glue handles boundary edges via Merkle). Trades
  partition disclosure for total gate-count reduction of O(N²) → O(N²/K) (Finding 7).
  Benchmarks target total gate count, with privacy loss quantified as the bit-content
  of the disclosed partition and sub-matrices.

Each variant follows the same five-stage implementation path: sub-circuit design,
glue-circuit design, pipeline split, correctness tests, and gate-count sanity check
before full benchmarks. Variants A and A++ share most pipeline infrastructure (the
hash-chain precomputation is the only A++-specific addition off-circuit). Estimated
effort: ~1 work-week per variant plus a third week for combined benchmarks and
frontier-figure preparation; the three-variant total is roughly 2.5–3 work-weeks of
implementation given the shared architecture.

**Sub-circuit and glue design (shared structure across all three variants).**
The sub-circuit proves a Hamiltonian *path* through M = N/K nodes from a private
segment of the cycle, publishing (start node, end node, partial cost) to the glue
along with a per-variant partition-check witness — sorted node set (A), grand-product
value + hash-chain endpoints (A++), or the M × M sub-matrix as public input (B). The
glue verifies endpoint connectivity across segments, performs the per-variant global
partition check, verifies K boundary Merkle proofs against the shared cost-matrix
Merkle root (A and A++) or via direct sub-matrix lookups (B), and asserts the summed
cost satisfies the public threshold.

For Variants A and A++, the sorted node set / Field-valued aggregates are exposed
rather than the segment in cycle order, so the in-segment visit ordering remains
private. For Variant A++ specifically, in-circuit Fiat-Shamir binds the per-segment
witnesses to the global cycle without requiring multi-round prover-verifier
interaction.

**Worked example: Variant A at N = 8, K = 2, M = 4, DEPTH = 6.**

To make the sub-circuit / glue interfaces concrete, consider the cycle
`0 → 5 → 3 → 2 → 7 → 4 → 1 → 6 → 0` with edge costs:

| Edge | Cost | Role |
|---|---|---|
| 0→5 | 10 | seg 0 internal |
| 5→3 | 12 | seg 0 internal |
| 3→2 | 8  | seg 0 internal |
| 2→7 | 15 | **boundary** (between segments) |
| 7→4 | 11 | seg 1 internal |
| 4→1 | 9  | seg 1 internal |
| 1→6 | 14 | seg 1 internal |
| 6→0 | 13 | **boundary** (closes the cycle) |

Total cost 92, threshold 100.

*Sub-circuit 0 (segment 0, cycle indices 0..3):*

| Field | Value | Visibility |
|---|---|---|
| `cycle_segment` | [0, 5, 3, 2] | private |
| `sorted_nodes` | [0, 2, 3, 5] | public |
| `start_node` | 0 | public |
| `end_node` | 2 | public |
| `edge_costs` | [10, 12, 8] | private |
| `partial_cost` | 30 | public |

The constraints (per the five-group structure) check that the cycle_segment values lie
in [0, N), that `sort([0,5,3,2]) == [0,2,3,5]`, that start=0=cycle_segment[0] and
end=2=cycle_segment[M-1], that Merkle proofs for leaves at indices 0·8+5=5, 5·8+3=43,
3·8+2=26 with leaf values 10, 12, 8 hash up to `root`, and that 10+12+8 = 30.

*Sub-circuit 1 (segment 1, cycle indices 4..7):*

| Field | Value | Visibility |
|---|---|---|
| `cycle_segment` | [7, 4, 1, 6] | private |
| `sorted_nodes` | [1, 4, 6, 7] | public |
| `start_node` | 7 | public |
| `end_node` | 6 | public |
| `edge_costs` | [11, 9, 14] | private |
| `partial_cost` | 34 | public |

Merkle proofs for leaves at indices 7·8+4=60, 4·8+1=33, 1·8+6=14 with values 11, 9, 14.

*Glue:*

| Field | Value | Visibility |
|---|---|---|
| `all_sorted_nodes` | [0, 2, 3, 5, 1, 4, 6, 7] | public |
| `starts` | [0, 7] | public |
| `ends` | [2, 6] | public |
| `partial_costs` | [30, 34] | public |
| `boundary_costs` | [15, 13] | private |
| `threshold` | 100 | public |

The glue's partition check sorts `all_sorted_nodes` and asserts equality with
[0,1,2,3,4,5,6,7]. It verifies the boundary Merkle proofs at leaves 2·8+7=23 (value 15)
and 6·8+0=48 (value 13). It asserts 30+34+15+13 = 92 ≤ 100.

*Verifier-side cross-checks (after `bb verify` succeeds on all three proofs):* all
three proofs declare the same `root`; glue.all_sorted_nodes[0..4] equals
sub_0.sorted_nodes; glue.all_sorted_nodes[4..8] equals sub_1.sorted_nodes; the starts,
ends, and partial_costs publications all agree. These checks are O(N) trivial equality
comparisons.

*What is privately preserved.* The verifier does not learn the interior order within
each segment — sub_0 could in principle have visited {3, 5} as 0→3→5→2 or 0→5→3→2; both
are consistent with the public outputs. The verifier also does not learn any individual
edge cost (only sums), nor the boundary edge costs.

*What is publicly exposed.* The verifier learns the partition ({0,2,3,5} | {1,4,6,7}),
the endpoints of each segment (0→2 and 7→6 as the two segments' start→end), the
boundary edges (2→7 and 6→0), and the per-segment cost sums. This is exactly the
"variant A statement" stated in Section 7.7: a partition-respecting Hamiltonian cycle
with per-segment cost accountability.

**Frontier mapping rather than crossover localisation.**
The experimental programme reports each variant as a point in
(total gate count, parallel proving time, per-prover memory, verifier privacy) space
across N ∈ {50, 100, 200, 500} and K ∈ {2, 4, 8}. The deliverable is a frontier figure
showing which variant Pareto-dominates which others in which regions, with the
structural reason for each dominance traced back to the dualism in Section 7.

**Cross-domain synthesis.**
The heuristic optimisation results from the parallel TSP-clustering project will be
integrated in a final chapter. The dualism in Section 7 frames the joint analysis: the
two domains' crossover behaviours are predicted to differ in direction, not just in
magnitude. Joint empirical measurement tests this prediction and characterises the
combined solve-then-prove pipeline.

**Folding schemes as future work.**
The UltraHonk-based hierarchical gate counts established here serve as the baseline
that recent folding-scheme designs (Nova, ProtoStar) would need to beat. A
folding-scheme implementation is beyond the scope of this thesis but is the natural
continuation: it would test whether the dualism is intrinsic to the problem class or a
property of the proof system in use. Variant A++'s in-circuit Fiat-Shamir construction
is essentially a non-recursive instantiation of the same pattern that recursive SNARKs
use internally for cross-proof challenge derivation, and provides an operational point
of reference for what folding schemes would need to improve upon.
