#import "/theme/headings.typ": section, subsection
#import "/theme/utils.typ": ccal
#import "/thesis/chapters/_theorems.typ": *

#counter(figure.where(kind: image)).update(0)
#counter(figure.where(kind: table)).update(0)
#counter(math.equation).update(0)

#heading(depth: 1, offset: 0, supplement: [Appendix], outlined: true)[Knowledge-Soundness Theorems] <app:soundness>

This appendix makes precise the reduction that @sub:soundness-reductions told in words. There we said a construction's soundness is a composition---the proof system's knowledge soundness, assumed, together with the arguments we built inside the circuit, each carrying its own small error---and that the whole is no worse than their sum. Here we state that claim formally: the property it proves, the assumptions it rests on, the per-mechanism lemmas that carry the encoding, and one knowledge-soundness theorem for each construction. Nothing below strengthens the chapter's claims. It only fixes them in the form a reviewer can check, and marks exactly where each error term enters and which assumption answers for it.

We write $FF$ for the scalar field, with $|FF| approx 2^254$, and keep the instance size $n$, the segment size $M = n \/ K$, and the segment count $K$ of the chapter. Every construction proves one and the same relation, the committed-matrix form of the problem of @sec:problem-definition:

$ R = { chevron.l (italic("root"), T), pi chevron.r : pi "is a permutation of" ccal("V"), "each edge of" pi "opens to" italic("root") ", and" "cost"#h(1pt)\(pi) <= T }. $ <eq:R-committed>

A construction $Pi_V$ is a prover paired with a verifier $"Verify"_V$; for the external constructions that verifier checks $K + 1$ proofs and one deterministic cross-check over their shared public inputs. What we ask of $Pi_V$ is that an accepting run should mean the prover _holds_ a witness for @eq:R-committed---not merely that one exists somewhere, but that this prover could produce it. That is knowledge soundness, and we state it through an emulator.

#section([The target and the assumptions], label: <app:sound-target>)

#definition("Knowledge soundness, witness-extended emulation")[
The argument $Pi_V$ is _knowledge-sound for $R$ with knowledge error $kappa$_, in the random-oracle model, if there is an expected-polynomial-time emulator $cal(E)$ such that for every probabilistic polynomial-time prover $P^*$ and every statement $x$,
$ Pr[ (tr, w) <- cal(E)^(P^*, cal(O))(x) : tr "accepts" and (x, w) in.not R ] <= kappa, $ <eq:ks>
where the transcript $tr$ is distributed as a real run of $P^*$ against $"Verify"_V$, and $cal(E)$ may observe the queries $P^*$ puts to the random oracle $cal(O)$.
] <def:ks>

The emulator does two things at once. It reproduces the proof the prover would really have made, so it cannot cheat by inventing easy transcripts; and whenever that proof is accepting, it returns a witness $w$. So a convincing proof cannot exist unless a witness can be drawn out of the very prover that made it---to convince is, up to the error $kappa$, to know @goldwasser1989 @bellare1992pok @bitansky2012. We call $kappa$ the _knowledge error_, and the rest of this appendix is the work of bounding it for each construction.

Each bound is a sum of two kinds of term: terms we _assume_, naming the result they stand on, and terms we _prove_, by showing that any cheat that defeats our encoding would break one of the assumed primitives. We collect the assumptions first.

#assumption("Argument knowledge soundness")[
For every arithmetic circuit $C$, the Fiat--Shamir--compiled UltraHonk argument is knowledge-sound for the satisfiability of $C$ with error $epsilon_"SNARK"(C)$, in the algebraic-group and random-oracle models @gabizon2019 @fuchsbauer2018agm @gabizon2020 @aztec_barretenberg.
] <asm:snark>

#assumption("Hash")[
Poseidon2 is collision-resistant: $"Adv"^("CR")(cal(A)) <= epsilon_"CR"$ for every efficient $cal(A)$. Where a construction derives a Fiat--Shamir challenge from it, we model it as a random oracle @poseidon2 @fiat1986 @bellare1993.
] <asm:hash>

#assumption("Binding")[
The commitment $C = "Poseidon2"(r, dot)$ is computationally binding. This is an instance of @asm:hash, not a new primitive: a second opening of $C$ would be a Poseidon2 collision. A Pedersen commitment would instead bind under the discrete-logarithm assumption, trading a hash error for a group one @pedersen1991.
] <asm:bind>

