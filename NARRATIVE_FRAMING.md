# Narrative Framing — The Perfect-Hiding Dilemma and the Hierarchical Escape

*Reference note locking in the "flat vs recursion, then hierarchical as the
escape" framing for Chapters 8-10. Captured 2026-05-31. This is a narrative /
positioning note, not new results — every claim traces to findings already in
`FRONTIER_REFRAME.md`, `HIERARCHICAL_EXPLAINED.md`, and the recursion
micro-benchmarks. Use it as the starting point when drafting the variant chapters.*

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
That is exactly the hierarchical family (A / A++ / committed-A / committed-A++):
K independent segment proofs + a glue proof, bound by verifier-side cross-checks
instead of an in-circuit verifier.

The pick-two triangle, now with the third corner:

| | parallel + low mem | O(1) verifier | low total cost |
|---|:--:|:--:|:--:|
| flat | ✗ | ✓ | ✓ |
| recursion | ✓ | ✓ | ✗ |
| **hierarchical (A/A++/committed-*)** | ✓ | ✗ | ✓ |
| folding (future) | ✓ | ✓ | ✓ |

The hierarchical family combines **flat's low total cost + recursion's parallelism**.
That is the "best of both worlds" — but ONLY on those two axes, and it is bought
with two prices, which must be named every time the claim is made.

---

## 3. The honest correction to "best of both worlds"

It is a **third corner of a triangle, not a dominating reconciliation.** The two
prices:

1. **O(K) verifier** — K+1 proofs, so `proof_bytes` and `verify_s` grow ~K (the
   binding-tax symptom that only recursion/folding remove).
2. **Privacy relaxation** — drops from structural hiding to: disclosed (A),
   computational-with-confirmation-oracle (A++), or computational + reveals-K
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
binding-tax / privacy-ladder story, and it motivates each later step:

1. **Perfect hiding, two ways** — flat (monolithic) vs recursion (decompose + bind
   *in-circuit*). The decomposition buys parallelism; the in-circuit binding costs
   704k*K.
2. **The question** — keep the decomposition, bind **externally** (cheap)? -> A / A++.
3. **The catch = the binding tax** — external binding leaks the partition (+ O(K)
   verifier + bookkeeping). This is the dualism made concrete: decomposition gives
   no ZK speedup, only redistribution; the binding removed from the circuit
   reappears as a leak.
4. **The fix** — committed-A/A++ close the leak (computational hiding, reveals only
   K), recovering near-flat privacy *without* recursion's tax.
5. **The frontier** — folding as the missing all-three corner (future work).

**Dependency to handle in the ordering:** recursion is *built from* the hierarchical
segments (it recurses on the A++ sub-circuits), so the decomposition concept must be
introduced before/with recursion. Clean fix: present decomposition up front as
shared, and frame the distinction as **where the binding lives** —
in-circuit (recursion, expensive) vs external (hierarchical, cheap-but-leaky).

---

## 5. Honesty caveats to carry while selling it

- **K× parallelism is still *projected***, not measured one-node-per-segment (the
  isolation benchmark is the pending empirical gap). Say "projected"/"estimated from
  circuit-size ratios" when selling recursion's or hierarchical's parallelism, or run
  the isolation benchmark to make it real. This is the claim most likely to draw fire.
- **Total work is conserved (the dualism).** "Best of both" must NOT imply
  hierarchical beats flat on total gates — it does not (~770-806k vs flat's ~782k).
  The win is *parallelizability of the same work*, not less work.
- **"Perfect hiding" of flat/recursion is structural**, not information-theoretic ZK
  (the SNARK's ZK is identical across all variants and is not a discriminator). It
  means the public surface carries no partition info.

---

## 6. The open narrative choice (decide at drafting time)

Two viable spines for Chapters 8-10:

- **(A) Perfect-hiding dilemma first** (this note): flat vs recursion -> escape via
  decomposition -> binding tax -> committed cure -> folding. Vivid hook; sets up a
  true cost/parallelism dilemma; recommended as the *opening*.
- **(B) Privacy progression first** (current `FRONTIER_REFRAME.md` Part 2): B -> A ->
  A++ -> committed -> recursion/flat, each step removing one binding-tax symptom.
  Monotone; matches the documented "binding tax as second structural result."

They are compatible — (A) is an entry point, (B) is the systematic backbone.
**Recommendation:** open with (A) for the hook, then settle into (B)'s progression
for the systematic treatment. Reconcile the two in `FRONTIER_REFRAME.md` when the
chapter structure is fixed.

---

*Related: `FRONTIER_REFRAME.md` (pick-two triangle F4, binding tax, privacy ladder),
`HIERARCHICAL_EXPLAINED.md` §9b/§14.5 (committed variants, privacy classes),
`FIGURES_AND_METRICS.md` (how to plot the frontier), `Thesis_Outline.md` Ch 8-10,
`project_recursion_experiment` memory (the 704k*K numbers).*
