#import "/theme/headings.typ": chapter, section, subsection
#import "/theme/colors.typ": colors
#import "/theme/utils.typ": inline, lc, fn

#chapter([Results], label: <chap:results>)

The previous chapter drew a map and promised numbers. It argued, one construction at a time, that the hierarchical proofs occupy a space with three corners and no center---cheap, parallel, structurally private, and never all three at once---and it left the reader with a shape rather than a scale. This chapter supplies the scale. The pick-two triangle of @sub:pick-two is a claim about where each construction sits; what follows is the measurement that pins it there, and the discipline that keeps the measurement honest.

We begin by fixing how the numbers are to be read: three controls, stated once and then applied silently, without which a results chapter misleads as easily by arithmetic as by error (@sec:fairness-controls). We then measure the flat baseline the whole thesis is read against (@sec:flat-eval)---how its circuit grows, what a single hash call really costs, where committing the cost matrix overtakes publishing it, and which of the backend's own numbers quietly mislead. With the baseline in hand we turn to the constructions: their gate counts set against the predictions of @chap:hierarchical (@sec:gates-vs-prediction), their proving time and memory when the segments are spread across machines (@sec:parallel-proving), and a small factorial that separates the price of aggregating from the price of the mechanism (@sec:factorial). We then read the constructions in equal-privacy slices, the only comparisons that are fair (@sec:equal-privacy-results), check the soundness arguments against deliberate cheating (@sec:soundness-validation), and finally draw the frontier the last chapter named (@sec:frontier-figure).

#section([Reading the Numbers Fairly], label: <sec:fairness-controls>)

A results chapter can mislead without a single wrong measurement. It is enough to compare two numbers that should never have been set side by side---a proof that hides the route against one that publishes it, the cost of changing the mechanism against the cost of changing everything at once, a wall-clock that shrank because the construction improved against one that shrank because more machines were thrown at it. Each of these is a fair-looking sentence built on an unfair comparison, and none of them involves an arithmetic mistake. So before any number is read, we fix three controls. They are simple to state and we state them here, at the front, so that the rest of the chapter can apply them without repeating itself.

#subsection([Compare Only Within a Privacy Class], label: <sub:control-class>)

The constructions do not all hide the same thing. @sub:privacy-ladder sorted them into classes by what an adversary learns of the partition: _structural_, where the partition is absent from the proof and hidden on no assumption, as in flat and recursion; _computational_, where it is present but sealed behind a commitment, as in the committed variants; and _disclosing_, where it sits on the surface in plaintext, as in the plain variants. These are not degrees of the same good. A proof that hides the route on no assumption and a proof that discloses it are answering different questions, and the prices they pay buy different things.

It follows that a cheaper number from one class is not a victory over a dearer number from another. The plain variants are cheap precisely because they hide nothing; reading their cost against recursion's and declaring them the winner would be reporting the discount for forgoing privacy as though it were an efficiency. So we never set a cost from one class against a cost from another as if the smaller simply won. Every comparison in this chapter is drawn _within_ a class---structural against structural, computational against computational---and where a cross-class number appears it is there to price the privacy itself, the gap between the classes, and is labeled as such. This is the discipline @sec:equal-privacy-results is built on, and the reason the frontier of @sec:frontier-figure has three corners rather than a single cheapest point.

#subsection([Change Exactly One Thing], label: <sub:control-one-thing>)

Every construction in the thesis is a point on a grid with two axes. One axis is the _regime_: how the proof is bound together---monolithic and whole (flat), or cut into segments and stitched, with the stitch left in the open (plain), sealed under a commitment (committed), or folded into a single recursive verification (recursion). The other axis is the _mechanism_: how the permutation at the heart of the statement is enforced---by sorting the cycle and checking the result, or by reducing it to a single grand-product fingerprint. The regime is the subject of @sec:stitching-tax; the mechanism is the subject of @sec:witness-inversion.

Laid out this way, a cause can be isolated by moving along one axis and holding the other fixed. Step down a _column_---change the regime, keep the mechanism---and whatever the cost does, it did so because the proof is bound differently; the delta is the price of aggregation, and nothing else moved to muddy it. Step across a _row_---change the mechanism, keep the regime---and the delta is the price of the fingerprint, the witness-time-against-gates inversion of @sec:witness-inversion read in isolation. What we do not do is change both at once. The diagonal step---a different regime _and_ a different mechanism---confounds the two prices into a single number from which neither can be recovered, and we treat it as forbidden.