#assumption("Recursive knowledge soundness")[
In-circuit proof verification composes knowledge soundness: from a satisfying outer witness that carries accepting inner proofs, the inner emulator extracts inner witnesses. With Fiat--Shamir instantiated by a concrete hash _inside_ the circuit, this composition is supported in idealized models rather than proved outright @valiant2008ivc @bitansky2012 @bowe2019halo @bunz2021pcd.
] <asm:rec>

With the target fixed by @def:ks and the ground set by the four assumptions above, the reduction itself is one short argument, stated and proved next.

#section([The two-layer reduction], label: <app:sound-reduction>)

The reduction is the move that splits the knowledge error into the one term we assume and the few we prove. It says: extract a witness that satisfies the _circuit_ with the proof system's emulator, then argue that a satisfying circuit-witness is a real route unless some primitive was broken. The first step is @asm:snark; the second is the encoding lemmas of the next section. Their composition is the whole of it.

#theorem("Two-layer reduction")[
Let $Pi$ be a construction whose verifier accepts a single proof of a circuit $C$, and let $"dec"$ map a satisfying assignment of $C$ to a candidate route with its openings. Suppose that for each constraint group $g$ of $C$ the implication "$g$ satisfied $==>$ the property $g$ encodes holds, except with probability $epsilon_g$" holds (the lemmas of @app:sound-lemmas). Then $Pi$ is knowledge-sound for $R$ with
$ kappa <= epsilon_"SNARK" + sum_g epsilon_g . $ <eq:reduction>
] <thm:reduction>

#proof[
Let $cal(E)_"SNARK"$ be the emulator @asm:snark gives for $C$, and define $cal(E)$ to run it and return $(tr, "dec"(w_C))$ from its output $(tr, w_C)$. Its distribution on transcripts is that of $cal(E)_"SNARK"$, hence real. Fix a prover $P^*$ and a statement $x$; $cal(E)$ fails only when $tr$ accepts yet $"dec"(w_C) in.not R$. Split on whether $w_C$ satisfies $C$:
- (a) $tr$ accepts but $w_C$ does _not_ satisfy $C$. By @asm:snark this happens with probability at most $epsilon_"SNARK"$.
- (b) $w_C$ satisfies $C$ but $"dec"(w_C) in.not R$. Then some group $g$ is satisfied while the property it encodes fails; by that group's lemma this has probability at most $epsilon_g$, and a union bound over the finitely many groups gives at most $sum_g epsilon_g$.
Events (a) and (b) are disjoint---one says no satisfying witness was extracted, the other that a satisfying witness decoded badly---and together they exhaust the ways $cal(E)$ can fail. Hence $kappa <= epsilon_"SNARK" + sum_g epsilon_g$.
]

This is the one place the argument barrier enters. The term $epsilon_"SNARK"$ is computational and cannot be removed: a _succinct_ argument for an #smallcaps[np] language cannot be unconditionally sound, because succinctness forces the verifier to trust a binding commitment rather than read the whole witness @brassard1988. Every other term below we either prove outright or charge to a named primitive's hardness. The external constructions verify $K + 1$ proofs rather than one; their version of @thm:reduction runs the per-proof emulator $K + 1$ times and is stated as @thm:external once the lemmas are in hand.

#section([The encoding lemmas], label: <app:sound-lemmas>)

Each constraint group earns a lemma of the form "satisfied $==>$ property, except with $epsilon$". The deterministic ones cost nothing; two carry a cryptographic term, and exactly one of those is probabilistic. Together they are the $sum_g epsilon_g$ of @thm:reduction.

#lemma("Range and threshold")[
A satisfying assignment has every $pi_k in [0, n)$ and $sum_k "cost"(pi_k, pi_(k+1)) <= T$, with error $0$. These are field and integer comparisons the circuit checks directly.
] <lem:range>

#lemma("Sort coverage")[
For the sort mechanism, a satisfying assignment has ${pi_0, dots, pi_(n-1)} = {0, dots, n-1}$, with error $0$. The glue sorts the published values and reads the identity permutation or aborts; the permutation argument _internal_ to the sort gadget runs on the proof system's own challenges and is already charged to $epsilon_"SNARK"$, so at our layer the coverage check is a deterministic equality.
] <lem:sort>

This is the formal content of the claim that "the sort is structural": it adds no term of its own to @eq:reduction.

#lemma("Merkle binding")[
If a satisfying assignment uses an edge cost that differs from the entry the matrix commits at that position, then one extracts a Poseidon2 collision. Hence the event has probability at most $epsilon_"CR"$.
] <lem:merkle>

