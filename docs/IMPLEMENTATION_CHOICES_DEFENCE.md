# Implementation Choices and Defence Notes

This note collects the implementation improvements we did not pursue, why they
matter, and how to defend the choices made in the thesis. The central framing is:

> The implementation is a controlled reference implementation, not a
> state-of-the-art prover stack. It fixes the backend and uses transparent,
> circuit-native primitives so that each measured cost can be attributed to one
> architectural choice.

The thesis studies the structural consequences of decomposing a zero-knowledge
proof of a route: total proving work, per-prover memory, parallel wall-clock,
verifier load, and partition privacy. Many state-of-the-art techniques could
improve absolute performance, but they would also change the experimental
surface. We therefore treat them as future work, not as missing pieces of the
main contribution.

## Main Defence

The implementation deliberately keeps three things fixed:

1. The proof backend: Noir plus Barretenberg/UltraHonk.
2. The statement: prove knowledge of a Hamiltonian cycle under a threshold,
   with costs bound to a committed matrix.
3. The comparison discipline: change one architectural variable at a time.

This lets the thesis answer questions that a more optimized system would blur:

- What does decomposition buy if proving is checking, not search?
- What work must be paid again at the recombination layer?
- What does the public surface reveal about the partition?
- Which constructions are comparable only at equal privacy?

The answer is the frontier: decomposition does not reduce total proving work,
but it reduces per-prover memory and exposes parallelism. Hiding the partition
then forces a choice between cheap external commitments and expensive recursive
aggregation.

## Improvement Table

| Improvement not implemented | What state of the art would do | Why we did not use it | Defence |
|---|---|---|---|
| Distributed prover backend | Systems such as DIZK and Pianist distribute proof generation across machines. | Our decomposition is at the statement level: graph segments, glue, and partition privacy. A distributed backend would hide the memory issue inside the prover and obscure the privacy axis. | We study the structural cost of decomposing the statement, not backend-level distributed proving. Distributed proving is complementary and could run underneath each segment proof. |
| Folding instead of full recursion | Nova, ProtoStar, ProtoGalaxy, CycleFold, and Mangrove-style folding reduce recursive aggregation overhead. | Folding would require a different proof architecture/backend and would break the single-backend comparison. | Our recursion is the direct endpoint: it measures the aggregation tax clearly. Folding is future work because it is the natural way to attack the empty corner of the frontier. |
| External proof aggregation | SnarkPack-style aggregation can reduce the verifier cost of checking many proofs. | Aggregation improves verifier cost but does not hide the partition or remove external bookkeeping. | Aggregation addresses only one face of the stitching tax. It is useful, but it is not a full solution to partition leakage. |
| Batched committed lookup | Caulk or related lookup arguments can replace many Merkle openings with a batched table-membership proof. | Merkle paths are transparent, Poseidon-native, simple to audit, and directly supported by the circuit structure. | Merkle openings are a clean baseline. They are not the fastest possible lookup mechanism, but they make edge-cost binding explicit and measurable. |
| Vector commitments / KZG / Verkle | Shorter openings, sometimes constant-size. | In-circuit verification may require expensive elliptic-curve or pairing arithmetic, often with trusted setup or non-native field costs. | Poseidon Merkle openings are longer but circuit-friendly and transparent. Constant-size openings are future work if their in-circuit cost is actually lower. |
| Hashed leaves or index-in-leaf Merkle design | Many Merkle designs hash each leaf, often including domain or index tags. | Our implementation uses raw cost leaves and an explicit leaf-index check, saving one Poseidon2 hash per opened edge. | This is sound because the circuit checks both the path to the root and the encoded leaf index. Hashing the leaf would be more conventional but strictly more expensive here. |
| Pedersen commitments | Pedersen gives unconditional hiding with computational binding. | In-circuit group operations are much more expensive than a Poseidon hash commitment. | Poseidon commitments match the computational adversary model and keep the committed variants cheap. Pedersen is future work if unconditional hiding is worth the cost. |
| Stronger domain separation | Production systems tag hash calls by role: Merkle node, Fiat-Shamir challenge, commitment fold, etc. | The implementation keeps roles structurally separated, but production-grade domain separation is an engineering-hardening step. | This is good future work. It strengthens robustness without changing the thesis architecture or measured frontier. |
| Matrix authenticity / provenance | A signed root, oracle attestation, or in-circuit signature check would prove the matrix is authoritative. | Our proof binds the route to a committed matrix; it does not prove who produced that matrix. | This is orthogonal. The thesis proves feasibility under a committed matrix, not external truth of the matrix. Binding is not authenticity. |
| Formal circuit verification | Mechanized proof that the Noir circuits implement the mathematical relation. | We provide reductions, circuit explanations, and negative tests, but not machine-checked circuit equivalence. | This is a limitation, not a contradiction. The thesis argues soundness by reduction and validates implementation behavior empirically. |
| GPU / accelerator optimization | Production provers use GPUs, clusters, or custom hardware for MSM/NTT and other heavy operations. | Hardware changes absolute timings but not the architectural trade-offs. | The thesis uses one machine and one backend to keep comparisons controlled. Acceleration is complementary performance engineering. |
| Adaptive or non-uniform segmentation | Segment sizes could be chosen by route geography, cost distribution, memory target, or worker capacity. | Uniform segmentation keeps the proof comparison clean and avoids mixing proof architecture with partition heuristics. | The thesis studies proof consequences of decomposition, not optimal route partitioning. Adaptive segmentation belongs in future work. |
| Collaborative proving / MPC witness split | Multiple parties jointly prove without revealing witness shares to each other. | Our threat model is one prover hiding the route and partition from the verifier. | Collaborative proving solves a different privacy problem: prover-to-prover privacy, not verifier-facing partition leakage. |

