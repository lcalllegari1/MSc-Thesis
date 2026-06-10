#chapter([The Flat Baseline], label: <chap:methodology>)

#section([The Anatomy of the Proof], label: <sec:proof-anatomy>)

Recall the statement we are after, first mentioned at the end of @sec:motivation and formally defined in @sec:prob-formulation: given a complete weighted graph on $N$ nodes, the prover knows a Hamiltonian cycle whose total cost does not exceed a public threshold $T$. We want the verifier to come away convinced this is the case without learning anything else---not the cycle, not its exact cost. Our task is to turn that one sentence into a zero-knowledge proof. More precisely, we go from the statement to a set of arithmetic constraints that together form a circuit, through a process called arithmetization. That circuit is what lets us build a zk-SNARK, which in turn lets us prove knowledge of a witness satisfying the circuit without revealing it.

#subsection([Defining the Witness], label: <sub:witness-def>)

The private witness is the cycle itself. Its exact cost is private too, but it can be derived directly from the cycle through the cost matrix, so it is never an explicit input the prover supplies. We represent the cycle as an array of node indices, where the $i$-th entry names the $i$-th node visited. The closing edge we leave implicit: once all $N$ nodes have been visited, the tour returns to where it began, but that final step back to the start is not written down. So an array of $N$ entries stands for $N$ directed edges, of which $N-1$ are given explicitly by consecutive entries and the last---the return to the start---is read off by convention rather than stored. Treating closure as a convention we read into the array, rather than a fact recorded in it, costs us no generality and buys two small conveniences: it keeps the encoding lean, and it means that proving a statement about an open path instead of a closed cycle---one that need not return to its first node---is a change of a single line in the implementation.

Now that we know what the witness looks like, the natural question arises: what must be true of that array for it to encode a valid, cheap-enough tour---that is, a valid witness?

#subsection([Defining the Constraints], label: <sub:constraints-def>)

We closed the last section with a reasonable question, and we are now ready to answer it. For the array to carry a valid witness, exactly three things must hold, and we encode each as its own block of constraints, which we call a _constraint group_. Together the three groups certify that the array describes a valid, sub-threshold tour. The numbering is not mere bookkeeping: these three groups are the skeleton every circuit in this thesis shares, and reading it once here buys the reader all the constructions to come. The hierarchical approaches will bend the groups only slightly, adapting them to hold for local segment proofs as well as for the single global proof of the flat approach.


- Group 1: _Permutation_
  #block(
    stroke: (left: 1.5pt + colors.primary),
    inset: (left: 10pt),
    height: 35pt,
    above: 1em,
    align(horizon)[
      The cycle visits every node exactly once: its entries are a permutation of the set ${0, dots, N-1}$.
    ]
  )
#v(5pt)
- Group 2: _Edge Cost_
  #block(
    stroke: (left: 1.5pt + colors.primary),
    inset: (left: 10pt),
    height: 55pt,
    above: 1em,
    align(horizon)[
      The cost charged for each edge is that edge's true cost under the (committed) cost matrix, and not some convenient number the prover invented.
    ]
  )
#v(5pt)
- Group 3: _Threshold_
  #block(
    stroke: (left: 1.5pt + colors.primary),
    inset: (left: 10pt),
    height: 15pt,
    above: 1em,
    align(horizon)[
      The $N$ edge costs sum to at most the public threshold $T$.
    ]
  )

It is worth pausing on what each group is there to stop, because every one of them closes a door a dishonest prover would otherwise walk through. Group 1 is what forces the route to be a genuine tour rather than a convenient walk: by demanding that the cycle be a permutation of the nodes, it prevents a dishonest prover from revisiting a cheap node and quietly skipping an expensive one, to avoid paying its cost, while still presenting what looks like a sequence of $N$ steps. Group 2 ties the proof to reality: edge costs are not numbers the prover hands over but values fixed in advance by the (committed) cost matrix, so this group is what stops the prover from charging a lower price than the graph actually demands. Group 3, finally, is the claim itself---that the tour comes in under budget---and is the one assertion the entire proof exists to make. The first two groups, in a sense, are there only so that the third means what we want it to mean.

