#set page(paper: "a4", margin: 2.5cm, numbering: "1")
#set par(justify: true, leading: 0.8em, spacing: 0.8em, first-line-indent: 1em)
#set text(size: 12pt)
#set heading(numbering: "1.")

#set text(font: "New Computer Modern")

#show heading: set text(font: "New Computer Modern Sans")
#show heading: set block(below: 1em)

#align(center)[
  #text(size: 16pt, weight: "bold", font: "New Computer Modern Sans")[Zero-Knowledge Proofs for TSP]
]

#v(3em)

#set enum(indent: 10pt)

= Brief Recap of the Circuit Structure

For our specific problem, we need the following logic to perform the verification:
#v(10pt)
1. Permutation Check (Each node of the graph must appear exactly once in the cycle).
2. Edge Cost Check (The cost of an edge is retrieved through a lookup on the public/committed cost matrix and aggregated in a variable that keeps track of the cycle cost).
3. Threshold Check (The computed cost is checked against the public threshold $T$).
#v(10pt)
Compared to the last draft, I removed the range check because a successful permutation check already covers it. Nevertheless, for some implementations the way in which the permutation check is performed _requires_ that range check to be explicit, but I considered it as a part _within_ it (e.g. the first attempt was pairwise distinctness + _range_, but as soon as we use a sort-based or grand-product-based permutation check, range is not needed and already covered).  

= The Flat Baseline

Single monolithic proof for the entire instance, we only work on different implementations over two axes:
#v(10pt)
1. How cost matrix is supplied: public input vs. committed (Merkle Tree)
2. How the permutation check is implemented: sort, grand-product are the focus, other implementations are considered for completeness and to show the progression in the logic (naive pairwise distinctness, presence, inverse map)
#v(10pt)

The important result is Merkle Commitment of cost matrix + sort and grand-product permutation checks. This is our baseline. 

The choice of the Merkle Commitment is natural because it reduces the public input surface from $O(N^2)$ matrix entries to $O(1)$ Merkle root, at the cost of more complex in-circuit verification, which becomes a Merkle path verification as opposed to a simple lookup into a matrix (still worth however).

The choice of the permutation check is not so much about what's better but rather what can be exported/adapted to hierarchical and recursive approaches, so that we have a fair comparison. The progression and the decision process will be detailed and explained in the thesis.

== The Problem

The bottleneck is that everything on the prover side grows with $N$. At some point the proof will take too much memory to fit in a single machine. This is what motivates the other approaches in the thesis: hierarchical and recursive, both different ways of applying _decomposition_ to zero-knowledge.

== The evidence

We will consider many metrics for our comparison, but the crucial ones are _circuit size_, _prove time_, _peak memory_. I extended the benchmarks to include bigger instances. Now we go up to 1000 nodes for intra-comparisons of flat approaches, and up to as many nodes as my laptop can handle for Merkle + sort and grand-product, so that we get to the point where such proofs are no longer feasible. We got to 4000 nodes with Merkle sort, and 3000 with Merkle grand-product. 

#figure(
  image("flat.png"),
  caption: [Flat approaches up to 1000 nodes.]
)

I included the time to generate the witness because it's one of the only metrics in which a significant difference is observed between Merkle sort and grand-product, which can be explained by diving deep into the circuit, and I think it's a good thing to include in the thesis. The thesis will also include other metrics where relevant, as proof size and verification time.

The plots for bigger instances are shown in the next sections when they become relevant for comparison with the decomposition approaches: hierarchical and recursive.

= Hierarchical Approaches

Instead of a single proof, we use $K$, each one dealing with $M = N / K$ nodes. For simplicity we considered $K = 2, 4, 8$ and appropriate values of $N$ that are all multiples of those values of $K$, to ensure "clean" numbers. But this does not bring any loss of generality. In the case where we don't have multiples, we will simply have one of the segments that has a different number of nodes, with no changes in the logic.

