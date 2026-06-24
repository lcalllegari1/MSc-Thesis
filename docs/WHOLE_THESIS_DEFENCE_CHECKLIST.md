# Whole-Thesis Defence Checklist

This checklist records the main project-level points to keep consistent before
the defence. It is not a task list for new implementation work. It is a guide
for reviewing the thesis, preparing answers, and keeping the contribution
properly framed.

## 1. Core Claim

The thesis should consistently claim:

> Decomposing a zero-knowledge proof of a route does not reduce total proving
> work, because proving is checking, not search. It reduces per-prover memory
> and enables parallel wall-clock gains, but recombination creates a structural
> trade-off between cost, verifier load, and partition privacy.

Avoid drifting into stronger claims:

- Not "we built the fastest TSP proof".
- Not "we solved private routing".
- Not "decomposition reduces proving work".
- Not "the proof proves optimality".

The contribution is the map of trade-offs.

## 2. Keep The Privacy Objects Separate

Do not blur these three objects:

| Object | What it means | Thesis position |
|---|---|---|
| Route privacy | The verifier should not learn the order of nodes in the tour. | Protected by witness hiding, except where public surfaces leak structure. |
| Partition privacy | The verifier should not learn which nodes belong to which segment. | The central privacy axis of the hierarchical constructions. |
| Matrix privacy/authenticity | Whether the verifier learns the cost matrix, and whether the matrix is the real one. | Matrix entries are not public in the Merkle representation, but a Merkle root is binding, not external authenticity. |

Important phrasing:

> Binding is not authenticity. A Merkle root binds the proof to one matrix; it
> does not prove that the matrix came from a trusted source.

Also be careful with hiding:

> A Merkle root is a binding digest. It should not be described as a
> brute-force-resistant hiding commitment for small domains unless a blinding
> factor or external entropy is present.

## 3. Evidence Chain

Each major claim should connect to a mechanism and a measurement.

| Claim | Mechanism | Evidence to point to |
|---|---|---|
| Flat proof hits a memory wall. | One monolithic circuit grows with the whole route. | Chapter 6 flat baseline memory/time. |
| Merkle representation eventually beats publishing the matrix. | Replace `n^2` public inputs with `n log n` Poseidon2 path checks. | Flat full-vs-Merkle crossover. |
| Grand product can have faster witness generation despite more gates. | Avoids dynamic prover-chosen memory used by sort/shuffle. | Witness-time inversion. |
| Decomposition does not lower total gates. | Segments conserve the original work and glue adds recombination. | Dualism total-work figure. |
| Parallelism lowers critical path. | Independent segment proofs can run on separate machines. | Parallel proving / isolation results. |
| Plain variants leak the partition. | Shared values are public and cross-checked externally. | Public-surface analysis in Chapter 5. |
| Commitments hide the partition computationally. | Shared values are blinded and re-opened inside glue as witness. | Committed variant privacy analysis. |
| Recursion restores structural privacy and one verifier. | Segment public inputs become private witness to the outer proof. | Recursive construction and verifier-tax results. |

Defence pattern:

> Claim, mechanism, measurement, limitation.

## 4. Be Precise About Feasibility vs Optimality

The proof does not show that the route is optimal. It shows knowledge of a valid
route whose cost is at most the public threshold.

Defence answer:

> Optimality would require proving no cheaper route exists, which is a much
> stronger and different statement. This thesis proves feasibility because that
> matches compliance-style use cases: the verifier needs assurance that the
> route is under a bound, not that it is globally optimal.

## 5. Explain Why Plain Variants Exist

Plain-sort and plain-product are not recommended deployments.

Their role:

- Plain-sort: the simplest sound external stitch; it makes the partition leak
  visible.
- Plain-product: the fingerprint lever; it compresses the public surface and
  motivates the recursive construction.
- Committed variants: practical external candidates when computational hiding is
  acceptable.
- Recursion: structural-privacy endpoint with one verifier-facing proof.

Defence answer:

> The plain variants are explanatory controls. They are included to isolate what
> committing and recursion buy, not because they are private enough to deploy.

## 6. Chapter 6 Must Close The Research Questions

Chapter 6 should explicitly answer the research questions from Chapter 1.

| Research question | Chapter 6 answer |
|---|---|
| What is the monolithic baseline and where is the wall? | Flat proof scaling, memory, proof size, verifier time. |
| What does decomposition buy? | Lower per-prover memory and parallel critical path, not lower total work. |
| What trade-off remains? | Privacy ladder and frontier: flat, committed, recursion. |

Do not let Chapter 6 become only a plot catalogue. Every plot should settle one
claim from Chapters 4 or 5.

## 7. Limitations Should Sound Intentional

State limitations as scope choices, not hidden weaknesses.

| Limitation | How to frame it |
|---|---|
| Single backend | Needed for controlled comparisons; changing backends would confound architecture with prover implementation. |
| Single-machine timings | Enough for relative critical-path estimates; not a deployment throughput claim. |
| Uniform segmentation | Isolates proof architecture from route-partition heuristics. |
| No formal circuit verification | Soundness is argued by reduction and validated with negative tests; mechanized verification is future work. |
| No matrix provenance | The proof binds to a matrix root; authenticity must be supplied externally. |
| Random-oracle / recursion assumptions | Standard assumptions, explicitly named rather than hidden. |

## 8. Future Work Should Map To The Frontier

Future work should not read like a random list of missing features.

| Future work | Which frontier pressure it addresses |
|---|---|
| Folding | Reduces recursion's aggregation tax; attacks the empty cheap + parallel + structurally private corner. |
| Batched committed lookups | Reduces Merkle edge-read cost. |
| Distributed proving backend | Improves execution of each large circuit or segment proof. |
| Matrix provenance | Adds authenticity to the committed cost matrix. |
| Formal circuit verification | Strengthens implementation assurance. |
| Adaptive segmentation | Improves practical scheduling and memory balance. |

## 9. Main Objection To Prepare For

Likely objection:

> If state-of-the-art folding and distributed proving exist, why is this thesis
> still useful?

Answer:

> Those systems optimize proving infrastructure. This thesis studies what is
> revealed and what must be recombined when the statement itself is decomposed.
> The techniques are complementary. A better backend can move the measured
> points, but the privacy/recombination structure remains the object being
> studied.

## 10. Final Decision Rule

The conclusion should give practical guidance:

| Need | Recommended construction |
|---|---|
| Small enough instance, strongest privacy wanted | Flat proof |
| Large instance, parallel proving needed, computational hiding acceptable | Committed-product |
| Large instance, one verifier-facing proof and structural partition privacy required | Recursion |
| All three: cheap, parallel, structurally private | Future work: folding |

Short final form:

> Use flat when the monolith fits. Use committed-product when memory and
> parallelism matter and computational partition hiding is acceptable. Use
> recursion when the verifier must see one proof and the partition must be
> absent from the public surface. Use folding, in future work, to try to occupy
> the empty corner.

## 11. Final Review Questions

Before submission or defence preparation, check:

- Does every chapter support the core claim?
- Does every research question get answered explicitly?
- Are all privacy claims about route, partition, and matrix separated?
- Are Merkle roots described as binding, not magically hiding?
- Are plain variants described as controls, not deployable privacy endpoints?
- Are cost comparisons made only at equal privacy, or clearly labelled as
  cross-privacy prices?
- Are total work and parallel wall-clock always distinguished?
- Are all future-work items mapped to a specific limitation or frontier pressure?
- Is the conclusion a decision guide, not just a summary?
