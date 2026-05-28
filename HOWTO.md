# Running the TSP ZKP Project

Practical reference for running every tool in this project.
All commands assume you are in the project root: `/home/callexyz/Desktop/plsgod/`

---

## Environment setup

Activate the Python environment once at the start of a session:

```bash
conda activate zk-tsp
```

All `python` commands below assume this environment is active.
If running from a script (non-interactive), prefix each Python call with
`conda run -n zk-tsp python` instead of just `python`.

---

## Full pipeline — quick start (n = 5)

Run these commands in order to go from nothing to a verified ZK proof.

```bash
# 1. Generate a TSP instance (graph + coordinates)
python pipeline/instance_gen.py -n 5 --out data/instance.json --dat data/matrix.dat

# 2. Solve for a Hamiltonian cycle
python pipeline/solver.py --json data/instance.json --out data/path.json

# 3. Format the circuit inputs (produces Prover.toml)
python pipeline/format_inputs.py \
  --instance data/instance.json \
  --path     data/path.json \
  --out      circuits/flat_full_pairwise/Prover.toml

# 4. Compile the Noir circuit  (run from the circuit directory)
cd circuits/flat_full_pairwise
nargo compile

# 5. Generate the witness (checks the proof statement is satisfiable)
nargo execute

# 6. Pre-compute the verification key  (do this once per compiled circuit)
bb write_vk \
  -b target/flat_full_pairwise.json \
  -o target/vk

# 7. Prove  (uses the pre-computed VK — no warning, better performance)
bb prove \
  -b target/flat_full_pairwise.json \
  -w target/flat_full_pairwise.gz \
  -k target/vk/vk \
  -o target/proof

# 8. Verify
bb verify \
  -k target/vk/vk \
  -p target/proof/proof \
  -i target/proof/public_inputs

# Return to project root when done
cd ../..
```

---

## Individual tools

### `pipeline/instance_gen.py` — generate a TSP instance

Produces a JSON file with node coordinates and the integer-scaled adjacency matrix.

```bash
python pipeline/instance_gen.py \
  -n 10          \    # number of nodes (required)
  --seed 42      \    # random seed for reproducibility (default: 42)
  --out  data/instance.json  \   # JSON output path (default: data/instance.json)
  --dat  data/matrix.dat         # plain-text matrix for external solvers (default: data/matrix.dat)
```

**Output — `instance.json` structure:**
```
metadata.n          — number of nodes
metadata.grid_size  — coordinate space side length (default: 1000)
metadata.precision  — distance scaling factor (default: 1000)
metadata.seed       — seed used
nodes               — list of [x, y] coordinates
matrix              — n x n list-of-lists, integer edge costs
```

---

### `pipeline/solver.py` — find a Hamiltonian cycle

Runs nearest-neighbour construction followed by 2-opt local search.
Produces a **cycle**: a list of n node indices.
The closing edge (last node back to first) is implicit — not stored in the file.

```bash
python pipeline/solver.py \
  --json data/instance.json  \   # instance JSON from instance_gen.py (required)
  --out  data/path.json           # output path JSON (default: data/path.json)
```

**Output — `path.json` structure:**
```json
[0, 3, 2, 1, 4]
```
A flat list of n node indices. The cycle is:
`0 -> 3 -> 2 -> 1 -> 4 -> 0` (return edge implicit).

---

### `pipeline/visualize.py` — plot instance and tour

```bash
# Plot the instance only (no tour)
python pipeline/visualize.py \
  --json data/instance.json

# Plot the instance with the tour overlaid
python pipeline/visualize.py \
  --json data/instance.json \
  --path data/path.json \
  --multiplier 1.1          # used to display the threshold (default: 1.1)

# Save to file instead of displaying
python pipeline/visualize.py \
  --json data/instance.json \
  --path data/path.json \
  --out  plots/tour_n5.png
```

---

### `pipeline/format_inputs.py` — create Prover.toml for the circuit

Reads instance + path, computes the threshold, and writes the TOML file
that `nargo execute` reads to generate the witness.

```bash
python pipeline/format_inputs.py \
  --instance  data/instance.json          \   # required
  --path      data/path.json              \   # required
  --out       circuits/flat_full_pairwise/Prover.toml  \  # required
  --multiplier 1.1                            # threshold = actual_cost * multiplier (default: 1.1)
```

**What it writes** (Prover.toml):
```toml
cycle        = ["0", "3", "2", "1", "4"]          # private witness
cost_matrix  = ["0", "501713", ..., "0"]           # public: n*n flat matrix
threshold    = "2500798"                           # public: cost upper bound
```

---

## Circuit workflow — `circuits/flat_full_pairwise`

All nargo and bb commands must be run from inside the circuit directory:

```bash
cd circuits/flat_full_pairwise
```

### Compile

Reads `src/main.nr`, produces `target/flat_full_pairwise.json` (ACIR bytecode):

```bash
nargo compile
```

### Generate witness

Reads `Prover.toml`, solves the circuit, writes `target/flat_full_pairwise.gz`:

```bash
nargo execute
```

