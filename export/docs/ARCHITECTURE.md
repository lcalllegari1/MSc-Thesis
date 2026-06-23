# Architecture

The project measures several ways to prove a Hamiltonian cycle bound for a generated TSP instance. Each benchmark cell patches compile-time Noir globals, creates a witness, proves it with `bb`, verifies it, and records timing/size/memory metrics.

## Data Flow

1. `pipeline/instance_gen.py` creates a deterministic Euclidean TSP instance.
2. `pipeline/solver.py` builds a valid Hamiltonian cycle with nearest-neighbour plus bounded 2-opt.
3. `pipeline/format_inputs.py` or `pipeline/merkle_builder` writes `Prover.toml` witness/public input files.
4. `nargo compile` and `nargo execute` build the circuit and witness.
5. `bb prove`, `bb verify`, and verifier helper scripts produce and check proofs.
6. Aggregators and plotters turn raw CSVs into comparison tables and figures.

Large deterministic instance artifacts are cached under `data/instances/` by `pipeline/instance_cache.py`; that cache is generated locally and ignored.

## Circuit Families

Flat baselines:

- `flat_full_pairwise`
- `flat_full_presence`
- `flat_full_sort`
- `flat_full_invperm`
- `flat_merkle_presence`
- `flat_merkle_sort`
- `flat_merkle_grand_product`

Hierarchical families:

- Variant A: `hierarchical_segment` + `hierarchical_glue`
- Variant A++: `hierarchical_segment_fs` + `hierarchical_glue_fs`
- Committed A: `hierarchical_segment_c` + `hierarchical_glue_c`
- Committed A++: `hierarchical_segment_cfs` + `hierarchical_glue_cfs`

Recursive family:

- `recursion` recursively verifies all `hierarchical_segment_fs` proofs and folds the glue logic into one outer proof.

## Production Boundary

This export keeps runnable source and tests only. The following stay in the experimental parent tree:

- historical benchmark archives
- generated CSV/PDF/PNG output
- thesis source and figure drafts
- API exploration scripts
- stale design/narrative markdown
- Noir/Rust build targets
