#!/usr/bin/env bash
# tests/hash_compat/run_test.sh
#
# Cross-validates that Rust (bn254_blackbox_solver) and Noir (poseidon library)
# produce identical Poseidon2 outputs on the same inputs.
#
# Steps:
#   1. Build and run the Rust binary:
#        - Verifies the known permutation([0,0,0,0]) smoke-test vector
#        - Prints HASH_HEX: <64-char hex> for hash([1,2], 2)
#   2. Write Prover.toml with left=1, right=2, expected=<hash from step 1>
#   3. Compile and execute the Noir circuit -- asserts hash == expected
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

echo "[1/3] Running Rust binary (smoke test + sponge hash)..."
RUST_OUTPUT=$("$RUST_BIN")
echo "$RUST_OUTPUT"

HASH_HEX=$(echo "$RUST_OUTPUT" | grep "^HASH_HEX:" | awk '{print $2}')
if [ -z "$HASH_HEX" ]; then
    echo "ERROR: Rust binary did not print HASH_HEX"
    exit 1
fi

# ── Step 2: write Prover.toml ─────────────────────────────────────────────────
echo "[2/3] Writing Noir Prover.toml with expected = 0x${HASH_HEX}..."
cat > "$NOIR_DIR/Prover.toml" <<EOF
left     = "1"
right    = "2"
expected = "0x${HASH_HEX}"
EOF

# ── Step 3: compile and execute Noir circuit ──────────────────────────────────
echo "[3/3] Compiling Noir circuit..."
(cd "$NOIR_DIR" && nargo compile)

echo "[3/3] Executing Noir circuit (asserts hash == expected)..."
(cd "$NOIR_DIR" && nargo execute)

echo ""
echo "=== PASSED: Rust and Noir Poseidon2 outputs match on [1, 2] ==="