The division is exhaustive: a witness that satisfies all three is a valid sub-threshold tour, and every valid sub-threshold tour satisfies all three. Its real value, though, is that the three groups are _orthogonal_: changing one leaves the others untouched. Group 3, the threshold, is settled once and never touched again; Group 1, the permutation mechanism, and Group 2, the way edge costs are bound, are the two knobs the rest of the thesis turns---and every variant we build turns exactly one. That is what later lets us read a change in cost as the work of a single group rather than an unattributable mix.

#subsection([Assembling the Circuit], label: <sub:assembling>)

We began with a single sentence defining our claim and broke it into three constraints stated in plain words. But we are yet to have something a prover can run. The next thing to do is to express the same three groups in program form: not the real code yet, that will come at the right time later on, but a pseudocode close enough to it that the shape of the circuit, and its costs, start to show through. 

Two choices have to be made before we can write anything down, and for both, the first instinct is the starting point. The first choice is about how to retrieve edge costs. Indeed, the circuit must somehow get at the edge costs, and the simplest way imaginable is to hand it the whole cost matrix as a public input: the prover and verifier already agree on the graph, so we give the circuit all $N^2$ entries and let it look up whatever it needs. We start there because it asks for no machinery and it simply works. It is worth flagging already that handing over the entire matrix is not the only way to give the circuit access to it: one could instead commit to the matrix and feed in only a short fingerprint, proving each looked-up cost against it. We will not need that yet, so we set it aside---but we mark the spot, because those $N^2$ public inputs will come back to bite us, and dealing with them is a crucial point in the sections to come.

One implementation detail deserves a word, since the listing that follows quietly leans on it. The cost matrix is by nature an $N times N$ table, but we do not store it as one: we flatten it row by row into a single one-dimensional array of $N^2$ entries, putting the cost of the directed edge from node $i$ to node $j$ at index $i dot N + j$. The reason is simple---a flat array is the shape the tooling handles most readily, from Noir's `Prover.toml` down to the Python script that formats the inputs---but it is worth clarifying, because it is exactly the arithmetic Group 2's lookup performs, and the same address $i dot N + j$ will reappear in @sec:representation when we commit to the matrix instead of publishing it.

The second choice is how to enforce Group 1---that the cycle is a permutation of the nodes---and here too the natural move is the direct one. If you wanted to convince yourself, in any ordinary program, that a list of $N$ numbers had no repeats, you would compare every entry against every other and make sure no two coincide. That pairwise distinctness check is the first thing we write. On its own, though, it is not enough: it guarantees that no node is visited twice, but not that every node is visited exactly once, because it does not check that the entries are real nodes---a prover could hand over $N$ distinct numbers that overshoot the graph entirely. To close this gap we add a _range check_, forcing every entry to be a valid node index. The two together do amount to a permutation of the nodes: $N$ entries, all distinct and all in range, must by the pigeonhole principle be exactly the nodes, each visited once. It is a correct check, but---as the gate count will shortly remind us---a quadratic one; cheaper mechanisms exist, and a stronger one will later enforce the permutation directly, with no separate range check. For now, the brute-force version is the honest starting point.

One convention before the listing that shows the pseudocode for our circuit. We write `require P` for a constraint: a relation the witness is obliged to satisfy for the proof to go through. The word is deliberate. In the real Noir source code this same line is written with an `assert`, but that name is a little misleading---it is not the runtime check of an ordinary program, which tests that a condition holds. A circuit cannot perform an `assert` in the same way another program does, and Noir will properly translate that instruction appropriately. However, for the sake of clarity, we write `require P` to encode the fact that we are adding $P$ to the system of equations the proof must satisfy, and a witness that violates it is not a witness in the first place. The signature, likewise, names the public and private inputs explicitly, since that split is the privacy surface that we analyze throughout this work.

