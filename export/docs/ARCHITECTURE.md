# Architecture

The project measures several ways to prove a Hamiltonian-cycle cost bound for a generated TSP
instance, in zero knowledge. Each benchmark cell patches compile-time Noir globals, creates a
witness, proves it with `bb`, verifies it, and records timing/size/memory metrics.

The naming follows the thesis register. The proof is either **monolithic** (a single circuit,
the Ch. 4 baseline) or **composite** (the route is cut into `K` segments, each proved on its
own, then recombined — the Ch. 5 constructions). A composite proof recombines either
**externally**, by a separate glue proof the verifier checks alongside the `K` segments, or
**recursively**, by an outer circuit that verifies the segments in-circuit. Orthogonally, the
per-segment partition fingerprint is checked by a **sort** or a **(grand-)product** mechanism,
and the external glue may stitch on **plain** shared values or on blinded **committed** ones.

## Data Flow

1. `pipeline/instance_gen.py` creates a deterministic Euclidean TSP instance.
2. `pipeline/solver.py` builds a valid Hamiltonian cycle with nearest-neighbour plus bounded 2-opt.
3. `pipeline/format_inputs.py` or `pipeline/merkle_builder` writes `Prover.toml` witness/public input files.
4. `nargo compile` and `nargo execute` build the circuit and witness.
5. `bb prove`, `bb verify`, and the verifier helper scripts produce and check proofs.
6. Aggregators and plotters turn raw CSVs into comparison tables and figures.

Large deterministic instance artifacts are cached under `data/instances/` by
`pipeline/instance_cache.py`; that cache is generated locally and ignored.

## Circuit Families

### Monolithic (Ch. 4 — the single-circuit baseline)

Shipped baselines (cost matrix committed to a Poseidon2 Merkle root):

- `monolithic_committed_sort` — the crowned baseline (permutation checked by sorting).
- `monolithic_committed_product` — grand-product permutation mechanism.

Mechanism study (public cost matrix; the Ch. 4 §"five ways to check a permutation" exploration,
kept for reference, not on the frontier):

- `monolithic_study_pairwise`
- `monolithic_study_sort`
- `monolithic_study_invperm`
- `monolithic_study_presence`
- `monolithic_study_committed_presence` (committed-matrix counterpart, for the representation crossover)

### Composite — external glue (Ch. 5)

Each variant is a `*_segment` circuit (one per leg) plus a `*_glue` recombiner the verifier
checks alongside the `K` segment proofs:

- `composite_plain_sort_segment` + `composite_plain_sort_glue` — stitch on plaintext, sort fingerprint.
- `composite_plain_product_segment` + `composite_plain_product_glue` — stitch on plaintext, grand-product fingerprint.
- `composite_committed_sort_segment` + `composite_committed_sort_glue` — stitch on blinded commitments, sort.
- `composite_committed_product_segment` + `composite_committed_product_glue` — stitch on blinded commitments, grand-product.

### Composite — recursive (Ch. 5)

- `composite_recursive` recursively verifies all `composite_plain_product_segment` proofs
  in-circuit and folds the glue logic into one outer proof. Its public surface collapses to
  `{root, threshold}` — the structural-privacy endpoint, equal to the monolithic baseline.

## Name Map (old experimental tree → this export)

| Experimental name | Export name | Thesis variant |
|---|---|---|
| `flat_merkle_sort` | `monolithic_committed_sort` | flat-sort (baseline) |
| `flat_merkle_grand_product` | `monolithic_committed_product` | flat-product |
| `flat_full_*`, `flat_merkle_presence` | `monolithic_study_*` | mechanism study |
| `hierarchical_segment`/`_glue` | `composite_plain_sort_*` | plain-sort |
| `hierarchical_segment_fs`/`_glue_fs` | `composite_plain_product_*` | plain-product |
| `hierarchical_segment_c`/`_glue_c` | `composite_committed_sort_*` | committed-sort |
| `hierarchical_segment_cfs`/`_glue_cfs` | `composite_committed_product_*` | committed-product |
| `recursion` | `composite_recursive` | recursive-product |

The Python harnesses, verifiers, builder mode flags (`--composite-plain-sort`,
`--composite-plain-product`, `--composite-committed-sort`, `--composite-committed-product`), and
the CSV `variant` strings all use the same export names.

## Production Boundary

This export keeps runnable source and tests only. The following stay in the experimental parent
tree: historical benchmark archives; generated CSV/PDF/PNG output; thesis source and figure
drafts; API-exploration scripts; stale design/narrative markdown; Noir/Rust build targets.
