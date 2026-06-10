# TSP ZKP — Design Log

This document records design decisions, alternatives considered, and rationale.
It is updated incrementally as the project evolves.

> **The unchosen → `DESIGN_SPACE.md`.** This log records *what we picked and why*;
> `DESIGN_SPACE.md` is the honest alternatives ledger — the full road-not-taken space per
> decision (incl. options stronger than ours), with viva-defense lines and the smart things
> we may have missed (committed-table lookups, folding/STARK recursion, approximation proofs,
> tree aggregation). Consult it before drafting any "alternatives considered" section.

---

## Variant naming convention

Variants are named `{regime}-{mechanism}`; see `Thesis_Outline.md` §N for the full three-level
scheme (variant / component / per-segment object). Quick reference:

| Variant | Old name | Code (segment / recombiner) |
|---|---|---|
| `flat-sort` | A's flat baseline (flat_merkle_sort) | `flat_merkle_sort` |
| `flat-product` | flat_merkle_grand_product | `flat_merkle_grand_product` |
| `plain-sort` | Variant A | `hierarchical_segment` / `_glue` |
| `plain-product` | Variant A++ | `hierarchical_segment_fs` / `_glue_fs` |
| `committed-sort` | committed-A | `hierarchical_segment_c` / `_glue_c` |
| `committed-product` | committed-A++ | `hierarchical_segment_cfs` / `_glue_cfs` |
| `recursive-sort` | recursive-A | `recursion` (sort inner; control) |
| `recursive-product` | recursive-A++ | `recursion` (product inner; shipped) |

- **regime** ∈ flat · plain · committed · recursive (the stitching tax, top→bottom)
- **mechanism** ∈ sort · product (the fingerprint lever)
- **components:** `segment` (per-leg), `glue` (external recombiner, used by `plain-*`/`committed-*`),
  `outer` (recursive recombiner). `recursive-*` reuses the `plain` segments as inners.
- **per-segment objects:** node-set fingerprint (`*-sort`) · product fingerprint `P_i` (`*-product`)
  · segment commitment `C_i` (`committed-*`); endpoints; chain anchors; partial cost.
- Code identifiers are **unchanged**; only conceptual references use the new names. Thesis prose
  uses **stitching tax** (not "binding tax"); *binding/hiding* are reserved for commitment properties.

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

**Instance + tree cache (one per N):** the O(N²) Poseidon2 tree build dominates
`merkle_builder` at large N and is identical for every variant/K/run on a given
instance. `pipeline/instance_cache.py` makes `(N, seed)` the cache key — the
instance, solved cycle and serialised tree are built once under
`data/instances/n{N}_seed{S}/` and reused by every harness; `merkle_builder
--tree-cache <path>` loads `tree.bin` instead of rebuilding (checksum-validated
against the input matrix). All harnesses now share **one instance per N across
all variants and runs** (sound because proving is data-oblivious — see
`HOWTO.md` → `instance_cache.py`). The flag is additive: a builder call without
`--tree-cache` is byte-identical to before.

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
| **Perm-GrandProduct** | In-circuit Fiat-Shamir `X = Poseidon2([c],1)` over the cycle hash chain, then `∏(X+cycle[i]) == ∏(X+j)` | ~N Poseidon2 (chain) + 2N mults; GROUP 1 subsumed. Probabilistic (Schwartz-Zippel + FS-in-ROM, ~2⁻²⁴⁶) vs the others' deterministic checks. **`flat_merkle_grand_product` = the plain-product grand-product gadget "collapsed to K=1"**; completes the {flat,recursive}×{sort,grand-product} grid (`NARRATIVE_FRAMING.md` §7-8). |

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
| **plain-product** — Merkle, grand product + in-circuit Fiat-Shamir | "...that decomposes into K segments with disclosed endpoints, segments themselves hidden" |
| **B** — flat_full, sub-matrix public | "...with disclosed M×M sub-matrices and disclosed partition" |

plain-sort and plain-product keep the cost matrix private (committed via Merkle root). B exposes
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
- **Glue shared between plain-sort and B**, with sort-based partition + K boundary Merkle proofs.
  plain-product has its own glue with grand-product partition check.

### Sub-circuit interface (shared by plain-sort and B, extended by plain-product)

```
Public inputs:
  root          : Field
  sorted_nodes  : [u32; M]   // segment node set, sorted ascending (plain-sort and B)
  start_node    : u32
  end_node      : u32
  partial_cost  : u64
  -- plain-product adds: (P_i, h_in_i, h_out_i, c, X) and removes sorted_nodes
```

### Glue interface (plain-sort and B)

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