This is not merely a reading convention; it is the discipline the figures of this chapter are drawn to make visible. The visual language fixes hue to the regime and marker to the mechanism, so that a legitimate comparison is one in which only the color changes, or only the marker, and the forbidden diagonal is exactly the step in which both change at once. When a later figure asks the reader to compare two curves, the grammar of the plot already says whether the comparison is a fair one.

#subsection([Report Both Clocks, and Say Which], label: <sub:control-both-clocks>)

The dualism of @sec:dualism established that decomposition conserves the prover's total work: cutting a proof into segments and stitching them never reduces the sum of the gates, it only relocates them and adds a tax for the relocation. And yet the entire motive for decomposing was a gain in time---segments that prove in parallel, each on a machine that need never hold the whole circuit. Both statements are true, and they are true of two different clocks. A single time can therefore flatter a construction or condemn it, depending on which clock the reader is invited to imagine.

So we report two, and we always label which is meant. The _total_ work is the sum of the cost across every piece---segments and stitch together---and it is the clock the dualism speaks to: decomposition never lowers it. The _parallel_ wall-clock is the time to finish when the segments run at once on separate machines, the longest segment plus the stitch that waits on all of them, and it is the clock on which the win actually appears. Conflating the two is the most natural way to claim a speedup the hardware delivered rather than the construction, or to miss one that is genuinely there; reporting only the total hides the parallel gain, reporting only the parallel hides the conserved cost it was bought with. Every timing in this chapter says, in so many words, which clock it stands on, and the wall-clock figures state the composition assumption they rest on---uncontended machines, one segment per prover---rather than leave it implied.

With the three controls fixed---compare within a class, move one axis at a time, name the clock---the numbers can be read without misleading. The first of them is the baseline the rest are read against, and we turn to it now.

#section([The Flat Baseline], label: <sec:flat-eval>)

The flat proof of @chap:methodology is the control: it is the whole statement proved in one circuit, and every construction that comes after is read as some multiple or fraction of it. Before those later numbers can mean anything we have to measure this one, and measure it in a way we can trust. So this section fixes how the measurements were taken, then reads the baseline's two costs in turn---the gates, which set the proving work, and the wall-clock and memory, which decide whether a single machine can carry the proof at all. Two facts surface along the way that bear on the whole thesis: a single hash inside the circuit costs far less than its textbook price, and the memory a flat instance demands runs into a hard ceiling not far past a thousand nodes.

#subsection([How the Baseline Was Measured], label: <sub:flat-setup>)

We sweep the instance size $n$ from $8$ to $4000$ nodes, finely at the small end where the curves bend and in wider steps past a thousand where they have straightened out. At each size the circuit is compiled once and then proved and verified two or three times over, on an otherwise idle machine---a four-core, eight-thread Intel Core i7-1165G7 with $16$ #lc[GB] of memory, running Barretenberg's UltraHonk prover (#inline[bb] $5.0$) behind the Noir compiler (#inline[nargo] beta-$20$). #footnote[The machine's memory ceiling matters for the wall this section ends at; if the benchmark host differs from the one quoted here, only the absolute memory and time figures move, not the scaling.]

Not every number we collect varies the same way, and the chapter reads more clearly once the two kinds are separated. The _structural_ metrics---the gate count, the ACIR opcode count, the proof size---are counted from the circuit rather than timed, and they are exact: across every repeat at every size their variation is precisely zero. The _wall-clock_ metrics---compile, witness, prove and verify time, and peak memory---are readings off a running machine and carry the noise of one, a few percent, largest at the smallest instances where fixed costs dominate and again at the largest where memory pressure does. We treat the two kinds as what they are. A structural count is reported as the single exact value it is; a time is reported as the mean over repeats, with the standing understanding that a two-percent wobble in a prove time is the machine talking, not the construction. When a later comparison turns on a small difference in time we say so plainly; when it turns on a gate count, we can simply be exact.

#subsection([Publishing the Matrix], label: <sub:flat-publish>)

The first cost the prover pays is the cost of the graph itself. The statement is about a weighted graph on $n$ nodes, and the most direct way to put its cost matrix in front of the circuit is to hand the whole thing over: all $n^2$ entries, as public inputs. Call this the _full_ representation. It is the right place to begin because its cost is the cost of the data and nothing more---no commitment, no hashing, just the matrix laid out in the open.

Measured, that cost is a clean quadratic. Across the entire sweep the gate count of the full-matrix flat proof, taken with the sort mechanism, fits

$ "gates"(n) = 7.25 thin n^2 + 26.5 thin n + 2829, quad R^2 approx 1 $ <eq:flat-full-fit>

