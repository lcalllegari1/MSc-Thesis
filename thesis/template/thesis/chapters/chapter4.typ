#import "/theme/headings.typ": chapter, section, subsection
#import "/theme/colors.typ": colors
#import "/theme/utils.typ": inline, lc, fn
#import "/thesis/chapters/_pseudocode.typ": *
#import "@preview/lovelace:0.3.0": *

#chapter([The Flat Baseline], label: <chap:methodology>)

This chapter builds the proof that the rest of the thesis measures everything against. Starting from the statement of @sec:prob-formulation, a Hamiltonian cycle whose cost stays under a public threshold, we turn one sentence into a single zero-knowledge circuit: we arithmetize it into three constraint groups, weigh five ways to enforce the permutation among them and carry two forward, and commit the cost matrix to a single root so the verifier holds one value in place of $N^2$. The result is _flat-sort_, a monolithic proof that hides the route, its cost, and the graph behind nothing but a root and a threshold. Two things come of building it: the baseline itself, the control every later construction is read against, and the _wall_, the point past which a single prover can no longer hold the whole circuit at once. That wall is the problem @chap:hierarchical takes up.

#section([The Anatomy of the Proof], label: <sec:proof-anatomy>)

Recall the statement we want to prove. It was first mentioned at the end of @sec:motivation and stated formally in @sec:prob-formulation: we are given a complete weighted graph on $N$ nodes, and the prover knows a Hamiltonian cycle through it whose total cost does not exceed a public threshold $T$. We want the verifier to come away convinced this is true, and to learn nothing else: not the cycle, and not its exact cost.

Our task in this chapter is to turn that one sentence into a zero-knowledge proof. We do it in steps. First we turn the statement into a set of arithmetic constraints, which together form a _circuit_; this step is called arithmetization. The circuit is what lets us build a zk-SNARK, and the zk-SNARK is what lets the prover show knowledge of a witness that satisfies the circuit without revealing it.

#subsection([Defining the Witness], label: <sub:witness-def>)

The private witness is the cycle itself. Its cost is private too, but we never supply the cost directly: it can be computed from the cycle through the cost matrix, so it is not a separate input.

We store the cycle as an array of node indices, where the entry at position $i$ names the $i$-th node the tour visits. We do not write down the final step. Once all $N$ nodes have been visited, the tour returns to where it started, and we treat that closing edge as understood rather than stored. So an array of $N$ entries stands for $N$ directed edges: the first $N-1$ are given by consecutive entries, and the last one, the return to the start, is read off by convention.

Leaving the closing edge implicit costs us nothing in generality, and it buys two small things. It keeps the encoding lean. And proving a statement about an open path, one that need not return to its first node, becomes a change of a single line in the code.

Now we know what the witness looks like. The natural question is: what must be true of this array for it to be a valid witness, that is, to encode a real tour that is cheap enough?

#subsection([Defining the Constraints], label: <sub:constraints-def>)

We can now answer that question. For the array to carry a valid witness, exactly three things must hold. We encode each one as its own block of constraints, and we call such a block a _constraint group_. Together, the three groups certify that the array describes a real tour whose cost is under the threshold.

The numbering matters, because these three groups are the skeleton of every circuit in this thesis, and reading them once here pays off in every construction that follows. The hierarchical approaches will bend the groups only slightly, so that they also hold for a single segment of the tour and not only for the whole of it, but the skeleton stays the same.


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

It is worth pausing on what each group is there to prevent, because each one closes a door a dishonest prover would otherwise walk through. Group 1 forces the route to be a real tour rather than a convenient walk: by requiring the cycle to be a permutation of the nodes, it stops a prover from visiting a cheap node twice and quietly skipping an expensive one, while still showing what looks like a sequence of $N$ steps. Group 2 ties the proof to reality: edge costs are not numbers the prover gets to invent, but values fixed in advance by the (committed) cost matrix, so this group stops the prover from charging less than the graph actually demands. Group 3 is the claim itself, that the tour comes in under budget, and it is the one thing the whole proof exists to show. In a sense, the first two groups are there only so that the third one means what we want it to mean.

The three groups cover everything: a witness that satisfies all three is a valid, under-threshold tour, and every valid, under-threshold tour satisfies all three. But the real value of the split is that the groups are _orthogonal_: changing one leaves the other two untouched. Group 3, the threshold, is settled once and never touched again. Group 1, the permutation check, and Group 2, the way edge costs are bound, are the two knobs the rest of the thesis turns, and every variant we build turns exactly one of them. That is what later lets us read a change in cost as the work of a single group, rather than an unclear mix of several.

#subsection([Assembling the Circuit], label: <sub:assembling>)

We started with one sentence and broke it into three constraints stated in plain words. But we still do not have anything a prover can run. The next step is to write the same three groups as a program: not the real code yet, that comes later, but a pseudocode close enough to it that the shape of the circuit, and its cost, begin to show.

Two choices have to be made first, and for both, the simplest option is where we start.

The first choice is how the circuit gets at edge costs. The circuit must look up the cost of each edge, and the simplest way imaginable is to hand it the whole cost matrix as a public input. The prover and verifier already agree on the graph, so we give the circuit all $N^2$ entries and let it read whatever it needs. We start here because it asks for no extra machinery and it simply works. Handing over the full matrix is not the only option: we could instead commit to the matrix and pass in only a short fingerprint, then prove each looked-up cost against it. We do not need that yet, so we set it aside. But we mark the spot, because those $N^2$ public inputs will come back to cause trouble, and dealing with them is one of the main points of the sections ahead.

One implementation detail deserves a sentence, because the listing that follows quietly relies on it. The cost matrix is by nature an $N times N$ table, but we do not store it as one. We flatten it row by row into a single one-dimensional array of $N^2$ entries, and we put the cost of the directed edge from node $i$ to node $j$ at index $i dot N + j$. The reason is simple: a flat array is the shape the tooling handles most easily, from Noir's `Prover.toml` down to the Python script that formats the inputs. It is worth stating clearly, because it is exactly the arithmetic Group 2's lookup performs, and the same address $i dot N + j$ will come back in @sec:representation when we commit to the matrix instead of publishing it.

The second choice is how to enforce Group 1, that the cycle is a permutation of the nodes. Here too we take the direct route. Suppose you wanted to check, in any ordinary program, that a list of $N$ numbers has no repeats: you would compare every entry against every other and make sure no two are equal. That pairwise check is the first thing we write. On its own, though, it is not quite enough. It guarantees that no node appears twice, but not that every node appears, because it does not check that the entries are real nodes: a prover could hand over $N$ distinct numbers that run past the end of the graph. To close this gap we add a _range check_, which forces every entry to be a valid node index. The two together do give a permutation: $N$ entries that are all distinct and all in range must, by the pigeonhole principle, be exactly the $N$ nodes, each used once. The check is correct, but it is quadratic, as the gate count will soon remind us. Cheaper checks exist, and a stronger one will later enforce the permutation directly, with no separate range check. For now, the brute-force version is the honest starting point.

One convention before the listing. We write #inline[require] $P$ for a constraint: a relation the witness must satisfy for the proof to go through. The word is chosen on purpose. In the real Noir source this same line is written with an #inline[assert], but that name is a little misleading. It is not the runtime check of an ordinary program, which tests that a condition holds and stops when it does not. A circuit cannot test anything while it runs; Noir turns the instruction into constraints behind the scenes. So we write #inline[require] $P$ to record what is really happening: we are adding $P$ to the system of equations the proof must satisfy, and a witness that breaks it is not a witness in the first place. The signature names the public and private inputs in the same spirit, since that split is the privacy surface we study throughout this work.

With this in place, we can read the circuit pseudocode in @fig:flat-pairwise.

#[
  #set text(font: "Libertinus Sans")
  #figure(
    kind: "listing",
    supplement: "Listing",
    caption: [The flat baseline in its simplest form: the public-matrix representation of @sec:representation with the pairwise permutation check of @sec:permcheck.],
    pseudocode-list(hooks: 0.5em, booktabs: true, booktabs-stroke: 1pt)[
      + *circuit* #fn[flat-full-pairwise]$(N)$ #h(1fr)
        + *public* $matrix[rng(0, N^2-1)], med T$
        + *private* $cycle[rng(0, N-1)]$
        - #hide("")
        - #lc[Group 1: _permutation, by range + pairwise distinctness_]
        + *for* $i$ *in* #fn[range]$(0, N)$:
          + *require* $cycle[i] < N$
        + *for* $i < j$ *in* #fn[range]$(0, N)$:
          + *require* $cycle[i] != cycle[j]$
        - #hide("")
        - #lc[Group 2: _edge cost, by direct lookup into the public matrix_]
        + $total arrow.l 0$
        + *for* $i$ *in* #fn[range]$(0, N)$:
          + $total arrow.l total + matrix[cycle[i] dot N + cycle[(i+1) pmod N]]$
        - #hide("")
        - #lc[Group 3: _threshold_]
        + *require* $total <= T$
    ]
  ) <fig:flat-pairwise>
]

Two details in this small circuit deserve a closer look, because each one shows what "writing a sentence as constraints" really costs.

The first detail hides in plain sight. The line #inline[require] $cycle[i] != cycle[j]$ looks exactly like a not-equal test you would write in any language, and that resemblance is the trap: a circuit has no such test. It can require that two values are equal; it cannot directly require that two values differ. So where does the $!=$ go?

It stands for a small trick. A field element $d$ is nonzero exactly when it has a multiplicative inverse, so to prove that $d = a - b$ is nonzero, it is enough to exhibit one. While building the witness, off to the side and in ordinary arithmetic that costs the circuit nothing, the prover computes $w = d^(-1)$ and supplies it as an extra private input. The circuit then requires the single equation $d dot w = 1$. If $a$ and $b$ differ, the honest prover's $w$ satisfies it. If $a = b$, then $d = 0$, no inverse exists, and no value of $w$ can make $d dot w = 1$: the constraint simply cannot be satisfied, and no proof can be formed.

