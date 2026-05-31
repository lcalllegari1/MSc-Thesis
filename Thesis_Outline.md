# Thesis Outline — Zero-Knowledge Proofs for the Travelling Salesman Problem

**Working title (draft):** *Zero-Knowledge Proofs for the Travelling Salesman Problem:
A Family of Statements, a Structural Dualism, and a Privacy-Cost Frontier*

**Alternative subtitle (2026-05-29 reframe):** *…a Structural Dualism, and the Binding
Tax of Decomposed Proofs* — surfaces the binding-tax spine (see new §8.8). Decide
during drafting; both subtitles are on the table.

**Author:** [author]
**Programme:** MSc Cybersecurity
**Supervisor:** [supervisor]
**Last updated:** 2026-05-26

---

## Working assumptions for this outline

These are the structural choices made during the 2026-05-26 outline brainstorm. They
can be revisited as drafting progresses; for now they shape the chapter list and the
page budget.

1. **Discovery narrative.** The thesis is written in the order the work actually
   unfolded: original framing → gate-count analysis → reframing → reframed
   contributions. The negative result (no hierarchical-Merkle gate-count benefit) is
   foregrounded and explained, not buried.
2. **Self-contained background, flexibly.** Chapter 2 explains ZKP, SNARKs, Plookup,
   Poseidon2, Merkle commitments, and the TSP-relevant complexity background from
   scratch, written for an examiner who is *not* a ZKP specialist. Where a topic only
   matters for one later result (e.g., Plookup as it bears on the ~87 gates finding),
   the explanation can stay concise rather than full-textbook.
3. **Dedicated Related Work chapter, provisionally.** Chapter 3 is included as a
   conventional standalone chapter. If it turns out thin or forced during drafting,
   it can be folded into Chapter 2 (background) and Chapter 8 (dualism), with the
   folding-schemes literature ending up alongside its natural discussion point in
   Chapter 8.5.
4. **No notation chapter.** Notation is introduced inline as variables appear. If the
   density grows uncomfortable during drafting, a short notation index can be added
   as front-matter or as Appendix D.
5. **Threat model as a section, not a chapter.** Section §4.5 carries the formal
   threat model for the flat circuits; the hierarchical chapters reference it and add
   per-variant disclosure considerations in §9.6. This gives the cybersecurity
   perspective explicit framing without inflating it into a standalone chapter.
6. **Clustered TSP solver as Appendix B + separate document.** The solver is for a
   different specific TSP application and is documented in its own report. Appendix B
   gives a short integration overview so the combined-pipeline analysis in Chapter 11
   is reproducible.

---

## Page budget (rough — to be refined)

| Part | Chapters | Estimated pages |
|---|---|---|
| Front matter (abstract, TOC, lists) | — | 6–10 |
| Part I — Foundations | Ch 1–3 | 35–50 |
| Part II — Flat Baseline | Ch 4–7 | 35–45 |
| Part III — Hierarchical Decomposition | Ch 8–10 | 30–40 |
| Part IV — Conclusion | Ch 11–12 | 10–15 |
| Appendices | A–C | 15–25 |
| **Total body** | | **130–170 pages** |

Higher end of the MSc range, justified by significant empirical content (benchmarks
to N=500 + hierarchical frontier figure) and the need for thorough background.

---

## Front matter

- **Title page**
- **Abstract** (≤ 1 page) — the reframed thesis pitch from supervisor report §1.2,
  compressed.
- **Acknowledgements**
- **Table of contents** + **list of figures** + **list of tables**
- **Notation index** (optional; add only if needed during drafting)

---

# Part I — Foundations

## Chapter 1 — Introduction *(~10 pages)*

**Purpose.** Open the discovery narrative; motivate the work; state contributions;
preview structure.

- §1.1 Motivation — privacy-preserving combinatorial optimisation as a real
  application class. Concrete example: a logistics operator wanting to demonstrate
  route quality without disclosing the route or the cost matrix.
- §1.2 The original research question — *"at what N does hierarchical beat flat?"*
  How it was chosen, what answer was anticipated.
- §1.3 What we found instead — preview the variant-as-statement reframe, the dualism,
  the negative result. Section ends with the reframed thesis pitch from
  `supervisor_report_draft.md` §1.2.
