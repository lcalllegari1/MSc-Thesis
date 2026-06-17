#import "/theme/headings.typ": chapter, section, subsection
#import "/theme/colors.typ": colors
#import "/theme/utils.typ": inline, lc, fn
#import "/thesis/chapters/_pseudocode.typ": *

#chapter([Introduction], label: <chap:introduction>)

This chapter introduces the idea of a zero-knowledge proof: what it is, why anyone would want one, and how it takes us from a puzzle to a real-world problem. We then tell the story this thesis grew out of, and the three research questions that story raised. Finally, we lay out the contributions of the thesis and outline the chapters that follow.

#section([Motivation], label: <sec:motivation>)

Alice has just solved a very hard Sudoku. She tells Bob, but Bob does not believe her. The obvious way to settle this is for Alice to show him the finished grid: Bob checks it in a few seconds and is convinced. But this hands Bob everything. The grid was hard to find, and now Bob has it for free, while Alice has given away the one thing that was difficult to produce. So a natural question comes up: can Alice convince Bob that she has a correct solution without showing him any of it?

Put this way, the question sounds impossible. A proof is something you show, and to prove that you know a thing seems to mean putting it on the table. A zero-knowledge proof is exactly the tool that gets around this. It lets Alice convince Bob that a statement is true while revealing nothing else. When it is done, Bob knows the statement holds, and that is all he knows. He has gained nothing he could reuse.

What makes Sudoku a good example is a simple asymmetry: a solution is hard to find but easy to check. The solution is valuable precisely because it is hard to find. That is exactly why being able to prove it, without giving it up, is worth something.

But how could such a proof work? If Alice shows the grid, she reveals everything. If she shows nothing, Bob has no reason to trust her. The way out is to turn the proof into a conversation. First, Alice locks in her finished grid without showing it. We call this step a _commitment_. Then Bob asks a question she could not have predicted: pick one row, say, and show that it contains each digit exactly once. An honest Alice can always answer. A cheater, who does not know in advance what Bob will ask, can prepare for only some of the questions, and is caught the moment Bob picks one she did not prepare for. The commitment is what stops Alice from changing her grid after she hears the question. And because the grid is locked afresh for each new question, with the digits hidden, the pieces Bob sees never add up to the solution. One round still leaves room for a lucky guess, so they repeat the exchange until the chance that a cheater slipped through every question is as small as Bob wants.

This exchange has a simple shape: commit, challenge, respond, and repeat. It is the original form of a zero-knowledge proof, and it already shows the three properties any such proof must have. An honest Alice always convinces Bob; we call this _completeness_. A cheating Alice almost never does; we call this _soundness_. And Bob learns nothing along the way; this is _zero-knowledge_ itself. The three properties make the proof useful, honest, and private, in that order. We define them carefully in @chap:background.

The asymmetry behind Sudoku is not special to puzzles, and it reaches much further. Suppose Alice is now a freight carrier and Bob is a client. Alice has promised that her deliveries across a network of stops cost no more than an agreed threshold. Bob, reasonably, wants to be sure she kept the promise. The obvious way to check is for Alice to hand over her route, so the total cost can be added up and compared against the threshold. But the route is a secret. It shows which customers she serves and how her business is shaped. What Alice wants is to prove that her route stays under the threshold, while keeping the route, and its exact cost, to herself.

Today, this kind of problem is usually handled by trust. Alice and Bob agree on a third party, an inspector or an auditor, who is allowed to see the route and confirm that it meets the threshold. This does not really remove the problem. It only moves it onto someone they both have to trust. A zero-knowledge proof removes that person completely: Alice can prove that her route honors the threshold, and the route never leaves her hands.

Zero-knowledge proofs are no longer a mathematical curiosity. They are used today to settle financial transactions privately, and to prove that large computations ran correctly without revealing their private inputs. They are also moving into identity systems, where a user can prove a fact about themselves without handing over sensitive documents. In each case, they shift the weight of trust away from institutions and onto mathematics.

This thesis uses one specific kind of proof, chosen to make the conversation above practical. The back-and-forth can be collapsed into a single short string. Alice computes it on her own and sends it once, and Bob can then check it by himself, at any time. A proof like this is _non-interactive_. It is also _succinct_: it stays small and quick to check even when the statement behind it is enormous. Finally, it must show that Alice genuinely knows the underlying information, called the _witness_, that makes the statement true, and not merely that such information exists. A proof with all of these properties, together with zero-knowledge, is called a zk-SNARK, short for zero-knowledge Succinct Non-interactive ARgument of Knowledge. zk-SNARKs are what we build.

