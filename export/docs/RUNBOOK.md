# Runbook

All commands assume the current directory is `export/`.

## Setup

```bash
python3 -m pip install -r requirements.txt
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

Use the Python interpreter from your project environment if `python3` is not the desired one, for example:

```bash
make smoke-monolithic PY=/path/to/python
```

## Monolithic Circuit Smoke Test

```bash
python3 pipeline/instance_gen.py -n 8 --out data/instance.json --dat data/matrix.dat
python3 pipeline/solver.py --json data/instance.json --out data/path.json
python3 pipeline/format_inputs.py \
  --instance data/instance.json \
  --path data/path.json \
  --out circuits/monolithic_study_pairwise/Prover.toml
cd circuits/monolithic_study_pairwise
nargo compile
nargo execute
cd ../..
```

The same flow is available as:

```bash
make smoke-monolithic N=8 CIRCUIT=circuits/monolithic_study_pairwise
```

## Benchmarks

Monolithic benchmark (the crowned baseline is `monolithic_committed_sort`; the public-matrix
`monolithic_study_*` circuits run the same way):

```bash
python3 pipeline/run_monolithic.py \
  --circuit circuits/monolithic_committed_sort \
  --ns 8 16 32 \
  --runs 3 \
  --out results/monolithic.csv
```

Composite, external glue (plain-product shown; swap the harness for the other three —
`run_composite_plain_sort.py`, `run_composite_committed_sort.py`,
`run_composite_committed_product.py`):

```bash
python3 pipeline/run_composite_plain_product.py \
  --ns 48 96 \
  --ks 2 4 \
  --runs 3 \
  --out results/composite_plain_product.csv
```

Composite, recursive:

```bash
python3 pipeline/run_composite_recursive.py \
  --exp 2 \
  --n 8 \
  --k 2 \
  --runs 1 \
  --out results/composite_recursive.csv
```

## Aggregation And Plots

```bash
python3 pipeline/aggregate_composite.py --in results/composite_plain_product.csv --out results/composite_plain_product_par.csv --mode parallel
python3 pipeline/aggregate_composite_recursive.py --in results/composite_recursive.csv --out results/composite_recursive_par.csv --mode parallel --split-components
python3 pipeline/plot.py --csv results/monolithic.csv results/composite_plain_product_par.csv results/composite_recursive_par.csv --out plots/frontier
```

## Correctness Tests

Each correctness file is an executable script. Start with the narrow monolithic baseline, then run the heavier composite suites when `nargo`, `bb`, and `merkle_builder` are working.

```bash
python3 tests/correctness/test_monolithic_study_pairwise.py
python3 tests/correctness/test_composite_recursive.py
```
