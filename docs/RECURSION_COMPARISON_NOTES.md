# Recursion ⇄ Flat — Insights, Reasoning & Decisions (session reference)

Purpose: a standing answer-sheet so the recurring questions about recursion
measurement, the flat comparison, deployment models, and the secondary metrics
don't have to be re-derived. Numbers are from this machine's sweeps
(`results/flat.csv`, `results/recursive_raw.csv`); treat them as the observed
shape, not exact constants.

See also: `HIER_MEASUREMENT_AND_PLOTS.md` (measurement semantics + plot taxonomy),
`Recursive_inner_circuit_choice_explained.md` (why the plain-product inner), `HOWTO.md`
(commands for every script named here).

---

## 0. The one-sentence frame

Flat and recursion sit at the **same privacy point** (perfect hiding, public
surface `(root, threshold)`) and the **same verifier surface** (one proof). So
flat-vs-recursion is **not** a privacy or verifier comparison — it is a
**cost / parallelism / memory** comparison of two routes to the same statement:
the monolithic prover (flat) vs **decompose into K segments → recursively
aggregate** (recursion).

**Headline result:** recursion trades *more total work* and *no speed win* for a
**bounded per-machine memory ceiling** (constant in N) and a flat-equivalent
**O(1) verifier**, at equal privacy.

---

## 1. How a recursion proof is produced (the 3-phase pipeline)

The outer circuit does **not** generate the inner proofs — it **consumes them as
witness** (`verify_honk_proof(vk, proof, pubs, key_hash)` is constraints over
`proof`, and `proof` is ordinary witness). So inner proofs must exist *before*
the outer can even solve its witness. Three phases (the driver
`run_recursion.py` does all three; by hand you do 1–2 yourself):

1. **Prove each segment** — `bb prove -t noir-recursive` → proof (458 fields) +
   public_inputs (9) + recursive VK.
2. **Serialize** those fields into the outer `Prover.toml`.
3. **Prove the outer** — `nargo execute` + `bb prove` → the one delivered proof.

Inner = the **plain-product segment** (`hierarchical_segment_fs`). Chosen for (a) a
ceteris-paribus comparison with the plain-product row, and (b) its **O(1) public surface**
(9 fields regardless of M) which keeps the outer ~segment-size-independent. *Not*
for privacy (recursion hides the partition either way). See
`Recursive_inner_circuit_choice_explained.md`.

---

## 2. The decomposition: segment / outer / aggregate

`aggregate_recursion.py --split-components` emits **three** variant rows per cell:

