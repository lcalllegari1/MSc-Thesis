# Related Work — Comparison Chapter Scaffold

*Scaffold for the thesis chapter that positions this work against **current research /
state-of-the-art implementations** — NOT the background/foundations literature review
(Plonk, Merkle trees, the ZK primitive, etc. live there). Organized along the same
**pick-two-triangle** axes as the contribution (parallelism+memory / O(1) verifier /
low prover cost, at fixed privacy), so each section answers "who else occupies this
corner, and how do we relate?"*

> **Citation hygiene:** ePrint numbers, titles, venues, and key author lists were
> **verified against the sources on 2026-06** (DIZK, deVirgo/zkBridge, Pianist, HEKATON,
> Soloist, Cirrus, Nova/SuperNova/HyperNova/ProtoStar/ProtoGalaxy/CycleFold, Mangrove,
> SnarkPack/aPlonK/SnarkFold, LegoSNARK, Halo, PCD, collaborative-zk, ZKGraph, Ligero).
> Still **best-effort, confirm before BibTeX:** exact "PCD without Succinct Arguments"
> ePrint (2020/1618) and a few full author lists. Performance figures are *as reported
> by the source* — re-check before quoting a number.

---

## 7.1 — Positioning & the comparison lens

State plainly what this thesis **is** and **is not**, because that decides what counts
as a comparison:

- **Is:** a *structural* analysis — the **dualism** (decomposing a ZK proof yields no
  algorithmic ZK speedup, only parallelism / per-prover memory), the **binding tax**
  (recombining K independent segment-proofs is *one* cost with three coupled symptoms:
  partition leakage, O(K) verifier, verifier-side bookkeeping), and a **frontier at
  fixed privacy** mapping flat ↔ hierarchical ↔ recursive — instantiated on a concrete
  NP statement (TSP / Hamiltonian cycle with a cost bound, route hidden), where the
  decomposition is a **graph partition with its own privacy meaning**.
- **Is not:** a performance-record distributed/streaming prover. We do **not** compete
  on raw prover throughput with the systems below; we compete on (a) the *structural
  treatment of recombination* and (b) *privacy of the decomposition as a first-class,
  measured axis* — which they omit.

**Substrate (deferred to the background chapter, noted here only for completeness):** the
implementation is in **Noir** compiled to ACIR and proved with **Barretenberg's UltraHonk**
(a Plonkish, lookup-friendly, universal-setup backend). These are tools we build on, not
comparison points.