- §1.4 Contributions — the four-point list from supervisor report §1.3: empirical
  flat baseline, negative result with structural explanation, variant-as-statement
  reframe, frontier-mapping methodology.
- §1.5 What this thesis does not claim — pre-empt NP-asymmetry overclaiming
  (supervisor report §1.4).
- §1.6 Thesis structure — short tour of Parts I–IV.

**Open questions for drafting:** length of the motivation example in §1.1 — a single
paragraph or a worked operational scenario? Probably the latter, but kept tight.

## Chapter 2 — Background *(~30–40 pages)*

**Purpose.** Make the thesis self-contained for an examiner who knows applied
cryptography but not ZK specifically.

- §2.1 Zero-knowledge proofs
  - §2.1.1 The interactive prover-verifier game
  - §2.1.2 Completeness, soundness, zero-knowledge
  - §2.1.3 Non-interactive proofs and the Fiat-Shamir transform
  - §2.1.4 Worked toy example (graph 3-colouring or sudoku)
- §2.2 SNARKs and circuit-based proof systems
  - §2.2.1 Arithmetic circuits over a prime field
  - §2.2.2 R1CS, AIR, and the ACIR intermediate representation
  - §2.2.3 PLONK and the polynomial commitment paradigm
  - §2.2.4 UltraHonk and Plookup *(concise — only what's needed for the ~87 gates
    finding to make sense)*
- §2.3 Cryptographic primitives in this work
  - §2.3.1 ZK-friendly hashing and Poseidon2
  - §2.3.2 Merkle commitments in the ZK context
- §2.4 The Travelling Salesman Problem
  - §2.4.1 Problem definition and applications
  - §2.4.2 NP-hardness, the verifier/finder asymmetry, and the implications for ZK
  - §2.4.3 Heuristic solvers (nearest-neighbour, 2-opt) and hierarchical / clustered
    approaches
- §2.5 Tooling: Noir and Barretenberg
  - §2.5.1 The Noir DSL and the proving pipeline
  - §2.5.2 ACIR opcodes vs UltraHonk gates *(forward reference to Finding 3)*
  - §2.5.3 Performance metrics: circuit size, proving time, proof size, verifier
    cost, peak memory

**Length flex.** Section 2.1 should be self-contained; 2.2 can lean concise where it
only services later findings; 2.4 should be tight because TSP is well-known
territory.

## Chapter 3 — Related Work *(~5–10 pages, provisional)*

**Purpose.** Position the contributions against existing literature.

- §3.1 ZK proofs over graph problems — what exists, what's missing for TSP
  specifically
- §3.2 Recursive and folding proof systems — Halo, Nova, ProtoStar, SuperNova; their
  natural problem classes; why they are out of scope here
- §3.3 Privacy-preserving combinatorial optimisation — MPC approaches, garbled
  circuits, TEEs as alternative trust models
- §3.4 Empirical methodology in ZK benchmarking — how others have measured and
  reported circuit costs; what this thesis does differently *(forward to Finding 4 on
  ACIR opcode count)*

**Provisional.** Drafted as a standalone chapter; if material is thin during writing,
fold §3.2 into Ch 8.5 (folding-schemes future direction) and §3.4 into Ch 7
(methodology) and remove this chapter.

---

# Part II — Flat Baseline

## Chapter 4 — Problem Formulation *(~8 pages)*

**Purpose.** State the cryptographic claim precisely; establish public/private
separation; introduce the threat model.

- §4.1 The TSP ZKP statement — Hamiltonian cycle existence with cost ≤ T against a
  committed cost matrix
- §4.2 Public-private separation — flat-full (matrix public) vs flat-Merkle (matrix
  committed)
- §4.3 Trust anchors for the Merkle commitment — the five mechanisms (authority
  signature, trusted oracle, cross-attestation, public timestamping,
  decommitment-on-dispute) from supervisor report §2.2
- §4.4 Threshold vs optimality — why cost ≤ T rather than "minimum cost"
- §4.5 **Threat model** *(cybersecurity perspective)*
  - §4.5.1 Adversary capabilities — malicious prover model (cheating-prover with
    polynomial computation); verifier honesty assumption
  - §4.5.2 What the proof system must guarantee — completeness, knowledge soundness,
    zero-knowledge
  - §4.5.3 What the proof system does *not* guarantee — input validity (the cost
    matrix must be bound by an external trust anchor; §4.3)
  - §4.5.4 Side-channel and metadata leaks — out of scope but acknowledged
  - §4.5.5 Forward reference to per-variant threat-model considerations in §9.6

