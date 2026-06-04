"""
pipeline/instance_cache.py -- one canonical TSP instance per problem size.

Every benchmark harness needs the same three artifacts for a given size N:
the instance (matrix + coordinates), a solved Hamiltonian cycle, and the
Poseidon2 Merkle tree over the N*N cost matrix.  All three are pure functions of
(N, seed), yet each harness used to regenerate them from scratch -- once per
variant (flat / A / A++ / committed / recursion), per K, per run.  At N>2000 the
tree build alone (O(N^2) Poseidon2 hashes, inside merkle_builder) dominates.

This module makes (N, seed) the cache key and persists the artifacts under
`data/instances/n{N}_seed{S}/`:

    instance.json   generate_instance(N, seed): metadata + nodes + matrix
    cycle.json      solver output: {cycle, cost}
    meta.json       cache-validity tag (version, N, seed, grid, precision, solver)
    tree.bin        the serialised Merkle tree -- written/validated by the Rust
                    merkle_builder via its --tree-cache flag (NOT this module)

`get_instance_and_cycle(n, seed)` returns the instance dict, the cycle, and the
path to hand to `merkle_builder --tree-cache`.  On a hit it loads instance.json
and cycle.json; on a miss (or a stale meta) it regenerates and persists both.

MEASUREMENT NOTE.  The harnesses now reuse ONE instance per N across all runs
and all variants (unified seed).  This is sound because SNARK proving is
data-oblivious: for a fixed circuit the gate count, proof size and peak memory
are independent of the witness values, and prove/verify times vary only with
system noise -- so repeated runs on the same instance measure exactly that
noise.  Instance *diversity* belongs in tests/correctness/, not the benchmark.

Bump CACHE_VERSION (or SOLVER_TAG) whenever instance_gen or solver semantics
change, so stale caches are rejected rather than silently reused.
"""

import json
import math
import os
import time
from pathlib import Path

from instance_gen import generate_instance
from solver import solve, cycle_cost

# ── Cache identity ────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = PROJECT_ROOT / "data" / "instances"

CACHE_VERSION = 1
# Captures the solver behavior that determines the cached cycle.  solver.solve
# runs nearest-neighbour, then 2-opt only for N <= two_opt_max_n (default 1000).
SOLVER_TAG = "nn+2opt<=1000/v1"


def cache_dir(n, seed):
    """Per-(N, seed) cache directory under data/instances/."""
    return CACHE_ROOT / f"n{n}_seed{seed}"


def tree_cache_path(n, seed):
    """Path to hand to `merkle_builder --tree-cache` for this instance."""
    return cache_dir(n, seed) / "tree.bin"


def _atomic_write_json(path: Path, obj):
    """Write JSON to a temp file then rename -- safe under parallel harnesses."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _expected_meta(n, seed, instance):
    md = instance["metadata"]
    return {
        "cache_version": CACHE_VERSION,
        "n": n,
        "seed": seed,
        "grid_size": md["grid_size"],
        "precision": md["precision"],
        "solver_tag": SOLVER_TAG,
    }


def _meta_is_valid(d: Path, n, seed):
    """True iff a complete, current cache entry exists at `d`."""
    meta_p, inst_p, cyc_p = d / "meta.json", d / "instance.json", d / "cycle.json"
    if not (meta_p.exists() and inst_p.exists() and cyc_p.exists()):
        return False
    try:
        meta = json.loads(meta_p.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        meta.get("cache_version") == CACHE_VERSION
        and meta.get("n") == n
        and meta.get("seed") == seed
        and meta.get("solver_tag") == SOLVER_TAG
    )


def get_instance_and_cycle(n, seed=42):
    """Return (instance, cycle, tree_cache_path) for the canonical (N, seed) instance.

    Loads from data/instances/n{N}_seed{S}/ when a valid cache exists; otherwise
    generates the instance + cycle, persists them (plus meta.json), and returns.
    The returned tree_cache_path is where merkle_builder will build-or-load the
    Merkle tree; this function does NOT touch tree.bin itself.
    """
    d = cache_dir(n, seed)
    rel = d.relative_to(PROJECT_ROOT)

    if _meta_is_valid(d, n, seed):
        instance = json.loads((d / "instance.json").read_text())
        cycle = json.loads((d / "cycle.json").read_text())["cycle"]
        print(f"  instance: cache HIT  read from {rel}/")
        return instance, cycle, tree_cache_path(n, seed)

    # Miss (or stale): regenerate deterministically and persist.
    t0 = time.perf_counter()
    instance = generate_instance(n, seed=seed)
    cycle = solve(instance["matrix"])
    cost = cycle_cost(instance["matrix"], cycle)

    _atomic_write_json(d / "instance.json", instance)
    _atomic_write_json(d / "cycle.json", {"cycle": cycle, "cost": cost})
    _atomic_write_json(d / "meta.json", _expected_meta(n, seed, instance))

    print(f"  instance: cache MISS generated + solved in "
          f"{time.perf_counter() - t0:.2f}s, wrote {rel}/")
    return instance, cycle, tree_cache_path(n, seed)


def threshold_for(cost, multiplier=1.1):
    """Cost upper bound used by every variant (kept here so it stays consistent)."""
    return math.ceil(cost * multiplier)
