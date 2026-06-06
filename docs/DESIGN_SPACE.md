# Design Space — Roads Not Taken (alternatives ledger)

*The honest audit of the design space: for each constraint / choice in the pipeline, the
**full** alternative space (not only the easy-to-beat ones), a verdict, the strongest threat,
and a one-line defense. Purpose: justify the choices made, defend against strong alternatives
at the viva, and surface anything smart we missed. Built 2026-06-04; **work on individual rows
when the relevant chapter is drafted.** Companion to `DESIGN.md` (records the choices), this
doc records the *unchosen*. Cross-linked from `MOTIVATION_AND_OBJECTIONS.md` (defense register).*

## How to read each row
**Choice** (what we did) · **Alternatives** (the space) · **Verdict** (defensible? where's the
danger?) · **Threat** (Low/Med/Strong — how likely to come up + how damaging) · **Defense line**
(the sentence that holds) · **Pursue?** (whether it's worth doing, future).

---

## Triage — where the danger is

- **Bulletproof** (one-sentence defense): cycle-vs-path, solver choice, feasibility-as-an-NP-statement, TSP-as-instrument, ZK-vs-MPC/TEE/FHE.
- **Defensible but rehearse the threat**: proof system (vs STARK/Plonky2 recursion); matrix commitment (vs committed-table lookups); recursion mechanism (vs folding/accumulation).
- **Genuine "did we aim right?" challenges**: feasibility vs **optimality/approximation**; flat K-way slicing vs **tree/recursive** decomposition.

**The four threats to rehearse (priority order)** — full detail in their rows below:
1. *"STARK/Plonky2 makes recursion cheap → 704k×K is a backend artifact."* (row 1.1)
2. *"Committed-table lookups (cq/Lasso) beat per-edge Merkle."* (row 1.4)
3. *"Why not fold/accumulate from the start?"* (row 3.3)
4. *"You proved feasibility, not optimality."* (row 2.2)

**Smart things possibly missed (constructive)** — raise these *ourselves* to show command of the space:
committed-table lookups (1.4) · tree/log-depth aggregation (3.1) · lookup-optimized hashes (1.3) ·
approximation-ratio proofs (2.2) · Waksman/Beneš permutation networks (2.3).

---

## Layer 1 — Proof system & primitives

### 1.1 Proof system — **chose UltraHonk (Noir/Barretenberg)**

| Alternative | Buys | Why not / threat |
|---|---|---|
| Groth16 | smallest proofs, cheap verify | per-circuit trusted setup, no universal SRS, no native recursion → clearly worse for many sizes + recursion. **Low.** |
| Halo2 (KZG/IPA) | mature, lookups, **atomic accumulation** | rejected for "API complexity before needing recursion" — but recursion *was* needed; Halo2 accumulation is arguably more natural than full in-circuit Honk verification. **Med.** |
| **Plonky2/3, STARKs (FRI)** | **recursion designed-in**; small recursive verifier | **the most dangerous alternative** — "recursion ≈704k gates" is UltraHonk-specific; a FRI backend can make it far cheaper, *moving the frontier*. **Strong.** |
| Nova / folding | aggregation w/o full in-circuit verification | named future work; "why not from day one?" **Med.** |
| Bulletproofs | no setup | linear verifier, slow → worse. **Low.** |

- **Verdict.** Defensible for a thesis (timeline, Noir maturity, lookups, no per-circuit setup, one clean backend for a controlled comparison) — but the *"recursion is expensive"* conclusion is partly a backend artifact and must be scoped as such (§11.3.1).
- **Defense line.** *The binding tax is a structural property of decomposition, present in any backend; its **magnitude** — and whether recursion or folding wins — is backend-dependent. UltraHonk is one instantiation; a STARK/folding backend shifts the corner, it does not erase the triangle.*
- **Pursue?** No (re-implementation). Cite Plonky2/STARK recursion costs from literature for contrast.

### 1.2 DSL — **chose Noir**
Alternatives: **Circom** (most popular, huge ecosystem, but Groth16/low-level), **gnark** (Go, fast, good recursion), **arkworks** (rejected — too low-level), Cairo/Leo. **Verdict:** defensible (high-level, UltraHonk lookups, timeline). **Threat: Low** — only "Noir is young/less battle-tested than Circom." **Defense line:** high-level DSL + lookup backend + native recursion in one toolchain, right for a single-developer thesis.

### 1.3 Hash — **chose Poseidon2**
Alternatives: Poseidon(1), Rescue-Prime (more gates), MiMC (more rounds), Pedersen-hash (EC), and **lookup-based hashes (Monolith, Reinforced Concrete)** that exploit Plookup and can be *cheaper than Poseidon2 in a lookup backend*. **Verdict:** defensible — Poseidon2 is the audited Noir default and the measured ~87 gates/call shows it already amortizes well under Plookup; switching hashes is risk for uncertain gain. **Threat: Low (constructive).** **Smart miss:** we have lookups but didn't lookup-optimize the hash — acknowledge in one sentence. **Pursue?** No.

### 1.4 Matrix commitment — **chose Merkle (Poseidon2), per-edge proofs**

| Alternative | Buys | Assessment |
|---|---|---|
| Verkle / KZG vector commitment | constant-size openings | pairing/KZG **in-circuit** (expensive) + trusted setup → rejected correctly (§5.6). |
| **Committed-table lookup (cq, Caulk, Baloo, Lasso)** | each used edge cost ∈ *committed* matrix via a lookup; replaces N Merkle proofs (N·DEPTH hashes) with N lookups | **strongest "smart thing possibly missed"** — modern private-table lookups, likely **substantially cheaper than per-edge Merkle**. |
| Plain Plookup (public table) | cheapest | table = matrix would be public → only valid in flat-full. |

- **Verdict.** Merkle is simple, transparent, no setup — fine for a thesis; but **probably not the asymptotically cheapest private-matrix binding.**
- **Defense line.** *Committed-table lookups (cq/Lasso) are the modern efficiency frontier for this step; we chose Merkle for transparency, no setup, and tooling maturity in Noir/bb — naming the cheaper alternative we did not pursue.*
- **Pursue?** **Maybe (future / a strong "limitations & future work" entry).** Threat **Strong** if unraised; raise it ourselves.

---

## Layer 2 — Statement & encoding

### 2.1 Hamiltonian cycle vs path — **chose cycle**
Standard TSP (n edges, closing edge implicit). Path = n−1 edges, simpler but non-standard. **Threat: Low. Bulletproof.**

### 2.2 Threshold (cost ≤ T) vs optimality — **chose feasibility** *(the big conceptual challenge)*
- **Optimality** ("this is the *minimum*") is **co-NP** — needs a verifiable **optimality certificate** in ZK (LP/Held–Karp lower bound, branch-and-bound certificate). Much harder, a different thesis.
- **Approximation** ("within ratio ρ of optimal") — prove cost ≤ ρ × (a certified lower bound). A *middle ground*: more valuable than feasibility, far easier than optimality.
- **Verdict.** Feasibility is the right *tractable* choice and the standard ZK-for-NP formulation. **Threat: Strong (conceptual)** — "you proved the easy direction."
- **Defense line.** *Feasibility is the NP statement (prove knowledge of a witness); optimality is co-NP and needs a certificate — a separate research line. Approximation-ratio proofs are the smart near-term bridge, which we name as future work.*
- **Pursue?** Approximation: **yes, as future work / a thesis-strengthening paragraph.** Optimality: out of scope.

### 2.3 Permutation check (GROUP 2) — **5 explored** (pairwise / sort / invperm / presence / grand-product)
Un-tried classics: **Waksman/Beneš routing networks** (O(N log N), deterministic, FS-free — a real alternative to the grand product) and **sorting networks** (data-oblivious). **Verdict:** this is a **strength** (unusual breadth); the grand product *is* the canonical (PLONK) permutation argument. **Threat: Low.** **Smart miss (minor):** Waksman/Beneš as a deterministic FS-free fingerprint — one sentence. **Pursue?** No (mention only).

### 2.4 Public vs private matrix — **chose both regimes** (flat-full public; flat-Merkle + all hierarchical committed)
The key clarification (binding ≠ authenticity): the proof shows consistency with *a committed matrix*, never that it is the *real* one (garbage-in-garbage-out). Authenticity needs an **external anchor** (signature/oracle/timestamp/dispute-reveal, §4.3) or an **in-circuit provenance proof** (prove in ZK the matrix carries a trusted authority's signature — private *and* authenticated; **not implemented**, future work §12.2). **Verdict:** solid; the orthogonality (matrix-privacy ⟂ partition-privacy) must be stated. **Threat: Low–Med** ("private only if you trust the commitment" — answered by the anchor/provenance distinction). **Pursue?** In-circuit provenance: future work.

---

## Layer 3 — Decomposition & recursion

### 3.1 Decomposition scheme — **chose flat K-way slicing of the found cycle**

| Alternative | Buys | Assessment |
|---|---|---|
| **Recursive / tree bisection** | **log-depth** aggregation (balanced binary tree of proofs) vs one outer verifying K inners (star) | for recursion, could rebalance the 704k×K cost + memory — **smart alternative.** |
| **Spatial / geometric clustering** (classical hierarchical-TSP: cluster → solve → stitch) | matches the optimizer's decomposition | we do *post-hoc cycle slicing*, not *cluster-then-solve*; a sharp examiner notes we decompose the *cycle*, not the *search*. |
| Edge-based / overlapping windows | — | minor. |

- **Verdict.** Flat node-partition is simplest and makes the binding tax cleanest to exhibit — defensible. **Threat: Med.**
- **Defense line.** *We decompose the **proof**, not the search — which is precisely why the dualism bites (there is no search to prune). Tree-structured PCD is the standard scalable aggregation and the natural log-depth extension we name but did not build.*
- **Pursue?** Tree/log-depth recursion: **future work.**

### 3.2 Binding mechanism — **chose external cross-check / commitment / in-circuit / (folding future)**
This *is* the contribution (the binding tax), well-covered. Named neighbors to cite so we're not blindsided: **SnarkPack** (IPA proof aggregation), **PCD/IVC**, batch verification. **Threat: Low** (it's our home turf). **Pursue?** N/A.

### 3.3 Recursion mechanism — **chose full in-circuit UltraHonk verification**
Alternatives: **folding (Nova/ProtoStar/HyperNova)**, **accumulation (Halo/atomic/ProtoStar)**, **cycle-of-curves**. We chose the **most expensive** form (full in-circuit verification) — honest and on-message (the C-corner; folding is the empty corner). **Verdict:** well-handled; make explicit "recursion here = *eager full verification*, the deliberately-expensive baseline folding would beat." **Threat: Med** ("why not the cheap recursion?"). **Defense line:** *folding is the named empty corner of the frontier (the thesis is the **map**); building it is a different backend and would break the single-backend controlled comparison.* **Pursue?** Folding: **the headline future work.**

### 3.4 Fiat–Shamir — **chose in-circuit Poseidon2 hash-chain**
Alternative: external/interactive challenge (loses non-interactivity). Soundness subtleties (FS-in-ROM; delicate recursive FS composition) already acknowledged. **Threat: Low.** **Defense line:** in-circuit FS keeps the protocol non-interactive and publicly verifiable; soundness = FS-in-ROM (cited, not reproved).

---

## Layer 4 — Methodology

### 4.1 Solver — **chose nearest-neighbour + 2-opt**
Correctly justified: proving cost is **witness-quality-independent** (we need a *valid* cycle, not an optimal one). Alternatives (LKH, Concorde, Christofides, OR-Tools) matter only if we ever prove approximation/optimality (2.2). **Threat: Low. Bulletproof for feasibility.**

### 4.2 The instrument — **chose TSP**
Alternatives as carrier: SAT, k-clique, graph colouring, scheduling, knapsack. TSP is well-chosen — its constraints are **non-local** (the heart of the dualism) and it has a real routing-privacy application. **Threat: Low** (objection O1 "TSP is the instrument not the product" is the defense). **Pursue?** "Does the dualism generalize to other non-local problems?" — future work.

### 4.3 Trust model — **chose ZK** (vs MPC / TEE / FHE)
For "prove I know a good route over private data," ZK is the right niche (single prover, non-interactive, publicly verifiable, no hardware trust). MPC needs multiple parties; TEE needs hardware trust; FHE computes-on-encrypted (different goal). **Threat: Low** — one related-work paragraph (§3.3) settles it.

---

## Maintenance
- Drill a row when its chapter is drafted; promote "Pursue? future work" rows into `Thesis_Outline.md` §12.2.
- New viva-style objections → add to `MOTIVATION_AND_OBJECTIONS.md` and back-link the row here.
- If a row's threat is neutralized with numbers (e.g., cite a Plonky2 recursion gate count), record the figure inline so the defense is evidence-backed, not assertion.

*Sources: `DESIGN.md` (choices), 2026-06-04 design-space audit; ZK literature (Halo2, Plonky2/3,
Nova/ProtoStar/HyperNova, cq/Caulk/Baloo/Lasso, Monolith/Reinforced-Concrete, SnarkPack, Waksman/Beneš).*