If this succeeds, the constraint system is satisfied — the proof statement is
true for your inputs.  If it fails, one of the assertions in the circuit
was violated (check the error message).

### Write verification key

The VK only depends on the circuit structure, not on the witness.
Compute it once after each `nargo compile` and reuse it for all proofs
of that circuit. Passing it explicitly to `bb prove` avoids recomputation
and eliminates the performance warning.

```bash
bb write_vk \
  -b target/flat_full_pairwise.json \
  -o target/vk
```

Output written to `target/vk/`:
```
vk        — the verification key (pass this to bb prove and bb verify)
vk_hash   — hash of the verification key
```

### Prove

Generate the ZK proof using the pre-computed VK:

```bash
bb prove \
  -b target/flat_full_pairwise.json \
  -w target/flat_full_pairwise.gz \
  -k target/vk/vk \
  -o target/proof
```

Output written to `target/proof/`:
```
proof           — the ZK proof bytes
public_inputs   — the public inputs (cost_matrix + threshold)
```

### Verify

Verify the proof using the same VK:

```bash
bb verify \
  -k target/vk/vk \
  -p target/proof/proof \
  -i target/proof/public_inputs
```

Separating prove and verify into distinct commands makes it easy to time
each step independently, which is one of the benchmarking metrics.

### Get gate/constraint count

```bash
bb gates -b target/flat_full_pairwise.json
```

Reports `acir_opcodes` (number of ACIR operations) and `circuit_size`
(number of UltraHonk gates after arithmetisation).
`circuit_size` is the main metric for comparing circuit complexity across N values.

---

## Circuit workflow — `circuits/flat_full_sort`

Same workflow as `flat_full_pairwise`; only the circuit directory and artifact
names differ. The step-by-step explanations apply unchanged — refer to the
section above for details on what each command does.

```bash
cd circuits/flat_full_sort
```

### Format inputs (from project root)

`format_inputs.py` is circuit-agnostic; just point `--out` at the right directory:

```bash
python pipeline/format_inputs.py \
  --instance data/instance.json \
  --path     data/path.json \
  --out      circuits/flat_full_sort/Prover.toml
```

### Compile, execute, prove, verify

```bash
nargo compile
nargo execute

bb write_vk \
  -b target/flat_full_sort.json \
  -o target/vk

bb prove \
  -b target/flat_full_sort.json \
  -w target/flat_full_sort.gz \
  -k target/vk/vk \
  -o target/proof

bb verify \
  -k target/vk/vk \
  -p target/proof/proof \
  -i target/proof/public_inputs

bb gates -b target/flat_full_sort.json
```

```bash
cd ../..
```

### Key difference from flat_full_pairwise

The permutation check uses `sort_via` (Noir stdlib) instead of pairwise modular
inverses. Internally this runs an unconstrained quicksort (zero circuit gates)
and then verifies the result in O(N) constrained operations via `check_shuffle`.
The range check (GROUP 1 in pairwise) is subsumed: if `sorted(cycle) == [0,...,N-1]`
and `sorted` is proven to be a rearrangement of `cycle`, every entry is necessarily
in range.

---

## Circuit workflow — `circuits/flat_full_invperm`

Same workflow as the other flat variants. The only differences are:
1. `Prover.toml` gains an `inv_perm` field — `format_inputs.py` generates it
   automatically when the `--out` path contains `invperm`.
2. The circuit takes `inv_perm` as a second private input.

### Format inputs (from project root)

```bash
python pipeline/format_inputs.py \
  --instance data/instance.json \
  --path     data/path.json \
  --out      circuits/flat_full_invperm/Prover.toml
```

Because `invperm` appears in the `--out` path, `format_inputs.py` automatically
computes and writes the inverse permutation alongside `cycle`.

### Compile, execute, prove, verify

```bash
cd circuits/flat_full_invperm

nargo compile
nargo execute

bb write_vk \
  -b target/flat_full_invperm.json \
  -o target/vk

bb prove \
  -b target/flat_full_invperm.json \
  -w target/flat_full_invperm.gz \
  -k target/vk/vk \
  -o target/proof

bb verify \
  -k target/vk/vk \
  -p target/proof/proof \
  -i target/proof/public_inputs

bb gates -b target/flat_full_invperm.json

cd ../..
```

### Key difference from flat_full_sort

The permutation check is entirely explicit: the prover supplies `inv_perm[v]`
(the position of node `v` in `cycle`) and the circuit checks `cycle[inv_perm[v]] == v`
for each `v`. This removes the N−1 sortedness checks that `sort_via` requires,
reducing the constrained gate count from ~3N to 2N for the permutation step.
The prover's extra cost is one O(N) scan off-circuit to build `inv_perm`.

---

## Circuit workflow — `circuits/flat_full_presence`

Same workflow as the other flat variants. The prover interface is the simplest
of the O(N) variants: only `cycle` is needed (no `inv_perm` extra witness).

### Format inputs (from project root)

```bash
python pipeline/format_inputs.py \
  --instance data/instance.json \
  --path     data/path.json \
  --out      circuits/flat_full_presence/Prover.toml
```

