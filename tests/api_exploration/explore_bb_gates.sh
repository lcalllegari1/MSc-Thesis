#!/usr/bin/env bash
# Explore the JSON structure returned by `bb gates`.
# Run from the project root after compiling flat_full_pairwise.
#
# Usage:  bash tests/api_exploration/explore_bb_gates.sh

CIRCUIT_DIR="circuits/flat_full_pairwise"
CIRCUIT_NAME="flat_full_pairwise"

echo "=== Raw bb gates output ==="
bb gates -b "$CIRCUIT_DIR/target/$CIRCUIT_NAME.json"

echo ""
echo "=== Parsed with jq ==="
bb gates -b "$CIRCUIT_DIR/target/$CIRCUIT_NAME.json" | jq '{
  acir_opcodes: .functions[0].acir_opcodes,
  circuit_size: .functions[0].circuit_size
}'
