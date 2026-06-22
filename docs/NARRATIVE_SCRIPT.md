# Narrative Script — The Thesis as a Three-Act Play

> **Chapter remap (2026-06-10) + framing update (2026-06-22).** This script predates the linear
> 7-chapter outline; its *staging* (scenes, characters, hinges, lines) is mostly current, but two
> things are stale beyond the chapter numbers: **(a)** the **frontier** is no longer "P/V/C at
> fixed privacy" — it is the pick-two of **cheap / parallel / structurally private**, with
> verification *riding with* privacy rather than being a separate axis (canonical:
> `FRONTIER_REFRAME.md` F4, Ch 5 `sub:pick-two`, Ch 1 §1.4); **(b)** the Ch 1 "original question →
> ~1.5%-pivot → reframe" staging (Scene 1, §1.2–1.3 below) is **not** used in the drafted Ch 1,
> which formalizes the problem (§1.2 Problem Definition) and poses the RQs (§1.3) directly.
> Chapter numbers here are the old 12-chapter scheme; translate on read:
>
> | Old (this doc) | New (`Thesis_Outline.md`) |
> |---|---|
> | Ch 1 Introduction (Scene 1) | Ch 1 |
> | Ch 2 Background (Scene 2) | Ch 2 |
> | Ch 4 Problem Formulation (Scene 3) | §2.5–2.6 |
> | Ch 5 Flat Circuit Design (Scene 4) | §4.1–4.2 |
> | Ch 7 Flat Evaluation (Scene 5) | §4.5 (the inversion) + §6.2 (the sweep) |
> | Ch 8.1–8.5 dualism (Scene 6) | §5.1 |
> | Ch 8.6–8.8 tax / lever / triangle (Scene 7) | §5.2–5.4 |
> | Ch 9 walk: Scenes 8 / 9 / 10 / 11 | §5.6 / §5.7 / §5.8 / §5.9 |
> | Ch 10 results: Scenes 12 / 13 | §6.1+§6.5 / §6.6+§6.8 |
> | Ch 11–12 | Ch 7 |
>
> Also stale below: every **[PROJECTED]** flag — the isolation sweeps have since landed
> (measured ~6.5× `plain-product`, ~4.7× `plain-sort` at N=3000 K=8; see
> `ISOLATION_BENCHMARK.md` status banner). Read "[PROJECTED]" as "measured, cite
> `results/hier_*_iso.csv`".

*The drafting blueprint for the body chapters. Every variant is a character with a
role, an entrance, lines (the claims it lands), and interactions (the comparisons). The
dramaturgy is not decoration — each archetype **is** the variant's argumentative job, so if a
scene has no dramatic function it has no thesis function and should be cut. Companion to
`Thesis_Outline.md` (Part 0 = the framework this script stages; the §-numbers below are its
chapters). Sources: `FRONTIER_REFRAME.md`, `NARRATIVE_FRAMING.md`, `HIERARCHICAL_EXPLAINED.md`.*

## How to use this document
- **Per scene:** *Setting* (where) · *On stage* (who) · *Beat* (narrative function) · *Lines*
  (the exact claims to land — draft from these) · *Interaction* (the comparison + its fairness
  control) · *Artifacts/data* (what to cite) · *Hinge out* (the transition sentence).
- **"Bulletproof" test:** a scene is ready to draft when its *Lines* can be written as
  paragraphs and its *Interaction* names the one variable that moved and the control that keeps
  it fair. If either is vague, the scene isn't ready.
- Numbers below are the current measured values (N≈480/500 anchor) — verify against the live
  `results/*.csv` before they go in the body. (The isolation sweeps have landed; former
  **[PROJECTED]** values are now measured — `results/hier_*_iso.csv`.)

---

## Dramatis Personæ — the cast

| Character | Archetype | Argumentative job | The one line it says to the reader |
|---|---|---|---|
| **flat_merkle_sort** | The Incumbent | the monolithic, perfect-hiding baseline everyone is measured against | *"Hide everything in one proof — succinct verifier, but serial and unparallelizable."* |
| flat_full_pairwise / _sort | The Ancestors | establish the four-group structure + the permutation-check axis | *"Here is the statement, and the naïvest way to check a permutation — now improve me."* |
| **flat_merkle_grand_product** | The Body Double | a stunt double for flat_sort wearing the gp mask; a control, off the frontier | *"At K=1 I'm a strictly worse trade — which is exactly why I'm the clean control."* |
| **plain-sort** (hierarchical_segment) | The Honest Fool | the simplest binding (external, plaintext) → exposes the stitching tax raw | *"Decompose and bind plainly: cheapest and deterministic — but I disclose the partition."* |
| **plain-product** (hierarchical_segment_fs) | The Chekhov's Gun | refines the surface but isn't cheaper; its payoff is deferred to recursion | *"I shrink the surface O(M)→O(1); I cost more, not less — trust me, you'll see why."* |
| **committed-sort / committed-product** | The Twins | the cure (blind the commitment); secretly the same privacy rung | *"Blind the binding: the leak closes, and despite our different mechanisms we are equals."* |
| **recursion** (plain-product-inner) | The Final Form | bind in-circuit → all three symptoms collapse, at a heroic prover cost | *"Verify the pieces inside the proof; the partition vanishes — and I pay 704k×K for it."* |
| recursive-sort | The Control Twin | shadows recursion to isolate aggregation from mechanism | *"Recurse on the sort inner so the mechanism matches flat — read the pure aggregation cost off me."* |
| **folding** | The Ghost | the corner that breaks the triangle; named, never built | *"I could give you all three at once — but I'm a different backend, and a different thesis."* |