### Compile, execute, prove, verify

```bash
cd circuits/flat_full_presence

nargo compile
nargo execute

bb write_vk \
  -b target/flat_full_presence.json \
  -o target/vk

bb prove \
  -b target/flat_full_presence.json \
  -w target/flat_full_presence.gz \
  -k target/vk/vk \
  -o target/proof

bb verify \
  -k target/vk/vk \
  -p target/proof/proof \
  -i target/proof/public_inputs

bb gates -b target/flat_full_presence.json

cd ../..
```

### Key difference from flat_full_invperm

The permutation check uses a mutable boolean mark array `seen[0..N-1]` rather
than an inverse-permutation witness. For each position i in the cycle the circuit
asserts `seen[cycle[i]] == false` then sets `seen[cycle[i]] = true`. If every
check passes, all N values in `cycle` are distinct; combined with the explicit
range check (GROUP 1), `cycle` is a permutation of {0,...,N-1}.

The tradeoff vs `flat_full_invperm`:
- **Prover interface simpler:** no `inv_perm` to compute or supply.
- **Circuit slightly heavier:** `seen` compiles to a RAM table (read-write
  memory) in UltraHonk rather than the ROM table used by `flat_full_invperm`.
  RAM carries higher per-access overhead (~4N ops vs ~2N ops for the permutation
  step), so `flat_full_presence` is expected to have a larger `circuit_size` at
  equal N.
- **GROUP 1 is explicit:** unlike `flat_full_sort` and `flat_full_invperm`, the
  range check `cycle[i] < N` is a separate constraint group and not subsumed.

---

## Changing N (instance size)

The circuit encodes N as a compile-time global in `src/main.nr`:

```noir
global N: u32 = 5;   // <-- change this line
```

**Steps to benchmark a new N:**

```bash
# 1. Update the global in the circuit source
sed -i 's/^global N: u32 = .*/global N: u32 = 10;/' \
    circuits/flat_full_pairwise/src/main.nr

# 2. Regenerate instance and path
python pipeline/instance_gen.py -n 10 --out data/instance.json --dat data/matrix.dat
python pipeline/solver.py --json data/instance.json --out data/path.json

# 3. Regenerate Prover.toml
python pipeline/format_inputs.py \
  --instance data/instance.json \
  --path     data/path.json \
  --out      circuits/flat_full_pairwise/Prover.toml

# 4. Recompile and re-run the circuit
cd circuits/flat_full_pairwise
nargo compile
nargo execute
bb write_vk -b target/flat_full_pairwise.json -o target/vk
bb prove -b target/flat_full_pairwise.json -w target/flat_full_pairwise.gz \
         -k target/vk/vk -o target/proof
bb verify -k target/vk/vk -p target/proof/proof -i target/proof/public_inputs
bb gates -b target/flat_full_pairwise.json
cd ../..
```

> **Important:** the N in `src/main.nr` and the n in `instance.json` must match,
> otherwise `nargo execute` will fail with an array size mismatch.

---

## Benchmarking

### Run benchmarks across multiple N values

```bash
python pipeline/run.py \
  --circuit circuits/flat_full_pairwise \
  --ns 5 8 10 15 20 \
  --runs 3 \
  --out results/flat_full_pairwise.csv
```

Options:
- `--circuit`  Path to circuit directory (required)
- `--ns`       Space-separated list of N values to test (required)
- `--runs`     Independent runs per N value; each uses a different random instance (default: 3)
- `--out`      Output CSV path (required); rows are appended so a partial run is safe to resume
- `--seed`     Base random seed (default: 42); each run uses `seed + n*1000 + run_idx`

The script:
1. Patches `global N: u32 = X;` in the circuit source and recompiles.
2. Pre-computes the verification key with `bb write_vk` (once per N).
3. Queries gate count with `bb gates` (once per N).
4. For each run: generates a fresh instance, solves it, formats Prover.toml,
   times `nargo execute`, `bb prove`, and `bb verify`, records proof size
   and peak memory from bb stderr.

CSV columns: `variant, n, run, circuit_size, acir_opcodes, compile_s, witness_s, prove_s, verify_s, proof_bytes, peak_mb`

### Plot the results

```bash
python pipeline/plot.py \
  --csv results/flat_full_pairwise.csv \
  --out plots/flat_full_pairwise
```

---

### Complexity analysis — theory vs empirical

Fits exact quadratic models to `circuit_size` and `acir_opcodes` across all
benchmarked variants, explains each coefficient in terms of the underlying
constraint structure, and generates a four-panel comparison figure.

```bash
python pipeline/analyze_complexity.py \
  --csv results/flat_full.csv \
  --out plots/flat_full_complexity
```

Prints three tables to stdout:
1. **Theoretical breakdown** — permutation class, ops per constraint group, extra witness.
2. **Fitted quadratic coefficients** — `a·N² + b·N + c` for both `acir_opcodes` and
   `circuit_size`, with R² and per-coefficient interpretation.