## Chapter 5 — Flat Circuit Design *(~12–15 pages)*

**Purpose.** Walk through the design decisions that produced the five flat variants.

- §5.1 Four-group structure (range, permutation, edge cost, threshold)
- §5.2 Type rationale (u32, u64, Field, bool) — why each is chosen
- §5.3 Permutation check strategies — pairwise, sort, invperm, presence; analytical
  cost comparison
- §5.4 Matrix representation — flat-full vs flat-Merkle, with the privacy/cost
  trade-off named explicitly
- §5.5 Merkle proof verification — the leaf-index check and why it is
  soundness-critical
- §5.6 Design alternatives considered and rejected — Verkle trees, leaf domain
  separation, polynomial encoding, etc. (mirrors supervisor report §3.6)

## Chapter 6 — Implementation Details *(~10 pages)*

**Purpose.** Show enough engineering detail that the work is reproducible without
overwhelming the reader.

- §6.1 Noir circuit organisation — five circuit directories, shared structure
- §6.2 The Rust Merkle builder — purpose, JSON interface, Poseidon2 compression
- §6.3 Hash compatibility cross-validation — Rust ↔ Noir Poseidon2 testing
- §6.4 The Python pipeline — instance generation, solver, format_inputs, run.py
- §6.5 Worked examples — N=4 and N=8 walk-throughs of flat-Merkle (mirrors
  supervisor report §4.5–4.6)

## Chapter 7 — Flat Baseline Evaluation *(~12 pages)*

**Purpose.** Present the empirical findings on the flat circuits.

- §7.1 Methodology — N range, number of runs, hardware, what was measured
- §7.2 Circuit-size models per variant (the 7.25·N² + linear-coefficient fits)
- §7.3 The ~87 gates/Poseidon2-call finding — Plookup amortisation; comparison with
  the ~264 literature value; methodological implication
- §7.4 Proving time, verification time, peak memory
- §7.5 The N≈175 flat-full ↔ flat-Merkle crossover — empirical and theoretical match
- §7.6 ACIR opcodes as a misleading metric — the N≈30 vs N≈175 discrepancy

---

# Part III — Hierarchical Decomposition

## Chapter 8 — The Optimisation-ZK Dualism *(~12 pages)*

**Purpose.** Make the central conceptual contribution — explain why hierarchical ZK
does not give the algorithmic speedup that classical hierarchical TSP gives.

- §8.1 Hierarchical decomposition in classical TSP — what clustering does, why it
  works (search-space shrinkage)
- §8.2 The naive hierarchical ZK design — split the cycle into K segments, prove
  each independently, stitch with a glue circuit. What we expected (parallel
  speedup AND gate savings).
- §8.3 The gate-count cancellation — why hierarchical Merkle does *not* reduce total
  gates over flat Merkle. The O(N) partition check + K boundary Merkle proofs in
  the glue exactly absorb the per-segment savings.
