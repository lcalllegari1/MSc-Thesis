# Zero-Knowledge Proof for TSP: Flat Circuits, Complexity Analysis, and Design Rationale

**Progress Report — May 2026**

---

## 1. Overview and Research Question

This report documents the first phase of the thesis: the design, implementation, and
benchmarking of flat zero-knowledge proof circuits for the Travelling Salesman Problem
(TSP). The work addresses a central question in applied ZKP research:

> **At what problem size N does a hierarchical (decomposed) ZKP circuit become cheaper
> than a flat (monolithic) one, and what governs the crossover?**

Answering this requires first characterising the flat baseline precisely — its cost
structure, empirical scaling, and the trade-offs between design variants. That is what
this phase delivers.

A secondary thread, motivated by parallel work on heuristic TSP solvers, frames the
same decomposition question in two complementary roles: *finding* a solution
(optimisation) and *verifying* one (zero-knowledge proof). The cross-domain comparison
is deferred to a later phase but motivates several design choices made here.

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
If the prover supplies the root themselves, they could choose a matrix convenient for
their claimed cycle. In the intended deployment, the root is fixed by an external
authority (the company that owns the graph), and the prover works against that fixed
commitment.

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

---

## 7. Cross-Domain Perspective: Optimisation and Verification

This thesis sits at the intersection of two computational tasks on the same problem
class. A parallel project studied hierarchical (clustered) heuristic solvers for TSP,
where the same decomposition question arises: at what N does splitting the problem into
k clusters of size N/k outperform solving the full N-node instance?

The structural analogy is close. Both studies involve a flat approach (monolithic
circuit or single-pass solver) and a hierarchical approach (segmented circuit or
clustered solver), both exhibit a crossover governed by the relative cost of solving
sub-problems versus combining results, and both can be characterised by empirical
benchmarks across a range of N.

The key asymmetry, and the reason the comparison is interesting rather than merely
parallel, concerns the nature of the trade-off in each domain.

In **heuristic optimisation**, decomposition trades solution quality for speed. A
clustered solver ignores inter-cluster edge costs during intra-cluster optimisation,
producing tours that are faster to compute but potentially worse in cost. The crossover
is entangled with an approximation ratio: the two regimes are not directly comparable on
the same objective.

In **ZKP verification**, decomposition preserves exact soundness. A hierarchical circuit
splits the proof into k segment proofs and a stitching circuit that verifies endpoint
connectivity and full node coverage. The soundness guarantee is identical to the flat
circuit — there is no quality degradation. The only cost is the stitching overhead,
which is O(k) and small relative to the sub-circuit cost.

This means hierarchical decomposition is a cleaner strategy in the verification context
than in the optimisation context. The ZKP crossover is a purely computational threshold;
the optimisation crossover requires a joint decision about acceptable solution quality.

The empirical results from the heuristic study — crossover N, quality degradation curves,
cluster size sensitivity — will be presented alongside the ZKP results in a combined
chapter once the hierarchical ZKP circuit is benchmarked. The comparison will address
whether the two crossover points coincide, and what the combined pipeline (solve +
prove) looks like when both decompositions are applied simultaneously.

---

## 8. Next Steps

**Immediate (before final flat baseline).**
Run benchmarks for flat_full_invperm and flat_full_presence to complete the permutation
overhead analysis. These are implemented and correctness-tested; the benchmarks take one
afternoon of machine time.

**Hierarchical ZKP circuit design.**
The hierarchical circuit splits the N-node Hamiltonian cycle into k segments of s = N/k
nodes each. Each segment is proved independently as a Hamiltonian path from a known
start node to a known end node, with cost ≤ T_i. A lightweight stitching circuit then
asserts: (a) the end node of segment i equals the start node of segment i+1 for all i,
and (b) the k start nodes together form a permutation of {0, s, 2s, …, (k-1)s} — i.e.,
the partition is valid and complete.

The central design question is the stitching circuit's cost and how it scales with k.
If stitching is O(k) (a small RAM-based permutation check on k items), the total
hierarchical cost is k × C(N/k) + O(k), where C(m) is the flat circuit cost for m nodes.
The crossover with flat_merkle_presence occurs when this expression is less than C(N).

**Experimental programme.**
Implement and benchmark the hierarchical circuit for a range of (N, k) pairs. Plot the
hierarchical cost surface against the flat baseline. Identify the empirical crossover
and compare it to the analytical prediction derived from the flat cost models established
here.

**Cross-domain synthesis.**
Integrate the heuristic optimisation results with the ZKP benchmarks to produce the
combined pipeline analysis described in Section 6.
