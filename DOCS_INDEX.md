# Docs Index

Map of the project's markdown docs — what each is for and a suggested read order.
(For commands, see `HOWTO.md`. For the chapter plan, see `Thesis_Outline.md`.)

## Start here
| Doc | What it is |
|---|---|
| `DOCS_INDEX.md` | This map. |
| `HOWTO.md` | All commands: build / prove / verify, benchmarking, aggregation, plotting (`make_frontier.py`), tests. The operational entry point. |
| `DESIGN.md` | Living design doc: shared architecture, the variant family, the dualism + **binding-tax** reframe (§9), and the **progress checklist** (current source of truth for what's implemented). |

## Theory & framing (the thesis spine)
| Doc | What it is |
|---|---|
| `FRONTIER_REFRAME.md` | The synthesis: dualism, binding tax, **pick-two triangle**, privacy ladder, resolved decisions (C1–C6), next steps. |
| `NARRATIVE_FRAMING.md` | The "perfect-hiding dilemma → hierarchical escape" spine for Ch 8–10 (flat vs recursion; "best of both worlds" honestly bounded). |
| `MOTIVATION_AND_OBJECTIONS.md` | Defense-prep register: 19 anticipated objections (gentle→hostile) with Concede-then-Defend answers. |
| `FIGURES_AND_METRICS.md` | Analysis-design menu for the write-up: derived metrics, plot types (Pareto scatter), alt axes, open figure decisions. |

## Technical references (per construction)
| Doc | What it is |
|---|---|
| `HIERARCHICAL_EXPLAINED.md` | The deep reference for every variant — A (§8), A++ (§9), **committed-A/A++ (§9b)**, B (§10), recursion; privacy analysis (§9.11, §14, incl. the ladder §14.4-5). |
| `VARIANT_A_IMPLEMENTATION.md` | Variant A implementation deep-dive. |
| `HIER_FS_IMPL.md` | Variant A++ implementation deep-dive (grand product + in-circuit Fiat-Shamir). |
| `Recursive_inner_circuit_choice_explained.md` | Why the recursion inner circuit is the A++ segment (O(1) public surface). |
| `thesis_guidelines_and_per_prover_parallel_mem_explained.md` | Thesis guidelines + the per-prover parallel/memory model explainer. |
| `something_on_motivation_and_defense.md` | Older motivation/defense notes (superseded in part by `MOTIVATION_AND_OBJECTIONS.md`). |

## Write-up planning & methodology
| Doc | What it is |
|---|---|
| `Thesis_Outline.md` | Chapter-by-chapter plan (Ch 9 variants, Ch 10 frontier figure). |
| `ISOLATION_BENCHMARK.md` | Methodology + verified runnable recipe to turn the K× parallelism speedup from a projection into a measurement (closes objection O12). Run before final submission. |
| `HIER_MEASUREMENT_AND_PLOTS.md` | Measurement semantics (per-segment vs cumulative, the `--isolated`/`--mode` knobs, concurrent vs isolated deployment claims) + a **plot taxonomy** organized by the question each chart answers. Read before designing figures. |

## Point-in-time records (historical — banner-marked, not current)
| Doc | What it is |
|---|---|
| `supervisor_report_draft.md` | Flat-phase progress report; **predates committed-*/recursion/binding-tax** (see its banner). |
| `SUPERVISOR_CALL_SUMMARY.md` | 2026-05-29 call summary; **predates committed-*** (see its banner). |
| `SESSION_SUMMARY.md` | Running session log. |

## Suggested read order
1. `DESIGN.md` (§1–§9 + checklist) → the what and why.
2. `FRONTIER_REFRAME.md` → the organizing results.
3. `HIERARCHICAL_EXPLAINED.md` → per-variant detail as needed.
4. `NARRATIVE_FRAMING.md` + `MOTIVATION_AND_OBJECTIONS.md` → write-up framing & defense.
5. `HOWTO.md` → to run anything.

*Memory note: the persistent project memory (`MEMORY.md` index + `project_*` files)
tracks live status across sessions; this index is the human-facing doc map.*
