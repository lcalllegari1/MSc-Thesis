# Isolation Benchmark — Measuring the K× Parallelism Claim

*How to turn the hierarchical "K× speedup" from a **projection** into a
**measurement**. This is the one open empirical gap flagged as objection O12
(`MOTIVATION_AND_OBJECTIONS.md`) and in `SUPERVISOR_CALL_SUMMARY.md` §6. Read this
before final submission. Captured 2026-05-31.*

---

## 1. The problem (why the current numbers are a projection)

The hierarchical variants claim that decomposing into K segments gives a ~K×
**wall-clock** speedup over flat, under a **distributed model**: one prover node per
segment, each proving an M = N/K-node sub-circuit (~1/K the gates of flat).

But the benchmark harnesses (`run_hier_*.py`) launch the **K+1 provers concurrently
on one machine**. `bb prove` is multi-threaded and already saturates the cores, so
K+1 of them **contend** for CPU and memory bandwidth. Therefore:

- `results/*_par.csv` (aggregator `--mode parallel`, the max over provers) records
  per-prover times **measured under contention** — inflated, *not* the isolated
  per-node time.
- The headline "K×" is currently **estimated from circuit-size ratios** (sub ≈ flat/K
  gates ⇒ time ≈ flat/K), not measured.

**What is already valid (do not re-measure):** `peak_mb` is *per-process*, so
contention does not inflate it (barring swap). The ~1/K **memory** drop is a genuine
measurement. The confound is purely about **time**.

The isolation benchmark removes the confound by timing each prover **alone**, with
the machine otherwise idle — which is exactly the per-node time in the distributed
model (each node gets a full machine = all cores, which is what a solo `bb prove`
uses here).

---

## 2. The reasoning (what to measure and the critical path)

You only need **three solo measurements** per (N, K) cell — not K+1 — because the K
segment sub-circuits are **identical** (same M, same gate count; only the witness
differs, which does not change prove time materially):

- `T_flat`  — flat_merkle_presence proving N nodes monolithically.
- `T_sub`   — one hierarchical segment proving M = N/K nodes.
- `T_glue`  — the glue proving the K-segment binding.

**Distributed wall-clock.** Two deployment models, both worth reporting:

- **(a) K+1 nodes — glue concurrent with the segments.** The glue circuit's inputs
  are derived from the *instance* (endpoints, P_i, boundary costs …), **not** from
  the segment *proofs* — the cross-check binds them only afterward. So the glue can
  prove in parallel with the segments on a (K+1)-th node:
  `T_dist = max(T_sub, T_glue)`  →  `speedup = T_flat / max(T_sub, T_glue)`.
  Since `T_glue < T_sub` at the thesis sizes, this is ≈ `T_flat / T_sub ≈ K`.
- **(b) K nodes — glue runs after the segments free a node:**
  `T_dist = T_sub + T_glue`  →  `speedup = T_flat / (T_sub + T_glue)`.

Report (a) as the headline (it is what the aggregator's `--mode parallel` max
models) and (b) as the conservative bound. Include witness-generation time
(`nargo execute`) in each term if you want end-to-end, but `bb prove` dominates.

**Key subtlety to state in the thesis:** this measures *compute* isolation. A real
distributed system adds network/coordination/dispatch overhead, which is out of
scope; the isolation benchmark is the *upper bound* on the achievable speedup, and
should be labelled as such (compute-only, single core-count class).

---

## 3. The protocol (clean measurement hygiene)

1. **Idle machine.** No other heavy processes; close browsers/IDEs. One prover at a
   time (the recipe below runs them sequentially, never concurrently).
2. **Warm-up + repeats.** Discard the first run (cold caches); take **median of R ≥ 5**.
3. **Same core-count class.** `bb` uses all cores by default — that defines your
   "node." State the machine's core count in the report. To *simulate* smaller nodes,
   pin with `taskset -c 0-3 bb prove …`; keep it consistent across flat/sub/glue.
4. **Same instance per cell** (seed fixed) so flat/sub/glue describe the same N-node
   problem.
5. **Sweep the cells you need** — the claim is methodological, so a few cells
   (e.g. N ∈ {192, 480}, K ∈ {2, 4, 8}) on one or two variants (A++ and/or
   committed-A++) suffice to validate it; you need not isolate every variant.