## The Forces (the drama, not the cast)

- **The Law of the World — the dualism.** Decompose a non-local problem and you get *no*
  algorithmic ZK speedup; the only payoff is parallelism. *Seeded* Ch 2 §2.4.2 (NP
  finder/checker asymmetry), *pronounced* Ch 8 §8.3–8.5.
- **The Antagonist — the stitching tax.** Recombining K independent proofs is one artifact with
  three coupled symptoms: **partition leak / O(K) verifier / bookkeeping**. Every decomposed
  character must contend with it. Revealed Ch 8 §8.6.
- **The Two Masks — the fingerprint lever** (deterministic **sort** vs probabilistic
  **grand-product+FS**). A *prop*, not a character: every decomposed character handles it,
  buying O(1) surface with computational soundness. Its meaning shifts each act (§0.4). Named
  Ch 8 §8.7.
- **The Chorus — "total work is conserved."** Repeated wherever the reader might think hierarchy
  beats flat. The win is *parallelizability of the same work*, never less work.

## The five structural rules that govern the script

1. **Compare to motivate (Ch 9) vs compare to measure (Ch 10).** Ch 9's transitions *are*
   pairwise, qualitative comparisons ("why this variant exists"); Ch 10 gathers the quantitative,
   cross-cutting comparisons ("what it costs"). No magnitude claims in Ch 9 beyond a forward-ref.