and the fit is not an approximation that happens to be good---it is the structure of the circuit read back off the data. The leading term counts the matrix. Each of the $n^2$ public entries costs about $7.25$ UltraHonk gates to carry into the circuit, the fixed plumbing of a public input, the same for every entry; and at any appreciable $n$ those $n^2$ entries are the whole story. The linear term is the permutation and threshold work that grows with the tour, and the constant is the scaffolding every proof carries no matter how small.

That the quadratic term is the _matrix_ and not the _mechanism_ is worth pinning down, because the permutation check is the natural suspect for the expensive part, and it is innocent. Trade the sort mechanism for the pairwise one---which enforces the permutation with $n(n-1)$ explicit comparisons, a mechanism that is itself genuinely quadratic---and the leading coefficient moves only from $7.25$ to $8.25$. A quadratic _mechanism_, when one is used, adds a single gate per entry; the published _matrix_ costs seven. This is the column-against-row discipline of @sub:control-one-thing made concrete before we have even left the flat row: the representation of the graph dominates the cost of a flat proof, and the choice of mechanism is a correction on top of it. The lesson points straight at the next move. If carrying the graph in the open is what a flat proof mostly pays for, the first thing any serious construction will do is stop carrying it in the open---and that is the move we measure next.

#subsection([Committing the Matrix], label: <sub:flat-commit>)

To stop publishing the matrix is to _commit_ it. Rather than hand over all $n^2$ entries, the prover hashes the matrix into a single Merkle root, makes only that root public, and proves each cost the circuit needs by exhibiting a Merkle path---the entry, its sibling hashes, and the chain that climbs to the root. The matrix is now private behind one field element, and the circuit no longer pays for $n^2$ public inputs. It pays for hashing instead.

How much hashing is a counting question. Each of the $n$ directed edges in the tour reads one cost from the matrix, and checking that read against the root costs a path of $D$ hashes, where $D = ceil(log_2 n^2)$ is the height of a tree over the $n^2$ leaves. So the dominant cost is $n dot D$ Poseidon2 calls, and since $D$ grows like $2 log_2 n$, the whole proof grows as $O(n log n)$---for the first time the flat statement is proved in sub-quadratic work. The fit confirms the shape and hands us a coefficient worth pausing on:

$ "gates"(n) = 85.75 thin (n dot D) + 16 thin n + 2830, quad D = ceil(log_2 n^2), quad R^2 approx 1 $ <eq:flat-merkle-fit>

That leading coefficient is the price of one Poseidon2 call inside the circuit: about $86$ UltraHonk gates. This is the first of the section's two facts, and it is a surprise, because a single Poseidon2 permutation is usually costed at around $264$ gates---roughly three times what we measure. The gap is amortisation. UltraHonk proves a hash through a lookup argument, and the tables a Poseidon2 needs are built once for the whole circuit and then shared across every call; the fixed cost of standing the tables up is paid by the proof as a whole, and the marginal cost of one more hash is only the few lookups that read them. A circuit with a single hash would see something near the full $264$; a circuit with $n dot D$ of them---past $n = 100$, already tens of thousands---sees the amortised $86$. The committed flat proof is hashing-bound, and its hashing is cheap precisely because there is so much of it. The figure is worth carrying forward, because every committed and hierarchical construction in this thesis is built on Merkle openings, and the price of each opening is this measured $86$, not the textbook $264$.

Set the two representations side by side and their costs decompose cleanly (@tab:flat-cost): the full proof pays $7.25$ gates on each of $n^2$ matrix entries, the committed proof about $86$ on each of $n dot D$ hashes. A heavier coefficient on a lighter count---and which product is smaller depends entirely on $n$.

#figure(
  caption: [The two flat representations, decomposed. The full proof pays a light per-element cost on a quadratic count; the committed proof a heavy per-element cost on a log-linear count. Whether $86 thin (n dot D)$ or $7.25 thin n^2$ is the smaller is the crossover of @fig:flat-crossover.],
  table(
    columns: (auto, auto, auto, auto),
    align: (left, center, center, center),
    table.header([*representation*], [*per element*], [*element count*], [*class*]),
    [full (publish matrix)], [$7.25$ gates / entry], [$n^2$ entries], [$O(n^2)$],
    [Merkle (commit matrix)], [$approx 86$ gates / hash], [$n dot D$ hashes], [$O(n log n)$],
  ),
) <tab:flat-cost>

