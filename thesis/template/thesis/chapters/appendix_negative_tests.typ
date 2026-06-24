#import "/theme/headings.typ": section, subsection
#import "/theme/utils.typ": inline
#import "/thesis/chapters/_theorems.typ": *

#counter(figure.where(kind: image)).update(0)
#counter(figure.where(kind: table)).update(0)
#counter(math.equation).update(0)

#heading(depth: 1, offset: 0, supplement: [Appendix], outlined: true)[The Negative-Test Battery] <app:negative-tests>

@sec:soundness-validation described, in summary, how each construction was tried against deliberate cheating, and @tab:negatives gave the consolidated result. This appendix is the full battery behind that table, and it is the empirical companion to @app:soundness. The two appendices answer the same question from opposite ends. @app:soundness _proves_ the reduction: it names, for each constraint group, a lemma of the form "group satisfied $==>$ the property it encodes holds", and bounds the chance the implication fails. This appendix _exercises_ those same lemmas: for each property a lemma promises, it exhibits a witness that violates exactly that property and confirms the construction rejects it---at the layer the reduction says it must. Nothing here is a proof of soundness; a finite list of cheats can never be that. What it can do, and what @sec:soundness-validation claimed for it, is look for a gap between the analysis and the circuits---a property some lemma assumes is enforced but the implementation quietly omits---and report that, across every mechanism the analysis leans on, no such gap was found. The tests live in #inline[tests/correctness/], one file per construction family.

#section([The method], label: <app:nt-method>)

Every test follows one shape, and the shape is what makes a rejection meaningful. The circuit's global size is patched and the circuit recompiled; a valid witness is built---for the committed constructions through the same Rust #inline[merkle_builder] that produces the real benchmark inputs, so the openings are genuine commitments and not stand-ins; the construction is run; and its exit status is read, with zero meaning _accept_ and any non-zero meaning _reject_. A cheat is then introduced by corrupting that valid witness in exactly one place, and the run repeated. The single-fault discipline is the same one @sub:control-one-thing imposed on the comparisons: a witness that fails two checks at once tells us nothing about which check did the work, so each corruption is aimed at one soundness mechanism and leaves the rest of the witness sound.

Two details keep the battery honest. First, each suite opens with _positive controls_ before any cheat: several valid permutations, a handful of randomly generated instances solved to real sub-threshold tours, and a tour whose cost meets the threshold exactly. These must all be accepted, and their acceptance is what licenses reading a later non-zero exit as the bite of the corruption rather than a broken harness. Second, a cheat caught before the Merkle group is reached needs no real commitment, so those cases are run against an all-zero dummy opening; a cheat that must survive the commitment in order to probe a _later_ group is built with real openings, so that the earlier groups pass and the construction is forced to rely on the group under test. The starkest instance of the second point is discussed with the flat battery below.

#section([The layers, and what lands where], label: <app:nt-layers>)

A construction can reject a cheat at one of three depths, and which one is itself part of what the battery checks, because the reduction predicts it.

The cheapest is _execution_: the corruption violates an in-circuit constraint, so witness generation fails and #inline[nargo execute] returns non-zero before any proof is built. This is where most cheats land, and it is exactly the layer the encoding lemmas of @app:sound-lemmas describe---each lemma is a statement about a constraint group, and a witness that breaks the group's property cannot satisfy the group. The range, coverage, Merkle-binding, threshold, commitment, and boundary checks all reject here.

The next is _verifier code_: for the external constructions the segments are bound not inside a circuit but by a deterministic cross-check the verifier runs over the $K + 1$ proofs' public inputs. A cheat that forges across that seam---segment proofs that are each individually valid but do not belong to one global tour---passes execution and is caught only when the cross-check compares the shared surface and finds it inconsistent. This is the trusted-code rejection @thm:external accounts for: it adds no term to the knowledge error, but it is a line of script that must be written and audited rather than a circuit constraint that proves itself.

The deepest is _proving_: recursion verifies its inner proofs inside the outer circuit, and the in-circuit verifier is the one constraint whose check is deferred to #inline[bb prove] rather than #inline[nargo execute]. A tampered inner proof passes witness generation---the outer witness is well-formed---and only makes the prover unsatisfiable. It is the single cheat in the whole battery that has to reach the heaviest layer to be caught, and it is the empirical face of the $epsilon_"rec"$ that @thm:recursion carries.