#proof[
The circuit checks a Merkle opening: it recomputes the path from the claimed leaf to the public root. If the used cost differs from the committed one yet the opening verifies, the claimed path and the genuine path are two distinct openings reaching the same root, i.e. two inputs Poseidon2 sends to one output along the way. An adversary defeating @lem:merkle thus yields a collision-finder of equal advantage; by @asm:hash its success is at most $epsilon_"CR"$.
]

#lemma("Grand-product coverage")[
For the product mechanism, write
$ Q(Y) = product_(k=0)^(n-1) (Y + pi_k) - product_(j=0)^(n-1) (Y + j). $ <eq:Q>
Both products are monic of degree $n$, so $deg Q <= n - 1$; and if the node multiset differs from ${0, dots, n-1}$ then $Q eq.not 0$, since a product $product (Y + a_k)$ determines its multiset of roots uniquely in $FF[Y]$. The glue's check is exactly $Q(X) = 0$ at the challenge $X = H(c)$. A non-covering assignment passes only if $X$ is one of the at most $n - 1$ roots of $Q$: with a truly random challenge this is the Schwartz--Zippel bound $epsilon_"SZ" <= (n - 1) \/ |FF|$ @schwartz1980 @zippel1979, and with $X = H(c)$ derived in the random-oracle model, where the prover must fix the nodes---hence $Q$---before the query that reveals $X$, a union bound over its $q$ oracle queries gives $epsilon_"SZ" + epsilon_"FS" <= q (n - 1) \/ |FF|$ @fiat1986 @bellare1993.
] <lem:product>

At the sizes this thesis runs, $n <= 5000$, the per-challenge bound $(n-1)\/|FF|$ is below $2^(-240)$; the Fiat--Shamir form pays for non-interactivity by the query factor $q$, and even at a generous $q = 2^128$ it stays below $2^(-113)$---negligible by any standard, though honestly weaker than the interactive figure the chapter quotes. Two points of the construction make the bound legitimate, both argued in @sub:challenge-binding: soundness rests on the _order_ of dependence, the tour fixed before the challenge it determines, not on the challenge being secret; and the chain must fold _every_ node, since a challenge built from a proper subset would let the prover settle the remaining segments after seeing it, reopening the root-hunting the bound forbids.

#lemma("Commitment binding")[
For the committed constructions, if the glue re-folds a value set different from the one a segment committed in its public $C_i$, then one extracts a Poseidon2 collision; the event has probability at most $epsilon_"bind" <= epsilon_"CR"$.
] <lem:commit>

#proof[
The verifier accepts only when the segment's published $C_i$ equals the value the glue re-folds from its own witnessed inputs under the same blinding. Two different inputs folding to one $C_i$ are a collision of the Poseidon2 fold; by @asm:bind, itself an instance of @asm:hash, this is at most $epsilon_"CR"$.
]

#section([The constructions], label: <app:sound-theorems>)

The single-circuit constructions are immediate from @thm:reduction with the lemmas that apply: @lem:range and @lem:merkle for flat-sort, and additionally @lem:product for flat-product. The external constructions need the multi-proof version.

#theorem("External constructions")[
Each external construction $V in {"plain-sort", "plain-product", "committed-sort", "committed-product"}$ is knowledge-sound for $R$ with
$ kappa_V <= (K + 1) epsilon_"SNARK" + epsilon_(("enc"),V), $ <eq:external>
where $epsilon_(("enc"),V)$ is $epsilon_"CR"$ for plain-sort; $epsilon_"CR" + epsilon_"SZ" + epsilon_"FS"$ for plain-product; $epsilon_"CR" + epsilon_"bind"$ for committed-sort; and $epsilon_"CR" + epsilon_"SZ" + epsilon_"FS" + epsilon_"bind"$ for committed-product.
] <thm:external>

#proof[
The composite emulator runs $cal(E)_"SNARK"$ on each of the $K + 1$ sub-provers and decodes; a union bound charges at most $(K + 1) epsilon_"SNARK"$ for any extraction failing. Given $K + 1$ satisfying witnesses, the verifier's cross-check---deterministic, and passing by hypothesis---forces the shared public surface to agree, so the $K$ segment routes and the glue's boundary data assemble into one global route. That route lies in $R$ unless a group's property fails: @lem:merkle on the internal and boundary edges ($epsilon_"CR"$), @lem:sort or @lem:product on coverage (nothing, or $epsilon_"SZ" + epsilon_"FS"$), and @lem:commit on the commitments where present ($epsilon_"bind"$). Summing gives @eq:external.
]

