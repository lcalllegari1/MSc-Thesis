# Narrative Framing — The Perfect-Hiding Dilemma and the Hierarchical Escape

> **Chapter remap (2026-06-10).** Chapter numbers in this doc are the old 12-chapter
> scheme. Translate on read: old Ch 8 (framework) → new §5.1–5.4 · old Ch 9 (the walk) →
> new §5.5–5.10 · old Ch 10 (results) → new Ch 6 · old Ch 7 (flat evaluation) → new
> §4.5/§6.2 · old Ch 4 (problem formulation) → new §2.5–2.6 (see `Thesis_Outline.md`).
> Also stale: any "projected, not measured" parallelism caveat — the isolation sweeps have
> landed (~6.5× `plain-product`, ~4.7× `plain-sort` at N=3000 K=8; `ISOLATION_BENCHMARK.md`).
> **Also stale (framing, 2026-06-22):** the **frontier** is now the pick-two of **cheap / parallel
> / structurally private** — verification *rides with* privacy, not a separate axis — so the
> "{P, V, C} at fixed privacy" tables here (§9.3.x) are superseded by `FRONTIER_REFRAME.md` F4 and
> Ch 5 `sub:pick-two`.

*Reference note locking in the "flat vs recursion, then hierarchical as the
escape" framing for the framework + walk chapters. Captured 2026-05-31. This is a narrative /
positioning note, not new results — every claim traces to findings already in
`FRONTIER_REFRAME.md`, `HIERARCHICAL_EXPLAINED.md`, and the recursion
micro-benchmarks. Use it as the starting point when drafting the variant chapters.*

> **UPDATE (2026-06-03) — the open choices are now resolved.** §6 below is
> superseded by **§9 (the locked spine + full connective map)**, the product of
> a working session that settled: (i) the spine = **stitching tax**, with the
> perfect-hiding dilemma as its **cold-open** and the privacy ladder demoted to a
> §9.6 section; (ii) recursion order = **result-first, build-last**; (iii) the
> recursion sub-arc presentation = **plain-product first (the shipped construction), plain-sort second
> (the fairness control)**; (iv) the verification→ZK separation enters as the
> **statement–witness boundary** (a restatement of "what is bound", not a fifth
> frame); plus the per-variant motivations, the two connective hinges, the
> prover/verifier reveal, and the non-circularity defense. §9 is the single
> drafting reference for Ch 8-10; §1-§8 remain as the supporting material it draws on.

---

## 1. The hook: perfect hiding, two ways (flat vs recursion)

Open on the two constructions that achieve **structural / perfect hiding** — public
surface `{root, T}`, partition carries no information:

| | parallel + low per-prover mem | O(1) verifier | low total cost (no agg. tax) |
|---|:--:|:--:|:--:|
| **flat** (monolithic) | ✗ | ✓ | ✓ (~782k gates, N=500) |
| **recursion** (decompose + verify in-circuit) | ✓ | ✓ | ✗ (~704k*K agg. tax; 2.2M @K=2, 3.8M @K=4) |

**Headline of the opening comparison:** *at perfect hiding you cannot have both low
total cost and parallelism — flat gives you cost, recursion gives you parallelism,
neither gives you both.* It is a clean, true result because privacy is held fixed
(both publish only `{root, T}`), so the comparison isolates the cost/parallelism
axis. This is the equal-privacy slice at the **structural-hiding** level.

---

## 2. The escape: relax privacy one notch -> the hierarchical family

Ask: the decomposition is what buys parallelism; the *in-circuit* binding is what
costs 704k*K. **What if we keep the decomposition but bind EXTERNALLY (cheap)?**
That is exactly the hierarchical family (plain-sort / plain-product / committed-sort / committed-product):
K independent segment proofs + a glue proof, bound by verifier-side cross-checks
instead of an in-circuit verifier.

The pick-two triangle, now with the third corner:

| | parallel + low mem | O(1) verifier | low total cost |
|---|:--:|:--:|:--:|
| flat | ✗ | ✓ | ✓ |
| recursion | ✓ | ✓ | ✗ |
| **hierarchical (plain-sort/plain-product/committed-*)** | ✓ | ✗ | ✓ |
| folding (future) | ✓ | ✓ | ✓ |

The hierarchical family combines **flat's low total cost + recursion's parallelism**.
That is the "best of both worlds" — but ONLY on those two axes, and it is bought
with two prices, which must be named every time the claim is made.

---

## 3. The honest correction to "best of both worlds"

It is a **third corner of a triangle, not a dominating reconciliation.** The two
prices:

1. **O(K) verifier** — K+1 proofs, so `proof_bytes` and `verify_s` grow ~K (the
   stitching-tax symptom that only recursion/folding remove).
2. **Privacy relaxation** — drops from structural hiding to: disclosed (plain-sort),
   computational-with-confirmation-oracle (plain-product), or computational + reveals-K
   (committed-*). The committed variants are precisely the construction that makes
   this relaxation as small as possible (one assumption below structural).

**Bulletproof phrasing (use this, not "best of both worlds"):**

> At perfect hiding, flat and recursion force a choice between total cost and
> parallelism. The hierarchical family escapes that dilemma — it combines flat's
> cost with recursion's parallelism — at a precisely characterized price: an O(K)
> verifier and a one-notch privacy relaxation, which the committed variants then
> minimize.

---

## 4. The integrated spine (entry point folds into the existing machine)

flat-vs-recursion-first is a different *entry point* into the same dualism /
stitching-tax / privacy-ladder story, and it motivates each later step:

1. **Perfect hiding, two ways** — flat (monolithic) vs recursion (decompose + bind
   *in-circuit*). The decomposition buys parallelism; the in-circuit binding costs
   704k*K.
2. **The question** — keep the decomposition, bind **externally** (cheap)? -> plain-sort / plain-product.
3. **The catch = the stitching tax** — external binding leaks the partition (+ O(K)
   verifier + bookkeeping). This is the dualism made concrete: decomposition gives
   no ZK speedup, only redistribution; the binding removed from the circuit
   reappears as a leak.
4. **The fix** — committed-sort/plain-product close the leak (computational hiding, reveals only
   K), recovering near-flat privacy *without* recursion's tax.
5. **The frontier** — folding as the missing all-three corner (future work).

**Dependency to handle in the ordering:** recursion is *built from* the hierarchical
segments (it recurses on the plain-product sub-circuits), so the decomposition concept must be
introduced before/with recursion. Clean fix: present decomposition up front as
shared, and frame the distinction as **where the binding lives** —
in-circuit (recursion, expensive) vs external (hierarchical, cheap-but-leaky).

---

## 5. Honesty caveats to carry while selling it

- **K× parallelism is now MEASURED** (isolation sweeps `results/hier_*_iso.csv`: ~6.5×
  `plain-product`, ~4.7× `plain-sort` at N=3000 K=8). The remaining caveat to carry: the
  per-proof times are solo runs; the K-machine wall-clock is their composition
  (max segment + glue), a deployment-model assumption to state, not a missing number.