| Row | Meaning |
|---|---|
| `recursion_k{K}` | **aggregate** = the whole job (segments + outer) as one point |
| `recursion_k{K}_seg` | the **segment phase** (the K inner proofs' contribution) |
| `recursion_k{K}_outer` | the **outer** recursive proof alone |

**There is deliberately no `_glue` row for recursion** (unlike the hierarchical
family). Recursion fuses the glue logic *into* the outer alongside the K
in-circuit verifications, which dominate it (~704k gates each vs ~63k total glue
at K=2). The glue is not a separately-measured artifact; **the whole outer is the
binding layer** — the recursion analogue of the hierarchical glue + O(K) verifier
tax. So the split is **segments vs outer**, not segments vs glue.

"aggregate" is fine as a term as long as it's clear it means *the combined
seg+outer job*, **not** the outer proof (which is itself the cryptographic
"aggregation" proof). When ambiguous, say "combined (seg+outer)".

---

## 3. Aggregation rules are **per metric** (this trips everyone up)

The combined row is **not** a single "innerstep + outer" formula. Each column
uses its own rule, and only **time** is affected by the `parallel`/`total` flag:

| Combined metric | Rule | parallel/total affects it? | = combine(seg, outer) |
|---|---|---|---|
| `circuit_size` / `acir` | Σseg + outer | **no** (structural) | seg **+** outer |
| `compile_s` | seg + outer (one each) | no | seg + outer |
| `prove_s` / `witness_s` | **innerstep + outer**, innerstep = `max` (parallel) / `sum` (total) | **yes** | seg **+** outer |
| `peak_mb` | **max(seg peaks, outer)** | **no** | **max(seg, outer)** |
| `verify_s` | outer | no | outer |
| `proof_bytes` | outer | no | outer |

- **`max(segments, outer)` lives in the `peak_mb` rule** — it didn't go away; it's
  just the memory column (peaks don't add: only one prover is resident at a time).
- **`max(seg)+outer` / `sum(seg)+outer` is the *time* rule only.**
- Consistency: combined = combine(`_seg`, `_outer`) for every metric (sum for
  time/gates, max for peak, outer-only for verify/bytes).

---

## 4. Three "segment" quantities (single ≠ `_seg` ≠ Σ)

| Quantity | Answers | Mode-dependent? |
|---|---|---|
| **single segment** | what does **one leaf** cost? (per-node) | **no** — fixed |
| **`_seg` row (segment *phase*)** | the K segments' contribution to *this deployment* | **yes** for time (`max`/`sum`) |
| **Σ segments** | total segment work | it *is* the sum |

The `_seg` row is the **segment phase**, aggregated the same way the combined row
is — so for time it's `max` (parallel) or `sum` (total). It is **not** "a single
segment." It only *coincides* with a single segment where the rule is `max`:
parallel-time (`max ≈ one segment`, since segments are near-identical) and
**always for `peak_mb`** (`max(seg peaks) = single-seg peak`, mode-independent —
which is why your "mode shouldn't change a single segment" intuition holds for
memory). For the *true* per-node single segment across all metrics, read the
**raw** CSV (what `plot_recursion_stack.py` does).

---

## 5. Deployment models: parallel / sequential / concurrent

Two orthogonal axes get conflated. **Axis 1 = where it runs; Axis 2 = how it was
measured.**

| Model | Where | Wall-clock | Source |
|---|---|---|---|
| **parallel** (distributed) | K machines, one segment each | `max(seg) + outer` | from *solo* (isolated) timings |
| **sequential / total** | 1 machine, segments one-at-a-time | `Σ(seg) + outer` | from *solo* timings |
| **concurrent** | 1 machine, all K at once (contend) | measured, lands in `[parallel, total]` | needs a *contended* measurement |

- The **outer is a serial tail in all three** (it consumes the inner proofs;
  can't overlap them).
- **parallel & sequential are the same numbers combined two ways** (`max` vs
  `sum`) — that's all the `--mode` flag does.
- **concurrent** is a separate *measurement* (with contention); you can't get it
  by summing solo times. `max(solo) ≤ concurrent ≤ Σ(solo)`.
- **For recursion, concurrent is degenerate → not reported.** The inner phase is
  the small term and the outer runs alone afterward, so concurrent ≈ total. (It
  matters for the *hierarchical* family, where the K+1 proofs are comparable.)

---

## 6. Is parallelization recursion's premise? (No — Amdahl)

Parallelization only speeds up the **cheap segment phase**; the **serial outer
dominates**. Measured parallel/total ratio (P/T):

- ~**0.98** at small N / large K (parallelism barely helps),
- down to ~**0.73–0.78** at large N (helps ≤27%).

And **even the ideal parallel number never beats flat**: N=1000 K=2 → parallel
**33.6 s** vs flat **25.1 s**. No K rescues it (higher K shrinks segments but
explodes the outer: K=8 outer ≈ 78 s). So **recursion gives no wall-clock win
over flat**, however scheduled.

**Consequence for the write-up:** the honest, like-for-like time comparison is
recursion's **single-machine (total/sequential)** number vs flat (flat is
single-machine too) — *not* "worst case to be generous," but **matched hardware**.
Show parallel-vs-total in the recursion-alone section (the small shaded gap,
`plot_recursion_modes.py`); it *licenses* using total in the flat comparison.
**Never present parallel as a speedup.** The win is memory, not speed.

---

## 7. The valuable flat-vs-recursion comparisons (taxonomy)

| # | Question | Series (per K) | Best plot | Verdict |
|---|---|---|---|---|
| C1 | total gates | flat + aggregate + outer | stacked bar / line | aggregate ≈ flat + ~const outer tax |
| C2 | **memory ceiling (the win)** | flat + single-seg + outer | line vs N, multi-K | recursion's worst machine ≈ constant in N; beats flat past a crossover |
| C3 | wall-clock time (honest negative) | flat + total (sum+outer) | line vs N | no speed win; serial outer tail |
| C4 | total CPU work | flat + aggregate (total) | line vs N | recursion does more total work |
| C5 | verifier | flat + outer | bar / table | **tie** (both O(1)) |
| C6 | aggregation tax vs K | outer | bar/line vs **K** | outer ≈ K×704k; aggregator RAM ~K× |
| C7 | frontier synthesis | flat, recursion@K, [plain-product] | cost-vs-cost scatter | two perfect-hiding corners (**not built yet**) |

**Curated series per metric matters** — each panel shows a *different* set (memory
wants seg+outer+flat; verify wants outer+flat; gates wants aggregate+flat). This
is what `plot_comparison.py` does.

### Key measured facts behind these
- **Outer ≈ constant in N** (verification circuit is N-independent): ~1.47M gates
  / ~2 GB / ~21 s at K=2, flat across N=48→1000.
- **Σ segments ≈ flat work** (conserved): N=1000 K=2 → Σseg ≈ 1.79M ≈ flat 1.73M.
- **aggregate ≈ flat + outer**; the **outer tax amortizes**: 96% of total at
  N=48 → 45% at N=1000 (K=2).
- **Memory crossover (K=2) ≈ N≈820**: flat peak (~2.45 MiB/node) crosses the
  constant ~2 GB outer ceiling there → beyond it, recursion's worst machine needs
  less RAM than flat.
- **Verifier is a tie**: every proof is **14656 bytes, 2 public inputs** (flat and
  all K); verify ≈ 12–16 ms, **independent of N and K**.

**K decision:** use **multiple K** (2,4,8). It's the knob trading per-leaf memory
(↓ with K) against aggregator cost (↑ with K), and the crossover N depends on K.
Use K=2 as the cheapest anchor in single-axis decompositions; show K=2/4/8 in the
memory-crossover and frontier figures.

---

## 8. Bringing in the hierarchical family (the full frontier)

The intermediate variants (plain-sort, plain-product, committed-sort/plain-product) turn the flat↔recursion line
into a frontier. The corners:

| Variant | Decomposition | Privacy (public surface) | Verifier | Prover / parallelism |
|---|---|---|---|---|
| **flat** | none (monolith) | perfect — `(root, threshold)` | **O(1)** | monolithic: no parallel, memory ↑ N |
| **A** | K segments + glue | **partition PUBLIC** | O(K) | parallel, per-node ≈ flat/K |
| **plain-product** | + in-circuit FS + grand-product | partition hidden, extra public fields (P_i,c,X,endpoints) | O(K) | parallel, per-node ≈ flat/K |
| **committed-sort/plain-product** | + blinded commitments | **equalized → perfect-ish** | O(K) | parallel, per-node ≈ flat/K (+commit) |
| **recursion** | K plain-product segments verified **in-circuit** + glue | perfect — `(root, threshold)` | **O(1)** | K leaves parallel **+ serial outer (huge)** |

**The organizing insight — the dualism.** plain-product and recursion are the *same*
decomposition; the O(K) binding work just lives in a different place: **external**
(plain-product → the *verifier* pays, cross-checks) vs **in-circuit** (recursion → the
*prover* pays, the outer). flat sidesteps decomposition entirely. The stitching tax
is **conserved, relocated** — verifier-side ↔ prover-side.

**Two slices — compare along one at a time (the family varies on two axes):**
- **Equal-privacy slice** (hold privacy, compare cost): **flat / committed-product /
  recursion** — all perfect hiding. Isolates cost⇄verifier⇄memory, no confound.
- **Privacy ladder** (vary privacy): **plain-sort → plain-product → committed-* → flat/recursion** —
  the price of progressively hiding the partition.

**Comparison taxonomy:**

| Group | Metric | Mode | Plot | Expectation (grounded) |
|---|---|---|---|---|
| Verifier (stitching tax) | `verify_s` | hier: Σ K+1 + cross-checks | line vs N / bar vs K | flat = recursion **O(1)** ≪ hier **O(K)** (hier_fs K2 ≈0.09 s vs ≈0.013 s) |
| | `proof_bytes` | — | bar @ fixed N | flat = recursion = 14656 ≪ hier ≈ (K+1)×14656 |
| Prover: parallel | `prove_s` | **isolated, parallel (max)** | line vs N | **hier wins** (real ≈K× speedup) < flat < **recursion ≈ outer (no speedup)** |
| Prover: total | `prove_s` | total (sum) | line vs N | hier ≈ flat (conserved) ≪ recursion (≫) |
| Prover: memory | `peak_mb` | per-node (isolated) | line vs N | **hier lowest** (≈flat/K) < recursion (outer ceiling, const, ↑K); flat ↑N unbounded |
| Total work | `circuit_size` | structural | stacked bar | flat ≈ hier total (+glue tax) ≪ recursion (+K×704k) |
| Privacy | public-surface size | — | **ladder / categorical** | plain-sort (leaks) → plain-product (hidden) → committed (equalized) → flat/recursion (minimal) |
| Synthesis | cost-vs-cost | fixed N | **Pareto scatter** | the triangle (see below) |

**Modes per family (the crucial difference):**
- **hierarchical** → measure **isolated** (solo → parallel/max = the *distributed
  speedup*, its selling point) **and** **concurrent** (one box = honest baseline);
  proofs are comparable-sized so contention matters.
- **recursion** → solo → parallel/total; **concurrent degenerate** (outer dominates).
- **flat** → single (monolith).
- **The contrast:** hierarchical's parallel is a **real ≈K× speedup** (independent
  proofs, no serial tail); **recursion's parallel is Amdahl-capped** (serial outer).
  So **hierarchical is the genuinely-parallel corner — recursion is not.** What
  recursion buys over hierarchical is *not speed* — it's the O(1) verifier +
  perfect hiding (the dualism, paid in the prover).

**The pick-two triangle (punchline):**
- **flat** — O(1) verifier + perfect privacy + simple, but **monolithic** (no
  parallel, memory ↑ N, scaling wall).
- **hierarchical** — **prover-optimal corner**: real parallel speedup + lowest
  per-node memory + tunable privacy, paid by an **O(K) verifier**.
- **recursion** — **verifier-optimal decomposed corner**: O(1) verifier + perfect
  hiding, paid by a **huge serial outer** (more total work, no speedup, high
  aggregator memory).

Can't have *cheap prover ⇄ cheap verifier ⇄ perfect privacy* all at once; each
variant sacrifices one. (Thesis stance: frontier, not crossover.)

---

## 9. Is moving work to the verifier (hierarchical's O(K)) sellable?

Yes — **conditionally**, and "moving work to the verifier" *undersells* it.

**The trade is asymmetric in hierarchical's favor.** vs recursion at K=2: you
spend **~75 ms verify + ~30 KB** (O(K): K+1 verifies + cross-checks, ~0.09 s /
44 KB vs ~0.016 s / 14.7 KB) to **save ~21 s + ~2 GB of prover** (the outer) *and*
gain real parallelism. The honest framing isn't "we burden the verifier" — it's
**"we keep the binding as cheap external checks instead of forcing it into a giant
in-circuit outer."** O(K) is asymptotic; in absolute terms it's milliseconds on a
tiny base.

**When sellable vs not (name the regime — this *is* the defense):**

| Sellable when… | Not sellable when… |
|---|---|
| **proving is the bottleneck** (large N, flat would OOM) | verification is the bottleneck (on-chain, gas) |
| verification is **infrequent / offline** (one auditor/regulator/counterparty) | **many** independent verifiers re-check |
| **distributed/parallel hardware** available | single-verifier-must-be-trivial |
| value **per-node feasibility** (commodity machines) | need a single succinct on-chain object |

The "verifier cheap at all costs" reflex comes from **one** model (blockchain /
many-verifier). The hierarchical corner serves the **opposite** regime, where the
verifier had idle slack and proving was the constraint.

**It's not dominated.** Recursion has the O(1) verifier but pays a huge serial
outer (no speedup, GBs); hierarchical has the cheapest, genuinely-parallel prover.
Neither wins universally → two distinct frontier corners (the dualism). Also: this
is the recognized **distributed / collaborative proving** corner of the literature
(RELATED_WORK), which accepts exactly this trade — so it has precedent/legitimacy.

**Concede-then-defend (for the defense):**
- *Concede:* the hierarchical aggregate is **not a strict SNARK** (no single
  succinct object; K+1 proofs + O(K) cross-checks) → loses in on-chain /
  many-verifier settings, full stop.
- *Defend:* that's not the target. For **prover-bound problems verified offline by
  few parties on distributed hardware**, it's the cheapest, most parallel,
  lowest-memory prover, and its O(K) verifier is a sub-second / tens-of-KB cost — a
  trivial price for prover feasibility. Recursion exists for when you *do* need the
  succinct verifier (at a prover cost); flat for small instances that need no
  decomposition.

**Bottom line:** sell it as *"cheap, parallel, low-memory prover at a small
offline-verifier cost,"* state the regime, concede it's not for on-chain, and
present it as a Pareto corner — the only framing under which *any* of the three is
"the answer."

---

## 10. Verifier time — why it looks weird (it's fine)

- All proofs are **14656 bytes / 2 public inputs** → `bb` pads UltraHonk proofs to
  a **fixed size** (recursion-friendliness), so the verifier does a **fixed amount
  of work**. Verification is **succinct: independent of circuit size, N, and K**.
- **flat "inconsistent"** (mean 12.7 ms, std 2.3 ms, range 8.8–19.6): at ~13 ms
  you measure *process spawn + file I/O + OS jitter*, not crypto. 144 invocations
  across 47 N → you see the noise floor; there's no N-signal to find.
- **recursion tight-within-K but K-ordered** (K=2 15.4±0.4, K=4 13.8±0.2,
  K=8 12.6±1.4): tight because the outer VK is N-independent and runs are
  clustered. The ~1.5 ms K-ordering is a **measurement artifact** (CPU
  turbo/cache state — each bigger-K verify follows a heavier prove), **not** a
  protocol property; the gap is *smaller* than flat's own std.
- **Takeaway:** report verify as **O(1) / constant, ~10–16 ms, independent of N
  and K**. Don't plot a "verify vs K" trend. The point: it **ties flat** and
  **beats the hierarchical family's O(K)** verifier. K=8's 4×-bigger circuit
  verifying as fast as K=2 *confirms* succinctness.

---

## 11. Secondary metrics — where they matter (scale-dependent!)

**These three are *not* uniformly negligible — their relevance depends on N.** At
N≤1000 witness ≈0.2 s and compile ≈0.5 s (both <1%); at **N=2000–3000 they grow to
~20–30 s (witness) and ~70–90 s (compile)** and can no longer be waved away. But
they get promoted *differently*, because one is per-proof and one is one-time:

| Metric | What it is | N≤1000 | N≈2000–3000 | Verdict |
|---|---|---|---|---|
| `witness_s` | **per-proof** solve time (`nargo execute`, before every `bb prove`) | <1% of prove | **~20–30% of prove** | **Take it into account** — fold into prover wall-clock (= witness + prove) |
| `compile_s` | **one-time** build cost (source→ACIR, once per config) | ~0.5 s | ~70–90 s | **Appendix / build-cost note** — amortized over all proofs; toolchain-dependent |
| `acir_opcodes` | pre-arithmetization size | — | — | Not a cost axis; only via the ratio `gates/acir` (below) |

**`witness_s` — promote to a visible per-proof cost at large N.**
- It is regenerated on *every* proof (not amortized), so the honest per-proof
  prover cost is **witness + prove**, not prove alone. Report prove as the dominant
  term but show witness as a stacked component (see the planned bar plot, §16).
- It already follows the right deployment structure: the aggregator computes
  `witness_s` with the **same `innerstep + outer` rule** as `prove_s`, so the
  parallel/total reasoning is unchanged — witness is just a now-visible term.
- It **decomposes favorably**: recursion/hierarchical only execute **M-sized**
  inner segments + a **fixed** (N-independent) outer witness — never a full-N
  witness — so per-node witness ≈ M-sized. Surfacing it slightly *helps* the
  decomposition story.

**`compile_s` — keep out of the per-proof / frontier comparison, but upgrade the note.**
- It's a **one-time, build-time** cost (paid once per circuit config, amortized to
  ~0 per proof in deployment; in the sweep it's compiled once per (N,K), not per
  run), and it's **toolchain-/machine-dependent** (a `nargo` performance number,
  not a cryptographic property — report the toolchain version, don't build a claim
  on it). So it does not belong on the per-proof frontier.