3. **Permutation check overhead** — `(variant − invperm)` circuit_size at each N,
   isolating the marginal cost of each permutation strategy.

Saves one PNG with four panels:
- (a/b) Linear-axis curves for acir_opcodes and circuit_size with fitted overlays.
- (c) Log-log acir_opcodes with empirical slope annotations.
- (d) Permutation-check overhead vs N (pairwise visible as O(N²) vs linear for O(N) variants).

Options: `--csv`, `--out`, `--dpi` (default 150).

Produces two PNG files:
- `plots/flat_full_pairwise_linear.png`  — linear axes, error bars show std across runs
- `plots/flat_full_pairwise_loglog.png`  — log-log axes with empirical slope annotation
  (slope ≈ exponent of the polynomial relationship, e.g. 2.0 for O(N^2))

Options:
- `--title`  Custom figure suptitle (default: CSV filename stem)
- `--dpi`    Output resolution (default: 150)

---

## Tests

The `tests/` folder has two sub-directories:

### `tests/correctness/` — soundness tests

These verify that the circuit rejects every invalid witness.
`nargo execute` exits non-zero when an `assert` fires — that's how we catch
a cheating prover.

```bash
# Run all soundness tests for flat_full_pairwise
python tests/correctness/test_flat_full_pairwise.py

# Run all soundness tests for flat_full_sort
python tests/correctness/test_flat_full_sort.py

# Run all soundness tests for flat_full_invperm
python tests/correctness/test_flat_full_invperm.py

# Run all soundness tests for flat_full_presence
python tests/correctness/test_flat_full_presence.py

# Run all soundness tests for flat_merkle_presence
# (builds the Rust merkle_builder automatically on first run)
python tests/correctness/test_flat_merkle_presence.py

# Run all soundness tests for Variant A (hierarchical, sub + glue)
# (patches circuit globals + recompiles per test; merkle_builder built on first run)
python tests/correctness/test_hierarchical_a.py
```

All test suites for `flat_full_*` cover the same invalid-witness categories:
- Valid baselines (must always pass)
- Out-of-range node index (GROUP 1 in pairwise; caught by GROUP 2 in sort)
- Duplicate nodes in the cycle (GROUP 2 violation in both)
- Threshold set below actual cost (GROUP 4 violation)
- Tampered cost matrix that inflates cost above threshold (GROUP 3+4 violation)
- Edge case N=1 (single-node trivial cycle)

`test_flat_merkle_presence.py` covers the same GROUP 1/2/4 categories plus:
- GROUP 3a: tampered `edge_costs` — the hash no longer matches the committed root
- GROUP 3b: flipped path bit — the reconstructed leaf index no longer matches
- GROUP 3c: wrong root — valid proofs from a correct matrix against a forged root

For GROUP 1/2 tests the Merkle fields are filled with structural zeros (the
circuit rejects before GROUP 3 so the dummy proofs are never checked).

**Prerequisite:** the Rust `merkle_builder` binary must be compiled.
The test builds it automatically, or you can build it manually:

```bash
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

### `tests/api_exploration/` — throwaway experiments

Shell and Python scripts for understanding tools before committing to a design.
Nothing here is part of the main pipeline.

```bash
# Inspect the JSON structure bb gates returns
bash tests/api_exploration/explore_bb_gates.sh

# See what error messages nargo execute produces for broken witnesses
bash tests/api_exploration/explore_nargo_errors.sh
```

Add new scripts here whenever you want to try out a Noir feature, a new bb
flag, or a library API without touching the main code.

---

## Circuit workflow — `circuits/flat_merkle_presence`

This variant replaces the N^2 public cost matrix with a single Poseidon2 Merkle
root.  The prover supplies per-edge Merkle opening proofs as private witnesses.

Two compile-time globals must be in sync: `N` (number of nodes) and
`DEPTH = ceil(log2(N^2))` (Merkle tree depth).  The harness patches both.

### Build the Rust Merkle builder (once)

The `pipeline/merkle_builder/` Rust crate computes the Merkle tree off-circuit
and writes Prover.toml.  Build it once before running benchmarks or tests:

```bash
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

### Format inputs (from project root)

```bash
# 1. Generate instance and solve as usual
python pipeline/instance_gen.py -n 5 --out data/instance.json --dat data/matrix.dat
python pipeline/solver.py --json data/instance.json --out data/path.json

# 2. Call the Rust builder directly (or via run.py; see Benchmarking section)
python - <<'EOF'
import json, math, sys
sys.path.insert(0, "pipeline")
from format_inputs import merkle_depth, write_merkle_prover_toml
from instance_gen import generate_instance
from solver import solve, cycle_cost

n = 5
inst = generate_instance(n, seed=42)
path = solve(inst["matrix"])
flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
cost = cycle_cost(inst["matrix"], path)
write_merkle_prover_toml(
    {"n": n, "cost": cost, "threshold": math.ceil(cost * 1.1),
     "cycle": path, "flat_matrix": flat},
    "circuits/flat_merkle_presence/Prover.toml",
    "pipeline/merkle_builder/target/release/merkle_builder",
)
EOF
```