So the $!=$ in the listing quietly hides two things the figure does not show: an extra witness value, the inverse, and one multiplication constraint. This is the style of these proofs in miniature, and a move we will use again and again. Stated plainly, it is _compute-then-check_: let the prover compute the answer freely and out of sight, then have the circuit check only a cheap relation on the result. The value the prover hands back, here the inverse $w$, is really a _hint_, something the circuit verifies but never has to find for itself, so we also call the move _the hint trick_. The cost here is one inverse and one constraint for each pair of positions, so $N(N-1) \/ 2$ in all. Next to that, the $N$ range checks barely register. This is exactly the quadratic cost the next section sets out to escape.

The second detail is a subtlety in Group 2 that we will meet again in @sec:witness-inversion. It is easy to walk past and important to get right: an array lookup that looks free can be one of the most expensive things a circuit does.

To see this, look closely at the cost lookup in the listing, $matrix[cycle[i] dot N + cycle[(i+1) pmod N]]$. It combines two different kinds of array access, and telling them apart is the whole point.

The inner reads, $cycle[i]$ and $cycle[(i+1) pmod N]$, fetch cycle entries at positions that are plain constants. The loop is unrolled at compile time (see @sec:snarks), so $i$ runs through $0, 1, dots, N-1$, and $(i+1) pmod N$ is just as fixed at each step. The values stored at those positions may be secret, since they are part of the prover's witness, but the positions themselves are decided before any secret is chosen.

The outer read, into $matrix$, is the opposite case: its index is built from those secret values, so the position it points to is not known until proving time.

Here is the surprising part. The obvious difference between the two reads, that the cycle's values are secret and the matrix's are public, is not the one the circuit cares about. Secrecy decides who learns what; it does nothing to the cost of a read. The difference that matters is the _position_: which slot of the array a read draws from. For the cycle, that slot is fixed when the circuit is compiled; for the matrix, it takes shape only at proving time. So what separates a cheap read from a costly one is not whether the value is public or private, but whether its position is known in advance. A read at a position fixed ahead of time is almost free. A read at a position the witness chooses, and so known only at proving time, is costly.

Why should a secret position cost so much more than a secret value? Because a circuit is a fixed wiring diagram, built once, before any witness exists. "Read position $3$ of the cycle" is a wire you can attach in advance: you need not know what value will flow along it, only which terminal to reach for. "Read position $k$ of the matrix," where $k$ appears only at proving time, cannot be wired in advance at all. The diagram is already fixed, so the circuit has no way to know which of the $N^2$ terminals to connect, and so it cannot reach a value whose position is decided only once the witness exists.

The way around this is, once again, the hint trick: have the prover compute, out of sight, what the circuit cannot, and let the circuit check only that the result is consistent. This check is a standard construction, called _offline memory checking_, or a _read-only-memory (ROM) lookup_ in the circuit's own terms. It is common enough to be worth understanding in its own right, and we explain it in @sec:snarks. What matters here is its price. A read at a fixed position is cheap, just a single wire. A read at a position the witness chooses is expensive, because it pulls in that whole check, paid once for every such access, and assembled by the prover's witness solver before proving can even begin.

With the baseline circuit in hand, the next step is optimization. Two questions come up right away. The first comes from the quadratic permutation check: is there a cheaper way to prove that the cycle is a permutation of the nodes? The second comes from the public inputs: the circuit uses only $N$ edge costs, yet we always supply the full matrix of $N^2$ entries, so the number of public inputs grows with the square of $N$. Can we shrink that public surface? We take these two questions in turn, starting in the next section.

#section([Five Ways to Check a Permutation], label: <sec:permcheck>)

The first of those two questions is the subject of this section. It has more than one answer: five in total, of which the pairwise check of @sec:proof-anatomy is the first and the worst. That check is correct but quadratic, comparing every position against every other, $N(N-1) \/ 2$ comparisons in all. What we want is a check that scales linearly with $N$. The four candidates ahead all reach that goal, by different routes and at different costs.

The section does three things, in order. First it introduces each mechanism in turn: the idea, what the prover supplies, what the circuit checks, and an itemized account of what that costs. Then it puts all of them side by side and measures them on identical instances (@sub:mech-measured). Finally it chooses the two mechanisms the rest of the thesis carries (@sub:choosing).

One warning is owed up front, because it changes how the cost analyses should be read: the choice will not be made by the costs. The itemized accounts cannot settle it, since their items carry very different gate prices, and the measurements, when they arrive, end in a near-tie. What settles the choice is a criterion that appears on no account at all: what each mechanism becomes when, in the chapters after this one, the single global proof is cut into pieces. The cost analysis is not wasted work. Working through it is how we come to understand the mechanisms' anatomy: how operations a programmer takes for granted, an array write, a lookup, a comparison, a hash, are actually realized inside a circuit, and at what price. That understanding is exactly what the final argument runs on.

There is a natural order in which to take the four, and it is set not by cleverness but by _memory_. A circuit's cheapest reads are those whose position is fixed before any witness exists. More costly are the reads whose position the prover chooses (@sec:proof-anatomy). More costly still are the cells the circuit must also _write_. So we begin with the most human check of all, the one a person keeps on a clipboard, and find that it asks for the heaviest memory the tooling offers. That cost is our cue to get cleverer. The next two mechanisms step down from read--write memory to read-only memory, and the last gives up prover-chosen memory altogether.

Three of the four, presence, sort, and inverse-permutation, are _exact_: when they pass, the cycle simply _is_ a permutation, with the certainty of an algebraic identity. The fourth, the grand product, is different in kind. It trades that certainty for a probabilistic argument, and the trade is deliberate, so we build toward it last. Throughout, the only thing changing is Group 1. Groups 2 and 3 stay fixed, so any cost difference between two of these circuits is the price of the permutation mechanism and nothing else. This is the discipline that organizes the whole thesis.

Each mechanism is about to be given a price, so a word on how prices will be stated, because it is easy to do this badly. The temptation is to count _constrained operations_ and compare totals. The trouble is that the operations are not alike: a range check, a memory access, and, further down the section, a hash invocation compile to very different numbers of gates, and a total that adds them together pretends otherwise. So we allow ourselves two kinds of statement and no third. We _itemize_: each mechanism's cost is a list of items with multiplicities, read straight off its listing. (Equality checks at fixed positions compile to wiring and stay off the list; a read that must match an expected value counts as one item, a read.) And we _count to classify_: a tally settles whether a mechanism is linear or quadratic, because no price per item can change an exponent. But a tally is never allowed to rank two linear mechanisms against each other. That question belongs to measurement, and @sub:mech-measured answers it.

One more distinction the accounts must respect, since two of the mechanisms ahead lean on the hint trick of @sec:proof-anatomy and hand work to the prover. Each mechanism keeps two separate accounts. The _in-circuit work_ is the constrained operations: these become gates, and the verifier's guarantee rests on them and on nothing else. The _off-circuit work_ is what the prover performs while building the witness, computing hints, sorting, scanning. It lays down no gates and proves nothing, but it takes real time at every single proof. We will find this second account to be anything but a footnote.

#subsection([Marking as We Go], label: <sub:presence>)

Ask a person to check that a list of $N$ names holds each guest exactly once, and they will neither sort it nor invert it. They will run a finger down the list and tick each name against a sheet, watching for one that is already ticked. It is the most direct check imaginable, and it ports into a circuit almost unchanged. The circuit keeps a boolean array $seen$ of length $N$, every entry false to start. The array is built into the circuit's own structure, not handed in by the prover, so that a cheater cannot quietly pre-tick it. The circuit then scans the cycle once. At position $i$ it reads $seen[cycle[i]]$, requires that the entry is still false (this node has not been visited before), and sets it to true. If two positions name the same node, the second visit finds the mark already set, and the requirement fails. One guard is needed, because $cycle[i]$ is used as an index into $seen$: an explicit range check $cycle[i] < N$ must ride along, since an out-of-range index would be meaningless. With it in place, $N$ values that are distinct and in range are exactly ${0, dots, N-1}$, each once.

Before pricing it, one feature of this check deserves to be named, plainly and without judgment for now, because it is the structural fact the whole mechanism stands on: the tick sheet is _addressed by node value_. The expression $seen[cycle[i]]$ uses a witness value as a physical position in an array. That is possible only because the set being checked against is ${0, dots, N-1}$, a contiguous range, fixed when the circuit is compiled, so that a dense array with exactly one cell per node exists to be addressed. The check never compares the cycle against a target it was handed; it compares it against a target built into its own geometry. Nothing is wrong with that here. We record the fact and move on, since it will carry weight in @sub:choosing.

What this check makes plain, and what earns it the opening slot, is the distinction every later cost turns on: the kind of _memory_ a circuit uses. The $seen$ array is not read-only. The circuit writes to it as it scans, and a read at step $j$ must reflect a write made at an earlier step $i < j$. That is a read--_write_ memory, a RAM, and the tooling backs it with the heaviest construction in this section: a table in which every access is logged, together with a consistency argument that proves each read returns the value most recently written to that cell. The argument works by sorting a record of all the accesses and checking it against its own timestamps. The in-circuit work is accordingly the longest we will write: $N$ initializing writes, $N$ reads, $N$ marking writes, and $N$ range checks guarding the indices, all of it on the most expensive memory the tooling offers. The off-circuit work, by contrast, is empty: the prover supplies the cycle and nothing else, since there is no hint to compute. What the long account buys back is auditability. There is no library call and no supplied map to distrust, just a sequential scan whose soundness fits in a sentence, which is worth something in a proof whose whole purpose is to be believed. But the account also tells us what to attack. If the costly thing is read--write memory, the natural question is whether we can get the same guarantee with memory the circuit only ever _reads_. We can, and the next two mechanisms show how.