- **Total work is conserved (the dualism).** "Best of both" must NOT imply
  hierarchical beats flat on total gates — it does not (~770-806k vs flat's ~782k).
  The win is *parallelizability of the same work*, not less work.
- **"Perfect hiding" of flat/recursion is structural**, not information-theoretic ZK
  (the SNARK's ZK is identical across all variants and is not a discriminator). It
  means the public surface carries no partition info.

---

## 6. The open narrative choice (RESOLVED 2026-06-03 — see §9)

> **Resolved.** The choice below is settled in **§9.1**: the spine is the **binding
> tax** (≈ option (B)'s systematic backbone, promoted to a *named contribution*), and
> option (A)'s perfect-hiding dilemma becomes its **cold-open scene** — not a separate
> spine. The two were never coequal: (A) is the opening scene of (B), and the privacy
> ladder is a §9.6 section, not a third spine. Read §9 for the full reasoning and the
> connective tissue. The original text is kept below for the record.

Two viable spines for Chapters 8-10:

- **(A) Perfect-hiding dilemma first** (this note): flat vs recursion -> escape via
  decomposition -> stitching tax -> committed cure -> folding. Vivid hook; sets up a
  true cost/parallelism dilemma; recommended as the *opening*.
- **(B) Privacy progression first** (current `FRONTIER_REFRAME.md` Part 2): B -> plain-sort ->
  plain-product -> committed -> recursion/flat, each step removing one stitching-tax symptom.
  Monotone; matches the documented "stitching tax as second structural result."

They are compatible — (A) is an entry point, (B) is the systematic backbone.
**Recommendation:** open with (A) for the hook, then settle into (B)'s progression
for the systematic treatment. Reconcile the two in `FRONTIER_REFRAME.md` when the
chapter structure is fixed.

---

## 7. The recursion sub-arc: two inner circuits and the Fiat–Shamir floor

The headline comparison in §1 is *recursion vs flat_merkle_sort* — both perfect-hiding,
both publish `{root, T}`. But the recursion we benchmark uses the **plain-product segment** as its
inner, which swaps flat's deterministic sort-partition for a grand-product + Fiat–Shamir
partition check. So "recursion vs flat" silently changes **two** things at once:
(i) monolithic → decompose-and-verify-in-circuit, and (ii) **deterministic → probabilistic
partition argument**. Insert **recursive-sort** (plain-sort segments inner; the sort-partition is
reconstructed in the *outer*) as an intermediate step to separate them.

### 7.1 The correction: this is a *soundness* step, not a *hiding* step

It is tempting to call the plain-product-inner's grand product a hiding cost. It is not. **Inside
recursion the partition is perfectly hidden either way** — plain-sort's `sorted_nodes[M]` and plain-product's
`P_i`/chain anchors both become *witness of the outer circuit*, so the final verifier sees
neither (`Recursive_inner_circuit_choice_explained.md`, §"Privacy is *not* the motivation").
Hiding is identical across flat_merkle_sort, recursive-sort, and recursive-product — it is the
SNARK's ZK, common to all and therefore not a discriminator (cf. §5, third bullet). What
differs is whether the partition **check** is *exact* (sort) or *probabilistic*
(grand product + Fiat–Shamir, error ≤ N/|F| ≈ 2⁻²⁵⁴). State the trade on the soundness
axis or it will not survive a careful reading.

### 7.2 The three-step arc

| step | construction | partition check | inner public surface | what the step isolates |
|---|---|---|---|---|
| 1 | **flat_merkle_sort** | deterministic sort | — (monolithic) | the perfect-hiding baseline |
| 2 | **recursive-sort** | deterministic sort (in the outer) | `O(M) = M+4` / segment | the **aggregation cost** at a *matched* (deterministic) partition check; surfaces the `O(M)` absorption penalty |
| 3 | **recursive-product** | grand product + Fiat–Shamir | `O(1) = 9` fields | the **inner-circuit win** (outer stays flat, ~1.47M at K=2, *M-independent*) bought with a probabilistic partition argument |

Reading: **1 → 2** answers *"what does recursion cost?"* — the K in-circuit verifiers at
~704k gates each (≈1.47M at K=2, ≈3.0M at K=4) — while holding the partition check
deterministic like flat, so nothing but the aggregation has changed. **2 → 3** answers
*"what does the plain-product inner buy?"* — its `O(1)` public surface keeps the outer
segment-size-independent (the measured "outer flat across N=48→480"), and the price is
moving the partition argument from exact to Schwartz–Zippel + Fiat–Shamir. Cost is
otherwise ~identical either way (the K verifications dominate; sort-vs-grand-product in the
glue is noise against ~704k×K). The repo produces both rows on the **same instance** via
`tests/recursion_micro/{run_recursion_a.py, compare_inner.py}` (both now keyed to the one
`(N, seed)` cache, so the head-to-head is ceteris paribus).

### 7.3 The Fiat–Shamir floor — recursion's unavoidable cost

Every non-interactive proof here is a public-coin interactive argument compiled with the
**Fiat–Shamir transform**: the verifier's random challenges are replaced by hashes of the
transcript, sound in the **Random Oracle Model**. Recursion verifies an inner proof *inside
a circuit*, so the outer must **recompute those Fiat–Shamir challenges in-circuit** (hash the
inner transcript) and run the polynomial-commitment opening checks. That transcript-hashing
+ opening arithmetic is the **bulk of the ~704k-gate inner verifier**. Three consequences,
which must be stated whenever recursion's cost is discussed:

1. **FS/ROM is not unique to plain-product, nor introduced by recursion** — flat_merkle_sort's single
   proof is *already* Fiat–Shamir-in-ROM. What recursion adds is a **second, in-circuit
   layer** of FS hashing (the outer hashing the inner transcript).
2. **That layer is unavoidable for *any* recursive design** — plain-sort-inner or plain-product-inner, sort or
   grand product. The ~704k×K gates are the price of recursion *as a technique*, independent
   of the partition-check choice. So recursive-sort is **not "Fiat–Shamir-free"**: it removes
   the grand-product FS *at the partition level* but keeps the structural recursion FS. The
   precise claim is "**deterministic at the partition check**," never "unconditionally sound
   end-to-end."
3. **The FS floor *is* recursion's stitching tax.** The gates that collapse the public surface
   to `{root, T}` are exactly the in-circuit FS-verifier. The dualism, all the way down:
   binding removed from the public surface reappears as in-circuit transcript-hashing cost.

**Honest caveat to carry:** recursive composition of Fiat–Shamir in the ROM is delicate (the
random oracle is instantiated by a concrete in-circuit hash). Treat recursion soundness as
*FS-in-ROM + the backend's recursion knowledge-soundness* (matches `Thesis_Outline.md`
§9.8.7), not as an unconditional guarantee.

---

## 8. Order of introduction & how to compare

### 8.1 Presentation order (conceptual)

The spine is still §6's recommendation — open with the perfect-hiding dilemma (A), settle
into the privacy progression (B) — with the recursion sub-arc (§7) slotted into the
perfect-hiding treatment:

1. **flat_merkle_sort** — monolithic; deterministic sort permutation check; public `{root, T}`.
2. **Decomposition** (introduced once, shared) — K segments + glue; the organising question
   is *where the binding lives*: in-circuit (recursion) vs external (hierarchical).
3. **Recursion (in-circuit binding)** — the perfect-hiding endpoint:
   - **3a. recursive-sort** — deterministic sort-partition in the outer; matched to flat's
     soundness flavor; isolates the **aggregation cost**; surfaces the `O(M)` penalty and the
     **Fiat–Shamir floor** (§7.3).
   - **3b. recursive-product** — grand-product inner; the `O(1)`-surface win, paid for with a
     probabilistic partition argument (§7.2).
4. **Hierarchical (external binding)** — the cheaper-but-leaky escape and its cure:
   **A** (partition disclosed) → **plain-product** (multiset hidden, `P_i` an unblinded oracle) →
   **committed-sort / committed-product** (blinded `C_i`; leak closed, computational hiding, reveals K).
   *(Variant B — sub-matrix public — sits at the disclosing end as the gate-saver.)*
5. **Folding** — the missing all-three corner (future work).

### 8.2 Comparison map — which pair isolates which axis

Every claim is a *controlled* comparison: change exactly one thing.

| compare | holds fixed | isolates |
|---|---|---|
| flat_merkle_sort ↔ **recursion** | perfect hiding `{root,T}` | **cost vs parallelism** at perfect hiding (the §1 dilemma) |
| flat_merkle_sort ↔ **recursive-sort** | perfect hiding **+ deterministic partition** | the **aggregation cost** alone (no soundness confound) |
| **recursive-sort ↔ recursive-product** | recursion + perfect hiding | inner-circuit choice: `O(M)`→`O(1)` surface **+** deterministic→probabilistic partition soundness |
| **plain-product ↔ recursion(plain-product inner)** | the plain-product statement | aggregation cost of trading external `O(K)`-verifier binding for in-circuit perfect hiding |
| **plain-sort ↔ plain-product** (standalone) | Merkle commitment, K | the **partition leak** (hiding) — plain-product hides the multiset plain-sort discloses |
| **plain-product ↔ committed-product** | the plain-product aggregates | the **blinding** — turns `P_i` (unblinded oracle) into a hiding commitment |
| flat ↔ **hierarchical** (any) | — | cost/parallelism at *relaxed* privacy (the third triangle corner) |

### 8.3 Equal-privacy slices (the honest panels)

Compare *only within a privacy class*, so a cost/parallelism delta is not secretly a privacy
delta:

- **Structural-hiding slice:** `{flat, recursion}` (incl. recursive-sort / recursive-product) — the
  §1 dilemma and the recursion sub-arc.
- **Computational-commit slice:** `{committed-sort, committed-product}` — the equal-privacy finding
  (§9.5a.3); same class, differ only in glue mechanism/cost.
- **Disclosing slice:** `{plain-sort, B}` — partition (and, for B, sub-matrix) public.

### 8.4 The {flat, recursive} × {sort, grand-product} factorial

The flat↔recursion comparison confounds *two* changes — structure (flat→recurse) and
permutation mechanism (sort→grand-product). Both controls now exist as circuits, so the
four cells are a clean factorial:

| | **sort** (deterministic) | **grand-product + FS** (probabilistic) |
|---|---|---|
| **flat** | `flat_merkle_sort` | **`flat_merkle_grand_product`** *(= plain-product collapsed to K=1)* |
| **recursive** | recursion-A | recursion-plain-product |

Reading the grid:
- **mechanism cost** = a *row* delta. The flat row (`flat_merkle_sort ↔ flat_merkle_grand_product`)
  isolates the gadget's **intrinsic** cost with **zero privacy delta** (both expose only
  `{root, T}`; flat has no partition, so sort-vs-grand-product is purely cost/soundness). The
  recursive row adds the recursion-specific **surface** effect (plain-sort's `O(M)` vs plain-product's `O(1)`
  public-input absorption).
- **aggregation cost** = a *column* delta (flat→recursive at a fixed mechanism).
- **separability** = checking the two are ~additive with no interaction — itself a result (the
  partition mechanism and the aggregation are orthogonal cost contributors; the dualism,
  quantified).

`flat_merkle_grand_product` also gives the **most direct headline**: `flat_merkle_grand_product
↔ recursion-plain-product` differ in *exactly* structure (both grand-product + FS), so it's the cleanest
"what does recursion cost" comparison against the shipped variant — with **no** soundness
disclaimer to carry (unlike `flat_merkle_sort ↔ recursion-plain-product`, which mixes in the sort→GP
change). Soundness-wise the flat grand product is the *simplest* setting of the Fiat–Shamir
challenge (one circuit, one cycle, X derived and consumed in place — no distributed stitching,
no recursion-FS layer), so it's also the right place to *introduce* the gadget.

### 8.5 Measured: the flat-row delta (sort vs grand-product) — and why witness time *inverts*

The flat row is a controlled experiment in the strict sense: `flat_merkle_sort` and
`flat_merkle_grand_product` share GROUP 3 (Merkle edge proofs) and GROUP 4 (threshold)
**byte-for-byte**, take the **identical Prover.toml**, and expose the **identical** public
surface `{root, T}`. The *only* difference is GROUP 2, the permutation check. So every metric
delta below is attributable to sort-vs-grand-product and nothing else.

Per-N averages from `results/flat.csv` (sort / grand-product / Δ):

| N | `circuit_size` | `witness_s` | `prove_s` | `proof_bytes` | `verify_s` |
|---|---|---|---|---|---|
| 8    | 7 074 / 7 635 / **+7.9%**   | 0.18 / 0.18 / −2%  | 0.17 / 0.17 | 14656 / 14656 | ~0.009 |
| 128  | 158 542 / 166 453 / **+5.0%** | 0.50 / 0.38 / **−23%** | 1.17 / 1.03 | 14656 / 14656 | ~0.014 |
| 512  | 801 294 / 832 725 / **+3.9%** | 1.38 / 0.94 / **−31%** | 5.27 / 4.48 | 14656 / 14656 | ~0.009 |
| 1000 | 1 733 830 / 1 795 151 / **+3.5%** | 3.68 / 2.05 / **−44%** | equal | 14656 / 14656 | ~0.012 |

The headline result is an **inversion**: the grand product compiles to **more** constraints yet
solves its witness **faster**, and the gap *widens* with N. Gate count and witness-solving cost
are not the same currency, and this row makes the difference legible. The four metrics decompose
cleanly:

**`circuit_size` (gp larger, delta shrinking with N).** The grand product adds an O(N) hash
chain (N Poseidon2 calls for the Fiat–Shamir challenge) plus 2N field multiplications; the sort's
`check_shuffle` is cheaper in raw constraints. But the shared Merkle group is O(N·DEPTH) =
O(N·log N), so as DEPTH climbs (6 at N=8 → 20 at N=1000) the fixed-linear gp overhead is
increasingly dwarfed. The +3.5% floor at N=1000 ≈ (N extra Poseidon2)/(N·DEPTH) ≈ 1/DEPTH ≈ 1/20.

**`witness_s` (gp faster, widening to −44%) — the dynamic-ROM shuffle, explained.** This is the
load-bearing finding, so it is worth being precise about what the sort path actually does at
witness-solving time.

The sort check proves `{cycle[i]} = {0,…,N−1}` in three steps (`flat_merkle_sort/src/main.nr`
GROUP 2): (1) an **unconstrained** quicksort produces `sorted` as a hint during witness
generation (zero constraints); (2) N−1 ordering constraints assert `sorted[i] ≤ sorted[i+1]`;
(3) stdlib `check_shuffle` links `sorted` back to `cycle` by asserting they are permutations of
each other. Step (3) is where the cost lives. To check the link, the prover needs a permutation
map π — *which input position each sorted element came from* — computed unconstrained, then
**verified** constrained: for each i it must read `cycle[π(i)]` and assert it equals `sorted[i]`.
Because π is a *witness* value (not known at compile time), `cycle[π(i)]` is an array read at a
**data-dependent index**. That is a **dynamic ROM lookup**.

What "dynamic ROM lookup" means and why it is expensive: an arithmetic circuit has no pointers —
you cannot "jump to address idx" when `idx` is itself a wire value. So a dynamic read `arr[idx]`
is realised as a **memory-consistency argument**. The array is modelled as a read-only memory
table; every access is logged as an `(index, value)` pair (ACIR emits dedicated `MEM_INIT` /
`MEM_OP` opcodes, which Barretenberg lowers to ROM-consistency gates); and the prover proves —
via *its own* internal sorting/permutation argument over the access log — that every read
returned the value actually stored at that index. So one `arr[witness_idx]` is **not one gate**:
it expands into table machinery, and crucially the **witness solver** must resolve the whole
access pattern at solve time — build the access log, sort it, and fill the consistency hints.
`check_shuffle` performs ~2N such dynamic accesses, so on top of the quicksort the solver does
O(N) dynamic-memory bookkeeping. That bookkeeping is what `witness_s` is paying for, and it grows
with N — hence the *widening* gap.

The grand product, by contrast, is entirely **straight-line, statically-indexed arithmetic**:
`lhs *= (X + cycle[i])`, `rhs *= (X + j)`, and the Poseidon2 challenge chain. The loops unroll at
comptime, so *every* array index is a compile-time constant — there are **no dynamic ROM lookups
at all**. The witness solver just evaluates a fixed sequence of multiplications and hashes in
order: no permutation hint, no access log, no memory-consistency sort. Straight-line evaluation
is cheap *per element* even though it emits *more* total constraints (the extra N Poseidon2). So
the two checks sit on opposite sides of the same trade: the sort buys *fewer constraints* with
*more witness-solver work* (quicksort + O(N) dynamic-ROM consistency); the grand product buys
*less witness-solver work* with *more constraints* (the O(N) FS chain). On the shared backbone
this GROUP-2 delta is the only moving part, so `witness_s` measures exactly the dynamic-ROM
overhead of the shuffle, and `circuit_size` measures exactly the FS-chain overhead of the product
— the same physical difference seen through two different cost lenses.

**`prove_s` / `peak_mb` / `proof_bytes` (essentially equal).** UltraHonk pads the circuit to the
next power of two before proving. The +3.5–7.9% gate delta never crosses a 2^k boundary, so both
variants land in the **same dyadic size class** — the proof is **byte-identical** (14 656 B at
every N, the smoking-gun confirmation), and the prover's MSM/FFT work and peak memory are
size-class-determined, not sensitive to the small constraint delta. Witness solving is the *only*
prover-side stage that "sees" the GROUP-2 difference, precisely because it operates on the actual
constraint/opcode stream rather than the padded dyadic circuit.

**`verify_s` (constant, ~0.01 s).** Succinct verification: independent of N and of the variant.

**Takeaway for the row delta.** The flat-row comparison yields a one-sentence thesis result:
*same statement, same privacy, same Merkle backbone, so the row isolates the permutation
mechanism — and a deterministic sort, though cheaper in constraints, is more expensive to* witness
*than a probabilistic grand product, because its `check_shuffle` resolves O(N) data-dependent
(dynamic-ROM) array reads at solve time while the grand product is pure straight-line arithmetic;
the two land in the same UltraHonk dyadic bucket, so prove time, memory, and proof size are
unchanged.* (Harness note: `compile_s` and `witness_s` are isolated `nargo` calls in
`pipeline/run.py` — source patching, instance solve/"pathing", VK write, `bb gates`, and the Rust
Merkle-tree build all sit *outside* both timers, so these deltas are circuit behaviour, not
measurement contamination. The N=8 `flat_merkle_sort` `compile_s`≈10 s is a one-off cold
dependency build, not signal.)

---

*Related: `FRONTIER_REFRAME.md` (pick-two triangle F4, stitching tax, privacy ladder),
`HIERARCHICAL_EXPLAINED.md` §9b/§14.5 (committed variants, privacy classes),
`Recursive_inner_circuit_choice_explained.md` (inner-circuit choice, the O(1) surface),
`FIGURES_AND_METRICS.md` (how to plot the frontier), `Thesis_Outline.md` Ch 8-10,
`project_recursion_experiment` memory (the 704k*K numbers).*

---

# 9. SESSION RESOLUTION (2026-06-03) — The locked spine, variant order, comparison plan, and connective tissue

*This part is the product of a full working session that closed the open choices
in §6 and worked out the connective tissue the earlier sections left implicit.
It is written to be self-contained and explicit — nothing is left "obvious" —
because it is the single reference to draft Ch 8-10 from. Where it restates an
earlier finding it does so deliberately, so this section can be read top-to-bottom
without cross-jumping.*

> **REVISED (2026-06-03, later in the same session) — the *ordering* decision is superseded by
> §11.** Working the cold-open's details (the deferral justification, the segment-reuse
> "zigzag", and the realization that "poles" is not enough to justify front-loading recursion)
> showed that the **dilemma-as-cold-open / result-first-build-last** ordering *fights the
> material*. The current recommended spine is the **monotone flow in §11**: it keeps the
> stitching-tax backbone but reaches recursion as the natural *endpoint* (no deferral, no zigzag)
> and demotes the flat↔recursion dilemma to an intro signpost + a derived synthesis. **§9 is
> retained for reference and comparison.** Its *analyses* remain valid and are reused by §11 —
> frame subordination (§9.1/§9.3), P/V/C (§9.3.2), the verification→ZK / statement-witness lens
> (§9.3.3), the per-variant motivations (§9.6), the recursion sub-arc / factorial (§9.7), the
> prover/verifier reveal (§9.8), §9.4.3's "natural recombination", and the refrains (§9.13).
> **Only the top-level *ordering* changed**; everything below still holds within the monotone
> frame. Read §11 first; consult §9 for the deeper treatment of any analysis it cites.

