#chapter([Introduction], label: <chap:introduction>)

This chapter introduces the idea of a zero-knowledge proof---what it is, why one would want it, and how it carries us from a puzzle to a real-world problem. We then tell the story the thesis originated from and the three research questions it raised. Finally, we lay out the thesis contributions and outline the structure of the remaining chapters.

#section([Motivation], label: <sec:motivation>)

Alice has just solved an incredibly hard Sudoku and says as much to Bob, who is skeptical and does not believe her. The obvious way to settle the matter is for Alice to show him the completed grid: Bob checks it in a moment and is convinced. However, this resolves the dispute entirely in Bob's favor. By handing over the grid, Alice has given away the only thing that was hard to come by, and Bob has obtained it for nothing. A reasonable question then follows: can Alice convince Bob that she holds a valid solution without revealing any of it?

Phrased that way, the question sounds like a contradiction. A proof, after all, is something one shows, and to prove that you know a thing is surely to exhibit it. Yet this contradiction is exactly what a zero-knowledge proof dissolves: it lets Alice convince Bob that a statement is true without revealing anything else---leaving Bob with nothing he did not already have, beyond the bare fact of the statement's truth.

The asymmetry of the Sudoku---that a solution is trivial to check but hard to find---is what makes the puzzle an ideal setting for a zero-knowledge proof. The solution is valuable precisely because it is hard to find, making the ability to prove it without surrendering it worth having.

But how could such a proof even work? If Alice reveals the grid, she reveals everything; if she reveals nothing, Bob has no reason to believe her. The escape is to make the proof a dialogue. Alice first locks in her completed grid without showing it---something that we call a _commitment_---and then Bob issues a challenge she could not have foreseen: reveal some specific row, say, and show that it carries each digit exactly once. An honest Alice can always comply; a bluffer, blind to what she will be asked, can have prepared for only some of the questions, and is exposed the moment Bob picks one she cannot answer. The initial commitment prevents Alice from adaptively changing her response based on the challenge. And because the grid is locked afresh for every challenge, with the digits disguised, the fragments Bob sees never accumulate into the solution, thus keeping it a secret. A single round still leaves room for luck, so they repeat, until the chance that a bluffer has slipped through every challenge is as small as Bob likes. This back-and-forth---commit, challenge, respond, repeat---is the original form of a zero-knowledge proof, and it already shows the three properties such a proof must have: an honest Alice always convinces Bob (_completeness_), a dishonest one almost never does (_soundness_), and Bob learns nothing along the way (_zero-knowledge_). These are the properties that make the proof, in turn, useful, honest, and private. We will formally define them throughout @chap:background.

The asymmetry that makes zero-knowledge proofs worthwhile is no accident of Sudoku, and it reaches much further than puzzles. To illustrate the real-world stakes, let Alice now be a freight carrier, and Bob a client to whom she has promised that her deliveries across a network of stops cost no more than an agreed threshold. Bob, reasonably, wants assurance that the promise has been kept. The obvious way for Alice to provide it is to hand over her route, from which the total cost can be checked against the threshold; the obvious reason she resists is that the route is a secret. It reveals which customers she serves and how her operation is shaped. What she would like is to prove that her route comes in under the threshold while keeping the route and the exact cost to herself.

Today, such a dilemma is usually solved by trust. Alice and Bob agree on a third party---an inspector, or auditor---allowed to see the route and vouch that it meets the threshold. This does not so much remove the problem as relocate it onto someone they must both believe. A zero-knowledge proof removes that someone altogether: Alice can prove that her route honors the threshold while the route never leaves her hands.

Zero-knowledge proofs are no longer a mathematical curiosity. Today, they are deployed in the real world to settle financial transactions anonymously and to prove large-scale computations were executed correctly without revealing the private inputs. Beyond blockchains, they are expanding into identity verification, allowing users to prove credentials without handing over sensitive documents. Ultimately, they shift the burden of trust from institutions to mathematics.

This thesis uses a specific kind of proof, chosen to make the dialogue practical. The back-and-forth just described can be collapsed into a single, short string: Alice computes it locally and sends it once. Bob can then verify it independently at any time. Such a proof is _non-interactive_. Crucially, this proof is also _succinct_, remaining small and fast to verify even when the statement it certifies is enormous. Finally, the proof must guarantee that Alice genuinely knows the underlying information---called the witness---that makes the statement true, rather than merely asserting that such a witness exists. A proof combining these properties while guaranteeing zero-knowledge is called a zk-SNARK (zero-knowledge Succinct Non-interactive ARgument of Knowledge), and zk-SNARKs are what we build.

