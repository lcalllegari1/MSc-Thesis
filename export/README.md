# ZK TSP Benchmark Project

This is the cleaned, source-only export of the TSP zero-knowledge proof benchmark project. The parent repository remains the experimentation workspace; this folder is intended to be the production/shipped tree.

## What Is Included

- `circuits/`: Noir circuits for the **monolithic** baseline and the **composite** constructions
  (external glue — plain and committed — and recursive). See `docs/ARCHITECTURE.md` for the
  full family and the old→new name map.
- `pipeline/`: Python benchmark, verifier, aggregation, plotting, and input-generation tools.
- `pipeline/merkle_builder/`: Rust helper for Poseidon2 Merkle inputs and composite witness files.
- `tests/correctness/`: executable soundness tests for the shipped circuit variants.
- `data/`, `results/`, `plots/`: empty runtime output directories.

Generated benchmark CSVs, plots, thesis drafts, archives, exploratory tests, and stale design notes are intentionally not part of this export.

## Prerequisites

Install and expose these tools on `PATH`:

- Python 3.11 or newer
- `nargo`
- `bb`
- Rust/Cargo, for `pipeline/merkle_builder`

Python packages are listed in `requirements.txt`.

```bash
python3 -m pip install -r requirements.txt
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

## Quick Smoke Run

From this directory:

```bash
make build-merkle
make smoke-monolithic N=8 CIRCUIT=circuits/monolithic_study_pairwise
```

For full benchmark and verification workflows, see `docs/RUNBOOK.md`. For the layout and variant model, see `docs/ARCHITECTURE.md`.