#subsection([Sorting the Cycle], label: <sub:sort>)

The tick sheet's expense was the writing. So forbid the circuit to write, and let it only read. And, using the hint trick we have leaned on twice already, let the prover do the real work outside the circuit altogether. The most familiar such check is to _sort_: a list is a permutation of ${0, dots, N-1}$ exactly when, sorted, it reads $0, 1, 2, dots, N-1$. Sorting is prohibitively expensive inside a circuit but free outside it, so the prover sorts the cycle while preparing the witness and hands the result in as a private _hint_, the array $sorted$. The circuit never sorts. Its entire job is to decide what that handed-in array is worth.

It is worth naming the split this leans on, because it is the engine of every mechanism that hands work to the prover. The tooling gives us two kinds of code. _Unconstrained_ code runs while the witness is being built: it computes values but lays down no constraints, adds no gates, and the verifier never sees it. The prover may sort, search, or invert, however convenient, for free. _Constrained_ code is the circuit proper: each line becomes gates and is part of what the proof attests. In the implementation the two meet in a single standard-library call, #inline[sort_via], which runs an ordinary quicksort in unconstrained code and then lays down constraints about its output. A free quicksort sounds too good, and the catch sits exactly where it should: nothing about the quicksort is attested. It leaves no trace in the constraint system, so the proof cannot tell whether it ran, ran correctly, or was replaced by something else entirely. From the circuit's point of view, $sorted$ is not "the output of a sort". It is one more private input, chosen by a prover we must assume is dishonest, and every property we mean to rely on must be re-established, in gates, as if the array had arrived from an adversary, because it may have. @fig:flat-sort shows the resulting Group 1: the sort itself (a) is unconstrained and free, and three constrained checks (b)--(d) decide what the hint is worth.

#[
  #set text(font: "Libertinus Sans")
  #figure(
    kind: "listing",
    supplement: "Listing",
    caption: [The _sort_-based permutation check, replacing Group 1 of @fig:flat-pairwise. The prover supplies the sorted cycle as a hint; the circuit checks it is sorted, is a rearrangement of the cycle, and equals $0, dots, N-1$. Groups 2--3 are unchanged.],
    pseudocode-list(hooks: 0.5em, booktabs: true, booktabs-stroke: 1pt)[
      + *circuit* #fn[flat-full-sort]$(N)$ #h(1fr)
        + *public* $matrix[rng(0, N^2-1)], med T$
        + *private* $cycle[rng(0, N-1)], med sorted[rng(0, N-1)]$ #h(1fr) #lc[(a) hint $= "sort"(cycle)$]
        - #hide("")
        - #lc[Group 1: _permutation, by an off-circuit sort_]
        + *for* $i$ *in* #fn[range]$(0, N-1)$: #h(1fr) #lc[(b) is sorted]
          + *require* $sorted[i] <= sorted[i+1]$
        + *require* #fn[check_shuffle]$(cycle, sorted)$ #h(1fr) #lc[(c) same multiset, $approx 2N$ reads]
        + *for* $i$ *in* #fn[range]$(0, N)$: #h(1fr) #lc[(d) is the identity]
          + *require* $sorted[i] = i$
        - #hide("")
        - #lc[Group 2 (edge cost) and Group 3 (threshold) exactly as in @fig:flat-pairwise]
    ]
  ) <fig:flat-sort>
]

Let us establish the checks one at a time, by asking what a cheating prover could do with each of them absent. The end state we want is the identity: the cycle's values, in some order, are $0, 1, dots, N-1$. The most direct constraint toward it is check (d), entry-by-entry equality $sorted[i] = i$. Suppose it were the only one. Then $sorted$ is pinned completely, and tied to nothing: a cheat submits the identity array as its "sorted" hint, puts any cycle whatsoever beside it, and the circuit, having never compared the two, accepts. The hint satisfies every constraint while certifying nothing; Group 1 has quietly evaporated. What is missing is the link, a proof that $sorted$ and $cycle$ hold _the same multiset of values_, each a rearrangement of the other. That is check (c), the standard-library routine #inline[check_shuffle]. With (c) and (d) together the argument closes: the cycle's values, rearranged, are exactly $0$ through $N-1$, each once, so the cycle is a permutation of the nodes. Two constrained checks, and the guarantee is complete.

The reader counting along will notice the listing contains a third. Check (b) requires that $sorted$ is, in fact, sorted: one comparison $sorted[i] <= sorted[i+1]$ per adjacent pair, $N-1$ in all. Given (d) it is logically redundant, since an array forced entry-by-entry to equal $0, dots, N-1$ is in order by inspection. It is on the account because it arrives bundled with the library call. The contract of #inline[sort_via] is "a sorted rearrangement of the input", which is sortedness (b) plus multiset equality (c), because the library cannot know that this particular caller's next move is to pin the array to the identity. For a general caller, sortedness _is_ the deliverable. We could write a bespoke Group 1 that drops (b); we keep the library routine, and the account records what is paid, not what logic strictly requires.

Check (c) hides the cost, and it repays opening up, both because it dominates the account and because its shape will explain the next mechanism. #inline[check_shuffle] is the hint trick in miniature (@fig:check-shuffle). First, unconstrained: the prover finds the map carrying one array onto the other, a list $idx$ of positions with $cycle[i] = sorted[idx[i]]$, by whatever means, for free. Then, constrained, it verifies that hint in _two_ passes. The first proves that $idx$ is a genuine permutation of the positions $0, dots, N-1$, that no slot is reused; without it a prover could aim several cycle entries at one sorted entry and smuggle in a duplicate. The second proves the map actually carries the cycle across, $sorted[idx[i]] = cycle[i]$. Each pass reads an array at a position the prover chose, $idx$ in the first and $sorted$ in the second, so the routine spends about $2N$ of those dynamic, prover-chosen lookups. There is a small irony in pass 1 worth noting: to prove that the cycle is a permutation, the library proves that a _map_ is a permutation, our original statement one level removed, only now over the positions $0, dots, N-1$ rather than the nodes. The problem has not been solved so much as moved to a place where it is cheaper to check.

#[
  #set text(font: "Libertinus Sans")
  #figure(
    kind: "listing",
    supplement: "Listing",
    caption: [Inside #inline[check_shuffle]: an unconstrained hint, then two constrained passes costing $approx 2N$ prover-chosen reads. Pass 1 is itself an inverse-permutation check applied to the shuffle map, a fact @sub:invperm will use.],
    pseudocode-list(hooks: 0.5em, booktabs: true, booktabs-stroke: 1pt)[
      + *procedure* #fn[check_shuffle]$(cycle, sorted)$ #h(1fr)
        - #lc[unconstrained: find $idx$ with $cycle[i] = sorted[idx[i]]$]
        + $idx[rng(0, N-1)] arrow.l$ #fn[find_shuffle]$(cycle, sorted)$
        - #hide("")
        - #lc[pass 1 --- $idx$ is a permutation of $rng(0, N-1)$ (no slot reused)]
        + *for* $v$ *in* #fn[range]$(0, N)$:
          + $p arrow.l$ #fn[index_of]$(v, idx)$ #h(1fr) #lc[unconstrained]
          + *require* $idx[p] = v$
        - #hide("")
        - #lc[pass 2 --- the map carries $cycle$ onto $sorted$]
        + *for* $i$ *in* #fn[range]$(0, N)$:
          + *require* $sorted[idx[i]] = cycle[i]$
    ]
  ) <fig:check-shuffle>
]

Now the two accounts, kept apart as the section's convention demands. Off-circuit, the prover pays twice: once for the quicksort itself, and once for discovering the shuffle map, which the listing writes as a scan per value. That is real work performed at every proof, with not a line of it constrained. In-circuit, the work is: $N-1$ ordering comparisons (check (b), paid for the reason just given), about $2N$ prover-chosen reads (check (c)), and the $N$ identity equalities of check (d), which sit at fixed positions and by the convention of this section stay off the account. On memory, the whole check is already lighter than the tick sheet: it only ever _reads_ its arrays, never writes them, so it lives in read-only memory (ROM) rather than read--write RAM, and read-only memory carries no write-consistency argument, which was the most expensive part of the RAM construction. A bonus falls out too: $sorted = 0, dots, N-1$, together with $sorted$ being a rearrangement of $cycle$, already forces every cycle entry into range, so the separate range check that the pairwise and presence circuits needed is here subsumed, for free. What neither account can show, and what @sub:mech-measured will put a number to, is how the two interact: those $approx 2N$ prover-chosen reads, and the off-circuit work behind them, will turn out to cost far more to _solve_ than to count.

#subsection([Supplying the Inverse], label: <sub:invperm>)

Look again at what the sort spent its cost on. The first pass of #inline[check_shuffle] did nothing but prove that a supplied map was a permutation of $0, dots, N-1$. That is _the very thing we set out to prove_, only about the shuffle map rather than the cycle. The sort, in other words, routes the cycle to the identity through an intermediary, the sorted array, and it pays to check both steps: cycle to sorted, then sorted to identity. If the prover could point us straight from the cycle to the identity, the intermediary would disappear, and one of the two steps with it.

That is the inverse-permutation check. The prover supplies a private array $invperm$ where $invperm[v]$ claims the position in the cycle at which node $v$ sits, the inverse of the map the cycle defines. The circuit walks $v$ from $0$ to $N-1$ and checks two things at each step: that $invperm[v]$ is in range, and that the cycle really carries $v$ there, $cycle[invperm[v]] = v$. That is the whole of it (@fig:flat-invperm). Two distinct nodes cannot claim the same position, since one cell cannot hold both, so the positions are forced distinct, and $N$ distinct in-range positions matched to the $N$ values $0, dots, N-1$ make the cycle a permutation. Range is subsumed once more, and the off-circuit work is the shortest a hint can have: one linear scatter, $invperm[cycle[i]] = i$, with no sorting and no searching, against the sort's quicksort and per-value scans.