The purpose of this work is to apply these proofs to a classic combinatorial optimization problem: the Travelling Salesman Problem (TSP). Concretely, given a weighted graph, we prove knowledge of a Hamiltonian cycle---a tour that visits every node exactly once and returns to its start---whose total cost does not exceed a public threshold. Crucially, the proof reveals neither the cycle itself nor its exact cost. We explore various zero-knowledge constructions for this proof and analyze the trade-offs of each approach.

#section([Research Questions], label: <sec:research-questions>)

The most direct method to prove our statement is the simplest: construct a single proof verifying the entire tour simultaneously by ensuring it visits every node exactly once, returns to its origin, and maintains a total cost below the public threshold. We define this as the _flat_, or monolithic, approach. It serves as the natural baseline: conceptually simple and straightforward to implement.

It has one obvious and critical bottleneck. As the number of nodes in the graph increases, the proof grows. By grows, we do not mean its size. The succinctness property of zk-SNARKs, as we have already noted, keeps the proof itself small and quick to check however large the statement behind it. What grows is everything on the prover's side: the size of the circuit that encodes the tour, the time to compile it, the time to generate the witness, the time to produce the proof, and the memory all of this consumes. These are the dimensions a zero-knowledge proof is really measured on, and we will become well acquainted with them in the chapters to come. Under the flat approach, the whole of this burden falls on a single machine.

None of this is new; the same bottleneck appears on the optimization side, where the goal is to find a tour of least cost. There, the natural instinct is to decompose the problem---cut it into smaller pieces, handle each on its own, and combine the results at the end. For the Travelling Salesman Problem this genuinely helps: decomposition shrinks the search space, letting exact algorithms, often paired with heuristics ones, return solutions in reasonable time. The price is paid in solution quality---the resulting tour is usually sub-optimal---but a good-enough tour is often all one needs, and the bargain is a favorable one. 

With no experience of zero knowledge to suggest otherwise, it is natural to expect this same decomposition to relieve the flat approach of its limits: rather than prove the whole tour in one piece, we cut it into segments, prove each segment on its own, and bind the segment proofs into a single statement about the whole. We call this the hierarchical approach; because its pieces are smaller and independent, it promises proofs that are lighter and can be produced in parallel. If decomposition rewards an ordinary solver so handsomely, surely it rewards a zero-knowledge prover too. And the only question seems to be how much: at what instance size does the hierarchical proof overtake the flat one, and what is the price we have to pay in the process? This was the question we set out to answer.

It is hard to find a definitive answer the question because there is no single axis on which to declare a winner: sharpen any one metric and some design comes out ahead, yet none comes out ahead on all of them at once. There are, in the end, no solutions here, only trade-offs. The error was to look at zero knowledge as we look at optimization. A solver gains from decomposition because it has a search to shrink; zero-knowledge proving has no search at all. Worse, breaking the tour into independently and locally proved pieces destroys the very thing the proof must establish---that the pieces form one valid global tour---and restoring it costs a bookkeeping step in the recombination that consumes, almost exactly, whatever the smaller pieces had saved. 

A negative result of this kind is more useful than it first appears: it does not merely close a door, it shows the door was the wrong one. The premise of the original question---that hierarchical and flat compete for a win in absolute terms, and that decomposition might have a favorable advantage that comes with an affordable cost---was simply false. Setting it aside leaves three sharper and deeper research questions, and they organize the rest of this thesis.

#subsection([The Advantages of Decomposition], label: <sub:rq1>)

Decomposition behaves differently in zero-knowledge than in optimization. That it remains worth studying at all suggests it must accomplish something other than what we initially expected.

#block(
  stroke: (left: 1.5pt + colors.primary), 
  inset: (left: 10pt), 
  height: 20pt,
  above: 1.5em,
  below: 1.5em,
  align(horizon)[#text(font: "Libertinus Sans", fill: colors.primary)[RQ1]: _If decomposition does not shrink the total work, what does it buy?_]
)

This question determines whether the approach is worth considering at all. The answer is that what changes is not how much work there is, but how that work is distributed.

The flat approach encodes the whole statement as one circuit, and that circuit grows with the number of nodes, until it becomes too large for one machine to hold in memory and grind through from beginning to end. The hierarchical approach tries to push past this limit by replacing the single large circuit with many small ones, mutually independent, each obtained by cutting the tour into segments. This independence is what lets the segments be proved separately and, given enough machines, at the same time. The catch is that the segments, on their own, prove nothing global: we still need to stitch their proofs together, both to tie them to a single instance and to establish that the full tour they compose has a total cost within the threshold. That stitching adds gates of its own, on top of those in every segment, so the total number of gates ends up higher than the flat circuit's, not lower. What decomposition buys, then, is not fewer gates but a different distribution of them: because each circuit is smaller and proved on its own, the peak memory any one machine needs drops; and because the segments are independent, the wall-clock time to prove them falls when they run in parallel. This is the first of our findings: where decomposition saves an optimizer real work by shrinking the search space, it saves the prover none. It only redistributes the work, allowing for parallel execution and a smaller per-machine footprint.