So the two representations cross. @fig:flat-scaling lays all four flat curves out at once: on log axes the committed proofs climb at the gentle log-linear rate and the full proofs at slope two, the two families fanning apart; on linear axes the quadratics overtake. At small $n$ the committed proof is the dearer of the two---a few thousand published entries cost less than the hashing to commit them, because $D$ is already a dozen levels deep while $n^2$ is still small. As $n$ grows the quadratic catches the log-linear and passes it for good. @fig:flat-crossover reads the meeting directly: between $n = 152$, where publishing still wins ($174$k gates against $201$k), and $n = 200$, where committing has pulled ahead ($298$k against $280$k), the two curves cross near $n approx 176$, where they sit within forty gates of each other---$232069$ against $232026$.

#figure(
  image("/assets/figures/01_flat_scaling.pdf", width: 100%),
  caption: [Gate scaling of the flat proof, across both matrix representation and permutation mechanism. The committed (Merkle) representations, in blue, climb at the log-linear rate of @eq:flat-merkle-fit; the full (publish) representations, in slate, at the quadratic rate of @eq:flat-full-fit. Left, on log axes, the slope is the complexity exponent and the two representations separate into two families; right, on linear axes, the same curves in absolute gates, where the quadratics overtake. Within a representation the mechanism---sort against product---is the small linear correction of @sub:flat-publish, all but invisible beside the choice of representation.],
) <fig:flat-scaling>

#figure(
  image("/assets/figures/02_flat_full_vs_merkle_crossover.pdf", width: 78%),
  caption: [Where committing the matrix overtakes publishing it, for the sort mechanism. The full representation (matrix public, quadratic) is cheaper only below the crossover at $n approx 176$; past it the Merkle representation (matrix committed, log-linear) wins and the gap widens without bound.],
) <fig:flat-crossover>

But the crossover is not where the decision is made, and saying so is the reason for measuring it. Even below $n = 176$, where publishing the matrix is the cheaper proof, the committed proof is the one the thesis builds on---because publishing the matrix _discloses the graph_, and the whole statement was meant to hide it. The crossover tells us that committing costs nothing asymptotically and little even at small instances; privacy tells us we would commit regardless. The canonical flat baseline, the control every later chapter is read against, is therefore the committed sort proof---_flat-sort_---at every size. The full representation was the instrument that let us see what the matrix costs and where the two representations trade; it was never a proof we would ship.

We now have the baseline's gates, and with them its shape: log-linear, hashing-bound, about $86$ gates a hash. What those gates cost in time and memory, and where that cost stops a single machine cold, is the reading the section closes on.

#subsection([Time, Memory, and the Wall], label: <sub:flat-wall>)

Gates are the structural cost, exact and machine-independent. What they become on a real prover---seconds and gigabytes---is the cost that decides whether the proof can be made at all, and it is the cost the rest of the thesis is organised around. @tab:flat-costs reads the committed baseline across the sweep.

#figure(
  caption: [The committed flat baseline (_flat-sort_) across the size sweep. Gates and proof size are exact; prove and verify times are means over repeats. Three things grow with the instance and two do not: the gate count and prove time climb together, peak memory climbs fastest of all, while the proof size is fixed and the verify time barely moves.],
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    align: (right, right, right, right, right, right),
    table.header([*$n$*], [*gates*], [*prove (s)*], [*verify (ms)*], [*proof (B)*], [*peak (MB)*]),
    [8],    [7\,074],     [0.17],  [9],  [14\,656], [44],
    [256],  [358\,158],   [4.45],  [9],  [14\,656], [517],
    [1000], [1\,733\,830],[25.1],  [12], [14\,656], [2\,451],
    [3000], [6\,224\,830],[91.9],  [15], [14\,656], [9\,736],
    [4000], [8\,298\,830],[114.5], [29], [14\,656], [13\,262],
  ),
) <tab:flat-costs>

The prover's time follows the gate count almost exactly. From $n = 1000$ to $n = 3000$ the circuit grows $3.6$-fold, from $1.73$ to $6.22$ million gates, and the prove time grows $3.7$-fold, from twenty-five seconds to ninety-two; proving is linear in the size of the circuit, as UltraHonk's prover is, so prove time simply inherits the log-linear shape of the gates. A flat instance of a thousand nodes proves in about twenty-five seconds, three thousand in a minute and a half.

Two of the costs do not grow at all, and they are the ones the chapter will lean on later. The proof is $14\,656$ bytes at every size, from eight nodes to four thousand---a fixed length, the succinctness the proof system promises: the verifier downloads the same small proof whatever the instance. Verification is nearly as flat, a handful of milliseconds throughout, nine at the small end and rising only to fifteen at $n = 3000$. This is the $O(1)$ verifier the rest of the chapter measures everything against---flat's single cheap check, the one @sec:stitching-tax says the external hierarchical variants pay $K$-fold to give up and recursion buys back. We pin it here so that the later "$O(K)$ verifier" has a unit: one flat verification is milliseconds, and one flat proof is fifteen kilobytes.

