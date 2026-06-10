# Motivation & Objections Register

*A defense-prep register: anticipated objections (from gentle to hostile), each
with an HONEST response that concedes what is true and defends what is sound.
Captured 2026-05-31; grow it as new objections surface. The guiding principle
(per the project's working style) is intellectual honesty — concede real gaps
plainly, because a sharply-bounded claim is more defensible than an oversold one.*

Cross-refs: `FRONTIER_REFRAME.md` (dualism, stitching tax, pick-two triangle),
`HIERARCHICAL_EXPLAINED.md` (§5.3 regimes, §6 threat models, §9.11 plain-product privacy,
§9b committed variants, §13 use-cases, §14 privacy bounds), `NARRATIVE_FRAMING.md`,
`ISOLATION_BENCHMARK.md` (O12 closure), `project_recursion_experiment` memory.

---

## A. Motivation — "why prove this at all?"

### O1. "A heuristic solver finds a good tour fast. If the matrix is public, anyone can do it. So why ZK-verify a path?"

**Concede first:** if the matrix is public **and** the route is not sensitive **and**
all you want is "does a tour ≤ T exist," then ZK is overkill — run a heuristic, or
publish the tour and let the verifier sum the edges (an O(N) check). Say this openly;
it sharply defines where the work *does* matter.

**The category error:** the proof does **not** assert "a good tour exists"
(heuristics settle that). It asserts "*my committed, hidden* route has property P
(cost ≤ T, visits required nodes, avoids forbidden ones …)" without revealing the
route. A heuristic gives the verifier *a* tour, not assurance about *the prover's*
tour. When the route must stay secret, a substitute tour is the wrong object.

**Where the value lives:**
1. **The route is the secret asset** — a firm's real route leaks customers, depots,
   capacities, schedules; they must prove compliance/cost without disclosing it
   (§13 use-cases). A public-matrix heuristic cannot certify *their* private route.
2. **The matrix is often private** (per-party costs); then *no one but the prover*
   can run the heuristic — the asymmetry the objection denies is fully restored. The
   "matrix is agreed" case is a *special case*, not the general one (§5.3).
3. **Commitment + accountability** — "I commit to route C and prove C ≤ T and is
   compliant"; under audit C opens and the commitment binds. A verifier-computed
   heuristic tour can't adjudicate a claim about C — it isn't C.
4. **Properties beyond cost** — capacity/fairness/compliance on a *private* route,
   which "a good tour exists" says nothing about.

**The deepest motivation (lead with this):** TSP is the *instrument*, not the
*product*. The contribution is a structural study of **decomposed/hierarchical ZK
proving** — the dualism (decomposition gives no ZK speedup; total work is conserved)
and the **stitching tax** (binding K independent proofs into one private statement
costs leakage + O(K) verifier). TSP is the cleanest lens: canonical NP-hard problem,
clean permutation witness, tunable N, real decomposition (clustering). The results
generalize to any decomposed-witness proof — zkRollups, IVC/folding, ML-inference
over partitioned data, supply-chain provenance. The objection targets the
application veneer; the contribution sits a level below it, in the proving
architecture.

### O2. "TSP is a toy. Why not a real application?"
TSP is deliberately an *instrument* (O1). Its value here is methodological: a clean,
scalable, decomposable NP-hard witness that exposes the dualism and stitching tax
without application-specific noise. A "real application" would *add* domain
complexity that obscures the structural results, which are the point and which
transfer. (If pressed for realism, the logistics/regulator framing of §13 is the
concrete instantiation.)

### O3. "You prove a *bound* (cost ≤ T), not optimality. So what — anyone can pick a loose T."
Correct, and intentional. Optimality proofs for TSP are co-NP-hard and not the goal.
The application picks T (an SLA, a budget, a regulatory ceiling); the proof certifies
a *specific hidden* route meets it. The verifier's interest is "is this party's
committed route within bound and compliant," not "is it optimal." A loose T is the
*verifier's* choice to accept; the cryptography faithfully certifies whatever bound
is claimed.

---

## B. Design choices

### O4. "Hierarchical decomposition gave NO gate savings — total work is conserved. So the whole idea failed."
This is **the central finding, not a failure** (the dualism). Decomposition adds a
constraint to *optimization* (shrinks the search) but weakens a constraint in *ZK*
(soundness must be bought back by O(N) glue) — opposite directions, because ZK does
no search. The payoff is **not** lower total cost; it is **parallelism + low
per-prover memory** (per-prover gates and memory drop ~1/K). Selling decomposition as
a cost win would be the dishonest move; selling it as a *redistribution* with a
parallelism/memory payoff is the honest and interesting one.

### O5. "Just use recursion (or folding) — strictly better: perfect hiding + O(1) verifier."
Recursion pays a **~704k×K** in-circuit-verification tax (2.2M gates @K=2, 3.8M @K=4
— measured), and its outer prover is heavy (~2-4 GB). The hierarchical variants
occupy the **P+C corner** (parallelism + low total cost) at conserved total work,
which recursion cannot (it sacrifices C). Folding removes the tax but is **future
work** (not in any production-grade Noir/UltraHonk stack at thesis time). The thesis
*maps the whole frontier* — recursion included as the perfect-hiding endpoint — so it
is not "ignoring" recursion; it is positioning it (pick-two triangle, F4).

### O6. "Why Poseidon-Merkle for the matrix and not a public matrix / KZG / Pedersen vector commitment?"
Poseidon2 is ZK-friendly (~264 gates/compress) and native to the Noir stack, so the
matrix commitment is cheap in-circuit and the public surface is just `root` (§5).
The commitment's *trust anchoring* (authority signature / oracle / decommit-on-
dispute) is discussed in §5; the thesis assumes *some* anchor exists, which is
standard. Alternative commitments are an orthogonal swap that wouldn't change the
structural results (only constants).