- But at ~90 s it's a real **build cost that scales with circuit size**, and it has
  a decomposition angle: **flat compiles a full-N monolith (worst); recursion/hier
  compile only M-sized pieces + a fixed outer/glue (bounded).** For recursion this
  is bounded *only if K co-scales with N* (else the inner segment grows — see §12).

**Meta-point: at large N, compile + witness + prove + memory all grow together —
facets of the *same* monolithic scaling wall.** This *reinforces* the thesis:
decomposition bounds all four (per-piece M-sized + fixed outer). witness joins the
headline (per-proof prover cost); compile joins the monolith-scaling-wall evidence
(build-time).

*(A fourth build-time cost — the O(N²) `merkle_builder` instance commitment — is a
separate, one-time, variant-independent setup cost; see §13 for why it's mentioned
but excluded from the comparison.)*

**The one insightful use of acir — the expansion ratio `gates/acir`:**

| | expansion |
|---|---|
| flat (any N) | **~7.6×** |
| recursion **segment** | ~8–9× |
| recursion **outer** | **~1900× (K=2) → ~3100× (K=8)** |

The outer is a *tiny program* (~1,200 ACIR opcodes) that arithmetizes into
millions of gates — i.e. recursion is expensive because **a few `verify_honk_proof`
builtins each explode into ~700k gates**, not because the program is large. Use
this once, in the recursion-alone section, to attribute the cost to the in-circuit
verifier rather than the TSP logic.