## 9.0 What this section settles

Four decisions, locked:

1. **The spine = the stitching tax** (a named conceptual contribution). The dualism is
   its prologue; the perfect-hiding dilemma is its cold-open *scene*; the pick-two
   triangle and the privacy ladder are its two *projections*. One design space, several
   lenses — not four competing theses (§9.1, §9.3).
2. **Recursion order = result-first, build-last.** State the flat-vs-recursion dilemma
   as a *finding* in the cold-open (no construction), present constructions in
   dependency order, and *build* recursion last — after plain-product exists to recurse on (§9.4,
   §9.5).
3. **The recursion sub-arc presentation = plain-product first, plain-sort second.** recursive-product is the
   shipped construction (the "free inner"); recursive-sort is introduced afterwards as the
   *fairness control* that de-confounds the comparison (§9.7).
4. **verification → ZK enters as the statement–witness boundary**, a precise restatement
   of the stitching tax's "what is bound" axis — used as a Background on-ramp and a
   sharpening of the variant-as-statement reframe, **not** promoted to a fifth organizing
   frame (§9.3.3).

The big idea that fuses spine (stitching tax) and cold-open (dilemma): **flat is the
stitching tax never incurred (K=1, nothing to bind); recursion is the stitching tax fully
folded into the prover (all three symptoms gone, 704k×K paid). Every hierarchical
variant is an interior point — a different way of paying.** So the cold-open dilemma is
the spine viewed at its two extremes, and Chapter 9 runs as a *loop*: open on the poles
→ fill the interior → return to one pole (recursion) to build it.

## 9.1 The spine decision — why the stitching tax, with the dilemma as cold-open

The three candidates are **not** coequal; two are components of the first.

### 9.1.1 Spine (a) — Binding tax  *(CHOSEN as backbone)*

**Through-line:** *Decomposition buys no algorithmic ZK win — only parallelism (the
dualism). To collect it you must rebind K proofs into one statement; that binding is a
single artifact with three coupled symptoms (partition leak, O(K) verifier, bookkeeping);
the family is generated by* where *binding lives ×* what *it binds; each variant removes one
symptom; folding removes all three cheaply.*

| Strengths | Weaknesses |
|---|---|
| **Generative, not a catalogue** — gives the reader a machine that *produces* the variants; each earns its place by removing a named symptom. | **Abstract up front** — the reader meets a "tax with three symptoms" before seeing one hierarchical construction in detail; risk of feeling imposed top-down. |
| **A named, ownable contribution** — examiners remember "the stitching tax"; theses are rewarded for one crisp conceptual handle. | **The unifying claim must hold** — "three symptoms, one artifact, dissolve together" is a claim; if an examiner finds a symptom that does not co-dissolve, the frame weakens. |
| **Absorbs everything** — dualism = prologue, triangle = cost projection, ladder = privacy projection. Unifies all four frames. | **Not standard literature** — must pre-empt "isn't this just the known cost of aggregation / no free lunch?" Answer: the *specific* 3-symptom decomposition that dissolves together is the contribution. |
| **Dissolves the recursion-dependency trap** — "where binding lives" *is* the axis (in-circuit vs external) distinguishing recursion from hierarchical. | **Buries the vivid result** — the flat-vs-recursion dilemma becomes one comparison inside a systematic treatment rather than the headline (fixed by using it as the cold-open). |

### 9.1.2 Spine (b) — Perfect-hiding dilemma  *(DEMOTED to the cold-open scene of (a))*

**Through-line:** *At perfect hiding, flat and recursion force cost XOR parallelism. The
hierarchical family escapes — flat's cost + recursion's parallelism — at a precisely
characterized price (O(K) verifier + one privacy notch, which committed-\* minimize).*

| Strengths | Weaknesses |
|---|---|
| **Immediate, vivid hook** — "cost XOR parallelism, here's how I break it" lands in one breath; reads like problem→resolution. | **Built on a 2-point comparison** — a whole spine on one dichotomy under-organizes 5+ variants; the systematic middle still needs a generative principle, which *is* the stitching tax. So **(b) collapses into (a) for the body.** |
| **Clear protagonist move** — the hierarchical family breaks the deadlock; memorable. | **Dependency trap bites hardest** — opening on the dilemma forces recursion up front, but recursion is built from plain-product; must present recursion as a black-box result and defer its construction. |
| **Front-loads equal-privacy honesty** — privacy held fixed in the opener; methodologically clean. | **"Best of both worlds" temptation** — the "escape" framing pulls toward overclaim; needs heavy caveat maintenance. It is a triangle *corner*, not a domination. |

### 9.1.3 Spine (c) — Privacy ladder  *(DEMOTED to the §9.6 privacy section)*

**Through-line:** *Order the constructions by the assumption their partition-hiding rests on:
disclosed (B/plain-sort) → computational-with-oracle (plain-product) → computational-commitment (committed-\*) →
structural/assumption-free (recursion/flat/folding). Cost/parallelism annotate each rung.*

| Strengths | Weaknesses |
|---|---|
| **Native to MSc Cybersecurity** — assumptions/privacy is home turf; examiners may expect a security-centric axis. | **Blind to the headline result** — recursion and flat sit at the *same* top rung, so the spine cannot see the cost-vs-parallelism dilemma, the most interesting comparison. |
| **Principled, near-monotone** — assumption-decreasing is a clean ordering. | **Backwards relative to effort** — the strongest empirical contribution is the cost/parallelism frontier; making privacy the spine demotes it to annotation. |
| Puts threat model / §9.6 at the centre. | **Not a clean line** — committed-sort and committed-product land on the *same* rung (the equal-privacy finding F7) and differ only in cost; "commit to hide" vs "don't put it there" are two mechanisms, a small lattice linearized by force. |

### 9.1.4 The verdict and what was *really* being decided

(b) is the opening *scene* of (a); (c) is the right organizing principle for the privacy
*section* (§9.6), not for the chapters. So the real, narrow decision was: **do you NAME
"the stitching tax" as a coined contribution and defend it, or keep the vivid dilemma on the
surface and leave the stitching-tax structure implicit underneath?** We chose to name it —
it unifies all four frames, neutralizes the dependency trap, and gives a contribution
examiners remember — *and* to keep the dilemma as the cold-open, because the hook and the
machine are not in conflict (the hook is the machine's first scene). The one legitimate
reason to have chosen (c) instead: if the supervisor/programme demands privacy as the
visible organizing axis of a Cybersecurity thesis. That remains a live institutional
consideration to confirm; if it bites, make (c) the spine with (a) demoted to a section, at
the cost of burying the best empirical result.

## 9.2 The unifying reframe and the loop structure

**The reframe (load-bearing):** the dilemma's two poles ARE the progression's two
endpoints. flat = K=1, stitching tax never incurred. recursion = stitching tax fully folded
into the prover (704k×K). The hierarchical variants are the interior — each a different
*way of paying* the tax. This turns the cold-open dilemma into the spine's own extremes,
so the chapter is not "hook, then unrelated systematic treatment" but a single arc.

**The loop:** open on the poles (§9.0 cold-open) → introduce shared decomposition once →
fill the interior (plain-sort → plain-product → committed) → **return** to one pole (recursion) to build it →
point past the map (folding). The reader ends where they started — now with the whole
space in hand. The loop is *productive*, not circular (the full defense is §9.10).

## 9.3 The four frames, subordinated — and the verification/ZK lens

### 9.3.1 The subordination

- **Binding tax** = the **spine** (the engine that generates the family).
- **Dualism** = the **prologue** (why decompose at all → parallelism is the only payoff).
- **Pick-two triangle** = the **cost projection** of the design space (at fixed privacy).
- **Privacy ladder** = the **privacy projection** of the same space (§9.6).

Say this explicitly so the reader stops drowning: *one design space (two binding decisions),
seen through a cost lens (triangle) and a privacy lens (ladder), with the dualism as the
reason the space exists at all.*

### 9.3.2 P + V + C — the three corners of the pick-two triangle

The three desiderata a decomposed-proof architecture might want, **at fixed privacy**:

- **P** — *Parallel proving + low per-prover memory*: K segments prove independently on K
  machines, each with small memory.
- **V** — *O(1) verifier*: succinct verification — proof size and verify time constant,
  independent of K.
- **C** — *low prover overhead / total cost*: no aggregation tax; total gates ≈ flat (the
  dualism's "work is conserved" floor).

Each architecture gets exactly **two**:

| | P | V | C | which axis it sacrifices |
|---|:--:|:--:|:--:|---|
| flat | ✗ | ✓ | ✓ | P (serial, one prover, high memory) |
| hierarchical (plain-sort / plain-product / committed) | ✓ | ✗ | ✓ | V (O(K) verifier) |
| recursion | ✓ | ✓ | ✗ | C (704k×K prover tax) |
| **folding** (future) | ✓ | ✓ | ✓ | — (breaks the triangle) |

### 9.3.3 The verification → ZK separation, done precisely (the statement–witness boundary)

The separation "an argument that a statement holds" vs "the zero-knowledge property added
on top" is **cryptographically real** — the repo proves it (`-no-zk` mode: 410 fields vs
458 for default ZK). Two legitimate uses, one trap:

**Good use #1 — the Background on-ramp (Ch 2 / Ch 5).** Teach it as: *here is a plaintext
checker of a TSP solution (the four constraint groups — range / permutation / edge-cost /
threshold — anyone can run given the witness); now Noir + UltraHonk let you prove you ran
that checker without revealing the witness — ZK is the property wrapped around the checker.*
Maps exactly onto the flat circuits; grounds the `-no-zk` measurement as "ZK is a separable,
measurable property"; sets up the threat model (the verifier checks the statement; ZK
guarantees nothing beyond it leaks).

