# Recursion: why the inner proof uses the plain-product sub-circuit (not plain-sort)

**Question.** In the recursive experiment the inner proofs are produced from
`hierarchical_segment_fs` (the plain-product sub-circuit). Since recursion hides
everything anyway — the inner proof's public inputs become *witness* of the outer
— the leakage that distinguishes plain-sort from plain-product no longer matters. So what is the
motivation for choosing plain-product as the inner rather than plain-sort?

This note records the reasoning so it can be cited later.

---

## Privacy is *not* the motivation

Inside recursion, both plain-sort's `sorted_nodes[M]` and plain-product's `P_i` / chain anchors
become **witness of the outer circuit**, so the final verifier sees neither —
**perfect hiding either way**. The plain-sort-vs-plain-product *leakage* distinction, which is the
entire reason plain-product exists as a standalone variant, genuinely evaporates. So *"I
used plain-product because it hides the partition"* would be a **bad** justification.

**One precision.** With the plain-product inner we actually use, the Fiat-Shamir /
grand-product machinery is **not redundant within that design** — it is still
load-bearing soundness. The outer receives only `P_i` (not the raw node list),
so it is *forced* to check the partition via `∏ P_i == ∏ (X + j)`, which needs
the sound Fiat-Shamir challenge `X`. The redundancy only materialises if you
**also switch the inner to plain-sort**: plain-sort exposes the node set, so the outer could
instead sort the concatenation and assert `== [0..N-1]`, dropping Fiat-Shamir
entirely. So *"leakage gone ⇒ plain-product's gadget is pointless"* requires that second
step; it is not automatic.

## The two motivations that *do* hold

**1. Controlled comparison (methodological).** Recursion's role on the frontier
is *the perfect-hiding successor to plain-product*. For the recursion row to mean *"what
does it cost to take plain-product and aggregate it into perfect hiding,"* the inner must
be exactly the plain-product segment — same circuit, same proven statement. Then the
measured delta between the plain-product row and the recursion row is **purely the
aggregation cost**, with no confounds. Use a plain-sort inner and you have changed two
things at once (different sub-circuit *and* recursion), muddying the comparison.

**2. plain-product's O(1) public surface is the better recursion target (technical).** This
survives even after privacy drops out. The recursive verifier must **absorb the
inner proof's public inputs in-circuit** (transcript + public-input
contribution), so its cost carries a term linear in the number of inner public
inputs:

- plain-product inner exposes **9 fields, regardless of M**.
- plain-sort inner exposes **M + 4 = O(N/K)** (e.g. 244 at N=480, K=2).

So plain-product keeps the outer's verification cost **~segment-size-independent** — exactly
the *"outer gates flat ~1.474M across N=48→480"* we measured. With a plain-sort inner the
outer carries an extra `O(M)·K ≈ O(N)` absorption term, and that clean "constant
outer" result partially breaks. In other words: the FS / grand-product gadget,
no longer needed for hiding inside recursion, now **earns its keep by minimising
the recursive verifier's public-input load.** Same gadget, new master.

(Cost is otherwise ~identical either way — the K in-circuit verifications at
~700k gates each dominate; sort-vs-grand-product in the glue is noise against
that. So the choice is about *control* + the *O(1) surface*, not raw cost.)

## The corollary — state it as a result, not a worry

> Recursion neutralises the A→plain-product privacy upgrade: the partition disclosure plain-product
> was engineered to avoid is hidden anyway once segments become witness.
> Consequently an **plain-sort-style (or stripped) inner with a deterministic
> sort-partition in the outer is arguably the more *natural* recursive design** —
> it trades plain-product's probabilistic Fiat-Shamir / Schwartz-Zippel soundness for a
> deterministic check, and recursion erases plain-sort's only drawback (public partition).
> We benchmark plain-product segments for a controlled comparison with the plain-product row and
> because their O(1) public surface keeps the recursive verification
> segment-size-independent.

This shows the dualism understood all the way down: plain-product's gadget and recursion's
in-circuit verifier are two routes to the same hidden partition, and once you
have one, the other becomes optional.

## Committee-ready summary

> **Not for privacy** — recursion hides the partition regardless of inner. plain-product
> inner is chosen for (a) a *ceteris paribus* comparison against the plain-product benchmark
> row, isolating the aggregation cost, and (b) its O(1) public surface, which
> keeps the recursive verifier's cost independent of segment size (visible as the
> flat ~1.474M-gate outer). An plain-sort-style inner is a valid — arguably more natural —
> alternative that drops Fiat-Shamir at the price of an O(M) public surface.

## Quantifying it: the plain-sort-inner variant

To turn the argument into a *number*, the repository also contains a separate
**plain-sort-inner recursion** variant that verifies plain-sort sub-proofs in-circuit and
does the sort-based partition in the outer:

- Circuits: `tests/recursion_micro/exp1_single_segment_a`,
  `tests/recursion_micro/exp2_k_segments_a`.
- Driver: `tests/recursion_micro/run_recursion_a.py`.
- Comparison: `tests/recursion_micro/compare_inner.py` runs the plain-product-inner and
  plain-sort-inner variants on the *same* instance (same N, K, seed) and reports the
  per-metric difference — most importantly the outer gate count, which exposes
  the `O(M)` public-input penalty argued above.

See `HOWTO.md` (recursion section) for how to run them.
