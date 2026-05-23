#!/usr/bin/env bash
# Explore what nargo execute error messages look like for different violations.
# Useful for understanding assertion messages and stderr format before writing
# automated tests that parse them.
#
# Run from the project root with the zk-tsp conda env active.
# Usage:  bash tests/api_exploration/explore_nargo_errors.sh

CIRCUIT_DIR="circuits/flat_full_pairwise"

run_case() {
    local label="$1"
    local toml_content="$2"

    echo ""
    echo "--- $label ---"
    echo "$toml_content" > "$CIRCUIT_DIR/Prover.toml"
    nargo execute 2>&1 --cwd "$CIRCUIT_DIR" || true
}

# Make sure we have N=5 compiled
cd "$CIRCUIT_DIR"
sed -i 's/^global N: u32 = .*/global N: u32 = 5;/' src/main.nr
nargo compile --quiet 2>/dev/null
cd ../..

# Out-of-range node
run_case "cycle[4]=5 (out of range for N=5)" \
'cycle = ["0", "1", "2", "3", "5"]
cost_matrix = ["0","1","1","1","1","1","0","1","1","1","1","1","0","1","1","1","1","1","0","1","1","1","1","1","0"]
threshold = "10"'

# Duplicate node
run_case "cycle=[0,0,2,3,4] (duplicate)" \
'cycle = ["0", "0", "2", "3", "4"]
cost_matrix = ["0","1","1","1","1","1","0","1","1","1","1","1","0","1","1","1","1","1","0","1","1","1","1","1","0"]
threshold = "10"'

# Threshold too tight
run_case "threshold=0 (always fails)" \
'cycle = ["0", "1", "2", "3", "4"]
cost_matrix = ["0","1","1","1","1","1","0","1","1","1","1","1","0","1","1","1","1","1","0","1","1","1","1","1","0"]
threshold = "0"'

echo ""
echo "Done."