To derive a hierarchical approach, before the standard "recursion", we temporarily forgot about zero-knowledge and focused on how to perform decomposed verification. This led to 2 different implementations that allow for verification, but that are not zero-knowledge and that leak information we would like to remain private. At first glance, they seem to be out of scope due to the leaking. But they are the natural starting point, and they will become even more useful as the inner mechanism for the recursive approach. They come from using sort and grand-product permutation check. Both provide $K + 1$ proofs. $K$ proofs for $K$ segments, and $1$ additional proof I called "the glue". The segment proofs are independent $M$-nodes proofs, and they prove each segment is honest w.r.t. public information of that segment. The glue takes those $K$ public summaries, considers the "joins" of each segments (the boundary edges), and makes sure they are about the same instance. The glue also performs those global checks (permutation, threshold). Then it will be enough to cross-check those $K+1$ proofs to make sure they are consistent with each other. This cross-check is external to the proofs, and is simply a set of equality checks between the proofs that ties them together. 

The two implementation only differ in the permutation check they use. But this has significant consequences.

#v(10pt)
1. *plain-sort*: permutation check remains a sort, but for this reason it must be enforced at the glue level, because the segment only know about their nodes. This means that the permutation check cannot be distributed to the segments. The only work that is distributed is the edge retrieval and verification of the edges within each segment. This means that each segment has to publish the nodes it deals with (sorted, not in cycle order, but still disclosed) for the glue to be able to put pieces back together. And in this variant they are published in _plain text_, hence the name.
2. *plain-product*: permutation check is a grand-product, which means that segments can produce their partial product with their nodes, and the glue only performs $K$ multiplications of this products + the RHS to ensure multiset equality. The benefit is that now permutation check work is distributed across segments. Drawback is that soundness of permutation is not deterministic as in the sort, but probabilistic based on a challenge and on Schwartz-Zippel. The challenge is computed using Fiat-Shamir on the cycle order, so that the cycle cannot be changed after it has been fixed without changing the challenge as well. Additional advantage is that the public surface of the segments is constant and $M$-independent. In the sort we published nodes of a segment for the glue to take in. Here we just publish the partial product, so the surface is smaller. This will be a crucial reason that justifies using this as the inner mechanism in the recursive approach, to obtain better results. The cost is obviously the probabilistic nature of the grand-product. But the size of the field makes the probability of cheating very low.
#v(10pt)

Both approaches still need to publish start and end nodes of each segments, so that the glue can compute the actual boundaries, retrieve their cost, check them, and aggregate all costs to check against the threshold.

Crucially, they both leak information. And they both require the verifier to check $K+1$ proofs + cross-check for consistency. Cross-check is trivial and fast, but $K+1$ proofs means that we have $(K + 1) dot "proof size"$, which weakens succinctness: each proof is still succinct in $N$, but the total verifier cost now grows linearly in $K$. Still manageable, but it needs an explanation. The most important thing is that this allows for breaking the memory barrier. Now we can verify bigger instances, because by dividing in segments we reduce single-segment prove time and memory. Also, since segments are independent, we now can prove and verify in parallel, which can contribute to big speed-ups.

Committed variants of both are considered: 

#v(10pt)
1. *committed-sort*
2. *committed-prod*
#v(10pt)

They try to fix the leak by using the commitment comparison Martin suggested. Instead of publishing values about the cycle, publish a commitment. The glue takes those values as witness, keeping them private, and then internally recomputes the commitment and checks they are consistent. This way the segments only publish commitments, and the glue checks against them. This essentially makes the two hierarchical variants comparable with the flat approach in the sense that they both hide everything, but the hiding of the hierarchical approach is only computational and depends on the Poseidon2 hash function. It can be made unconditional using Pedersen Commitments, but EC operations would make this very expensive in-circuit. It's a trade-off worth noting I think. I think it's still a valuable comparison to have.

So the hierarchical approaches up to now make the verifier pay, in the sense that it has multiple proofs to verify. The reason is that the stitching of segments is enforced externally. The prover gains parallelism (or concurrent proving at least) and the ability of handling bigger instances by decomposing them. The crucial fact is that decomposition does not reduce the amount of work. It distributes it across proofs.

