// =============================================================================
// TSP Hamiltonian Cycle ZKP - Flat / Full Matrix / Inverse-Permutation Check
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
//   inv_perm     - the inverse permutation of cycle:
//                  inv_perm[v] = i  means  cycle[i] == v.
//                  Computed by the prover off-circuit in O(N) time.
//
// Design choice - "Flat-Full":
//   Identical to flat_full_pairwise. The entire cost matrix is passed as
//   public input. See that variant for the rationale and the trade-off
//   against the Merkle commitment approach.
//
// Design choice - "InvPerm" permutation check:
//   The prover supplies inv_perm as an additional private witness - the
//   inverse mapping from node values to their positions in cycle.
//
//   The circuit verifies, for each v in {0,...,N-1}:
//     1. inv_perm[v] < N          (position is in range)
//     2. cycle[inv_perm[v]] == v  (cycle really holds v at that position)
//
//   Soundness argument: if inv_perm[u] == inv_perm[v] for u != v, then
//   cycle at that single position would have to equal both u and v
//   simultaneously - impossible. So the N position checks implicitly force
//   inv_perm to be injective, hence bijective, hence cycle covers all of
//   {0,...,N-1} exactly once.
//
//   Compared to flat_full_sort (which uses sort_via internally):
//     flat_full_sort:   N-1 ordering checks + ~2N ROM lookups (check_shuffle)
//     flat_full_invperm: N range checks     +  N ROM lookups
//   The saving comes from eliminating the sortedness verification entirely.
//   The cost is that the prover must compute and supply inv_perm off-circuit.
//
//   Note: the explicit range check (cycle[i] < N) from flat_full_pairwise is
//   again subsumed. The N equality assertions force cycle to hold each value
//   in {0,...,N-1} exactly once, which implies all entries are in range.
//
// Instance size:
//   N is set as a compile-time global. The benchmark harness recompiles this
//   circuit for each value of N under test.
// =============================================================================

// The number of nodes in this instance. Set at compile time; recompile per N.
global N: u32 = 8;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: the Hamiltonian cycle.
    // cycle[i] is the i-th node visited (zero-indexed).
    // Positions 0..N-1 cover all N nodes; the edge cycle[N-1] -> cycle[0] is
    // the return edge closing the cycle. It is NOT stored explicitly.
    // -------------------------------------------------------------------------
    cycle: [u32; N],

    // -------------------------------------------------------------------------
    // PRIVATE: inverse permutation of cycle (additional prover witness).
    // inv_perm[v] = i  such that  cycle[i] == v.
    // The prover computes this off-circuit in O(N) time via a single scan.
    // Providing it as a witness shifts work from constrained (proof) to
    // unconstrained (prover bookkeeping), reducing circuit gate count.
    // -------------------------------------------------------------------------
    inv_perm: [u32; N],

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
    // CONSTRAINT GROUP 2 - Inverse-permutation check
    // =========================================================================
    // For each value v in {0,...,N-1}, the prover claims that node v lives at
    // position inv_perm[v] in the cycle. Two constraints per v:
    //
    //   a. inv_perm[v] < N  -- position is a valid index (range check)
    //   b. cycle[inv_perm[v]] == v  -- cycle really holds v at that position
    //      (dynamic ROM lookup: inv_perm[v] is a runtime value)
    //
    // Together these N pairs prove cycle is a permutation of {0,...,N-1}:
    //   - Each v has a claimed position (constraint a keeps it in bounds).
    //   - Two distinct values u != v cannot share a position: that would
    //     require cycle[pos] == u AND cycle[pos] == v, a contradiction.
    //   - So the N positions are distinct, covering all of {0,...,N-1} once.
    //
    // Cost: N range checks + N dynamic ROM lookups = 2N constrained operations.
    // The sortedness checks in flat_full_sort are entirely absent here.
    for v in 0..N {
        assert(inv_perm[v] < N, "inv_perm entry out of range");
        assert(cycle[inv_perm[v]] == v as u32, "cycle missing node v at claimed position");
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