plain-product's glue replaces `all_sorted_nodes` with `(P_is[K], h_ins[K], h_outs[K], c, X,
expected_product)` and the sort-based partition check with the grand-product check.

### The structural reason no single variant universally dominates

Hierarchical decomposition adds a constraint in optimisation (good — search shrinks)
and weakens a constraint in ZK (bad — soundness must be restored by O(N) glue work).
The NP asymmetry between finding and checking holds, but the strategy that exploits it
in classical optimisation (trading verification overhead for search-space pruning)
does not transfer to ZK because there is no search to prune. Decomposition in ZK
becomes pure overhead unless it is used to disclose structure to the verifier (plain-sort, Variant B) or to enable parallel work-sharing (all three) — neither of which is an
algorithmic improvement.

See `supervisor_report_draft.md` §7 for the full dualism argument and §7.7 for the
variant-to-use-case mapping.

### Benchmark interpretation (added 2026-05-27)

The plain-sort full benchmark sweep completed. Two metrics require careful interpretation
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
plain-product replaces O(N) sort with O(K) grand product; its glue memory should be
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

## 9. The Binding Tax, Committed Variants, and the Privacy Ladder (reframe 2026-05-29)

This section records the conceptual reframe from the 2026-05-29 discussion. It does
not supersede §8; it adds the organizing spine that sits under it. Full synthesis
with numbers and next steps lives in `FRONTIER_REFRAME.md`.

> **Status update (2026-05-31): committed-sort and committed-product are now IMPLEMENTED**
> (no longer the analytical "could-build" point this section originally described).
> Circuits `hierarchical_{segment,glue}_{c,cfs}`, builder modes `--hierarchical-{c,cfs}`,
> verifiers/harnesses `verify_hier_{c,cfs}.py` / `run_hier_{c,cfs}.py`, and 7/7
> correctness suites. See `HIERARCHICAL_EXPLAINED.md` §9b/§14.4-5 and the checklist
> below. The narrative role (plain-sort/plain-product = diagnosis + disclosure; committed-* = cure) is
> in `NARRATIVE_FRAMING.md`; defense prep in `MOTIVATION_AND_OBJECTIONS.md`.

### 9.1 The stitching tax — one artifact, three symptoms

Decomposing into K independent segment-proofs forces a binding step to recombine them
into one sound, private statement. That binding is a **single object with three
coupled symptoms**, all of which are the *shared public surface of independent proofs*:
1. **partition leakage** (the shared values are disclosed),
2. **O(K) verifier cost** (K+1 proofs → K× proof bytes + K× verify time),
3. **verifier-side bookkeeping** (the equality cross-checks in `verify_hier*.py`).

They dissolve **together** under one move: fold the binding into a proof. Recursion
does this (the cross-checks become in-circuit asserts; the verifier returns to a single
`bb verify` on `(root, threshold)`). Folding does it cheaply. So the privacy leak, the
O(K) verifier cost, and the external bookkeeping are not three separate problems — they
are three faces of "independent proofs need external binding."

### 9.2 Two decisions generate the whole family

- **Where binding lives:** verifier-side (plain-sort, plain-product, B) / in-circuit (recursion) /
  deferred (folding, future).
- **What is bound:** plaintext (discloses — the leak; good when disclosure is the goal)
  / hiding commitment (committed-sort/plain-product) / witness (recursion — the limit).

### 9.3 The pick-two triangle (frontier, at fixed privacy)

Three desiderata; each architecture gives exactly two. The O(K) verifier cost is the
**price plain-sort/plain-product pay to keep P and C together** — a defining feature of the corner.

| | Parallel + low per-prover mem (P) | O(1) verifier (V) | Low prover overhead (C) |
|---|:--:|:--:|:--:|
| flat (K=1) | ✗ | ✓ | ✓ |
| plain-sort / plain-product / committed-* | ✓ | ✗ | ✓ |
| recursion | ✓ | ✓ | ✗ |
| folding (future) | ✓ | ✓ | ✓ (breaks the triangle) |

### 9.4 The commitment fix — close the leak without recursion

Bind on **hiding commitments** instead of plaintext: each sub exposes
`C_i = Commit(values; r_i)`; the glue takes values+openings as witness and runs the
partition/boundary/cost checks in-circuit; the verifier checks `sub_i.C_i == glue.C_i`.
Public surface collapses to `(root, threshold, C_0..C_{K-1})`; the bookkeeping becomes
ZK automatically (comparing opaque blobs) and can be collapsed to one digest per proof.
For plain-product this is minimal — `P_i` is already a per-segment summary lacking blinding.

**Implemented (2026-05-31).** Both committed-sort (`C_i = fold(r, [cycle_segment…,
partial_cost])`, glue does the O(N) sort over witnessed nodes) and committed-product
(`C_i = fold(r, [P_i, h_in, h_out, start, end, partial_cost])`, glue keeps the
distributed grand-product; sub G7 dropped) use a Poseidon2 fold (the 2-input
compression already cross-validated in `tests/hash_compat`), with blinding from
`/dev/urandom`. Public surfaces: committed-sort `{root, T, C_is}`, committed-product
`{root, T, X, C_is}`. Pedersen is left as the analytical unconditional-content upgrade.

### 9.5 plain-sort is NOT dominated by plain-product (correction to an earlier read)

Glue-to-glue, plain-product's grand product beats plain-sort's sort (N=480 K=2: 6,987 gates / 31 MB vs
14,822 / 159 MB). But plain-product **relocates** that O(N) work into the K segments (+~3.5%/sub),
so on **totals plain-sort is cheaper at every measured K** (N=480: plain-sort 769,926 / 775,622 / 787,014
vs plain-product 788,533 / 794,401 / 806,137 for K=2/4/8). Per-prover memory **ties at K=8**
(~159 MB) for opposite reasons (plain-sort pinned by O(N) glue floor; plain-product by its heavier sub). plain-sort also has a **deterministic** partition check (no Schwartz–Zippel error).

plain-product's real justification, in order of durability:
1. **Best recursion inner** — O(1) public surface (9 fields, M-independent) keeps the
   recursive verifier segment-size-independent (single-segment outer = 704,363 gates
   flat at N=8 *and* N=480; a plain-sort inner exposes M+4 fields and grows with N).
2. **High-K memory** — O(K) glue removes plain-sort's O(N) memory floor; plain-product keeps falling at
   K≥16 where plain-sort plateaus.
3. **Distributed partition check** — O(M)/segment parallel + O(K) merge vs plain-sort's serial
   O(N) sort.

So plain-product is *the design you recurse on*, not a cheaper plain-sort. Cut recursion from the thesis
and plain-product's standalone case gets thin.

### 9.6 Privacy classification and the ladder

"Perfect hiding" of flat/recursion is **structural** (the public surface carries no
route/partition info), not information-theoretic ZK (UltraHonk-ZK is computational/
statistical and identical across all variants — not a discriminator). Per
implementation:

| Implementation | Partition privacy class | Rests on |
|---|---|---|
| flat_full | matrix disclosed; no partition | — |
| flat_merkle_presence | no partition; matrix committed | weak matrix hiding (entropy/blinding) |
| plain-sort | **disclosed** (node-sets + endpoints plaintext) | nothing (unconditional leak) |
| plain-product | **computational, oracle** (`P_i` ~C(N,M), confirms guesses); endpoints plaintext | subset-product hardness |
| committed-sort/plain-product (Poseidon) | **computational** | hash one-wayness |
| committed-sort/plain-product (Pedersen) | **unconditional content** (K revealed; comp. binding) | perfect-hiding primitive |
| Recursion (recursive-sort & recursive-product) | **structural / assumption-free** (partition is witness) | nothing |
| Variant B | **disclosed** (partition + sub-matrices) | nothing (by design) |
| Folding (future) | **structural / assumption-free** | nothing |

**Ladder (assumption-decreasing):** B → plain-sort → plain-product → committed(hash) → committed(Pedersen)
→ recursion/folding/flat. Two mechanisms: *commit to hide it* (computational/
unconditional) vs *don't put it there at all* (assumption-free). recursive-sort and recursive-product have **identical** final privacy. Even unconditional committed-* is a notch
weaker than recursion: it still publishes K commitments, whereas recursion makes the
partition structurally absent.

**Equal-privacy finding (implemented):** under full equalization committed-sort and
committed-product reach the *same* rung (multiset computational, interior order
info-theoretic, reveal K); they differ only in glue cost/mechanism (O(N) sort + O(N)
commit-fold vs distributed grand-product + O(K) commit-fold) — the equal-privacy
restatement of §9.5.

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
- [x] Flat circuit — Flat-Merkle, Perm-Sort (`circuits/flat_merkle_sort`)
- [x] Flat circuit — Flat-Merkle, Perm-GrandProduct (`circuits/flat_merkle_grand_product`; reuses the flat Prover.toml, X internal → public surface `{root,T}` identical to flat_merkle_sort; `tests/correctness/test_flat_merkle_grand_product.py` 30/30)
- [x] Hash compatibility test: `tests/hash_compat/`
- [x] Git repo initialised
- [x] Thesis reframing (2026-05-23, sharpened 2026-05-26) + supervisor report updated
- [x] Instance + tree cache: `pipeline/instance_cache.py` + `merkle_builder --tree-cache` (one instance per N, shared across all variants/runs; enables N>2000 sweeps without rebuilding the tree each time)

### Pending baseline housekeeping

- ~~Benchmarks for flat_full_invperm and flat_full_presence to N=500~~ **dropped (2026-06-10)**
  — both are out-of-scope variants (Outline §F.2); the §4.2 mechanism study draws on
  `results/flat.csv` as-is.
- ~~Figures generated from `results/500.csv` via `analyze_complexity.py`~~ **superseded** —
  thesis figures now come from `pipeline/plot_thesis_figures.py` → `plots/figures/`.

### Hierarchical implementation programme

- [x] plain-sort — Merkle, sorted nodes public (2026-05-27)
    - [x] Sub-circuit `circuits/hierarchical_segment` (G1..G5)
    - [x] Glue circuit `circuits/hierarchical_glue` (G2..G4; G1 is structural-only)
    - [x] `pipeline/merkle_builder` extended with `--hierarchical K --out-dir`
    - [x] `pipeline/verify_hier.py` — K+1 `bb verify` + 4 cross-checks
    - [x] `pipeline/run_hier.py` — K-shadow parallel benchmark harness
    - [x] `tests/correctness/test_hierarchical_a.py` — 6 tests (1 valid + 4 negatives + 1 sanity at N=48 K=4)
    - [x] Full benchmark sweep into `results/hier_a.csv` (completed 2026-05-27; N∈{48,96,192,480}, K∈{2,4,8})
    - [x] Isolation benchmark — **done (2026-06)**: `results/hier_sort_iso.csv` (N≤5000,
      K∈{2,4,8}, per-circuit uncontended times). Measured at N=3000 K=8: critical path
      12.4s (max sub) + 7.35s (glue) = 19.7s vs flat 91.9s → **~4.7×** (the serial O(N)
      glue sort is the gap to ideal).
- [x] plain-product — Merkle, grand product + in-circuit Fiat-Shamir (implemented + validated 2026-05-28)
    - [x] Hash-compat extension: single-input `Poseidon2::hash([c],1)` cross-validated Rust↔Noir (`tests/hash_compat/`); N=8 reference table filled in `HIER_FS_IMPL.md` §11
    - [x] Sub-circuit `circuits/hierarchical_segment_fs` (G1..G7: +G5 chain link, +G6 grand product, +G7 challenge consistency; no sorted_nodes)
    - [x] Glue circuit `circuits/hierarchical_glue_fs` (G1..G7: chain stitch G1-G3, FS bind G4, grand-product partition G5 with **in-circuit** RHS, boundary Merkle G6, threshold G7)
    - [x] `pipeline/merkle_builder` extended with `--hierarchical-fs K --out-dir` (chain → c → X, per-segment P_i / h_in / h_out, two new Prover.toml writers)
    - [x] `pipeline/verify_hier_fs.py` — K+1 `bb verify` + ~6K+3 equality cross-checks (same root/c/X; per-segment starts/ends/partial_costs/P_is/h_ins/h_outs). No field arithmetic (Option B).
    - [x] `pipeline/run_hier_fs.py` — K-shadow parallel harness (`/tmp/hier_fs_shadows`, variant=`hier_fs`); `aggregate_hier.py` made variant-aware (emits `hier_fs_k{K}`)
    - [x] `tests/correctness/test_hierarchical_fs.py` — 8 tests (1 valid + 6 negatives incl. Schwartz-Zippel partition overlap + 1 sanity at N=48 K=4); all pass
    - [x] End-to-end reference proof verifies; gate counts at N=8: sub +6.7% vs plain-sort, glue ≈parity (the −67% glue win is a large-N effect)
    - [x] Full benchmark sweep — **done (2026-06)**, landed as `results/hier_gp_iso.csv`
      (isolated per-circuit times, N≤5000, K∈{2,4,8}). At N=3000 K=8: 12.7s (max sub) +
      0.55s (glue) = 13.2s vs flat 86.1s → **~6.5×** measured speedup; the O(K) glue stays
      sub-second at every N (the surface win made operational).
    - **Design divergence from `HIERARCHICAL_EXPLAINED.md` §9.9:** `expected_product` is computed **in-circuit** (D5 = Option B), not supplied/checked by the verifier. The Python verifier therefore does no field arithmetic.
    - **Privacy refinement:** plain-product hides the partition *computationally* (not information-theoretically): public `P_i` is a multiset oracle (~C(N,M)) and chain anchors are an ordering oracle (~(M-2)!). This is the price of the non-recursive architecture — see `HIERARCHICAL_EXPLAINED.md` §9.11/§14.2.
- [x] Variants committed-sort & committed-product — blinded-commitment privacy cure (implemented + validated 2026-05-31)
    - [x] committed-product circuits `circuits/hierarchical_{segment,glue}_cfs` (sub: fold aggregates into `C_i`, drop G7, h_in + r private; glue: G0 recompute, grand-product partition; public `{root,X,C_i}` / `{root,T,X,C_is}`)
    - [x] committed-sort circuits `circuits/hierarchical_{segment,glue}_c` (sub: fold `[cycle_segment…,partial_cost]` into `C_i`, drop per-segment sort; glue: G0 recompute + O(N) sort, needs `M` global; public `{root,C_i}` / `{root,T,C_is}`)
    - [x] `pipeline/merkle_builder` extended with `--hierarchical-c` / `--hierarchical-cfs` (commit_fold over 2-input Poseidon2, blinding from `/dev/urandom`)
    - [x] `pipeline/verify_hier_{c,cfs}.py` — K+1 `bb verify` + cross-check collapses to same root (+ X for cfs) and `glue.C_is[i] == sub_i.C_i` (opaque blobs, ZK)
    - [x] `pipeline/run_hier_{c,cfs}.py` — parallel harnesses (variant=`hier_c` / `hier_cfs`); `aggregate_hier.py` variant-agnostic (emits `hier_c_k{K}` / `hier_cfs_k{K}`)
    - [x] `tests/correctness/test_hierarchical_{c,cfs}.py` — 7/7 each (baseline, sub-G8 + glue-G0 commitment binding, boundary Merkle, partition violation, verifier cross-check, N=48 K=4 sanity)
    - [x] All 4 committed circuits compile from their checked-in N=8 defaults
    - [x] Full benchmark sweeps — **done (2026-06)**, landed as
      `results/hier_committed_sort_iso.csv` / `results/hier_committed_gp_iso.csv`
      (isolated per-circuit times, N≤5000, K∈{2,4,8}).
- [ ] Variant B — flat_full, sub-matrix public
- [ ] Frontier figure: (total gates, parallel wall-clock, per-prover memory, privacy bits) for all variants
- [ ] Integration with clustered TSP solver (B-side, partitioned routing) for combined-pipeline analysis

### Done since

- Recursive composition of the K segment proofs into one outer proof — **promoted to a
  first-class variant** (2026-06-01). Outer circuit `circuits/recursion` (moved from the
  `tests/recursion_micro/exp2_k_segments` experiment), harness `pipeline/run_recursion.py`,
  verifier `pipeline/verify_recursion.py` (ONE `bb verify`, zero cross-checks — the
  stitching-tax collapse made operational), correctness suite `tests/correctness/test_recursion.py`
  (9/9: baseline + root/bind/threshold/boundary asserts at execute + tampered-proof &
  tampered-VK-commitment at prove + grand-product overlap + K=4 generality). Recurses on the
  *plain* plain-product segment (`hierarchical_segment_fs`); committing the inner would be redundant
  since the outer already makes the partition a witness. Re-attains flat_merkle's perfect
  hiding (public surface = `root, threshold`); ~704k gates per in-circuit verification, ~K×
  total. **Outer-proof ZK confirmed:** default `bb prove` is ZK (458-field / 14656-byte proof
  vs 410 for `-no-zk`); the harness + verifier assert 14656 bytes so a future bb default flip
  can't silently break hiding. The single-segment `exp1` and the plain-sort-inner set (`exp2_k_segments_a`,
  `run_recursion_a.py`, `compare_inner.py`) stay in `tests/recursion_micro/` as off-frontier
  **diagnostics**. See HOWTO.md and `Recursive_inner_circuit_choice_explained.md`.

### Future / out of scope

- Folding-scheme variant (Nova/ProtoStar) — the natural continuation; the only
  unimplemented frontier corner. Would remove the ~704k×K recursive-verifier overhead.
- Hash commitment for sorted node sets (alternative to plain-product for partition hiding)
- **Full soundness proofs for the variants** (knowledge-soundness reductions + per-variant
  ε-bounds; FS-in-ROM and recursion KS cited, not reproved) — plan captured in
  `Thesis_Outline.md` §9.8 / "Deferred analytical work". Plus the consolidated
  soundness-validation table (§10.1a). To return to in the analysis phase.