#[
  #set text(font: "Libertinus Sans")
  #figure(
    kind: "listing",
    supplement: "Listing",
    caption: [The inverse-permutation check: one pass and $N$ prover-chosen reads, the sort with the intermediary removed. The value $v$ serves at once as the array index and the expected value, the saving the implicit identity target allows. Groups 2--3 unchanged.],
    pseudocode-list(hooks: 0.5em, booktabs: true, booktabs-stroke: 1pt)[
      + *circuit* #fn[flat-full-invperm]$(N)$ #h(1fr)
        + *public* $matrix[rng(0, N^2-1)], med T$
        + *private* $cycle[rng(0, N-1)], med invperm[rng(0, N-1)]$ #h(1fr) #lc[hint: $invperm[cycle[i]] = i$, an $O(N)$ scatter]
        - #hide("")
        - #lc[Group 1: _permutation, by a supplied inverse map_]
        + *for* $v$ *in* #fn[range]$(0, N)$:
          + *require* $invperm[v] < N$ #h(1fr) #lc[position in range]
          + *require* $cycle[invperm[v]] = v$ #h(1fr) #lc[read $cycle$ at a chosen position]
        - #hide("")
        - #lc[Group 2 (edge cost) and Group 3 (threshold) exactly as in @fig:flat-pairwise]
    ]
  ) <fig:flat-invperm>
]

The accounts, side by side with the sort's. In-circuit: $N$ range checks and $N$ reads, against the sort's $N-1$ orderings and $approx 2N$ reads. The per-entry guards pair off, range checks against orderings, so the whole of the saving is the step we removed. Where the sort proved a map a permutation (pass one) _and_ that it carried the cycle across (pass two), the inverse check does the first job directly against the cycle and needs no second: one pass, $N$ prover-chosen reads in place of $approx 2N$. Off-circuit: one scan, against a sort and a search. Inverse-permutation is the sort with the intermediary taken out. Its memory is the same read-only ROM, and only the counts differ, on both accounts at once.

One more feature must be named before the price can be understood, because the lightness of this check is not all honest economy. Every permutation check compares the cycle against a _target_ set, and this one's target is _implicit_. Watch the value $v$ in $cycle[invperm[v]] = v$: the same $v$ is at once the _index_ into $invperm$ and the _value_ we expect to find. The two roles fuse into one number only because the target is the contiguous range $0, dots, N-1$, so that a node value can serve directly as an array position. Nothing need be supplied or stored to name the target, because the loop counter spins it out for free. We have seen this device before. It is the tick sheet's addressing trick from @sub:presence#[], where a value addressed a mark cell; here it addresses a slot of the inverse map. The sort, for the record, touches the same free target in its check (d), but uses it only as _data_, as comparison values on the right-hand side, never as an address. Two of our three exact linear mechanisms, then, are built on the same quiet assumption: that the set being checked against is ${0, dots, N-1}$ itself, contiguous and known when the circuit is compiled. What becomes of them when that assumption fails is the hinge of @sub:choosing; we mark the spot. For the flat proof the assumption holds, the saving is real, and of the exact mechanisms inverse-permutation is the leanest on both accounts.

#subsection([From Sets to Polynomials], label: <sub:grand-product>)

The three mechanisms so far are variations on one theme: each proves, _exactly_ and with certainty, that the cycle's multiset of values is ${0, dots, N-1}$. The fourth abandons certainty for something subtler and, as we will see across the rest of this thesis, far more useful. It is worth saying at the outset that at this point in the story, a single flat proof, the grand product is not the rational choice. It is more elaborate than the sort, and it trades away a guarantee for a gamble, in exchange for a benefit that, here, is exactly zero. We introduce it anyway, and now, for two reasons: because it is the next mechanism in the permutation family, and because the benefit it cannot collect at the flat level is precisely the one that decomposition will later make decisive. The reader is asked to file it away. The argument for it begins in @sub:choosing, and the chapters beyond develop it in full.

The idea begins with a reformulation. To say that the multiset ${cycle[0], dots, cycle[N-1]}$ equals the multiset ${0, dots, N-1}$ is to say that the two collections agree, with multiplicity, as _sets of numbers_, with order forgotten. There is a classical way to test multiset equality with a single number. From each side, form the polynomial that collects one linear factor per element, and compare the two polynomials:
$
P(Y) = product_(i=0)^(N-1) (Y + cycle[i]), quad Q(Y) = product_(j=0)^(N-1) (Y + j).
$
Distinct values yield distinct factors, and a product of linear factors determines them uniquely, so $P$ and $Q$ are equal _as polynomials_ if and only if the two multisets coincide: each shared value contributes the identical factor, and any discrepancy leaves a factor unmatched. So the permutation question becomes a question about whether two polynomials are the same.

Checking that two polynomials are identical sounds harder than what we started with, not easier; the saving comes from not checking it everywhere, but only at one point. Evaluate both products at a single field value $X$ and compare the two numbers $P(X)$ and $Q(X)$. If the multisets are equal, the polynomials are identical and the two numbers agree at every $X$. If the multisets differ, the difference $D = P - Q$ is a nonzero polynomial of degree at most $N-1$, and such a polynomial has at most $N-1$ roots in the field. So the two numbers agree only if $X$ happens to be one of those at most $N-1$ unlucky points, out of a field of size on the order of $2^254$. This is the Schwartz--Zippel principle: a nonzero low-degree polynomial is almost nowhere zero, so an identity that holds at a random point almost certainly holds everywhere.

Everything now turns on that word _random_. If the prover could see $X$ before committing to the cycle, a cheater could fix a bogus cycle and then search for one of the $N-1$ roots of its own difference polynomial, and the check would be worthless. So the challenge $X$ must be unpredictable to the prover and yet reproducible by the verifier, with no interaction between them. The standard device for this is the Fiat--Shamir transform, which we treat properly in @sec:fiat-shamir: in place of a challenge drawn by a live verifier, one _derives_ the challenge by hashing the data the prover has already committed to. Here the circuit computes $X$ by hashing the entire cycle with the Poseidon2 hash, chaining $h_(j+1) = H([h_j, cycle[j]])$ across all $N$ entries and folding the result once more into $X$, so that $X$ depends on every node the prover chose. Modeled as a random oracle, the hash returns a value the prover cannot anticipate and cannot steer, fixed once the cycle is fixed. The same $cycle$ array feeds both the hash chain and the products, which is what stops a prover from deriving $X$ from one cycle and running the product over another. With $X$ pinned this way, a wrong multiset survives with probability at most $(N-1) \/ |FF|$, below $2^(-240)$ at every instance size we run, negligible by any standard.

The pseudocode is short, and the shape of the cost is visible in it.

#[
  #set text(font: "Libertinus Sans")
  #figure(
    kind: "listing",
    supplement: "Listing",
    caption: [The grand-product permutation check. The challenge $X$ is hashed from the cycle in-circuit (Fiat--Shamir), then the two multiset polynomials are compared at that single point. Groups 2--3 unchanged.],
    pseudocode-list(hooks: 0.5em, booktabs: true, booktabs-stroke: 1pt)[
      + *circuit* #fn[flat-full-product]$(N)$ #h(1fr)
        + *public* $matrix[rng(0, N^2-1)], med T$
        + *private* $cycle[rng(0, N-1)]$
        - #hide("")
        - #lc[Group 1a: _derive the Fiat--Shamir challenge from the whole cycle_]
        + $h arrow.l 0$
        + *for* $j$ *in* #fn[range]$(0, N)$:
          + $h arrow.l$ #fn[H]$(h, cycle[j])$
        + $X arrow.l$ #fn[H]$(h)$
        - #hide("")
        - #lc[Group 1b: _compare the two products at_ $X$]
        + $lhs arrow.l 1, quad rhs arrow.l 1$
        + *for* $i$ *in* #fn[range]$(0, N)$:
          + $lhs arrow.l lhs dot (X + cycle[i])$
          + $rhs arrow.l rhs dot (X + i)$
        + *require* $lhs = rhs$
        - #hide("")
        - #lc[Group 2 (edge cost) and Group 3 (threshold) exactly as in @fig:flat-pairwise]
    ]
  ) <fig:flat-grandproduct>
]

Both accounts are short, and one of them is empty. Off-circuit there is nothing at all: no hint, no extra witness. Like the presence check, the prover supplies the cycle and not a value more. In-circuit, the constrained work is linear: $N$ hash invocations for the challenge chain and $2N$ field multiplications for the two products, with no library shuffle and, crucially, no dynamic memory at all. This is the foot of the ladder the section has been descending. The presence check needed read--write RAM; the sort and inverse checks dropped to read-only ROM; the grand product asks for no prover-chosen memory whatever. Every array index in @fig:flat-grandproduct is a compile-time constant, so the whole check is straight-line, statically-indexed arithmetic, which, we will find in @sec:witness-inversion, is the property that makes it cheap to _run_ even where it is not cheap to count. As with the exact mechanisms, the range check comes for free: a multiset equal to ${0, dots, N-1}$ has all its entries in range by definition.

What sets this mechanism apart is not its gate count, which is comparable to the others, but what it does to the proof's soundness. The first three mechanisms are _exact_: when they pass, the cycle _is_ a permutation, full stop, with the certainty of an algebraic identity. The grand product is _probabilistic_: when it passes, the cycle is a permutation _unless_ the prover was astronomically lucky with the challenge, and the guarantee rests on modeling the hash as a random oracle. We have traded a structural certainty for a computational one. At the flat level this is a pure loss: we pay in soundness and receive nothing, since the public surface is already as small as it can be. The reason to make the trade lies further on, when the cycle is cut into segments and each segment must publish a fingerprint of its share of the partition. There, the grand product's single field element will collapse a per-segment surface that the sort would leave linear, and the trade turns favorable. That argument opens at @sub:choosing and becomes the spine of @chap:hierarchical; @sec:representation takes the first step in the same effort against the public surface, committing the matrix down to a single root. For now we have only loaded the gun.

