// =============================================================================
// TSP Hamiltonian Cycle ZKP - Flat / Full Matrix / Presence Check
// =============================================================================
//
// What we prove:
//   "I know a Hamiltonian cycle on a complete weighted graph G of N nodes
//    with total edge cost <= threshold T."
//
// Public inputs (the verifier knows these):
//   cost_matrix  - the N*N edge weight table, flattened row-major
//   threshold    - the declared upper bound on cycle cost
//
// Private witness (only the prover knows this):
//   cycle        - the ordered sequence of N node indices that form the cycle.
//                  The closing edge is implicit: cycle[N-1] -> cycle[0].
//
// Design choice - "Flat-Full":
//   Identical to flat_full_pairwise. The entire cost matrix is passed as
//   public input. See that variant for the rationale and the trade-off
//   against the Merkle commitment approach.
//
// Design choice - "Presence" permutation check:
//   The circuit maintains a mutable boolean mark array `seen` of length N,
//   initialised to all-false. For each position i in the cycle:
//     1. assert(cycle[i] < N)              -- range check (GROUP 1)
//     2. assert(seen[cycle[i]] == false)   -- node not yet visited (GROUP 2)
//     3. seen[cycle[i]] = true             -- mark node as visited
//
//   If every presence check passes, no two positions in cycle share the same
//   node value. Combined with the range check, the N distinct values in
//   [0, N-1] must be exactly {0, ..., N-1}: cycle is a permutation.
//
//   Memory model: `seen` is a mutable array indexed by a runtime value.
//   In Barretenberg UltraHonk, this compiles to a RAM table (read-write
//   memory) rather than a ROM (read-only memory). Each RAM access is
//   verified via a timestamp-based consistency argument that enforces
//   the sequential semantics of the loop.
//
//   The initialisation `[false; N]` sets the N initial RAM entries to zero;
//   this is part of the circuit structure (constant, not witness-supplied),
//   so a cheating prover cannot pre-set `seen` to bypass detection.
//
//   Constraint cost (approximate):
//     N  RAM init writes  (initialise seen[0..N-1] = false)
//     N  range checks     (cycle[i] < N)                    -- GROUP 1
//     N  RAM reads        (assert seen[cycle[i]] == false)  -- GROUP 2
//     N  RAM writes       (seen[cycle[i]] = true)           -- GROUP 2
//     ~4N constrained operations total for the permutation step.
//
//   Compared to other variants:
//     flat_full_pairwise:  O(N^2) modular-inverse gates
//     flat_full_sort:      ~3N   (N-1 ordering checks + ~2N ROM via check_shuffle)
//     flat_full_invperm:   2N    (N range checks + N ROM lookups; extra witness)
//     flat_full_presence:  ~4N   (N init + N range + N RAM reads + N RAM writes)
//
//   Unlike flat_full_invperm, no extra private witness is needed -- the prover
//   supplies only `cycle`. Unlike flat_full_sort, the permutation argument is
//   a direct sequential scan with no stdlib dependencies, making the soundness
//   argument straightforward to audit. The cost is that `seen` compiles to a
//   RAM rather than a ROM table, which carries higher per-access overhead in
//   UltraHonk than the ROM lookups in flat_full_invperm.
//
//   Note: GROUP 1 (range check) is explicit here, unlike flat_full_sort and
//   flat_full_invperm where it is subsumed by the permutation argument.
//
// Instance size:
//   N is set as a compile-time global. The benchmark harness recompiles this
//   circuit for each value of N under test.
// =============================================================================