With all of this in mind, we are now ready for our circuit pseudocode specification, presented in @fig:flat-pairwise that follows.

#figure(
```
circuit flat-pairwise
  public   matrix[0 .. N²−1],  T
  private  cycle[0 .. N−1]

  // Group 1 — permutation, by range + pairwise distinctness
  for i in [0, N):
      require cycle[i] < N
  for i < j in [0, N):
      require cycle[i] ≠ cycle[j]

  // Group 2 — edge cost, by direct lookup into the public matrix
  total ← 0
  for i in [0, N):
      total ← total + matrix[ cycle[i]·N + cycle[(i+1) mod N] ]

  // Group 3 — threshold
  require total ≤ T
```,
caption: [The flat baseline in its simplest form: the public-matrix representation of @sec:representation with the pairwise permutation check of @sec:permcheck.],
) <fig:flat-pairwise>

Two details in this small circuit deserve a closer look, because each is a lesson in what "writing a sentence as constraints" really costs.

The first hides in plain sight. The line `require cycle[i] ≠ cycle[j]` looks exactly like a not-equal test one would write in any language, and that resemblance is precisely the trap: a circuit has no such test. It can assert that two polynomials are equal; it cannot directly assert that two values differ. So where does the `≠` go? It is shorthand for a small trick. A field element $d$ is nonzero exactly when it has a multiplicative inverse, so in order to prove that $d = a - b$ is nonzero it is enough to exhibit one. The prover, while generating the witness---off to the side, in ordinary arithmetic that costs the circuit nothing---computes $w = d^(-1)$ and supplies it as an extra private input. The circuit then enforces the single equality $d dot w = 1$. If $a$ and $b$ differ, the honest prover's $w$ satisfies it; if $a = b$, then $d = 0$, no inverse exists, and no value of $w$ can make $d dot w = 1$---the constraint is simply unsatisfiable, and no proof can be formed. So the `≠` in the listing quietly conceals two things the figure does not show: an extra witness value, the inverse, and one multiplication constraint. This is the SNARK style in miniature, a pattern we will meet again and again---let the prover compute freely and out of sight, and have the circuit check only a cheap relation on the result. The cost here is one inverse and one constraint per pair of positions, hence $N(N - 1) \/ 2$ of them: this is exactly the quadratic the next section sets out to escape.

The second detail is a subtlety in Group 2 that we will meet again in @sec:witness-inversion and that is easy to walk past and important to get right: an array lookup that looks free can be one of the most expensive things a circuit does. To understand this, look closely at the cost lookup presented in the listing, `matrix[ cycle[i]·N + cycle[(i+1) mod N] ]`: it actually tangles together two kinds of array access, and telling them apart is the whole point. The inner reads `cycle[i]` and `cycle[(i+1) mod N]` fetch cycle entries at positions that are plain constants---the loop is unrolled at compile time (see @sec:snarks), so `i` runs through $0, 1, ..., N-1$, and `(i+1) mod N` is just as fixed at each step. This means that even if the values sitting at those positions are secret---they are part of the prover's witness---the positions themselves are settled before any secret is chosen. The outer read into `matrix` is the opposite case: its index is built out of those secret values, so the position it points to is not known until proving time. Surprisingly, the obvious difference between the two reads---that the cycle's values are secret and the matrix's public---is not the one the circuit cares about: secrecy decides who learns what, but it does nothing to the cost of a read. Then what is the true difference? The position---which slot of the array a read draws from. For the cycle that slot is fixed when the circuit is compiled; for the matrix it takes shape only at proving time. So what divides a cheap read from a costly one is not whether the value is public or private, but whether its position is known in advance: a value whose position is fixed ahead of time is almost free to read, while one whose position is determined by the witness---that is, only at proving time---is costly.