#subsection([The Cost of Stitching Pieces Back Together], label: <sub:rq2>)

The parallelism gained from decomposition requires structural independence, and independence introduces a critical obstacle. Proofs generated in isolation certify their localized segments and nothing more. They contain no evidence that the segments represent genuine slices of the same global tour. To overcome this, we need an aggregation layer---the glue, so to speak---that stitches the independent proofs back together, ensuring they hold as a continuous Hamiltonian cycle rather than a collection of disjointed paths.


#block(
  stroke: (left: 1.5pt + colors.primary), 
  inset: (left: 10pt), 
  height: 50pt,
  above: 1.5em,
  below: 1.5em,
  align(horizon)[#text(font: "Libertinus Sans", fill: colors.primary)[RQ2]:
  _What are the structural and computational costs of stitching independent proofs into a single global statement---one that guarantees soundness while strictly preserving zero-knowledge?_]
)

This aggregation introduces a systemic overhead we define as _the stitching tax_, and it has three angles to it: what the aggregation reveals, how much it asks of the verifier, and the external trust assumptions required to coordinate the proofs. None of the three is fixed. How much each one costs is set by two decisions---where the stitching is enforced, and what primitives it is made of. If the system enforces stitching externally using plaintext partitions, the design fails across all three dimensions. The plaintext partitions leak routing data, the verifier must sequentially validate every segment, and an external coordinator must be trusted to cross-check the logic. Moving the stitching logic inside a unified proof, or replacing plaintext partitions with cryptographic commitments, mitigates these penalties---though never without secondary costs. These two decisions define a spectrum of aggregation architectures, each paying the stitching tax differently.

#subsection([The Trade-offs of Each Approach], label: <sub:rq3>)

These two decisions yield not one design but many, and each pays the stitching tax in its own currency---sacrificing either privacy, verifier efficiency, or prover overhead. While we might desire a single, universally optimal architecture, cryptographic reality denies us one.

#block(
  stroke: (left: 1.5pt + colors.primary), 
  inset: (left: 10pt), 
  height: 36pt,
  above: 1.5em,
  below: 1.5em,
  align(horizon)[#text(font: "Libertinus Sans", fill: colors.primary)[RQ3]:
  _If no design wins outright, what is the shape of the trade-offs? Where does each architecture excel, and where does it fall short?_]
)

Laid out together, the designs form a frontier. No single approach dominates across all metrics; each serves as the optimal answer for a strictly different operational environment. The trade-offs manifest in a sharp and recurring shape: every design we build secures two of those three angles we just mentioned and surrenders the third.

These three research questions set the ground for this thesis, and the answers that come from the empirical evidence of our implementations are its contributions.

#section([Contributions], label: <sec:contributions>)

The cryptographic ingredients of this thesis are standard---Merkle commitments, grand-product arguments, recursive proof composition---and we claim no invention of them. The primary contribution is not a novel cryptographic gadget, but a structural map: a rigorous account of how these familiar primitives trade against one another when a zero-knowledge proof is decomposed. The individual architectures we build serve as empirical evidence for this map, not the ultimate result.

Two of our contributions are structural, with implications extending far beyond the specific application evaluated here. The first is a generative negative result: demonstrating that decomposition strictly redistributes, rather than reduces, a prover's computational load. The second is the formalization of the stitching tax. This concept organizes the design space, proving that architectural variants strictly fall out of two specific decisions regarding how independent proofs are aggregated. Neither finding is isolated to the Travelling Salesman Problem; both dictate the cryptographic realities of proving global invariants through localized pieces, and we expect them to carry over.

The remaining two contributions are what the map is for. The frontier turns the trade-offs into guidance: it dictates which design to deploy when optimizing for parallelism, verifier efficiency, or prover metrics, and it marks the one combination that no design in our setting can deliver. Finally, the methodology is the part we would most like to see reused---a way of comparing designs that differ in both privacy and mechanism without confounding the two: one mechanism at a time, only within a fixed privacy class, with the tempting cross-comparisons ruled out.

All four claims are argued conceptually and then checked against the implementation of a family of different proofs---flat, hierarchical, committed, and recursive---built in Noir and run end to end.

#section([Structure of the Thesis], label: <sec:thesis-structure>)