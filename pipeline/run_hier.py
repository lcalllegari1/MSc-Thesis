"""
pipeline/run_hier.py — Variant A hierarchical TSP benchmark harness.

Mirrors pipeline/run.py for the flat circuits.  Differences:
  * Two compiled circuits per (N, K) cell: hierarchical_segment and
    hierarchical_glue.  Patcher handles N + M = N/K + K + DEPTH together.
  * K+1 proofs per run (K sub-proofs + 1 glue), proved in PARALLEL using
    per-segment shadow directories under .runs/sub_i/.  Each shadow contains
    a full copy of the compiled circuit plus its own Prover.toml so
    `nargo execute` and `bb prove` don't race on target/<name>.gz.
  * K+1 CSV rows per (N, K, run), distinguished by a `circuit` column with
    values "sub_0" .. "sub_{K-1}" / "glue".  Downstream analysis aggregates
    these into max(prove_s) for parallel wall-clock projection and sum for
    total CPU work.
  * The verifier cross-check (pipeline/verify_hier.py) runs once per cell to
    confirm the K+1 proofs are mutually consistent.  Not timed as a metric.

For each (N, K) the script:
  1. Patches N, M, K, DEPTH in both .nr files and recompiles + writes VKs.
  2. Sets up K shadow dirs for the sub-circuit (copies of target/ and src/).
  3. For each run, generates an instance, solves a cycle, builds the K+1
     Prover.tomls via the Rust merkle_builder --hierarchical, then launches
     K+1 parallel processes that run `nargo execute && bb prove` in their
     shadow / glue dir.  Each process records its own wall-clock witness_s
     and prove_s (under K+1-way CPU contention).
  4. Runs verify_hier.py against the produced proofs to sanity-check the
     cross-checks.  A row is emitted regardless; the script aborts loudly
     only on outright failure.

Output CSV columns (one row per circuit, K+1 rows per cell):
    variant n k m run circuit circuit_size acir_opcodes compile_s
    witness_s prove_s verify_s proof_bytes peak_mb verify_hier_s xchecks_ok

Usage:
    python pipeline/run_hier.py \\
        --ns 48 96 192 480 \\
        --ks 2 4 8 \\
        --runs 3 \\
        --out results/hier_a.csv
"""

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUB_DIR      = PROJECT_ROOT / "circuits" / "hierarchical_segment"
GLUE_DIR     = PROJECT_ROOT / "circuits" / "hierarchical_glue"
SUB_NAME     = "hierarchical_segment"
GLUE_NAME    = "hierarchical_glue"
BUILDER_BIN  = PROJECT_ROOT / "pipeline" / "merkle_builder" / "target" / "release" / "merkle_builder"
VERIFY_HIER  = PROJECT_ROOT / "pipeline" / "verify_hier.py"

# Per-N-K sub-circuit shadow dirs.  Hosted under /tmp/ rather than
# inside circuits/hierarchical_segment/.runs/ because Nargo walks up looking
# for the outermost Nargo.toml and would otherwise treat .runs/sub_i as a
# sub-project of the parent and write into the parent's target/.
SHADOW_ROOT  = Path("/tmp/hier_a_shadows")

# Pipeline helpers (instance gen + solver).
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))
from instance_gen   import generate_instance
from solver         import solve, cycle_cost
from instance_cache import get_instance_and_cycle