### Compile, execute, prove, verify

```bash
cd circuits/flat_merkle_presence

# Patch N and DEPTH for the chosen instance size (e.g. N=5, DEPTH=5)
sed -i 's/^global N: u32 = .*/global N: u32 = 5;/'     src/main.nr
sed -i 's/^global DEPTH: u32 = .*/global DEPTH: u32 = 5;/' src/main.nr

nargo compile
nargo execute

bb write_vk \
  -b target/flat_merkle_presence.json \
  -o target/vk

bb prove \
  -b target/flat_merkle_presence.json \
  -w target/flat_merkle_presence.gz \
  -k target/vk/vk \
  -o target/proof

bb verify \
  -k target/vk/vk \
  -p target/proof/proof \
  -i target/proof/public_inputs

bb gates -b target/flat_merkle_presence.json

cd ../..
```

### Key differences from flat_full_presence

- **Public inputs**: `root: Field` + `threshold: u64` (was N^2 + 1 fields).
- **Private witness gains**: `edge_costs: [u64; N]`, `siblings: [Field; N*DEPTH]`,
  `path_bits: [bool; N*DEPTH]`.
- **GROUP 3** verifies a Merkle opening proof per edge instead of doing a direct
  ROM lookup into a public cost matrix.
- **Two globals**: both `N` and `DEPTH = ceil(log2(N^2))` must be patched before
  recompiling.  The benchmark harness (`run.py`) patches both automatically.

### Benchmarking with run.py

`run.py` detects `"merkle"` in the circuit directory name, patches DEPTH alongside N,
and calls the Rust builder to generate Prover.toml:

```bash
python pipeline/run.py \
  --circuit circuits/flat_merkle_presence \
  --ns 5 8 10 15 20 25 30 40 50 \
  --runs 3 \
  --out results/flat_merkle_presence.csv
```

---

## Variant A workflow — `circuits/hierarchical_segment` + `circuits/hierarchical_glue`

Variant A is the first hierarchical design (Merkle commitment, partition
public).  Instead of one circuit covering the whole N-node cycle, it splits
into:

- **K sub-proofs** of `circuits/hierarchical_segment` — one per segment.
  Each proves a Hamiltonian path of M = N/K nodes inside its segment, with
  internal edge costs Merkle-bound to the same root.
- **1 glue proof** of `circuits/hierarchical_glue` — proves the K segments
  partition `{0..N-1}`, verifies the K boundary edges' Merkle proofs, and
  enforces the total-cost threshold.

The K+1 proofs are independent UltraHonk proofs.  The verifier runs
`bb verify` K+1 times and then `pipeline/verify_hier.py`, which parses each
proof's `public_inputs` dump and runs four cross-checks that bind the proofs
to a single instance.  See `HIERARCHICAL_EXPLAINED.md` §8 for the theory and
`VARIANT_A_IMPLEMENTATION.md` for the implementation plan that was followed.

### Prerequisites

```bash
# Build the Rust merkle_builder (shared with flat_merkle_presence).
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

Both sub and glue circuits depend on the same Poseidon2 library
(`poseidon v0.3.0`) used by `flat_merkle_presence` and cross-validated by
`tests/hash_compat/`.

### Compile-time globals

| Circuit | Globals | Patched per |
|---|---|---|
| `hierarchical_segment` | `N`, `M`, `DEPTH` | `(N, K)` cell (M = N/K, DEPTH = ⌈log₂(N²)⌉) |
| `hierarchical_glue` | `N`, `K`, `DEPTH` | `(N, K)` cell |

`run_hier.py` patches all of these and recompiles automatically.  For a
manual run, use `sed` (shown below).

### Single end-to-end run on the §8.9 reference instance (N=8, K=2)

This walkthrough proves the documented cycle `0 → 5 → 3 → 2 → 7 → 4 → 1 → 6
→ 0` (total cost 92, threshold 100).  See `HIERARCHICAL_EXPLAINED.md` §8.9 for
the expected per-segment public values.

```bash
# 1. Patch circuit globals (defaults to N=8, K=2 in the repo but be explicit).
sed -i 's/^global N: u32 = .*/global N: u32 = 8;/' \
    circuits/hierarchical_segment/src/main.nr
sed -i 's/^global M: u32 = .*/global M: u32 = 4;/' \
    circuits/hierarchical_segment/src/main.nr
sed -i 's/^global DEPTH: u32 = .*/global DEPTH: u32 = 6;/' \
    circuits/hierarchical_segment/src/main.nr

sed -i 's/^global N: u32 = .*/global N: u32 = 8;/'  \
    circuits/hierarchical_glue/src/main.nr
sed -i 's/^global K: u32 = .*/global K: u32 = 2;/'  \
    circuits/hierarchical_glue/src/main.nr
sed -i 's/^global DEPTH: u32 = .*/global DEPTH: u32 = 6;/' \
    circuits/hierarchical_glue/src/main.nr

# 2. Compile both circuits and write verification keys (once per (N, K)).
( cd circuits/hierarchical_segment && nargo compile \
    && bb write_vk -b target/hierarchical_segment.json -o target/vk )
