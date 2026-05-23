#!/usr/bin/env bash
# Explore Noir array sorting APIs: constrained vs unconstrained, gate costs.
#
# Creates a throwaway Nargo project in /tmp, tries several sort approaches,
# reports whether each compiles, executes, and what the gate count is.
# Cleans up on exit.
#
# Run from the project root with the zk-tsp conda env active.
# Usage:  bash tests/api_exploration/explore_noir_sort.sh

set -euo pipefail

WORK_DIR="/tmp/noir_sort_explore"
N=5

# Prover.toml for a 5-element permutation (cycle = [2,0,4,1,3])
PROVER_TOML='arr = ["2", "0", "4", "1", "3"]'

# ── Helpers ──────────────────────────────────────────────────────────────────

cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

init_project() {
    local name="$1"
    local circuit_src="$2"
    local prover_toml="$3"

    rm -rf "$WORK_DIR"
    mkdir -p "$WORK_DIR/src"

    cat > "$WORK_DIR/Nargo.toml" <<EOF
[package]
name = "$name"
type = "bin"
authors = []

[dependencies]
EOF

    printf '%s\n' "$circuit_src" > "$WORK_DIR/src/main.nr"
    printf '%s\n' "$prover_toml" > "$WORK_DIR/Prover.toml"
}

try_circuit() {
    local label="$1"

    echo ""
    echo "━━━ $label ━━━"

    # Compile
    if ! nargo compile 2>/tmp/noir_sort_compile.err; then
        echo "  COMPILE FAILED:"
        sed 's/^/    /' /tmp/noir_sort_compile.err
        return
    fi
    echo "  compile: OK"

    # Execute (witness generation)
    if ! nargo execute 2>/tmp/noir_sort_exec.err; then
        echo "  EXECUTE FAILED:"
        sed 's/^/    /' /tmp/noir_sort_exec.err
        return
    fi
    echo "  execute: OK"

    # Gate count
    local gates_json
    gates_json=$(bb gates -b "target/${1// /_}.json" 2>/dev/null || true)
    if [ -n "$gates_json" ]; then
        local acir circuit_size
        acir=$(echo "$gates_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['functions'][0]['acir_opcodes'])" 2>/dev/null || echo "?")
        circuit_size=$(echo "$gates_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['functions'][0]['circuit_size'])" 2>/dev/null || echo "?")
        echo "  gates: circuit_size=$circuit_size  acir_opcodes=$acir"
    else
        echo "  gates: (bb gates failed or not applicable)"
    fi
}

# ── Case 1: arr.sort_via() in constrained code ───────────────────────────────
#
# Noir arrays have a sort_via(comparator) method.
# In constrained context this compiles to a sorting network — number of gates
# depends on the Noir version's implementation.

CASE1_NAME="sort_via_constrained"
CASE1_SRC="
global N: u32 = ${N};