Why should a secret position cost so much more than a secret value? Because a circuit is a fixed wiring diagram, soldered once, before any witness exists. Something like "Read position $3$ of the cycle" is a wire you can attach in advance: you need not know what value will flow along it, only which terminal to reach for. By contrast, "Read position $k$ of the matrix"---where $k$ surfaces only at proving time---cannot be wired in advance at all: with the diagram already fixed, the circuit has no way to know which of the $N^2$ terminals it should connect, and so cannot reach a value whose position is decided only once the witness exists. The way around it is, once again, the pattern we met with the `≠` check: have the prover compute, out of sight, what the circuit cannot, and let the circuit check only that the result is consistent.

This check is a general construction---_offline memory checking_, or a _read-only-memory (ROM) lookup_ in the circuit's own terms---used widely enough to be worth understanding in its own right, and explained in @sec:snarks. However, the thing that matters here is its price. A read at a fixed position is cheap and consists of a single wire; a read at a witness-chosen position is expensive, because it drags in that whole check---paid once for every such access, and assembled by the prover's witness solver before proving can even begin.

With the baseline circuit in hand, the next step is optimization. Two questions arise immediately. The first stems from the quadratic permutation check: is there a more efficient way to prove that the cycle is a permutation of the nodes? The second concerns the public inputs: only $N$ edge costs are used, but the full cost matrix of $N^2$ entries is always supplied, making the number of public inputs quadratic in $N$. Is there a way to reduce this public input surface? We address these two questions next.

#section([Five Ways to Check a Permutation], label: <sec:permcheck>)

The first of those two questions is the subject of this section, and it has more than one answer. The pairwise check of @sec:proof-anatomy is correct but quadratic, and we already named the culprit: it compares every position against every other, $N(N-1) \/ 2$ comparisons in all. What we want is a check that scales linearly with $N$, and the route to one is a pattern we have already met twice---once for the $≠$ test, once for the matrix lookup. Both times the move was the same: let the prover compute something freely, off to the side and out of the circuit, and have the circuit verify only a cheap relation on the result. The pairwise check never makes that move; it does all of its work inside the circuit. Each mechanism that follows makes it, and they differ only in _what_ the prover is asked to supply and _what_ the circuit then checks.

We present four such mechanisms, and the pairwise check makes five in total. The first three---sort, inverse-permutation, and presence---are different bookkeeping tricks for the same exact, structural guarantee, and they trade circuit gates against prover effort and against the kind of memory the tooling must stand up. The fourth, the grand product, is different in kind: it abandons exactness for a probabilistic argument, and in doing so changes the very flavor of the proof's soundness. That last mechanism is the one that matters most for everything after this chapter, and we build toward it deliberately. Throughout, the check we are sharpening is Group 1, the permutation group; Groups 2 and 3 are untouched, so any difference in cost between two of these circuits is attributable to the permutation mechanism and to nothing else---a small instance of the discipline that organizes the whole thesis.

#subsection([Sorting the Cycle], label: <sub:sort>)

The most familiar way to convince yourself that a list of $N$ numbers is exactly ${0, dots, N-1}$, each once, is to sort it and look: if the sorted list reads $0, 1, 2, dots, N-1$, the original was a permutation, and otherwise it was not. The trick is to do this without paying for the sort inside the circuit, where sorting is anything but cheap.

The pattern supplies the escape. Sorting is something the prover can do for free in ordinary code, off-circuit, while preparing the witness; what is ruinously expensive is sorting _inside_ the circuit, and that is exactly the part we can avoid. So the prover sorts the cycle on the side and hands the result in as an extra private input---a _hint_ we will call `sorted`. The circuit itself never sorts anything. It has only to satisfy itself, with cheap linear checks, that this handed-in array is what the prover claims: a sorted rearrangement of the cycle that happens to read $0, 1, dots, N-1$. @fig:flat-sort shows the Group 1 this produces, and the three checks (b)--(d) it rests on; we read them in turn.