( cd circuits/hierarchical_glue && nargo compile \
    && bb write_vk -b target/hierarchical_glue.json -o target/vk )

# 3. Build the reference instance's K+1 Prover.tomls into /tmp/hier_ref.
python - <<'EOF'
import json, subprocess
N = 8
flat = [0] * (N * N)
for f, t, c in [(0,5,10),(5,3,12),(3,2,8),(2,7,15),
                (7,4,11),(4,1,9),(1,6,14),(6,0,13)]:
    flat[f * N + t] = c
payload = json.dumps({
    "n": N, "flat_matrix": flat,
    "cycle": [0, 5, 3, 2, 7, 4, 1, 6],
    "threshold": 100, "cost": 92,
})
subprocess.run(
    ["pipeline/merkle_builder/target/release/merkle_builder",
     "--hierarchical", "2", "--out-dir", "/tmp/hier_ref"],
    input=payload, text=True, check=True,
)
EOF

# 4. Prove sub_0  (segment [0, 5, 3, 2]).
cp /tmp/hier_ref/sub_0/Prover.toml circuits/hierarchical_segment/Prover.toml
( cd circuits/hierarchical_segment \
  && nargo execute \
  && bb prove -b target/hierarchical_segment.json \
              -w target/hierarchical_segment.gz \
              -k target/vk/vk -o target/proof_sub0 )

# 5. Prove sub_1  (segment [7, 4, 1, 6]).
cp /tmp/hier_ref/sub_1/Prover.toml circuits/hierarchical_segment/Prover.toml
( cd circuits/hierarchical_segment \
  && nargo execute \
  && bb prove -b target/hierarchical_segment.json \
              -w target/hierarchical_segment.gz \
              -k target/vk/vk -o target/proof_sub1 )

# 6. Prove glue.
cp /tmp/hier_ref/glue/Prover.toml circuits/hierarchical_glue/Prover.toml
( cd circuits/hierarchical_glue \
  && nargo execute \
  && bb prove -b target/hierarchical_glue.json \
              -w target/hierarchical_glue.gz \
              -k target/vk/vk -o target/proof_glue )

# 7. Stage the K+1 proofs into a single directory layout that verify_hier.py
#    expects:  <dir>/{sub_0, sub_1, glue}/{proof, public_inputs}.
mkdir -p /tmp/hier_ref_proofs/sub_0 /tmp/hier_ref_proofs/sub_1 /tmp/hier_ref_proofs/glue
cp circuits/hierarchical_segment/target/proof_sub0/{proof,public_inputs} /tmp/hier_ref_proofs/sub_0/
cp circuits/hierarchical_segment/target/proof_sub1/{proof,public_inputs} /tmp/hier_ref_proofs/sub_1/
cp circuits/hierarchical_glue/target/proof_glue/{proof,public_inputs}    /tmp/hier_ref_proofs/glue/

# 8. Run K+1 bb verify + 4 cross-checks in one go.
python pipeline/verify_hier.py \
  --proof-dir /tmp/hier_ref_proofs \
  --n 8 --k 2 \
  --sub-vk  circuits/hierarchical_segment/target/vk/vk \
  --glue-vk circuits/hierarchical_glue/target/vk/vk
```

Expected output ends with `ACCEPTED`: all three `bb verify` calls succeed,
and the cross-checks (same root, `all_sorted_nodes` chunks match each sub's
`sorted_nodes`, `starts/ends/partial_costs` match) all pass.

The same end-to-end flow (plus 4 negative tests and an N=48 K=4 sanity
check) runs automatically via:

```bash
python tests/correctness/test_hierarchical_a.py
```

### Building Prover.tomls for an arbitrary instance

```bash
# Generate instance + solve cycle as usual.
python pipeline/instance_gen.py -n 48 --out data/instance.json --dat data/matrix.dat
python pipeline/solver.py --json data/instance.json --out data/path.json

# Then feed the resulting matrix and cycle to merkle_builder --hierarchical.
python - <<'EOF'
import json, math, subprocess
inst = json.load(open("data/instance.json"))
path = json.load(open("data/path.json"))
n = len(path)
flat = [inst["matrix"][i][j] for i in range(n) for j in range(n)]
cost = sum(inst["matrix"][path[i]][path[(i+1) % n]] for i in range(n))
payload = json.dumps({
    "n": n, "flat_matrix": flat, "cycle": path,
    "threshold": math.ceil(cost * 1.1), "cost": cost,
})
subprocess.run(
    ["pipeline/merkle_builder/target/release/merkle_builder",
     "--hierarchical", "4", "--out-dir", "/tmp/hier_n48_k4"],
    input=payload, text=True, check=True,
)
EOF