fn main(arr: [u32; N]) {
    let sorted = arr.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..N {
        assert(sorted[i] == i as u32, \"sorted != [0..N-1]\");
    }
}
"

init_project "$CASE1_NAME" "$CASE1_SRC" "$PROVER_TOML"
(cd "$WORK_DIR" && try_circuit "$CASE1_NAME")

# ── Case 2: arr.sort() (no comparator) in constrained code ──────────────────
#
# Some Noir versions expose a plain .sort() with default ordering.

CASE2_NAME="sort_default_constrained"
CASE2_SRC="
global N: u32 = ${N};

fn main(arr: [u32; N]) {
    let sorted = arr.sort();
    for i in 0..N {
        assert(sorted[i] == i as u32, \"sorted != [0..N-1]\");
    }
}
"

init_project "$CASE2_NAME" "$CASE2_SRC" "$PROVER_TOML"
(cd "$WORK_DIR" && try_circuit "$CASE2_NAME")

# ── Case 3: sort_via inside an unconstrained function ────────────────────────
#
# unconstrained fn runs during witness generation only — zero circuit gates.
# The sort result is then verified in O(N) constrained assertions.
# This is the approach we want to understand for flat_full_sort.

CASE3_NAME="sort_unconstrained"
CASE3_SRC="
global N: u32 = ${N};

// Runs at witness-generation time only; contributes 0 constrained gates.
unconstrained fn sort_hint(arr: [u32; N]) -> [u32; N] {
    arr.sort_via(|a: u32, b: u32| a <= b)
}

fn main(arr: [u32; N]) {
    // Range check: every entry must be a valid index.
    for i in 0..N {
        assert(arr[i] < N as u32, \"index out of range\");
    }

    // Unconstrained sort: no gates spent here.
    let sorted = unsafe { sort_hint(arr) };

    // Verify sorted is actually sorted: O(N) range comparisons.
    for i in 0..(N - 1) {
        assert(sorted[i] <= sorted[i + 1], \"sorted array is not sorted\");
    }

    // Verify sorted == [0, 1, ..., N-1]: O(N) equality checks.
    // Together with the sortedness check above this proves the multiset
    // {sorted[0],...,sorted[N-1]} = {0,...,N-1} without pairwise comparisons.
    for i in 0..N {
        assert(sorted[i] == i as u32, \"sorted != [0..N-1]\");
    }

    // QUESTION: is this sufficient to prove arr is a permutation of {0..N-1}?
    // We know sorted == [0..N-1].  But we have not yet proven sorted was
    // derived from arr -- a dishonest prover could supply a fake sorted.
    // See Case 4 for the fix.
}
"

init_project "$CASE3_NAME" "$CASE3_SRC" "$PROVER_TOML"
(cd "$WORK_DIR" && try_circuit "$CASE3_NAME")

# ── Case 4: unconstrained sort + constrained inverse-permutation link ─────────
#
# Fixes the soundness gap in Case 3: proves sorted was derived from arr
# by additionally providing the inverse permutation inv_perm, where
# inv_perm[v] = position of value v in arr.
# Constrained verification: arr[inv_perm[v]] == v for all v — O(N) dynamic
# ROM lookups.  This is the candidate approach for flat_full_sort.

CASE4_PROVER='arr = ["2", "0", "4", "1", "3"]
inv_perm = ["1", "3", "0", "4", "2"]'
# inv_perm[0]=1 means arr[1]=0 ✓
# inv_perm[1]=3 means arr[3]=1 ✓
# inv_perm[2]=0 means arr[0]=2 ✓
# inv_perm[3]=4 means arr[4]=3 ✓
# inv_perm[4]=2 means arr[2]=4 ✓

CASE4_NAME="sort_unconstrained_with_inv_perm"
CASE4_SRC="
global N: u32 = ${N};

unconstrained fn sort_hint(arr: [u32; N]) -> [u32; N] {
    arr.sort_via(|a: u32, b: u32| a <= b)
}

fn main(
    arr:      [u32; N],   // the cycle (private)
    inv_perm: [u32; N],   // inv_perm[v] = position of value v in arr (private hint)
) {
    // Range check arr.
    for i in 0..N {
        assert(arr[i] < N as u32, \"arr entry out of range\");
    }

    // Unconstrained sort for a readable check (optional -- could drop this entirely).
    let sorted = unsafe { sort_hint(arr) };

    // Sortedness and equality to [0..N-1] confirm sorted is the target.
    for i in 0..(N - 1) {
        assert(sorted[i] <= sorted[i + 1], \"sorted not in order\");
    }
    for i in 0..N {
        assert(sorted[i] == i as u32, \"sorted != [0..N-1]\");
    }

    // Constrained permutation proof via inverse mapping: O(N) dynamic lookups.
    // For each value v, the prover claims it lives at position inv_perm[v].
    // Soundness: if inv_perm[u] == inv_perm[v] for u != v, then we would need
    // arr[inv_perm[u]] == u AND arr[inv_perm[u]] == v simultaneously -- impossible.
    for v in 0..N {
        assert(inv_perm[v] < N as u32, \"inv_perm entry out of range\");
        let v_u32: u32 = v as u32;
        assert(arr[inv_perm[v]] == v_u32, \"inv_perm does not match arr\");
    }
}
"

init_project "$CASE4_NAME" "$CASE4_SRC" "$CASE4_PROVER"
(cd "$WORK_DIR" && try_circuit "$CASE4_NAME")

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Notes:"
echo "  Case 1/2 — constrained sort: if it compiles, the sort itself costs gates."
echo "  Case 3   — unconstrained sort only: quick, but has soundness gap."
echo "  Case 4   — unconstrained sort + inv_perm: O(N) constrained work, sound."
echo "  Compare circuit_size values to flat_full_pairwise N=5: circuit_size=3108"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