### O7. "Six variants is padding."
They are **one progression line**, not six competing solutions: flat (baseline) → plain-sort
(diagnosis: discloses) → plain-product (diagnosis: oracle-leak) → committed-sort/plain-product (cure) →
recursion (endpoint). Each is a load-bearing rung that motivates the next; B is the
analytically-characterized disclosure extreme. Removing any rung breaks the
monotone privacy ladder or the dualism/stitching-tax argument (`NARRATIVE_FRAMING.md`).

---

## C. Soundness & trust

### O8. "The external verifier cross-check is hand-rolled trusted code, not cryptography. Your soundness has a hole."
**Concede the surface:** the cross-checks (`verify_hier*.py`) expand the *trusted
code* surface. **Defend the substance:** they are deterministic, public,
assumption-free **integer/field-equality comparisons** on values that `bb verify`
has *already* cryptographically bound; they add no field arithmetic and no new
cryptographic assumption (F2). They faithfully mirror the in-circuit asserts that
recursion performs — recursion just moves them inside a proof. This is conventional
for aggregation / PCD / rollup verifiers. **Honest hardening (pending):**
auto-generate the cross-check from the circuit public-input ABI so it cannot drift,
plus property tests (`FRONTIER_REFRAME.md` Part 5, step 7).

### O9. "plain-product's 'hidden partition' is fake — you admitted it's just a confirmation oracle."
Correct, and we say so unprompted (§9.11): plain-product's `P_i` and chain anchors are
*confirmation oracles* (break work ≈ C(N,M) / (M-2)!), so its hiding is a *work
factor*, not information-theoretic. That honest diagnosis is exactly why **committed-product
exists** — it blinds those values so the oracle closes. plain-product is the honest in-between
rung, not an overclaim.

### O10. "committed-* still 'reveals K' and rests on Poseidon — so it isn't really private either."
True — and stated as the honest ceiling (§9b.4, §F9/F10): committed-* hide the
multiset *computationally* (on Poseidon) and reveal the segment count K, placing them
**one assumption below** flat/recursion (which make the partition structurally
absent, assumption-free). The contribution is the *precise characterization* of that
one-notch gap and that committed-* reach it **without** recursion's 704k×K tax.
Pedersen is noted as the unconditional-content upgrade.

### O11. "In-circuit Fiat-Shamir / random-oracle — is the grand-product check actually sound?"
Soundness is in the random-oracle model (Poseidon2 as RO), with Schwartz-Zippel error
≤ N/2^254 — negligible (§7). The challenge X is derived *after* the prover commits to
the cycle (the hash chain), defeating the fixed-X forgery. This is the standard FS
argument, and the partition-overlap negative test exercises exactly this rejection
(`test_hierarchical_{fs,cfs}.py`). *A full written proof — the FS-in-ROM reduction with the
explicit ε-bound, alongside the other variants' knowledge-soundness reductions — is planned;
the proof plan is captured in `Thesis_Outline.md` §9.8.*

