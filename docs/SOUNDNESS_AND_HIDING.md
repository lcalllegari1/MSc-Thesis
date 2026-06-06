# Soundness & Hiding — Security Classes and the Thesis's Soundness Layering

*Foundational reference pinning the security-class vocabulary (computational /
unconditional / information-theoretic / perfect / statistical) and how it applies to this
thesis's soundness and privacy claims. Underpins Ch 2 background, §9.8 (soundness proofs),
and the privacy ladder (§9.6). Captured 2026-06-04. Keep definitions consistent with this
doc everywhere they appear.*

---

# Part A — The security-class taxonomy

These words are **not a flat list of three siblings.** The structure is a tree:
*unconditional/IT* is one branch, *computational* the other; *perfect* and *statistical*
subdivide the unconditional branch.

```
                 SECURITY of a property (hiding, soundness, ZK…)
                 ┌──────────────────────────┴──────────────────────────┐
     UNCONDITIONAL / INFORMATION-THEORETIC                        COMPUTATIONAL
     (holds vs an UNBOUNDED adversary; no hardness assumption)    (holds only vs a BOUNDED/PPT
                 ┌──────────────┴──────────────┐                   adversary; rests on a hardness
             PERFECT                        STATISTICAL            assumption — DL, CR, factoring…)
        (advantage / error = 0)      (advantage / error = ε,
        adversary learns EXACTLY     negligible but NONZERO,
        nothing / check never lies)  e.g. 2⁻¹²⁸, vs ANY adversary)
```

