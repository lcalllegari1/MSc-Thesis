# Clean Reimplementation Guide

This document is a rebuild contract for turning the current experimental thesis
workspace into a clean, documented, source-only repository.

The short answer is: yes, we can reproduce the project cleanly from scratch, but
the right move is not to polish the current root tree in place. Treat the current
repo as the reference implementation and test oracle, then rebuild a smaller
target repo around stable naming, module boundaries, and acceptance gates.

`PROJECT_BLUEPRINT.md` remains the thesis-level specification. This guide is the
implementation-level extraction plan: what to copy, what to rewrite, what to
rename, and what must be proven unchanged before the export is trusted.

## 1. Target

The exported repository should contain only:

- Noir circuits needed for the shipped construction family and mechanism-study
  controls.
- Python orchestration for instances, witnesses, benchmarks, verification,
  aggregation, and plots.
- The Rust witness builder for Poseidon2 Merkle trees, commitments, Fiat-Shamir
  values, and per-variant `Prover.toml` files.
- Correctness tests and hash-compatibility tests.
- Minimal generated-output placeholders: `data/.gitkeep`, `results/.gitkeep`,
  `plots/.gitkeep`.
- Operator docs: architecture, runbook, measurement semantics, security model,
  and this rebuild guide.

The exported repository should not contain:

- Thesis drafts, Typst source, supervisor notes, narrative docs, or defense prep.
- Historical benchmark archives.
- Generated CSV/PDF/PNG outputs.
- API exploration, recursion micro-experiments, stale variant-B work, or old
  naming-only compatibility files.
- Noir `target/`, Rust `target/`, generated `Prover.toml`, instance caches, or
  temporary shadow directories.

The existing `export/` directory is a useful staging tree, not the final design.
It already has the right circuit names and a source-only boundary, but much of
the Python and Rust structure is still copied forward from the incremental
workspace.

## 2. Source Of Truth

Use these current files as input references:

| Role | Current source |
|---|---|
| Thesis-level system spec | `PROJECT_BLUEPRINT.md` |
| Current implementation decisions | `docs/DESIGN.md` |
| Alternatives and future-work framing | `docs/DESIGN_SPACE.md` |
| Merkle leaf/index-binding design | `docs/MERKLE_LEAF_DESIGN.md` |
| Current export shape | `export/docs/ARCHITECTURE.md` |
| Current operational commands | `export/docs/RUNBOOK.md`, `docs/HOWTO.md` |
| Naming context | `thesis/NAMING.md`, `export/docs/ARCHITECTURE.md` |

For the clean repo, prefer the export naming register in code:

- `monolithic_*` for one-proof circuits.
- `composite_*` for segmented constructions.
- `plain`, `committed`, and `recursive` for the stitching regime.
- `sort` and `product` for the permutation/fingerprint mechanism.
- `segment`, `glue`, and `recursive` for component roles.

Thesis prose may still use `flat-sort`, `plain-product`, and similar conceptual
variant names. Code, file paths, CLI flags, and CSV `variant` strings should use
one consistent repository grammar.

## 3. Recommended Clean Layout

Keep the current user-facing `pipeline/` name if continuity matters, but make it
a real package internally instead of a directory of duplicated scripts.

