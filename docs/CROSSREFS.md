# Cross-Reference Ledger

Single source of truth for thesis **labels** and the **forward/back references**
between chapters. Chapters are drafted out of order, so this ledger is maintained by
hand *as we draft* — the goal is that the final cross-reference pass is **verification
against this ledger**, not rediscovery of links from a cold read.

**Companion tooling (built + verified, Typst 0.14):**
- `thesis/drafts/_stubs.typ` — placeholder labels that keep the document compiling
  before target sections exist (and the running "labels we owe" list). Wire it into the
  master with `#import "drafts/_stubs.typ": setup` then `#show: setup` (a `show ref` rule
  does not propagate through `#include`). A `@ref` to a stub renders as red `[TBD: …]`;
  defining a real section whose label still has a stub errors ("label occurs multiple
  times"), forcing you to delete the stub.
- `pipeline/check_refs.py` — mechanical report (run: `python3 pipeline/check_refs.py
  --ledger docs/CROSSREFS.md`): DANGLING / STUB-COVERED / DUPLICATE / ORPHAN, plus a sync
  check of this registry against the actual `.typ` files. Exit 1 on dangling/duplicate.

## How to use

- **Reference a not-yet-written section:** use the real `@sec:x` label in prose; add a
  `🔲 stub` row to §1 below **and** a `#stub(...) <sec:x>` line in `_stubs.typ`.
- **Draft a section:** give its heading the `<sec:x>` label, flip its row to `✅`, and
  **delete its stub** from `_stubs.typ` (Typst's duplicate-label error enforces this).
- **Decide two passages should link:** add a row to §2 *immediately* — even if one or
  both ends aren't written yet. This is the part that makes the final pass tractable.
- **On finishing a chapter:** update §1 + §2, delete the chapter's now-defined stubs,
  (run `check_refs` once it exists), and read the chapter once against §2.

Legend: ✅ defined · 🔲 stub (owed) · ⚠️ needs attention.

---

## 1. Label registry

| Label | Status | Home | Purpose | Referenced from |
|---|---|---|---|---|
| `<chap:introduction>` | ✅ | Ch 1 | Introduction chapter | — |
| `<chap:background>` | 🔲 stub | Ch 2 | Background chapter | ch1 §1.1 ("formally define them throughout") |
| `<sec:motivation>` | ✅ | §1.1 | Sudoku → logistics motivation | ch4 §4.1 opener |
| `<sec:research-questions>` | ✅ | §1.2 | the three research questions | — |
| `<sub:rq1>` | ✅ | §1.2 | RQ1 — what decomposition buys | — |
| `<sub:rq2>` | ✅ | §1.2 | RQ2 — what stitching costs | — |
| `<sub:rq3>` | ✅ | §1.2 | RQ3 — the shape of the trade-offs | — |
| `<sec:contributions>` | ✅ | §1.3 | the four-point contribution list | — |
| `<sec:thesis-structure>` | ⚠️ | §1.4 | Structure of the Thesis — **header exists, body unwritten** (write last) | — |
| `<chap:methodology>` | ⚠️ | Ch 4 | **title/label mismatch**: titled "The Flat Baseline" → reconcile to `<chap:flat>`? | — |
| `<sec:proof-anatomy>` | ✅ | §4.1 | the constraint-group anatomy | ch4 §4.2 (×3) |
| `<sub:witness-def>` | ✅ | §4.1 | Defining the Witness | — |
| `<sub:constraints-def>` | ✅ | §4.1 | Defining the Constraints | — |
| `<sub:assembling>` | ✅ | §4.1 | Assembling the Circuit | — |
| `<fig:flat-pairwise>` | ✅ | §4.1 | the flat-pairwise pseudocode listing | ch4 §4.1 (×2) |
| `<sec:permcheck>` | ✅ | §4.2 | permutation-mechanism study | ch4 §4.1 (caption; closing) |
| `<sub:sort>` | ✅ | §4.2 | sort mechanism | — |
| `<sub:invperm>` | ✅ | §4.2 | inverse-permutation mechanism | — |
| `<sub:presence>` | ✅ | §4.2 | presence/RAM mechanism | — |
| `<sub:grand-product>` | ✅ | §4.2 | grand-product + Fiat–Shamir mechanism | — |
| `<sub:types-and-pair>` | ✅ | §4.2 | type rationale + the sort↔product pair | — |
| `<fig:flat-sort>` | ✅ | §4.2 | sort-check pseudocode listing | ch4 §4.2 (sort subsection) |
| `<fig:check-shuffle>` | ✅ | §4.2 | inside check_shuffle (hint + two passes) | ch4 §4.2 (sort subsection) |
| `<fig:flat-invperm>` | ✅ | §4.2 | inverse-permutation pseudocode listing | ch4 §4.2 (invperm subsection) |
| `<fig:flat-grandproduct>` | ✅ | §4.2 | grand-product pseudocode listing | ch4 §4.2 |
| `<fig:perm-mechanisms>` | ✅ | §4.2 | the five-mechanism comparison table | ch4 §4.2 (×2) |
| `<sec:zk>` | 🔲 stub | §2.1 | ZK proofs: completeness/soundness/ZK, knowledge soundness (container of `<sec:fiat-shamir>`) | ch5 (sound-first discipline); §5.7 (knowledge soundness) |
| `<sec:snarks>` | 🔲 stub | §2.2 | SNARKs / arithmetic circuits / **memory in circuits** / recursion para (see owed-content note ‡) | ch4 §4.1 (loop-unroll; ROM), §4.2 (memory taxonomy), §4.5 (witness inversion); ch5 §5.5 (no dynamic memory), §5.7 (in-circuit verification) |
| `<sec:metrics>` | 🔲 stub | §2.2 *(closing subsection of `<sec:snarks>`)* | ACIR-vs-gates, the metric set, data-obliviousness | ch4 §4.4 (metric set); Ch 6 |
| `<sec:primitives>` | 🔲 stub | §2.3 | Poseidon2 (RO/preimage/collision) · Merkle · **commitments (hiding/binding, Pedersen)** (see owed-content note ‡) | ch4 §4.3 (Merkle); ch5 §5.5.2, §5.6 (three senses; commitment hiding/binding); §5.8.1 (Pedersen/unconditional) |
| `<sec:tsp>` | 🔲 stub | §2.4 | TSP / Hamiltonicity · NP-hardness · **finder/checker asymmetry** · clustered solver | ch5 §5.1 `<sec:dualism>` (asymmetry = dualism pivot; solver-decomposition = the mirror) |
| `<sec:prob-formulation>` | 🔲 stub | §2.5 *(renumbered from §2.6 in the 2026-06-10 Ch 2 cut)* | TSP-ZKP problem statement; binding≠authenticity; threshold≠optimality | ch4 §4.1 opener, §4.3 (binding≠authenticity), §4.4 (feasibility not optimality) |
| `<sec:threat-model>` | 🔲 stub | §2.6 | adversary / guarantees / non-guarantees, defined once | ch4 §4.3 ("return to it with the threat model"); ch5 §5.8.2 `<sub:soundness-reductions>` |
| `<sec:fiat-shamir>` | 🔲 stub | §2.1 *(inside `<sec:zk>`)* | Fiat–Shamir / random-oracle challenge (+ Schwartz–Zippel) | ch4 §4.2 (grand product); ch5 §5.5.2 `<sub:challenge-binding>` |
| `<sec:representation>` | 🔲 stub | §4.3 | matrix representation (flat-full vs Merkle) | ch4 §4.1 (×2), §4.2 (×3: gun callback; surface-war first step; committed matrix) |
| `<sec:witness-inversion>` | 🔲 stub | §4.5 | the witness-time inversion | ch4 §4.1 detail 2, §4.2 (the pair; perm-table caption) |
| `<chap:hierarchical>` | 🔲 stub | Ch 5 | Hierarchical and Recursive Constructions | ch4 §4.2 (invperm loan comes due; grand-product spine) |

**‡ Owed content for stubbed sections (so the inbound refs make sense):**
- `<sec:snarks>` (§2.2) must cover, once: **(a)** an arithmetic circuit is a *fixed,
  finite, loop-free, branch-free* graph fixed before the witness (→ why loops unroll;
  why the `≠` inverse trick needs no branching); **(b)** **offline memory checking**
  (cite Blum–Evans–Gemmell–Kannan–Naor 1991/94; circuit synonym **ROM lookup**, ACIR
  `MEM_INIT`/`MEM_OP`): array as (address,value) table, prover's sorted access-log hint,
  sorted/permutation/consistency checks, cost linear in dynamic reads. Hedge: Barretenberg
  may lower to a lookup-argument (Plookup/logUp) variant — same cost shape. This is the
  **billed ~1.5 pp** the drafted Ch 4/5 lean on hardest (§4.2 memory taxonomy, §4.5
  inversion, §5.5 "no dynamic memory"). Split a dedicated `<sec:dynamic-memory>` if §2.2
  grows. **(c)** one paragraph: a circuit can **verify a proof in-circuit** (recursive
  composition + its soundness) — enough for §5.7's `verify_proof` gadget / `vk`; systems
  (Halo/Nova/folding) are Ch 3's, not here. Closing `<sec:metrics>`: ACIR-opcodes-vs-gates,
  the metric set, **data-obliviousness** (one-instance-per-size). *Pipeline mechanics stay
  in Ch 4 §4.4 — do not duplicate.*
- `<sec:primitives>` (§2.3) must cover, once: **(a)** Poseidon2 with its **three security
  senses named** — random-oracle behaviour, **preimage resistance**, **collision
  resistance** — because §5.5.2 and §5.6 invoke each by name (RO → unforeseeable challenge;
  preimage → can't invert X to a tour; collision → can't find a second tour to the same c /
  can't open a commitment two ways); **(b)** Merkle commitment (binding via collision
  resistance, DEPTH openings, the soundness-critical leaf-index check); **(c)** commitments
  in general: **hiding** vs **binding**, **computational** vs **unconditional**, with
  **Pedersen** (unconditional hiding / DLOG binding) as the alternative §5.8.1 names. Without
  (c), §5.6 and the privacy ladder (computational vs structural hiding) have nothing to cite.
- `<sec:fiat-shamir>` (§2.1) must state **Schwartz–Zippel** *and* Fiat–Shamir at the
  **order-of-dependence** level §5.5.2 uses: the tour is fixed first, the challenge derived
  from it second (X = H(c)), so a cheat cannot pick the multiset *after* seeing the point.
- `<sec:tsp>` (§2.4) must plant the **finder/checker asymmetry** and the clustered-solver
  decomposition (N! → ~K·(N/K)!·K!) **neutrally** — §5.1 weaponizes both (the asymmetry is
  the dualism's pivot; the solver's region split is the mirror ZK inverts). No hint here that
  ZK refuses decomposition; that is §5.1's reveal.
- `<sec:witness-inversion>` (§4.5) must **backreference §4.1 detail 2**: sort's
  `check_shuffle` does ≈2N secret-indexed reads (`cycle[π(i)]`, π a witness), so the
  solver build+sorts that access log at solve time ⇒ sort is slower to witness than
  grand-product *despite fewer constraints*.

---

## 2. Intended cross-references (wire when both ends exist)

Each row is a link we have *decided* on. "Wired?" tracks whether the actual `@ref`
exists yet in the `.typ`. `fwd` = forward ref, `back` = backward ref.

| Anchor / concept | Source (introduces) | Should be referenced from | Wired? | Note |
|---|---|---|---|---|
| circuit is fixed / loop-free | §2.2 `<sec:snarks>` | §4.1 (loop unrolled) | ✅ fwd | "(see @sec:snarks)" |
| dynamic-read cost / offline memory checking | §2.2 `<sec:snarks>` | §4.1 detail 2 | ✅ fwd | "explained in @sec:snarks" |
| witness-time inversion mechanism | §4.1 detail 2 | §4.5 `<sec:witness-inversion>` | 🔲 back | §4.5 owes the backref (see ‡) |
| `i·N+j` flat index → Merkle leaf index | §4.1 (matrix indexing) | §4.3 `<sec:representation>` | ✅ fwd | "the same address … will reappear" |
| pairwise quadratic ⇒ cheaper perm checks | §4.1 (perm mechanism) | §4.2 `<sec:permcheck>` | ✅ fwd | "a stronger one will later enforce…"; §4.2 now delivers (sort subsection) |
| N² public inputs are a bottleneck | §4.1 (matrix as public input) | §4.3 `<sec:representation>` | 🔲 fwd | §4.1 gestures ("come back to bite us"); §4.2 closing sentence re-points; make explicit when §4.3 lands |
| sort↔product is the sharpest pair (witness inversion) | §4.2 `<sub:types-and-pair>` | §4.5 `<sec:witness-inversion>` | ✅ fwd | §4.2 sets up the twist; §4.5 owes the measured result + the §4.1-detail-2 backref |
| grand product's O(1) surface pays off only under decomposition (the loaded gun) | §4.2 `<sub:grand-product>` | §4.3 `<sec:representation>` + Ch 5 walk | ✅ fwd | §4.2 "we have only loaded the gun"; §4.3 / §5.7 (`plain-product`) fire it |
| Fiat–Shamir / Schwartz–Zippel (random-oracle challenge) | §2.1 `<sec:fiat-shamir>` | §4.2 `<sub:grand-product>` | ✅ fwd | "we treat properly in @sec:fiat-shamir" |
| dynamic vs static array reads (ROM/RAM cost) | §2.2 `<sec:snarks>` + §4.1 detail 2 | §4.2 (sort, invperm, presence) | ✅ back | §4.2 leans on §4.1's dynamic-read lesson for all three exact mechanisms |
| FS order-of-dependence (tour fixes challenge) | §2.1 `<sec:fiat-shamir>` | §5.5.2 `<sub:challenge-binding>` | 🔲 fwd | §5.5.2 rebuilds the chain across K proofs; assumes the flat FS picture |
| Poseidon three senses (RO/preimage/collision) | §2.3 `<sec:primitives>` | §5.5.2 `<sub:challenge-binding>`, §5.6 `<sec:committed>` | 🔲 fwd | §5.5.2/§5.6 name each sense; background defines them once |
| commitment hiding/binding; computational vs unconditional; Pedersen | §2.3 `<sec:primitives>` | §5.6 `<sec:committed>`, §5.8.1 `<sub:privacy-ladder>` | 🔲 fwd | the privacy "cure" + ladder rung; Pedersen named in §5.6/§5.8.1 |
| Merkle binding + leaf-index check | §2.3 `<sec:primitives>` | §4.3 `<sec:representation>` | 🔲 fwd | §4.3 calls the leaf-index check "the most important line in the section" |
| in-circuit verification / recursive composition | §2.2 `<sec:snarks>` | §5.7 `<sec:recursion>`, `<sub:outer>` | 🔲 fwd | `verify_proof` gadget + `vk`; soundness rests on recursion KS |
| knowledge soundness | §2.1 `<sec:zk>` | §5.7 (recursion) | 🔲 fwd | composing knowledge-sound proofs |
| metric set / data-oblivious | §2.2 `<sec:metrics>` | §4.4 `<sec:tooling>`, Ch 6 | 🔲 fwd | "the metrics … defined in @sec:metrics"; one-instance-per-size justified by data-obliviousness |
| finder/checker asymmetry (dualism seed) | §2.4 `<sec:tsp>` | §5.1 `<sec:dualism>` | 🔲 fwd | the asymmetry IS the dualism's pivot |
| clustered-solver decomposition (the mirror) | §2.4 `<sec:tsp>` | §5.1 `<sec:dualism>` | 🔲 fwd | ZK inverts the solver's region split — §5.1 needs the neutral solver picture |
| binding ≠ authenticity | §2.5 `<sec:prob-formulation>` | §4.3 `<sec:representation>` | ✅ fwd | §4.3 "we develop it properly in @sec:prob-formulation" |
| threshold ≠ optimality (feasibility) | §2.5 `<sec:prob-formulation>` | §4.4 `<sec:tooling>` | ✅ fwd | §4.4 "proving feasibility … not optimality … a distinction we return to" |
| threat-model vocabulary (trust base) | §2.6 `<sec:threat-model>` | §5.8.2 `<sub:soundness-reductions>` | 🔲 fwd | §5.8.2 reads each variant's trust base against this |

---

## 3. Open housekeeping (non-label)

- `<chap:methodology>` vs title "The Flat Baseline" — reconcile the chapter label.
- The 3-group prose scheme (Group 1 Permutation / 2 Edge Cost / 3 Threshold; range
  folded into the pairwise mechanism) diverges from the Noir code's `CONSTRAINT GROUP
  1..4` — reconcile the appendix/code mapping when the appendix is drafted.