The goal of this work is to apply these proofs to a classic combinatorial optimization problem: the Travelling Salesman Problem (TSP). Concretely, we are given a weighted graph, and we prove that we know a Hamiltonian cycle in it: a tour that visits every node exactly once and returns to its start, whose total cost does not exceed a public threshold. The proof reveals neither the tour nor its exact cost. We build several zero-knowledge constructions for this task and study the trade-offs of each.

#section([Research Questions], label: <sec:research-questions>)

The most direct way to prove our statement is also the simplest: build a single proof that checks the whole tour at once. One circuit confirms that the tour visits every node exactly once, returns to its start, and has a total cost below the public threshold. We call this the _flat_, or monolithic, approach. It is the natural baseline, simple to think about and straightforward to implement.

It has one obvious and serious bottleneck. As the number of nodes in the graph grows, the proof grows with it. By grows we do not mean its size. The succinctness of a zk-SNARK, as we have already noted, keeps the proof itself small and quick to check, however large the statement behind it. What grows is everything on the prover's side: the size of the circuit that encodes the tour, the time to compile it, the time to generate the witness, the time to produce the proof, and the memory all of this consumes. These are the dimensions a zero-knowledge proof is really measured on, and we will get to know them well in the chapters ahead. Under the flat approach, this entire burden falls on a single machine.

None of this is new. The same bottleneck appears on the optimization side, where the goal is to find the tour of least cost. There, the natural instinct is to decompose the problem: cut it into smaller pieces, solve each on its own, and combine the results at the end. For the Travelling Salesman Problem this genuinely helps. Decomposition shrinks the search space, which lets exact algorithms, often paired with heuristics, return good solutions in reasonable time. The price is solution quality, since the resulting tour is usually suboptimal. But a good-enough tour is often all one needs, so the trade is usually worth it.

With no experience of zero-knowledge to suggest otherwise, it is natural to expect the same decomposition to relieve the flat approach of its limits. Rather than prove the whole tour in one piece, we cut it into segments, prove each segment on its own, and bind the segment proofs into a single statement about the whole tour. We call this the _hierarchical_ approach. Because its pieces are smaller and independent, it promises proofs that are lighter and can be produced in parallel. If decomposition rewards an ordinary solver so well, surely it rewards a zero-knowledge prover too. The only question seems to be how much: at what instance size does the hierarchical proof overtake the flat one, and what price do we pay along the way? This was the question we set out to answer.

It turned out to be hard to answer, because there is no single axis on which to declare a winner. Sharpen any one metric and some design comes out ahead, yet none comes out ahead on all of them at once. In the end there are no outright winners here, only trade-offs. Our mistake was to look at zero-knowledge the way we look at optimization. A solver gains from decomposition because it has a search to shrink; a zero-knowledge prover has no search at all. Worse, cutting the tour into pieces that are proved independently destroys the very thing the proof must establish, namely that the pieces form one valid global tour. Restoring that fact costs a bookkeeping step during recombination, and that step consumes almost exactly what the smaller pieces had saved.

A negative result of this kind is more useful than it first appears. It does not merely close a door; it shows the door was the wrong one. The premise behind the original question, that hierarchical and flat compete for an outright win and that decomposition might offer a real advantage at an affordable cost, was simply false. Setting it aside leaves three sharper questions, and they organize the rest of this thesis.

#subsection([The Advantages of Decomposition], label: <sub:rq1>)

Decomposition behaves differently in zero-knowledge than in optimization. That it is still worth studying at all suggests it must achieve something other than what we first expected.

#block(
  stroke: (left: 1.5pt + colors.primary),
  inset: (left: 10pt),
  height: 20pt,
  above: 1.5em,
  below: 1.5em,
  align(horizon)[#text(font: "Libertinus Sans", fill: colors.primary)[RQ1]: _If decomposition does not shrink the total work, what does it buy?_]
)

This question decides whether the approach is worth considering at all. The answer is that what changes is not how much work there is, but how that work is distributed.

The flat approach encodes the whole statement as one circuit, and that circuit grows with the number of nodes, until it becomes too large for a single machine to hold in memory and grind through from start to finish. The hierarchical approach tries to push past this limit by replacing the one large circuit with many small ones. The small circuits are mutually independent, each obtained by cutting the tour into segments, and that independence is what lets them be proved separately and, given enough machines, at the same time. The catch is that the segments on their own prove nothing global. We still have to stitch their proofs together: both to tie them to a single instance, and to establish that the full tour they compose has a total cost within the threshold. That stitching adds gates of its own, on top of those in every segment, so the total number of gates ends up higher than the flat circuit's, not lower. What decomposition buys, then, is not fewer gates but a different arrangement of them. Because each circuit is smaller and proved on its own, the peak memory any one machine needs drops; and because the segments are independent, the wall-clock time to prove them falls when they run in parallel. This is the first of our findings: where decomposition saves an optimizer real work by shrinking the search space, it saves the prover none. It only redistributes the work, which allows parallel execution and a smaller footprint per machine.