---

## 4. The runnable recipe (verified commands)

Paste this, set the four parameters at the top. It patches the circuit globals,
compiles flat + the chosen variant's sub + glue, builds one instance's Prover.toml's,
and reports the median solo `bb prove` time for flat, sub, and glue. (It leaves the
circuit globals patched to (N,K); the harnesses re-patch on their next run, so that
is harmless — or `git checkout circuits/.../src/main.nr` to restore.)

```bash
#!/usr/bin/env bash
set -euo pipefail
# ── parameters ──────────────────────────────────────────────────────────────
N=480; K=4; VARIANT=hier_fs; RUNS=5          # VARIANT ∈ hier_a|hier_fs|hier_c|hier_cfs
ROOT=/home/callexyz/Desktop/plsgod
PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python      # needs numpy (instance gen)
BIN=$ROOT/pipeline/merkle_builder/target/release/merkle_builder

# ── variant -> circuit dirs + builder flag ──────────────────────────────────
case $VARIANT in
  hier_a)   SUB=hierarchical_segment;     GLUE=hierarchical_glue;     FLAG=--hierarchical ;;
  hier_fs)  SUB=hierarchical_segment_fs;  GLUE=hierarchical_glue_fs;  FLAG=--hierarchical-fs ;;
  hier_c)   SUB=hierarchical_segment_c;   GLUE=hierarchical_glue_c;   FLAG=--hierarchical-c ;;
  hier_cfs) SUB=hierarchical_segment_cfs; GLUE=hierarchical_glue_cfs; FLAG=--hierarchical-cfs ;;
  *) echo "unknown VARIANT $VARIANT"; exit 1 ;;
esac
M=$((N/K)); DEPTH=$(python3 -c "print((($N*$N)-1).bit_length())")

# ── patch globals + compile + write VKs (sub, glue, flat) ───────────────────
# (patching a global the circuit doesn't have -- e.g. M in the fs/a glue -- is a no-op)
patch(){ sed -i -E "s/^global $1: u32 = [0-9]+;/global $1: u32 = $2;/" "$3"; }
patch N $N $ROOT/circuits/$SUB/src/main.nr;  patch M $M $ROOT/circuits/$SUB/src/main.nr;  patch DEPTH $DEPTH $ROOT/circuits/$SUB/src/main.nr
patch N $N $ROOT/circuits/$GLUE/src/main.nr; patch K $K $ROOT/circuits/$GLUE/src/main.nr; patch M $M $ROOT/circuits/$GLUE/src/main.nr; patch DEPTH $DEPTH $ROOT/circuits/$GLUE/src/main.nr
patch N $N $ROOT/circuits/flat_merkle_presence/src/main.nr; patch DEPTH $DEPTH $ROOT/circuits/flat_merkle_presence/src/main.nr
for C in $SUB $GLUE flat_merkle_presence; do
  ( cd $ROOT/circuits/$C && nargo compile >/dev/null 2>&1 \
       && bb write_vk -b target/$C.json -o target/vk >/dev/null 2>&1 )
done

# ── generate one instance + Prover.toml's (hier K+1, and flat) ──────────────
$PY - "$N" "$K" > /tmp/iso_payload.json <<'PYEOF'
import json, math, sys
sys.path.insert(0, "/home/callexyz/Desktop/plsgod/pipeline")
from instance_gen import generate_instance
from solver import solve, cycle_cost
n, k = int(sys.argv[1]), int(sys.argv[2])
inst = generate_instance(n, seed=42); cyc = solve(inst["matrix"]); m = inst["matrix"]
flat = [m[i][j] for i in range(n) for j in range(n)]; cost = cycle_cost(m, cyc)
json.dump({"n": n, "k": k, "flat_matrix": flat, "cycle": cyc,
           "cost": cost, "threshold": math.ceil(cost * 1.1)}, sys.stdout)
PYEOF
$BIN $FLAG $K --out-dir /tmp/iso_hier < /tmp/iso_payload.json
mkdir -p /tmp/iso_flat && $BIN --out /tmp/iso_flat/Prover.toml < /tmp/iso_payload.json

# ── solo timing: median of RUNS bb-prove wall times (machine idle) ──────────
solo(){  # $1=circuit dir/name  $2=Prover.toml
  cp "$2" "$ROOT/circuits/$1/Prover.toml"
  ( cd "$ROOT/circuits/$1" && nargo execute >/dev/null 2>&1 )
  for r in $(seq 1 $RUNS); do
    t0=$(date +%s.%N)
    ( cd "$ROOT/circuits/$1" && bb prove -b target/$1.json -w target/$1.gz \
         -k target/vk/vk -o /tmp/iso_proof >/dev/null 2>&1 )
    t1=$(date +%s.%N); awk "BEGIN{print $t1-$t0}"
  done | sort -n | awk '{a[NR]=$1} END{print a[int((NR+2)/2)]}'   # median (drops to upper-mid)
}
T_SUB=$(solo $SUB  /tmp/iso_hier/sub_0/Prover.toml)
T_GLUE=$(solo $GLUE /tmp/iso_hier/glue/Prover.toml)
T_FLAT=$(solo flat_merkle_presence /tmp/iso_flat/Prover.toml)

echo "── isolation result (N=$N K=$K variant=$VARIANT, median of $RUNS) ──"
echo "T_flat=$T_FLAT s   T_sub=$T_SUB s   T_glue=$T_GLUE s"
awk "BEGIN{md=($T_SUB>$T_GLUE)?$T_SUB:$T_GLUE;
  printf \"(a) K+1 nodes (glue concurrent): T_dist=%.3f s, speedup=%.2fx\n\", md, $T_FLAT/md;
  printf \"(b) K nodes  (glue after):       T_dist=%.3f s, speedup=%.2fx\n\", $T_SUB+$T_GLUE, $T_FLAT/($T_SUB+$T_GLUE)}"
```