The other possibility is to use recursion. This solves all the problems at the verifier side, but comes with greater costs for the prover. The recursive approach simply takes the segment proofs as inner proofs to verify in-circuit. The prover still needs to prove $K$ segments + the outer circuit, but since the latter internally verifies the $K$ proofs, the verifier only needs to verify the outer proof. 

Recursion has a constant overhead due to in-circuit verification, but the behavior is much more stable, which means there is a point where it becomes competitive with the flat approach, and this competitiveness is primarily in memory rather than in speed. The inner proofs use the mechanisms we already built earlier, plain-sort and plain-product. They now make much more sense, because as inner proofs, they don't need to hide anything by design. They will be handed to the outer proof as witnesses, so there is no risk of leaking anything. And this is directly comparable to flat approaches, and the committed variants of the hierarchical ones.
Using committed variants for inner circuit only complicates the circuit for no reason. In my opinion, this kinda connects all the dots, giving each variant a reason to exist, if not for the final comparison, at least as components that help the bigger picture. 

= Summary of Constructions

The hierarchical plain variants are dominated by their committed versions. So they don't take part in the deployable "map" of variants, but they are still valuable because they mark the starting point and the inner mechanism of the recursive approach. The "thought process/flow" can be presented like this:

1. Flat approach #sym.arrow bottleneck of monolithic proof #sym.arrow decomposition #sym.arrow
2. Hierarchical approach #sym.arrow plain variants #sym.arrow leakage problem #sym.arrow committed variants #sym.arrow verifier overhead of $K+1$ proofs #sym.arrow
3. Recursive approach #sym.arrow verifier fixed, in-circuit constant overhead due to inner proof verification on prover side #sym.arrow 
4. Trade-offs of each approach, with conceptual analysis + empirical benchmark.

Do you think this is reasonable, and a good walk from the flat baseline to the decomposed alternatives? I tried to include variants that allow for first-principle derivation of proofs like the recursive one, in order to present the problems along the way, which explain what are the limits of each approach and how solving one problem often creates another on a different dimension.

= Some Result on Experiments

In the pages that follow, I will show some experimental results of the benchmark I've been running for all variants. They are a little bit overwhelming, but I will dissect them properly and step by step when explaining in the thesis. For now, they provide a rough idea of the empirical evidence I gathered. I split them by $K$ to avoid cluttering them too much. The consequence is that they are a lot of plots. But I will find a proper way to put them in the thesis.

A note on the naming of variants in the plots (legend):
- _iso_ stands for "isolated", and it simply means the benchmark was run sequentially for each segment, i.e. not concurrently. This gives a truthful projection of how parallel performance looks like if we have the hardware.
- when hierarchical approaches are involved, we always have the data w.r.t. the single most expensive segment (worst case) + the glue (or outer for the recursive approach).
- _fs_ stands for Fiat-Shamir, and it simply means the corresponding line is of an implementation that uses the grand-product. The naming is not consistent with sort/product, but I will fix it to ensure consistency. 
- _c_ stands for committed, so _cfs_ simply refers to committed + grand product.

#v(10pt)

We lead with the synthesis, the equal-privacy frontier. Once the partition is hidden, three constructions remain genuinely comparable: the flat baseline, the committed-product hierarchical variant, and recursion with a product inner. All three hide the same information, so the comparison is fair, and they turn out to be three non-dominated corners. The figures below show them at $K = 2, 4, 8$. Flat is simple and keeps an $O(1)$ verifier, but its memory grows without bound. Committed-product gives the lowest per-node memory and full parallelism, but makes the verifier pay $O(K)$. Recursion-product keeps the $O(1)$ verifier and perfect hiding, but pays a large outer that is constant in $N$. The prose that follows dissects the two pairwise comparisons that compose this frontier, recursion versus flat and then hierarchical versus flat, and explains the role of the inner mechanism: a plain-sort inner has an $O(M)$ public surface because each segment must publish its nodes, while a plain-product inner has a constant surface, which is why recursion with a product inner is $M$-independent and a sort inner is not.