#subsection([The Mechanisms, Measured], label: <sub:mech-measured>)

@fig:perm-mechanisms gathers the five mechanisms in the order we met them, one row apiece, both accounts spelled out, together with the two structural columns the section has been quietly filling in. Read down the memory column and the story so far is there: the quadratic pairwise check; the presence check on read--write RAM; the sort and inverse refinements stepping down to read-only ROM; the grand product asking for no prover-chosen memory at all, and standing apart in the soundness column too, where exact certainty gives way to a probabilistic argument. The target column records the quieter observation, twice marked and not yet used: two of the mechanisms address arrays by node value and so carry their target built into their own geometry, while the sort takes its target as plain comparison data and the grand product compresses any multiset into a single field element. That column does no work in this subsection; it is the hinge of the next one.

#figure(
table(
  columns: 6,
  align: (left, left, left, left, left, left),
  table.header([*mechanism*], [*in-circuit work*], [*off-circuit work*], [*memory*], [*target*], [*soundness*]),
  [pairwise], [$N$ range checks, $N(N-1) \/ 2$ pairs], [inverse per pair], [---], [implicit (range check)], [exact],
  [presence], [$N$ range checks, $approx 3N$ RAM ops], [none], [RAM (dynamic)], [implicit (value as address)], [exact],
  [sort], [$N$ comparisons, $approx 2N$ reads], [sort + shuffle map], [ROM (dynamic)], [as data (any array)], [exact],
  [inverse-perm.], [$N$ range checks, $N$ reads], [inverse map (one scan)], [ROM (dynamic)], [implicit (value as address)], [exact],
  [grand product], [$N$ hashes, $2N$ multiplications], [none], [none (static)], [any (one field element)], [probabilistic],
),
caption: [The five permutation mechanisms for Group 1, in order of presentation. The first four are exact; the grand product trades exactness for a probabilistic argument (Schwartz--Zippel over a Fiat--Shamir challenge), and uniquely uses no dynamic memory. As the section's convention requires, the two cost columns are lists, not sums: their items carry different gate prices, since a hash invocation weighs far more than a read or a comparison, so lists of different lengths do not rank the mechanisms; @fig:mech-measured does. Read down the memory column for the story of the section, and down the target column for the hinge of @sub:choosing.],
) <fig:perm-mechanisms>

The counts cannot rank the four linear mechanisms; measurement can. The protocol is this section's discipline made physical: four circuits, pairwise, presence, sort, and inverse-permutation, identical in Groups 2 and 3 and in every input, differing only in Group 1, compiled and proven over the full-matrix representation at sizes up to $N = 500$ (the pairwise--sort pair, on to $N = 1000$), five runs per point. (The grand product sits this round out deliberately: its measured comparison is staged in @sec:witness-inversion, against the sort, in the committed-matrix representation of @sec:representation#[], one controlled experiment at a time. Nothing below would change with it present; its distinction, as we said, was never its cost.) The metrics are the set we use throughout the thesis: gate count, witness-generation time, proving time, proof size, and peak prover memory.

One implementation note is needed before the numbers can be read fairly, because gate counts are sensitive to it: types. Node indices and positions are unsigned 32-bit integers (#inline[u32]). They range over $0, dots, N-1$, comfortably within $32$ bits for every instance we consider, and keeping them narrow keeps the range checks cheap. Edge costs are #inline[u64], wide enough that a sum of $N$ edge costs cannot overflow even at our largest $N$. The presence array is #inline[bool], the natural type for a tick sheet and the one that compiles to the lightest RAM cells. The grand product, by contrast, works in the native field type (#inline[Field]): its challenge is a hash output and its products are field elements, quantities that live in $FF$ and have no business being range-constrained to $32$ or $64$ bits. The rule throughout is to use the narrowest type that holds the value, because every surplus bit is a constraint the prover pays for, and to step up to #inline[Field] exactly when the arithmetic is genuinely field arithmetic, as the hash chain and the products are.

@fig:mech-measured holds the headline numbers at $N = 500$; @fig:mech-witness-plot traces the trends across the sweep. Three readings, in order of how much they surprise.

#figure(
table(
  columns: 6,
  align: (left, right, right, right, right, right),
  table.header([*mechanism*], [*gates*], [*vs. sort*], [*witness (s)*], [*vs. sort*], [*prove (s)*]),
  [pairwise], [2 072 578], [+13.3%], [2.76], [+66%], [23.9],
  [presence], [1 827 838], [−0.04%], [1.23], [−26%], [20.9],
  [sort], [1 828 579], [---], [1.67], [---], [21.4],
  [inverse-perm.], [1 825 580], [−0.16%], [1.21], [−27%], [20.9],
),
caption: [The four exact mechanisms head to head at $N = 500$, full-matrix representation, means over five runs. Proof size is $14 656$ bytes for all four; peak prover memory ranges $2.5$--$2.9$ GB. Gate counts are deterministic; times carry run-to-run noise of a few percent.],
) <fig:mech-measured>

The first reading is the one the tallies already promised: the exponent decides, and pairwise retires. Against the sort it starts ahead: at $N = 8$ the sort circuit is marginally _larger_ ($3505$ against $3472$ gates), the linear machinery's fixed overhead not yet repaid by so short a list. But by $N = 104$ it trails by some ten thousand gates, and at $N = 1000$ by nearly a million, a gap that grows like $N^2$ because it _is_ the quadratic: the $N(N-1) \/ 2$ pair gadgets, at about two gates apiece, that the linear mechanisms took off the account. Its witness is worse still, two-thirds slower than the sort's at $N = 500$ and widening, dragged down by the quadratic load of unconstrained inversions on its off-circuit account. The lesson is the expected one stated precisely: the asymptotically better mechanism wins, but only once $N$ is large enough to pay off its constant overhead. There is also one that is easy to miss: the most instructive number in pairwise's row is how _small_ its penalty looks. Thirteen percent, for a quadratic mechanism, because the representation it sits in is itself quadratic. The $N^2$-entry cost matrix dominates every row of this table, and mechanism differences ride on top as small perturbations. The table is quietly answering a question we have not asked yet: of the two questions that closed @sec:proof-anatomy, the second is worth more than the first.

The second reading is the near-tie, and it is exactly why this section refused to rank mechanisms by their item counts. The three linear mechanisms land within $0.16$ percent of one another on gates, a spread of six gates per node between the leanest and the heaviest, though their accounts read $approx 2N$, $approx 3N$, and $approx 4N$ items. Had item counts decided, presence would have placed last; measured, its $4N$ operations ride on featherweight boolean cells and land it second, a few hundred gates _under_ the sort, whose reads and comparisons cost more apiece. The items are simply not priced alike, and in this representation all of them together are a thin slice of a circuit the shared cost-matrix machinery dominates. Proving time, proof size, and peak memory follow the gates, as they must: the trio proves within three percent of one another, produces byte-identical proofs, and peaks within five percent on memory. By every meter the verifier or the proving system sees, the three exact mechanisms are interchangeable.

The third reading is the one that breaks the tie, and it is the first appearance of a finding this thesis will keep returning to. Witness-generation time separates the trio cleanly: from $N = 100$ up, inverse-permutation solves twenty-two to thirty-one percent faster than the sort, and presence, after a slower start, converges to the same advantage as $N$ grows, at gate counts that differ by a rounding error. The ranking does not follow the gates; it follows the _other_ numbers on the accounts: the count of prover-chosen reads the witness solver must resolve, and the off-circuit work behind the hints. The sort pays $approx 2N$ dynamic reads where the inverse check pays $N$, and pays a quicksort and a search for its hint where the inverse check pays one scan. Presence pays no hint at all, and its RAM traffic, for all the weight of the consistency argument in gates, proves cheap to _solve_. Even the retired pairwise check obeys the rule in its broader form, its witness the slowest of all under a quadratic load of unconstrained inversions that no gate records: _witness time tracks the work the circuit does not see._ Gate count and witness-solving cost, we conclude for the first time and not the last, are different things. The finding gets a section of its own (@sec:witness-inversion), where the clean two-point experiment, sort against grand product with everything else fixed, gives it its sharpest form. What the four-way comparison adds is that the effect is _graded_, visible already inside the exact family, scaling with exactly the quantities the gate meter ignores.

So the measurements return a verdict, and it is worth stating honestly before we override it: if cost decided, we would carry inverse-permutation, fewest gates by a nose, fastest witness, both accounts the shortest, with presence a whisker behind and the sort third of three. We are about to carry the sort and the grand product. The case is the business of the next subsection, and not a single row of this table is what makes it.

#subsection([Choosing for the Road Ahead], label: <sub:choosing>)

Why not simply take the measurements' word? For two reasons, one small and one structural. The small one: a verdict by a nose among near-ties is barely a verdict. The trio's gate spread is a rounding error, and the witness advantage, real as it is, separates mechanisms that agree on everything else. The structural one is the reason this subsection exists: cost was never the right criterion, because this circuit is not the product. It is the _baseline_ of a comparison. The program of this thesis, set out in @sec:research-questions, is to cut this proof into $K$ independent segment proofs and study what the cutting buys and costs. The flat circuit's job, from @chap:hierarchical onward, is to be the control everything else is measured against. So a mechanism should be chosen not by its weight here, but by whether it survives the cut.