```text
zk-tsp/
|-- README.md
|-- Makefile
|-- requirements.txt
|-- .gitignore
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- RUNBOOK.md
|   |-- SECURITY_MODEL.md
|   |-- MEASUREMENT.md
|   `-- REIMPLEMENTATION_GUIDE.md
|-- circuits/
|   |-- monolithic_committed_sort/
|   |-- monolithic_committed_product/
|   |-- monolithic_study_pairwise/
|   |-- monolithic_study_sort/
|   |-- monolithic_study_invperm/
|   |-- monolithic_study_presence/
|   |-- monolithic_study_committed_presence/
|   |-- composite_plain_sort_segment/
|   |-- composite_plain_sort_glue/
|   |-- composite_plain_product_segment/
|   |-- composite_plain_product_glue/
|   |-- composite_committed_sort_segment/
|   |-- composite_committed_sort_glue/
|   |-- composite_committed_product_segment/
|   |-- composite_committed_product_glue/
|   `-- composite_recursive/
|-- pipeline/
|   |-- cli/
|   |   |-- bench.py
|   |   |-- verify.py
|   |   |-- aggregate.py
|   |   `-- plot.py
|   |-- zk_tsp/
|   |   |-- variants.py
|   |   |-- instances.py
|   |   |-- solver.py
|   |   |-- noir.py
|   |   |-- barretenberg.py
|   |   |-- witnesses.py
|   |   |-- metrics.py
|   |   |-- composite.py
|   |   `-- verify.py
|   `-- merkle_builder/
|       |-- Cargo.toml
|       `-- src/
|           |-- main.rs
|           |-- field.rs
|           |-- merkle.rs
|           |-- cache.rs
|           |-- partition.rs
|           |-- commitment.rs
|           |-- modes/
|           |   |-- monolithic.rs
|           |   |-- plain_sort.rs
|           |   |-- plain_product.rs
|           |   |-- committed_sort.rs
|           |   `-- committed_product.rs
|           `-- toml.rs
|-- tests/
|   |-- correctness/
|   |-- hash_compat/
|   `-- unit/
|-- data/.gitkeep
|-- results/.gitkeep
`-- plots/.gitkeep
```

The CLI can preserve familiar commands by providing small wrappers, but the
shared behavior should live under `pipeline/zk_tsp/`.

## 4. Migration Map

| Current experimental path | Clean export path |
|---|---|
| `circuits/flat_merkle_sort` | `circuits/monolithic_committed_sort` |
| `circuits/flat_merkle_grand_product` | `circuits/monolithic_committed_product` |
| `circuits/flat_full_pairwise` | `circuits/monolithic_study_pairwise` |
| `circuits/flat_full_sort` | `circuits/monolithic_study_sort` |
| `circuits/flat_full_invperm` | `circuits/monolithic_study_invperm` |
| `circuits/flat_full_presence` | `circuits/monolithic_study_presence` |
| `circuits/flat_merkle_presence` | `circuits/monolithic_study_committed_presence` |
| `circuits/hierarchical_segment` | `circuits/composite_plain_sort_segment` |
| `circuits/hierarchical_glue` | `circuits/composite_plain_sort_glue` |
| `circuits/hierarchical_segment_fs` | `circuits/composite_plain_product_segment` |
| `circuits/hierarchical_glue_fs` | `circuits/composite_plain_product_glue` |
| `circuits/hierarchical_segment_c` | `circuits/composite_committed_sort_segment` |
| `circuits/hierarchical_glue_c` | `circuits/composite_committed_sort_glue` |
| `circuits/hierarchical_segment_cfs` | `circuits/composite_committed_product_segment` |
| `circuits/hierarchical_glue_cfs` | `circuits/composite_committed_product_glue` |
| `circuits/recursion` | `circuits/composite_recursive` |
| `pipeline/run.py` | `pipeline/cli/bench.py --variant monolithic_*` |
| `pipeline/run_hier*.py` | `pipeline/cli/bench.py --variant composite_*` |
| `pipeline/run_recursion.py` | `pipeline/cli/bench.py --variant composite_recursive` |
| `pipeline/verify_hier*.py` | `pipeline/cli/verify.py --variant composite_*` |
| `pipeline/verify_recursion.py` | `pipeline/cli/verify.py --variant composite_recursive` |
| `pipeline/aggregate_hier.py` | `pipeline/cli/aggregate.py --family composite` |
| `pipeline/aggregate_recursion.py` | `pipeline/cli/aggregate.py --family recursive` |
| `pipeline/merkle_builder/src/main.rs` | split into the Rust modules listed above |
| `tests/correctness/test_hierarchical_*.py` | `tests/correctness/test_composite_*.py` |