2. **The per-variant template (6 beats), used identically for plain-sort, plain-product, committed-\*, recursion:**
   *(i)* the transition (one variable changed) · *(ii)* construction · *(iii)* the row-reading
   (the lever's meaning here) · *(iv)* soundness consequence · *(v)* what it buys/costs
   (qualitative) · *(vi)* privacy class. Sameness is what makes the walk read as a controlled
   experiment.
3. **The three fairness controls** (stated once, Ch 10 §10.1; invoked by name thereafter):
   **(1) privacy class** — compare only within a slice (committed-\* *exist to create the slice*);
   **(2) mechanism** — hold sort/gp fixed (read down a *column*; the *diagonal* is forbidden);
   **(3) aggregation model** — report *total* (CPU work, conserved) and *parallel* (wall-clock,
   the win) both, labeled, never silently one.
4. **The lever's four readings** (Ch 8 §8.7 plants; each Ch 9 scene collects one): flat = pure
   cost (benefit-zero) · plain-sort/plain-product = live trade (neither dominates) · committed = privacy-neutral ·
   recursion = soundness-only + outer-surface.
5. **The reveal is earned, not asserted.** The flat↔recursion dilemma is a *derived synthesis*
   at the Ch 10 climax, after both poles are built — never a Ch 1 cold open (only a one-line signpost there).

## Stage-presence timeline

```
Chapter:            1   2   4   5   6   7  | 8   9  | 10  11  12
─────────────────────────────────────────────────────────────────
flat_merkle_sort    .   .   o   ███ █   ██ | █   █    █   .   .     LEAD (carried as K=1)
flat_full_*         .   .   .   ██  .   █  | .   .    .   .   .     ancestors
flat_merkle_gp      .   .   .   o   .   ██ | .   .    █   .   .     body double (Ch7 twist, Ch10 control)
A                   .   .   .   .   .   .  | .   ██   █   .   .     the Fool (diagnosis)
plain-product                 .   .   .   .   .   .  | .   ██╌╌╌█→  .   .     the Gun (fires in Scene 11)
committed-sort/plain-product     .   .   .   .   .   .  | .   ██   █   .   .     the Twins
recursion           (·)  .   .   .   .   . | (·) ███  █   █   █     the Final Form (S1 promise → S11 climax)
recursive-sort         .   .   .   .   .   .  | .   o    █   .   .     control twin
folding             .   .   .   .   .   .  | o   .    .   o   ██    the Ghost
─────────────────────────────────────────────────────────────────
dualism (Law)       .   o   .   .   .   .  | ██  ·    ·   ·   .     seeded §2.4, pronounced Ch8
stitching tax (Antag) .   .   .   .   .   .  | ██  ██   █   ·   .
fingerprint lever   .   .   .   ██  .   ██ | ██  ██   ██  .   .     the Two Masks — every decomposed scene
"total work conserved" (Chorus)  ─────────── repeated Ch 8, 9, 10 ───────────
```
`███`=lead scene · `██`=on stage · `█`=present · `o`=cameo · `(·)`=foreshadowed · `╌→`=gun fires

---

# ACT I — The Old World *(Ch 1–7)*

## Scene 1 — "The Promise" *(Ch 1 — Introduction)*
- **On stage:** the narrator; recursion *promised* but unseen; flat_merkle_sort named.
- **Beat:** motivate the work; plant the two-poles tension; tell the discovery story; do **not** construct anything.
- **Lines:**
  - *Motivation (§1.1):* a logistics operator must convince a client its route meets a budget T without revealing the route (operational secret) or the cost matrix (proprietary rates). Privacy-preserving combinatorial optimization is the application class.
  - *The original question (§1.2):* "at what N does hierarchical ZK beat flat?" — natural, because classical hierarchical TSP *does* give a speedup.
  - *The pivot (§1.3 — the "how"):* a total-gate-cost analysis found hierarchical-Merkle ~1.5% **worse** than flat-Merkle; the crossover doesn't exist; that negative result forced the reframe to the **stitching tax / frontier**. *(Trailer; the rigorous accounting is Scene 6 / §8.3.)*
  - *The signpost (§1.6):* "the design space has two perfect-hiding extremes — flat and recursion — and a family between them that trades the verifier for cheapness." One paragraph, no cost asserted.
- **Interaction:** none yet (orientation only).
- **Artifacts/data:** the ~1.5% no-gain figure (cite Ch 8).
- **Hinge out:** *"Before any of this can be made precise, the world needs its rules."* → Ch 2.

## Scene 2 — "The Rules of the World" *(Ch 2 — Background)*
- **On stage:** the world's physics (ZK, SNARKs, Poseidon2, Merkle, TSP); **the Law, seeded.**
- **Beat:** make the thesis self-contained for a non-ZK examiner; plant the dualism's root cause as neutral background.
- **Lines:**
  - ZK completeness/soundness/ZK; Fiat–Shamir; UltraHonk + Plookup (concise — only enough for the ~87-gates finding).
  - Poseidon2 + Merkle commitments in the ZK setting.
  - *TSP (§2.4):* definition; **NP finder/checker asymmetry (§2.4.2)** — finding is hard, checking is easy; *this is the seed.* **Heuristic + clustered solvers (§2.4.3)** — *why* clustering speeds classical TSP: the search space shrinks N! → ~K·(N/K)!·K!. Taught **neutrally**, as the optimizer's win, with no hint yet that ZK will refuse it.
- **Interaction:** none.
- **Artifacts/data:** the search-shrinkage formula.
- **Hinge out:** *"With the primitives in hand, state exactly what is being proved — and what is kept secret."* → Ch 4.

## Scene 3 — "The Contract" *(Ch 4 — Problem Formulation)*
- **On stage:** the statement; the matrix-privacy fork.
- **Beat:** sign the cryptographic contract; introduce the first privacy axis and the honest fine print.
- **Lines:**
  - *Statement (§4.1):* prover knows a Hamiltonian cycle over N nodes with total cost ≤ T against a committed cost matrix.
  - *Public vs private matrix (§4.2):* flat-full (matrix public) vs flat-Merkle (matrix committed, root public). **Binding ≠ authenticity:** the proof shows the route is valid + cheap against *the committed matrix*; it cannot vouch that the matrix is the *real* one (garbage-in-garbage-out). Authenticity needs an **external anchor** (§4.3: signature/oracle/timestamp/dispute-reveal) or, in principle, an **in-circuit provenance proof** (prove in ZK the matrix carries a trusted authority's signature — private *and* authenticated; not implemented, named as future work §12.2).
  - *Use-case fork:* public matrix = only the route is secret (public road data; commit-before-reveal); private matrix = the cost structure itself is sensitive (proprietary rates; classified geography), and a trust anchor exists.
  - *Threat model (§4.5):* cheating prover, honest verifier; the proof does **not** guarantee input validity. **Adversary defined once, here.**
- **Interaction:** flat-full ↔ flat-Merkle as a *privacy* contrast (the cost contrast comes in Scene 5).
- **Artifacts/data:** the five trust anchors; the use-case table.
- **Hinge out:** *"Two representations of the matrix, two privacy regimes — now meet the circuits that realize them."* → Ch 5.

## Scene 4 — "Meet the Family" *(Ch 5 — Flat Circuit Design)*
- **On stage:** **flat_full_pairwise**, **flat_full_sort** (Ancestors); **the Two Masks' first appearance**; **flat_merkle_sort** crowned; **flat_merkle_grand_product** in the wings.
- **Beat:** build the flat circuits as a sequence of one-variable design choices; introduce gp *as a permutation mechanism* (no forward debt); crown the baseline.
- **Lines:**
  - *Four groups (§5.1):* range / permutation / edge-cost / threshold.
  - *Permutation mechanisms (§5.3 — the Masks enter):* pairwise (O(N²)) → sort (O(N)) → invperm/presence (mentioned) → **grand-product+FS**. The grand product is simply *the next mechanism* in this family — **not** a control built for a future comparison. **The key observation, planted here:** at K=1 the public surface is already O(1)={root,T}, so the grand product's surface benefit is *zero* — it would be a strictly worse trade. So nobody *chooses* it at flat; it earns its place only as a mechanism worth measuring. *(Its later relevance to decomposition is a callback in Scene 9, not a promise here.)*
  - *Matrix representation (§5.4):* flat-full (matrix public, O(N²) public input) → **flat-Merkle** (matrix committed, O(N·log N) proof overhead). **Crown flat_merkle_sort** as the monolithic, perfect-hiding baseline the whole of Part III answers to.
- **Interaction:** pairwise→sort = the permutation-cost step (one variable); full→Merkle = the matrix-commit step (one variable). Both *compare-to-motivate*.
- **Artifacts/data:** the circuit dirs; the four-group decomposition.
- **Hinge out:** *"Five circuits built — now measure them, and watch the grand product do something it has no right to do."* → Ch 7.

## Scene 5 — "The First Twist" *(Ch 7 — Flat Baseline Evaluation)*
- **On stage:** all flat circuits; **flat_merkle_grand_product's big scene.**
- **Beat:** present the flat findings; land the witness-time inversion as an anomaly the reader files away.
- **Lines:**
  - *Models (§7.2):* circuit_size ≈ 7.25·N² + linear; per-variant fits.
  - *The ~87 gates finding (§7.3):* Poseidon2 amortizes to ~87 gates/call under Plookup (vs the ~264 literature value) — a methodological result.
  - *The inversion (§7.4 — the twist):* `flat_merkle_sort` vs `flat_merkle_grand_product` share GROUP 3 (Merkle) and GROUP 4 (threshold) byte-for-byte and expose the *identical* `{root,T}` — so the only moving part is GROUP 2. Result: gp compiles to **more** gates (+3.5–7.9%, shrinking with N) yet solves its witness **faster** (up to **−44%** at N=1000, *widening* with N). Cause: sort's `check_shuffle` does ~2N **dynamic-ROM** reads (data-dependent indices → memory-consistency machinery the *witness solver* must resolve); gp is pure straight-line, statically-indexed arithmetic. Both land in the same UltraHonk dyadic bucket → proof is **byte-identical (14 656 B)**, prove time/memory unchanged. *Gate count and witness cost are different currencies.*
  - *Crossover (§7.5):* flat-full ↔ flat-Merkle at **N≈175** (empirical = theoretical).
  - *(§7.6):* ACIR opcodes mislead (N≈30 vs N≈175 discrepancy).
- **Interaction:** the flat **row** of the future 2×2 factorial — a *strict* controlled experiment (only GROUP 2 moves). Fairness control: mechanism isolated, zero privacy delta. *(But the reader doesn't know it's a factorial row yet — that's Ch 10.)*
- **Artifacts/data:** the per-N table (sort/gp/Δ); 14 656 B; the dynamic-ROM explanation.
- **Hinge out (Act I → II):** *"The flat world is mapped and the Incumbent reigns — but one anomaly lingers, and one desire is unmet: we cannot parallelize."* → Ch 8.

---

# ACT II — Decomposition *(Ch 8–9)*

## Scene 6 — "The Temptation and the Law" *(Ch 8.1–8.5 — the dualism)*
- **On stage:** the desire (parallelism); **the Law.**
- **Beat:** decompose, expect a speedup, get the negative result.
- **Lines:**
  - *Temptation (§8.1–8.2):* **callback to §2.4.3** — "recall decomposition is a win for an optimizer." Split the cycle into K segments + a glue. Expect parallel proving *and* gate savings.
  - *The Law (§8.3):* the glue must restore the global partition check (sort/grand-product over all N) + K boundary Merkle proofs; this **exactly cancels** the per-segment saving — hierarchical-Merkle is ~1.5% *worse* than flat-Merkle in total gates. *(This is the Scene-1 pivot, now rigorous.)*
  - *Why (§8.4):* the NP asymmetry (seeded §2.4.2) does not transfer — classical hierarchy trades verification overhead for *search* reduction; ZK does no searching, so there is nothing to reduce.
  - *The only payoff (§8.5):* embarrassingly-parallel proving + per-prover memory — **not** algorithmic speedup. **Chorus:** total work is conserved.
- **Interaction:** hierarchical-Merkle ↔ flat-Merkle on *total gates* — the negative result. Fairness: same statement, same privacy.
- **Artifacts/data:** the ~1.5% overhead; the gate-accounting table.
- **Hinge out:** *"If decomposition saves nothing, why pay for it — and what is the price of stitching the pieces back together?"* → §8.6.

## Scene 7 — "The Antagonist Revealed" *(Ch 8.6–8.8 — stitching tax, lever, triangle)*
- **On stage:** **the stitching tax**; **the Two Masks get their meaning**; the triangle.
- **Beat:** name the antagonist; arm the lever; draw the battlefield.
- **Lines:**
  - *The tax (§8.6):* K independent proofs bind to nothing (`bb verify` only proves each internally consistent). Binding them = **one artifact, three symptoms** (partition leak / O(K) verifier / bookkeeping), generated by two decisions (*where* binding lives × *what* it binds). **Seed the reveal:** "the O(K) verifier will turn out to be the *cheap* way to pay."
  - *The lever (§8.7 — the Masks armed):* decomposition forces each segment to publish a partition **fingerprint**. Sort = the inherited fingerprint (the sorted node set): **structural soundness, but O(M)/segment surface + serial**. Grand-product = the lever on the surface symptom: **O(1) surface + distributable, paid in computational (ROM-probabilistic) soundness.** The price (structural→computational) *falls out* of the surface win — it was never an independent goal. *Same lever, same trade, at every level (§0.4).*
  - *The triangle (§8.8):* P (parallel + low mem) / V (O(1) verifier) / C (low prover overhead); each architecture gives exactly two; folding (the Ghost) is the empty corner. The frontier *is* this triangle at fixed privacy.
- **Interaction:** none yet (the map, not a comparison).
- **Artifacts/data:** the three-symptom anatomy; the P/V/C table.
- **Hinge out:** *"The tax must be paid by someone — enter the simplest payer."* → Ch 9, Scene 8.

## Scene 8 — "The Honest Fool" *(Ch 9 — plain-sort)*
- **On stage:** **A**; flat_merkle_sort (as the thing decomposed).
- **Beat:** the simplest binding exposes the tax in daylight.
- **Lines (per-variant template):**
  - *(i) Transition:* monolithic → K segments + glue, bound **externally on plaintext**.
  - *(ii) Construction:* each segment proves a Hamiltonian path of M=N/K nodes with internal Merkle proofs, publishes (sorted_nodes[M], start, end, partial_cost); glue checks connectivity, sorts the concatenated N nodes == [0..N), verifies K boundary Merkle proofs, sums ≤ T.
  - *(iii) Row-reading:* the lever = **sort**; the fingerprint is the plaintext sorted node set (O(M)/segment).
  - *(iv) Soundness:* deterministic — the sort *is* the multiset check; no Schwartz–Zippel error.
  - *(v) Buys/costs:* **cheapest total gates** of the decomposed family, deterministic; **but the partition is disclosed** (the tax, raw).
  - *(vi) Privacy:* **disclosed** — unconditional leak (node-sets + endpoints). The diagnosis + the disclosure-regime endpoint.
- **Interaction:** plain-sort ↔ flat_merkle_sort = the *decomposition step* (compare-to-motivate: buys parallelism, costs the tax).
- **Artifacts/data:** plain-sort's total gates 769,926 (K=2); privacy ~10.3 bits at N=8.
- **Hinge out:** *"A leaks because it binds plaintext — can we shrink what it exposes? Enter the over-engineer."* → plain-product.

## Scene 9 — "The Chekhov's Gun" *(Ch 9 — plain-product)*
- **On stage:** **plain-product**; plain-sort (as predecessor).
- **Beat:** refine the surface; deliver the honest "not cheaper"; place the gun on the mantel.
- **Lines (template):**
  - *(i) Transition:* sort/O(M) → **grand-product+FS / O(1)** (one variable: the mechanism/surface).
  - *(ii) Construction:* each segment derives a Fiat–Shamir challenge X via a Poseidon2 hash-chain over its cycle and publishes a single grand-product fingerprint P_i (+ endpoints, partial_cost); glue combines K fingerprints (O(K), not O(N)).
  - *(iii) Row-reading — the lever, live:* O(M)→O(1) surface + distributable check, **paid in** Schwartz–Zippel + FS-in-ROM soundness.
  - *(iv) Soundness:* probabilistic, ≤ N/|F| per check + FS-in-ROM (~2⁻²⁵⁴) — negligible.
  - *(v) Buys/costs — the defining honest beat:* **not cheaper** (relocates the O(N) work into the K segments: total 788,533 vs plain-sort's 769,926 at K=2; plain-sort is cheaper at *every* measured K — **F7, neither dominates**). Motivated on **surface + soundness + the recursion bridge — never on hiding.**
  - *(vi) Privacy:* still leaks — now via the **unblinded P_i oracle** (~C(N,M), confirms guesses). *plain-product is not a privacy improvement over plain-sort.*
  - **The gun:** "plain-product's real justification — the O(1), M-independent surface — pays off only when something verifies the segment *in-circuit*. Hold that thought."
- **Interaction:** plain-sort ↔ plain-product = the **lever, live** (row comparison, binding fixed). Fairness: both plaintext, both leak — so the delta is *pure mechanism*, not privacy.
- **Artifacts/data:** 788,533 vs 769,926 (K=2); plain-product glue O(K); the C(N,M) oracle bound.
- **Hinge out:** *"Both plain-sort and plain-product leak. The cure is not a new mechanism but a new *thing to bind* — enter the twins."* → committed-\*.

## Scene 10 — "The Twins" *(Ch 9 — committed-sort / committed-product)*
- **On stage:** **committed-sort and committed-product together** (they must co-enter).
- **Beat:** close the leak; reveal the equal-privacy finding.
- **Lines (template, shared):**
  - *(i) Transition:* plaintext → **blinded commitment** (one variable: *what* is bound).
  - *(ii) Construction:* each segment publishes one blinded `C_i = fold(r_i, [values])` over the 2-input Poseidon2 instead of the cleartext scalars; the glue takes values+openings as **witness**, recomputes C_i (asserts == public), runs all partition/boundary/threshold checks in-circuit. Verifier cross-check collapses to opaque-blob equality (`sub_i.C_i == glue.C_i`) — ZK for free. committed-sort folds the cycle-segment + cost (glue does the O(N) sort); committed-product folds the plain-product aggregates (glue does the grand product).
  - *(iii) Row-reading — privacy-neutral:* sort vs gp now differ **only** in glue cost/mechanism, not privacy.
  - *(iv) Soundness:* + commitment binding (Poseidon, computational).
  - *(v) Buys/costs:* leak closes (reveals only K commitments); **only the O(K)-verifier symptom remains.** Stays in the non-recursive corner (P + C kept).
  - *(vi) Privacy:* **computational** (reveals K; hiding on Poseidon) — one notch below flat/recursion's *structural* hiding, reached **without** recursion's gate tax.
  - **The reveal — equal-privacy finding:** committed-sort and committed-product land at the **same** privacy rung (multiset computational, interior order info-theoretic, reveal K). Identical twins; they differ only in glue cost. *This is the equal-privacy restatement of F7, and it needs both twins to be told.*
- **Interaction:** committed-sort ↔ committed-product = the **lever at equal privacy** (pure cost/soundness). Fairness: privacy held fixed → the delta is *only* mechanism.
- **Artifacts/data:** the C_i fold; public surfaces {root,X,C_i}/{root,C_i}; the equal-privacy class.
- **Hinge out (Act II → III):** *"One symptom survives — the O(K) verifier — and the gun is still on the mantel. To remove the last symptom, stop binding *outside* the proof."* → recursion.

---

# ACT III — Recursion and the Frontier *(Ch 9 climax → Ch 10)*

## Scene 11 — "The Final Form" *(Ch 9 — recursion; the climax)*
- **On stage:** **recursion (plain-product-inner)**; **plain-product (the gun fires)**; recursive-sort (Control Twin slips in).
- **Beat:** bind in-circuit; collapse all symptoms; fire the gun; pay the cost.
- **Lines (template):**
  - *(i) Transition:* external binding → **in-circuit (witness)** (one variable: *where* binding lives).
  - *(ii) Construction:* the outer circuit takes the K segment proofs **and their public inputs** as private witness, verifies them in-circuit (`verify_honk_proof`), and re-runs the glue logic on those now-trusted-but-private values. Public surface collapses to **{root, T}** — the same as flat_merkle.
  - *(iii) Row-reading — soundness-only:* inside recursion the partition is witness *either way*, so recursive-sort ↔ recursive-product trades **partition-check soundness + outer surface**, not hiding.
  - *(iv) Soundness:* + recursion KS + FS-in-ROM. The **Fiat–Shamir floor**: the outer must recompute the inner verifier's transcript challenges *in-circuit* — that recomputation is the *bulk* of the ~704k gates and is unavoidable for **any** inner.
  - *(v) Buys/costs:* all three symptoms fall at once; **the gun fires** — plain-product's O(1), M-independent surface keeps the recursive verifier **segment-size-independent: 704,363 gates whether N=8 or N=480**. An plain-sort inner (O(M) surface) would make the outer grow with N. Prover pays **~704k×K**: ≈1.47M gates (K=2, ~24 s, ~2.1 GiB), ≈3.0M (K=4, ~40 s, ~4.1 GiB); ≈**25×** plain-product at K=2, ≈**45×** at K=4 — the gap *widens* with K.
  - *(vi) Privacy:* **structural / assumption-free** (partition absent from the public surface) — the perfect-hiding endpoint, equal to flat.
- **Interaction:** recursion ↔ committed (the last symptom removed); recursion ↔ flat (the two perfect-hiding poles — *set up here, paid off in Scene 13*).
- **Artifacts/data:** 704,363; 14 656-byte ZK outer proof (458 fields vs 410 no-zk); the K-scaling table.
- **Hinge out:** *"Both perfect-hiding poles are now built. But every comparison so far moved one variable by hand — to compare across the whole space we need a fair instrument."* → Ch 10.

## Scene 12 — "The Line-up" *(Ch 10.1, 10.4 — methodology + the 2×2 factorial)*
- **On stage:** **flat_merkle_grand_product** and **recursive-sort** (the Body Doubles, sole purpose); all four factorial cells.
- **Beat:** state the fairness controls; run the de-confounding factorial.
- **Lines:**
  - *The three controls (§10.1, stated once):* **(1)** compare only within a privacy slice; **(2)** hold the mechanism fixed (read down a column; the **diagonal is forbidden**, e.g. `flat_sort ↔ recursive-product`); **(3)** report total *and* parallel cost, labeled.
  - *The factorial (§10.4):* {flat, recursive} × {sort, grand-product}. **Row** delta = mechanism cost (the Scene-5 inversion). **Column** delta = aggregation cost (flat→recursive at fixed mechanism). **Separability** (≈additive, no interaction) = *the dualism, quantified* — and the license for every column comparison. Headline clean cell-pair: **`flat_merkle_grand_product ↔ recursive-product`** (differ in *exactly* structure — no soundness caveat).
- **Interaction:** the factorial *is* the controlled instrument; the Body Doubles do their only job and exit.
- **Artifacts/data:** the 2×2 table with measured gates; the separability check.
- **Hinge out:** *"With a fair instrument in hand, bring the hiders onto one stage."* → §10.5.

## Scene 13 — "The Confrontation" *(Ch 10.5–10.6 — equal-privacy slice + frontier; the synthesis)*
- **On stage:** **flat_merkle_gp, committed-product, recursion** (equal-privacy slice); plain-sort / plain-product / committed-sort as upstream markers; folding's empty corner.
- **Beat:** crystallize the triangle; derive the flat↔recursion dilemma as an *earned* result.
- **Lines:**
  - *The headline fair comparison:* **{flat_merkle_gp, committed-product, recursion-plain-product}** — equal privacy (control 1), fixed mechanism (control 2), reported at both total and parallel cost (control 3). Read the **pick-two triangle** directly off their positions: flat = V+C (no P); committed = P+C (O(K) V); recursion = P+V (704k×K C).
  - *The earned dilemma:* "having built *both* poles, flat and recursion are the two perfect-hiding extremes — flat pays in serial cost, recursion in 704k×K prover work — and the hierarchical family is precisely what lives between them." *(Now a result the reader watched derived, not a Ch 1 teaser.)*
  - *The aggregation honesty (control 3):* total work — hierarchy never beats flat (the Chorus). Parallel wall-clock — hierarchy's win, **measured**: ~6.5× (`plain-product`) / ~4.7× (`plain-sort`) at N=3000 K=8 (`results/hier_*_iso.csv`).
  - *The upstream markers:* plain-sort (disclosed) and plain-product (oracle) drawn as arrows *into* committed-\*, not as co-equal points — the diagnosis the cure improved on.
  - *The empty corner:* folding sits at (P+V+C), unfilled.
- **Interaction:** the equal-privacy slice = the whole frontier in one figure; every other comparison is a controlled relaxation of one axis of this one.
- **Artifacts/data:** the frontier figure (option (a) headline / (b) lever-bars — `Thesis_Outline.md` §0.7); coordinates from `results/hier_{c,cfs}.csv`.
- **Hinge out:** *"One corner of the map is deliberately empty. Name who could fill it."* → Ch 12.

## Coda — "The Ghost" *(Ch 11–12 — Discussion + Future Work)*
- **On stage:** **folding** (named, never built); the cast in retrospect.
- **Beat:** interpret; hand over the sequel.
- **Lines:**
  - *Decision guidance (§11.2):* the compass — given a use case (disclosure ok? parallel hardware? O(1) verifier needed?), which point on the grid? Map to the Scene-3 use cases.
  - *Limitations (§11.3):* single backend; parallelism **projected** not measured (the one gap — isolation sweep); soundness argued by reduction (plain-product/recursion rest on FS-in-ROM + recursion KS, cited not reproved); no mechanized/circuit-level formal verification.
  - *Future work (§12.2):* **folding** (Nova/ProtoStar) is the corner that breaks the triangle — P+V+C at once, erasing recursion's 704k×K tax; a *different backend*, so out of this single-backend comparison by design. Also: the in-circuit provenance proof (Scene 3); other non-local graph problems (does the dualism generalize?).
- **Interaction:** folding ↔ recursion (what it would remove); folding ↔ the triangle (the corner it fills).
- **Hinge out:** *"The map is complete but for one square — and that square is the next thesis."*

---

# The hinges (the load-bearing transitions — write these first)

| # | From → To | The hinge question | The answer that pulls the reader across |
|---|---|---|---|
| H1 | Act I → Scene 6 | "decomposition saves nothing — why pay?" | parallelism is the *only* payoff (the Law) |
| H2 | Scene 6 → 7 | "what does stitching cost?" | the stitching tax (antagonist) |
| H3 | Scene 7 → 8 | "who pays it first?" | the simplest payer, plain-sort (the Fool) |
| H4 | Scene 8 → 9 | "can we shrink what plain-sort exposes?" | the lever — but it's not cheaper (the Gun) |
| H5 | Scene 9 → 10 | "both still leak — how to hide?" | bind a *commitment*, not plaintext (the Twins) |
| H6 | Scene 10 → 11 | "one symptom left — remove it?" | bind *in-circuit* (the Final Form; the Gun fires) |
| H7 | Scene 11 → 12 | "how to compare the whole space fairly?" | the factorial + three controls |
| H8 | Scene 12 → 13 | "what does the controlled comparison show?" | the triangle + the earned dilemma |
| H9 | Scene 13 → Coda | "what fills the empty corner?" | folding (the Ghost) |

# Comparison ledger (every comparison: home · isolates · control · data)

| Comparison | Scene/§ | Isolates | Fairness control | Data |
|---|---|---|---|---|
| pairwise → sort | S4 / §5.3 | permutation-check cost | one variable | O(N²)→O(N) |
| full → Merkle | S4 / §5.4 | matrix-commit cost | one variable | N≈175 crossover |
| **sort ↔ gp (flat)** | S5 / §7.4 | mechanism (witness inversion) | mechanism; zero privacy delta | +3.9% gates / −31–44% witness; 14 656 B |
| hier-Merkle ↔ flat-Merkle | S6 / §8.3 | the dualism (no gate gain) | same statement+privacy | ~1.5% worse |
| plain-sort ↔ flat_merkle_sort | S8 / §9.x | decomposition (tax appears) | one variable | parallelism vs leak |
| **plain-sort ↔ plain-product** | S9 / §9.x | the lever, live | binding fixed (both plaintext) | 769,926 vs 788,533 (K=2); F7 |
| **committed-sort ↔ committed-product** | S10 / §9.x | the lever at equal privacy | privacy fixed | equal-privacy rung |
| plain-product ↔ committed-product | S10 / §9.x | the blinding (leak closes) | mechanism+structure fixed | reveal K, computational |
| committed ↔ recursion | S11 / §9.x | in-circuit binding (last symptom) | privacy ~fixed | O(K) verifier → O(1); 704k×K |
| **down a column** (flat→committed→recursion) | S13 / §10.5 | the stitching tax | mechanism fixed | the spine |
| **2×2 factorial** | S12 / §10.4 | mechanism ⟂ aggregation (separability) | the de-confounder | `flat_gp ↔ rec-plain-product` clean |
| **equal-privacy slice** | S13 / §10.5 | stitching-tax cost at fixed privacy | privacy equalized (committed-\*) | the headline frontier |
| flat ↔ recursion | S13 / §10.6 | cost vs parallelism at perfect hiding | the earned climax | ~782k serial vs 704k×K |
| **[forbidden] flat_sort ↔ rec-plain-product** | — | — | confounds mechanism+aggregation | named as the trap |

# The refrains (repeat verbatim across Ch 8–10)
- **Total work is conserved** — hierarchy never beats flat on total gates; the win is parallelizability of the *same* work.
- **plain-product is never motivated on hiding** — it still leaks (the P_i oracle); its case is surface + soundness + the recursion bridge.
- **"Perfect hiding" of flat/recursion is structural, not IT-ZK** — the public surface carries no partition info; UltraHonk-ZK is identical across all variants and is not a discriminator.
- **The K× parallel speedup is MEASURED** — isolation sweeps `results/hier_*_iso.csv`; state the composition assumption (solo per-proof times; K-machine wall-clock = max segment + glue).

# Cross-reference map
| Scene | Outline § | Source notes |
|---|---|---|
| S1 | Ch 1 / Part 0 §0.1 | discovery narrative note (Ch 1) |
| S2 | Ch 2 §2.4 | §2.4.3 callback note (§8.1) |
| S3 | Ch 4 §4.2–4.5 | the binding-vs-authenticity discussion (session 2026-06-04) |
| S4 | Ch 5 §5.1–5.4 | Part 0 §0.3 (gp-as-mechanism) |
| S5 | Ch 7 §7.4 | `NARRATIVE_FRAMING.md` §8.5 |
| S6 | Ch 8 §8.1–8.5 | `FRONTIER_REFRAME.md` F-dualism |
| S7 | Ch 8 §8.6–8.8 | `FRONTIER_REFRAME.md` F3/F4; Part 0 §0.3 |
| S8–S10 | Ch 9 (walk) | `HIERARCHICAL_EXPLAINED.md` §8/§9/§9b; Part 0 §0.4 |
| S11 | Ch 9 (recursion) | `Recursive_inner_circuit_choice_explained.md`; `project_recursion_experiment` memory |
| S12 | Ch 10 §10.1, §10.4 | `NARRATIVE_FRAMING.md` §8.2–8.4; Part 0 §0.5 |
| S13 | Ch 10 §10.5–10.6 | Part 0 §0.7; `FIGURES_AND_METRICS.md` |
| Coda | Ch 11–12 | `MOTIVATION_AND_OBJECTIONS.md`; `ISOLATION_BENCHMARK.md` |

*Section source: 2026-06-04 narrative-execution session. Stages `Thesis_Outline.md` Part 0 + Ch 5–10.*