#section([The flat battery], label: <app:nt-flat>)

The flat constructions prove the whole statement in one circuit, so every cheat is an in-circuit one and every rejection is at execution. @fig:nt-flat lists the battery for the grand-product variant; the sort and presence variants differ only in the coverage row, enforcing range as an explicit group of its own where the grand product folds range and coverage into a single check.

#figure(
  caption: [The flat negative battery (grand-product variant), each cheat against the lemma of @app:sound-lemmas it attacks and the layer that catches it. Every rejection is at execution. The sort and presence variants enforce range as a separate group; the product variant subsumes it into the grand-product coverage check.],
  table(
    columns: (auto, auto, auto),
    align: (left, left, left),
    table.header([*cheat*], [*property attacked*], [*caught at*]),
    [out-of-range node ($pi_k = n$)],          [range (@lem:range)],                [execute],
    [far out-of-range node ($pi_k = 99$)],      [range (@lem:range)],                [execute],
    [duplicate node],                           [coverage (@lem:product)],           [execute],
    [all-same node ($[2, dots, 2]$)],           [coverage (@lem:product)],           [execute],
    [real-Merkle non-permutation ($[0,1,0,1]$)],[coverage, in isolation (@lem:product)], [execute],
    [tampered edge cost],                       [Merkle binding (@lem:merkle)],      [execute],
    [flipped path bit],                         [Merkle binding (@lem:merkle)],      [execute],
    [wrong root],                               [Merkle binding (@lem:merkle)],      [execute],
    [threshold $=$ cost $- 1$],                 [threshold (@lem:range)],            [execute],
    [threshold $= 0$],                          [threshold (@lem:range)],            [execute],
  ),
) <fig:nt-flat>

One cheat in the table carries more weight than the others, and it is the reason the real #inline[merkle_builder] is used for it. The non-permutation $[0, 1, 0, 1]$ is built with _genuine_ Merkle openings: every one of its edges is a real committed leaf, so the Merkle group (@lem:merkle) passes without complaint. The witness is wrong only in that its nodes are not a permutation---node $0$ and node $1$ each appear twice, nodes $2$ and $3$ not at all---and the only check that can see this is the coverage one. So this case isolates the grand product as the sole mechanism standing between a non-tour and acceptance, and its rejection is the empirical content of @lem:product: the fingerprint catches a multiset mismatch that every other group in the circuit waves through. A cheat that broke coverage _and_ the Merkle binding at once could be caught by either, and would tell us nothing about which; forcing real openings around a bad permutation is what makes the test a test of @lem:product alone.

#section([The external battery], label: <app:nt-external>)

The hierarchical constructions split the proof into $K$ segments and a glue, and bind them either by republishing shared values in the open or, for the committed family, by sealing them under per-segment commitments. @fig:nt-external lists the battery for committed-A, the sort-partitioned committed construction; the plain family drops the two commitment rows and exposes the shared values directly, and the product family replaces the sort coverage row with the grand-product one.

#figure(
  caption: [The external negative battery (committed-A, sort partition). The first four cheats are in-circuit and reject at execution; the last forges across the seam between segments and is caught only by the verifier's deterministic cross-check. The glue-group labels (G0, G2, G6, G8) are the construction's own constraint names.],
  table(
    columns: (auto, auto, auto),
    align: (left, left, left),
    table.header([*cheat*], [*property attacked*], [*caught at*]),
    [tampered hidden glue value],   [commitment binding --- glue G0 (@lem:commit)],  [execute],
    [tampered segment commitment $C_i$], [commitment binding --- sub G8 (@lem:commit)], [execute],
    [tampered boundary cost],       [Merkle binding --- glue G6 (@lem:merkle)],      [execute],
    [overlapping partition (node in two segments)], [sort coverage --- glue G2 (@lem:sort)], [execute],
    [mixed-cycle proof set],        [cross-check binding (@thm:external)],           [verifier code],
  ),
) <fig:nt-external>