# /tmp/hier_n48_k4/{sub_0..sub_3, glue}/Prover.toml are now ready.
# Patch circuit globals for (N=48, K=4, M=12, DEPTH=12), compile, and proceed
# as in the reference walkthrough — or just use run_hier.py below.
```

### Soundness tests

```bash
python tests/correctness/test_hierarchical_a.py
```

Covers six cases:

1. **VALID** — reference instance N=8 K=2: K+1 proofs all generate and
   verify_hier.py accepts.
2. **INVALID — segment overlap** (hierarchical-unique): cheating cycle puts
   node 3 in both segments.  Glue G2 partition check rejects during
   `nargo execute`.
3. **INVALID — cross-check mismatch** (hierarchical-unique): mix sub-proofs
   from one valid cycle with the glue proof from a different valid cycle
   through the same matrix.  Each `bb verify` accepts; the
   `glue.starts[1] != sub_1.start_node` cross-check fires in verify_hier.py.
4. **INVALID — cost binding** (inherited from flat_merkle): sub G5 catches
   `sum(edge_costs) != partial_cost`.
5. **INVALID — boundary Merkle** (inherited from flat_merkle): glue G3
   catches a tampered boundary cost (hash chain ≠ root).
6. **VALID — N=48 K=4** sanity check: confirms the (N, K)-patching machinery
   works for non-toy sizes (witness only, no full proving).

### Benchmark sweep — `pipeline/run_hier.py`

```bash
python pipeline/run_hier.py \
  --ns 48 96 192 480 \
  --ks 2 4 8 \
  --runs 3 \
  --out results/hier_a.csv
```

Options mirror `run.py`:

- `--ns`   Space-separated list of N values (required).  Each must be
  divisible by every K under test; cells with `N % K != 0` are skipped.
- `--ks`   Space-separated list of K values (required).
- `--runs` Independent runs per (N, K) cell (default: 3).
- `--out`  Output CSV path (required); appended to.
- `--seed` Base seed (default: 42); per-run seed = `seed + N*1000 + K*100 + run_idx`.

What it does per `(N, K)` cell:

1. Patches `N, M, K, DEPTH` in both circuits' `src/main.nr` and recompiles.
   Writes a fresh VK for each.  Records `circuit_size`, `acir_opcodes`,
   `compile_s` per circuit.
2. Materialises K shadow directories under `/tmp/hier_a_shadows/sub_i/`,
   each a self-contained nargo project (copied `Nargo.toml + src/`, plus
   a freshly-compiled `target/`).  Shadows live outside the project tree
   because nargo walks up looking for the outermost `Nargo.toml` and would
   otherwise treat `circuits/hierarchical_segment/.runs/sub_i/` as a child
   of the parent project and write into the parent's `target/`.
3. Per run: generates a TSP instance, solves it, calls
   `merkle_builder --hierarchical K` to produce K+1 Prover.tomls, then
   spawns K+1 parallel `nargo execute && bb prove` workers (one per
   sub-circuit shadow plus one in the glue dir).  Records each worker's
   own wall-clock `witness_s` and `prove_s` (under K+1-way CPU contention).
4. After all proves complete, runs `bb verify` serially per circuit
   (clean per-circuit verify time) and then `verify_hier.py` to validate
   the cross-checks.  Emits K+1 CSV rows with `circuit` column set to
   `sub_0..sub_{K-1}` / `glue`.

CSV columns:

```
variant n k m run circuit circuit_size acir_opcodes compile_s
witness_s prove_s verify_s proof_bytes peak_mb verify_hier_s xchecks_ok
```

Downstream aggregation is handled by `pipeline/aggregate_hier.py` — see
the next section.

### Aggregating raw `hier_a.csv` for plotting

`run_hier.py` writes K+1 rows per cell — one per circuit (`sub_0..sub_{K-1}`
/ `glue`).  `pipeline/aggregate_hier.py` collapses those into one row per
`(N, K, run)` cell with the same schema as `run.py`'s flat output, so the
existing `pipeline/plot.py` can ingest it directly.

```bash
# Parallel wall-clock projection (max prove_s across the K+1 circuits per cell):
python pipeline/aggregate_hier.py \
    --in   results/hier_a.csv \
    --out  results/hier_a_parallel.csv \
    --mode parallel

# Or total CPU work (sum prove_s across the K+1 circuits):
python pipeline/aggregate_hier.py \
    --in   results/hier_a.csv \
    --out  results/hier_a_total.csv \
    --mode total
```

**Aggregation rules used:**

| Output column | Per cell aggregation |
|---|---|
| `circuit_size` | `K * sub.circuit_size + glue.circuit_size` (total gates across all K+1 circuits) |
| `acir_opcodes` | same |
| `compile_s` | `sub.compile_s + glue.compile_s` (one sub compile + one glue compile per cell) |
| `witness_s` | `max` (parallel) or `sum` (total) across the K+1 rows |
| `prove_s` | `max` (parallel) or `sum` (total) across the K+1 rows |
| `verify_s` | `sum(verify_s)` + `verify_hier_s` (serial K+1 `bb verify` + cross-checks) |
| `proof_bytes` | `sum` (the K+1 proofs delivered to the verifier) |
| `peak_mb` | `max` (max single-prover memory) |

Variant column defaults to `hier_a_k{K}` (one variant per K).  Pass
`--mode-in-name` to disambiguate as `hier_a_k{K}_{mode}` if you want both
parallel and total plotted in the same figure.

### Plotting flat + hierarchical results in one figure

`pipeline/plot.py` now accepts multiple `--csv` inputs.  Pass the flat
baseline CSV first, then any number of aggregated hier CSVs:

```bash
# Aggregate first
python pipeline/aggregate_hier.py \
    --in   results/hier_a.csv \
    --out  results/hier_a_parallel.csv \
    --mode parallel