Start with what cost savings can and cannot buy, because the scalability question makes the point bluntly. Every number in @fig:mech-measured is a constant factor on a circuit that grows with $N$, quadratically in this representation, and still without bound after @sec:representation commits the matrix away. The prover's memory grows with the circuit: at $N = 500$, proving any of the four already peaks between two and a half and three gigabytes. Somewhere up the axis, every flat circuit meets the same wall, an instance too large for one prover to hold, and a permutation mechanism cannot move that wall by more than its share of the circuit, a share we have just measured in fractions of a percent. Choosing the cheapest mechanism is choosing to hit the wall a rounding error later. The only way to move the wall itself is to make each _proof_ smaller: cut the cycle into $K$ segments, prove each on its own, and reassemble the guarantee, which is the program of @chap:hierarchical. The criterion this hands us is not _which mechanism is cheapest here_, but _which mechanisms survive the cut?_ A second, quieter constraint points the same way: whichever mechanism the decomposed constructions carry, the flat baseline must carry the same one, or every later flat-versus-decomposed comparison would change two variables at once, the same one-variable discipline this section has been practicing, applied to the chapters ahead.

What does the cut change, exactly, for a permutation check? One thing, and we have been marking it for three subsections: the _target_. Every mechanism in this section proves that an array of values matches a target multiset, and at the flat level that target is the friendliest one imaginable, the contiguous range ${0, dots, N-1}$, known when the circuit is compiled, produced entry by entry from a loop counter, free to name and, for two of our mechanisms, free to use as an address. A segment of a decomposed proof enjoys none of that. It holds an $M$-node piece of the cycle, and the set it must check against is _its own share of the nodes_: an arbitrary $M$-element subset of ${0, dots, N-1}$, different for every instance, known only to the prover. And it must moreover _publish_ a fingerprint of that share, because the layer that reassembles the $K$ segment proofs has to verify that the shares are disjoint and together exhaust the nodes. Why publication is forced, and what it costs in privacy, is the business of @chap:hierarchical; here we need only the fact. The target, in short, stops being implicit and becomes explicit data. Under that one change, the mechanisms of this section meet three different fates.

The presence check does not survive it. Its tick sheet is addressed by node value over the target's domain, the fact we recorded in @sub:presence#[], and an arbitrary subset offers no domain to address. Concretely, a segment has two options, both unworkable. It can keep a sheet over the full global domain, one cell per node in ${0, dots, N-1}$: but then every segment pays for an $N$-cell RAM, and the initialization alone is $N$ writes, so its cost ceases to shrink with $M$, which forfeits the very thing decomposition is for. $K$ provers each doing work proportional to $N$ is the flat proof multiplied, not divided. Or it can try a dense $M$-cell sheet over its own subset: but addressing that sheet means mapping each node value to its slot in an arbitrary set, the map must come from the prover as a hint, and verifying a supplied position map is precisely the shuffle machinery of @sub:sort#[]. The tick sheet has collapsed into the sort with extra steps. The clipboard check exists only while values can serve as addresses; explicit targets revoke that privilege.

Inverse-permutation survives, but not as itself. Nothing stops a segment from supplying an inverse map against its published share: the share arrives as a sorted array (strictly increasing, which buys its distinctness for $M-1$ comparisons), and the map claims each published value's position in the segment's piece. But look at what happened to the account. The value-as-address fusion is dead, since the published array, not the loop counter, now names the targets, and that published artifact is the _sorted node set_: the very object the sort-based segment publishes, the same size, the same disclosure, the same read-only memory underneath. The check arrives at the segment level as the sort's _twin_, distinguishable only by its halved count of dynamic reads. That residue is real, the law of @sec:witness-inversion does not stop holding, and nothing about the constructions ahead removes the reads. But it is a constant-factor edge on a mechanism otherwise identical to one we already hold, a midpoint on a line whose endpoints, the sort's $approx 2N$ reads and the grand product's none, we are about to carry anyway. A midpoint settles no question the endpoints leave open.

The sort survives unchanged, and that is its entire case. "Organize and inspect" never asked who the target was: check (d) compares the organized array against a list of expected values, and whether that list is produced from a loop counter or read from a published input changes the comparison's right-hand side and nothing else. One mechanism, one form, any target. The uniformity pays a second time at the recombining layer: the statement to check there is that $K$ published shares, each already sorted, together tile ${0, dots, N-1}$, and that statement _is_ a sort, of the concatenated shares against the identity. The mechanism reproduces itself one level up; the global check is the local check at scale.

And the grand product is what the cut was waiting for. Its fingerprint of a multiset is a single field element whatever the multiset, and, decisively, multiset union becomes _multiplication_ of fingerprints. Let each segment publish the product taken over its own share, $P_i$, the product of $(X + v)$ over its nodes $v$. The recombining layer then checks $P_1 dot P_2 dot dots.c dot P_K = product_(v=0)^(N-1) (X + v)$, which is $K$ field multiplications against the one target that is free at every level, the global identity. No segment ever writes down its share; no layer ever re-organizes $N$ values; the local work _aggregates_ instead of being redone, because products of products are products. Sorted lists, by contrast, do not concatenate into sorted lists, so the sort's recombiner must take up all $N$ values again, in sequence. The per-segment public surface falls from the sort's (and the twin's) $M$-element array to one element. Two honesty notes, both with costs charged elsewhere: making $K$ segments agree soundly on the single challenge $X$ is a genuine construction, built in @chap:hierarchical, not a free generalization of @fig:flat-grandproduct; and a published $P_i$, small as it is, is not thereby _private_, so what it leaks, and what it costs to close the leak, are questions for the same chapter. We are choosing a mechanism here, not yet certifying its privacy. At the flat level, we said, the grand product's benefit is exactly zero; this is the benefit, named at last, and the soundness cost of @sub:grand-product remains its standing price.

So the choice writes itself, and for the first time in the section it is not close. We carry the _sort_: the canonical exact mechanism, standard-library-backed, the one member of its family whose form is indifferent to its target and therefore identical at every level we will build. And we carry the _grand product_: the only probabilistic mechanism, no extra witness, no dynamic memory, and the only fingerprint that stays a single field element as the construction grows. For the record, because honesty about near-misses is cheap: inverse-permutation could follow as the sort's twin, and carrying it instead would change no claim ahead, a somewhat faster witness on the same surface, the same soundness, the same side of every divide this thesis draws. What it would not do is stake out any position the sort and the grand product do not already hold between them. As for the accounts and the measurements that occupied most of this section: they did not make the choice, and that was the point of making them. They are what lets us _read_ everything that follows. We now know what a RAM cell, a prover-chosen read, and a hash invocation actually cost, in gates and in solving time, and on which account. So when a later chapter changes one variable and the meters move, we will know which item did it. The costs were the anatomy lesson; the road ahead made the choice.

The two survivors are worth holding side by side as the section closes, because the contrast between them is the sharpest the thesis can draw, and it recurs at every turn. They sit on opposite sides of nearly every axis. The sort is exact, the grand product probabilistic. The sort leans on dynamic, prover-chosen reads; the grand product is pure straight-line arithmetic. The sort's published artifact, once publishing begins, will be a node set; the grand product's a single field element. And, the twist the measurements have already hinted at, the one that looks cheaper on paper will turn out not to be the one that is cheaper to run. That inversion is a result in its own right, and we give it its own treatment, with the controlled experiment it deserves, in @sec:witness-inversion. First, though, we turn to the second of the two questions left open at the end of @sec:proof-anatomy: the cost matrix, all $N^2$ entries of it, still sitting in the public inputs.

#section([Committing to the Matrix], label: <sec:representation>)

We now take up the second question. Every circuit so far hands the verifier all $N^2$ entries of the cost matrix as a public input, and that is a problem on two fronts. This section names both, fixes them with a single change of representation, and then looks closely at the one check that makes the fix sound.

The first problem is cost. A public input is not free: each one the verifier supplies costs the circuit a few gates, and there are $N^2$ of them. Only $N$ edge costs are ever read, yet the whole matrix is handed over, so the public surface grows with the square of $N$. We saw the effect in @sub:mech-measured. At the sizes we measured, the $N^2$-entry matrix dominates every circuit, and the permutation mechanism we worked so hard to choose rides on top as a perturbation of a fraction of a percent.

The second problem is privacy. Publishing the matrix means publishing the graph: every edge cost, for every pair of nodes, in the clear. In the freight-carrier setting of @sec:motivation that is the carrier's entire cost structure, which is exactly the kind of thing she would want to keep to herself. Hiding the route is little comfort if the map it runs on is public. Our circuits so far hide the cycle and its cost but expose the matrix completely, and we would like to hide that too.

Both problems have the same source, and the same fix. The trouble is that we hand the verifier the whole matrix, so we stop doing that. Instead of publishing the matrix, we _commit_ to it: we reduce the whole table to a single short value, publish only that value, and have the prover show that each edge cost it uses is consistent with the committed table. The verifier now holds one field element in place of $N^2$, and the matrix itself never appears in public. The commitment we use is a _Merkle tree_, built with the Poseidon2 hash.

The construction is standard. Recall from @sec:proof-anatomy that we already store the matrix as a flat array of $N^2$ entries, with the cost of the edge from node $i$ to node $j$ at index $i dot N + j$. Those entries are the leaves of the tree, padded with zeros up to the next power of two. We hash the leaves together in pairs, each pair giving one parent, with $H$ the Poseidon2 hash; then hash the parents in pairs, and so on up, halving the count at every level until a single node remains at the top. That top node is the _root_. The number of levels from a leaf to the root is the tree's depth, written $DEPTH$; since the tree is built over $N^2$ leaves, $DEPTH$ is about $2 log_2 N$. The root is the single public value that now stands in for the matrix. Change any one entry and the root changes, because the change travels up every level on that entry's path, so the root is a binding commitment to the whole table.

Publishing the root settles the verifier's side: one value instead of $N^2$. But it moves work onto the circuit. The circuit can no longer look an edge cost up in a public table, because there is no public table any more. Instead, the prover supplies each edge cost as a private input and proves, in the circuit, that the value it supplied really is the one the root commits to at that position. This is the hint trick again, on a larger object: the prover hands in not just the cost but a short certificate that it sits at the right place in the committed tree, and the circuit checks that certificate.

The certificate is the _Merkle proof_. For a given leaf it is the list of sibling nodes met on the way up to the root, one per level, $DEPTH$ in all. Given the leaf value and those siblings, anyone can replay the hashing: combine the leaf with its sibling to get the parent, combine that with the next sibling, and so on up. If the value and its siblings are genuine, the replay lands on the published root. If the prover lies about the cost, the replay lands somewhere else, and matching the real root would mean finding a Poseidon2 collision, which we assume is infeasible. So the prover supplies, for each of the $N$ edges, its cost, the $DEPTH$ sibling hashes, and the $DEPTH$ direction bits that say whether each step combines the running value on the left or on the right. The circuit replays the hash and requires the result to equal the root.

There is a gap in that argument, and closing it is the most important line in the section. Replaying the hash proves that the supplied cost sits at _some_ leaf of the committed tree. It does not prove the cost sits at the _right_ leaf. A dishonest prover could take a genuine, correctly-hashing proof for some cheap entry elsewhere in the matrix and present it for an edge that is in fact expensive. The hash check would pass, the root would match, and the prover would have charged a price the graph never set.

What pins the proof to the right leaf is the position. The direction bits do double duty: read as a binary number, least significant bit first, they _are_ the index of the leaf the proof opens. And we know exactly which index this edge must open, because we chose the layout: the edge from $cycle[i]$ to $cycle[(i+1) pmod N]$ lives at index $cycle[i] dot N + cycle[(i+1) pmod N]$, the very address from @sec:proof-anatomy. So the circuit reconstructs the index from the direction bits and requires it to equal that expected address. With this check in place, a passing proof certifies both things at once: the cost is in the committed matrix (the hash), and it is at the position this edge demands (the index). Drop the check and Group 2 means nothing; keep it and the binding is complete. One could instead fold the position into each leaf, hashing the index alongside the cost so that a proof for the wrong place simply fails to hash; we keep the leaf as the raw cost and make the index check explicit, which keeps both the leaf's meaning and the soundness step in plain view.

#[
  #set text(font: "Libertinus Sans")
  #figure(
    kind: "listing",
    supplement: "Listing",
    caption: [The flat-Merkle circuit's Group 2: each edge cost is bound to the committed root by one Merkle proof. The prover supplies the cost, the $DEPTH$ sibling hashes, and the $DEPTH$ direction bits as a hint; the circuit checks the bits encode the right leaf index (a), replays the hash up to the root (b), and accumulates (c). Group 1 is the sort of @fig:flat-sort; Group 3 is the threshold of @fig:flat-pairwise.],
    pseudocode-list(hooks: 0.5em, booktabs: true, booktabs-stroke: 1pt)[
      + *circuit* #fn[flat-merkle-sort]$(N, DEPTH)$ #h(1fr)
        + *public* $root, med T$
        + *private* $cycle[rng(0, N-1)], med edgecosts[rng(0, N-1)],$
        + #h(2.4em) $siblings[rng(0, N dot DEPTH - 1)], med pathbits[rng(0, N dot DEPTH - 1)]$ #h(1fr) #lc[hint: $N$ Merkle proofs]
        - #hide("")
        - #lc[Group 1: _permutation, by the sort of_ @fig:flat-sort]
        - #lc[Group 2: _edge cost, by one Merkle proof per edge against_ $root$]
        + $total arrow.l 0$
        + *for* $i$ *in* #fn[range]$(0, N)$:
          - #lc[(a) leaf-index check: the proof must open this edge's cell]
          + $leafidx arrow.l 0$
          + *for* $d$ *in* #fn[range]$(0, DEPTH)$:
            + *if* $pathbits[i dot DEPTH + d]$: $space leafidx arrow.l leafidx + 2^d$
          + *require* $leafidx = cycle[i] dot N + cycle[(i+1) pmod N]$
          - #lc[(b) replay the hash up the path; the result must be the root]
          + $node arrow.l edgecosts[i]$
          + *for* $d$ *in* #fn[range]$(0, DEPTH)$:
            + *if* $pathbits[i dot DEPTH + d]$: $space node arrow.l$ #fn[H]$(siblings[i dot DEPTH + d], node)$
            + *else*: $space node arrow.l$ #fn[H]$(node, siblings[i dot DEPTH + d])$
          + *require* $node = root$
          - #lc[(c) accumulate the verified cost]
          + $total arrow.l total + edgecosts[i]$
        - #hide("")
        - #lc[Group 3: _threshold, exactly as in_ @fig:flat-pairwise]
        + *require* $total <= T$
    ]
  ) <fig:flat-merkle>
]