The last row is the one the other constructions cannot stage, because only the external family has a seam to forge across. Two valid proof sets are produced through the _same_ committed matrix but for two different tours, and a hybrid is assembled---segment proofs from the first tour, glue from the second. Each proof in the hybrid is individually valid, so every segment and the glue pass execution; what is wrong is that they do not describe one tour. The construction catches this in #inline[verify_hier_c.py], where the cross-check requires the same root across all $K + 1$ proofs and each segment's published commitment to match the glue's record of it---and the mixed set fails that comparison. This is exactly the rejection @thm:external describes as costing no knowledge error but living in trusted code: the binding here is a script the verifier runs, audited rather than proved, and the test confirms the script does what the theorem assumes.

#section([The recursion battery], label: <app:nt-recursion>)

Recursion folds the segments into a single outer proof that verifies each inner proof in-circuit and re-runs the glue logic on their now-trusted public inputs. The seam the external family exposed is gone---there is no external cross-check, because the binding moved inside the circuit---and with it goes the verifier-code layer. What remains is two layers: the glue asserts at execution, and the in-circuit verifier at proving. @fig:nt-recursion lists the battery.

#figure(
  caption: [The recursion negative battery. The glue-logic cheats reject at execution; the two that tamper the inner proof or its verification key pass execution and make #inline[bb prove] unsatisfiable, caught by the in-circuit verifier (@thm:recursion). There is no standalone chain-tamper cheat: the chain anchors and Fiat--Shamir challenges are read from the verified inner public inputs and cannot be falsified independently of the proofs that carry them.],
  table(
    columns: (auto, auto, auto),
    align: (left, left, left),
    table.header([*cheat*], [*property attacked*], [*caught at*]),
    [root mismatch],                    [glue root assert],                      [execute],
    [start-bind mismatch],              [boundary bind],                         [execute],
    [threshold exceeded],               [threshold (@lem:range)],                [execute],
    [tampered boundary cost],           [Merkle binding (@lem:merkle)],          [execute],
    [partition overlap],                [grand-product coverage (@lem:product)], [execute],
    [tampered inner proof],             [recursive verification (@thm:recursion)], [prove (#inline[bb])],
    [tampered verification-key commitment], [recursive verification (@thm:recursion)], [prove (#inline[bb])],
  ),
) <fig:nt-recursion>

The two prove-layer cheats are recursion's defining feature, and the gap in the table---the absence of a standalone chain-tamper cheat---is the other side of the same coin. In the external constructions the segment's hash chain, its Fiat--Shamir challenge, and its grand-product point are independent public inputs, each pinned by its own glue assert, so each can be tampered on its own and caught on its own. In recursion those same values are _read from the inner proofs' public inputs_, which the in-circuit verifier has already bound to the proofs that produced them. There is nothing to tamper independently: change the challenge and the proof it came from no longer verifies, so the cheat is caught as a proof failure, not a chain failure. That inseparability is recursion's soundness upgrade over external binding, and it is why the partition-overlap cheat---a non-permutation across segments---is the test that exercises the chain end to end, rejected at the chain-derived challenge exactly as @lem:product predicts. The tampered proof and the tampered key-commitment are the only corruptions the construction defers past execution, and they reach #inline[bb prove] because that is where the inner verification lives; the verification key is included because it is what binds the outer proof to the inner circuit's identity, so a tampered binding limb of it is as fatal as a tampered proof.

#section([What the battery shows], label: <app:nt-summary>)

Read across the four tables, the pattern is the one @sec:soundness-validation promised and @app:soundness predicts. Every property an encoding lemma of @app:sound-lemmas promises some group enforces---range, coverage by sort or by grand product, Merkle binding, threshold, commitment binding, the boundary join, the recursive verification---is met by a cheat built to violate that property and nothing else, and every cheat is rejected at the layer the reduction places its check: the in-circuit groups at execution, the external seam in verifier code, the recursive verification at proving. No corruption was accepted; no rejection landed at a layer other than the predicted one. This does not prove the constructions sound, and the limitations @app:soundness states---no random-oracle-free analysis, no machine-checked proofs, no formal verification of the circuits against the relations the lemmas assume---are untouched by any amount of testing. What the battery establishes is narrower and still worth having: across every mechanism the soundness argument leans on, the circuit closes the door the analysis says it should, at the place it says it should. That is the most a test, as against a proof, can offer, and it is the ground on which @sec:frontier-figure draws the frontier.