---

## 12. How far to push N (scaling beyond 1000)

- **The core claims are already made** at N≤1000 (constant outer, Σseg≈flat,
  amortizing tax, K=2 crossover, Amdahl, verifier tie). More same-K points just
  re-confirm shapes → diminishing returns.
- **The one extension worth the compute: the capability boundary.** Flat OOMs
  around **N≈6000–8000** on a 16–32 GB box (~2.45 MiB/node); if recursion (with
  suitable K) clears the same N, "recursion uses less RAM" becomes "**flat
  cannot, recursion can**" — the strongest scalability claim.
- **You must co-scale K with N.** At fixed K=2 the *segment* itself grows and
  overtakes the outer around **N≈1700** → the segment OOMs. Per-machine peak ≈
  `max(2.45·N/K, ~1024·K)` MiB; optimal **K ≈ √(N/427)** gives ~**√N** memory
  scaling vs flat's linear. Rough schedule: K=2 to ~1700, K=4 to ~8000, K=8 to
  ~16000.
- **The outer's K-growth is itself the ceiling** (≈1 GB & ~10 s per added
  verification) — and hitting it is the result that **motivates folding /
  tree-recursion** (ClientIVC, Protogalaxy) as future work.

---

## 13. Instances / the "grid" — basically irrelevant to cost