#figure(
```
  // Group 1 — permutation, by an off-circuit sort
  // (a) the prover sorts the cycle off-circuit and hands it in
  private  sorted[0 .. N−1]            // hint: = sort(cycle), free in ordinary code

  // (b) the array handed in really is sorted
  for i in [0, N−1):
      require sorted[i] ≤ sorted[i+1]

  // (c) it is a rearrangement of the cycle (same multiset of values)
  require check_shuffle(cycle, sorted)  // ≈ 2N prover-chosen reads

  // (d) and it is exactly 0, 1, ..., N−1
  for i in [0, N):
      require sorted[i] = i
```,
caption: [The sort-based permutation check, replacing Group 1 of @fig:flat-pairwise. The prover supplies the sorted cycle as a hint (a); the circuit verifies it is sorted (b), is a rearrangement of the cycle (c), and equals $0, dots, N-1$ (d). Groups 2 and 3 are unchanged.],
) <fig:flat-sort>

Check (b) confirms that the handed-in array really is in order: one comparison `sorted[i] ≤ sorted[i+1]` per adjacent pair, $N-1$ in all. Sortedness on its own, though, says nothing about the cycle---an array can be flawlessly sorted while omitting some nodes and repeating others. Check (c) is what ties it back: `check_shuffle`, a standard library routine, confirms that `sorted` and `cycle` hold the same multiset of values---that each is a rearrangement of the other. Like everything else in the pattern, it does this by taking an unconstrained permutation map from the prover and merely verifying it, at a cost of roughly $2N$ array reads. With (b) and (c) together we know `sorted` holds exactly the cycle's values, now in order; check (d) pins those values down, asserting `sorted[i] = i` for every $i$, a system satisfiable only when the sorted array reads $0, 1, dots, N-1$. Chaining the three: the cycle's values, put in order, are $0$ through $N-1$ each exactly once---which is to say the cycle is a permutation of the nodes.

The cost has dropped from quadratic to linear: on the order of $3N$ constrained operations---$N-1$ ordering checks, the $approx 2N$ reads inside the shuffle, and the $N$ equalities---against the pairwise check's $N(N-1) \/ 2$. There is even a small bonus. The combination "`sorted` equals $0, dots, N-1$ and `sorted` is a rearrangement of `cycle`" already forces every cycle entry to lie in range, so the explicit range check that the pairwise circuit needed as a separate guard is now subsumed, free of charge. The price is paid in two coins. The prover must do real work off-circuit (the sort and the permutation map), though that work is cheap in ordinary arithmetic and costs the circuit nothing. And---less visibly, but it will matter a great deal later (@sec:witness-inversion)---those $approx 2N$ reads inside `check_shuffle` are reads at positions the prover chooses, the expensive dynamic kind from @sec:proof-anatomy, not the free static kind.

How much does the step from quadratic to linear actually buy? Because the sort and the pairwise circuits are identical everywhere except Group 1, their gate-count difference is exactly the price of the permutation mechanism, with nothing else mixed in. At small $N$ the two are neck and neck---at $N = 8$ the sort circuit is even marginally _larger_ ($3505$ against $3472$ gates), the linear machinery's fixed overhead not yet repaid by so short a list. By $N = 104$ the sort is ahead by some ten thousand gates, and at $N = 1000$ by nearly a million---a gap that grows like $N^2$, because it _is_ the quadratic, now removed. The lesson is the expected one stated precisely: the asymptotically better mechanism wins, but only once $N$ is large enough to pay off its constant overhead.

#subsection([Supplying the Inverse], label: <sub:invperm>)

The sort check does two jobs: it establishes that the sorted array is sorted, and that it matches the cycle. The first job, on reflection, is only a means to an end---we sort the cycle solely so that comparing it against $0, 1, dots, N-1$ becomes trivial. If the prover could point us straight at the answer, we could skip sorting altogether.