// The number of nodes in this instance. Set at compile time; recompile per N.
global N: u32 = 500;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: the Hamiltonian cycle.
    // cycle[i] is the i-th node visited (zero-indexed).
    // Positions 0..N-1 cover all N nodes; the edge cycle[N-1] -> cycle[0] is
    // the return edge closing the cycle. It is NOT stored explicitly.
    // -------------------------------------------------------------------------
    cycle: [u32; N],

    // -------------------------------------------------------------------------
    // PUBLIC: edge cost matrix, flattened row-major.
    // cost_matrix[i * N + j] is the cost of the directed edge from node i to j.
    // Using a flat 1-D array because Noir's Prover.toml format handles 1-D
    // arrays most naturally. The Python formatter computes the flat index.
    // -------------------------------------------------------------------------
    cost_matrix: pub [u64; N * N],

    // -------------------------------------------------------------------------
    // PUBLIC: cost upper bound.
    // The prover claims the cycle costs at most this much.
    // The verifier sets T = actual_cost * multiplier before receiving the proof.
    // -------------------------------------------------------------------------
    threshold: pub u64,
) {
    // =========================================================================
    // CONSTRAINT GROUP 1 - Range check
    // =========================================================================
    // Each cycle entry must be a valid node index: 0 <= cycle[i] < N.
    // This check is explicit here, unlike flat_full_sort and flat_full_invperm
    // where it is subsumed by the permutation argument.
    //
    // The lower bound (>= 0) is free because cycle entries are u32.
    // The upper bound guard is necessary: the presence array `seen` has exactly
    // N entries, and an out-of-range index in the RAM access `seen[cycle[i]]`
    // would be undefined behaviour. The assert fires first and produces a clear
    // error message.
    //
    // Running this as a separate loop before the presence loop means out-of-range
    // indices are caught at GROUP 1 before GROUP 2 is entered.
    // Cost: N range assertions.
    for i in 0..N {
        assert(cycle[i] < N, "node index out of range");
    }

    // =========================================================================
    // CONSTRAINT GROUP 2 - Presence check (permutation check)
    // =========================================================================
    // A mutable boolean mark array of length N, initialised to all-false.
    // For each position i, we read seen[cycle[i]] and assert it equals false
    // (node not yet visited), then immediately set it to true (mark as visited).
    //
    // Soundness argument:
    //   If any two positions i < j satisfy cycle[i] == cycle[j], then when the
    //   loop reaches iteration j the entry seen[cycle[j]] is already true (it
    //   was set at iteration i), and the assertion fires. So all N values in
    //   cycle are distinct. Combined with GROUP 1 (each value in [0, N-1]), the
    //   N distinct values are exactly {0, 1, ..., N-1}.
    //
    // Why assert(seen[cycle[i]] == false) rather than assert(!seen[cycle[i]]):
    //   Both compile identically for bool, but the equality form states the
    //   expected value explicitly, matching the style of GROUP 1 and GROUP 4.
    //
    // Memory model:
    //   `seen` is a RAM table (read-write memory) in UltraHonk. The value
    //   [false; N] is part of the circuit structure -- constant, not supplied
    //   by the prover -- so a cheating prover cannot pre-initialise `seen` to
    //   avoid detection. The RAM consistency argument (timestamp-based) enforces
    //   that each read reflects the most recent write, correctly capturing the
    //   sequential semantics: the write at iteration i is visible at iteration j > i.
    //
    // Cost: N RAM init writes (from initialisation) + N RAM reads + N RAM writes.
    let mut seen: [bool; N] = [false; N];
    for i in 0..N {
        assert(seen[cycle[i]] == false, "duplicate node in cycle");
        seen[cycle[i]] = true;
    }

    // =========================================================================
    // CONSTRAINT GROUP 3 - Cycle cost computation
    // =========================================================================
    // Accumulate the cost of all N directed edges, including the return edge.
    // Identical to flat_full_pairwise; see that file for detailed commentary.
    //
    // (i+1) % N is comptime, so cycle[(i+1)%N] is a static array access.
    // cost_matrix[from * N + to] is a dynamic ROM lookup (runtime index).
    // Cost: N dynamic ROM lookups + N additions.
    let mut total_cost: u64 = 0;

    for i in 0..N {
        let from: u32 = cycle[i];
        let to:   u32 = cycle[(i + 1) % N]; // comptime index: wraps to 0 at i = N-1

        // Dynamic ROM lookup: index depends on the private witness.
        let edge_cost: u64 = cost_matrix[from * N + to];

        total_cost += edge_cost;
    }

    // =========================================================================
    // CONSTRAINT GROUP 4 - Threshold check
    // =========================================================================
    // The accumulated cycle cost must not exceed the public threshold.
    // u64 comparison decomposes into a range check on the difference,
    // costing O(64) boolean gates regardless of the actual cost values.
    assert(total_cost <= threshold, "cycle cost exceeds threshold");
}
