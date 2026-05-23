# tests/

This folder has two purposes:

---

## 1. `api_exploration/`

Standalone scripts for understanding tools, APIs, and behaviours *before*
committing to a design. Nothing here is part of the main pipeline.

Examples of things that belong here:
- Trying out `nargo` or `bb` command-line flags
- Experimenting with Noir language features (generics, comptime, stdlib)
- Quick Python experiments (msgpack, subprocess patterns, CSV edge cases)
- Throwaway Noir circuits that test a single idea in isolation

Naming convention: `explore_<topic>.py` or a self-contained Noir project
directory under `api_exploration/noir/<topic>/`.

---

## 2. `correctness/`

Tests that verify the circuit rejects every invalid witness it should reject.

A ZKP circuit is only sound if *every possible cheat* is caught as a
constraint violation. `nargo execute` returns a non-zero exit code when any
`assert` fails — we exploit this to drive negative tests.

### What to test

| Case | What it checks |
|---|---|
| Valid cycle | Baseline: a correct witness must always pass |
| Out-of-range node | `cycle[i] >= N` must fail CONSTRAINT GROUP 1 |
| Duplicate node | `cycle[i] == cycle[j]` must fail CONSTRAINT GROUP 2 |
| Wrong cost | Tampered `flat_matrix` values must fail CONSTRAINT GROUP 3/4 |
| Cost above threshold | Correct cycle but `threshold` set too low must fail GROUP 4 |
| Trivial cycle (N=1) | Edge case: single-node cycle must pass |

### How to run

```bash
# From project root, with zk-tsp conda env active:
python tests/correctness/test_flat_full_pairwise.py
```

Each test case:
1. Writes a `Prover.toml` with the tampered inputs.
2. Calls `nargo execute` in the circuit directory.
3. Asserts the return code is 0 (valid) or non-zero (invalid).

A passing test suite means the circuit enforces all four constraint groups.
