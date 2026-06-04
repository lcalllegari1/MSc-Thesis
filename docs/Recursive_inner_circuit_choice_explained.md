# Recursion: why the inner proof uses the A++ sub-circuit (not A)

**Question.** In the recursive experiment the inner proofs are produced from
`hierarchical_segment_fs` (the Variant A++ sub-circuit). Since recursion hides
everything anyway — the inner proof's public inputs become *witness* of the outer
— the leakage that distinguishes A from A++ no longer matters. So what is the
motivation for choosing A++ as the inner rather than A?

This note records the reasoning so it can be cited later.

---

## Privacy is *not* the motivation

Inside recursion, both A's `sorted_nodes[M]` and A++'s `P_i` / chain anchors
become **witness of the outer circuit**, so the final verifier sees neither —
**perfect hiding either way**. The A-vs-A++ *leakage* distinction, which is the
entire reason A++ exists as a standalone variant, genuinely evaporates. So *"I
used A++ because it hides the partition"* would be a **bad** justification.

**One precision.** With the A++ inner we actually use, the Fiat-Shamir /
grand-product machinery is **not redundant within that design** — it is still
load-bearing soundness. The outer receives only `P_i` (not the raw node list),
so it is *forced* to check the partition via `∏ P_i == ∏ (X + j)`, which needs
the sound Fiat-Shamir challenge `X`. The redundancy only materialises if you
**also switch the inner to A**: A exposes the node set, so the outer could
instead sort the concatenation and assert `== [0..N-1]`, dropping Fiat-Shamir
entirely. So *"leakage gone ⇒ A++'s gadget is pointless"* requires that second
step; it is not automatic.

## The two motivations that *do* hold

**1. Controlled comparison (methodological).** Recursion's role on the frontier
is *the perfect-hiding successor to A++*. For the recursion row to mean *"what
does it cost to take A++ and aggregate it into perfect hiding,"* the inner must
be exactly the A++ segment — same circuit, same proven statement. Then the
measured delta between the A++ row and the recursion row is **purely the
aggregation cost**, with no confounds. Use an A inner and you have changed two
things at once (different sub-circuit *and* recursion), muddying the comparison.

**2. A++'s O(1) public surface is the better recursion target (technical).** This
survives even after privacy drops out. The recursive verifier must **absorb the
inner proof's public inputs in-circuit** (transcript + public-input
contribution), so its cost carries a term linear in the number of inner public
inputs:

- A++ inner exposes **9 fields, regardless of M**.
- A inner exposes **M + 4 = O(N/K)** (e.g. 244 at N=480, K=2).

So A++ keeps the outer's verification cost **~segment-size-independent** — exactly
the *"outer gates flat ~1.474M across N=48→480"* we measured. With an A inner the
outer carries an extra `O(M)·K ≈ O(N)` absorption term, and that clean "constant
outer" result partially breaks. In other words: the FS / grand-product gadget,
no longer needed for hiding inside recursion, now **earns its keep by minimising
the recursive verifier's public-input load.** Same gadget, new master.

(Cost is otherwise ~identical either way — the K in-circuit verifications at
~700k gates each dominate; sort-vs-grand-product in the glue is noise against
that. So the choice is about *control* + the *O(1) surface*, not raw cost.)

## The corollary — state it as a result, not a worry

> Recursion neutralises the A→A++ privacy upgrade: the partition disclosure A++
> was engineered to avoid is hidden anyway once segments become witness.
> Consequently an **A-style (or stripped) inner with a deterministic
> sort-partition in the outer is arguably the more *natural* recursive design** —
> it trades A++'s probabilistic Fiat-Shamir / Schwartz-Zippel soundness for a
> deterministic check, and recursion erases A's only drawback (public partition).
> We benchmark A++ segments for a controlled comparison with the A++ row and
> because their O(1) public surface keeps the recursive verification
> segment-size-independent.

This shows the dualism understood all the way down: A++'s gadget and recursion's
in-circuit verifier are two routes to the same hidden partition, and once you
have one, the other becomes optional.

## Committee-ready summary

> **Not for privacy** — recursion hides the partition regardless of inner. A++
> inner is chosen for (a) a *ceteris paribus* comparison against the A++ benchmark
> row, isolating the aggregation cost, and (b) its O(1) public surface, which
> keeps the recursive verifier's cost independent of segment size (visible as the
> flat ~1.474M-gate outer). An A-style inner is a valid — arguably more natural —
> alternative that drops Fiat-Shamir at the price of an O(M) public surface.

## Quantifying it: the A-inner variant

To turn the argument into a *number*, the repository also contains a separate
**A-inner recursion** variant that verifies Variant A sub-proofs in-circuit and
does the sort-based partition in the outer:

- Circuits: `tests/recursion_micro/exp1_single_segment_a`,
  `tests/recursion_micro/exp2_k_segments_a`.
- Driver: `tests/recursion_micro/run_recursion_a.py`.
- Comparison: `tests/recursion_micro/compare_inner.py` runs the A++-inner and
  A-inner variants on the *same* instance (same N, K, seed) and reports the
  per-metric difference — most importantly the outer gate count, which exposes
  the `O(M)` public-input penalty argued above.

See `HOWTO.md` (recursion section) for how to run them.
