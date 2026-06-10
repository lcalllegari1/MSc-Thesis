# Docs Index

Map of the project's markdown docs — what each is for and a suggested read order.
(For commands, see `HOWTO.md`. For the chapter plan + the current framing, see `Thesis_Outline.md`.)

> **Variant names.** Variants are now `{regime}-{mechanism}`: `flat-sort` / `flat-product` /
> `plain-sort` / `plain-product` / `committed-sort` / `committed-product` / `recursive-sort` /
> `recursive-product`. Full scheme + old↔new↔code mapping in `Thesis_Outline.md` §N (quick copy in
> `DESIGN.md`). Code identifiers (`hierarchical_segment_fs`, …) are unchanged. Thesis prose uses
> **stitching tax** (internal docs may still say "binding tax").
>
> **Status (2026-06-10).** All benchmark sweeps are **done** (incl. the isolation sweeps —
> the K× speedup is **measured**; see the `ISOLATION_BENCHMARK.md` status banner and
> `Thesis_Outline.md` §6.4). The docs that still used the old 12-chapter scheme
> (`NARRATIVE_SCRIPT.md`, `NARRATIVE_FRAMING.md`, `HIERARCHICAL_EXPLAINED.md`) now carry an
> **old→new chapter remap banner** at the top — translate on read; their substance is current.
> Drafts: Ch 1 done (structure tour stubbed), Ch 4 §4.1–4.2 done (`thesis/drafts/`).

## Start here — the canonical framing
| Doc | What it is |
|---|---|
| `Thesis_Outline.md` | **The canonical document.** The read-first framing (the dualism + the stitching tax + the fingerprint lever, the variant grid, the column/row/forbidden-diagonal discipline), the **§N naming convention**, the linear **7-chapter** plan, the frontier-figure options, the drafting order. Read this first. |
| `NARRATIVE_SCRIPT.md` | **The drafting blueprint.** Stages the body as a three-act play: every variant is a character with a role, an entrance, the claims it lands, and its comparisons. The scene→section map, the load-bearing hinges, the comparison ledger, the refrains. *(Chapter/scene numbers predate the 7-chapter remap.)* |
| `HOWTO.md` | All commands: build / prove / verify, benchmarking, aggregation, plotting, tests. The operational entry point. |
| `DESIGN.md` | Living design log: the naming convention, shared architecture, the variant family, the dualism + stitching-tax reframe, and the progress checklist (source of truth for what's implemented). |
| `DESIGN_SPACE.md` | **The alternatives ledger (roads not taken).** Per-decision full alternative space — including options *stronger* than ours — with verdicts, the viva threats to rehearse, defense lines, and the smart things possibly missed. The defensive companion to `DESIGN.md`. |

## Theory & framing (detail behind the outline's framing)
| Doc | What it is |
|---|---|
| `FRONTIER_REFRAME.md` | The findings synthesis: dualism, stitching tax, the pick-two triangle, the family-generating decisions, the commitment fix, the `plain-sort`-not-dominated-by-`plain-product` result (F7), the privacy ladder, resolved decisions. |
| `NARRATIVE_FRAMING.md` | **Prose source (demoted).** The long-form paragraphs behind the script: the controlled walk, the {flat,recursive}×{sort,product} factorial + the witness-time inversion, per-variant transition prose. Come here for full paragraphs while drafting. *(Chapter numbers predate the remap.)* |
| `SOUNDNESS_AND_HIDING.md` | **The security-class reference.** Computational / unconditional / information-theoretic / perfect / statistical (definitions, axes, the two impossibility walls), the two-layer soundness model, the ε-term taxonomy, and why "structural ≠ IT-ZK". Grounds the background, the soundness plan, and the privacy ladder. |
| `MOTIVATION_AND_OBJECTIONS.md` | Defense-prep register: anticipated objections (gentle→hostile) with concede-then-defend answers. |
| `FIGURES_AND_METRICS.md` | Analysis-design menu: derived metrics, plot types (Pareto scatter), alt axes, open figure decisions. |
| `RELATED_WORK.md` | Comparison-chapter scaffold: SOTA grouped by frontier corner, synthesis table, the gap. Comparison vs current research — not background. |

## Technical references (per construction)
| Doc | What it is |
|---|---|
| `HIERARCHICAL_EXPLAINED.md` | The deep reference for every variant — `plain-sort` (§8), `plain-product` (§9), `committed-*` (§9b), the disclosing "B" (§10), recursion; privacy analysis + the ladder. *(Internal §-numbers are the doc's own, not thesis chapters.)* |
| `HIER_FS_IMPL.md` | `plain-product` implementation deep-dive (grand product + in-circuit Fiat–Shamir). |
| `Recursive_inner_circuit_choice_explained.md` | Why the recursion inner is the `plain-product` segment (O(1) public surface) rather than `plain-sort`. |
| `RECURSION_COMPARISON_NOTES.md` | Answer-sheet for the flat-vs-recursion questions: segment/outer/aggregate decomposition, per-metric aggregation rules, deployment models, the comparison taxonomy, scaling notes. |

## Methodology
| Doc | What it is |
|---|---|
| `CROSSREFS.md` | **The cross-reference ledger.** Label registry + intended forward/back references between chapters; what each not-yet-written section owes. Maintained as chapters are drafted (out of order). Companion: `thesis/drafts/_stubs.typ` (compile-safe placeholder labels), `pipeline/check_refs.py` (deferred). |
| `ISOLATION_BENCHMARK.md` | **DONE** — methodology that produced the measured K× speedup (`results/hier_*_iso.csv`; ~6.5× `plain-product`, ~4.7× `plain-sort` at N=3000 K=8). Kept as the §6.4 write-up source. |
| `HIER_MEASUREMENT_AND_PLOTS.md` | Measurement semantics (per-segment vs cumulative, the `--isolated`/`--mode` knobs, concurrent vs isolated claims) + a plot taxonomy by the question each chart answers. Read before designing figures. |

## Archived (historical — `docs/archive/`, not current framing)
| Doc | What it is |
|---|---|
| `archive/supervisor_report_draft.md` | Flat-phase progress report; predates committed/recursion/stitching-tax and the renaming. Superseded; a Ch 2/Ch 4 prose source only. |
| `archive/VARIANT_A_IMPLEMENTATION.md` | Pre-build implementation plan for `plain-sort`; substance realized in `HIERARCHICAL_EXPLAINED.md` §8 + Appendix A. Kept for the N=8/K=2 reference values. |

## Suggested read order
1. `Thesis_Outline.md` (the framing + §N + the chapter map) → the what and why.
2. `FRONTIER_REFRAME.md` → the findings behind it.
3. `HIERARCHICAL_EXPLAINED.md` → per-variant detail as needed.
4. `NARRATIVE_SCRIPT.md` + `NARRATIVE_FRAMING.md` + `MOTIVATION_AND_OBJECTIONS.md` → drafting & defense.
5. `HOWTO.md` → to run anything.

*Memory note: the persistent project memory (`MEMORY.md` index + `project_*` files) tracks live status
across sessions; this index is the human-facing doc map.*