One note for reading the plots. The line with no component suffix is the combined cost of the whole cell. For prove time and peak memory it is the maximum of the segment and the glue, so it sits exactly on the worst-case segment whenever the segment dominates the glue (which holds throughout our data, though this is an empirical fact and not a definition). For gate count, verify time and proof size it is instead their sum. The segment line we plot is always the single worst-case segment, and the glue line (or the outer line, for recursion) is always the binding proof, shown separately so that neither hides the other.

#page(
  flipped: true
)[
  #figure(
    image("13_equalprivacy_k2_linear.png", width: 120%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("13_equalprivacy_k4_linear.png", width: 120%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("13_equalprivacy_k8_linear.png", width: 120%),
  )
]

== Recursion (product inner) versus flat, and the role of K.
Both routes prove the identical statement and hand the verifier the same object (a single UltraHonk proof of
  14,656 bytes, checked in ~12–20 ms independently of N and K) so this is purely a comparison of prover cost, memory, and total work, not of verifier burden or privacy.
  Flat proves the whole tour monolithically, so its gate count, prover time and peak memory all grow roughly linearly in N (≈1.79 M gates / 25 s / 2.4 GB at N=1000, rising
  to ≈6.4 M / 86 s / 8.3 GB at N=3000). Recursion instead proves K independent segments of size M = N/K and then verifies all K segment proofs inside one outer circuit. The
  outer is the dominant and most characteristic cost: it is essentially independent of N: each in-circuit proof verification costs a fixed ≈740 k gates, ≈1 GB and ≈10 s
  regardless of segment size, but it scales linearly in K, measuring ≈1.47 M gates / 2.1 GB / 20 s at K=2, ≈3.0 M / 4.1 GB / 40 s at K=4, and ≈6.1 M / 8.1 GB / 78 s at K=8.
  The per-node segment, by contrast, shrinks as K rises (its work is ∝ M = N/K). This is the central trade-off in K: increasing K makes each leaf cheaper and more numerous
  but inflates the outer aggregation in direct proportion, and because the outer runs as a serial tail after the leaves (it consumes their proofs) it can never be hidden by
  parallelism. Consequently recursion buys no reliable speed advantage. Even in the idealized parallel best case its wall-clock is governed by the fixed-but-K-growing
  outer, so it loses to flat at small and moderate N (≈32 s vs 25 s at N=1000, K=2) and only dips below flat at large N and the lowest K (≈66 s vs 86 s at N=3000, K=2), with
  each increase in K pushing it back above flat. The robust win is memory: a proving node only ever holds one M-sized segment or the outer, so the machine's peak is bounded
  by max(per-leaf ∝ N/K, outer ∝ K), a ceiling that is constant in N for a fixed K, whereas flat's peak climbs without bound. Flat therefore crosses the recursion ceiling
  at a K-dependent point (around N≈800 for K=2, and proportionally later for larger K), beyond which recursion needs strictly less RAM per machine; raising K is precisely
  the mechanism that keeps a larger N feasible, paid for by a larger constant outer.

=== How this changes with a plain-sort inner segment.

  Replacing the product segment with a plain-sort segment leaves the qualitative picture intact: same one-proof verifier,
  same dominant outer, same conclusion that memory rather than speed is the win. But it changes one quantity: the outer is no longer constant in N. A product
  (grand-product) segment collapses its proof obligation into an O(1) public surface (a handful of accumulator and endpoint fields), so the in-circuit verifier binds the
  same fixed amount of public data per segment whatever M is, and the outer stays flat in N (≈3.009 M → 3.019 M gates from N=48 to N=3000 at K=4, a +0.3% drift). A
  plain-sort segment instead exposes an O(M) public surface: the per-segment ordering/edge data the binding must read. So the outer has to hash and bind a public-input
  vector that grows with the segment size, and its gate count creeps up with N (≈3.010 M → 3.162 M over the same range, +5%) instead of holding constant. The effect is
  second-order at the sizes measured, because the fixed ≈740 k-gate verification primitive still dominates each in-circuit check and the inner segments themselves are
  near-identical in cost (≈202 k vs 209 k gates at N=512, K=4; the sort segment is in fact marginally cheaper). But it is exactly why the product segment is the preferred
  recursion inner: it keeps the outer's cost a function of K alone and preserves the clean "outer constant in N" scaling, whereas plain-sort reintroduces a mild N-dependence
  into the aggregation layer that would compound at larger N.


#page(
  flipped: true
)[
  #figure(
    image("11_hier_committed_gp_vs_flat_k2_linear.png", width: 110%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("11_hier_committed_gp_vs_flat_k4_linear.png", width: 110%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("11_hier_committed_gp_vs_flat_k8_linear.png", width: 110%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("12_hier_committed_sort_vs_flat_k2_linear.png", width: 110%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("12_hier_committed_sort_vs_flat_k4_linear.png", width: 110%),
  )
]

#page(
  flipped: true
)[
  #figure(
    image("12_hier_committed_sort_vs_flat_k8_linear.png", width: 110%),
  )
]


== Hierarchical (K + 1 proofs) versus flat.

The plots here are the committed variants, the deployable ones that hide the partition (the plain variants behave almost identically on the prover side, since the commitment is nearly free; they only differ in what they leak). Hierarchical proving and flat proving solve the same problem in two different shapes. Flat proves the whole tour as one
  circuit. Hierarchical splits the tour into K segments and
  adds one small glue proof that binds them together. Because each segment covers only M = N/K nodes, the work on a single proving node falls by about a factor of K: at
  N=1000 the per-node committed-product segment takes about 13 seconds and 1.28 GB at K=2, 7 seconds and 0.62 GB at K=4, and 3.8 seconds and 0.33 GB at K=8, so each node does roughly the flat
  cost divided by K. This is the win that hierarchical is built for, and it grows with K, since more segments means smaller, cheaper, lower-memory nodes that can run in
  parallel. The cost of that win shows up on the verifier side. Flat delivers a single proof (14,656 bytes, checked in about 12 milliseconds), while hierarchical delivers
  K+1 proofs and runs K+1 verifications plus a cross-check, so both the proof size and the verify time grow with K. At N=1000 the proof size goes from about 44 KB at K=2 to
  73 KB at K=4 to 132 KB at K=8 (each step adds one more segment proof), and the verify time rises from about 0.11 to 0.26 seconds, against flat's steady 0.012 seconds. The
  total gate count, by contrast, is essentially unchanged: K segments plus glue come to about 1.81 to 1.83 million gates across all K, close to flat's 1.79 million, with the
  small extra being the stitching overhead together with the in-circuit commitment. In short, hierarchical does not reduce the total work, it redistributes it. It trades a single large prover for K small parallel
  provers, and a single cheap verifier for a verifier whose cost grows with K. Raising K sharpens both sides of that trade at the same time.

=== How sort differs from product.

  This compares committed-sort against committed-product, but the contrast is structural and would look the same for the plain variants: committing the published values hides them, it does not change their size or the work the glue does. On the segment side the two encodings behave almost identically. The per-node segment cost and the conserved total work
  are within a few percent of each other (about 209k gates each at N=512, K=4), and the verifier tax grows with K the same way for both. They differ in one place, the glue. With the product encoding the glue
  stays tiny and roughly constant, only tens of megabytes (about 35 to 55 MB at N=1000 across all K), because it only has to bind a handful of accumulator and endpoint
  values. With the sort encoding the glue is much heavier, and it grows with the full instance size N rather than with the segment size, because it has to bind the global
  ordering across all the segments, and committing those nodes does not shrink them. Its peak memory climbs from about 0.6 GB at N=1000 to 2.3 GB at N=2000 and roughly 11.9 GB at N=5000 (this steep growth is worth re-confirming against a fresh run before we lean on it too hard), and it does not get smaller as K
  increases. This has a concrete effect on the memory win. In the distributed picture the memory a machine needs is the larger of the segment node and the glue node. For
  product the glue is negligible, so the per-machine peak keeps falling like 1/K as K grows. For sort the glue is a fixed floor that the shrinking segments eventually drop
  below: at N=1000 the segment still dominates at K=2 and K=4 (about 1.21 GB and 0.64 GB), but at K=8 the glue (about 0.60 GB) overtakes the 0.33 GB segment and sets the
  per-machine peak. At large N this matters a great deal, because the sort glue grows into the multi-GB range on its own, so the glue node becomes a memory bottleneck and
  raising K no longer lowers the overall memory ceiling. The practical reading is that the product encoding keeps the clean memory and parallelism win at every K, while the
  sort encoding keeps the same segment-level win but reintroduces a heavy, N-growing, K-independent glue that caps the memory benefit at high K and large N.

= Summary Table and Closing

#figure(
  table(
    columns: (auto, 1fr, auto, 1fr, 1fr),
    align: (left, left, left, left, left),
    inset: 6pt,
    [*Construction*], [*Privacy*], [*Verifier*], [*Prover (per node)*], [*Role*],

    [Flat (Merkle, sort / product)],
    [Perfect (root + threshold only)],
    [$O(1)$, one proof],
    [Monolithic; memory grows with $N$, no parallelism],
    [Baseline; hits the memory wall],

    [Plain-sort hierarchical],
    [Leaks segment node sets],
    [$O(K)$, $K+1$ proofs],
    [$approx N/K$, but heavy $O(N)$ glue],
    [Building block; sort inner for recursion],

    [Plain-product hierarchical],
    [Leaks boundaries + partial products],
    [$O(K)$, $K+1$ proofs],
    [$approx N/K$, light glue],
    [Building block; product inner for recursion],

    [Committed-sort hierarchical],
    [Computational (Poseidon2)],
    [$O(K)$, $K+1$ proofs],
    [$approx N/K$, heavy glue persists],
    [Deployable, but dominated by committed-product],

    [Committed-product hierarchical],
    [Computational (Poseidon2)],
    [$O(K)$, $K+1$ proofs],
    [$approx N/K$, light glue (lowest memory)],
    [*Frontier corner*: prover-optimal],

    [Recursion (product inner)],
    [Perfect (root + threshold only)],
    [$O(1)$, one proof],
    [Bounded ceiling $max(N/K, K dot "outer")$; serial outer],
    [*Frontier corner*: verifier-optimal],

    [Recursion (sort inner)],
    [Perfect (root + threshold only)],
    [$O(1)$, one proof],
    [Like product, but outer grows with $N$],
    [Dominated by product inner],
  ),
  caption: [All constructions across privacy, verifier cost and per-node prover cost. At equal (partition-hiding) privacy the three non-dominated corners are flat, committed-product hierarchical, and recursion with a product inner.],
)

Taken together, the constructions trace one idea from a single angle to a small map. Flat sets the baseline and shows the wall: a monolithic proof whose memory grows with the instance until a single machine can no longer hold it. Decomposition is the way out, and it comes in two shapes that turn out to be the same work placed in two different places. The hierarchical shape keeps the binding outside the proofs, so the prover gets parallelism and low per-node memory while the verifier pays for $K+1$ proofs. The recursive shape folds the binding into one outer proof, so the verifier is back to a single check while the prover pays a large, constant outer. The plain and sort variants are not deployable on their own, since they leak or carry a heavy glue, but they earn their place as the rungs that motivate the committed versions and as the inner mechanisms the recursion reuses. What survives at equal privacy is a frontier of three corners rather than a single winner: flat for small instances, committed-product when proving is the bottleneck and the verifier has slack, and recursion-product when the verifier must stay succinct and the partition must stay perfectly hidden. The clean statement is that one cannot have a cheap prover, a cheap verifier, and perfect privacy all at once; each corner gives up exactly one. Two things remain open before these numbers are final: the concurrent single-machine measurement that will replace the parallel best case used here, and a re-run to confirm the steep growth of the sort glue. Neither is expected to move the shape of the frontier, only to firm up the constants.
