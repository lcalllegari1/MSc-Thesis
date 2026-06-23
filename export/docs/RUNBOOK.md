# Runbook

All commands assume the current directory is `export/`.

## Setup

```bash
python3 -m pip install -r requirements.txt
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

Use the Python interpreter from your project environment if `python3` is not the desired one, for example:

```bash
make smoke-flat PY=/path/to/python
```

## Flat Circuit Smoke Test

```bash
python3 pipeline/instance_gen.py -n 8 --out data/instance.json --dat data/matrix.dat
python3 pipeline/solver.py --json data/instance.json --out data/path.json
python3 pipeline/format_inputs.py \
  --instance data/instance.json \
  --path data/path.json \
  --out circuits/flat_full_pairwise/Prover.toml
cd circuits/flat_full_pairwise
nargo compile
nargo execute
cd ../..
```

The same flow is available as:

```bash
make smoke-flat N=8 CIRCUIT=circuits/flat_full_pairwise
```

## Benchmarks

Flat benchmark:

```bash
python3 pipeline/run.py \
  --circuit circuits/flat_full_pairwise \
  --ns 8 16 32 \
  --runs 3 \
  --out results/flat.csv
```

Hierarchical A++ benchmark:

```bash
python3 pipeline/run_hier_fs.py \
  --ns 48 96 \
  --ks 2 4 \
  --runs 3 \
  --out results/hier_fs.csv
```

Recursive benchmark:

```bash
python3 pipeline/run_recursion.py \
  --exp 2 \
  --n 8 \
  --k 2 \
  --runs 1 \
  --out results/recursion.csv
```

## Aggregation And Plots

```bash
python3 pipeline/aggregate_hier.py --in results/hier_fs.csv --out results/hier_fs_par.csv --mode parallel
python3 pipeline/aggregate_recursion.py --in results/recursion.csv --out results/recursion_par.csv --mode parallel --split-components
python3 pipeline/plot.py --csv results/flat.csv results/hier_fs_par.csv results/recursion_par.csv --out plots/frontier
```

## Correctness Tests

Each correctness file is an executable script. Start with the narrow flat baseline, then run the heavier recursive suite when `nargo`, `bb`, and `merkle_builder` are working.

```bash
python3 tests/correctness/test_flat_full_pairwise.py
python3 tests/correctness/test_recursion.py
```