**Good use #2 — sharpen the variant-as-statement reframe.** Make the varying axis the
**statement–witness boundary**: *the verification relation R_TSP is constant; the SNARK's ZK
is constant; what every variant chooses is the boundary between what is in the public
statement and what is left in the witness.* plain-sort puts the partition in the statement
(discloses), committed-\* put a commitment to it (hides computationally), recursion leaves it
in the witness (absent). This **is** the stitching tax's "what is bound" decision (plaintext /
commitment / witness) — so it reinforces the spine rather than competing with it, and it
justifies plain-sort correctly: plain-sort's disclosure is a *statement choice*, not a ZK weakness.

**The trap (do not fall in).** There are THREE distinct notions hiding under
"verification vs ZK":
1. the **argument** (soundness/completeness);
2. the **SNARK's ZK** (the `-no-zk` toggle) — **identical across all variants**, not a
   discriminator;
3. **what the public statement discloses** — the axis plain-sort/plain-product/committed/recursion vary on.

The A→plain-product→committed story lives in #3, **not** #2. Never write "plain-product adds more
zero-knowledge than plain-sort" — plain-sort and plain-product have *identical* SNARK ZK; plain-product's **statement** discloses
less. An examiner who knows ZK catches that instantly.

**Two guardrails:**
- **Keep #2 and #3 rigidly distinct.** Variants differ in *what the statement discloses*
  (structural), never in "how much ZK." Reserve "zero-knowledge" for the constant SNARK
  property.
- **Don't overload "verification" and don't make this a fifth frame.** "Verification" already
  means the SNARK **verifier** (the V in the triangle, `verify_s`); call the plaintext-checker
  step "checking/validating a solution" or "the relation R_TSP." Use the separation only as
  (a) the Background on-ramp and (b) a restatement of "what is bound" — promoting it to a
  third structural result re-clutters the thing the spine just cleaned up.

## 9.4 Recursion order — result-first, build-last (and how to motivate its cost early)

### 9.4.1 The three options and the verdict

- **(A) Result first, build last  *(CHOSEN)*.** State the dilemma as a finding in the
  cold-open (recursion = a *result*: its cost + surface, no construction), present
  constructions in dependency order, build recursion last. Vivid hook + honest build order;
  the forward reference *motivates* ("we'll build this once we have its components"); works
  under any spine. Mild cost: recursion is mentioned twice (teaser + construction) — manage
  with an explicit "as previewed in §9.0" pointer and keep the teaser to the table + one
  sentence.
- **(B) Strict dependency order.** No hook; everything in build order. Maximally honest but
  buries the most memorable result as the last station; reader lacks momentum. (A) = (B) + a
  free hook, so (A) dominates.
- **(C) Recursion as full opener.** *Ruled out — strictly dominated.* Constructing recursion
  first means explaining plain-product's grand product + Fiat–Shamir before plain-product is motivated (recursion
  recurses on the plain-product segment) — the most sophisticated artifact taught to a reader who has
  not seen one segment. (A) gets the same front-loaded *result* with none of the inversion.

### 9.4.2 How to motivate "recursion costs a lot" in the cold-open, before any construction

You need the *shape*, not the exact number: **recursion's prover cost grows with K because
each inner proof is verified inside a circuit, and in-circuit proof verification is
expensive.** Three legs, increasing strength:

1. **Literature / theory (plausibility).** It is *well established* that the dominant cost of
   recursive SNARKs is the in-circuit verifier (curve arithmetic + Fiat–Shamir transcript
   hashing). Not your claim to defend — it is *why folding exists* (Nova's pitch is "avoid the
   expensive in-circuit verifier"). The cold-open may assert it as known.
2. **Your own measurement (the number).** The specific ~704k/segment is *your empirical
   result* (the repo benchmarks it), forward-referenced to Ch 10. You are stating a result
   whose *mechanism* is derived in §9.5 and whose *value* is measured in Ch 10 — not asking
   for faith.
3. **The qualitative claim is all the dilemma needs.** The hook only requires "recursion is
   more total prover work than flat" to make cost-XOR-parallelism bite. The 704k is the
   payoff later, not a premise now.

**Cold-open phrasing:** *"Recursion's cost is dominated by verifying each inner proof inside
the outer circuit — a well-understood bottleneck, and precisely what folding schemes were
designed to avoid. For our backend this is ~704k gates per segment, hence ~K× total (§9.5
constructs it; Ch 10 measures it)."*

### 9.4.3 Why recursion is the *natural* application of decomposition (the conceptual anchor)

This is the deep motivation that makes recursion the gravitational centre of the arc rather
than just "one of three bindings." It sharpens the cold-open (§9.0) and Hinge 1 (§9.9.1), and
answers the question *"why recursion, and not something else, for decomposition?"*

**The core insight — verification is a computation, so you can prove it.** Decomposition
produces **proof objects** (the K segment proofs). The most basic question in the framework:
*what is the natural thing to do with a proof?* You **verify** it. And verification is just a
**computation** — a fixed algorithm (`bb verify`) taking (VK, proof, public inputs) → a bit.
The whole thesis rests on "a SNARK proves any computation." Verification is a computation.
Therefore **the proof system can prove its own verification** — and that self-application *is*
recursion (`verify_honk_proof` in `circuits/recursion` is the verifier algorithm expressed as a
circuit). Recursion is the proof system applied to its own output. One sentence:

> *Decomposition fragments one proof into K; the proof system's native way to recombine proofs
> is to prove they verify; that is recursion.*

**"Natural" made rigorous, in two senses:**
- **Formal — recursion is the *inverse* of decomposition.** Count proofs. Decomposition:
  1 statement → K proofs. Recursion: K proofs → 1 proof (verify them inside one circuit). It is
  the **recombination** that undoes the fragmentation, and because it recombines all the way to a
  single proof it **restores exactly the guarantee decomposition broke** — one proof, O(1)
  verifier, structural hiding (the inner public inputs become the outer's *witness*). "Decompose
  for the prover, recombine for the verifier."
- **Cryptographic — the binding is *proven*, not asserted.** The cross-instance checks (same
  `root`, matching boundaries, covering partition) become **in-circuit asserts on now-trusted
  values**, so the binding inherits the proof system's own soundness; no new trust object (one
  VK, one `bb verify`). The binding is itself a theorem the proof carries.

**Why not something else — the alternatives are not faithful recombinations:**
- **External cross-checks (hierarchical):** binds, but is **not a recombination** — K+1 proofs
  remain, the shared values must be *disclosed* to be compared (the leak), and the binding lives
  in an external, non-cryptographic checker (the trusted-code surface). The cheap **shortcut**.
- **Re-prove everything in one circuit:** a single proof, but you've *abandoned* decomposition —
  one circuit over all K segments **is flat**.
- **Folding (Nova/ProtoStar):** not a different answer but a **refinement of recursion** —
  recursion with the expensive in-circuit verification *deferred/amortized*. It presupposes
  recursion as the primitive it optimizes, which is why recursion (eager) is the natural first
  answer and folding (lazy) the optimization.

So among bindings, recursion is the unique one that (a) uses the proof system itself, (b)
recombines to a single proof restoring flat's form, and (c) is the primitive folding then
refines. That triad is what makes it canonical.

**The honest conditional (so it survives an examiner who says "rollups aggregate externally —
that's the standard thing"):** recursion is the natural application **given the goal of
preserving the monolithic guarantee** (one proof, O(1) verifier, structural hiding). Relax that
goal and external binding is *operationally* cheaper and simpler to build. Two senses of natural:
recursion is **conceptually** natural (the faithful recombination that keeps the guarantee);
hierarchical is **operationally** natural (the least-effort shortcut). The thesis benchmarks
against "preserve the guarantee" — which is *exactly why* recursion is the canonical pole and
hierarchical the **characterized compromise** against it (defined by *what it gives up*).

**Effect on the order.** Recursion belongs in the cold-open as a *pole* because it is what
decomposition *wants to become*. The dilemma sharpens to: *flat (never fragment) vs recursion
(fragment, then faithfully recombine) — same guarantee, opposite cost/parallelism* — and the
hierarchical interior is opened by the question *"can we bind more cheaply if we give up the
faithful recombination?"* Recursion is the centre the whole arc orbits; hierarchical is the
deviation tolerated to dodge its price.

## 9.5 The full chapter flow (Ch 8 → 9 → 10), beat by beat

### Chapter 8 — setup (dualism → stitching tax)

- **§8.1–8.5 Dualism.** Classical hierarchical TSP shrinks search; naive hierarchical ZK
  saves no gates (the O(N) partition check + K boundary Merkle proofs absorb the per-segment
  savings) → **decomposition's only payoff is parallelism.**
- **§8.8 The stitching tax (the engine).** K independent proofs must be rebound; name it —
  one artifact, three coupled symptoms (partition leak / O(K) verifier / bookkeeping),
  generated by two decisions (*where* binding lives × *what* it binds); the pick-two triangle
  as the cost geometry. **Seed the reveal here:** one line that the O(K)-verifier "symptom"
  will turn out to be the *cheap* way to pay.
- **Exit sentence:** *"The stitching tax is paid differently by every construction; the
  sharpest way to see its two extremes is a single comparison — which opens the next chapter."*

### Chapter 9 — the variants (the loop)

- **§9.0 Cold open — the perfect-hiding dilemma.** flat vs recursion, both publish
  `{root, T}`; flat ~782k serial, recursion 704k×K parallel; *at perfect hiding you can't
  have both.* Recursion as **result only** (cost + surface). Pivot: *these are the two poles
  of the stitching tax; the chapter fills the interior, then returns to build recursion.*
- **§9.1 Shared decomposition** — K segments + glue, introduced once. Organizing question:
  **where does binding live, external or in-circuit?**
- **§9.2 plain-sort** — *buy parallelism → the tax appears in full* (leak + O(K) + bookkeeping);
  cheapest total gates, deterministic; the disclosure-regime endpoint + the diagnosis.
- **§9.3 plain-product** — *shrink surface O(M)→O(1) + un-serialize the check*; **honestly not
  cheaper** (relocates O(N) into segments); a surface/critical-path investment whose payoff is
  deferred to recursion; motivate on surface/soundness, **never** on hiding.
- **§9.4 committed-sort / committed-product** — *close the leak* (blinded C_i, reveals only K); the
  equal-privacy finding (same rung, differ only in glue cost/mechanism); **only the O(K)
  verifier remains.**
- **§9.5 Recursion** — *built last; cheque cashed.* In-circuit/witness binding; surface →
  `{root, T}`; all three symptoms collapse; prover pays 704k×K; plain-product's O(1) surface pays off.
  Contains the recursion sub-arc (§9.7 below) and the prover/verifier reveal (§9.8 below) and
  the Fiat–Shamir floor.
- **§9.6 Privacy analysis** — the **privacy ladder** lives here as the local axis (spine-c in
  its proper home) + per-variant threat model.

### Chapter 10 — the comparison

- **§10.1 Two principles, up front.** (1) Compare only *within* a privacy class. (2) Every
  claim changes *exactly one* thing.
- **§10.2 Equal-privacy slices** — structural {flat, recursion}; computational-commit
  {committed-sort, committed-product}; disclosing {plain-sort, B}.
- **§10.3 The 2×2 factorial** {flat, recursive} × {sort, grand-product}: column delta =
  aggregation cost; row delta = mechanism cost (flat row = strict controlled experiment, the
  witness-time inversion); separability = the dualism quantified. **Headline:**
  `flat_merkle_grand_product ↔ recursive-product` (differ in exactly structure, no soundness
  caveat).
- **§10.4 Cross-class cost/benefit** — flat↔hierarchical (the third corner); A↔plain-product; plain-product↔committed.
- **§10.5 The frontier figure** — the pick-two triangle at fixed privacy: recursion the
  perfect-hiding endpoint, committed-sort/plain-product the equal-privacy non-recursive points, plain-sort/plain-product as
  upstream disclosure/oracle markers (arrows, not co-equal), folding the empty corner.
- **The refrain, repeated:** *total work is conserved* — hierarchical never beats flat on
  total gates; the win is parallelizability of the same work.

## 9.6 Order of variant introduction & per-variant motivation

**Order:** flat → plain-sort → plain-product → committed-sort/plain-product → recursion → folding (monotone, symptom-removal).
Hold two things: (i) recursive-sort / recursive-product are **not** in this list — they are the
recursion *sub-arc* inside §9.5 (§9.7); (ii) presentation order ≠ implementation order
(plain-sort → B → plain-product in code). Variant B, if built, sits at the **disclosing end** beside plain-sort
(sub-matrix public) as the gate-saver.

### 9.6.1 The links flat → decomposition → plain-sort → plain-product (transition prose)

**flat → decomposition** *(motivation + problem):*
> *Flat proves the whole cycle in one circuit — one prover, serially, holding the entire
> witness. Can we parallelise? Split the cycle into K segments and prove each independently.
> The dualism warns us this saves no total work — but it buys K small, independent provers.
> The catch: K independent proofs bind to nothing. `bb verify` shows each is internally
> consistent; nothing forces them to share one matrix, agree on boundaries, or cover the node
> set. Decomposition forces a binding step — and the rest of this chapter is organised by
> where that binding lives and what it binds.*

**decomposition → plain-sort** *(the minimal, diagnostic instantiation):*
> *The most direct answer is to bind externally, on the plaintext values: K segment proofs
> plus a glue proof, with the verifier running equality cross-checks. That is plain-sort — and
> because it binds plaintext, it exhibits the stitching tax in its rawest form (the partition is
> simply disclosed). We start here precisely because it makes the tax visible.*

**plain-sort → plain-product** *(driven by plain-sort's concrete inefficiencies, not privacy):*
> *plain-sort's glue exposes O(M) per segment and runs a serial O(N) sort. plain-product attacks both — a
> grand-product multiset check shrinks the public surface to O(1) and distributes the work. It
> is not cheaper overall; it is a surface and critical-path move whose payoff we defer.*

### 9.6.2 Why plain-sort and plain-product before committed-\* — the hidden premise refuted

The question "why not just use committed-\* directly?" assumes committed-\* **dominate**
plain-sort/plain-product. They do not: committed-\* are better on **privacy** but cost more (blinding, in-circuit
opening checks, the commitment fold) and remain a notch below flat/recursion (reveal K, hiding
rests on the scheme). "Just use committed" is only correct *when you need partition privacy and
can pay for it* — a regime, not the default. The motivations are **asymmetric**:

- **plain-sort is a genuine endpoint, not a stepping stone.** Cheapest total gates, deterministic check
  (no Schwartz–Zippel error), simplest soundness. The motivating scenario is real: in many
  deployments the partition is public anyway (known territory/cluster assignment; federated
  node ownership), where blinding is pure waste. plain-sort is the **disclosure-regime** frontier point.
- **plain-product is a waypoint — admit it.** It is weakly motivated *as a standalone deployed variant*
  (not cheaper than plain-sort; standalone hiding only computational-with-oracle). Motivate it on what it
  actually earns: (i) **the design you recurse on** — its O(1) surface keeps the recursive outer
  segment-size-independent (a plain-sort inner, M+4 fields, makes the outer grow with N); (ii) the
  **high-K / distributed-check corner** (O(K) glue removes plain-sort's O(N) memory floor); (iii) the
  **de-confounding control** below.

**The decisive argument (de-confounding).** committed-product differs from plain-sort in *two* independent
ways: (i) the surface/check change (plain-sort → plain-product) and (ii) the blinding (plain-product → committed-product). Skip
the intermediates and the two changes are conflated — you cannot attribute which cost/benefit
came from which decision. plain-product isolates (i), so plain-product → committed-product cleanly isolates (ii), the
cost of the blinding alone. **plain-product is to committed-product what recursive-sort is to recursive-product:** the
control that holds one variable fixed.

**Two more reasons the intermediates must be exhibited:**
- **Diagnosis before cure.** The blinding is only legible as a fix if the reader has seen the
  leak it closes (A shows it raw; plain-product shows the subtler oracle leak). Present committed-\* cold
  and the commitment fold looks like unmotivated machinery.
- **The progression *is* the contribution + the equal-privacy finding needs the backdrop.** Each
  step removes one symptom (a structural result requiring visible rungs); and "committed-sort and
  committed-product reach the *same* rung" is only meaningful against plain-sort and plain-product being *unequal* (A
  discloses; plain-product computational-oracle). committed-\* **equalize** what plain-sort/plain-product left unequal.

**Chapter stance (per resolved C6).** Draw plain-sort/plain-product as the upstream *diagnosis / disclosure* points
on the progression line, with arrows into committed-\* — not as co-equal frontier markers — and
*say out loud* that plain-product standalone is a waypoint. That honesty is stronger than a forced
standalone justification an examiner would see through.

## 9.7 The recursion sub-arc — plain-product first (shipped), plain-sort second (the fairness control)

recursive-product and recursive-sort play two different roles: **plain-product is the construction you ship; plain-sort is
a measurement instrument.** Leading with plain-product matches the build order (the "free inner" the
hierarchical arc just handed you) and avoids making plain-product look like a destination climbed toward.

**Why plain-product leads (and isn't a thing you "improve to").** You arrive at recursion via the
hierarchical arc, which hands you the plain-product segment as the free inner; its O(1) surface is *why* it
is the smart choice (outer stays segment-size-independent). So recursive-product falls out of the
construction — don't motivate it, it *is* the recursion.

**The transition to plain-sort — fairness forces a control:**
> *We now ask what recursion **cost**. The obvious comparison is recursive-product against
> flat_merkle_sort — both perfect-hiding, both `{root, T}`. But it is not fair: flat_merkle_sort
> → recursive-product changes **two** things at once — the **structure** (monolithic →
> decompose-and-verify-in-circuit) and the **partition mechanism** (deterministic sort →
> grand-product + Fiat–Shamir). A cost delta could be either. To isolate the cost of recursion
> **as a technique**, we hold the mechanism fixed: recurse on the **A** segment, keeping the
> deterministic sort, matched to flat. That is recursive-sort — built not as a variant to deploy,
> but as an experimental control, exactly as flat_merkle_grand_product was a control on the flat
> side.*

This frames recursive-sort as an **instrument, not a competitor** (so introducing it after plain-product is
forward motion toward rigor, not backtracking), and pre-states its handicap honestly (its O(M)
inner surface makes the outer grow with N — the very thing plain-product fixed), reinforcing that it is a
measurement tool.

**How to move from there — the factorial, then the headline:**

| | sort (deterministic) | grand-product + FS |
|---|---|---|
| **flat** | `flat_merkle_sort` | `flat_merkle_grand_product` |
| **recursive** | **recursive-sort** | **recursive-product** |

- **Column delta** (flat → recursive, mechanism fixed) = **pure aggregation cost** (the K
  in-circuit verifiers ~704k each) — what recursive-sort was built to measure.
- **Row delta** (sort → grand-product, structure fixed) = **pure mechanism cost** — flat row at
  zero privacy delta (the witness-time inversion), recursive row adding the O(M)→O(1)
  surface-absorption effect.
- **Separability** (deltas ~additive, no interaction) = a result in itself; the dualism
  quantified.
- **Headline:** *the sharpest single statement is `flat_merkle_grand_product ↔ recursive-product`
  (both grand product, differ in exactly the structure — no soundness caveat); recursive-sort's
  role was to prove that delta is attributable to structure alone, by showing the same column
  delta at the sort mechanism too.* Then **retire recursive-sort** (it is off the frontier figure).

**The correction to carry through the whole sub-arc (state once, loudly):** inside recursion,
plain-sort vs plain-product is **not** a hiding difference — both partitions (plain-sort's `sorted_nodes`, plain-product's `P_i`) become
witness of the outer circuit, so the verifier sees neither. The choice is purely **soundness +
surface** (exact sort vs Schwartz–Zippel + Fiat–Shamir; O(M) vs O(1) surface). Hiding is identical
across flat, recursive-sort, recursive-product — it is the SNARK's ZK, constant, not a discriminator.

## 9.8 The prover/verifier reveal — setup→reveal, not problem→relief

The insight to preserve: *hierarchical moves the binding cost to the verifier (O(K) — a little
more verify time / proof bytes), which is cheap and yields big prover gains; recursion keeps the
cost on the prover (704k×K — big).* Because hierarchical is introduced first, the O(K) verifier
enters as a mild *symptom*, and recursion then **re-frames it as a bargain** — a stronger shape
than introducing recursion's pain first:

- **Recursion-first (rejected order):** "big prover cost (recursion) … *relief*: move it to the
  verifier, cheap (hierarchical)." → problem → relief.
- **a+b (chosen):** mild verifier symptom (hierarchical) → recursion reveals the alternative
  costs the prover 704k×K → the symptom is **re-framed as the smart trade**. → setup →
  payoff-reveal. A cost the reader pre-accepted becoming the punchline beats relief from a pain
  just felt; and it is native to the spine — the O(K) verifier is precisely *the one symptom
  committed-\* leave standing*, so the narrative is already asking "is removing this last symptom
  worth it?"

**Three touch-points:**
1. **Seed (§8.8 / §9.2):** *"This O(K) verifier looks expensive now; §9.5 shows it is the cheap
   way to pay the stitching tax."*
2. **Reveal (§9.5):** *"Recursion eliminates the O(K) verifier — back to one succinct proof — but
   pays for it on the prover: 704k×K (~1.47M at K=2, ~3.0M at K=4). The hierarchical family paid
   for the **same** binding with an O(K) verifier: K×14.6 KB of proof and K×~10 ms of
   verification — at K=8, ~117 KB and ~90 ms, both negligible. The tax is conserved; what differs
   is who pays and by how much."*
3. **Quantify (§10.4 / triangle §10.5):** a property of the geometry — **giving up V is cheap,
   giving up C is expensive** → hierarchical is the pragmatic sweet spot; recursion's corner is
   justified only under a hard O(1)-verifier requirement → drives the use-case mapping.

**Use-case mapping (the verdict):** **hierarchical for off-chain / few verifiers** (verifier cost
cheap, prover parallelism precious); **recursion for on-chain / many verifiers** (O(1) verifier
paid repeatedly, prover blow-up amortizes). **Honest boundary:** "negligible verifier cost" holds
*off-chain at low K*; at very large K or on-chain it stops being negligible and recursion's corner
wins. Naming that boundary *is* the use-case mapping, so it strengthens the punch.

## 9.9 The two connective hinges (the loop's load-bearing transitions)

The whole loop runs on one rail — the **binding-location axis** ("where does the binding live:
external or in-circuit?").

### 9.9.1 Hinge 1 — cold-open → hierarchical ("what sits in the middle?")

The move: decompose recursion's *cost* into its *source.* Recursion's 704k×K does **not** come
from splitting into K segments (that part is cheap and buys the parallelism) — it comes from
verifying each segment proof *inside a circuit.* That is the lever. (Recall §9.4.3: that
in-circuit verification is the *faithful* recombination — recursion is what decomposition
naturally becomes; Hinge 1 is the decision to *forgo* it, externally and cheaply.)

> *Recursion buys parallelism by decomposing, then pays for perfect hiding by verifying every
> segment proof in-circuit — and it is that in-circuit verification, not the decomposition, that
> costs 704k×K. So a question presents itself: can we keep the decomposition — and its
> parallelism — but **not** verify the proofs in-circuit? We can. Bind the K proofs **externally**,
> with verifier-side cross-checks, instead of folding them into one circuit. External binding is
> cheap. The catch is that it cannot hide the values it binds on: the partition surfaces, the
> verifier now handles K+1 proofs, and the checks must be bookkept. This is the stitching tax — and
> the family that pays it externally is the hierarchical family, which sits between the two poles:
> it keeps recursion's parallelism and flat's low prover cost, and pays instead with an O(K)
> verifier and a privacy relaxation.*

This uses only the *fact* that recursion's cost lives in the in-circuit verifier (grounded per
§9.4.2) — **not** recursion's construction. The motivation for hierarchical is earned without
having built recursion.

### 9.9.2 The middle (one line)

The interior walks the *what-is-bound* sub-axis: **A** (plaintext, leak raw) → **plain-product** (plaintext,
surface shrunk — the deferred investment) → **committed** (commitment, leak closed). After
committed-\*, **only the O(K) verifier remains.**

### 9.9.3 Hinge 2 — hierarchical → recursion (callback + construction + free inner)

Triggered by the *last surviving symptom*; a promise kept, not a new introduction.

> *committed-\* closed the leak, but one symptom survives: the O(K) verifier. There is exactly one
> way to remove it and recover perfect, structural hiding at the same time: stop binding externally
> and fold the binding into a proof — verify the segments **in-circuit** after all. This is the
> construction we previewed in §9.0 as the perfect-hiding pole and deliberately deferred. We
> deferred it because it is built **from the segments we have just developed**, and we can now
> build it.*

The **free-inner** payoff (closes the loop, cashes the §9.3/plain-product promise):

> *The outer circuit needs an inner proof to verify — and we already have one. It reuses the plain-product
> segment unchanged; plain-product's O(1) public surface, which earlier looked like an unmotivated
> optimisation, is precisely what keeps the outer circuit segment-size-independent. The hierarchical
> detour was not only the cheaper alternative to recursion — it produced the component recursion is
> built from. (We do not even commit the inner: the outer already turns every inner public input
> into witness, so blinding would be redundant — the privacy comes from the recursion structure for
> free.) With the binding folded in-circuit, every shared value becomes witness, the verifier
> collapses to one `bb verify`, the public surface returns to `{root, T}`, all three symptoms vanish
> at once — and the prover pays the 704k×K we promised at the outset.*

That last clause feeds the prover/verifier reveal (§9.8) immediately.

## 9.10 The non-circularity defense (keep this ready — it is the crux objection)

**The worry, granted:** *recursion is costly → hierarchical is cheaper but leaks / fat verifier →
recursion fixes those → but recursion is costly → back at square one.* This reading is correct
**only under the assumption that the thesis is hunting for a single best construction.** It is not.

**Dissolution — the thesis maps a frontier, it does not crown a winner.** The deliverable is a
**map + a rule for choosing**, not a champion. Three constructions, three corners of the triangle,
each correct in a different regime. You cannot be "back at square one" because flat ≠ hierarchical ≠
recursion — three distinct vertices. You visit recursion *last* because it is the last corner to
characterize, not because it wins.

**Three concrete reasons recursion-at-the-end is strictly more than recursion-at-the-start:**

1. **Trade, not regress (different axis).** Hierarchical sacrifices **V** (O(K) verifier);
   recursion sacrifices **C** (prover cost). Recursion fixes hierarchical's V-problem by paying on
   a *different* axis (C) — moving along an *edge* of the triangle, not looping to the origin. A
   regress would mean recursion reintroduces hierarchical's *own* O(K) verifier; it does not
   (recursion's verifier is O(1)).
2. **Spiral, not circle (the cost is re-valued).** The *number* (704k×K) is the same at both
   visits; its *status* is not:

   | | cold open (start) | the return (end) |
   |---|---|---|
   | recursion is… | a black box | a construction you derived |
   | its cost is… | **asserted** (literature + forward-ref) | **derived** (it *is* the in-circuit FS-verifier) |
   | the cost means… | the **bad half of a dilemma** | the **price of a feature** (O(1) verifier + structural hiding) **with a known buyer** |
   | the question is… | "is this cost bad?" | "*when* is this cost worth paying?" |

3. **Ends pointing out, not back.** The section terminates by identifying that recursion's cost is
   intrinsic to in-circuit binding (the FS floor) and that the thing that removes it — **folding** —
   lives *outside* the triangle (the empty P+V+C corner). The arc *closes the map* and *opens the
   next frontier*; it does not return to ignorance.

**The formal part — no *logical* circularity (the dependency DAG):**
1. "in-circuit proof verification is expensive" — literature; depends on nothing in the thesis.
2. "recursion costs ~704k×K" = (1) + your measurement.
3. "hierarchical is worth exploring" — motivated by (2) + the binding-location insight.
4. "the plain-sort/plain-product segment circuits exist" — built to realize (3).
5. "recursion can be constructed" — its inner *is* the plain-product segment (4) + the in-circuit binding choice.
6. "recursion's cost is derived and contextualized" — (5) + (2).

No node depends on itself; in particular **(2), the cost, stands on (1) + measurement and never
depends on (5), the construction.** So when (3) uses recursion's cost to motivate hierarchical, it
leans on (2), which does not wait for the construction built later. The *only* recurrence is that
recursion is **mentioned** at the start (using (2)) and **built** at the end (5) — **presentation
order, not logical dependency.** (Compare: a paper's abstract states "95% accuracy" before §4
describes the method; not circular, because the result rests on experiments independent of where
the prose sits.)

**The one-sentence version:** *We never return to square one because square one was a dilemma with
two flawed options, and the end is a complete decision procedure over a three-corner map —
hierarchical when the verifier is cheap, recursion when O(1) verification is mandatory, folding to
escape both. The cost number is unchanged; what changed is that you now know its mechanism, its
alternative, and exactly who should pay it. A circle returns you to ignorance; this returns you with
the map drawn.*

## 9.11 Folding as future work — principled scope, not avoidance

The non-defensive answer: **you *did* investigate folding immediately — conceptually — and
identifying it as the triangle-breaking corner is itself a result.** What you did not do is
*implement* it, for a reason that is a *strength*:

- **Implementing folding would break the thesis's own comparison discipline.** The entire method is
  controlled, single-backend (UltraHonk) comparison — apples-to-apples is the point. Folding
  (Nova/ProtoStar/SuperNova) is a *different proof system*, typically a different curve cycle and
  tooling ecosystem; dropping it in means a backend change mid-thesis, confounding every cost
  comparison the thesis spent its length controlling. So folding is out of scope **because of the
  methodological commitment that makes the rest rigorous.**
- **The prediction is the deliverable.** The contribution is mapping the frontier and showing
  folding is the unique corner targeting P+V+C at once (it removes the in-circuit verifier that
  costs recursion 704k×K). Identifying the corner — and *why* folding fills it — is a falsifiable
  prediction and a roadmap; building it would be a second study.
- **The conceptual response is immediate and on-page.** The moment recursion's cost lands (§9.5),
  the *theoretical* answer "folding removes exactly this" appears as a forward pointer. So you
  respond to "recursion is costly" instantly at the level of *identifying the fix*, and reserve only
  the *implementation* for future work.

**Phrasing (§12.2.1):**
> *The natural response to recursion's prover tax is folding: schemes like Nova were designed
> precisely to remove the in-circuit verifier that costs recursion 704k×K. In our framework, folding
> is the single corner that breaks the pick-two triangle — P, V, and C simultaneously. We identify it
> as that corner and characterise what it must achieve; we do not implement it, because folding
> requires a different proof system, and introducing a second backend would undermine the controlled
> single-backend comparison on which every cost claim in this thesis rests. Implementing and
> benchmarking a folding variant is therefore a self-contained continuation, not a missing piece of
> the present study.*

The distinction that defuses the objection: **investigated conceptually = yes, immediately;
implemented = no, and for a reason that protects the thesis's rigor rather than excusing its absence.**

## 9.12 Placement map — where every artifact sits

| artifact | binding (where / what) | statement position | role in the arc |
|---|---|---|---|
| `flat_full_*` | n/a / matrix public | matrix disclosed | Part II baseline (pre-Merkle); not in the hierarchical arc |
| `flat_merkle_{presence,sort}` | n/a (K=1) | `{root,T}` | the monolithic pole; perfect-hiding baseline |
| `flat_merkle_grand_product` | n/a (K=1) | `{root,T}` | **control** — plain-product at K=1; the factorial's flat-grand-product cell |
| **plain-sort** | external / plaintext | partition disclosed | diagnosis + disclosure endpoint; cheapest, deterministic |
| **plain-product** | external / plaintext (`P_i` oracle) | partition computational-oracle | recursion bridge + control isolating surface/check |
| **committed-sort / plain-product** | external / commitment | partition hidden (reveal K) | the cure; equal-privacy non-recursive points |
| **recursion** (plain-product-inner) | in-circuit / witness | partition absent | perfect-hiding endpoint; the C-corner cost |
| recursive-sort | in-circuit / witness | partition absent | **control** (sub-arc); aggregation-cost isolator; off-frontier |
| Variant B *(unbuilt)* | external / plaintext + sub-matrix | partition + sub-matrices disclosed | most-disclosing gate-saver; attaches beside plain-sort |
| folding *(future)* | deferred / witness | partition absent | the empty P+V+C corner |

## 9.13 Refrains and honesty caveats (repeat throughout Ch 8-10)

- **Total work is conserved** — hierarchical never beats flat on total gates (~770–806k vs ~782k);
  the win is *parallelizability of the same work*, never less work.
- **K× parallelism is MEASURED** (`results/hier_*_iso.csv`: ~6.5× `plain-product`, ~4.7×
  `plain-sort` at N=3000 K=8) — the former #1 defense vulnerability, closed. Carry only the
  composition-assumption caveat (solo per-proof times; wall-clock = max segment + glue).
- **plain-product is motivated on surface/soundness, never on hiding** — inside recursion the partition is
  hidden either way.
- **"Negligible verifier cost" is conditional** — true off-chain at low K; at large K or on-chain it
  stops being negligible, and that boundary *is* the use-case mapping.
- **"Perfect hiding" is structural**, not IT-ZK — the SNARK's ZK is identical across all variants and
  is not a discriminator.
- **Keep the SNARK-ZK property (constant) rigidly distinct from statement-disclosure (varies)** —
  never write "plain-product adds more ZK"; plain-product's *statement* discloses less (§9.3.3).

### 9.14 The shape in one breath

**flat (no binding) → decompose (binding forced; dualism) → name the two poles (flat / recursion) →
walk the interior by *what is bound* (plain-sort discloses → plain-product shrinks the surface → committed hides) →
return to build recursion (binds in the witness; collapses everything; prover pays) → folding (defer
the cost).** Each arrow is one move across the statement–witness / binding-location axes; each variant
is the cheapest-or-necessary point at its rung; the O(K)-verifier "symptom" met at plain-sort is re-framed as
the bargain when recursion's prover bill lands; and the loop closes productively because the detour
manufactured the inner that recursion is built from.

*Session source: 2026-06-03 narrative working session. Supersedes the §6 open choice; consistent with
`FRONTIER_REFRAME.md` Part 2 (progress-line) and Part 4 (decisions C1–C6), `Thesis_Outline.md` Ch 8-10,
and `HIERARCHICAL_EXPLAINED.md` §9b/§14.5.*

---

# 10. THE PROTOCOL FLOW — prover, verifier, the artifacts, and how cheating is prevented

*Captured 2026-06-03. This is **background / implementation** material, not Ch 8-10 narrative —
it maps to **Ch 2** (SNARK pipeline, ACIR/VK/witness), **Ch 4** (the statement + threat model
§4.5), and **Ch 6** (implementation). It is kept here so the session's outputs stay together.
Everything below is grounded in the actual code: the `flat_merkle_sort` circuit, the harness
`pipeline/run.py`, the external verifier `pipeline/verify_hier.py`, and the recursion outer
`circuits/recursion`. Use it as the source for §2.5 / §4.5 / §6 and the soundness subsections
(§5.x, §9.3.3, §9.8). It answers two questions explicitly: the **threshold cheat** (§10.5) and
**"how does the verifier know the proof is of the correct computation, not a valid proof of some
other false program?"** (§10.6).*

## 10.1 The pipeline — five commands, five artifacts

`pipeline/run.py` runs exactly this sequence per circuit:

```
nargo compile                                   →  target/{name}.json    (circuit: ACIR + ABI)
bb write_vk  -b target/{name}.json -o vk        →  target/vk/vk          (verification key)
nargo execute                                   →  target/{name}.gz      (witness)
bb prove  -b {name}.json -w {name}.gz -k vk -o  →  target/proof/proof
                                                   target/proof/public_inputs
bb verify -k vk -p proof -i public_inputs       →  accept / reject (one bit)
```

The clean seam:
- **Prover side** needs circuit (`.json`) + witness (`.gz`) + VK → produces `proof` +
  `public_inputs`.
- **Verifier side** needs **only** VK + `proof` + `public_inputs` → outputs one bit. It never
  sees the witness.

`write_vk` runs **before and independently of any witness** — the VK is a property of the
*circuit*, not of any input. That fact is the whole answer to the "false program" question
(§10.6).

## 10.2 What each piece *means*

- **The circuit (`target/{name}.json`, from `nargo compile`).** `main.nr` compiled into **ACIR**
  — a *fixed* system of arithmetic constraints over the field — plus an **ABI** recording which
  inputs are `pub` vs private and their order. Once compiled it is frozen equations; every
  `assert(...)` becomes one or more of them. `bb gates` counts them.
- **The witness (`target/{name}.gz`, from `nargo execute`).** The **complete assignment of a
  value to every wire** — not just the declared private inputs (`cycle`, `edge_costs`,
  `siblings`, `path_bits`) but *every intermediate*: the `sorted` array, every Merkle `current`
  hash, the running `total_cost`, the boolean decomposition of the threshold comparison.
  `nargo execute` *runs* the circuit (incl. the unconstrained quicksort hint) to compute all of
  them. This is the secret the proof demonstrates knowledge of without revealing.
- **The verification key (`target/vk/vk`, from `bb write_vk`).** A **cryptographic commitment to
  the circuit's constraint system** — UltraHonk preprocesses the fixed ACIR into committed
  selector/permutation polynomials; the VK holds those commitments (+ circuit size, public-input
  count). A cryptographic fingerprint of *the exact equations*. Change one `assert`, recompile,
  the VK changes. This is the object that pins *which computation*.
- **The proof (`target/proof/proof`).** A constant-size (14 656 B in these runs) UltraHonk
  argument attesting: *"I know a witness satisfying every constraint of the circuit committed by
  this VK, consistent with these public inputs."* **Sound relative to the VK** and **bound to the
  public inputs** (both via the Fiat–Shamir transcript, which hashes the public inputs and the
  circuit commitments into the verifier's challenges).
- **The public inputs (`target/proof/public_inputs`).** A dump of the `pub` ABI values — for
  `flat_merkle_sort`, exactly **`root` and `threshold`**, 32 bytes each (`verify_hier.py` parses
  these 32-byte chunks back into ints). The values both parties agree on in the clear;
  everything else is hidden.

## 10.3 What the prover does / produces (concretely, `flat_merkle_sort`)

1. Off-circuit: load/solve a Hamiltonian cycle, read each edge cost from the matrix, build the N
   Merkle proofs (`siblings` + `path_bits`) against the committed `root` (Rust `merkle_builder`
   builds the tree; `format_inputs.py` writes `Prover.toml`).
2. `nargo execute` fills the witness: runs the sort, recomputes every Merkle hash chain,
   accumulates `total_cost`, and **evaluates every `assert`**. If any assert fails *here*, witness
   generation aborts — no witness, no proof. (Honest glue-logic violations die at this layer.)
3. `bb prove` turns the satisfying witness into `proof` + emits `public_inputs` (`root`,
   `threshold`).

Output to the world: `proof` + `public_inputs`. Nothing else.

## 10.4 What the verifier does / gets (two steps — the second is easy to forget)

1. **`bb verify -k vk -p proof -i public_inputs`** → accepts iff the proof is a valid UltraHonk
   argument *for the circuit committed by `vk`* *with those exact `public_inputs`*.
2. **Check the public inputs are the ones it agreed to.** `bb verify` proves validity *for
   whatever public inputs were supplied* — it does **not** know which `root`/`threshold` the
   verifier *wanted*. So the verifier must independently confirm `public_inputs ==
   (agreed_root, agreed_threshold)`. (`verify_hier.py` makes this explicit: step 1 is `bb verify`
   ×(K+1); step 2 is the equality cross-checks on the parsed dumps.)

The verifier gets **one bit** plus the assurance that *a qualifying cycle exists* — and learns
nothing about the cycle, edge costs, or matrix beyond `root` and `threshold`.

## 10.5 How each constraint group blocks a cheat (incl. the threshold cheat)

The statement is *"I know a Hamiltonian cycle whose edges, priced by the matrix committed in
`root`, sum to ≤ `threshold`."* Each group nails one clause:

- **GROUP 2 — permutation (can't fake a non-cycle).** `sorted = cycle.sort_via(...)`, then
  `assert(sorted[i] == i)`. A cheater would visit cheap nodes twice; blocked because `sorted`
  must equal `[0..N-1]` *and* `check_shuffle` proves `sorted` is a genuine rearrangement of
  `cycle` ⟹ `cycle` is exactly `{0,…,N-1}`, every node once. (Subsumes the range check.)
- **GROUP 3 — Merkle binding (can't fake edge costs)** — two sub-locks:
  - *(3b) path-to-root:* hash `edge_costs[i]` up through `DEPTH` Poseidon2 levels with the
    supplied `siblings`, `assert(current == root)`. `root` is a public input fixed by the
    verifier; Poseidon2 collision-resistance ⟹ no fake cost + fake siblings hash to the real
    `root`.
  - *(3a) leaf-index check:* collision-resistance alone is insufficient — a prover could present a
    *legitimate* proof for a *different* leaf carrying a conveniently small cost. So the circuit
    reconstructs the leaf index from `path_bits` and asserts it equals
    `from*N + to = cycle[i]*N + cycle[(i+1)%N]`, forcing each proof to be for *exactly the edge
    the cycle uses*. 3a + 3b together pin `edge_costs[i]` to the true committed entry.
- **GROUP 4 — threshold (the explicit cheat answer).** `total_cost += edge_costs[i]`, then
  `assert(total_cost <= threshold)`. **`total_cost` is not a free variable the prover can set
  small** — it is a *determined wire*, constrained to equal the sum of the `edge_costs`, each of
  which is pinned by GROUP 3. The prover has no freedom to "declare" a low cost: the only
  satisfying assignment uses the *real* costs, and the *real* sum is compared. If the true cycle
  cost exceeds `threshold`, the assert is unsatisfiable ⟹ `nargo execute` fails (or, for a
  hand-forged witness, `bb prove` cannot produce a verifying proof). The `u64` comparison
  compiles to a **range check on the difference** (64 boolean wires), so wraparound/overflow can't
  make a big number look small — the boolean decomposition only exists if the values are genuinely
  in range.

**Composition (the soundness story):** GROUP 2 ⟹ a real tour; GROUP 3 ⟹ the costs are the
*committed* costs of *that tour's* edges; GROUP 4 ⟹ those true costs sum within budget.
Knowledge-soundness of UltraHonk then gives: a verifying proof ⟹ the prover *knows* such a
witness ⟹ a real qualifying cycle exists.

## 10.6 The deep question — correct computation, not a valid proof of a *false* program

Two independent bindings plus one external trust anchor:

**(a) The proof is bound to the *circuit* — via the VK.** A SNARK proof is not a free-floating
"this is true" token: `bb prove` produces a proof *with respect to a specific constraint system*,
and `bb verify` checks it *against the VK*, which is the commitment to that system (§10.2). The
verification equation balances only when the proof was generated for **the exact circuit the VK
commits to**. A valid proof of some *other* program (one that skips GROUP 4, or asserts
`total_cost <= total_cost`) is a proof for a *different constraint system* ⟹ a *different VK* ⟹
fed to `bb verify` under the **honest TSP VK it fails.** The VK is what makes "valid" mean
"valid *of this computation*."

**(b) The proof is bound to the *public inputs* — via Fiat–Shamir.** `root` and `threshold` are
absorbed into the proof transcript, so a proof made for `(root₁, T₁)` will not verify if presented
with `(root₂, T₂)`. You cannot replay a proof for a lax threshold under a strict one.

**(c) The one piece the math does *not* give you — the trust anchor.** The VK is just bytes: it
certifies "*some* circuit," and the proof certifies "valid for the circuit of *this* VK." Nothing
cryptographic says *"this VK is the honest TSP circuit in `main.nr`."* That binding is the
**verifier's responsibility**, by exactly two honest routes:
  1. **Recompile and reproduce** — the verifier runs `nargo compile` + `bb write_vk` on the
     *open-source* circuit and uses *that* VK (deterministic build ⟹ reproduces the published VK).
     Now "VK = audited program" is *established*, not taken on faith.
  2. **Attested VK** — published/signed by a trust anchor (§4.3), and the verifier checks the
     attestation.
Likewise "`root` commits to the *real* matrix" is an external anchor (§4.3: authority signature,
oracle, timestamping, decommit-on-dispute) — the circuit proves consistency *with* `root`, never
that `root` is "true." (This is `FRONTIER_REFRAME.md` F2: trusted-code surface, not cryptographic
trust base.)

**The full chain a verifier relies on:** recompile the public circuit → reproduce the VK (binds
VK ↔ audited program) → `bb verify` (binds proof ↔ VK ↔ public inputs) → check the public inputs
are the agreed `(root, threshold)` → trust `root` via an external anchor. Cryptography covers the
middle links; the two ends (VK↔source, root↔matrix) are deliberate, named trust assumptions.

## 10.7 The two project-specific binding layers (where the variants differ)

Everything above is *one* proof. The decomposed variants add a layer binding *K+1* proofs to one
instance — the stitching tax made operational:

- **External binding (hierarchical plain-sort/plain-product/committed — `verify_hier*.py`).** Each segment proof and
  the glue proof verify *internally* with their own `bb verify`, but that never forces a shared
  instance. So the verifier runs **K+1 `bb verify` calls, then pure Field-equality cross-checks**
  on the parsed `public_inputs`: same `root` across all proofs; `glue.starts[i] ==
  sub_i.start_node`; `glue.partial_costs[i] == sub_i.partial_cost`; the partition chunks match.
  Deterministic integer comparisons on values `bb verify` already bound cryptographically — they
  *are* the binding, done verifier-side. The O(K)-verifier + bookkeeping symptoms.
- **In-circuit binding (recursion — `circuits/recursion`, `verify_recursion.py`).** The outer
  circuit calls `verify_honk_proof` on each of the K inner proofs **inside the circuit**, taking
  each inner's `public_inputs` as **witness** (`sub_pub` layout
  `[start, end, partial_cost, root, P_i, h_in, h_out, c, X]`), then re-runs the glue logic on
  those now-trusted private values. The cross-checks become *in-circuit asserts* (binding folded
  into one proof) and the inner public inputs never reach the outer surface (only `root, threshold`
  remain → structural hiding). The verifier runs **one `bb verify`, zero cross-checks** — the
  stitching tax collapsed, at ~704k gates/inner. This is §9.4.3's "faithful recombination" in code.

**Two-layer catch (validated in `tests/correctness/test_recursion.py`):** glue-logic cheats die at
`nargo execute` (the assert fails during witness generation); a tampered inner proof or VK
commitment dies at `bb prove`/`bb verify`. `key_hash` is non-binding (the VK commitments bind).

## 10.8 One-line mental model

The **VK** says *which equations*; the **witness** is a secret solution to them; the **proof**
says *"I have a solution and it agrees with these public inputs"*; **`bb verify`** checks that
against the VK; and *"is this the right equations and the right matrix?"* is answered **outside**
the math by recompiling the open circuit and anchoring `root`. The circuit's four assert-groups
are what make "a solution exists" mean "a real, in-budget, correctly-priced Hamiltonian cycle
exists" — and nothing weaker.

*Section source: 2026-06-03 protocol-flow walkthrough. Grounded in `circuits/flat_merkle_sort/src/main.nr`,
`pipeline/run.py`, `pipeline/verify_hier.py`, `circuits/recursion/src/main.nr`. Feeds Thesis_Outline
§2.5, §4.5, §6, and the soundness subsections §5.x / §9.3.3 / §9.8.*

---

# 11. THE MONOTONE FLOW (current recommended spine; §9's dilemma cold-open retained for comparison)

*Captured 2026-06-03 (late session). This **supersedes the ordering decision in §9** while keeping
all of §9's analyses. The change is only top-level order: §9 opened on the flat↔recursion dilemma
and deferred recursion's construction; §11 walks a single monotone line and reaches recursion as
the natural endpoint, with the dilemma demoted to an intro signpost + a derived synthesis. §9 is
kept for reference and for the deeper treatment of any analysis cited here. **Scope note:** per the
2026-06-03 decision, this flow ignores `flat_full_presence`, `flat_full_invperm`,
`flat_merkle_presence`, and Variant B; the in-scope set is `flat_full_pairwise`, `flat_full_sort`,
`flat_merkle_sort`, `flat_merkle_grand_product`, plain-sort, plain-product, committed-sort, committed-product, recursion
(plain-product-inner), recursive-sort (control), and folding (future).*

## 11.1 The root decision that tips monotone over the cold-open: the contribution is the *map*, not the variants

The cold-open (§9) and the monotone flow encode *different claims about what the thesis
contributes*. Resolving that is what settles the order:

- The variants use **standard techniques** (Merkle commitments, grand products, blinded
  commitments, in-circuit verification). "I invented hierarchical TSP ZK variants" is the **weak,
  exposed** claim — an examiner answers "those are known techniques applied to TSP."
- The **original, durable** contribution is the **framework**: (1) the **dualism** (decomposing a
  non-local problem gives *no* ZK speedup, only parallelism — a negative result with a structural
  explanation); (2) the **stitching tax** (recombining K decomposed proofs is one artifact, three
  coupled symptoms); (3) the **frontier** (the pick-two triangle; flat/hierarchical/recursion are
  *points*, folding the predicted empty corner); (4) the **methodology** (controlled, equal-privacy
  comparison). **The variants are evidence that instantiates the map.**

The cold-open *spotlights the invention of hierarchical* (the weak claim); the monotone flow
*foregrounds the framework* (the strong claim) and lets every variant — flat, hierarchical,
recursion alike — be a point of one map. That is why monotone wins here: it matches the contribution
the thesis can actually defend. (Corollary already drawn for the title: lead with the framework —
"stitching tax / cost–privacy frontier" — not with "novel constructions".)

## 11.2 Variant roles (the regroup — the in-scope set, by job)

Not "many variants" — a small set with three distinct jobs:

| Role | In-scope variants | Why it exists |
|---|---|---|
| **Baselines** (Part II, Ch 5–7) | `flat_full_pairwise`, `flat_full_sort`, `flat_merkle_sort` | Establish the problem, the four-group structure, the permutation-check axis, and the public→committed matrix move. `flat_merkle_sort` is carried into Part III as the **K=1 monolithic endpoint**. |
| **Frontier points** (Part III — *the contribution*) | plain-sort, plain-product, committed-sort, committed-product, recursion(plain-product-inner), [`flat_merkle_sort` as K=1], [folding = future] | The points that **instantiate the map** along the stitching-tax progression. |
| **Instrumental controls** (Ch 10, for rigor) | `flat_merkle_grand_product` (= plain-product at K=1), recursive-sort (plain-sort-inner) | Exist **only to de-confound comparisons** (mechanism vs aggregation in the 2×2 factorial). **Off the frontier figure.** |

## 11.3 The monotone order, step by step — and the reason for *every* position

**The organizing principle (this is the deep reason for the whole ordering):** the sequence is a
**controlled walk** — *each consecutive step changes exactly one design dimension.* The order is the
apples-to-apples discipline turned into a narrative: every transition isolates one variable, so the
reader can attribute each cost/privacy delta to a single cause. State this once up front; it justifies
every placement below.

The dimensions, and the single one that moves at each step:

| # | from → to | the ONE thing that changes | what it isolates / why it's here |
|---|---|---|---|
| 1 | — → **flat_full_pairwise** | (the starting point) | The simplest correct statement: public matrix, O(N²) **pairwise** permutation check. Establishes the **four-group structure** (range / permutation / edge-cost / threshold). Naivest permutation check = the baseline to improve. |
| 2 | flat_full_pairwise → **flat_full_sort** | permutation check: pairwise → **sort** (O(N²)→O(N)) | Public matrix held fixed ⟹ isolates the **permutation-check cost axis**. Why second: it's the one-variable improvement of step 1. |
| 3 | flat_full_sort → **flat_merkle_sort** | matrix representation: **public → committed** (root) | Sort held fixed ⟹ isolates the **cost of committing the matrix** (the O(N·log N) Merkle overhead vs the O(N²) public-input cost; the crossover). Why third: it's the privacy-relevant move (matrix hidden, surface = `{root,T}`), and it produces the **monolithic perfect-hiding baseline** Part III builds on. |
| 4 | flat_merkle_sort → **flat_merkle_grand_product** | permutation mechanism: **sort → grand-product + FS** | Committed matrix + surface `{root,T}` held fixed, zero privacy delta ⟹ isolates the **permutation-mechanism cost** (the witness-time inversion). **Instrumental:** it is plain-product collapsed to K=1, introduced here as the flat-row **control** for the Ch 10 factorial. Why here: it completes the permutation-mechanism study at K=1 *before* decomposition adds the structure variable. |
| — | **(Ch 8: the framework)** | — | Between the flat study and the points, declare the contribution: **dualism** (decompose ⟹ no speedup, only parallelism) → **stitching tax** (one artifact, three symptoms; two decisions: *where* binding lives × *what* it binds) → the **pick-two triangle**. The points in Ch 9 are read against this. |
| 5 | flat_merkle_sort → **decomposition** | structure: **monolithic → K segments + binding** | The move that buys parallelism (dualism: no gate savings). Binding forced ⟹ the organizing question for all that follows: *where does binding live (external / in-circuit), what does it bind (plaintext / commitment / witness)?* Introduced once, shared. |
| 6 | decomposition → **plain-sort** | binding realized: **external, plaintext, sort** | The *simplest* binding (external + plaintext) ⟹ exhibits the **stitching tax raw** (partition disclosed, O(K) verifier, bookkeeping). Cheapest total gates, deterministic. Why first among hierarchical: minimal external binding, the **diagnosis** + the **disclosure-regime** point — show the tax plainly before optimizing. |
| 7 | plain-sort → **plain-product** | partition mechanism/surface: **sort/O(M) → grand-product+FS/O(1)** | External + plaintext held fixed ⟹ isolates the **surface/check refinement**. Honestly **not cheaper** (relocates O(N) into the segments). Motivated on **surface + soundness + the recursion bridge**, *never on hiding* (still leaks, now via the `P_i` oracle). Why second: it is the one-variable efficiency move on plain-sort, and the segment recursion will later reuse. |
| 8 | plain-product → **committed-product** (and plain-sort → **committed-sort**) | what is bound: **plaintext → blinded commitment** | Structure/mechanism held fixed ⟹ isolates the **blinding**. Closes the leak (`C_i`, reveals only K); bookkeeping becomes ZK. **Equal-privacy finding:** committed-sort and committed-product reach the *same* rung, differing only in glue cost — so present them together; the finding *needs* both. After this, **only the O(K)-verifier symptom remains.** Why before recursion: monotone — committed removes *one* symptom (the leak); recursion then removes the *last* (the verifier). Jumping plain-product→recursion would remove two at once and destroy the clean attribution. |
| 9 | committed → **recursion (plain-product-inner)** | where binding lives: **external → in-circuit (witness)** | The only binding that removes the **last** symptom (O(K) verifier) *and* restores structural hiding — the **faithful recombination** (§9.4.3): verify the K segment proofs in-circuit, their public inputs become witness, surface → `{root,T}`. Built on the **plain-product** segment (its O(1) surface keeps the outer segment-size-independent — plain-product's deferred payoff). Prover pays **704k×K**. Why last among built variants: it is the endpoint the progression converges on; reaching it here makes the **flat↔recursion dilemma a *derived synthesis*** (§11.5). |
| 9c | recursion(plain-product) ↔ **recursive-sort** | the inner: **plain-product → plain-sort** (grand-product → sort) | **Instrumental control**, introduced *with* recursion for the Ch 10 factorial: recurse on the plain-sort (sort) segment to hold the mechanism matched to flat, isolating **aggregation cost** from mechanism. Off-frontier. Inside recursion this is a **soundness/surface** trade, *not* hiding (both partitions are witness either way). |
| 10 | recursion → **folding** | when binding happens: **eager → deferred** | The predicted **empty corner** (P+V+C): defers the in-circuit verification, removing recursion's prover tax. Future work — a *different backend*, so building it would break the controlled single-backend comparison (§9.11). Closes the map by naming what would break the triangle. |

**Reading the table as a chain:** steps 1→4 walk the *flat* study, changing one of {permutation check, matrix representation, permutation mechanism} at a time. Step 5 introduces the *structure* variable (decomposition). Steps 6→9 walk the *binding* decisions — first *what is bound* held external (A plaintext → plain-product surface-refined → committed blinded), then *where binding lives* (committed external → recursion in-circuit). Step 10 changes *when*. Every link is one variable; the narrative order **is** the controlled experiment.

## 11.4 The three-chapter mapping

- **Ch 8 — declare the framework (the contribution).** Dualism → stitching tax → pick-two triangle.
- **Ch 9 — walk the points (monotone evidence).** `flat_merkle_sort` (K=1 endpoint) → decomposition →
  plain-sort → plain-product → committed-sort/plain-product → recursion → folding. Each a worked construction; each transition the
  one-variable step from §11.3.
- **Ch 10 — measure + compare.** The frontier figure (triangle, real coordinates); the equal-privacy
  slices; the **2×2 factorial** {flat, recursive} × {sort, grand-product} — *here*
  `flat_merkle_grand_product` and recursive-sort do their only job (de-confounding), explicitly flagged
  as controls. (Reuses §9.7's factorial reading and §9.8's reveal verbatim.)
- *(Part II / Ch 5–7 carries the flat study — steps 1–4 — as the empirical baseline.)*

## 11.5 Where the dilemma goes (it is *not* lost — it is relocated and strengthened)

The flat↔recursion dilemma does not open the chapter; it lands in two stronger places:

1. **An intro signpost (chapter intro / Ch 1):** one paragraph — *"this chapter traverses a space
   whose extremes are flat and recursion; between them lies a family that trades the verifier for
   cheapness."* No construction, no deferral, no asserted cost. Pure orientation.
2. **A derived synthesis (when recursion lands, end of Ch 9 / opening of Ch 10):** having *built* both
   endpoints — *"recursion recovered flat's succinct verifier and structural hiding, but at a prover
   cost flat never paid; flat and recursion are the two perfect-hiding poles, and the hierarchical
   family is what lives between them."* This is where the **pick-two triangle** crystallizes and the
   **prover/verifier reveal** (§9.8) fires — now as *earned* results, not front-loaded assertions.

A dilemma is a better punchline than a teaser: as a cold-open it is an unexplained assertion; as a
synthesis it is a result the reader watched you derive. (This also makes §9.10's non-circularity
defense largely unnecessary — there is no result-first/build-last loop to defend.)

## 11.6 What carries over from §9 unchanged (do not rewrite these — reuse them)

The monotone frame changes *order*, not *analysis*. These §9 pieces are reused as-is:
- **§9.3.2 P/V/C** and the triangle — the cost geometry the synthesis (§11.5) crystallizes.
- **§9.3.3 verification→ZK / statement–witness boundary** — the precise lens for *what is bound*
  (steps 6–9); the guardrails (never "plain-product adds more ZK") still bind.
- **§9.4.3 recursion = the natural recombination** — now the *synthesis line* at step 9, not a deferred
  promise.
- **§9.6.2 why plain-sort/plain-product before committed** (diagnosis-before-cure, de-confounding, plain-sort as disclosure
  endpoint, plain-product as recursion bridge) — these *are* the step-6/7/8 reasons, restated in §11.3.
- **§9.7 the recursion sub-arc + 2×2 factorial** — step 9c + Ch 10; plain-product first (shipped), recursive-sort
  the fairness control.
- **§9.8 the prover/verifier reveal** — fires at the synthesis (§11.5); seed it at step 6 (plain-sort's O(K)
  verifier), pay it off at step 9.
- **§9.12 placement map** and **§9.13 refrains/caveats** — unchanged (total work conserved; measured
  parallelism with the composition caveat; plain-product never motivated on hiding; structural ≠ IT-ZK).

## 11.7 The shape in one breath (monotone)

**flat_full_pairwise → flat_full_sort** (change the permutation check) **→ flat_merkle_sort** (commit
the matrix) **→ flat_merkle_grand_product** (change the mechanism — a K=1 control) **→ [Ch 8: dualism +
stitching tax + triangle] → decompose** (add structure; binding forced) **→ plain-sort** (external/plaintext —
the tax, raw) **→ plain-product** (refine the surface/check; the recursion bridge) **→ committed-sort/plain-product** (blind it
— close the leak) **→ recursion** (bind in-circuit — the faithful recombination; the last symptom falls;
prover pays) **→ folding** (defer the cost — the empty corner). One variable per step; the framework is
the claim; the variants are the evidence; the dilemma is the synthesis, not the opening.

*Section source: 2026-06-03 (late session) reorganization. Supersedes §9's ordering only; reuses §9's
analyses. Scoped to the in-scope variant set (presence/invperm/merkle_presence/B excluded). Feeds
`Thesis_Outline.md` Ch 8-10 and the title decision (framework-forward).*