The cross-check adds no term: its equality comparisons are deterministic, so they contribute $0$ to $kappa_V$. They are not free of trust, however---they are part of $"Verify"_V$, a script that must be written and audited correctly---but that is _trusted code_, a distinct thing from the _cryptographic_ trust base @eq:external accounts. Omitting the cross-check is a verifier bug, not a broken assumption.

#theorem("Recursion")[
Under @asm:rec, the recursive construction is knowledge-sound for $R$ with
$ kappa_"rec" <= epsilon_"SNARK"^("out") + K epsilon_"SNARK"^("in") + epsilon_(("enc"),"in"), $ <eq:recursion>
where $epsilon_(("enc"),"in")$ are the inner segment's encoding terms ($epsilon_"CR" + epsilon_"SZ" + epsilon_"FS"$ for the product inner that recursion ships).
] <thm:recursion>

#proof[
We sketch the argument. The outer emulator @asm:snark extracts the outer witness, which carries the $K$ inner proofs and their public inputs; the outer circuit's in-circuit verification asserts each inner proof accepts. Applying the inner emulator to each extracted proof yields the segment witnesses, and the outer circuit's re-run of the glue logic on those values places the assembled route in $R$ under the same lemmas as @thm:external. The composition is @asm:rec.
]

The sketch hides one genuine gap, stated here as a limitation rather than smoothed over. The inner emulator is a random-oracle statement, but the outer circuit checks the inner Fiat--Shamir challenge with a _concrete_ hash; the step that treats an in-circuit-verified proof as extractable is therefore supported in idealized models, not proved for the instantiated scheme. This is the standard cost of recursion, and the thesis claims it as a cited reduction, not a fresh proof.

#figure(
  caption: [The knowledge error of each construction, by @thm:reduction (single-circuit), @thm:external, and @thm:recursion. Every bound carries $epsilon_"SNARK"$ and $epsilon_"CR"$; the column that moves across a sort\/product row is precisely $epsilon_"SZ" + epsilon_"FS"$, the soundness price of the fingerprint lever.],
  table(
    columns: (auto, auto),
    align: (left, left),
    table.header([*construction*], [*knowledge error* $kappa <=$]),
    [flat-sort],          [$epsilon_"SNARK" + epsilon_"CR"$],
    [flat-product],       [$epsilon_"SNARK" + epsilon_"CR" + epsilon_"SZ" + epsilon_"FS"$],
    [plain-sort],         [$(K+1) epsilon_"SNARK" + epsilon_"CR"$],
    [plain-product],      [$(K+1) epsilon_"SNARK" + epsilon_"CR" + epsilon_"SZ" + epsilon_"FS"$],
    [committed-sort],     [$(K+1) epsilon_"SNARK" + epsilon_"CR" + epsilon_"bind"$],
    [committed-product],  [$(K+1) epsilon_"SNARK" + epsilon_"CR" + epsilon_"SZ" + epsilon_"FS" + epsilon_"bind"$],
    [recursive-sort],     [$epsilon_"SNARK"^("out") + K epsilon_"SNARK"^("in") + epsilon_"CR"$],
    [recursive-product],  [$epsilon_"SNARK"^("out") + K epsilon_"SNARK"^("in") + epsilon_"CR" + epsilon_"SZ" + epsilon_"FS"$],
  ),
) <tab:soundness-bounds>

Read down the table and the honest scope of the chapter's claim is exact. Three constructions---flat-sort, plain-sort, committed-sort---reduce to @asm:snark and @asm:hash alone, with no recourse to the random-oracle model: their coverage is the deterministic @lem:sort, and committed-sort's only addition is binding, again a collision (@lem:commit). The three product constructions add @lem:product, sound in the random-oracle model. The recursive constructions add @asm:rec on top, the one step we grant heuristically. And three things we do _not_ claim, each a real limitation carried to the conclusion: a random-oracle-free analysis of Fiat--Shamir, a machine-checked version of these proofs, and formal verification of the Noir circuits against the relations the lemmas assume they encode. The lever's signature survives into the soundness layer unchanged: across any sort-to-product row the bound gains exactly $epsilon_"SZ" + epsilon_"FS"$ and nothing else, the same trade of a structural certainty for a computational one that @sub:weighing weighed in cost.