> Note: drop the first of `RUNS` (cold cache) by setting `RUNS=6` and reading the
> median of the last 5, or simply use a larger `RUNS`; the `awk` median is robust to
> one cold outlier.

---

## 5. Reporting

Record, per cell, into a small `results/isolation.csv`
(`variant, n, k, runs, t_flat_s, t_sub_s, t_glue_s, speedup_a, speedup_b, cores, machine`),
then in the thesis present **speedup vs K** (one line per variant) against the ideal
`speedup = K` reference. The headline sentence becomes measured, not projected:

> "On a C-core machine, isolated proving gives a measured X.X× wall-clock speedup at
> K=4 (ideal 4×), with the gap attributable to the glue and to sub-linear prover
> scaling."

**Tie-in to the existing pipeline:** an isolated run feeds the *same* downstream
tooling. If you produce per-prover **solo** times in the run-harness CSV schema,
`aggregate_hier.py --mode parallel` (max over provers) computes exactly model (a),
and `--mode total` the serial bound — so the frontier figure can use measured
parallel numbers with no plotting changes.

---

## 6. Threats to validity (state these honestly)

- **Compute-only.** Ignores network/coordination/dispatch of a real distributed
  system → this is an *upper bound* on the speedup.
- **One core-count class.** The speedup is relative to nodes with this machine's core
  count; a different class shifts it. State the core count.
- **`bb` threading.** A solo `bb prove` may not scale linearly with cores, so
  `T_sub` is not exactly `T_flat/K` even in isolation — which is precisely why this
  must be *measured*, and is itself a finding (sub-linear prover scaling).
- **Single instance per cell.** Prove time is witness-independent for fixed size, so
  one instance suffices; still, average a couple of seeds if you want error bars.

---

## 7. Optional convenience (not yet built)

A clean future addition: an `--isolated` flag on the `run_hier_*.py` harnesses that
runs the K+1 provers **sequentially** (each timed alone) and tags the CSV variant
(e.g. `hier_fs_iso`). Then the whole existing aggregate → plot → `make_frontier`
chain produces measured parallel numbers automatically. The recipe above is the
manual equivalent and is sufficient to close objection O12; the flag is purely a
UX upgrade. (Ask if you want it implemented.)

*Related: `MOTIVATION_AND_OBJECTIONS.md` O12, `FIGURES_AND_METRICS.md` (speedup &
memory-reduction derived metrics), `HOWTO.md` (benchmarking), `SUPERVISOR_CALL_SUMMARY.md`
§3.2/§6, `thesis_guidelines_and_per_prover_parallel_mem_explained.md`.*