This is exactly what the inverse-permutation check does. The prover supplies, as an extra private witness, an array `inv_perm` of length $N$ where `inv_perm[v]` claims to be the position in the cycle at which node $v$ sits---the inverse of the map the cycle defines. The circuit then walks $v$ from $0$ to $N-1$ and, for each, checks two things: that the claimed position `inv_perm[v]` is in range, and that the cycle really does carry $v$ there, that is, `cycle[inv_perm[v]] = v`. That is all. Two distinct nodes $u ≠ v$ cannot be assigned the same position, because the single cell at that position cannot equal both $u$ and $v$ at once; so the claimed positions are distinct, and $N$ distinct in-range positions paired with the $N$ values $0, dots, N-1$ force the cycle to be a permutation. The range check is again subsumed.

The accounting is $2N$ constrained operations---$N$ range checks and $N$ reads---which undercuts the sort's $approx 3N$ by removing the sortedness verification entirely. The saving comes from asking the prover for more: where the sort check synthesized its own permutation map inside `check_shuffle`, here the prover hands the inverse over directly, shifting that bookkeeping out of the circuit. It is the pattern pushed one step further---supply more off-circuit, check less on-circuit. The dynamic reads remain, however: `cycle[inv_perm[v]]` is a read at a witness-chosen position, the same costly kind the sort incurs, and there are $N$ of them.

#subsection([Marking as We Go], label: <sub:presence>)

The two checks so far both lean on the standard library and on the prover supplying a structured hint. There is a third route that is more elementary, asks the prover for nothing beyond the cycle itself, and is correspondingly easy to read and to trust---a virtue worth something in a proof whose entire purpose is to be believed.

The idea is the one a person would use to check a guest list against arrivals: keep a sheet, and tick each name as it comes in; if anyone is already ticked, someone is double-counted. The circuit keeps a boolean array `seen` of length $N$, all entries false to begin with, built into the circuit's structure rather than supplied by the prover---so a cheating prover cannot pre-tick it. Then it scans the cycle once: at each position $i$ it reads `seen[cycle[i]]`, asserts it is still false (this node has not been visited before), and sets it to true. If two positions named the same node, the second visit would find the mark already set, and the assertion would fire. A separate range check is needed here, since `cycle[i]` indexes into `seen` and an out-of-range index would be meaningless; with that guard in place, $N$ distinct in-range values are exactly ${0, dots, N-1}$.

This mechanism exposes a distinction the earlier two slid past. The `seen` array is not read-only: the circuit writes to it as it goes, and a later read must reflect an earlier write. That is no longer a read-only memory but a read--_write_ one, and the tooling backs it with a different, somewhat heavier construction---a RAM table whose consistency is enforced by a timestamp argument that the write at step $i$ is visible at every later step $j > i$. Counting the initialization, the reads, and the writes, the permutation step runs to about $4N$ constrained operations, the dearest of the three exact mechanisms. What it buys back is auditability: no library shuffle, no supplied inverse, just a sequential scan whose soundness argument fits in a sentence. We flag it less for its cost than for the read-only-versus-read-write line it draws, a line that decides how the tooling realizes any array a circuit touches.

#subsection([From Sets to Polynomials], label: <sub:grand-product>)

The three mechanisms so far are variations on one theme: each proves, _exactly_ and with certainty, that the cycle's multiset of values is ${0, dots, N-1}$. The fourth abandons certainty for something subtler and, as we will see across the rest of this thesis, far more useful. It is worth saying at the outset that at this point in the story---a single, flat proof---the grand product is not the rational choice. It is more elaborate than the sort, and it trades away a guarantee for a gamble, in exchange for a benefit that, here, is exactly zero. We introduce it anyway, and now, because it is the next mechanism in the permutation family and because the benefit it cannot collect at the flat level is precisely the one that decomposition will later make decisive. The reader is asked to file it away; @sec:representation and the chapters beyond will call it back.

