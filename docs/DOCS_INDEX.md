# Docs Index

Map of the project's markdown docs — what each is for and a suggested read order.
(For commands, see `HOWTO.md`. For the chapter plan + the current framing, see
`Thesis_Outline.md`.)

## Start here — the canonical framing
| Doc | What it is |
|---|---|
| `Thesis_Outline.md` | **The canonical document.** Part 0 carries the current framing (the dualism + the binding tax + the **fingerprint lever**, the variant grid, the column/row/forbidden-diagonal comparison discipline, the two frontier-figure options) and the full chapter-by-chapter plan. Read this first; it supersedes the older "crossover" / "three-variants" framings (in git history at checkpoint `ec5932a`). |
| `NARRATIVE_SCRIPT.md` | **The drafting blueprint for Ch 5–10.** Stages the thesis as a three-act play: every variant is a character with a role, an entrance, lines (the claims it lands), and interactions (the comparisons). Scene→section map, stage-presence timeline, the nine load-bearing hinges, the comparison ledger, the refrains. Draft Part II/III from here; it instantiates `Thesis_Outline.md` Part 0. |
| `HOWTO.md` | All commands: build / prove / verify, benchmarking, aggregation, plotting (`make_frontier.py`), tests. The operational entry point. |
| `DESIGN.md` | Living design doc: shared architecture, the variant family, the dualism + binding-tax reframe (§9), and the progress checklist (source of truth for what's implemented). |
| `DESIGN_SPACE.md` | **The alternatives ledger (roads not taken).** Per-decision full alternative space — including options *stronger* than ours — with verdicts, the four viva threats to rehearse (STARK/Plonky2 recursion, committed-table lookups, folding, optimality-vs-feasibility), defense lines, and the smart things possibly missed. The defensive companion to `DESIGN.md`. |

## Theory & framing (detail behind Part 0)
| Doc | What it is |
|---|---|
| `FRONTIER_REFRAME.md` | The findings synthesis: dualism, binding tax (F3), the **pick-two triangle** (F4), the family-generating decisions (F5), the commitment fix (F6), the A-not-dominated-by-A++ result (F7), the privacy ladder, resolved decisions (C1–C6). |
| `NARRATIVE_FRAMING.md` | Detailed narrative prose: the monotone controlled-walk (§11), the {flat,recursive}×{sort,grand-product} factorial (§8.4) and the measured witness-time inversion (§8.5), per-variant transition prose (§9.6). The outline's Part 0 summarizes this; come here for full paragraphs while drafting. |
| `SOUNDNESS_AND_HIDING.md` | **The security-class reference.** Pins computational / unconditional / information-theoretic / perfect / statistical (definitions, axes, the two impossibility walls), the two-layer soundness model (SNARK KS vs encoding lemmas), the `ε`-term taxonomy + nested-Schwartz–Zippel insight, and why "structural ≠ IT-ZK". Grounds Ch 2 background, §9.8 soundness proofs, and the privacy ladder. |
| `MOTIVATION_AND_OBJECTIONS.md` | Defense-prep register: anticipated objections (gentle→hostile) with Concede-then-Defend answers. |
| `FIGURES_AND_METRICS.md` | Analysis-design menu: derived metrics, plot types (Pareto scatter), alt axes, open figure decisions. |
| `RELATED_WORK.md` | Comparison-chapter scaffold: SOTA grouped by frontier corner, synthesis table, the gap. Comparison vs current research — not background. |

## Technical references (per construction)
| Doc | What it is |
|---|---|
| `HIERARCHICAL_EXPLAINED.md` | The deep reference for every variant — A (§8), A++ (§9), committed-A/A++ (§9b), B (§10), recursion; privacy analysis (§9.11, §14, incl. the ladder §14.4–5). |
| `VARIANT_A_IMPLEMENTATION.md` | Variant A implementation deep-dive. |
| `HIER_FS_IMPL.md` | Variant A++ implementation deep-dive (grand product + in-circuit Fiat–Shamir). |
| `Recursive_inner_circuit_choice_explained.md` | Why the recursion inner is the A++ segment (O(1) public surface). |
| `RECURSION_COMPARISON_NOTES.md` | Answer-sheet for the flat-vs-recursion questions: segment/outer/aggregate decomposition, per-metric aggregation rules, deployment models, the comparison taxonomy, scaling notes. |

## Methodology
| Doc | What it is |
|---|---|
| `ISOLATION_BENCHMARK.md` | Methodology + runnable recipe to turn the K× parallelism speedup from a projection into a measurement (closes objection O12). Run before final submission. |
| `HIER_MEASUREMENT_AND_PLOTS.md` | Measurement semantics (per-segment vs cumulative, the `--isolated`/`--mode` knobs, concurrent vs isolated claims) + a plot taxonomy by the question each chart answers. Read before designing figures. |

## Point-in-time records (historical — not current framing)
| Doc | What it is |
|---|---|
| `supervisor_report_draft.md` | Flat-phase progress report; predates committed-*/recursion/binding-tax. Useful as a chapter-source for Parts I–II, but the framing is superseded by `Thesis_Outline.md` Part 0. |

## Suggested read order
1. `Thesis_Outline.md` Part 0 → the framing and the map.
2. `FRONTIER_REFRAME.md` → the findings behind it.
3. `HIERARCHICAL_EXPLAINED.md` → per-variant detail as needed.
4. `NARRATIVE_FRAMING.md` + `MOTIVATION_AND_OBJECTIONS.md` → drafting prose & defense.
5. `HOWTO.md` → to run anything.

*Memory note: the persistent project memory (`MEMORY.md` index + `project_*` files)
tracks live status across sessions; this index is the human-facing doc map.*
