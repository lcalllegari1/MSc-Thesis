#!/usr/bin/env bash
# tests/hash_compat/run_test.sh
#
# Cross-validates that Rust (bn254_blackbox_solver) and Noir (poseidon library)
# produce identical Poseidon2 outputs on the same inputs, for two sponge shapes:
#   * two-input   Poseidon2::hash([1, 2], 2)        (Merkle / A++ chain step)
#   * single-input Poseidon2::hash([c], 1)          (A++ Fiat-Shamir challenge)
#
# The single-input check is the load-bearing hash for Variant A++; it must pass
# before the A++ circuits are written.
#
# Steps:
#   1. Build and run the Rust binary:
#        - Verifies the known permutation([0,0,0,0]) smoke-test vector
#        - Prints HASH_HEX        for hash([1,2], 2)
#        - Prints SINGLE_IN / HASH_SINGLE_HEX for hash([c], 1)
#        - Natively checks the A++ grand-product partition identity
#   2. Write Prover.toml with both (input, expected) pairs
#   3. Compile and execute the Noir circuit -- asserts both hashes match
#
# Run from project root:
#   bash tests/hash_compat/run_test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUST_DIR="$SCRIPT_DIR/rust"
NOIR_DIR="$SCRIPT_DIR/noir"

echo "=== hash_compat cross-validation ==="

# ── Step 1: build Rust binary ─────────────────────────────────────────────────
echo "[1/3] Building Rust binary (first build fetches git deps, may take a minute)..."
cargo build --release --quiet --manifest-path "$RUST_DIR/Cargo.toml"
RUST_BIN="$RUST_DIR/target/release/hash_compat"

echo "[1/3] Running Rust binary (smoke test + sponge hashes + A++ reference table)..."
# Capture stdout (grep-able key/value lines) and let stderr (the reference table
# + smoke/identity status) stream to the console.
RUST_OUTPUT=$("$RUST_BIN")
echo "$RUST_OUTPUT"

grab() { echo "$RUST_OUTPUT" | grep "^$1:" | awk '{print $2}'; }
HASH_HEX=$(grab "HASH_HEX")
SINGLE_IN=$(grab "SINGLE_IN")
HASH_SINGLE_HEX=$(grab "HASH_SINGLE_HEX")

for v in HASH_HEX SINGLE_IN HASH_SINGLE_HEX; do
    if [ -z "${!v}" ]; then
        echo "ERROR: Rust binary did not print $v"
        exit 1
    fi
done

# ── Step 2: write Prover.toml ─────────────────────────────────────────────────
echo "[2/3] Writing Noir Prover.toml (2-input and single-input expected values)..."
cat > "$NOIR_DIR/Prover.toml" <<EOF
left      = "1"
right     = "2"
expected2 = "0x${HASH_HEX}"
single_in = "0x${SINGLE_IN}"
expected1 = "0x${HASH_SINGLE_HEX}"
EOF

# ── Step 3: compile and execute Noir circuit ──────────────────────────────────
echo "[3/3] Compiling Noir circuit..."
(cd "$NOIR_DIR" && nargo compile)

echo "[3/3] Executing Noir circuit (asserts both hashes == expected)..."
(cd "$NOIR_DIR" && nargo execute)

echo ""
echo "=== PASSED: Rust and Noir Poseidon2 match on [1,2] (in_len=2) and [c] (in_len=1) ==="