The idea begins with a reformulation. To say that the multiset ${"cycle"[0], dots, "cycle"[N-1]}$ equals the multiset ${0, dots, N-1}$ is to say that the two collections agree, with multiplicity, as _sets of numbers_---order forgotten. There is a classical way to test multiset equality with a single number. Form, from each side, the polynomial whose roots are the side's elements, and compare the two polynomials:
$
P(Y) = product_(i=0)^(N-1) (Y + "cycle"[i]), quad Q(Y) = product_(j=0)^(N-1) (Y + j).
$
Because $Y |-> Y + dot$ is a bijection, $P$ and $Q$ are equal _as polynomials_ if and only if the two multisets coincide---each shared value contributes the identical factor, and any discrepancy leaves a factor unmatched. So the permutation question becomes a question about whether two polynomials are the same.

Checking that two polynomials are identical sounds harder than what we started with, not easier; the saving comes from not checking it everywhere, only at one point. Evaluate both products at a single field value $X$ and compare the two numbers $P(X)$ and $Q(X)$. If the multisets are equal the polynomials are identical and the two numbers agree at every $X$. If the multisets differ, the difference $D = P - Q$ is a nonzero polynomial of degree at most $N-1$, and such a polynomial has at most $N-1$ roots in the field; so the two numbers agree only if $X$ happens to be one of those at most $N-1$ unlucky points, out of a field of size on the order of $2^254$. This is the Schwartz--Zippel principle: a nonzero low-degree polynomial is almost nowhere zero, so an identity that holds at a random point almost certainly holds everywhere.

Everything now turns on that word _random_. If the prover could see $X$ before committing to the cycle, a cheater could fix a bogus cycle and then search for one of the $N-1$ roots of its own difference polynomial, and the check would be worthless. The challenge $X$ must therefore be unpredictable to the prover and yet reproducible by the verifier, with no interaction between them. The standard device for this is the Fiat--Shamir transform, which we treat properly in @sec:fiat-shamir: in place of a challenge drawn by a live verifier, one _derives_ the challenge by hashing the data the prover has already committed to. Here the circuit computes $X$ by hashing the entire cycle with the Poseidon2 hash---chaining $h_(j+1) = H([h_j, "cycle"[j]])$ across all $N$ entries and folding the result once more into $X$---so that $X$ depends on every node the prover chose. Modeled as a random oracle, the hash returns a value the prover cannot anticipate and cannot steer, fixed once the cycle is fixed. The same `cycle` array feeds both the hash chain and the products, which is what stops a prover from deriving $X$ from one cycle and running the product over another. With $X$ pinned this way, a wrong multiset survives with probability at most $(N-1) \/ |FF| approx 2^(-246)$---negligible by any standard.

The pseudocode is short, and the shape of the cost is visible in it.

#figure(
```
  // Group 1 — permutation, by grand product with Fiat–Shamir challenge
  // (a) derive the challenge from the whole cycle
  h ← 0
  for j in [0, N):
      h ← H( h, cycle[j] )
  X ← H( h )

  // (b) compare the two products at X
  lhs ← 1;  rhs ← 1
  for i in [0, N):
      lhs ← lhs · (X + cycle[i])
      rhs ← rhs · (X + i)
  require lhs = rhs
```,
caption: [The grand-product permutation check. The challenge $X$ is hashed from the cycle in-circuit (Fiat--Shamir), then the two multiset polynomials are compared at that single point.],
) <fig:flat-grandproduct>

Counting constrained work, the check is linear: $N$ hash invocations for the challenge chain and $2N$ field multiplications for the two products, with no library shuffle and---crucially---no dynamic memory at all. Every array index in @fig:flat-grandproduct is a compile-time constant, so the whole check is straight-line, statically-indexed arithmetic. As with the exact mechanisms, the range check comes for free: a multiset equal to ${0, dots, N-1}$ has all its entries in range by definition.