The cost that grows, and the one that finally bites, is memory. Peak prover memory climbs with the circuit at roughly a kilobyte and a half per gate: half a gigabyte at $n = 256$, two and a half at $n = 1000$, nearly ten at $n = 3000$, and thirteen and a third at $n = 4000$. Set that last figure against the machine. The host holds sixteen gigabytes, and at four thousand nodes the prover is already using thirteen of them. There is no room to go much further. A flat instance of five or six thousand nodes does not prove slowly on this machine---it does not prove at all, because the prover cannot fit the circuit in memory. This is the _wall_. It is not a figure of speech but a measured ceiling, the largest flat instance the hardware will carry, and it is the reason everything after this section exists. Every construction the thesis goes on to build is, at bottom, an attempt to get past this one number: to prove a tour too large for a single prover by cutting it into pieces each small enough to fit, with room to spare. The dualism of @sec:dualism already warned that the cutting cannot lower the _total_ work; the wall is why one would cut anyway.

The flat baseline is now fully read---log-linear in its gates, hashing-bound at about $86$ a hash, succinct in proof and verifier, and walled by memory not far past a thousand nodes. One number remains, and it is a cautionary one: a metric the toolchain reports that looks like it measures cost and, read carelessly, does not.

#subsection([What the Opcode Count Hides], label: <sub:flat-acir>)

Alongside the gate count, the toolchain reports a second size: the ACIR opcode count, the number of operations the circuit compiles to _before_ arithmetization. It sits right next to the gate count in the output, it is smaller and tidier, and it is tempting to read as the circuit's true size. It is not the proving cost, and the gap between the two is worth a paragraph, because taking one for the other is the easiest way to draw a false conclusion from a correct measurement.

The trouble is that an opcode is not a gate, and different opcodes become different numbers of gates. Our own data shows it cleanly. By the opcode count, the pairwise mechanism looks _twice_ as expensive as sort: pairwise compiles to about $2 n^2$ opcodes, sort to about $n^2$, a clean two-to-one. By the gate count, the same two mechanisms sit within a seventh of each other, $8.25 n^2$ against $7.25 n^2$. The opcode count says pairwise costs double; the prover says it costs fourteen percent more. Both are right about what they measure. They disagree because the extra opcodes pairwise spends are multiplications---one opcode and one gate apiece---while the $n^2$ opcodes both mechanisms share are public inputs, one opcode but seven-and-a-quarter gates apiece. The opcode count weighs a multiplication and a public input the same; UltraHonk charges the input seven times more.

The hash is the sharpest form of the same effect. A Poseidon2 call is a single blackbox opcode, indivisible in the ACIR, and it expands to the scores of gates @sub:flat-commit measured. So a hashing-bound circuit---which the committed baseline is---carries an opcode count that badly understates its proving cost: a handful of opcodes per Merkle level standing in for the eighty-six gates each level truly costs. Count opcodes and the committed proof looks lean; prove it and the hashing is the entire bill.

The lesson is the plain one: know what a number measures before you trust it. The opcode count is a pre-arithmetization figure, a fair proxy for how large the circuit _description_ is and how long it takes to compile, but not for what it costs to prove. Proving cost lives in the gates, because the gates are what the prover commits to and what its time and its memory scale with. Gates are therefore the currency this chapter reports, and wherever a comparison could turn on the difference we use them and not opcodes.

Honesty adds one qualification, because this section's own central comparison happens _not_ to suffer the distortion. Full against Merkle crosses at the same $n approx 176$ whether it is read in opcodes or in gates, because a public input and a Merkle level happen to expand at nearly the same rate---$7.25$ gates against about $7.8$. That agreement is luck of composition, not a property of the metric, and the pairwise gap on the very same data shows how readily it breaks. The opcode count was right about the crossover here and would have been wrong about the mechanisms, and nothing in the number itself tells you which case you are in. Which is exactly why one reads the gates.

With that caution logged, the baseline is fully in hand: its scaling, its hashing cost, its succinct verifier, its memory wall, and the one number not to trust. Every construction the earlier chapters built was designed against this baseline. The next section is the first to set their _measured_ gates beside the predictions @chap:hierarchical made for them, and to ask whether the analysis and the prover agree.
