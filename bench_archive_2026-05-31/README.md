# Benchmark archive — 2026-05-31

Snapshot of `results/` and `plots/` as they stood on 2026-05-31, archived to start a
clean benchmarking phase. The top-level `results/` and `plots/` were emptied so fresh
sweeps (now including the **committed-A / committed-A++** variants and the
**`--isolated`** parallelism measurement, ideally run uniformly on one machine) land
in a clean tree.

## What's here
- `results/` — the raw + aggregated CSVs from the flat / A / A++ / recursion phase:
  `500.csv` (flat baseline), `hier_a*.csv`, `hier_fs*.csv`, `recursion_*.csv`,
  `recursion_inner_cmp/`. Still valid data — kept for reference/comparison.
- `plots/` — figures generated from the above (pre-redesign; the thesis frontier
  figure will be regenerated with the new tooling and metrics).

## Note on doc references
Some docs (HOWTO.md, make_frontier examples, etc.) reference paths like
`results/500.csv` or `results/recursion_full_tot.csv`. Those illustrate commands;
re-running the sweeps repopulates the top-level `results/`. To plot against this
archived data directly, point `--csv` / `--include` at
`bench_archive_2026-05-31/results/...`.