#subsection([The Cost of Stitching Pieces Back Together], label: <sub:rq2>)

The parallelism we gain from decomposition rests on structural independence, and that independence introduces a problem of its own. Proofs generated in isolation certify their own segments and nothing more. They carry no evidence that the segments are genuine slices of the same global tour. To fix this we need an aggregation layer, the glue, that stitches the independent proofs back together and ensures they hold as a single continuous Hamiltonian cycle rather than a collection of disconnected paths.


#block(
  stroke: (left: 1.5pt + colors.primary),
  inset: (left: 10pt),
  height: 50pt,
  above: 1.5em,
  below: 1.5em,
  align(horizon)[#text(font: "Libertinus Sans", fill: colors.primary)[RQ2]:
  _What are the structural and computational costs of stitching independent proofs into a single global statement---one that guarantees soundness while strictly preserving zero-knowledge?_]
)

This aggregation introduces an overhead we call _the stitching tax_, and it has three angles: what the aggregation reveals, how much it asks of the verifier, and the external trust needed to coordinate the proofs. None of the three is fixed. How much each one costs is set by two decisions: where the stitching is enforced, and what it is made of. If the system enforces stitching externally, using plaintext partitions, the design pays on all three angles at once. The plaintext partitions leak routing data, the verifier must check every segment in turn, and an external coordinator must be trusted to cross-check the logic. Moving the stitching inside a single proof, or replacing plaintext partitions with cryptographic commitments, eases these penalties, though never without secondary costs. These two decisions define a spectrum of aggregation designs, each paying the stitching tax in a different way.

#subsection([The Trade-offs of Each Approach], label: <sub:rq3>)

These two decisions yield not one design but many, and each pays the stitching tax in its own way, sacrificing either privacy, verifier efficiency, or prover overhead. We might wish for a single design that is best at everything, but cryptographic reality denies us one.

#block(
  stroke: (left: 1.5pt + colors.primary),
  inset: (left: 10pt),
  height: 36pt,
  above: 1.5em,
  below: 1.5em,
  align(horizon)[#text(font: "Libertinus Sans", fill: colors.primary)[RQ3]:
  _If no design wins outright, what is the shape of the trade-offs? Where does each architecture excel, and where does it fall short?_]
)

Laid out together, the designs form a frontier. No single approach dominates across all metrics; each is the best answer for a different operational setting. The trade-offs take a sharp and recurring shape: every design we build secures two of the three angles just mentioned and gives up the third.

These three research questions set the ground for this thesis, and the answers, drawn from the empirical evidence of our implementations, are its contributions.

#section([Contributions], label: <sec:contributions>)

The cryptographic ingredients of this thesis are standard: Merkle commitments, grand-product arguments, recursive proof composition. We claim no invention of them. Our main contribution is not a new cryptographic gadget but a structural map: a careful account of how these familiar primitives trade against one another when a zero-knowledge proof is decomposed. The individual designs we build are the empirical evidence for this map, not the result itself.

Two of our contributions are structural, and their implications reach well beyond the specific problem studied here. The first is a negative result, and a productive one: decomposition strictly redistributes a prover's work rather than reducing it, and seeing why is what opens the rest of the framework. The second is the formalization of the stitching tax. This concept organizes the design space and shows that the architectural variants fall out of just two decisions about how independent proofs are aggregated. Neither finding is specific to the Travelling Salesman Problem. Both describe what happens whenever one proves a global property through local pieces, and we expect them to carry over.

The remaining two contributions are what the map is for. The frontier turns the trade-offs into guidance: it tells us which design to deploy when we care most about parallelism, verifier efficiency, or prover cost, and it marks the one combination that no design in our setting can deliver. Finally, the methodology is the part we would most like to see reused: a way of comparing designs that differ in both privacy and mechanism without confusing the two. We change one mechanism at a time, compare only within a fixed privacy class, and rule out the tempting cross-comparisons.

All four claims are argued conceptually and then checked against an implementation of a family of proofs, flat, hierarchical, committed, and recursive, built in Noir and run end to end.

#section([Structure of the Thesis], label: <sec:thesis-structure>)