# ── CSV layout ────────────────────────────────────────────────────────────────
FIELDNAMES = [
    "variant",       # always "hier_a"
    "n", "k", "m",   # geometry
    "run",           # 1-based run index for this (n, k)
    "circuit",       # "sub_0".."sub_{K-1}" / "glue"
    "circuit_size",  # UltraHonk gate count for this circuit
    "acir_opcodes",  # ACIR opcode count
    "compile_s",     # nargo compile wall time (per circuit, once per cell)
    "witness_s",     # nargo execute wall time (under K+1-way contention)
    "prove_s",       # bb prove wall time (under K+1-way contention)
    "verify_s",      # bb verify wall time (serial, run once after)
    "proof_bytes",   # size of the proof file
    "peak_mb",       # peak mem during bb prove (from bb stderr)
    "verify_hier_s", # wall time for pipeline/verify_hier.py (same value all K+1 rows)
    "xchecks_ok",    # 1 if verify_hier accepted, else 0
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def merkle_depth(n):
    """ceil(log2(n*n)); 0 for n<=1.  Matches pipeline/format_inputs.py."""
    return (n * n - 1).bit_length() if n * n > 1 else 0


def run_cmd(cmd, cwd=None):
    """Run a subprocess, return (elapsed_seconds, stdout, stderr, returncode)."""
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return time.perf_counter() - t0, r.stdout, r.stderr, r.returncode


def parse_peak_mb(stderr):
    vals = [float(m) for m in re.findall(r"mem: ([\d.]+) MiB", stderr)]
    return max(vals) if vals else float("nan")


def parse_gates(stdout):
    data = json.loads(stdout)
    fn = data["functions"][0]
    return fn["acir_opcodes"], fn["circuit_size"]


def patch_globals(src_path: Path, **values):
    """Patch `global NAME: u32 = NUMBER;` lines for the given globals."""
    text = src_path.read_text()
    for name, value in values.items():
        text = re.sub(
            rf"^global {name}: u32\s*=\s*\d+;",
            f"global {name}: u32 = {value};",
            text, flags=re.MULTILINE,
        )
    src_path.write_text(text)


def configure_circuits(n, k):
    """Patch + compile both circuits for (N, K).  Returns metadata dict."""
    if n % k != 0:
        raise ValueError(f"N={n} must be divisible by K={k}")
    m     = n // k
    depth = merkle_depth(n)
    patch_globals(SUB_DIR  / "src" / "main.nr", N=n, M=m, DEPTH=depth)
    patch_globals(GLUE_DIR / "src" / "main.nr", N=n, K=k, DEPTH=depth)

    meta = {"n": n, "k": k, "m": m, "depth": depth, "compile_s": {}, "gates": {}}
    for cdir, cname in [(SUB_DIR, SUB_NAME), (GLUE_DIR, GLUE_NAME)]:
        compile_s, _, err, rc = run_cmd(["nargo", "compile"], cwd=cdir)
        if rc != 0:
            raise RuntimeError(f"nargo compile failed in {cdir}:\n{err}")
        meta["compile_s"][cname] = compile_s
        _, _, _, _ = run_cmd(
            ["bb", "write_vk", "-b", f"target/{cname}.json", "-o", "target/vk"],
            cwd=cdir,
        )
        _, gates_out, _, _ = run_cmd(
            ["bb", "gates", "-b", f"target/{cname}.json"], cwd=cdir
        )
        meta["gates"][cname] = parse_gates(gates_out)
    return meta


def make_shadow_dirs(k):
    """
    Create K shadow dirs under SUB_DIR/.runs/sub_i, each a self-contained
    copy of the compiled sub-circuit so K parallel nargo execute / bb prove
    invocations don't race on shared target/<name>.gz.
    """
    if SHADOW_ROOT.exists():
        shutil.rmtree(SHADOW_ROOT)
    SHADOW_ROOT.mkdir(parents=True)

    for i in range(k):
        sd = SHADOW_ROOT / f"sub_{i}"
        sd.mkdir()
        shutil.copy(SUB_DIR / "Nargo.toml", sd / "Nargo.toml")
        # Copy src/ and re-compile inside the shadow.  The compiled
        # target/<name>.json embeds absolute paths to source files (via its
        # debug file_map); reusing the main dir's .json would make nargo
        # write target/<name>.gz back to the main dir on `nargo execute`,
        # causing K parallel workers to race on a single output path.
        # Re-compiling makes each shadow a self-contained nargo project.
        shutil.copytree(SUB_DIR / "src", sd / "src")
        _, _, err, rc = run_cmd(["nargo", "compile"], cwd=sd)
        if rc != 0:
            raise RuntimeError(f"nargo compile failed in shadow {sd}:\n{err}")
        # Copy the main VK (derived from bytecode, identical across shadows
        # since the source is identical) into the shadow's target/vk.
        (sd / "target" / "vk").mkdir(parents=True, exist_ok=True)
        for vk_file in ("vk", "vk_hash"):
            src = SUB_DIR / "target" / "vk" / vk_file
            if src.exists():
                shutil.copy(src, sd / "target" / "vk" / vk_file)


def write_inputs_json(n, k, instance, cycle, multiplier=1.1):
    """Build the JSON payload for merkle_builder --hierarchical."""
    matrix = instance["matrix"]
    flat = [matrix[i][j] for i in range(n) for j in range(n)]
    cost = cycle_cost(matrix, cycle)
    return {
        "n": n, "k": k, "flat_matrix": flat,
        "cycle": cycle, "cost": cost,
        "threshold": math.ceil(cost * multiplier),
    }


def build_hier_tomls(payload_dict, k, out_dir, tree_cache=None):
    """Invoke merkle_builder --hierarchical K --out-dir <dir>."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    payload = json.dumps(payload_dict)
    cmd = [str(BUILDER_BIN), "--hierarchical", str(k), "--out-dir", str(out_dir)]
    if tree_cache is not None:
        cmd += ["--tree-cache", str(tree_cache)]
    r = subprocess.run(
        cmd, input=payload, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"merkle_builder failed:\n{r.stderr}")


# ── Parallel prove driver ─────────────────────────────────────────────────────
# Each worker runs `nargo execute && bb prove` in its own dir and writes timing
# info to a sidecar JSON.  All K+1 workers launch in parallel; the main thread
# waits for all then collects metrics.

WORKER_SCRIPT = r'''
import json, os, subprocess, sys, time

cwd       = sys.argv[1]
name      = sys.argv[2]
proof_out = sys.argv[3]
meta_out  = sys.argv[4]

t0 = time.perf_counter()
r = subprocess.run(["nargo", "execute"], cwd=cwd, capture_output=True, text=True)
witness_s = time.perf_counter() - t0
if r.returncode != 0:
    json.dump({"witness_s": witness_s, "prove_s": float("nan"),
               "peak_mb": float("nan"), "ok": False,
               "stage": "witness", "err": r.stderr},
              open(meta_out, "w"))
    sys.exit(0)

t0 = time.perf_counter()
r = subprocess.run(
    ["bb", "prove",
     "-b", f"target/{name}.json",
     "-w", f"target/{name}.gz",
     "-k", "target/vk/vk",
     "-o", proof_out],
    cwd=cwd, capture_output=True, text=True,
)
prove_s = time.perf_counter() - t0
peak_mb = float("nan")
import re
vals = [float(m) for m in re.findall(r"mem: ([\d.]+) MiB", r.stderr)]
if vals:
    peak_mb = max(vals)
json.dump({"witness_s": witness_s, "prove_s": prove_s, "peak_mb": peak_mb,
           "ok": r.returncode == 0, "stage": "done",
           "err": r.stderr if r.returncode != 0 else ""},
          open(meta_out, "w"))
'''


def spawn_worker(cwd, circuit_name, proof_dir, meta_path):
    """Spawn a Popen running WORKER_SCRIPT.  Returns the Popen handle."""
    return subprocess.Popen(
        ["python3", "-c", WORKER_SCRIPT,
         str(cwd), circuit_name, str(proof_dir), str(meta_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def parallel_prove_all(k, hier_dir, scratch, isolated=False):
    """
    Launch K+1 `nargo execute && bb prove` workers and collect metrics.

    isolated=False (default): workers run CONCURRENTLY (one-machine contention;
    matches results/*_par.csv).  isolated=True: workers run SEQUENTIALLY (each alone),
    so each prover's witness_s/prove_s is its solo time -- the per-node time in the
    distributed model.  See ISOLATION_BENCHMARK.md.

    Returns a list of K+1 dicts:  [{circuit, witness_s, prove_s, peak_mb, ok, ...}].
    """
    results = []
    procs   = []
    meta_paths = []

    def launch(cwd, name, proof_dir, meta_path):
        p = spawn_worker(cwd, name, proof_dir, meta_path)
        if isolated:
            p.wait()          # finish this prover before the next starts (solo timing)
        return p

    wall_t0 = time.perf_counter()

    # ── Sub-circuit workers (K of them) ──────────────────────────────────────
    for i in range(k):
        shadow = SHADOW_ROOT / f"sub_{i}"
        shutil.copy(hier_dir / f"sub_{i}" / "Prover.toml", shadow / "Prover.toml")
        proof_dir = scratch / f"sub_{i}"
        proof_dir.mkdir(parents=True, exist_ok=True)
        meta_path = scratch / f"sub_{i}.meta.json"
        procs.append(launch(shadow, SUB_NAME, proof_dir, meta_path))
        meta_paths.append((f"sub_{i}", meta_path, proof_dir))

    # ── Glue worker (1) ──────────────────────────────────────────────────────
    shutil.copy(hier_dir / "glue" / "Prover.toml", GLUE_DIR / "Prover.toml")
    glue_proof = scratch / "glue"
    glue_proof.mkdir(parents=True, exist_ok=True)
    glue_meta  = scratch / "glue.meta.json"
    procs.append(launch(GLUE_DIR, GLUE_NAME, glue_proof, glue_meta))
    meta_paths.append(("glue", glue_meta, glue_proof))

    # ── Wait for all (no-op for already-finished isolated workers) ───────────
    for p in procs:
        p.wait()
    wall_total = time.perf_counter() - wall_t0

    # ── Collect ──────────────────────────────────────────────────────────────
    for circuit, meta_path, proof_dir in meta_paths:
        try:
            meta = json.loads(meta_path.read_text())
        except Exception as e:
            meta = {"ok": False, "witness_s": float("nan"), "prove_s": float("nan"),
                    "peak_mb": float("nan"), "err": f"meta parse: {e}"}
        proof_path = proof_dir / "proof"
        meta["circuit"] = circuit
        meta["proof_bytes"] = proof_path.stat().st_size if proof_path.exists() else 0
        results.append(meta)
    results.append({"_wall_total_s": wall_total})
    return results


def run_verify_hier(scratch, n, k):
    """Run pipeline/verify_hier.py against scratch/.  Returns (rc, elapsed)."""
    cmd = [
        "python3", str(VERIFY_HIER),
        "--proof-dir", str(scratch),
        "--n", str(n), "--k", str(k),
        "--sub-vk",  str(SUB_DIR  / "target" / "vk" / "vk"),
        "--glue-vk", str(GLUE_DIR / "target" / "vk" / "vk"),
    ]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, (time.perf_counter() - t0)


def measure_verify_s(scratch, circuit, k):
    """Measure a serial `bb verify` for the given circuit.  Returns elapsed seconds."""
    if circuit == "glue":
        cdir, cname = GLUE_DIR, GLUE_NAME
        proof_dir = scratch / "glue"
    else:
        # circuit = "sub_<i>"
        i = int(circuit.split("_")[1])
        cdir  = SHADOW_ROOT / f"sub_{i}"
        cname = SUB_NAME
        proof_dir = scratch / circuit
    elapsed, _, _, _ = run_cmd(
        ["bb", "verify",
         "-k", "target/vk/vk",
         "-p", str(proof_dir / "proof"),
         "-i", str(proof_dir / "public_inputs")],
        cwd=cdir,
    )
    return elapsed


# ── Main benchmark loop ───────────────────────────────────────────────────────

def benchmark(ns, ks, runs, out_csv, seed, isolated=False):
    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_csv.exists()
    variant_tag = "hier_a" + ("_iso" if isolated else "")

    with open(out_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()

        for n in ns:
            # One canonical instance per N, shared across all K and all runs
            # (the Merkle tree is over the N*N matrix, independent of the
            # partition).  tree_cache is reused by every merkle_builder call.
            instance, cycle, tree_cache = get_instance_and_cycle(n, seed)

            for k in ks:
                if n % k != 0:
                    print(f"\n[N={n} K={k}] SKIP (N not divisible by K)")
                    continue
                m = n // k

                print(f"\n[N={n} K={k} M={m}] patching, compiling, writing VKs ...")
                meta = configure_circuits(n, k)
                sub_acir, sub_circuit_size   = meta["gates"][SUB_NAME]
                glue_acir, glue_circuit_size = meta["gates"][GLUE_NAME]
                print(f"  sub:  acir={sub_acir}, circuit_size={sub_circuit_size}, "
                      f"compile={meta['compile_s'][SUB_NAME]:.2f}s")
                print(f"  glue: acir={glue_acir}, circuit_size={glue_circuit_size}, "
                      f"compile={meta['compile_s'][GLUE_NAME]:.2f}s")

                make_shadow_dirs(k)

                payload = write_inputs_json(n, k, instance, cycle)

                for run_idx in range(1, runs + 1):
                    print(f"  run {run_idx}/{runs} ...", end=" ", flush=True)

                    cell_dir  = Path(f"/tmp/run_hier/n{n}_k{k}/run{run_idx}")
                    if cell_dir.exists():
                        shutil.rmtree(cell_dir)
                    hier_dir  = cell_dir / "tomls"
                    scratch   = cell_dir / "proofs"
                    build_hier_tomls(payload, k, hier_dir, tree_cache)

                    res = parallel_prove_all(k, hier_dir, scratch, isolated)
                    wall_total = res.pop()["_wall_total_s"]

                    # All proves OK?
                    if any(not r["ok"] for r in res):
                        fails = [(r["circuit"], r.get("err", "")[:200]) for r in res if not r["ok"]]
                        print(f"FAILED proves: {fails}")
                        continue

                    # Serial bb verify per circuit + verify_hier cross-checks.
                    verify_s_per = {}
                    for r in res:
                        verify_s_per[r["circuit"]] = measure_verify_s(scratch, r["circuit"], k)
                    vh_rc, vh_s = run_verify_hier(scratch, n, k)
                    xcheck_ok = 1 if vh_rc == 0 else 0

                    # Emit K+1 rows.
                    for r in res:
                        circuit = r["circuit"]
                        is_glue = (circuit == "glue")
                        writer.writerow({
                            "variant":      variant_tag,
                            "n":            n, "k": k, "m": m,
                            "run":          run_idx,
                            "circuit":      circuit,
                            "circuit_size": glue_circuit_size if is_glue else sub_circuit_size,
                            "acir_opcodes": glue_acir          if is_glue else sub_acir,
                            "compile_s":    round(meta["compile_s"][GLUE_NAME if is_glue else SUB_NAME], 4),
                            "witness_s":    round(r["witness_s"], 4),
                            "prove_s":      round(r["prove_s"],   4),
                            "verify_s":     round(verify_s_per[circuit], 4),
                            "proof_bytes":  r["proof_bytes"],
                            "peak_mb":      round(r["peak_mb"], 3),
                            "verify_hier_s":round(vh_s, 4),
                            "xchecks_ok":   xcheck_ok,
                        })
                    f.flush()

                    prove_max = max(r["prove_s"] for r in res)
                    prove_sum = sum(r["prove_s"] for r in res)
                    print(
                        f"wall_total={wall_total:.2f}s  "
                        f"max(prove)={prove_max:.2f}s  sum(prove)={prove_sum:.2f}s  "
                        f"verify_hier={'OK' if xcheck_ok else 'FAIL'}({vh_s:.2f}s)"
                    )

    print(f"\nDone. Results written to {out_csv}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Variant A hierarchical TSP benchmark sweep.")
    ap.add_argument("--ns", nargs="+", type=int, required=True,
                    help="N values to sweep, e.g. --ns 48 96 192 480")
    ap.add_argument("--ks", nargs="+", type=int, required=True,
                    help="K values to sweep, e.g. --ks 2 4 8")
    ap.add_argument("--runs", type=int, default=3,
                    help="Runs per (N, K) cell (default: 3)")
    ap.add_argument("--out", required=True,
                    help="Output CSV path, e.g. results/hier_a.csv")
    ap.add_argument("--seed", type=int, default=42,
                    help="Base seed; per-run seed = seed + N*1000 + K*100 + run (default: 42)")
    ap.add_argument("--isolated", action="store_true",
                    help="Run the K+1 provers SEQUENTIALLY (each alone) for solo timing "
                         "instead of concurrently; tags the variant '<base>_iso'. "
                         "Use on an idle machine to measure the K* speedup (see "
                         "ISOLATION_BENCHMARK.md).")
    args = ap.parse_args()

    if not BUILDER_BIN.exists():
        print(f"ERROR: merkle_builder not built.  Run:")
        print(f"  cargo build --release --manifest-path pipeline/merkle_builder/Cargo.toml")
        sys.exit(1)

    benchmark(args.ns, args.ks, args.runs, args.out, args.seed, args.isolated)


if __name__ == "__main__":
    main()
