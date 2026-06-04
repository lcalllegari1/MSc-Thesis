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

### `pipeline/instance_cache.py` — one canonical instance + Merkle tree per N

The benchmark harnesses do **not** call `instance_gen` / `solver` directly any
more — they go through `get_instance_and_cycle(n, seed)`, which caches the three
artifacts every variant needs (instance, solved cycle, Poseidon2 Merkle tree)
under `data/instances/n{N}_seed{S}/`:

```
data/instances/n{N}_seed{S}/
  instance.json   # generate_instance(N, seed): metadata + nodes + matrix
  cycle.json      # solver output: {cycle, cost}
  meta.json       # cache-validity tag (version, N, seed, grid, precision, solver)
  tree.bin        # serialised Merkle tree, written/validated by merkle_builder
```

Why this exists: the Merkle tree over the N² cost matrix is O(N²) Poseidon2
hashes and dominates `merkle_builder` at large N. The instance, cycle and tree
are pure functions of `(N, seed)`, so **one instance per N is built once and
reused by every variant (flat / A / A++ / committed / recursion), every K, and
every run.** The Rust builder gets the tree path via `--tree-cache <path>` and
loads it on a hit instead of rebuilding (look for `tree cache HIT` on stderr).

This is sound because SNARK proving is **data-oblivious**: for a fixed circuit
the gate count, proof size and peak memory are independent of the witness
values, and prove/verify times vary only with system noise. So repeated runs on
the same instance measure exactly that noise; instance *content* is irrelevant
to the metrics (instance *diversity* lives in `tests/correctness/`, not the
benchmark).

**Clearing / regenerating the cache:**
```bash
rm -rf data/instances/n2000_seed42   # drop one size
rm -rf data/instances                # drop all (regenerated on next run)
```
A stale cache is rejected automatically: the Python side bumps `CACHE_VERSION` /
`SOLVER_TAG` in `instance_cache.py` when instance/solver semantics change, and
the Rust side checksums `flat_matrix` against `tree.bin`'s header (a mismatch
rebuilds rather than serving a wrong tree). `data/instances/` is git-ignored —
the trees are large (~270 MB at N=2000) and kept local only.

> A `merkle_builder` call *without* `--tree-cache` (e.g. the standalone
> `format_inputs.py` quick-start, or `tests/correctness/`) behaves exactly as
> before — the cache is purely additive.

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
- `--runs`     Repeated runs per N value; all reuse the one canonical instance for that N (timing-noise samples, see below) (default: 3)
- `--out`      Output CSV path (required); rows are appended so a partial run is safe to resume
- `--seed`     Base seed (default: 42); the per-N instance is keyed by `(N, seed)` and cached under `data/instances/` (see `instance_cache.py`)

The script:
1. Patches `global N: u32 = X;` in the circuit source and recompiles.
2. Pre-computes the verification key with `bb write_vk` (once per N).
3. Queries gate count with `bb gates` (once per N).
4. Loads (or builds + caches) the canonical instance/cycle/tree for N and writes
   Prover.toml **once per N** — the witness is identical across runs.
5. For each run: times `nargo execute`, `bb prove`, and `bb verify`, records
   proof size and peak memory from bb stderr.

> **Why runs share one instance.** SNARK proving is data-oblivious, so for a
> fixed circuit the gate count / proof size / peak memory are constant and only
> the timings move — with system noise, not the graph. Reusing one instance per
> N therefore makes the error bars measure exactly what varies, and lets all
> variants be compared on the same instance. Instance diversity is exercised in
> `tests/correctness/`, not here.

CSV columns: `variant, n, run, circuit_size, acir_opcodes, compile_s, witness_s, prove_s, verify_s, proof_bytes, peak_mb`

### Plot the results

```bash
# Simplest: one CSV, default 8-metric grid, linear + log-log PNGs.
python pipeline/plot.py \
  --csv results/flat_full_pairwise.csv \
  --out plots/flat_full_pairwise
```

`plot.py` groups rows by `(variant, N)`, plots mean ± std across runs, one line
per variant, and always writes a `_linear` and a `_loglog` file.

Options:
- `--csv`       One or more CSVs (concatenated; the `variant` column = one line). Required.
- `--out`       Output path prefix, no extension. Required.
- `--metrics`   Which metrics to draw (default: all eight — `circuit_size acir_opcodes
                prove_s witness_s verify_s proof_bytes peak_mb compile_s`). Pass a subset
                to focus a figure.
- `--variants`  Variant names or `fnmatch` globs to include (default: all in the CSV),
                e.g. `--variants 'hier_c_k*' 'hier_cfs_k*' flat_merkle_presence`.
- `--min-n` / `--max-n`  Window the size range read from a big CSV (filters on N), so one
                large CSV serves many figures without splitting it.
- `--separate`  Write one file per metric (`<out>_<metric>_<scale>.<fmt>`) instead of the
                single grid (grid is the default).
- `--format`    `png` (default), `pdf`, or `svg`. **Use `pdf` for thesis figures** (vector,
                scales crisply in LaTeX).
- `--legend`    `outside` (default; one shared legend below), `inside` (on a panel), or
                `none`. Switch with e.g. `--legend inside`.
