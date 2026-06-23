PY ?= python3
N ?= 8
K ?= 2
RUNS ?= 1
CIRCUIT ?= circuits/flat_full_pairwise
OUT ?= results/flat.csv

.PHONY: build-merkle smoke-flat bench-flat bench-hier-fs bench-recursion test-flat-pairwise test-recursion clean-generated

build-merkle:
	cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml

smoke-flat:
	$(PY) pipeline/instance_gen.py -n $(N) --out data/instance.json --dat data/matrix.dat
	$(PY) pipeline/solver.py --json data/instance.json --out data/path.json
	$(PY) pipeline/format_inputs.py --instance data/instance.json --path data/path.json --out $(CIRCUIT)/Prover.toml
	cd $(CIRCUIT) && nargo compile && nargo execute

bench-flat:
	$(PY) pipeline/run.py --circuit $(CIRCUIT) --ns $(N) --runs $(RUNS) --out $(OUT)

bench-hier-fs:
	$(PY) pipeline/run_hier_fs.py --ns $(N) --ks $(K) --runs $(RUNS) --out results/hier_fs.csv

bench-recursion:
	$(PY) pipeline/run_recursion.py --exp 2 --n $(N) --k $(K) --runs $(RUNS) --out results/recursion.csv

test-flat-pairwise:
	$(PY) tests/correctness/test_flat_full_pairwise.py

test-recursion:
	$(PY) tests/correctness/test_recursion.py

clean-generated:
	find circuits -type d -name target -prune -exec rm -rf {} +
	find circuits -name Prover.toml -delete
	rm -rf pipeline/merkle_builder/target data/instances