# Then plot together with the existing flat baseline
python pipeline/plot.py \
    --csv results/500.csv results/hier_a_parallel.csv \
    --out plots/flat_vs_hier_a
```

Produces `plots/flat_vs_hier_a_linear.png` and `plots/flat_vs_hier_a_loglog.png`,
each with one line per variant (flat_full_pairwise, flat_full_sort, ...,
hier_a_k2, hier_a_k4, hier_a_k8) and per-variant slope annotations on the
log-log panels.

Comparing apples to apples:

- The **proof_bytes** panel will show hier well above flat — that's expected,
  since the verifier receives K+1 separate proofs (~14.6 KB × (K+1)).
- The **prove_s** panel under `--mode parallel` is the wall-clock of the
  K+1-way parallel run on a single machine — which is CPU-contended.  Each
  prover gets ~1/(K+1) of available threads, so observed prove_s is worse
  than flat for all K.  The theoretical K× speedup (estimated from
  circuit_size ratios) requires isolated hardware per prover and is not
  directly measured by this benchmark.  Run an isolation experiment (one
  sub-circuit, no siblings) to confirm.
- The **peak_mb** panel uses max across K+1 provers, so it measures the
  largest single prover's footprint.  Note: the glue circuit sorts
  `all_sorted_nodes[N]` (N elements regardless of K), creating an O(N)
  memory floor.  At K≥8, N=480 the glue (~159 MB) exceeds the sub-circuit
  (~152 MB) and becomes the reported peak.  Total single-machine RAM (not
  shown) = K×sub_peak + glue_peak and exceeds flat for all K.

### Common issues (hierarchical-specific)

**Shadow workers fail with "Failed to open file: target/hierarchical_segment.gz"**
A previous shadow was placed inside the project tree (`circuits/.../...`)
instead of `/tmp/`.  Nargo's project-root resolution walks up to the outer
`Nargo.toml`, so executions inside the project tree write to the main
`target/`.  Confirm `SHADOW_ROOT` in `pipeline/run_hier.py` points to
`/tmp/hier_a_shadows` (it does by default).

**`merkle_builder` exits with "N must be divisible by K"**
N and K must satisfy `N % K == 0` so each segment has the same M = N/K.
The recommended N values 48, 96, 192, 480 are divisible by all of {2, 4, 8}.

**`verify_hier.py` reports "root mismatch"**
The K+1 proofs come from different matrices (i.e., different merkle_builder
invocations).  Make sure all K+1 Prover.tomls came from the *same*
`merkle_builder --hierarchical` call.

**`verify_hier.py` reports a starts/ends/partial_costs mismatch**
The sub-circuit and glue Prover.tomls don't refer to the same instance —
most likely the glue was rebuilt with a different cycle while one of the
sub-circuit proofs was kept from an older run.

---

## Variants

| Directory | Matrix input | Permutation check | Status |
|---|---|---|---|
| `flat_full_pairwise` | Full N^2 public inputs | Pairwise O(N^2) | done |
| `flat_full_sort` | Full N^2 public inputs | Sort-based ~3N constrained | done |
| `flat_full_invperm` | Full N^2 public inputs | Inv-perm witness 2N constrained | done |
| `flat_full_presence` | Full N^2 public inputs | Presence mark array ~4N constrained | done |
| `flat_merkle_presence` | Poseidon2 Merkle root | Presence mark array ~4N + N*DEPTH hashes | done |
| `hierarchical_segment` + `hierarchical_glue` | Poseidon2 Merkle root | Per-segment `sort_via` + global partition check | done (Variant A) |
| Variant A++ (Merkle, grand product + FS) | Poseidon2 Merkle root | Grand product with in-circuit Fiat-Shamir | future |
| Variant B (flat-full, sub-matrix public) | K disclosed M×M sub-matrices | Per-segment ROM lookup | future |

---

## Common issues

**`nargo execute` fails with "node index out of range"**
The cycle contains an index >= N. The solver output doesn't match the instance size.
Check that `instance_gen.py` and `solver.py` used the same JSON file.

**`nargo execute` fails with "duplicate node in cycle"**
The solver returned a path with a repeated node. Re-run `solver.py` —
the 2-opt phase should produce a valid cycle for any instance.

**`nargo execute` fails with "cycle cost exceeds threshold"**
The threshold in Prover.toml is below the actual cycle cost.
This should not happen with the default multiplier of 1.1.
If you manually edited Prover.toml, re-run `format_inputs.py`.

**`nargo execute` fails with an array size error**
The N in `src/main.nr` does not match the n in `instance.json`.
Update the global and recompile.