- `--no-title`  Omit the figure suptitle (let the LaTeX caption be the title).
- `--title`     Custom suptitle (default: first CSV's filename stem).
- `--dpi`       Raster DPI for PNG (default 150; ignored for vector formats).

Examples:
```bash
# Thesis figure: committed variants + flat baseline, N<=192, vector, per-metric files.
python pipeline/plot.py \
  --csv results/all.csv --out plots/committed_small \
  --variants 'hier_c_k*' 'hier_cfs_k*' flat_merkle_presence \
  --max-n 192 --separate --format pdf --no-title \
  --metrics circuit_size prove_s peak_mb proof_bytes

# Quick look at just the new ACIR/witness metrics, legend on the panel.
python pipeline/plot.py --csv results/all.csv --out plots/acir \
  --metrics acir_opcodes witness_s --legend inside
```

Per-variant colours/markers are **stable across figures** (keyed by the variant
name), so a variant looks the same in every plot regardless of which others are
shown. To curate the final thesis colours/labels, edit two dicts near the top of
`pipeline/plot.py`: `STYLE_OVERRIDES` (pin a variant to a colour slot) and
`DISPLAY_NAMES` (relabel a variant in legends). Both are empty (identity) by default.

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

---

## Hierarchical benchmarking and the frontier

The hierarchical variants emit **K+1 rows per (N, K) cell** (one per circuit:
`sub_0..sub_{K-1}`, `glue`). Each variant has its own harness; all four share the
CSV schema and downstream tooling.

```bash
# Variant A (sorted-nodes public)     -> results/hier_a.csv   (variant col "hier_a")
python pipeline/run_hier.py     --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_a.csv
# Variant A++ (grand product + FS)    -> results/hier_fs.csv  (variant col "hier_fs")
python pipeline/run_hier_fs.py  --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_fs.csv
# Variant committed-A (blinded C_i, sort partition)        -> results/hier_c.csv
python pipeline/run_hier_c.py   --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_c.csv
# Variant committed-A++ (blinded C_i, grand-product)       -> results/hier_cfs.csv
python pipeline/run_hier_cfs.py --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_cfs.csv
```

Shared options: `--ns`, `--ks`, `--runs`, `--out`, `--seed`. Each harness patches
the circuit globals, compiles sub + glue, builds the K+1 `Prover.toml`s via
`merkle_builder` (mode `--hierarchical{,-fs,-c,-cfs}`), proves the K+1 circuits in
parallel, then runs the matching `verify_hier{,_fs,_c,_cfs}.py` cross-check.
Prerequisite: the Rust builder must be compiled
(`cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml`).

### Aggregate K+1 rows into one point per cell

`aggregate_hier.py` is variant-agnostic (reads the `variant` column) and turns the
raw CSV into a `plot.py`-compatible one (`{variant}_k{K}` rows):

```bash
python pipeline/aggregate_hier.py --in results/hier_cfs.csv \
  --out results/hier_cfs_parallel.csv --mode parallel
```
- `--mode parallel` (default): `prove_s`/`witness_s` use **max** over the K+1 provers
  — the ideal one-node-per-segment wall-clock. `--mode total` uses **sum** (total CPU work).
- `--mode-in-name` appends `_parallel`/`_total` to the variant name so both modes can
  coexist in one figure.
- Other metrics: `circuit_size`/`acir_opcodes` = K·sub + glue; `verify_s` = Σ bb-verify +
  cross-check; `proof_bytes` = Σ (the K+1 proofs); `peak_mb` = max (per-prover peak).
- `--split-components` *additionally* emits two rows per cell beside the combined one:
  `{variant}_k{K}_seg` (the K segments only — `max`/`sum` per `--mode`, no glue) and
  `{variant}_k{K}_glue` (the glue proof alone; the external cross-check time rides with
  glue, as the verifier-side binding tax). They sum back to the combined row, so it is a
  faithful decomposition. `plot.py` needs no change — each is its own `variant`/line; draw
  them with e.g. `--variants 'hier_fs_k4_seg' 'hier_fs_k4_glue'`. Use it for the write-up's
  "segments vs binding glue" reasoning (see `HIER_MEASUREMENT_AND_PLOTS.md` §E).

### One-shot: aggregate + plot the frontier

`make_frontier.py` chains the aggregator and `plot.py` in one command and echoes
every sub-command it runs (so the chain is reproducible by hand). Pass raw
hierarchical CSVs with `--aggregate` and already-plot-ready CSVs (the flat baseline
`results/500.csv`, recursion CSVs) with `--include`; all `plot.py` flags above are
forwarded.

```bash
# Equal-privacy frontier: flat + committed-A/A++ + recursion, parallel wall-clock.
python pipeline/make_frontier.py \
  --aggregate results/hier_c.csv results/hier_cfs.csv \
  --include   results/500.csv results/recursion_full_tot.csv \
  --out plots/frontier --mode parallel

# Thesis panel: window to N<=192, committed + flat only, vector, one file per metric.
python pipeline/make_frontier.py \
  --aggregate results/hier_c.csv results/hier_cfs.csv --include results/500.csv \
  --out plots/frontier_small --mode parallel --max-n 192 \
  --variants 'hier_c_k*' 'hier_cfs_k*' flat_merkle_presence \
  --separate --format pdf --no-title --legend inside \
  --metrics circuit_size prove_s peak_mb proof_bytes
```
`--mode both` produces `_parallel` and `_total` lines in the same figure.

### Isolation benchmark (the K× parallelism claim)

The harnesses above launch the K+1 provers **concurrently on one machine**, so their
per-prover times are measured under contention — the headline K× speedup is therefore
a *projection*, not a measurement. To **measure** it, run any hierarchical harness with
**`--isolated`** on an **idle machine**: it proves the K+1 circuits **sequentially**
(each alone, so its time is its solo per-node time) and tags the variant `<base>_iso`.

```bash
PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
$PY pipeline/run_hier_cfs.py --ns 192 480 --ks 2 4 8 --runs 5 --isolated --out results/hier_cfs_iso.csv
# turn solo times into the distributed wall-clock with the SAME aggregator:
#   model (a) K+1 nodes (glue concurrent) = max over provers:
$PY pipeline/aggregate_hier.py --in results/hier_cfs_iso.csv --out results/hier_cfs_iso_par.csv --mode parallel
#   model (b) K nodes (glue after)        = sum:
$PY pipeline/aggregate_hier.py --in results/hier_cfs_iso.csv --out results/hier_cfs_iso_tot.csv --mode total
```

`--mode parallel` (max over the K+1 solo times) is the distributed wall-clock; plot
the `*_iso_par` series against flat (`results/500.csv`) for the **measured** speedup.
Full reasoning, the deployment models, measurement protocol, a manual copy-paste
recipe (for `taskset` core-pinning), and the reporting format are in
**`ISOLATION_BENCHMARK.md`** (this closes the open gap O12; run before final submission).

---

## Full comparison sweep recipe (flat + hierarchical + recursion)

The canonical end-to-end recipe to produce **comparable** results across every
variant and dimension. Ordered as a funnel — *deterministic → noisy*,
*like-with-like → across-class*, *honest baseline → idealized claim* — so each
phase is a precondition for the next. (Conceptual companion: `HIER_MEASUREMENT_AND_PLOTS.md`
§7; isolation protocol: `ISOLATION_BENCHMARK.md`.)

```bash
PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
```

### Frame (fix once, before sweeping)

| Parameter | Value | Why |
|---|---|---|
| N-sweep | `48 96 192 480` | all divisible by lcm(2,4,8)=8; feeds scaling/exponent plots |
| anchor N | **480** | the fixed-N decomposition & frontier figures live here |
| K set | `2 4 8` | where A / A++ / committed-* diverge at fixed N |
| flat comparator | `flat_merkle_sort` at the **same** N | sort matches the hier permutation check; same N ⇒ no ±4% fudge |
| runs | 3 (flat/hier), 1–2 (recursion, heavy) | mean±std bands |
| deployment | concurrent **and** `--isolated` (hier); solo (recursion) | two *different claims*, not two estimates (see the isolation section) |

The hier harnesses take **lists** (`--ns … --ks …`); `run_recursion.py` takes a
**single** `--n/--k`, so recursion cells are looped, appending to one CSV.

### Phase 0 — structural pass (gate counts; deterministic, no repeats)

Settles the dualism / binding-tax-in-gates story where numbers are exact. Cheap
(`--runs 1`, and `--skip-prove` for recursion's heavy outer).

```bash
$PY pipeline/run.py --circuit circuits/flat_merkle_sort --ns 48 96 192 480 --runs 1 --out results/flat_sort.csv
$PY pipeline/run.py --circuit circuits/flat_merkle_grand_product --ns 48 96 192 480 --runs 1 --out results/flat_gp.csv
$PY pipeline/run_hier_fs.py  --ns 48 96 192 480 --ks 2 4 8 --runs 1 --out results/hier_fs.csv
$PY pipeline/run_hier.py     --ns 48 96 192 480 --ks 2 4 8 --runs 1 --out results/hier_a.csv
$PY pipeline/run_hier_cfs.py --ns 48 96 192 480 --ks 2 4 8 --runs 1 --out results/hier_cfs.csv
$PY pipeline/run_hier_c.py   --ns 48 96 192 480 --ks 2 4 8 --runs 1 --out results/hier_c.csv
for k in 2 4 8; do for n in 48 96 192 480; do
  $PY pipeline/run_recursion.py --exp 2 --n $n --k $k --runs 1 --skip-prove --out results/recursion_gates.csv
done; done
```
*Feeds:* `circuit_size = K·sub+glue` vs flat vs `sum(inner)+outer`; `circuit_size/K`
per-prover shrink; stacked gate decomposition (E1/J5).  **`flat_merkle_grand_product`**
is the grand-product flat baseline — a plain `run.py` flat circuit (same Prover.toml
as `flat_merkle_sort`, no builder/harness change).  Together with `flat_merkle_sort`,
recursion-A and recursion-A++ it completes the **{flat,recursive}×{sort,grand-product}**
2×2: the `flat_sort↔flat_gp` delta is the permutation-mechanism gadget cost (no
privacy delta — both expose only `{root,T}`), and `flat_gp↔recursion-A++` is the
matched-mechanism aggregation cost (the cleanest flat↔recursion comparison; see
`NARRATIVE_FRAMING.md` §7-8).

### Phase 1 — single-machine runtime (concurrent; the honest baseline)

No reframe needed — flat, hier, recursion are all one box. Delivers the "no
wall-clock speedup on one box" result and the **real** `peak_mb ~1/K` drop.

```bash
$PY pipeline/run.py --circuit circuits/flat_merkle_sort --ns 48 96 192 480 --runs 3 --out results/flat_sort.csv
$PY pipeline/run_hier_fs.py  --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_fs_conc.csv
$PY pipeline/run_hier.py     --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_a_conc.csv
$PY pipeline/run_hier_cfs.py --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_cfs_conc.csv
$PY pipeline/run_hier_c.py   --ns 48 96 192 480 --ks 2 4 8 --runs 3 --out results/hier_c_conc.csv
```

### Phase 2 — distributed runtime (`--isolated`; the K× claim)

On an **idle** box: each prover runs solo so its `prove_s` is the genuine per-node
time. Aggregate `--mode parallel` (max) = distributed wall-clock vs the ideal-K
diagonal; label it **compute-only upper bound**.

```bash
$PY pipeline/run_hier_fs.py  --ns 48 96 192 480 --ks 2 4 8 --runs 3 --isolated --out results/hier_fs_iso.csv
$PY pipeline/run_hier.py     --ns 48 96 192 480 --ks 2 4 8 --runs 3 --isolated --out results/hier_a_iso.csv
$PY pipeline/run_hier_cfs.py --ns 48 96 192 480 --ks 2 4 8 --runs 3 --isolated --out results/hier_cfs_iso.csv
$PY pipeline/run_hier_c.py   --ns 48 96 192 480 --ks 2 4 8 --runs 3 --isolated --out results/hier_c_iso.csv
```

### Phase 3 — recursion full runtime (solo; RAM-gated)

Recursion inners are already solo (= isolated); the aggregator derives both
deployment models from one run. **RAM ceiling:** K=2 ≈ 2.1 GB, K=4 ≈ 4.1 GB,
**K=8 ≈ 8+ GB** — only add K=8 with ~16 GB. The outer is N-independent (~704k);
the inner grows with N.

```bash
for k in 2 4; do for n in 48 96 192 480; do          # add `8` to the k-loop only if RAM allows
  $PY pipeline/run_recursion.py --exp 2 --n $n --k $k --runs 2 --out results/recursion.csv
done; done
$PY pipeline/run_recursion.py --exp 1 --n 48 --k 2 --runs 1 --out results/recursion_diag.csv  # off-frontier diagnostic
```

### Phase 4 — aggregate into comparable rows

Both modes on **isolated** data; **parallel only** on concurrent.

```bash
# concurrent -> single-machine wall-clock (co-plots with flat + recursion directly):
for v in hier_fs hier_a hier_cfs hier_c; do
  $PY pipeline/aggregate_hier.py --in results/${v}_conc.csv --out results/${v}_conc_par.csv --mode parallel
done
# isolated -> distributed wall-clock (max) AND total CPU work (sum):
for v in hier_fs hier_a hier_cfs hier_c; do
  $PY pipeline/aggregate_hier.py --in results/${v}_iso.csv --out results/${v}_iso_par.csv --mode parallel
  $PY pipeline/aggregate_hier.py --in results/${v}_iso.csv --out results/${v}_iso_tot.csv --mode total
done
# recursion (one raw -> both models):
$PY pipeline/aggregate_recursion.py --in results/recursion.csv --out results/recursion_par.csv --mode parallel
$PY pipeline/aggregate_recursion.py --in results/recursion.csv --out results/recursion_tot.csv --mode total
```

What each view legitimately states (carry these labels into figures):

| View | Claim | Compare against |
|---|---|---|
| concurrent + `parallel` (max) | single-machine wall-clock of the decomposed job | flat + recursion **directly** |
| isolated + `parallel` (max) | distributed wall-clock, one node/segment | ideal-K diagonal; **compute-only upper bound** |
| isolated + `total` (sum) | total CPU work | dualism (work conserved, not reduced) |
| `peak_mb` (max) | per-node footprint (~1/K) | flat — *valid even from concurrent* |
| `verify_s` / `proof_bytes` | O(K) binding tax (hier) vs O(1) (recursion/flat) | what the wins are paid with |

### Notes

- **Gate on correctness:** every hier cell needs `xchecks_ok == 1` and all `bb verify`
  passing; recursion needs `verify_recursion.py` accepting (one verify + 14656-byte ZK guard).
- **Equal-privacy spine** (the minimum viable frontier if time-boxed): `flat_merkle_sort`,
  `hier_fs` (concurrent+isolated), `recursion` (K=2,4) at N=480 — enough for the
  three-corner Pareto (J2) and verifier-cost-vs-K (J1). committed-* and A are the next layer.
- **Order matters:** present concurrent ("no free lunch on one box") *before* isolated
  (the K× upper bound) so the headline reads as conditional, not oversold.

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

# Flat-Merkle grand-product (in-circuit Fiat-Shamir permutation check); 30 cases
# incl. real-Merkle non-permutations that isolate the grand product from GROUP 3
python tests/correctness/test_flat_merkle_grand_product.py

# Run all soundness tests for Variant A (hierarchical, sub + glue)
# (patches circuit globals + recompiles per test; merkle_builder built on first run)
python tests/correctness/test_hierarchical_a.py

# Variant A++ (grand product + in-circuit Fiat-Shamir)
python tests/correctness/test_hierarchical_fs.py

# Variant committed-A   (blinded commitment, sort partition)
python tests/correctness/test_hierarchical_c.py

# Variant committed-A++ (blinded commitment, grand-product partition)
python tests/correctness/test_hierarchical_cfs.py
```

The committed-variant suites add two checks beyond A/A++: the **sub-side commitment
binding** (G8 — tampering the public `C_i` is rejected) and the **glue-side
commitment binding** (G0 — tampering a now-hidden witnessed value while keeping
`C_is` is rejected), plus a verifier cross-check that rejects mixed proof sets.

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
- `--runs` Repeated runs per (N, K) cell (default: 3); all reuse the one
  canonical instance for that N (timing-noise samples).
- `--out`  Output CSV path (required); appended to.
- `--seed` Base seed (default: 42); the instance is keyed by `(N, seed)` and
  cached under `data/instances/` (shared across all K and all variants — the
  Merkle tree is over the N×N matrix, independent of the partition). See
  `pipeline/instance_cache.py`.

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
3. Loads the canonical (cached) instance + cycle + tree for N, then per run
   calls `merkle_builder --hierarchical K --tree-cache ...` to produce K+1
   Prover.tomls (the tree is built once and reused), and spawns K+1 parallel
   `nargo execute && bb prove` workers (one per sub-circuit shadow plus one in
   the glue dir).  Records each worker's own wall-clock `witness_s` and
   `prove_s` (under K+1-way CPU contention).
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

## Variant A++ workflow — `circuits/hierarchical_segment_fs` + `circuits/hierarchical_glue_fs`

Variant A++ is the partition-**hidden** hierarchical design (Merkle commitment,
grand-product multiset equality, in-circuit Fiat-Shamir).  It is a near-exact
mirror of Variant A; the only architectural change is *how the partition is
enforced*:

- A's sub-circuit publishes `sorted_nodes[M]` and the glue sorts the
  concatenation against `[0..N-1]` (the partition is public).
- A++'s sub-circuit publishes a single Field grand product `P_i = ∏(X+node)`
  and folds its segment into a Poseidon2 hash chain (`h_in_i → h_out_i`); the
  glue checks `∏ P_i == ∏_{j}(X+j)` at a Fiat-Shamir challenge
  `X = Poseidon2([c],1)` derived in-circuit from the full-cycle chain terminal
  `c`.  The partition is never disclosed.

The K+1 proofs are still independent UltraHonk proofs; the verifier runs
`bb verify` K+1 times then `pipeline/verify_hier_fs.py`, which cross-checks that
all proofs share the same `root`, `c`, and `X`, and that the glue's per-segment
arrays match each sub-proof's scalars.  See `HIERARCHICAL_EXPLAINED.md` §9 for
the theory and `HIER_FS_IMPL.md` for the implementation plan that was followed.

> **Privacy note.** A++ hides the partition *computationally*, not
> information-theoretically: the public `P_i` is a multiset-confirmation oracle
> (~C(N,M) work) and the public chain anchors `h_in/h_out` are an ordering
> oracle (~(M-2)! work).  This is strong at the benchmark sizes and the price of
> the non-recursive K+1-proof architecture.  See `HIERARCHICAL_EXPLAINED.md`
> §9.11 / §14.2.

### Prerequisites

```bash
# Build the Rust merkle_builder (shared with all Merkle variants).
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

A++'s load-bearing hash is the single-input Fiat-Shamir challenge
`Poseidon2::hash([c], 1)`.  It is cross-validated (Rust ↔ Noir) by the hash-compat
test, which also emits the N=8 reference table (`HIER_FS_IMPL.md` §11):

```bash
bash tests/hash_compat/run_test.sh   # asserts both [l,r],2 and [c],1 shapes match
```

### Compile-time globals

| Circuit | Globals | Patched per |
|---|---|---|
| `hierarchical_segment_fs` | `N`, `M`, `DEPTH` | `(N, K)` cell (M = N/K, DEPTH = ⌈log₂(N²)⌉) |
| `hierarchical_glue_fs` | `N`, `K`, `DEPTH` | `(N, K)` cell |

`run_hier_fs.py` patches and recompiles automatically.  The circuits ship at the
N=8, K=2 reference size.

### Single end-to-end run on the reference instance (N=8, K=2)

Same documented cycle as A (`0 → 5 → 3 → 2 → 7 → 4 → 1 → 6 → 0`, cost 92,
threshold 100).  Only the builder flag (`--hierarchical-fs`), circuit names, and
verifier (`verify_hier_fs.py`) differ from A's walkthrough.

```bash
# 1. Patch + compile both circuits, write VKs (circuits already default to N=8, K=2).
( cd circuits/hierarchical_segment_fs && nargo compile \
    && bb write_vk -b target/hierarchical_segment_fs.json -o target/vk )
( cd circuits/hierarchical_glue_fs && nargo compile \
    && bb write_vk -b target/hierarchical_glue_fs.json -o target/vk )

# 2. Build the reference instance's K+1 Prover.tomls into /tmp/hier_fs_ref.
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
     "--hierarchical-fs", "2", "--out-dir", "/tmp/hier_fs_ref"],
    input=payload, text=True, check=True,
)
EOF

# 3. Prove sub_0, sub_1, glue (mirrors A; the sub circuit is reused for both segments).
for seg in 0 1; do
  cp /tmp/hier_fs_ref/sub_${seg}/Prover.toml circuits/hierarchical_segment_fs/Prover.toml
  ( cd circuits/hierarchical_segment_fs \
    && nargo execute \
    && bb prove -b target/hierarchical_segment_fs.json \
                -w target/hierarchical_segment_fs.gz \
                -k target/vk/vk -o target/proof_sub${seg} )
done
cp /tmp/hier_fs_ref/glue/Prover.toml circuits/hierarchical_glue_fs/Prover.toml
( cd circuits/hierarchical_glue_fs \
  && nargo execute \
  && bb prove -b target/hierarchical_glue_fs.json \
              -w target/hierarchical_glue_fs.gz \
              -k target/vk/vk -o target/proof_glue )

# 4. Stage the K+1 proofs for verify_hier_fs.py.
mkdir -p /tmp/hier_fs_proofs/sub_0 /tmp/hier_fs_proofs/sub_1 /tmp/hier_fs_proofs/glue
cp circuits/hierarchical_segment_fs/target/proof_sub0/{proof,public_inputs} /tmp/hier_fs_proofs/sub_0/
cp circuits/hierarchical_segment_fs/target/proof_sub1/{proof,public_inputs} /tmp/hier_fs_proofs/sub_1/
cp circuits/hierarchical_glue_fs/target/proof_glue/{proof,public_inputs}    /tmp/hier_fs_proofs/glue/

# 5. Run K+1 bb verify + the cross-checks (same root/c/X; per-segment field equalities).
python pipeline/verify_hier_fs.py \
  --proof-dir /tmp/hier_fs_proofs \
  --n 8 --k 2 \
  --sub-vk  circuits/hierarchical_segment_fs/target/vk/vk \
  --glue-vk circuits/hierarchical_glue_fs/target/vk/vk
```

Expected output ends with `ACCEPTED`.  The sub public-inputs dump has exactly 9
field elements (constant in M — one of A++'s wins) and the glue has 6K+4.

### Soundness tests

```bash
python tests/correctness/test_hierarchical_fs.py
```

Covers eight cases (baseline + seven perturbations):

1. **VALID** — reference instance N=8 K=2 passes end to end.
2. **INVALID — cost binding** (inherited): sub G4 catches `sum(edge_costs) != partial_cost`.
3. **INVALID — boundary Merkle** (inherited): glue G6 catches a tampered boundary cost.
4. **INVALID — cross-check `c`** (A++-unique): mix sub-proofs from cycle A with the
   glue from cycle B (same matrix).  Each `bb verify` accepts; `verify_hier_fs.py`
   rejects because `sub_i.c != glue.c` (the A++ analogue of A's "same root").
5. **INVALID — bad `P_i`** (A++-unique): tamper a sub's grand product; sub G6 rejects.
6. **INVALID — broken chain** (A++-unique): tamper `glue.h_ins[1]`; glue G2 rejects.
7. **INVALID — partition overlap** (A++-unique): node 3 in both segments.  Each sub
   is locally valid, but glue G5's grand-product check fails via Schwartz-Zippel at
   the unforgeable chain-derived X.  *This is the headline demonstration that the
   grand product replaces A's sort.*
8. **VALID — N=48 K=4** sanity (witness only).

### Benchmark sweep — `pipeline/run_hier_fs.py`

Identical interface to `run_hier.py`; same grid recommended for direct A vs A++
comparison:

```bash
python pipeline/run_hier_fs.py \
  --ns 48 96 192 480 \
  --ks 2 4 8 \
  --runs 3 \
  --out results/hier_fs.csv
```

It patches/compiles the `_fs` circuits, uses `/tmp/hier_fs_shadows` (distinct from
A's shadow dir, so both sweeps can run concurrently), builds K+1 Prover.tomls via
`merkle_builder --hierarchical-fs`, proves K+1-way in parallel, and runs
`verify_hier_fs.py` per cell.  CSV schema and columns are identical to
`run_hier.py`'s (variant column = `hier_fs`).

### Aggregating + plotting (A and A++ together)

`pipeline/aggregate_hier.py` is **variant-aware**: it reads the `variant` column
from the raw CSV, so the *same* command serves both A and A++ — `hier_a.csv`
yields `hier_a_k{K}` rows and `hier_fs.csv` yields `hier_fs_k{K}` rows.  No flag
needed.  Aggregation rules (per cell) are unchanged from the A section above
(`circuit_size = K*sub + glue`, `prove_s/witness_s = max` for `--mode parallel`
or `sum` for `--mode total`, `peak_mb = max`, etc.).

```bash
# Aggregate A++ (parallel wall-clock projection and total CPU work).
python pipeline/aggregate_hier.py --in results/hier_fs.csv --out results/hier_fs_par.csv --mode parallel
python pipeline/aggregate_hier.py --in results/hier_fs.csv --out results/hier_fs_tot.csv --mode total

# (Do the same for A if not already done.)
python pipeline/aggregate_hier.py --in results/hier_a.csv  --out results/hier_a_par.csv  --mode parallel
python pipeline/aggregate_hier.py --in results/hier_a.csv  --out results/hier_a_tot.csv  --mode total
```

**The frontier figure** — flat baseline, A, and A++ on the same axes (the
thesis's headline comparison).  `plot.py` accepts any number of CSVs and draws
one line per `variant`:

```bash
python pipeline/plot.py \
  --csv results/500.csv results/hier_a_par.csv results/hier_fs_par.csv \
  --out plots/flat_vs_hier_a_vs_hier_fs
```

Reading the panels (A++ specifics):

- **circuit_size** — A++'s sub is ~+6% over A's (chain G5 + challenge G7); the
  glue drops sharply at large N (A's O(N) sort is gone, replaced by ~N cheap
  field mults).  Watch the `peak_mb` glue line: A++'s glue should fall well below
  A's ~159 MB floor at N=480 — the headline empirical claim to confirm.
- **proof_bytes** — same as A (K+1 separate proofs; ~14.6 KB × (K+1)).
- **prove_s** under `--mode parallel` is CPU-contended single-machine wall-clock,
  same caveat as A: the per-prover speedup requires isolated hardware.

### Common issues (A++-specific)

**`verify_hier_fs.py` reports "c mismatch" or "X mismatch"**
The K+1 proofs come from different *cycles* (not just different matrices).  All
K+1 Prover.tomls must come from the same `merkle_builder --hierarchical-fs` call —
`c` and `X` are derived from the full cycle, so any cycle difference trips this.

**Glue `nargo execute` fails with "grand-product partition mismatch"**
The segment node-multisets do not tile `{0..N-1}` (overlap or a missing node).
This is the partition check (glue G5) firing correctly — expected for a cheating
instance, a bug otherwise.

**Glue `nargo execute` fails with "X != Poseidon2(c)"**
Rust/Noir Poseidon2 drift on the single-input shape.  Re-run
`bash tests/hash_compat/run_test.sh`; it must pass before any A++ proof is valid.

---

## Recursion micro-experiments — `tests/recursion_micro/`

These two experiments measure the cost of **recursive proof verification** — folding
the per-segment cross-checks *into* an outer circuit that verifies the segment
proofs in-circuit.  The per-segment public values (endpoints, `P_i`, chain
anchors, `c`, `X`) become **witness** of the outer circuit and vanish from the
public surface, which collapses back to `(root, threshold)` — flat_merkle's
**perfect / information-theoretic hiding**.  The price is a single monolithic
proof of ~10⁶ gates.  This is the frontier's "perfect hiding is expensive" row;
folding (ClientIVC / Protogalaxy) is the proposed resolution (future work).

| Mode | Outer circuit | What it proves |
|---|---|---|
| **1 — single segment** *(diagnostic, off-frontier)* | `tests/recursion_micro/exp1_single_segment` | Recursively verifies **one** `hierarchical_segment_fs` proof. Isolates the per-segment recursion overhead. Diagnostic only — not a complete TSP statement; keep its `recursion_1seg` row off the frontier figures. |
| **2 — K segments** *(THE recursion variant)* | `circuits/recursion` | Recursively verifies **all K** segment proofs **and** re-runs the full glue (chain stitch, FS bind, grand-product partition, K boundary Merkle edges, threshold). A **complete** recursive proof of the K-segment cycle, exposing only `(root, threshold)`. The perfect-hiding endpoint / equal-ground counterpart of A++ at the same K. The circuit is generic over K (an array of K proofs); the harness patches `N, K, DEPTH`. |

The inner is the **unmodified `hierarchical_segment_fs`** (the A++ sub-circuit):
recursion-friendliness comes from the *proving flavor*, not a circuit attribute,
so the inner is identical to what A++ benchmarks — equal-ground by construction.
(*Why A++ and not the A sub-circuit, given recursion hides the partition either
way?* See `Recursive_inner_circuit_choice_explained.md` for the full rationale;
short version — A++'s O(1) public surface keeps the recursive verification
segment-size-independent, and it gives a controlled comparison with the A++ row.
A parallel **A-inner** variant exists to quantify the difference: see "A-inner
recursion" below.)

**ZK path (important).** We use the **ZK** recursive verifier `verify_honk_proof`
(`UltraHonkZKProof`, length **458**), proved with `bb -t noir-recursive` —
**not** the toy's `verify_honk_proof_non_zk` (length 410, `-t
noir-recursive-no-zk`).  For the final verifier's view only the *outer* proof
must be ZK; ZK *inner* proofs additionally hide each segment's witness from the
aggregator who runs the outer prover.  **Confirmed (bb 5.0.0-nightly.20260324):**
default `bb prove` (the outer) is ZK — a **458-field / 14656-byte** proof; `-no-zk`
is 410 fields.  The hiding claim rests on this, so both `run_recursion.py` and
`verify_recursion.py` **assert the 14656-byte length**, failing loudly if a future
bb default flips to non-ZK.

### Prerequisites

```bash
# bb_proof_verification (the in-circuit Honk verifier) resolves from the Aztec
# packages repo, tag v5.0.0-nightly.20260518 — fetched automatically on first
# `nargo compile` of either outer circuit.
# The merkle_builder must be built (shared with all Merkle variants):
cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml
```

### Running an experiment

`run_recursion.py` does everything per `(N, K, run)`: patches + compiles the
inner segment, writes its **recursive ZK** VK, generates+solves an instance,
builds the K+1 Prover.tomls (`merkle_builder --hierarchical-fs`), proves the
needed segment(s) with `bb prove -t noir-recursive`, assembles the outer
`Prover.toml`, then compiles the outer circuit and records `bb gates`, witness,
prove (time + peak mem) and verify.  The shared segment source is
snapshotted and **restored** afterwards, so your A++ setup is left untouched.

```bash
# Exp 2 (default) — the complete K-segment recursive proof / THE variant
# (any K >= 2, N divisible by K).  Outer circuit = circuits/recursion:
python pipeline/run_recursion.py --exp 2 --n 48 --k 2 --runs 1 \
    --out results/recursion.csv
python pipeline/run_recursion.py --exp 2 --n 48 --k 4 --runs 1 \
    --out results/recursion.csv

# Exp 1 — DIAGNOSTIC: isolate the single-segment recursion cost (off-frontier;
# N=48 K=2 matches A++'s smallest sweep point; outer cost ~independent of N):
python pipeline/run_recursion.py --exp 1 --n 48 --k 2 --runs 1 \
    --out results/recursion_diag.csv

# Verify a produced outer proof — ONE bb verify, no cross-checks (the binding-tax
# collapse made operational), plus a ZK-length guard:
python pipeline/verify_recursion.py \
    --proof-dir circuits/recursion/target/proof \
    --vk        circuits/recursion/target/vk/vk

# --skip-prove  : only compile / `bb gates` / `nargo execute` the outer (fast;
#                 gets the headline gate count without the heavy outer bb prove).
# --runs R      : repeat the cell R times (each row tagged with `run`).
```

The outer recursive prove is heavy and grows with K: the gate count is
~`K x 7e5` (each in-circuit verifier checks a fixed-size proof, so it's
~independent of N but linear in K).  Rough peak memory: ~1 GiB (K=1) / ~2.1 GiB
(K=2) / ~4.3 GiB (K=4) — **check you have the RAM before large K** (K=4 needs a
~16 GiB machine).  Per the benchmark workflow, drive larger sweeps yourself; the
harness is left ready.

### How the pipeline fits together (the outer consumes inner proofs — it does not generate them)

**You cannot just run the outer circuit.**  A Noir circuit + `bb` is a prover for
one fixed relation, not an orchestrator: `bb prove` takes a *complete* witness
(everything in `Prover.toml`) and emits a proof — it never spawns sub-processes
or computes its inputs.  The recursion call `verify_honk_proof(vk, proof, pubs,
key_hash)` is just *constraints* over `proof`, and `proof` is **ordinary
witness**.  So the K inner proofs (458 field elements each) must already sit in
the outer `Prover.toml` before `nargo execute` can even solve the witness.  Run
the outer with no `Prover.toml` and it fails immediately — the inner proof is
*required input*, not something the outer derives.

The recursive proof is therefore a **three-phase pipeline**, and the circuit
itself contributes only phase 3:

```
phase 1  prove each segment       bb prove -t noir-recursive --output_format json
                                   -> proof_i/proof.json (458), public_inputs.json (9), vk.json (vk[115] + hash)
phase 2  serialize those fields into the OUTER Prover.toml
                                   (proofs[], sub_pubs[], sub_vk, key_hash, + boundary witness from the glue toml)
phase 3  prove the outer          nargo execute + bb prove   -> the 1 delivered proof
```

`run_recursion.py` **is** the orchestrator: it performs all three phases, so with
the driver it is genuinely one command and you feed nothing by hand.  Without the
driver you must do phases 1–2 yourself.  The manual recipe (Exp 1, single
segment — Exp 2 is the same with K inner proofs plus the boundary witness):

```bash
SEG=circuits/hierarchical_segment_fs          # patched to (N, M, DEPTH) + nargo compile first
# (the segment's Prover.toml comes from `merkle_builder --hierarchical-fs K`,
#  e.g. copy out-dir/sub_0/Prover.toml into $SEG/Prover.toml — see the A++ section.)
# phase 1: recursive ZK VK + one segment proof
bb write_vk -b $SEG/target/hierarchical_segment_fs.json -t noir-recursive -o $SEG/target/vk
bb write_vk -b $SEG/target/hierarchical_segment_fs.json -t noir-recursive --output_format json -o $SEG/target/vk_json
(cd $SEG && nargo execute && bb prove -b target/hierarchical_segment_fs.json \
    -w target/hierarchical_segment_fs.gz -k target/vk/vk -t noir-recursive \
    --output_format json --verify -o /tmp/seg0)
# phase 2: hand-write tests/recursion_micro/exp1_single_segment/Prover.toml using
#   verification_key = vk_json/vk.json ["vk"]   (115 fields)
#   key_hash         = vk_json/vk.json ["hash"]
#   proof            = /tmp/seg0/proof.json ["proof"]          (458 fields)
#   sub_pub          = /tmp/seg0/public_inputs.json ["public_inputs"]  (9 fields)
#   root             = sub_pub[3]
# phase 3: run the outer
(cd tests/recursion_micro/exp1_single_segment && nargo compile && nargo execute && \
    bb write_vk -b target/rec_exp1_single_segment.json -o target/vk && \
    bb prove -b target/rec_exp1_single_segment.json -w target/rec_exp1_single_segment.gz \
        -k target/vk/vk -o /tmp/outer && \
    bb verify -k target/vk/vk -p /tmp/outer/proof -i /tmp/outer/public_inputs)
```

This manual proof/VK-field plumbing (phase 2) is exactly what makes the recursion
path "finicky," and why folding frameworks (ClientIVC / Protogalaxy), which
orchestrate the inner→outer hand-off internally, are the natural next step.

Raw CSV schema (one row per measured circuit):

```
exp,n,k,m,depth,run,role,circuit,gates,acir,compile_s,witness_s,prove_s,verify_s,proof_bytes,peak_mb
```

`role` is `inner_segment` (the segment proof(s)) or `outer_recursive` (the
recursive verifier — its `gates` is THE recursion cost number).

### Headline numbers (N=48, this machine)

| Circuit | gates | prove | peak | verify | proof |
|---|---|---|---|---|---|
| inner segment (A++ sub) | 28,480 (K=2) / 15,184 (K=4) | ~0.5–0.8 s | ~62 MiB | — | — |
| **Exp 1 outer** (verify 1) | **704,363** | ~8.6 s | ~1.0 GiB | ~0.02 s | 14.7 KB |
| **Exp 2 outer, K=2** (verify 2 + glue) | **1,473,357** | ~24 s | ~2.1 GiB | ~0.02 s | 14.7 KB |
| **Exp 2 outer, K=4** (verify 4 + glue) | **3,008,907** | ~40 s | ~4.1 GiB | ~0.02 s | 14.7 KB |

- One in-circuit ZK verification ≈ **704k gates**, ~147× the segment's own logic,
  and **independent of segment size** (identical at N=8 and N=48).
- Recursion scales **~K×**: K=2 ≈ 2.09× and K=4 ≈ 4.27× the single verification
  (3,008,907 / 704,363); the full glue tax is small (~63k gates at K=2, ~191k at
  K=4). Prove time and peak memory track the same ~K growth.
- **vs A++ at the same K** (aggregated total proving work): recursion is ~25×
  (K=2) → ~45× (K=4) more gates, and the gap *widens* with K — A++'s total grows
  slowly (~K small subs + glue) while recursion adds a full ~700k-gate verifier
  per segment. That is the aggregation layer dwarfing the TSP logic.

### Comparable results — aggregate, then plot

The raw CSV is *not* in the `plot.py` schema (like the raw `hier_*` CSVs aren't).
`pipeline/aggregate_recursion.py` is the recursion analogue of
`aggregate_hier.py`: it folds each `(exp, N, run)` cell's inner+outer rows into
one `run.py`-schema row.  Aggregation rules: `circuit_size = sum(inner) + outer`
(total proving work); `prove_s / witness_s = inner-step + outer` where the inner
step is `max` (`--mode parallel`, default) or `sum` (`--mode total`); **`verify_s`
and `proof_bytes` are the OUTER's only** (the verifier checks exactly one proof —
recursion's whole point); `peak_mb = max(the K inner-segment peaks and the outer
peak)`.

> **What `peak_mb = max` means (and why it's correct here).** Each raw `peak_mb`
> is the peak RSS of *one* `bb prove` process. The aggregator reports the **max
> over the K inner peaks and the outer peak** — the heaviest single proving step
> ("per-prover peak"), the same metric `aggregate_hier.py` uses, so recursion and
> A++ are compared on the same axis. Because the outer consumes the inner proofs
> as *data* (the inner provers have already exited and freed their memory), only
> one prover is resident at a time under sequential proving — so the machine's
> peak-over-time **is** this max, exactly. It would under-count only if K inner
> provers ran *concurrently* and their memory summed above the outer
> (`sum(inner) > outer`); in every measured cell the outer dominates by 4–14×
> (worst: N=480 K=4 → Σinner 1.17 GB vs outer 4.1 GB), so the two interpretations
> coincide. An inner *larger* than the outer would be reported (inner peaks are
> in the max); only the concurrent-sum case is not modelled, and it never arises.

```bash
# Aggregate (parallel projection of the inner proofs; total CPU work too).
python pipeline/aggregate_recursion.py --in results/recursion_micro.csv \
    --out results/recursion_par.csv --mode parallel
python pipeline/aggregate_recursion.py --in results/recursion_micro.csv \
    --out results/recursion_tot.csv --mode total
```

Output variant column: exp 2 → `recursion_k{K}` (one line per K — e.g.
`recursion_k2`, `recursion_k4` — the complete variants to compare against
`hier_fs_k2`, `hier_fs_k4`), exp 1 → `recursion_1seg` (single-segment diagnostic
— its `verify_s` / `proof_bytes` describe verifying *one* segment proof, not a
full cycle).

`--split-components` (recursion).  Like the hierarchical aggregator, this emits
two extra rows per cell beside the combined one: `recursion_k{K}_seg` (the K inner
A++ segment proofs only) and `recursion_k{K}_outer` (the outer recursive proof
alone).  **Honesty note:** there is deliberately **no `_glue` row** — recursion
fuses the glue logic into the outer circuit together with the K in-circuit
verifications, which dominate it (~704k gates each vs ~63k total glue at K=2), so
the glue is not a separately measured artifact.  The whole **outer is the binding
layer** — the recursion analogue of the hierarchical glue + verifier tax — so the
split is *segments vs outer*, not *segments vs glue*.  The inner proofs are
consumed by the outer (never delivered to the final verifier), so the `_seg` row
carries no `verify_s` / `proof_bytes`.  Draw with `--variants 'recursion_k4_seg'
'recursion_k4_outer'`.

### Component bar charts — `plot_recursion_stack.py`

For the "where does the recursion cost go" composition figure (HIER_MEASUREMENT_AND_PLOTS.md §E),
`pipeline/plot_recursion_stack.py` reads the **raw** recursion CSV (it needs both the
single-segment and the cumulative-over-K values, which the aggregator conflates) and
draws **metric-aware** bars at a **fixed K**:

- **additive metrics** (`circuit_size`, `prove_s`, `witness_s`, `acir_opcodes`) — a
  2-layer **stack** `[ΣK segments | outer]` that truly sums to the total, plus a thin
  **companion** bar for one segment (the per-node / ideal-parallel value).
- **`peak_mb`** — **grouped** bars (single-segment vs outer), never stacked: peak memory
  is max-not-sum (only one prover is resident at a time), so a stack would draw memory
  the machine never occupies. `--include-concurrent-mem` adds the hypothetical
  Σ-segments bar (only realized if all K inner provers ran concurrently — recursion does not).
- **`verify_s` / `proof_bytes`** — a single **outer-only** bar (the O(1) verifier win).

```bash
$PY pipeline/plot_recursion_stack.py --csv results/recursive_raw.csv --k 2 \
    --out plots/recursion_components --metrics circuit_size prove_s peak_mb \
    --format pdf --no-title
# run once per K (K is fixed per figure; mixing K on one per-N axis is ambiguous).
```

### Line charts with a K-aware palette — `plot_recursion_lines.py`

`pipeline/plot.py` hashes each variant name to a colour, so the recursion split
variants (`recursion_k2`, `_k2_seg`, `_k2_outer`, `_k4`, …) get unrelated, often
similar shades.  `pipeline/plot_recursion_lines.py` is plot.py with a recursion
palette: **colour keyed by K** (K=2 blue, K=4 orange, K=8 green — pinned to the K
value, stable across figures) and **marker/linestyle keyed by the component**
(combined `o`-solid, `_seg` `s`-dashed, `_outer` `^`-dotted, `_glue` `D`-dashdot).
So all series of one K share a hue and are told apart by glyph.  It takes the
**aggregated** CSV (use `--split-components`) and forwards every plot.py flag.

```bash
$PY pipeline/plot_recursion_lines.py --csv results/recursive_par.csv \
    --out plots/recursion_lines --metrics circuit_size prove_s peak_mb
```

Plot **one aggregation mode per figure**: the palette keys on K + component only,
so if you used `--mode-in-name` (e.g. `recursion_k2_parallel` vs `_total`) filter
to one with `--variants 'recursion_*_parallel'`, else the two modes draw alike.

### Full flat-vs-recursion comparison — `plot_comparison.py`

`pipeline/plot_comparison.py` is the dedicated figure for the flat-vs-recursion
comparison (both are perfect-hiding, one-proof variants — so this is a
cost/parallelism/memory comparison, not a privacy one).  It draws **curated
series per metric** (the C1–C6 taxonomy), as a grid for inspection or one file
per metric with `--separate` for the thesis:

| metric | series drawn (per K) | the point |
|---|---|---|
| `circuit_size` | flat + aggregate + outer | aggregate ≈ flat + ~constant outer tax |
| `prove_s` | flat + aggregate | wall-clock (parallel: max-seg + outer) |
| `peak_mb` | flat + single-seg + outer | the win: per-leaf vs constant outer ceiling vs flat (crossover) |
| `verify_s` / `proof_bytes` | flat + outer | tie (both O(1)) |

Input is **aggregated** CSVs: the flat baseline (`flat_merkle_sort` by default,
`--flat-variant` to change) + the recursion **`--split-components`** CSV.  Time
uses the **parallel** projection, so feed a `--mode parallel` recursion CSV.
Colour is keyed by K (flat in black), marker/linestyle by component.

```bash
# grid (inspection):
$PY pipeline/plot_comparison.py --csv results/flat.csv results/recursive_par.csv \
    --out plots/flat_vs_recursion

# thesis figures (one vector file per metric):
$PY pipeline/plot_comparison.py --csv results/flat.csv results/recursive_par.csv \
    --out plots/flat_vs_recursion --separate --format pdf --no-title

# restrict to K in {2,4}:
$PY pipeline/plot_comparison.py --csv results/flat.csv results/recursive_par.csv \
    --out plots/cmp_k24 --k 2 4
```

`--match-n` clips the flat baseline to only the N values where recursion is also
defined (the recursion sweep is sparser), so both lines span the same N — handy
when the dense flat sweep visually dwarfs the few recursion points. Respects `--k`.

### Recursion parallel-vs-total gap — `plot_recursion_modes.py`

`pipeline/plot_recursion_modes.py` is the recursion-alone motivation figure: it
shows that the **parallel** (distributed, `max-seg+outer`) and **total**
(single-machine, `sum-seg+outer`) wall-clocks are *close* — because the serial
outer dominates and only the cheap segment phase parallelizes (Amdahl). The small
shaded gap is what justifies carrying the **total / single-machine** number into
the apples-to-apples comparison with flat (flat is single-machine too), instead of
the optimistic parallel projection.

Because mode isn't a CSV column, it reads the **raw** CSV and derives *both* modes
itself, per (N,K): `parallel = max(inner)+outer`, `total = sum(inner)+outer`. Only
time metrics (`prove_s`, `witness_s`) differ between modes (gates are structural,
memory is per-process max → zero gap), so it restricts to those. It also prints
the P/T ratio per (K,N).

```bash
$PY pipeline/plot_recursion_modes.py --csv results/recursive_raw.csv \
    --out plots/recursion_modes --metrics prove_s
# observed: P/T ranges ~0.98 (small N / large K) down to ~0.73 (large N) —
# parallelism trims <=27%, never enough to beat flat (see plot_comparison.py).
```

### Prover wall-clock stacked bars — `plot_prover_time_bars.py`

`pipeline/plot_prover_time_bars.py` shows the per-proof prover wall-clock =
**witness + prove** as grouped, stacked bars: x = N, a **cluster per N** for
flat / K=2 / K=4 / K=8, each bar a stack of `prove` (solid, bottom) + `witness`
(hatched, on top). Stacking is valid — the two phases (`nargo execute` then
`bb prove`) are sequential, so they add. Witness is a sliver at small N (drawn
anyway, for consistency) but grows to ~20–30% at N=2000–3000 (see
`RECURSION_COMPARISON_NOTES.md` §11). Colour = variant; the hatched cap = witness.

Input is **aggregated** CSVs (flat baseline + recursion `aggregate_recursion`
output; the `recursion_k{K}` combined rows carry `prove_s`/`witness_s` already
combined). The N axis defaults to the recursion sweep points (flat is clipped to
match). Deployment (parallel/total) is whichever `--mode` you aggregated with.

```bash
$PY pipeline/plot_prover_time_bars.py \
    --csv results/flat.csv results/recursive_par.csv \
    --out plots/prover_time_bars --title "Prover wall-clock (witness + prove), parallel"
# single N (one cluster): add  --n 1000 ;  subset K: add  --k 2 4
```

### Cost-vs-cost frontier scatter — `plot_frontier_scatter.py`

`pipeline/plot_frontier_scatter.py` is the synthesis figure (C7): at a **fixed N**,
each variant is a **point** in a 2-D cost space (x = a verifier cost, y = a prover
cost), so the family's trade-off becomes a Pareto picture and the binding tax shows
up as geometry — hierarchical pays on the verifier (→ right), recursion on the
prover (↑ up), flat pays neither decomposition cost (but its prover-memory rises
with N). Colour = K (flat black), marker = family; same-family points are joined by
a faint K-trajectory; `--pareto` draws the non-dominated lower-left front.

Input is **aggregated** CSVs (the combined `variant` rows). Most informative with
the **full family** (flat + `hier_*` + recursion); for flat+recursion only the
verifier axis collapses (both O(1)), so pick two varying axes (`--x prove_s
--y peak_mb`).

```bash
$PY pipeline/plot_frontier_scatter.py \
    --csv results/flat.csv results/recursive_par.csv results/hier_fs_par.csv \
    --n 96 --out plots/frontier_scatter --pareto
# default axes: --x proof_bytes --y peak_mb. Override e.g. --x verify_s --y prove_s.
```

**Reading it:** the frontier *shifts with N*. At small N flat dominates (cheap on
both axes); recursion sits upper-left (verifier-cheap, memory-heavy) and is often
*dominated* there; A++ sits lower-right (memory-cheap, O(K) verifier). At large N
flat's memory climbs and the decomposed variants enter the front — so plot it at
the largest N your data covers for the most informative picture.

**The frontier figure** — flat baseline, A++, and recursion (all K) on the same
axes (`plot.py` draws one line per `variant`, matching by `n`):

```bash
python pipeline/plot.py \
  --csv results/500.csv results/hier_fs_par.csv results/recursion_par.csv \
  --out plots/frontier
```

Reading the panels (recursion specifics):

- **circuit_size** — `recursion_k2` sits ~52× and `recursion_k4` ~100× above the
  corresponding `hier_fs_k{K}` per-proof line: the cost of the K in-circuit
  verifiers (~`K x 7e5` gates). This is the headline tradeoff, and it scales ~K.
- **verify_s** / **proof_bytes** — recursion is **flat in K**: one ~14.7 KB proof,
  one ~15 ms verify, for *any* K — versus A++'s K+1 proofs and K+1 verifies plus
  cross-checks. The aggregation reflects this (outer-only).
- **peak_mb** / **prove_s** — recursion climbs back above flat and grows ~K (one
  big proof, no K-way parallelism); A++'s parallel wins are surrendered. That *is*
  the "perfect hiding is expensive" story; folding is the row that would recover
  both.

> Single-N note: `plot.py` draws lines across `N`. With one `N` measured you get
> single points (no slope). Add more `N` (`--n 96 192 ...`, divisible by K) for
> trend lines, or read the values from `results/recursion_par.csv` directly for a
> one-`N` table comparison.

### A-inner recursion (the alternative design) and `compare_inner.py`

The experiments above use the **A++** sub-circuit as the inner. A deliberate,
**fully separate** duplicate uses the **Variant A** sub-circuit instead — see
`Recursive_inner_circuit_choice_explained.md` for *why* (short version: inside
recursion the partition is hidden either way, so A's public node set is no longer
a leak; A lets the outer check the partition by a deterministic **sort** instead
of A++'s grand-product + Fiat-Shamir, at the price of an **O(M) public surface**).

- Circuits: `exp1_single_segment_a`, `exp2_k_segments_a` (sort-based partition,
  no FS; globals `N,K,M,DEPTH`).
- Driver: `run_recursion_a.py` — same flags as `run_recursion.py`, inner =
  `circuits/hierarchical_segment`, builder `--hierarchical` (not `-fs`),
  A `sub_pub` = `M+4` fields. Writes `results/recursion_a_micro.csv`.

```bash
python tests/recursion_micro/run_recursion_a.py --exp 2 --n 48 --k 2 --runs 1 \
    --out results/recursion_a_micro.csv
```

**Head-to-head:** `compare_inner.py` runs *both* variants on the **same instance**
(both drivers load the instance from the same `(N, seed)` cache via
`instance_cache.py`, so one `--seed` gives both the identical cycle and segmentation) and
prints the per-metric delta for the outer proof:

```bash
python tests/recursion_micro/compare_inner.py --n 480 --k 2 --exp 2 --skip-prove
#   --skip-prove : gate-only (fast).  --keep-csv DIR : save both raw CSVs + a diff CSV.
```

What it shows (this machine):

| metric | A++ inner | A inner | note |
|---|---|---|---|
| inner public inputs | 9 (O(1)) | M+4 (O(M)) | 28 @N48, 244 @N480 |
| inner segment gates | 28,480 | 27,084 | A ~−5% (no FS gadgets) |
| **outer gates @ N=48** | 1,473,357 | 1,475,164 | +0.1% — a wash at M=24 |
| **outer gates @ N=480** | 1,475,250 (flat in N) | 1,497,705 (grows) | **+22,455 (+1.5%)** — the O(M) term |
| outer witness_s @ N=480 | 0.19 s | 0.66 s | A's in-circuit sort, +250% |
| outer proof_bytes | 14,656 | 14,656 | **identical** (1 ZK proof) |
| outer verify_s | ~0.016 s | ~0.016 s | identical |
| outer peak_mb | ~2.1 GiB | ~2.0 GiB | identical (outer-dominated) |

**Reading it.** The two designs are *practically equal* in total cost (the K
in-circuit verifications dominate both), and **identical on the verifier side**
(one 14.7 KB proof, ~16 ms verify, perfect hiding — both expose only
`root,threshold`). The one structural signal: **A++'s outer is flat in N**
(1.473M→1.475M across N=48→480) while **A's grows** (1.475M→1.498M) — the O(M)
public-input absorption + the N-element sort. That is the rationale's prediction,
measured. (`outer prove_s` differences are dominated by single-run noise — re-run
`--runs 3` if you need that column; the gate counts are exact.)

### Common issues (recursion-specific)

**`nargo compile` (outer) fails with "Invalid comment character: only ASCII…"**
Noir comments must be ASCII; avoid box-drawing/Unicode in the outer `main.nr`.

**Outer `nargo execute` fails inside the recursive verify**
The inner proof / VK / public-inputs fed to `verify_honk_proof` don't agree.
Re-derive them from the *same* `bb prove -t noir-recursive` call — the proof,
`vk.json["vk"]`, `vk.json["hash"]`, and `public_inputs.json` must be one set.
The driver does this automatically; only relevant if assembling by hand.

**Proof length assertion (`expected 458 … got 410`)**
A non-ZK proof leaked in. Both `write_vk` and `prove` must use `-t
noir-recursive` (ZK), and the outer must import `UltraHonkZKProof`, not
`UltraHonkProof`.

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
| `hierarchical_segment_fs` + `hierarchical_glue_fs` | Poseidon2 Merkle root | Grand product + in-circuit Fiat-Shamir (partition hidden) | done (Variant A++) |
| `circuits/recursion` (+ reused `hierarchical_segment_fs`) | Poseidon2 Merkle root | In-circuit recursive verify of K **A++** segment proofs + glue (grand-product partition; any K≥2; **perfect** hiding) | done (recursion **variant**) |
| `tests/recursion_micro/exp2_k_segments_a` (+ reused `hierarchical_segment`) | Poseidon2 Merkle root | In-circuit recursive verify of K **A** segment proofs + glue (**sort** partition, no FS; any K≥2; **perfect** hiding) | done (A-inner comparison variant) |
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