Legacy names should appear only in this migration table and possibly in one
architecture name-map section. They should not appear in code paths, CLI flags,
CSV values, or test names.

## 5. Module Boundaries

### Noir Circuits

Circuits should be dumb and local:

- No generated `Prover.toml` committed, except optional tiny examples if the
  runbook explicitly uses them.
- Each circuit directory contains only `Nargo.toml`, `src/main.nr`, and maybe a
  short `README.md` if the public/private interface is non-obvious.
- `global N`, `global M`, `global K`, and `global DEPTH` remain compile-time
  constants patched by the harness.
- Every `main.nr` begins with a short public/private input contract.
- Group comments should use the final terminology consistently:
  permutation, edge-cost binding, threshold, stitch, commitment, recursion.

Do not try to create a shared Noir library unless the deduplication is clearly
worth the complexity. Noir compile-time constants and backend behavior make
copying small verified gadgets defensible.

### Rust Witness Builder

The current `merkle_builder/src/main.rs` is doing too much:

- Poseidon2 field hashing.
- Raw-leaf Merkle tree construction.
- Tree cache load/save.
- Flat witness generation.
- Plain sort/product composite witness generation.
- Committed sort/product witness generation.
- Commitment blinding.
- CLI parsing.
- TOML formatting.
- Unit tests.

Split it by responsibility:

| Module | Owns |
|---|---|
| `field.rs` | `FieldElement` helpers, Poseidon2 two-input compression, one-input hash |
| `merkle.rs` | raw-cost leaves, tree build, root, proof extraction, path-bit convention |
| `cache.rs` | tree cache format, checksum, atomic write, stale-cache rejection |
| `partition.rs` | `N`, `K`, `M` validation, cycle slicing, internal and boundary edges |
| `commitment.rs` | `commit_fold`, blinding scalar generation |
| `toml.rs` | typed TOML writers and value formatting |
| `modes/*.rs` | one module per witness-generation mode |
| `main.rs` | CLI parse, input validation, dispatch only |

Preserve these load-bearing semantics exactly:

- Merkle leaves are raw cost values, not hashed leaves.
- Path bits are least-significant-bit first.
- The circuit checks both Merkle membership and leaf-index reconstruction.
- Tree cache misses must rebuild; cache mismatches must never be silently used.
- `X = Poseidon2([c], 1)` and `c` is the full-cycle hash-chain terminal.
- `committed-product` publishes `X` but keeps `c` private in the glue witness.
- Commitment fold is `acc = r; acc = Poseidon2(acc, value)` over the committed
  values in the same order as the circuit.

### Python Pipeline

The current duplicated runner scripts should collapse into shared modules plus a
small CLI.

Core modules:

| Module | Owns |
|---|---|
| `variants.py` | declarative registry of circuit dirs, components, globals, builder mode, verifier mode |
| `instances.py` | deterministic instance/cycle cache and threshold policy |
| `solver.py` | nearest-neighbour plus bounded 2-opt |
| `noir.py` | patch globals, compile, execute, locate artifacts |
| `barretenberg.py` | `bb gates`, `write_vk`, `prove`, `verify`, proof-size checks |
| `witnesses.py` | JSON payloads, Rust builder invocation, Prover.toml placement |
| `composite.py` | shadow directory creation, component scheduling, parallel execution |
| `metrics.py` | timing, peak-memory parsing, CSV schema |
| `verify.py` | public-input extraction and cross-checks |

CLI shape:

```bash
python -m pipeline.cli.bench --variant monolithic_committed_sort --n 8 --runs 1
python -m pipeline.cli.bench --variant composite_plain_product --n 48 --k 4 --runs 3
python -m pipeline.cli.verify --variant composite_committed_product --workdir ...
python -m pipeline.cli.aggregate --input results/raw.csv --mode parallel --out results/agg.csv
```

Compatibility wrappers such as `pipeline/run_monolithic.py` can remain for a
release or two, but they should delegate to the shared CLI and contain no logic.

