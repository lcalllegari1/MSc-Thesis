PY ?= python3
N ?= 8
K ?= 2
RUNS ?= 1
CIRCUIT ?= circuits/monolithic_study_pairwise
OUT ?= results/monolithic.csv

.PHONY: build-merkle smoke-monolithic bench-monolithic bench-composite-plain-product bench-composite-recursive test-monolithic-study-pairwise test-composite-recursive clean-generated

build-merkle:
	cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml

smoke-monolithic:
	$(PY) pipeline/instance_gen.py -n $(N) --out data/instance.json --dat data/matrix.dat
	$(PY) pipeline/solver.py --json data/instance.json --out data/path.json
	$(PY) pipeline/format_inputs.py --instance data/instance.json --path data/path.json --out $(CIRCUIT)/Prover.toml
	cd $(CIRCUIT) && nargo compile && nargo execute

bench-monolithic:
	$(PY) pipeline/run_monolithic.py --circuit $(CIRCUIT) --ns $(N) --runs $(RUNS) --out $(OUT)

bench-composite-plain-product:
	$(PY) pipeline/run_composite_plain_product.py --ns $(N) --ks $(K) --runs $(RUNS) --out results/composite_plain_product.csv

bench-composite-recursive:
	$(PY) pipeline/run_composite_recursive.py --exp 2 --n $(N) --k $(K) --runs $(RUNS) --out results/composite_recursive.csv

test-monolithic-study-pairwise:
	$(PY) tests/correctness/test_monolithic_study_pairwise.py

test-composite-recursive:
	$(PY) tests/correctness/test_composite_recursive.py

clean-generated:
	find circuits -type d -name target -prune -exec rm -rf {} +
	find circuits -name Prover.toml -delete
	rm -rf pipeline/merkle_builder/target data/instances