**The one-sentence gap (the chapter's thesis):** across the SOTA below, decomposition is
treated as a *performance* technique and recombination as *engineering*; none isolates
recombination as a structural cost with a **privacy face**, and none makes the **privacy
of the partition** a measured dimension — which is exactly what this work does, on a
concrete combinatorial statement.

---

## 7.2 — Distributed & collaborative proving (the parallelism + memory corner)

*Two distinct decomposition axes that must be disentangled: splitting the **circuit**
across workers vs splitting the **witness** across distrusting parties.*

### 7.2.1 Split the circuit/computation across workers

**DIZK** — [USENIX Security 2018](https://www.usenix.org/conference/usenixsecurity18/presentation/wu).
The first distributed zk-SNARK; it partitions proof generation across a compute cluster
to prove statements ~100× larger than a monolithic prover can. It reports a *linear
inter-worker communication* cost from the interleaved FFT, which later systems target.
*Relevance:* the canonical ancestor of "decompose the proving work for scale" — our
hierarchical variants are a deliberately simpler instance of the same decompose-and-
recombine pattern, but we analyze the *recombination cost* and the *no-ZK-speedup*
result that DIZK (focused on scale) does not.

**deVirgo / zkBridge** — Xie, Zhang, Cheng, Zhang, Zhang, Jia, Boneh, Song, [CCS 2022, arXiv 2210.00264](https://arxiv.org/abs/2210.00264).
The distributed prover (deVirgo) inside zkBridge; it data-parallelizes a GKR/Virgo-style proof but
the primary node still does cryptographic work scaling with the subcircuit and needs
linear inter-worker communication. It demonstrates distributed proving driving a concrete
application (cross-chain bridges). *Relevance:* shows distributed proving in production
and the same primary-node/communication bottleneck our analysis abstracts away; our glue
proof is the analog of its "primary" aggregation step.

**Pianist: Scalable zkRollups via Fully Distributed Zero-Knowledge Proofs** — Liu, Xie, Zhang, Song, Zhang, [IEEE S&P 2024, ePrint 2023/1271](https://eprint.iacr.org/2023/1271).
A distributed Plonk prover that encodes witnesses as *bivariate* polynomials so workers
run FFTs only on local data, removing the linear-communication cost of DIZK/deVirgo. It
reports a performant solution for both data-parallel and non-data-parallel circuits.
*Relevance:* the SOTA "communication-free" decomposition; cite it as exactly the
inter-worker-communication optimization we **do not** pursue (honest scope limit), while
noting our per-prover-memory win has the same motivation.

**HEKATON** — Rosenberg, Mopuri, Hafezi, Miers, Mishra, [CCS 2024, ePrint 2024/1208](https://eprint.iacr.org/2024/1208) ([PDF](http://www.cs.umd.edu/~imiers/pdf/HEKATON.pdf)).
A horizontally-scalable zkSNARK that decomposes arbitrary computations and recombines via
*proof aggregation* with only *constant* inter-worker communication, and primary-node work
scaling only with the number of workers. It targets unbounded computation size with bounded
per-node resources. *Relevance:* the closest "decompose → aggregate" architecture to our
hierarchical-then-bind pipeline; its aggregation step is the engineered counterpart of our
glue proof / verifier cross-checks, and a natural reference for how the O(K) symptom is
handled at scale.

**Soloist** — [ePrint 2025/557](https://eprint.iacr.org/2025/557.pdf).
A distributed SNARK for R1CS achieving *constant proof size* with reported ~100× smaller
communication and ~7× faster proving than Hekaton on general circuits. It also reports
lower memory and faster preprocessing than Pianist. *Relevance:* current frontier of
distributed-prover efficiency; useful to show how far the *performance* axis has advanced,
sharpening that our contribution is on a *different* (structural + privacy) axis.

**Cirrus** — [ePrint 2024/1873](https://eprint.iacr.org/2024/1873.pdf).
The first *accountable* distributed SNARK with linear-time worker and coordinator
computation, minimal communication, and a universal trusted setup. "Accountable" = a
misbehaving worker can be identified. *Relevance:* introduces *accountability* among
distributed provers — a property orthogonal to ours but in the same deployment model;
worth a sentence to show the design space breadth.

**Proving CPU Executions in Small Space** — [ePrint 2025/611](https://eprint.iacr.org/2025/611.pdf).
A scheme for proving large executions with low *space* (memory) rather than by horizontal
scaling. It reports proving with a small memory footprint via streaming/space-efficient
techniques. *Relevance:* directly speaks to our **per-prover memory ~1/K** result — an
alternative route to the same low-memory goal (stream within one node vs split across
nodes), a clean contrast for the memory dimension.

### 7.2.2 Split the witness across distrusting provers (collaborative proving)

**Collaborative zk-SNARKs** — [Ozdemir & Boneh, USENIX Security 2022, ePrint 2021/1530](https://eprint.iacr.org/2021/1530).
Lifts a conventional zk-SNARK into an MPC among N provers that jointly produce one proof
over a *distributed secret witness*, keeping each party's share private from the others.
It reports near-single-prover runtime for an honest majority and ~2× for N−1 malicious.
*Relevance:* a **different decomposition axis** — privacy *between provers*, not privacy of
the *partition from the verifier*; cite to explicitly delineate scope so reviewers don't
conflate "collaborative" with our segment-decomposition.

**Scalable Collaborative zk-SNARK** — [ePrint 2024/143](https://eprint.iacr.org/2024/143.pdf) / [2024/940](https://eprint.iacr.org/2024/940).
A fully distributed collaborative prover built on HyperPlonk with small communication, with
a "private proof delegation" application (offload proving to many servers, none learning the
witness). It reports scalable workload distribution for general circuits. *Relevance:* the
performance-scaled version of collaborative proving; same scope-delineation point as above,
and a reference for "proof delegation" as a deployment our distributed model resembles
operationally but motivates differently.

---

## 7.3 — Recombination: recursion, folding, accumulation, aggregation, commit-and-prove

*This is where our **recursion variant** lives and where **folding** is our declared
"corner that breaks the triangle." The unifying question — how do you bind K independent
pieces into one sound statement? — is exactly the **binding tax**. Sub-grouped by* where
*the binding lives: in-circuit (recursion/folding), formal framework (PCD), external
(aggregation), or commit-then-link (CP-SNARKs).*

### 7.3.1 The binding formalism

**Proof-Carrying Data (PCD)** — ["Proof-Carrying Data and Hearsay Arguments from Signature Cards", Chiesa & Tromer, ICS 2010](https://projects.csail.mit.edu/pcd/) and ["PCD without Succinct Arguments", Bünz–Chiesa–Mishra–Spooner, CRYPTO 2021, ePrint 2020/1618](https://eprint.iacr.org/2020/1618).
The formalism for composing proofs across a distributed computation so each node's proof
attests to the whole history; it is the abstract object our "bind K segment-proofs into one
statement" instantiates. The 2021 work shows PCD is achievable from weaker primitives than
full succinct arguments. *Relevance:* gives the precise vocabulary for the **binding tax** —
PCD *is* binding done in-circuit; our verifier-side cross-checks are the cheap, leaky
alternative PCD/recursion replaces. Frame the binding tax as "the cost of approximating PCD
externally."

### 7.3.2 In-circuit recursion, accumulation & folding

**Halo / accumulation schemes** — [Bowe, Grigg, Hopwood, ePrint 2019/1021](https://eprint.iacr.org/2019/1021).
Introduced recursive proof composition *without* a trusted setup by deferring the expensive
verifier check via an *accumulator* amortized across a recursion chain. It reports practical
recursion by avoiding a full in-circuit pairing per step. *Relevance:* the conceptual root
of "make recursion cheap by not fully verifying each step in-circuit" — the lineage from
which folding descends, and the historical contrast to our recursion variant, which *does*
pay a full in-circuit Honk verification (~704k gates) per segment.

**Nova / SuperNova / HyperNova / ProtoStar / ProtoGalaxy / CycleFold** —
[Nova, CRYPTO 2022](https://eprint.iacr.org/2021/370); [SuperNova, ePrint 2022/1758](https://eprint.iacr.org/2022/1758);
[HyperNova, ePrint 2023/573](https://eprint.iacr.org/2023/573); [ProtoStar, ASIACRYPT 2023, ePrint 2023/620](https://eprint.iacr.org/2023/620);
[ProtoGalaxy, ePrint 2023/1106](https://eprint.iacr.org/2023/1106); [CycleFold, ePrint 2023/1192](https://eprint.iacr.org/2023/1192).
The folding-scheme family: instead of verifying each step's proof in-circuit, *fold* two
instances into one with O(1)/O(log) recursive overhead, giving IVC with a tiny per-step
cost (SuperNova adds non-uniform steps; HyperNova generalizes to CCS; ProtoStar/ProtoGalaxy
minimize recursive work; CycleFold handles the curve cycle). They report recursion overhead
far below full in-circuit verification. *Relevance:* **this is our missing frontier corner.**
Our recursion pays ~704k×K because it verifies in-circuit; folding is the principled way to
"defer the prover tax" — cite this family as the resolution our future-work section points
to, and as the reason recursion's cost is a *characterized price*, not a dead end.

**Mangrove** — [CRYPTO 2024, ePrint 2024/416](https://eprint.iacr.org/2024/416).
A folding-based SNARK framework with a "uniformizing" compiler (turn any computation into
identical steps), a low-memory two-pass parallelizable prover, and a **commit-and-fold**
optimization that simplifies the folded relation. It reports proving 2^24 gates in ~2 min
at ~390 MB on a laptop, competitive with monolithic SNARKs. *Relevance:* **the work most
adjacent to ours** — its commit-and-fold echoes our *committed-* variants, and its
low-memory/parallel folding is the performance realization of our folding corner; engage it
directly and concede it is the *performance* embodiment, while our contribution is the
*structural map + privacy ladder + NP application*.

**Survey & index.** [A survey of folding-based ZKPs (ScienceDirect 2025)](https://www.sciencedirect.com/science/article/abs/pii/S002002552500831X);
[awesome-folding](https://github.com/lurk-lab/awesome-folding). *Relevance:* one-stop
citations for the folding landscape; use the survey to justify "folding is the accepted
route to cheap recursion" without enumerating every scheme.

### 7.3.3 External aggregation

**SnarkPack** — [FC 2022, ePrint 2021/529](https://eprint.iacr.org/2021/529.pdf).
Aggregates n Groth16 proofs into one with O(log n) proof size and verifier time, reusing
existing powers-of-tau (no new setup). It reports aggregating 8192 proofs in ~8.7 s and
verifying in ~163 ms — exponentially faster than batch verification. *Relevance:* attacks
**exactly one** of our binding-tax symptoms — the O(K) verifier (→ O(log K)). The sharp,
*novel* observation our framing yields: aggregation cures the verifier-cost symptom but
**not** the partition leak or the bookkeeping — so it is *not* a full cure, whereas
recursion/folding dissolve all three at once.

**aPlonk** — [ePrint 2022/1352](https://eprint.iacr.org/2022/1352); **SnarkFold** —
[ePrint 2023/1946](https://eprint.iacr.org/2023/1946.pdf).
aPlonk aggregates Plonk proofs with logarithmic-size aggregate proofs; SnarkFold aggregates
proofs via IVC/folding rather than pairing-based inner products, reporting verifier cost
independent of the number of proofs. *Relevance:* round out the aggregation design space
(Plonk-native, and folding-based aggregation) — SnarkFold is the bridge between §7.3.2 and
§7.3.3 and reinforces that folding subsumes external aggregation.

### 7.3.4 Commit-and-prove (the committed-* lineage)

**LegoSNARK / CP-SNARKs** — [Campanelli, Fiore, Querol, CCS 2019, ePrint 2019/142](https://eprint.iacr.org/2019/142).
A framework for *commit-and-prove* SNARKs: commit to data once, then compose modular proofs
that operate on the committed values, linked by the commitment. It reports efficient
"gadget" composition with a linking overhead far below re-proving. *Relevance:* our
**committed-A / committed-A++** variants are precisely a commit-and-prove construction
(each segment exposes a blinded commitment `C_i`; the glue proves linkage over the openings).
Cite LegoSNARK as the general pattern our privacy "cure" instantiates, and
[Collaborative CP-NIZKs (Alghazwi, Bontekoe, Visscher, Turkmen, 2024), arXiv 2407.19212](https://arxiv.org/pdf/2407.19212)
as the collaborative crossover.

---

## 7.4 — zkVM continuations (the production embodiment — strongest contrast)

*Production zkVMs implement precisely the flat → segment → recursively-aggregate spectrum
this thesis maps — making them the most direct operational analog.*

**RISC Zero continuations** — [Continuations blog](https://risczero.com/blog/continuations) /
[Recursion docs](https://dev.risczero.com/api/recursion).
Splits a long execution trace into segments, proves each independently (a STARK per segment),
then **recursively aggregates** them into one constant-size proof. It reports unbounded
computation size with constant final proof size via recursion. *Relevance:* RISC Zero ≈ our
**recursion corner** (decompose, then bind in-circuit); cite its segment+recursion design as
"the same architecture, on generic VM execution rather than a combinatorial statement, and
with no privacy analysis of the segmentation."

**SP1** — [zkVM continuations overview](https://github.com/rkdud007/awesome-zkvm).
Uses continuations (prove chunks independently) but, as documented, does **not** implement
the recursive-aggregation step — it outputs one proof per chunk. *Relevance:* SP1-without-
aggregation ≈ our **hierarchical corner** (external binding, K independent proofs, O(K)
verifier). The SP1-vs-RISC-Zero pair *is* our hierarchical-vs-recursion pair, in production.

**Jolt** — [a16z: FAQs on Jolt](https://a16zcrypto.com/posts/article/faqs-on-jolts-initial-implementation/) / [Building Jolt](https://a16zcrypto.com/posts/article/building-jolt/).
A lookup-centric zkVM; its writeups state the continuation tradeoff explicitly: *more
segments → faster prover via parallelism, but larger proof size before recursion.*
*Relevance:* that sentence is **our pick-two triangle, empirically validated** — quote it as
external confirmation. The contrast that highlights our contribution: zkVMs decompose generic
traces *by time* with no partition-privacy notion; we decompose a *graph* where the partition
*means something*, and we make privacy a measured axis.

---

## 7.5 — ZK for graph / combinatorial problems & private routing (the application domain)

**ZKGraph** — [arXiv 2507.00427 (2025)](https://arxiv.org/pdf/2507.00427).
Translates graph operations (neighborhood expansion, single-source shortest path) into
composable PLONKish circuits, then composes them for complex graph queries with privacy and
verifiability. It reports a circuit library and benchmarks for private verifiable graph
queries. *Relevance:* the **closest application sibling** — same idea (compose circuits over
a graph, privacy + verifiability) but for *queries* (shortest path), not for *proving
knowledge of a constrained Hamiltonian cycle with a cost bound*; and it composes circuits
without our dualism / binding-tax analysis. Our statement is different and arguably harder,
and we study its *decomposition cost*.

**Privacy-Preserving Shortest Path Computation** — [NDSS 2017](https://www.ndss-symposium.org/wp-content/uploads/2017/09/privacy-preserving-shortest-path-computation.pdf).
Computes shortest paths over a graph while hiding query and/or graph data using cryptographic
techniques (e.g., encrypted/garbled structures). It reports practical private shortest-path
queries on city-scale graphs. *Relevance:* a *different* privacy model (hide query/graph from
a server, often MPC/encryption, not a succinct public proof); cite to carve out our niche —
**verifiable AND private from the verifier**, with a single succinct artifact.

**PYCRO — Privacy-Preserving Cross-Domain Routing Optimization** — [arXiv 1505.05960](https://arxiv.org/pdf/1505.05960).
Computes policy-compliant shortest paths and bandwidth allocation across administrative
domains while protecting each domain's private topology, via secure computation. It reports
the first practical privacy-preserving cross-domain routing. *Relevance:* shows routing
*optimization* under privacy in a non-SNARK (MPC) setting — a contrast for "what privacy
means" and evidence that route/optimization privacy is a real, studied need, motivating the
TSP application.

**Foundational lineage (cite briefly — mostly background).**
[GMW: "Proofs that yield nothing but their validity", Goldreich–Micali–Wigderson, JACM 1991](https://dl.acm.org/doi/10.1145/116825.116852)
established ZK for all NP via graph 3-coloring / Hamiltonicity; it is the *theoretical* root
this thesis instantiates *practically* and *succinctly*. Keep to one or two sentences so the
chapter stays about current research.

### Paradigm contrast (one entry)

**MPC-in-the-head / VOLE-based ZK** — e.g., [IKOS, STOC 2007](https://web.cs.ucla.edu/~rafail/PUBLIC/77.pdf), [Ligero, CCS 2017](https://eprint.iacr.org/2022/1608).
An alternative route to ZK for NP: simulate an MPC "in the head" (or use VOLE correlations)
to get cheap-prover, often *non-succinct* proofs without a universal SNARK. They report very
fast provers at the cost of larger, sometimes interactive, proofs. *Relevance:* a contrast
for the *whole approach* — these avoid the decomposition/recombination question entirely by
not being succinct; positioning against them clarifies *why* we are in the succinct-SNARK
regime where the binding tax even arises.

---

## 7.6 — Synthesis: comparison table + the gap

| Work / family | Decomposes? | Recombination | Privacy of *partition*? | Statement | Parallelism *measured*? |
|---|---|---|---|---|---|
| DIZK / Pianist / HEKATON / Soloist / Cirrus | circuit across workers | engineered comm / aggregation | ✗ (not analyzed) | general | yes (their focus) |
| Collaborative zk (Ozdemir; Scalable coZK) | witness across provers | MPC | between provers (not verifier) | general | yes |
| PCD (Chiesa–Tromer; Bünz et al.) | abstract | in-circuit (formal) | n/a | general | n/a |
| Halo / Nova / HyperNova / ProtoStar / **Mangrove** | step / IVC | folding (in-circuit, cheap) | n/a | general | yes |
| SnarkPack / aPlonk / SnarkFold | — | external aggregation | ✗ | batch | — |
| LegoSNARK / CP-SNARKs | — | commit-then-link | (commitment hiding) | modular | — |
| RISC Zero / SP1 / Jolt | execution by time | recursion (RZ) / none (SP1) | ✗ | generic VM | yes (their tradeoff) |
| ZKGraph / PP-shortest-path / PYCRO | query / graph | composition / MPC | partial / different model | graph queries / routing | — |
| **This thesis** | **graph partition** | flat / external (hier) / in-circuit (recursion) / folding (future) | **✓ first-class, measured ladder** | **TSP / Ham. cycle + cost bound** | **yes (isolation benchmark)** |

**The gap = the empty "privacy of partition" column down the SOTA rows.** Decomposition is
ubiquitous (for scale, memory, or unbounded computation); recombination is well-studied
(folding, aggregation, PCD); but **no line treats the privacy of the decomposition structure
as a first-class, measured dimension on a concrete combinatorial statement** — which is this
thesis's contribution, together with the dualism and binding-tax framing that organizes all
of the above into one frontier.

---

## Honest framing notes (carry into the prose)

- **Do not** tabulate raw prover throughput against Pianist / HEKATON / Soloist / RISC Zero —
  wrong axis, and we lose. Compare on *per-prover memory* (we measure it), *conceptual
  treatment of recombination*, and *privacy* (they omit it).
- **Mangrove** is the most likely "scoop" of the framing (commit-and-fold + low-memory
  folding). Engage it head-on: it is the *performance* realization of our folding corner;
  our novelty is the *structural map + privacy ladder + the NP-application frontier*, not a
  competing folding scheme.
- **Aggregation ≠ full cure** (the SnarkPack point) and **SP1-vs-RISC-Zero = hierarchical-vs-
  recursion** (the zkVM point) are the two highest-leverage, defensible, novel-sounding
  observations — give them prominence.

---

## Source links (flat list, for the bibliography pass)

- DIZK — https://www.usenix.org/conference/usenixsecurity18/presentation/wu
- deVirgo / zkBridge (CCS 2022) — https://arxiv.org/abs/2210.00264 , https://dl.acm.org/doi/10.1145/3548606.3560652
- Pianist (S&P 2024) — https://eprint.iacr.org/2023/1271
- HEKATON (CCS 2024) — https://eprint.iacr.org/2024/1208 , http://www.cs.umd.edu/~imiers/pdf/HEKATON.pdf
- Soloist — https://eprint.iacr.org/2025/557.pdf
- Cirrus — https://eprint.iacr.org/2024/1873.pdf
- Proving CPU Executions in Small Space — https://eprint.iacr.org/2025/611.pdf
- Collaborative zk-SNARKs (Ozdemir & Boneh) — https://eprint.iacr.org/2021/1530
- Scalable Collaborative zk-SNARK — https://eprint.iacr.org/2024/143.pdf , https://eprint.iacr.org/2024/940
- Collaborative CP-NIZKs — https://arxiv.org/pdf/2407.19212
- Proof-Carrying Data (Chiesa–Tromer, ICS 2010) — https://projects.csail.mit.edu/pcd/
- PCD without Succinct Arguments — https://eprint.iacr.org/2020/1618
- Halo — https://eprint.iacr.org/2019/1021
- Nova — https://eprint.iacr.org/2021/370
- SuperNova — https://eprint.iacr.org/2022/1758
- HyperNova — https://eprint.iacr.org/2023/573
- ProtoStar — https://eprint.iacr.org/2023/620
- ProtoGalaxy — https://eprint.iacr.org/2023/1106
- CycleFold — https://eprint.iacr.org/2023/1192
- Mangrove — https://eprint.iacr.org/2024/416
- Folding survey (ScienceDirect) — https://www.sciencedirect.com/science/article/abs/pii/S002002552500831X
- awesome-folding — https://github.com/lurk-lab/awesome-folding
- SnarkPack — https://eprint.iacr.org/2021/529.pdf
- aPlonk — https://eprint.iacr.org/2022/1352
- SnarkFold — https://eprint.iacr.org/2023/1946.pdf
- LegoSNARK / CP-SNARKs — https://eprint.iacr.org/2019/142
- RISC Zero continuations — https://risczero.com/blog/continuations
- RISC Zero recursion docs — https://dev.risczero.com/api/recursion
- SP1 / awesome-zkvm — https://github.com/rkdud007/awesome-zkvm
- Jolt (a16z) — https://a16zcrypto.com/posts/article/faqs-on-jolts-initial-implementation/ , https://a16zcrypto.com/posts/article/building-jolt/
- ZKGraph — https://arxiv.org/pdf/2507.00427
- Privacy-Preserving Shortest Path (NDSS 2017) — https://www.ndss-symposium.org/wp-content/uploads/2017/09/privacy-preserving-shortest-path-computation.pdf
- PYCRO (cross-domain routing) — https://arxiv.org/pdf/1505.05960
- GMW (ZK for all NP) — https://dl.acm.org/doi/10.1145/116825.116852
- IKOS (MPC-in-the-head) — https://web.cs.ucla.edu/~rafail/PUBLIC/77.pdf
- Ligero — https://eprint.iacr.org/2022/1608

---

*Related project docs: `FRONTIER_REFRAME.md` (the pick-two triangle, privacy ladder),
`NARRATIVE_FRAMING.md` (flat-vs-recursion-then-hierarchical spine), `MOTIVATION_AND_OBJECTIONS.md`
(defense register), `Thesis_Outline.md` (chapter plan).*