@fig:flat-merkle shows the resulting Group 2; Group 1 is the sort of @fig:flat-sort and Group 3 the threshold check, both unchanged. Now the trade. We have removed $N^2$ public inputs and the direct matrix lookup, and put in their place $N$ Merkle proofs, each $DEPTH$ Poseidon2 hashes tall. The new cost is therefore about $N dot DEPTH$ hash invocations, which grows like $N log N$. We have traded a quadratic public surface for a near-linear pile of in-circuit hashing.

Whether that is a good trade depends on $N$. At small $N$ the matrix is tiny and the hashing is pure overhead, so the public-matrix circuit is cheaper. As $N$ grows the quadratic surface overtakes the $N log N$ hashing, and the committed circuit pulls ahead. There is a crossover between the two; we locate it precisely in @sec:flat-eval, and here it is enough to know that one exists and which side of it each circuit wins on.

The privacy problem falls away at the same time, and at no extra cost. The matrix is no longer in the public inputs at all; only its root is. The root is a hash, so it reveals nothing about the entries that produced it, and the edge costs the prover uses are private witness like everything else. The committed circuit hides the matrix, the route, and the cost together. The public-matrix circuit hides only the route and the cost.

One piece of fine print belongs here, though we develop it properly in @sec:prob-formulation. Committing to the matrix proves the prover used costs consistent with _a_ matrix, the one behind the root. It does not prove that matrix is the _real_ one. A prover who commits to a matrix of all zeros can honestly prove a zero-cost tour. Binding is not authenticity: the root ties the proof to a fixed table, but something outside the proof, a signature from a trusted authority or a published reference root, must vouch that the table is the right one. We flag the distinction here and return to it with the threat model.

Two alternatives are worth naming before we move on. The first is to commit with a vector commitment that opens in constant size, such as a KZG or Verkle commitment, instead of a Merkle tree whose openings grow with $DEPTH$. The opening would be shorter, but verifying it inside the circuit means doing elliptic-curve pairing arithmetic in the circuit, far more expensive than Poseidon2 hashing, and it brings a trusted setup we would rather avoid. The second, and the stronger one, is to replace the per-edge proofs with a committed-lookup argument, of the kind used by schemes such as cq or Lasso, which prove that all $N$ used costs come from the committed table in one batched argument rather than $N$ separate proofs. This is very likely cheaper than per-edge Merkle proofs, and it is the honest answer to "is this the best you can do". We did not pursue it. The Merkle construction is simple, transparent, needs no setup, and is well supported by the tooling, which suits a baseline whose job is to be a clean control rather than the last word in efficiency. We name the cheaper road as one we did not take, and return to it as future work in @sec:future-work.

This settles the flat baseline. We carry forward the committed representation together with the sort permutation check of @sec:permcheck, and call the result _flat-sort_: the monolithic circuit that hides route, cost, and matrix behind a single root and a single threshold, and proves the whole tour in one piece. It is the perfect-hiding baseline, in a precise sense we sharpen later: nothing in its public surface, the root and $T$, says anything about the structure of the tour. Every decomposed construction in the chapters ahead is measured against it, and every one of them will have to work to recover the privacy it gives away for free.

It is worth noting what just happened to the public surface, because it is the first move in a longer campaign. We began this chapter with $N^2$ public matrix entries and have reduced them to a single root. That is the same reduction the grand product promised for the partition back in @sub:grand-product, when we loaded the gun: a large public object collapsed to one field element. Here the object is the matrix; there it will be each segment's share of the nodes. The committed matrix is where that idea first pays off, and it is the representation the controlled comparison of @sec:witness-inversion runs in. With the construction settled, we turn next to how it is built and run (@sec:tooling), before returning, in @sec:witness-inversion, to the comparison the choice of permutation mechanism left unfinished.

#section([From Instance to Proof], label: <sec:tooling>)

We have said what each circuit proves. This section describes how the circuits are actually built, fed, and measured, because the numbers in this thesis are only as trustworthy as the pipeline that produced them. The pipeline has three stages: make a problem instance, turn it into a witness, then prove it and record what the proving cost. One detail cuts across all three and earns its own paragraph: the matrix commitment is computed in one language and checked in another, and the two must agree exactly. We take the stages in turn, then the cross-language seam, then the one assumption that lets us reuse a single instance per size. Full source listings are in Appendix A; here we keep to the shape and the choices.

Each variant is its own Noir package: the flat circuits of this chapter, and the hierarchical and recursive ones of the chapters to come. The size $N$, and for the committed circuits the tree depth $DEPTH$, are compile-time globals. This is forced, not a convenience. An arithmetic circuit is fixed before any witness exists (@sec:snarks), so its loops unroll and its array sizes settle at compile time, which means a circuit for $N = 8$ and a circuit for $N = 1000$ are two different circuits, not one circuit run on two inputs. The harness therefore patches $N$, and $DEPTH$ where it applies, into the source and recompiles for every size it measures.