**"Unconditional" and "information-theoretic" are the same umbrella** — two emphases ("no
assumption" vs "provable by information/probability theory"). It splits into **perfect**
(zero) and **statistical** (negligible-but-nonzero). **Computational** is the other branch.

## Definitions

| Term | Definition | Error/advantage | Adversary | Rests on |
|---|---|---|---|---|
| **Computational** | secure unless someone *efficiently* breaks a hardness assumption | negligible *for PPT* | polynomial-time | an assumption (DL, collision-resistance, …) |
| **Unconditional = Information-theoretic** | secure against *any* adversary, regardless of compute | — (umbrella) | unbounded | nothing |
| ↳ **Perfect** | distributions *identical* / check *never* errs | exactly **0** | unbounded | nothing |
| ↳ **Statistical** | distributions ε-close / check errs w.p. ≤ ε | negligible, **nonzero** | unbounded | nothing |

**Anchoring examples.** *Computational:* KZG/Pedersen **binding**, Poseidon collision-resistance,
all SNARK soundness, RSA. *Perfect:* one-time pad, Pedersen **hiding**, Shamir secret sharing,
the **sort permutation check** (error 0). *Statistical:* statistically-hiding commitments,
statistical ZK, **Schwartz–Zippel with a truly random challenge** (`ε_SZ = N/|F|`).

## The three distinguishing axes

1. **Adversary power.** Computational protects only against feasible computation; unconditional
   against an adversary with infinite time ⟹ unconditional is automatically **quantum-safe** for
   that property.
2. **Dependence on an assumption.** Computational *can break* if the assumption falls (new
   algorithm, bigger/quantum computer); unconditional *cannot* — no assumption to break. The
   **longevity / "harvest-now-break-later"** axis: a computationally-hidden secret recorded today
   can be exposed in 30 years; an unconditionally-hidden one never.
3. **Whether the slack is zero.** Perfect = nothing leaks / no false proof exists. Statistical =
   a negligible but real probability, *independent of compute*.

## What each brings — and the two impossibility walls

**Computational brings efficiency and succinctness; unconditional brings permanence.** You
cannot have everything — two theorems make this concrete, and both bite in this thesis:

- **No commitment is both unconditionally hiding *and* unconditionally binding.** Pick one to be
  computational. *Pedersen* = perfectly hiding, computationally binding. *Poseidon/hash* =
  computationally hiding, (statistically) binding. ⟹ this is exactly the committed-A/A++ choice:
  Poseidon gives computational hiding cheaply; Pedersen would upgrade hiding to perfect at the
  price of computational binding + higher in-circuit cost.
- **A *succinct* argument for NP cannot have unconditional soundness.** Succinctness forces the
  verifier not to check everything, which forces reliance on a computationally-binding commitment
  ⟹ **every SNARK is an *argument* (computational soundness).** This is *why* "SNARK is an argument,
  not a proof" — a barrier, not a quirk of UltraHonk. The price of small proofs is computational
  soundness.

**The trade is always the same shape:** computational = cheap, small, flexible, but conditional
and mortal; unconditional = eternal and assumption-free, but bigger, costlier, or provably
incompatible with some other goal.

## Terminology pitfalls
- **"Information-theoretic" ≠ "perfect."** Rigorously it is the umbrella (perfect *or* statistical);
  some authors say "IT" to mean perfect. Define once, stay consistent.
- **"Statistical" is still unconditional** — the nonzero ε is a probability over randomness, not a
  computational advantage. Do not let it drift into the computational box.
- **`ε_SZ` changes class under Fiat–Shamir.** Schwartz–Zippel error is **statistical (IT)** if the
  challenge is truly random (interactive); once derived by FS from a hash it is only
  **ROM-computational** (a q-query grinding bound). Same gadget, different class by interactivity.

---

# Part B — Soundness as two layers (the §9.8 foundation)

"Soundness" in this thesis is **two distinct properties stacked.** Conflating them is the trap.

**Layer 1 — SNARK (argument) knowledge soundness.** Noir/Barretenberg's property: *"if the proof
verifies, the prover knows a wire assignment satisfying the **constraint system**."* It is an
**argument** → **computational**, error `ε_SNARK`, resting on the polynomial-commitment binding.
It is **identical across all variants** (the backend) and **meaning-agnostic** — it certifies the
gates are satisfied, not what they *mean*.

**Layer 2 — Encoding soundness (the constraint groups).** *Your* property; Noir gives nothing here:
*"if the constraint system is satisfied, the witness is a valid TSP solution."* Mostly a
**deterministic, unconditional logical implication** — the group↔cheat mapping. This is where the
variants differ and where the permutation check's soundness lives.

**The composition (not a single number):**
```
proof verifies
   ──[ε_SNARK, computational, Noir's job]──▶  witness satisfies the circuit
   ──[encoding lemmas, YOUR job]──────────▶  witness ∈ R_TSP
```

## Per-group encoding lemmas (Layer 2)

Each group gets a lemma "satisfied ⟹ property, with error ε":

| Group | Property enforced | Error | Class |
|---|---|---|---|
| Range (G1) | cycle[i] ∈ [0,N) | 0 | perfect (deterministic) |
| Permutation (G2, **sort**) | {cycle} = [0,N) | 0 | **perfect** |
| Permutation (G2, **grand-product+FS**) | {cycle} = [0,N) | `ε_SZ + ε_FS` | **statistical → ROM-computational** |
| Edge-cost / Merkle (G3) | used cost = committed matrix entry | `ε_CR` | **computational** (Poseidon CR) |
| Threshold (G4) | Σ costs ≤ T | 0 | perfect (deterministic) |

Two groups carry a cryptographic assumption: **Merkle always** (Poseidon collision-resistance);
**permutation only under gp** (`ε_SZ + ε_FS`). The sort variant's permutation is assumption-free.

## The error taxonomy — these are NOT all "the same computational"

- **`ε_SNARK`** — computational; *cryptographic hardness* (commitment binding / AGM).
- **`ε_CR`** — computational; Poseidon collision-resistance.
- **`ε_SZ`** — **information-theoretic** (probability over a random X); no assumption.
- **`ε_FS`** — **ROM**-based (idealized hash; bounds a q-query grinder).

The sort permutation check has **none** of `ε_CR`-on-permutation / `ε_SZ` / `ε_FS`; gp adds
`ε_SZ + ε_FS`. *This single error term is the "structural vs computational soundness" flip of the
fingerprint lever (§8.7) made formal.*

## The nested-Schwartz–Zippel insight (worth a §8.7 sentence)

`ε_SNARK` itself decomposes: the underlying PLONK/Honk **IOP** is *information-theoretically*
sound (its polynomial-identity checks are Schwartz–Zippel); only the **compilation** to an
argument (the polynomial commitment) injects the *computational* `ε_PCS`. So the SNARK already
runs SZ + Fiat–Shamir *around* the circuit. The **grand product runs the same `ε_SZ + ε_FS`
machinery a second time, *inside* the circuit**; the **sort** does not (it bolts a deterministic
layer onto the SNARK's probabilistic core). This is the same phenomenon as recursion's
**Fiat–Shamir floor** (the outer recomputes the inner verifier's transcript in-circuit). Framing:
gp = "let the circuit use the proof system's native probabilistic argument"; sort = "encode it
deterministically." The lever is then *inevitable*, not arbitrary.

## How §9.8 composes (deliverable)

You **do not reprove `ε_SNARK`** — cite UltraHonk KS as an assumption. Prove the Layer-2 encoding
lemmas (deterministic ones rigorously; gp/Merkle modulo their named assumption), then compose into
**one knowledge-soundness theorem per variant**:

> *Assuming UltraHonk KS, Poseidon CR (+ Poseidon-as-RO for gp, + commitment binding for committed-\*,
> + recursion KS for recursion), construction V is knowledge-sound for `R_TSP` with error
> `ε ≤ ε_SNARK + ε_CR (+ ε_SZ + ε_FS)(+ ε_bind)(+ ε_rec)`.*

**Honest-scope ladder (writes itself from the error terms):**
- **flat-sort, A, committed-A** — fully provable at paper rigor (deterministic lemmas + `ε_SNARK` + `ε_CR`).
- **flat-gp, A++, committed-A++** — provable *modulo* `ε_SZ + ε_FS` in the ROM.
- **recursion** — + recursion KS + the in-circuit FS floor.

**Negative tests (§10.1a) validate but do not prove.** A hand-built non-permutation is rejected at
`nargo execute` (validates the deterministic encoding lemmas) — but the tests **cannot** exercise
the `ε_SZ` failure (it is negligible by construction), which is exactly why that branch needs the
analytic bound, not a test.

---

# Part C — Where each class lands in the thesis

| Object | Class | Note |
|---|---|---|
| SNARK knowledge soundness | computational | the argument barrier; identical across variants |
| Sort permutation check | perfect (unconditional) | error 0, deterministic |
| Grand-product + FS | statistical (interactive) → ROM-computational (FS) | `ε_SZ` IT, `ε_FS` ROM |
| Merkle binding | computational | Poseidon collision-resistance |
| SNARK ZK (route hiding) | computational/statistical | **identical across variants — not a discriminator** |
| committed-* hiding (Poseidon) | computational | hash one-wayness |
| committed-* hiding (Pedersen, analytical) | perfect content + computational binding | the impossibility wall, made concrete |

## The crucial fourth thing — "structural" is none of these

The privacy ladder's top rung (flat/recursion: partition **structurally absent**) is **not a hiding
class at all.** The other rungs *publish the partition and hide it* (computationally or
unconditionally). Flat/recursion **do not publish it** — it is ordinary witness, protected by the
*same* SNARK-ZK that already hides the route, with **no extra assumption specific to the partition.**

That is why **structural ≠ information-theoretic ZK**:
- *IT-hiding* = the data **is present** and provably leaks nothing even to an unbounded verifier.
- *Structural* = the data **is not in the public surface to begin with**, so "how well hidden" never arises.

The privacy ladder is "assumption-**decreasing**" because each step down either removes the
partition's *extra* hiding assumption (Pedersen → recursion) or makes the partition disappear
entirely (structural = **zero marginal assumption** beyond the SNARK-ZK common to all variants).

---

*Related: `DESIGN_SPACE.md` (the Merkle-vs-lookup and proof-system choices that set `ε_CR`/`ε_SNARK`),
`FRONTIER_REFRAME.md` (the privacy ladder), `Thesis_Outline.md` §8.7 (the fingerprint lever) / §9.6
(privacy ladder) / §9.8 (the soundness theorems this doc grounds).*