---

## D. Implementation & methodology

### O12. "Your K× parallelism speedup is projected from gate ratios, not measured. The central 'parallelism win' is unproven."
**CLOSED (2026-06) — the attack no longer lands.** The isolation sweeps were run
(`results/hier_*_iso.csv`, N≤5000, K∈{2,4,8}; methodology in `ISOLATION_BENCHMARK.md`).
Measured at N=3000, K=8, critical path (max segment + glue) vs flat: `plain-product`
13.2s vs 86.1s → **~6.5×**; `plain-sort` 19.7s vs 91.9s → **~4.7×** (the serial O(N)
glue sort is the gap to ideal — the O(K)/serial symptom made visible in wall-clock).
Per-prover **peak memory** drops ~1/K as before. **The residual concession, stated
honestly:** the per-proof times are *uncontended solo runs*; the K-machine wall-clock
is their composition (max + glue), not a multi-node deployment measurement. That is a
deployment-model assumption, not a missing number — say "measured, composed under the
one-prover-per-node model."

### O13. "You only benchmark to N≈480. Real TSP has millions of cities. Does anything hold at scale?"
The **structural results are size-independent**: the dualism and stitching tax are
asymptotic/analytical, and the benchmark validates their *constants and crossovers*,
not their existence. The wall at large N is a **SNARK-backend** limitation (proving
any large circuit), not specific to this work — and folding is precisely the
scale-direction (future work). N≤480 is sufficient to exhibit the conserved-work
plateau, the ~1/K memory drop, and the recursion tax.

### O14. "You used a heuristic solver to generate the witness, so the instances are easy and the prover proves nothing hard."
The solver is **only witness generation** — it supplies *a* valid tour ≤ T for the
prover to prove possession of. The ZK proof's cost and soundness are **independent of
how the tour was found**; instance hardness does not affect the proving-architecture
study (which is the contribution). For the *application*, the prover legitimately
possesses a route (theirs); for the *thesis*, any valid witness exercises the
circuits identically.

### O15. "Single-machine, contended benchmarks confound your parallel timing."
Acknowledged and surfaced: the harness records both the isolated per-prover view
(`*_par`) and the contended total (`*_tot`); the K×-speedup model assumes one node
per segment. This is the same gap as O12 — the resolution is the isolation benchmark.

### O16. "Why Noir / UltraHonk? Your numbers are backend-specific."
The **gate counts are UltraHonk-specific and labeled as such**; the backend-
independent complexity is captured by `acir_opcodes` (and the `circuit_size/acir`
expansion ratio), which is why both are reported. UltraHonk/Noir were chosen for
maturity and tooling. The structural results (dualism, stitching tax, privacy ladder)
are backend-agnostic; a different backend would shift constants, not conclusions.

### O17. "How do I trust the circuits are correct?"
Each variant has a negative-soundness suite that confirms every tampered witness is
rejected (`tests/correctness/test_*`, 7/7 for the committed variants incl. sub-G8 /
glue-G0 commitment binding and the partition-violation check). The Rust builder's
Poseidon2 is cross-validated against Noir's (`tests/hash_compat`). The builder is
deterministic; instances are seeded.

---

## E. Scope & contribution

### O18. "This is engineering, not novel cryptography. Where's the new primitive?"
**Concede:** there is no new cryptographic primitive — by design. The contribution is
an **applied/systems** one: a structural characterization (the dualism and the
stitching tax), a privacy ladder with a precisely-located computational rung
(committed-*), and an empirical frontier map across six implemented constructions.
That is an appropriate and defensible MSc contribution; positioning it as crypto-
theory would be the overclaim. (Folding/IVC is flagged as the theory direction that
would extend it.)

### O19. "Variant B is unimplemented — the work is incomplete."
B is **analytically characterized** (§14.3) and deliberately scoped out: under its
intended matrix-public regime its privacy collapses to plain-sort's, so implementing it adds
little beyond the disclosure-extreme datapoint already described. Scoping it as
analytical is a defensible time/effort choice, stated as such.

---

*To extend: add new objections under the right section with the same
Concede-then-Defend structure, and cite the artifact that backs the defense.*
