# Correctness Tests

`tests/correctness/` contains executable soundness tests for the shipped circuit variants. They build witnesses, run `nargo execute`, and where needed run `bb prove`/`bb verify` to confirm invalid witnesses are rejected at the expected layer.

Run from the export root, with `nargo`, `bb`, Cargo, and the Python dependencies available:

```bash
python3 tests/correctness/test_flat_full_pairwise.py
python3 tests/correctness/test_recursion.py
```

The recursive test is heavier because it builds the Merkle helper, proves inner recursive segments, assembles the outer witness, and checks negative cases against the in-circuit verifier.