## What We Are Missing for State of the Art

The main state-of-the-art gaps are:

1. Folding-based aggregation.
   This is the most important missing optimization. It could reduce the
   recursive aggregation tax and make the structurally private endpoint more
   practical.

2. Batched committed lookups.
   Per-edge Merkle openings are simple, but a committed lookup argument could
   reduce the cost of proving that all used edge costs come from the committed
   matrix.

3. Backend-level distributed proving.
   The implementation decomposes the statement manually. A distributed prover
   could also parallelize the proving of each large circuit internally.

4. Production hardening.
   This includes domain separation, matrix provenance, audited verifier code,
   stronger randomness handling for blinding factors, and formal circuit
   verification.

These are real improvements, but none invalidates the thesis. They move points
on the frontier; they do not remove the frontier unless folding or a comparable
technique changes the recombination architecture itself.

## How to Answer Defence Questions

### Why not use folding?

Folding is the natural next step, but it would change the proof architecture and
the backend assumptions. The thesis first characterizes the cost of the direct
recursive construction. That cost is the baseline against which folding becomes
meaningful future work.

### Why not use a distributed prover?

A distributed prover solves a backend scaling problem. This thesis studies a
statement-level decomposition problem: what the proof reveals when the route is
cut into graph segments. The two approaches are complementary.

### Why use Merkle paths if lookup arguments are faster?

Merkle paths are transparent, easy to audit, and cheap enough with Poseidon2.
They also make the binding mechanism clear: the circuit checks the opened cost,
the path to the root, and the leaf index. A lookup argument would be a better
optimized implementation, but it would add a more complex subprotocol.

### Why use Poseidon hash commitments instead of Pedersen?

Poseidon commitments are cheap inside the circuit. Pedersen commitments give
stronger hiding but require expensive group arithmetic. Since the thesis already
works in the computational adversary model, Poseidon gives the right cost and
assumption balance for the implemented variants.

### Why is the raw-leaf Merkle design acceptable?

The leaves are the cost values directly, padded to a power of two. The circuit
does not rely only on "this value hashes to the root"; it also reconstructs the
leaf index from the path bits and checks that it equals the expected matrix
address. That closes the wrong-leaf attack while saving one hash per opened
edge.

### Does the committed matrix prove the costs are real?

No. It proves the route is feasible under the matrix committed by the root.
Authenticity of the matrix is an external provenance question: a signature,
published root, oracle, or authority would be needed. The thesis is explicit
that binding is not authenticity.

### Why are the plain variants included if they leak?

They are not deployment candidates. They are explanatory controls. Plain-sort
shows the simplest sound external stitch and makes the leakage visible.
Plain-product shows the fingerprint lever and becomes the substrate for
recursion. They are necessary to understand what committing and recursion buy.

### Why is recursion still useful if it is expensive?

Because it is the endpoint that restores the flat proof's public surface:
only the root and threshold remain public. It buys structural privacy and a
single verifier at the cost of an aggregation proof. That is exactly the
trade-off the thesis measures.

## Final Position

The implementation should be defended as follows:

> We did not choose the fastest known component at every point. We chose the
> simplest circuit-native component that made each architectural cost visible.
> The result is a controlled comparison: Merkle paths expose the cost of binding
> edge reads, commitments expose the cost of hiding the public surface, and
> recursion exposes the cost of internalizing the stitch. State-of-the-art
> techniques such as folding, distributed proving, and committed lookups are
> valuable future work, but they optimize points on the map rather than replacing
> the map.

## References

- DIZK: https://www.usenix.org/conference/usenixsecurity18/presentation/wu
- Pianist: https://eprint.iacr.org/2023/1271
- Caulk: https://eprint.iacr.org/2022/621
- Nova: https://eprint.iacr.org/2021/370
- ProtoStar: https://eprint.iacr.org/2023/620
- Mangrove: https://eprint.iacr.org/2024/416
- SnarkPack: https://doi.org/10.1007/978-3-031-18283-9_10
