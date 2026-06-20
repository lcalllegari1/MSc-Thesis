# Naming Convention (canonical)

This file is the single source of truth for how we name the constructions in
this thesis. It is **conceptual**: it fixes the terms and the axes they live on.
The project-wide refactor of figure/file labels to match is a **separate, later
pass** — until then, the "working label" columns record both the old and the
intended new prefixes.

The central distinction — *how many levels the proof has* — is **one axis**,
named in **two registers**: an **artifact** register (what the proof *is*) and a
**structural** register (how it's *built*). They co-vary perfectly, so either
register may be used without contradiction. "Monolithic/Composite" leads in
titles and narrative; "flat/hierarchical" is the structural justification and
the root of the working labels.

---

## 1. Primary partition — the two registers

| Artifact register | Structural register | Levels | Definition |
|---|---|---|---|
| **Monolithic** | **Flat** | 1 | A single, un-layered circuit. One prover, one proof, no sub-statements. The degenerate base of the hierarchy. |
| **Composite** | **Hierarchical** | ≥2 | A parent stage over K child stages. The full statement is decomposed; the proof is assembled from parts. |

**Coupling:** Monolithic ≡ Flat, Composite ≡ Hierarchical.

**Why "flat" is justified.** (1) *Structure:* the monolithic proof is a single,
un-layered circuit — one level, no parent, no sub-proofs — the flat
(zero-hierarchy) base case of the very hierarchy the composite proofs build up.
That single-level-ness is precisely what makes it monolithic. (2)
*Representation:* it supplies the cost matrix as a single flat N²-entry array
(the original `flat-full` variant) and treats the cycle as one flat sequence,
never segmented.

---

## 2. Binding sub-axis — applies *within* Composite only

Both composite species are hierarchical (a parent over K children). They differ
**only in how the parent binds the children.** "Hierarchical" therefore names
the structure they *share* — it is not a discriminator between them.

| Species | Parent binds children by… | Yields | Trust | Working prefix |
|---|---|---|---|---|
| **Glued** *(or Stitched — see open Q1)* | checking shared **public boundary values** (endpoints chain, partial costs sum) | K+1 separate proofs | verifier checks every piece | `glued-*` (was `hier-*`) |
| **Recursive** | **verifying the child proofs in-circuit** | one proof | verifier checks one proof that vouches for the rest | `rec-*` (was `recursion-*`) |

---

## 3. Orthogonal axes — independent of the above

| Axis | Values | Definition |
|---|---|---|
| **Permutation mechanism** | **Sort** · **Product** | How the Hamiltonian-cycle permutation is enforced. *(Legacy, not carried: pairwise, presence, inverse.)* |
| **Cost representation** | **Public** · **Committed** | Cost matrix as a public N² array vs. a Merkle root. |
| **Privacy level** | **A** · **A++** *(see open Q2)* | Boundary data revealed as needed vs. perfect-hiding / privacy-equalized (blinded commitments). *(Composite only.)* |

---

## 4. Old → new mapping

| Old regime / label | New: Composition | Binding | Other axes |
|---|---|---|---|
| `flat-{sort,product,…}` | Monolithic (Flat) | — | mechanism |
| `flat-merkle` | Monolithic (Flat) | — | representation = Committed |
| `plain` / `hier-glue(-product)` | Composite | Glued | privacy = A |
| `committed` / `hier-committed` | Composite | Glued | privacy = A++, repr = Committed |
| `hier-segment(-product)` | Composite | Glued | (the child / segment circuit) |
| `recursive` / `recursion-outer` | Composite | Recursive | — |

---

## 5. Proposed working-label grammar (for the later refactor — NOT applied yet)

```
{flat | glued | rec}-{sort | product}[-committed][-pp]
```

- `flat | glued | rec` — composition (structural register root)
- `sort | product` — permutation mechanism
- `-committed` — cost representation is committed (Merkle root) rather than public
- `-pp` — A++ ("perfect privacy") rather than A

Example: `glued-product-committed-pp`.

---

## 6. Chapter titles implied by this convention

- **Ch4: Monolithic Proofs** — with a "we call it the *flat* approach" disclaimer in the opener.
- **Ch5: Composite Proofs** — two sections: **§ Glued** (boundary-value binding) and **§ Recursive** (in-circuit proof verification).

---

## Open decisions (resolve, then delete this section)

- **Q1 — Glued vs. Stitched** for the first composite species. "Glued" matches `fig:hier-glue`; "Stitched" matches the *stitching tax* of RQ2. Pick one as canonical.
- **Q2 — Privacy axis labels.** Keep `A` / `A++`, or rename to self-describing terms (e.g. `revealing` / `hiding`)?