## 6. Variant Registry Contract

Put all variant metadata in one Python registry. Avoid hard-coded path/name
tuples scattered across runners and verifiers.

Required fields:

```python
Variant(
    name="composite_plain_product",
    family="composite",
    components=[
        Component("segment", "circuits/composite_plain_product_segment"),
        Component("glue", "circuits/composite_plain_product_glue"),
    ],
    globals={
        "segment": ["N", "M", "DEPTH"],
        "glue": ["N", "K", "DEPTH"],
    },
    builder_mode="composite-plain-product",
    verifier_mode="plain-product",
    public_surface="root, starts, ends, partial_costs, P_is, h_ins, h_outs, c, X, threshold",
    aggregation_modes=["parallel", "total"],
)
```

The same registry should drive:

- Circuit patching.
- Witness-builder flags.
- Shadow directory naming.
- CSV variant names.
- Verification cross-checks.
- Runbook examples.
- Plot labels.

This single change removes most of the current script sprawl.

## 7. Rebuild Phases

### Phase 0: Freeze The Oracle

Before changing architecture, record the current behavior:

- Save current tool versions: `nargo --version`, `bb --version`, `rustc --version`,
  `python --version`.
- Run at least the export smoke tests.
- Run the hash compatibility test.
- Run a representative correctness subset:
  - monolithic committed sort/product,
  - composite plain sort/product,
  - composite committed sort/product,
  - composite recursive.
- Keep one tiny known-good `N=8` or `N=16` output bundle outside the clean repo
  for manual comparison.

### Phase 1: Create The Clean Skeleton

Create a fresh repo or a fresh branch. Add only:

- `.gitignore`
- `README.md`
- `Makefile`
- `requirements.txt`
- empty `data/`, `results/`, `plots/`
- `docs/ARCHITECTURE.md`
- `docs/RUNBOOK.md`

Copy the renamed circuit tree from `export/circuits/` as the starting point.
Do not copy root-level generated outputs, archives, thesis files, or old docs.

Acceptance gate:

- `rg --files` shows only source, tests, docs, and `.gitkeep` placeholders.
- `find circuits -name target -o -name Prover.toml` returns nothing unless a
  deliberate tiny example is documented.

### Phase 2: Rebuild The Rust Builder

Start from current `pipeline/merkle_builder/src/main.rs`, but split it before
adding features.

Implementation order:

1. `field.rs`
2. `merkle.rs`
3. `cache.rs`
4. `partition.rs`
5. `commitment.rs`
6. `toml.rs`
7. `modes/monolithic.rs`
8. `modes/plain_sort.rs`
9. `modes/plain_product.rs`
10. `modes/committed_sort.rs`
11. `modes/committed_product.rs`
12. thin `main.rs`

Acceptance gate:

- Rust unit tests cover the tree shape, proof reconstruction, path-bit index,
  cache mismatch rejection, hash-chain challenge, and commitment fold.
- `tests/hash_compat/` passes against Noir for both two-input and one-input
  Poseidon2.
- Builder output for a tiny instance matches the old builder semantically:
  same root, same path bits, same edge costs, same `X`, same commitment fold
  when blinding is fixed for a test.

### Phase 3: Rebuild Monolithic Workflows

Implement the Python package modules needed for monolithic runs:

- instance generation and cache,
- solver,
- circuit global patching,
- Noir compile/execute,
- `bb` gates/prove/verify,
- monolithic witness generation.

Acceptance gate:

- `monolithic_study_pairwise` smoke test works at `N=8`.
- `monolithic_committed_sort` and `monolithic_committed_product` prove and verify.
- Correctness tests reject duplicate nodes, out-of-range nodes, threshold
  failures, tampered Merkle edge costs, wrong root, and flipped path bits.

### Phase 4: Rebuild External Composite Workflows

Add composite scheduling and verification for:

- `composite_plain_sort`
- `composite_plain_product`

Acceptance gate:

- `K+1` proofs are produced for each cell.
- Shadow directories prevent target-file races.
- Verifier cross-checks catch mixed proof sets.
- Aggregation can emit both `parallel(max)` and `total(sum)` rows.
- Product variant has no Python field arithmetic in the verifier; the glue does
  the product relation in-circuit.

### Phase 5: Rebuild Committed Composite Workflows

Add:

- `composite_committed_sort`
- `composite_committed_product`

Acceptance gate:

- Segment public surface collapses to root plus commitment (and `X` for product).
- Glue public surface is root, threshold, commitments (and `X` for product).
- Cross-checks compare opaque commitments, not plaintext partition values.
- Tests cover both segment-side and glue-side commitment binding failures.

### Phase 6: Rebuild Recursive Workflow

Add `composite_recursive`.

Preserve the design decision:

- Inner proofs are `composite_plain_product_segment` proofs.
- The outer proof verifies the segment proofs in-circuit.
- The outer public surface is only root and threshold.

Acceptance gate:

- One outer proof verifies with one `bb verify`.
- No verifier-side cross-checks are required.
- The ZK proof-size guard remains pinned to the expected default ZK proof size
  for the pinned `bb` version.
- A small `N=8, K=2` recursive run completes.

### Phase 7: Rebuild Aggregation And Plots

Only after correctness is stable:

- Reintroduce aggregation.
- Reintroduce plot generation.
- Keep result CSVs generated and ignored.

Acceptance gate:

- One raw CSV schema for monolithic and composite rows, or a documented pair of
  schemas with an explicit normalizer.
- Every plotted row is gated on successful proof verification and
  `xchecks_ok == 1` where applicable.
- Measurement docs explain concurrent, isolated, parallel, total, and peak-memory
  interpretations.

### Phase 8: Documentation Pass

The clean repo should ship with:

- `README.md`: project scope, included files, prerequisites, quick smoke run.
- `docs/ARCHITECTURE.md`: variant grid, data flow, circuit family, name map.
- `docs/RUNBOOK.md`: setup, smoke runs, benchmark commands, test commands.
- `docs/SECURITY_MODEL.md`: threat model, matrix authenticity non-goal,
  soundness/hiding assumptions, public surfaces.
- `docs/MEASUREMENT.md`: CSV schema, instance cache, deployment readings,
  aggregation rules.
- `docs/REIMPLEMENTATION_GUIDE.md`: this guide, copied into the export.

Acceptance gate:

- A reader can run the smoke test from a fresh checkout using only `README.md`
  and `RUNBOOK.md`.
- A reader can understand why each circuit exists using only `ARCHITECTURE.md`.
- A reader can interpret benchmark numbers using only `MEASUREMENT.md`.

## 8. Release Checklist

Before publishing the clean repo:

- `git status --short` contains only intentional source/doc changes.
- `rg "hierarchical_|flat_merkle|flat_full|hier_fs|hier_cfs|Variant A|A\\+\\+"`
  returns nothing outside migration docs and historical name maps.
- `find . -name target -o -name Prover.toml -o -name '*.csv' -o -name '*.pdf'`
  returns nothing that is intended to be ignored.
- `cargo test --manifest-path pipeline/merkle_builder/Cargo.toml` passes.
- Hash compatibility passes.
- Correctness tests pass for all shipped variants.
- `make smoke-monolithic` passes.
- One composite smoke run passes.
- One recursive smoke run passes or is explicitly marked heavy with a documented
  command.
- README and runbook commands have been tested from a clean checkout.

## 9. Practical Strategy

Do the rebuild in two passes.

First pass: create a behavior-preserving export. Copy from `export/`, split the
Rust builder, add the variant registry, and collapse duplicated Python harnesses.
Do not change circuit logic.

Second pass: polish the public repo. Remove compatibility wrappers, tighten docs,
normalize CSV names, and ensure legacy names exist only in the name-map appendix.

This keeps risk low: every phase can be checked against the current repo, while
the final result no longer inherits the incremental implementation structure.