- `instance_gen.py` places nodes at **continuous** real coords in a 1000×1000
  square (not a discrete lattice), Euclidean distance × `precision=1000`. So
  there's **no crowding/collision limit** — any N fits; at N=4000 spacing is
  ~16k scaled units (no degenerate zero edges); costs fit u64/field.
- **The instance is irrelevant to the benchmark**: circuit cost depends on **N and
  the construction**, not on the matrix *values* (they're witness). Two N=4000
  instances prove identically. The instance only needs (a) a valid tour (always
  exists), (b) numeric bounds (fine). Solver optimality is also irrelevant (it
  only sets the threshold = 1.1×tour).
- **The real walls at N=2000–4000 are NOT the grid:**
  1. **2-opt is O(N²)/sweep in Python** → slow. **Fixed:** `solve()` now skips
     2-opt for `N > 1000` (`two_opt_max_n`), keeping the nearest-neighbour tour
     (a valid cycle is all the proof needs).
  2. **Merkle commitment over N² leaves** (4M at N=2000, **16M at N=4000**) →
     the real time/memory cost of instance/witness prep (`merkle_builder`).

**`merkle_builder` — what it is and how to treat it.** A Rust binary that builds
the Poseidon2 Merkle tree over the **N² cost matrix** → the public `root` + the
per-edge membership proofs (`siblings`/`path_bits`) written into each `Prover.toml`.
Rust (not Python) because the hashes must be **bit-identical** to Noir's in-circuit
Poseidon2 (same `acir`/bn254 crates; cross-checked by `tests/hash_compat`). Called
by the `run_*.py` harnesses (`--hierarchical-fs K` for plain-product/recursion, etc.). It
builds `2·next_pow2(N²)` field elements → ~70–90 MB at N=1000, **~1.3 GB and a
minute-or-two at N=4000** (16.7M sequential Poseidon2 perms).

- **Is it a thesis result? No — mention it precisely, don't address it.** It is
  **instance preprocessing**: computed *once per instance*, *publicly*, *outside*
  proving and verification (the circuit takes `root` as a public input + does only
  `DEPTH` hashes per used edge — it never rebuilds the tree). And it is **identical
  for flat / hierarchical / recursion** (same matrix → same root), so it **cancels**
  in any cross-variant comparison. Same category as `compile_s`: excluded from the
  per-proof / frontier comparison.
- **The one sentence to include (prevents an overclaim):** the **proving** cost is
  sub-quadratic (≈O(N) gates, O(N log N) in-circuit hashing), but the **instance
  commitment is O(N²)** — inherent to committing a *dense* N×N cost matrix, not a
  flaw of the ZK construction (the input *is* Θ(N²) data). So don't claim "O(N)
  end-to-end"; there's an unavoidable O(N²) public preprocessing.
- **Regime + future work:** dense-matrix instances are Θ(N²) to specify/commit →
  this family targets moderate N (hundreds–few thousand). **Sparse / structured
  instances** (geometric k-NN graphs) would commit o(N²) edges → removes the
  quadratic setup; a clean future-work hook.
- **Optimise only for workflow, not the thesis:** if the build annoys you at
  N≥4000, parallelise the level-wise loop (rayon → time) or use a streaming build
  (frontier stack → drops peak memory from ~GB to ~MB). Neither changes the
  argument (shared, one-time, excluded).

---

## 14. Tooling built/changed this session

| Script | What | Input |
|---|---|---|
| `aggregate_recursion.py` | added `--split-components` → `_seg` / `_outer` rows (+ combined) | raw |
| `aggregate_hier.py` | added `--split-components` → `_seg` / `_glue` rows (+ combined) | raw |
| `plot_recursion_stack.py` | component bars; **metric-aware** (stack additive, **grouped** memory) | **raw** |
| `plot_recursion_lines.py` | recursion lines; **colour=K, marker=component** palette | aggregated (split) |
| `plot_recursion_modes.py` | **parallel-vs-total gap** (computes both modes itself) | **raw** |
| `plot_comparison.py` | **flat-vs-recursion, curated per metric**; grid + `--separate`; `--match-n` | aggregated (flat + split) |
| `plot_prover_time_bars.py` | **prover wall-clock = witness+prove**, grouped stacked bars (flat/K2/K4/K8 per N) | aggregated (flat + recursion) |
| `plot_frontier_scatter.py` | **C7 cost-vs-cost Pareto** (verifier ↔ prover), point per variant/K at fixed N | aggregated (flat + hier + recursion) |
| `solver.py` | skip 2-opt for `N > 1000` (`two_opt_max_n`) | — |

**Which CSV where:** raw (`recursive_raw.csv`) → `aggregate_*` and the
`plot_recursion_stack`/`_modes` scripts (they need single + cumulative);
aggregated (`recursive_par.csv` with `--split-components`) → `plot.py`,
`plot_recursion_lines.py`, `plot_comparison.py`.

---

## 15. Decisions made (and why)

- **Recursion split = segments vs outer** (no fabricated `_glue` row) — honest, the
  outer is the binding layer; only the hierarchical family has a real separate glue.
- **Components delivered as separate variant rows** → `plot.py` needs no change
  (it keys lines off the `variant` column).
- **Comparison script:** aggregated input, **curated series per metric**,
  **parallel** projection for time, **metric-vs-N only** (the C7 cost-vs-cost
  scatter is a different chart type, **not built yet**).
- **Flat time comparison uses total/sequential** (matched single-machine),
  motivated by the Amdahl gap; framed as **"no speed win — memory is the win."**
- **plain-product inner:** motivate its existence theoretically (plain-sort's O(M) public surface →
  plain-product), but back the recursion-specific O(M)-absorption claim with a **minimal
  confirmatory `compare_inner.py --skip-prove` run** (gate-count delta, a few N at
  K=2) — because the rationale is empirical and a cheap run could confirm *or*
  undercut it. Don't assert it blind.
- **Thesis flow:** (1) flat + scalability wall (memory); (2) decompose → recurse,
  recursion-only at K=2/4/8 with the Amdahl gap; (3) flat_merkle vs recursion
  (curated metrics, memory crossover headline, time as honest negative);
  (4) synthesis / frontier.

---

## 16. Open / optional (not done yet)

- **Prover-time stacked bar** — **DONE**: `plot_prover_time_bars.py` (groups for
  flat/K2/K4/K8 per N, each a witness+prove stack; witness shown even where it's a
  sliver). Pass a `--mode parallel` recursion CSV for the distributed view,
  `--mode total` for single-machine. Will show the ~20–30% witness once N=2000–3000
  data exists.
- **C7 frontier scatter** — **DONE**: `plot_frontier_scatter.py` (cost-vs-cost
  Pareto, point per variant/K at fixed N; `--pareto` draws the front). **Finding:**
  the frontier *shifts with N* — at small N flat dominates and **recursion is
  dominated** (same O(1) verifier as flat at far higher memory); plain-product holds the
  memory-cheap / O(K)-verifier corner. Recursion enters the front only at large N
  (flat's memory climbs past the outer ceiling) or when perfect hiding is required.
  Plot at the largest N your data covers. Needs `hier_*` data at a matching N for
  the full triangle (else the verifier axis collapses — use two varying axes).
- **Capability-boundary run** — push flat to OOM + 2–3 recursion points past it
  with co-scaled K (N=2000/K2, 4000/K4, 8000/K4). Targeted, not a sweep.
  (Capability boundary = the N where *flat can't produce a proof at all* on the
  machine — OOM ~N≈6000–8000 on 16–32 GB — while recursion with co-scaled K still
  completes. The qualitative "flat can't, recursion can" wall, stronger than the
  quantitative memory crossover.)
- **`compare_inner.py` confirmatory run** for the plain-product-vs-plain-sort inner gate delta.
- **`merkle_builder` memory/time estimate at N=4000** (16M leaves) before a run.
- Optional helper: given target N + RAM budget, print recommended co-scaled K and
  predicted segment/outer peak.