What sets this mechanism apart is not its gate count, which is comparable to the others, but what it does to the proof's soundness. The first three mechanisms are _exact_: when they pass, the cycle _is_ a permutation, full stop, with the certainty of an algebraic identity. The grand product is _probabilistic_: when it passes, the cycle is a permutation _unless_ the prover was astronomically lucky with the challenge, and the guarantee rests on modeling the hash as a random oracle. We have traded a structural certainty for a computational one. At the flat level this is a pure loss---we pay in soundness flavor and receive nothing, since the public surface is already as small as it can be. The reason to make the trade lies further on, when the cycle is cut into segments and each segment must publish a fingerprint of its share of the partition: there, the grand product's single field element $X$ and its product will collapse a per-segment surface that the sort would leave linear, and the trade turns favorable. That argument is the spine of @sec:representation and the chapters after it; for now we have only loaded the gun.

#subsection([A Word on Types, and the Pair That Matters], label: <sub:types-and-pair>)

Before drawing the comparison together, a brief word on the types these mechanisms use, since the choice is not arbitrary and the circuit's cost is sensitive to it. Node indices and positions are unsigned 32-bit integers (`u32`): they range over $0, dots, N-1$, comfortably within $32$ bits for every instance we consider, and keeping them narrow keeps the range checks cheap. Edge costs are `u64`, as established in @sec:proof-anatomy: wide enough that a sum of $N$ edge costs cannot overflow even at our largest $N$. The presence array is `bool`, the natural type for a tick sheet and the one that compiles to the lightest RAM cells. The grand product, by contrast, works in the native field type (`Field`): its challenge is a hash output and its products are field elements, quantities that live in $FF$ and have no business being range-constrained to $32$ or $64$ bits. The rule throughout is to use the narrowest type that holds the value, because every surplus bit is a constraint the prover pays for---and to step up to `Field` exactly when the arithmetic is genuinely field arithmetic, as the hash chain and the products are.

@fig:perm-mechanisms gathers the five mechanisms. Read down the cost column and the story of the section is there: the quadratic pairwise check, then three linear refinements that differ in what the prover supplies and which memory model they invoke, then the grand product---also linear, but standing apart in the last column, where exact certainty gives way to a probabilistic argument.

#figure(
table(
  columns: 5,
  align: (left, left, left, left, left),
  table.header([*mechanism*], [*permutation cost*], [*extra witness*], [*memory*], [*soundness*]),
  [pairwise], [$N(N-1) \/ 2$], [inverse per pair], [---], [exact],
  [sort], [$approx 3N$], [sorted array], [ROM (dynamic)], [exact],
  [inverse-perm.], [$2N$], [inverse map], [ROM (dynamic)], [exact],
  [presence], [$approx 4N$], [none], [RAM (dynamic)], [exact],
  [grand product], [$approx 3N$], [none], [none (static)], [probabilistic],
),
caption: [The five permutation mechanisms for Group 1. The first four are exact; the grand product trades exactness for a probabilistic argument (Schwartz--Zippel over a Fiat--Shamir challenge), and uniquely uses no dynamic memory.],
) <fig:perm-mechanisms>

Of the five, one pairing deserves to be singled out, because it recurs throughout the thesis as the sharpest contrast we can draw: the sort against the grand product. They sit on opposite sides of nearly every axis. The sort is exact; the grand product is probabilistic. The sort leans on dynamic, prover-chosen reads; the grand product is pure straight-line arithmetic. And yet---this is the twist we are deliberately holding back---the one that looks cheaper on paper is not the one that is cheaper to run, and which is which is not what intuition predicts. That inversion is a result in its own right, and we give it its own treatment, with measurements, in @sec:witness-inversion. First, though, we turn to the second of the two questions left open at the end of @sec:proof-anatomy: the cost matrix, all $N^2$ entries of it, still sitting in the public inputs.