- §8.4 NP asymmetry and how it transfers (or doesn't) under decomposition —
  classical hierarchical exploits the asymmetry by trading verification overhead for
  search reduction; in ZK there is no search to reduce.
- §8.5 Embarrassingly-parallel vs algorithmic speedup — careful distinction; the
  parallelism benefit is real but is not what "hierarchical decomposition" usually
  means in algorithm design.
- §8.6 Folding schemes as a future direction — Nova/ProtoStar/SuperNova as the
  research direction that would test whether the dualism is intrinsic to TSP or to
  the proof system. Out of scope for this thesis.
- §8.7 Implications for proof-system design — the predictive heuristic: "does this
  problem factor locally?"
- §8.8 **The binding tax — the second structural result** *(added 2026-05-29 reframe)*
  - §8.8.1 One artifact, three symptoms — decomposition forces a binding step to
    recombine K independent segment-proofs; that binding manifests as *partition
    leakage*, *O(K) verifier cost*, and *verifier-side bookkeeping*, all of which are
    the shared public surface of independent proofs. They dissolve together by folding
    the binding into a proof.
  - §8.8.2 Two decisions generate the family — *where* binding lives (verifier-side /
    in-circuit / deferred) × *what* is bound (plaintext / hiding commitment / witness).
  - §8.8.3 The pick-two triangle — P (parallel + low per-prover mem) / V (O(1) verifier)
    / C (low prover overhead); each architecture gives exactly two; folding is the
    missing corner. The frontier is this triangle *at fixed privacy*.
  - §8.8.4 Relation to the dualism — §8 explains *why decompose* (parallelism is the
    only payoff); §8.8 explains *how the variants pay* for it. Source:
    `FRONTIER_REFRAME.md` / DESIGN.md §9.

**Cross-refs.** §8.3 ↔ Finding 6; §8.4 ↔ Finding 8; §8.7 ↔ §10.5 and §11.2; §8.8 ↔
§9.1, §9.6, §10.5, §12.2.1.

## Chapter 9 — Three Hierarchical Variants *(~15–18 pages)*

**Purpose.** Present the variant-as-statement reframe and the variants as *points in
the binding-tax design space* (§8.8) on the privacy/cost frontier.

**Note (2026-05-29 reframe; committed-* implemented 2026-05-31).** This chapter was
titled "Three Hierarchical Variants" (A, A++, B). It now presents the family as **one
progression line**, not a flat catalogue: A and A++ are the **diagnosis** (A discloses
the partition; A++ hides the node-sets but only behind confirmation oracles) *and* the
low-cost **disclosure-regime** points; **committed-A / committed-A++** are the **cure**
(bind on blinded commitments — partition hidden computationally, reveals only K);
**recursion** is the perfect-hiding endpoint (partition structurally absent, at the
≈704k×K cost). Each step removes exactly one binding-tax symptom (§8.8). The chapter
title may be relaxed to "Hierarchical Variants" during drafting. See DESIGN.md §9,
`FRONTIER_REFRAME.md`, and `HIERARCHICAL_EXPLAINED.md` §9b.

- §9.1 The variant-as-statement reframe — variants don't compete on cost; they prove
  different statements. Mirrors supervisor report §7.7 / Finding 10. *Now subordinated
  to the binding-tax spine: each variant is a choice of where binding lives and what is
  bound (§8.8.2).*
- §9.2 Common architecture — K sub-proofs + glue, independent composition (model
  (i)), N divisibility discipline, K parameterisation, glue sharing between A/B
- §9.3 Variant A — Merkle, sorted-nodes-public
  - §9.3.1 Sub-circuit (five constraint groups) and glue interface
  - §9.3.2 Worked example at N=8, K=2 (the example from supervisor report §8)
  - §9.3.3 Soundness argument
  - §9.3.4 Gate-count prediction
- §9.4 Variant A++ — Merkle, grand product + in-circuit Fiat-Shamir
  - §9.4.1 The grand-product multiset commitment
  - §9.4.2 The hash-chain construction and challenge derivation
  - §9.4.3 Soundness chain (Fiat-Shamir + Schwartz-Zippel)
  - §9.4.4 Cost analysis: ~5.5% sub-circuit overhead; O(N) → O(K) glue
- §9.5 Variant B — flat-full, sub-matrix public
  - §9.5.1 Sub-circuit (sub-matrix as public input) and glue (reuses A's logic)
  - §9.5.2 Gate-count analysis: O(N²/K)
- §9.5a **Committed-A / Committed-A++** *(implemented 2026-05-31)* — the leak-closing
  move (the *cure* for the diagnosis A/A++ provide): bind on hiding commitments instead
  of plaintext, glue checks openings in-circuit (G0), verifier compares opaque
  commitments. Closes the partition leak while keeping the non-recursive architecture
  (stays in the O(K)-verifier corner — parallelism + low per-prover memory preserved).
  - §9.5a.1 Construction — `C_i = fold(r_i, [values])` over the 2-input Poseidon2;
    committed-A++ folds the A++ aggregates `[P_i, h_in, h_out, start, end, partial_cost]`
    (drops the sub's G7); committed-A folds `[cycle_segment…, partial_cost]` (drops the
    per-segment sort). Public surface `{root, X, C_i}` / `{root, C_i}`; bookkeeping is ZK.
  - §9.5a.2 Hiding type — computational (Poseidon, implemented) vs unconditional-content
    (Pedersen, analytical: costlier in-circuit, computational binding). See §9.6.6.
  - §9.5a.3 **Equal-privacy finding** — committed-A and committed-A++ reach the *same*
    privacy class (multiset computational, interior order info-theoretic, reveal K); they
    differ only in glue cost/mechanism (O(N) sort + O(N) commit-fold vs distributed
    grand-product + O(K) commit-fold). The equal-privacy restatement of the F7 "A not
    dominated by A++" result.
  - §9.5a.4 Status — **built + validated**: circuits `hierarchical_{segment,glue}_{c,cfs}`,
    builder `--hierarchical-{c,cfs}`, verifiers/harnesses `verify_hier_*` / `run_hier_*`,
    correctness suites `test_hierarchical_{c,cfs}.py` (7/7 each). Sweeps pending.
    Source: `HIERARCHICAL_EXPLAINED.md` §9b, `FRONTIER_REFRAME.md` Part 4–5.
- §9.5b **Recursion as a first-class variant** *(added 2026-05-29 reframe)* — in-circuit
  binding: the outer verifies the K inner proofs, their public inputs become witness,
  public surface collapses to `(root, threshold)`. Implemented + benchmarked.
  - §9.5b.1 Why it is the perfect-hiding endpoint — partition structurally absent
    (assumption-free), same surface as flat_merkle.
  - §9.5b.2 Inner-circuit choice — A++-inner vs A-inner; the O(1)-surface argument
    (outer flat ~704,363 gates, N-independent). Source:
    `Recursive_inner_circuit_choice_explained.md`.
  - §9.5b.3 Cost — ~704k gates per in-circuit verification, ~K× total; the prover-side
    price of collapsing the binding tax (the C corner of the §8.8.3 triangle).
- §9.6 Privacy analysis and per-variant threat-model considerations
  - §9.6.1 Quantitative privacy bound for Variant A — the worked example
    (10.3 bits at N=8) and the general formula
  - §9.6.2 Threat-model dependence — matrix-private vs matrix-public regimes;
    cycle-recovery feasibility under each
  - §9.6.3 What A++ buys back vs A
  - §9.6.4 B's privacy profile — partition + sub-matrix disclosure
  - §9.6.5 **The privacy ladder** *(added 2026-05-29; committed-* implemented 2026-05-31)*
    — assumption-decreasing ordering: B → A → A++ → committed-A/committed-A++ (Poseidon,
    same rung) → committed(Pedersen) → recursion/folding/flat. Two mechanisms: *commit to
    hide it* vs *don't put it there at all*
    (assumption-free). Clarify that flat/recursion "perfect hiding" is **structural**
    (public surface carries no partition info), not information-theoretic ZK — the
    SNARK's ZK is identical across all variants and is not a discriminator. Per-variant
    table in DESIGN.md §9.6.
  - §9.6.6 **Commitment taxonomy box** *(added 2026-05-29 reframe)* — the hiding/binding
    tradeoff: Poseidon (computational hiding, cheap) vs Pedersen (unconditional content
    hiding, costly, computational binding). A++'s `P_i` framed as a binding-but-
    unblinded commitment (oracle, ~C(N,M)); the commitment fix = adding blinding.
- §9.7 Use-case mapping — which variant for which real-world scenario (mirrors
  supervisor report §7.7 use-case table)

**Note on order.** Variants are presented A → A++ → B in this chapter, even though
the implementation order is A → B → A++ (since B reuses A's glue and is the cheaper
second variant — see DESIGN.md §8 architectural commitments). The presentation order
follows the conceptual progression (simple baseline → privacy refinement → gate
optimisation), not the implementation order.

## Chapter 10 — Hierarchical Empirical Results *(~10 pages)*

**Purpose.** Present the frontier figure and supporting evidence.

- §10.1 Methodology — N ∈ {48, 96, 192, 480}, K ∈ {2, 4, 8}, runs per cell
- §10.2 Per-variant gate counts vs analytical predictions
- §10.3 Parallel proving time — single-machine vs K-process timing
- §10.4 Per-prover peak memory
- §10.5 **The frontier figure** — (total gates, parallel wall-clock, per-prover
  memory) panels × (Variant A, A++, B, flat-Merkle baseline). Privacy bits
  annotated.
  - §10.5a **Reframe (2026-05-29; committed-* implemented 2026-05-31):** redesign as the
    **pick-two triangle at fixed privacy** (§8.8.3) with **recursion as the perfect-hiding
    endpoint** and **committed-A / committed-A++** as the equal-privacy non-recursive
    points. Equal-privacy comparison panel: flat / committed-A / committed-A++ / recursion
    all at the "partition hidden" slice, reading the P/V/C triangle directly; A / A++ drawn
    as the upstream *disclosure / oracle-leak* points on the same progression line (arrows,
    not co-equal markers). Folding shown as the empty (P+V+C) corner. Cost coordinates from
    the `results/hier_c.csv` / `results/hier_cfs.csv` sweeps. Source:
    `FRONTIER_REFRAME.md` Part 2/5, `HIERARCHICAL_EXPLAINED.md` §9b/§14.5.
- §10.6 Comparison with flat baseline — anchored at N=480 against flat-Merkle's
  N=500

---

# Part IV — Conclusion

## Chapter 11 — Discussion *(~8 pages)*

**Purpose.** Step back and interpret.

- §11.1 The variant-as-statement reframe in retrospect — was it the right framing?
  what alternative framings remained on the table?
- §11.2 Practical guidance — a decision tree for "given my use case, which variant?"
  Building on §9.7 with more granular guidance.
- §11.3 Limitations and threats to validity
  - §11.3.1 Single proof system (UltraHonk only); generalisation unclear
  - §11.3.2 Single hardware (single machine); parallel-prover claims are
    extrapolations from sub-circuit timings
  - §11.3.3 Specific TSP variant (symmetric/asymmetric/Euclidean — clarify)
  - §11.3.4 No formal soundness proof for A++'s Fiat-Shamir construction (relies on
    standard arguments)
- §11.4 Combined pipeline with the clustered solver — the cross-domain comparison
  promised in §1.3; refers to the separate solver document and Appendix B

## Chapter 12 — Conclusion and Future Work *(~5 pages)*

**Purpose.** Close the loop.

- §12.1 Summary of contributions — restated from §1.4 with the supporting evidence
  for each
- §12.2 Future work
  - §12.2.1 Folding-scheme variant (Nova/ProtoStar) — the only unimplemented
    frontier corner; would remove the ~704k×K per-step verifier overhead measured
    for recursion (Ch 10 / report §7.8). *Reframe (2026-05-29): folding is precisely
    the corner that breaks the §8.8.3 pick-two triangle — it targets P + V + C
    simultaneously (parallel proving, O(1) verifier, and low prover overhead). Frame it
    as the single design that collapses the binding tax (§8.8.1) at low cost on every
    axis.*
  - §12.2.2 Other graph problems with non-local constraints (k-clique, graph
    colouring) — does the dualism apply?
  - §12.2.3 Threat-model extensions — actively malicious verifier, network
    adversary
- §12.3 Closing reflections — what the discovery process suggests about ZK
  applied research more generally

---

# Appendices

## Appendix A — Circuit Code Listings *(~10 pages)*

Selected main.nr files for the most important variants. Cross-referenced from
Chapters 5, 6, 9. Full code available in the repository.

- A.1 flat_merkle_presence (annotated)
- A.2 hierarchical_segment (Variant A) — once implemented
- A.3 hierarchical_glue (Variant A) — once implemented
- A.4 hierarchical_segment_fs (Variant A++)
- A.5 hierarchical_segment_cfs / hierarchical_glue_cfs (committed-A++) — the commitment
  fold (G8/G0) + dropped sub-G7 are the diff worth showing against A.4
- A.6 hierarchical_segment_c / hierarchical_glue_c (committed-A) — the glue-side O(N) sort
  over witnessed nodes + commitment recompute

## Appendix B — Clustered TSP Solver Integration *(~5 pages)*

Cross-references the separate solver document. Short summary so this thesis is
self-contained for the combined-pipeline analysis in Chapter 11.

- B.1 What the solver does — clustering, local optimisation, stitching
- B.2 Pipeline integration — solver output as ZKP input
- B.3 Empirical observations from combined runs
- B.4 Pointer to the separate solver document

## Appendix C — Full Benchmark Tables *(~10 pages)*

The full numerical tables underlying the figures in Chapters 7 and 10. Per-variant,
per-N, per-K, per-run, with mean ± std.

## Appendix D — Notation Index *(optional, add if needed)*

Single-page glossary of symbols (N, K, M, DEPTH, T, c, X, P_i, h_i, …) introduced
throughout the thesis.

---

# Mapping: outline ↔ existing materials

This is for the drafting phase — each chapter has a starting point in already-written
material.

| Chapter | Starting material |
|---|---|
| Ch 1 Introduction | supervisor_report §1 |
| Ch 2 Background | new writing; some material from supervisor_report §3.5 (Poseidon2), §3.1 (UltraHonk), §2.3 (threshold) |
| Ch 3 Related Work | new writing |
| Ch 4 Problem Formulation | supervisor_report §2.1, §2.2, §2.3; new §4.5 threat model |
| Ch 5 Flat Circuit Design | supervisor_report §3 (most subsections) |
| Ch 6 Implementation | supervisor_report §4; circuit source comments |
| Ch 7 Flat Evaluation | supervisor_report §5, §6 (Findings 1–5) |
| Ch 8 Dualism | supervisor_report §7; **§8.8 binding tax → DESIGN.md §9 + FRONTIER_REFRAME.md Part 1–2** |
| Ch 9 Hierarchical Variants | supervisor_report §7.7, §8; SESSION_SUMMARY hierarchical sections; **§9.5a/b + §9.6.5/6 → DESIGN.md §9 + FRONTIER_REFRAME.md Part 3** |
| Ch 10 Hierarchical Empirical | new writing once benchmarks are run; **§10.5a triangle → FRONTIER_REFRAME.md Part 2/5** |
| Ch 11 Discussion | supervisor_report §6 (Findings 8, 10, 11); new writing |
| Ch 12 Conclusion | supervisor_report §8 future work; new writing |
| Appendix A | repository source |
| Appendix B | separate solver document + new integration text |
| Appendix C | results/*.csv post-processed |

---

# Open structural questions

These are things the outline does not yet resolve. They are not blocking — drafting
can start with the structure as-is and resolve them as material accumulates.

1. **Does Chapter 3 survive?** If during drafting it turns out to be ~3 pages of
   forced references, fold its material into Chapters 2 and 8 and delete the
   chapter. If it grows to 8+ pages of substantive comparison, keep it.
2. **Does Appendix D appear?** Decide once the notation density of the body is
   visible. Likely yes — the hierarchical chapters introduce K, M, P_i, h_i, X, c
   which compound quickly.
3. **How much of the original discovery narrative goes in §1 vs §8?** Current plan:
   §1 previews briefly, §8 develops fully. If §1 feels too thin without the
   discovery story it can absorb more; conversely, if §8 feels redundant after §1
   it can be trimmed.
4. **Variant order in Chapter 9.** Current plan: A → A++ → B (conceptual order).
   Alternative: A → B → A++ (implementation order, easier writing flow). Decide
   when drafting Chapter 9.
5. **Does the cybersecurity perspective need more space than §4.5 + §9.6?** If yes,
   add a §11.5 "Cybersecurity perspective synthesis" before §11.4.

---

# Drafting order suggestion

Not strictly the order chapters should be read in, but the order they can be drafted
without blocking on missing material:

1. **Ch 5, Ch 6, Ch 7** — flat baseline material is settled and ready
2. **Ch 8, Ch 9 (without §9.6.2 quantitative bounds)** — hierarchical conceptual
   material is settled; per-variant gate analyses are mostly done
3. **Ch 4 (with threat model §4.5)** — problem formulation can be written once the
   variant material is fresh
4. **Ch 2** — background, written for the audience the rest already targets
5. **Ch 1, Ch 3** — introduction and related work; both benefit from knowing the
   final shape of the contributions
6. **Ch 10** — empirical hierarchical results; blocked on running the actual
   benchmarks
7. **Ch 11, Ch 12** — discussion and conclusion; written last
8. **Appendices** — compiled at the end

This order also matches roughly the order in which the actual research will conclude
its remaining work: hierarchical implementation → benchmarks → write-up.