An instance is a complete weighted graph. We build one by placing $N$ points uniformly at random in a square grid and taking the integer-scaled Euclidean distance between each pair. The generator is seeded, so a given size always yields the same instance. To get a cycle to prove, we run a solver: nearest-neighbor construction followed by 2-opt local search, a few dozen lines of dependency-free Python. The solver does not need to be good. We are proving _feasibility_, that a cycle exists under the threshold, not _optimality_, that it is the cheapest one, a distinction we return to in @sec:prob-formulation. Any valid Hamiltonian cycle whose cost falls under the threshold is a complete witness, so a cheap heuristic is exactly the right tool, and its suboptimality costs the proof nothing.

Turning an instance and a cycle into the `Prover.toml` the proving stack reads depends on the representation. For the public-matrix circuits a short Python script writes the witness directly: the cycle as a private array, the whole matrix as a public array, the threshold as a public scalar. For the committed circuits the work moves to a small Rust program, the Merkle builder. It builds the Poseidon2 tree over the $N^2$ matrix entries (@sec:representation), and for each edge of the cycle it reads off the cost, the $DEPTH$ sibling hashes, and the $DEPTH$ direction bits, writing them out as private witness alongside the public root and threshold. The tree is built in Rust for two reasons: it costs $N^2$ Poseidon2 hashes, too slow in Python at the sizes we reach, and it is the same tree for every variant and every run on a given instance. So the builder serializes the tree to disk and reloads it on later calls, paying the quadratic build only once.

That split puts a hash function on both sides of a trust boundary. The root the verifier accepts is computed by the Rust builder, while the proof that each edge cost matches that root is checked inside the Noir circuit. The two never compare notes at run time, so their two Poseidon2 implementations must produce bit-for-bit identical output, or honest Merkle proofs would simply fail to verify. We pin this with a compatibility test that runs the same inputs through both and checks they agree, for the two-input compression that builds internal nodes and for the one-input form that folds the Fiat--Shamir challenge. It is a small test guarding a quiet but total failure mode: a one-bit disagreement between the languages would break every committed proof at once.

A single driver runs each size end to end. It patches and recompiles the circuit, builds the witness, then times the three stages the proving stack performs, witness generation (#inline[nargo execute]), proving (#inline[bb prove]), and verification (#inline[bb verify]), recording the gate count, the proof size, and peak memory as it goes. Results are written to a CSV one row at a time, so a sweep that runs for hours never loses what it has already measured. The metrics are the set used throughout the thesis and defined in @sec:metrics: the gate count (#inline[circuit_size]), the three times (#inline[witness_s], #inline[prove_s], #inline[verify_s]), the proof size (#inline[proof_bytes]), and peak prover memory (#inline[peak_mb]).

One choice in the harness is worth defending, because every averaged number in the thesis rests on it. We use a single instance per size, reused across all variants and all repeated runs, rather than a fresh random instance each time. This is sound because SNARK proving is _data-oblivious_. For a fixed circuit, the gate count, the proof size, and the peak memory do not depend on the witness values at all; they are properties of the circuit, which is the same whatever cycle we feed it. Only the times depend on the input, and only weakly, through system noise rather than through the data. So repeated runs on one instance measure exactly the run-to-run noise we want an average to smooth, and nothing is lost by holding the instance fixed. Checking that the circuits accept _valid_ witnesses and reject _invalid_ ones is a separate, correctness question, handled by a separate test suite and not by the benchmark. We come back to this when we read the results in @sec:fairness.

To make the pipeline concrete, take the smallest committed instance, $N = 8$. The matrix has $64$ entries, which is already a power of two, so the tree has $64$ leaves and depth $DEPTH = 6$. The builder hashes the matrix to a single root and, for the eight-edge cycle the solver returns, emits eight edge costs, each with its six sibling hashes and six direction bits, together with the root and the threshold. Witness generation fills in the rest, proving produces a proof of $14656$ bytes, and verification accepts. That proof size is worth a glance, because it is exactly the size we will see at $N = 1000$ and $N = 4000$ as well. The circuit behind it grows from about seven thousand gates here to over eight million there, the witness and proving times grow with it, and the proof itself does not move. That is succinctness, made concrete on the smallest case we run.

With the pipeline in place, the flat circuits are built, fed, measured, and trusted. One piece of the chapter is still owed: the comparison @sec:permcheck set up and deliberately left open, between the two mechanisms we chose to carry. We close the chapter with it.

#section([The Witness-Time Inversion], label: <sec:witness-inversion>)

In @sec:permcheck we chose two permutation mechanisms to carry forward, the sort and the grand product, and we left the section on a warning: the one that looks cheaper on paper is not the one that is cheaper to run. We can now make that precise. This section is a single controlled experiment, the cleanest the chapter can run, and it settles a question the gate count alone answers wrongly.

The two circuits we compare are flat-sort and flat-product, both in the committed representation of @sec:representation. They are built to differ in exactly one place. Group 2, the Merkle edge-cost check, is byte-for-byte identical in both. Group 3, the threshold, is identical too. They take the same private witness, the same cycle and the same Merkle proofs, and they expose the same public surface, the root and $T$. The only difference between them is Group 1: one proves the permutation by sorting, the other by the grand product of @sub:grand-product. So whatever the meters show when we run them, the difference is the work of the permutation mechanism and nothing else. This is the one-variable discipline of @sec:permcheck applied to its sharpest pair, and it is why we waited for the committed representation to run it. In the full-matrix circuits of @sub:mech-measured the $N^2$ matrix drowned every mechanism difference; here the matrix is a single root, and the difference stands clear.

Start with the gate count, because it sets up the surprise. The grand product compiles to _more_ constraints than the sort, at every size we measured. Its Group 1 carries a piece the sort does not: the hash chain that derives the challenge $X$, one Poseidon2 call per node, laid down as $N$ extra invocations. That is a real addition, and it shows. The grand-product circuit is larger by between three and eight percent, with the gap shrinking as $N$ grows, because the $N$ extra hashes are a fixed overhead that the rest of the growing circuit dilutes. On the gate meter, plainly, the sort is the cheaper circuit.

Now run them, and watch the witness. @fig:witness-inversion holds the numbers. Despite compiling to more gates, the grand product solves its witness _faster_, and not by a margin one could call noise. At $N = 1000$ it is forty-four percent faster; at $N = 3000$, seventy percent. The gap is not fixed either: it starts small, a few percent around $N = 100$, and widens steadily with $N$. The circuit that costs more to describe costs far less to build.

#figure(
table(
  columns: 6,
  align: (right, right, right, right, right, right),
  table.header([*N*], [*sort gates*], [*product gates*], [*sort witness (s)*], [*product witness (s)*], [*witness Δ*]),
  [104], [129 346], [135 787], [0.38], [0.35], [−9%],
  [1000], [1 733 830], [1 795 151], [3.68], [2.05], [−44%],
  [3000], [6 224 830], [6 408 651], [21.0], [6.36], [−70%],
),
caption: [flat-sort against flat-product in the committed representation, means over the runs at each size. The grand product compiles to more gates at every $N$ (+3% to +8%, shrinking with $N$) yet solves its witness faster, by a margin that widens from a few percent near $N = 100$ to $-70%$ at $N = 3000$. Proof size is $14656$ bytes for both circuits at every $N$, and proving time matches to within a few percent: the two share a dyadic bucket, so the difference is confined to the witness step. Gate counts are deterministic; witness times carry a few percent of run-to-run noise.],
) <fig:witness-inversion>

The reason is the distinction we met in @sec:proof-anatomy and have been tracking since: where each Group 1 does its work. The sort's work runs through #inline[check_shuffle], which reads arrays at positions the prover chose, about $2N$ such reads in all. We saw in @sec:proof-anatomy what a read at a prover-chosen position costs. It cannot be wired in advance, so it compiles to a memory-consistency check, and that check is something the witness solver must assemble and resolve at solve time, before any proof can begin. The grand product has none of these. Its Group 1 is straight-line, statically-indexed arithmetic: the hash chain steps through the cycle in order, the two products multiply their factors in order, and every array index is a compile-time constant. The solver simply evaluates it, top to bottom, with no memory log to build. The gates count the constraints in the finished circuit; the witness time counts the solver's work in filling it, and the solver's work is dominated by exactly the dynamic memory the gate count records as ordinary arithmetic. We saw the same effect in milder form in @sub:mech-measured, where the exact mechanisms separated on witness time at gate counts that agreed to a rounding error. This is that effect at full strength, between the two mechanisms we actually carry.

Everything the verifier and the proving system see is unchanged. The proof is $14656$ bytes in both circuits, at every $N$: the two land in the same dyadic bucket, the power of two that UltraHonk pads the circuit up to, so the object that gets proved is the same size. Proving time follows the bucket and matches to within a few percent. Peak memory is close as well, with the sort running a little heavier at the largest sizes, which is itself a faint echo of the same cause, since the dynamic-memory machinery costs the solver some memory as well as some time. The whole of the difference lives in one place: the witness step, on the prover's side, before the proof is made.

The lesson is worth stating plainly, because it runs against the grain of how cost is usually reported in this field. Gate count and witness-solving cost are different things. A circuit can be cheaper to describe and more expensive to build, or the reverse, and this pair inverts them: fewer gates and a slower witness for the sort, more gates and a faster witness for the grand product. Gate count is the headline number in zero-knowledge, the one quoted to compare designs, and here it points the wrong way. It is a standing reminder to ask, before trusting any single number, what that number actually measures.

This is a local finding, and we measured it here, at the flat level, on purpose: it is cleanest before decomposition adds its own costs on top. It does not stay local. When we lay out the full comparison in @sec:factorial, this same gap reappears as the difference a row makes, the cost of the mechanism, which the factorial there separates cleanly from the cost of aggregation. And it adds a second mark to the grand product's account. In @sub:choosing the grand product earned its place on the public surface it will save once the tour is cut into pieces, paid for with a weaker kind of soundness. We can now add that, as $N$ grows, it is also the faster of the two to witness. The mechanism that looked like the elaborate gamble is, in the end, the one that runs lighter.
