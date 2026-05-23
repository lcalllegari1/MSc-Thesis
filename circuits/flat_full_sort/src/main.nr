// =============================================================================
// TSP Hamiltonian Cycle ZKP - Flat / Full Matrix / Sort-based Permutation Check
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
// Design choice - "Sort" permutation check:
//   We prove the cycle visits every node exactly once by sorting a copy of
//   the cycle array and asserting the result equals [0, 1, ..., N-1].
//
//   Noir's `sort_via` stdlib method does this in O(N) constrained operations:
//     1. An unconstrained quicksort computes the sorted result (zero gates).
//     2. N-1 ordering constraints confirm the output is sorted.
//     3. `check_shuffle` (stdlib) confirms sorted is a permutation of the
//        input using ~2N dynamic ROM lookups (hint computed unconstrained,
//        verified constrained).
//
//   Combined with the N equality checks (sorted[i] == i), this is the
//   full permutation proof. Compare to flat_full_pairwise which uses
//   N*(N-1)/2 modular-inverse gates (O(N^2)).
//
//   Note: the explicit range check (cycle[i] < N) present in flat_full_pairwise
//   is not needed here. If sorted == [0,...,N-1] and sorted is proven to be a
//   permutation of cycle, the multiset of cycle must equal {0,...,N-1},
//   which implies every entry is already in range.
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
    // CONSTRAINT GROUP 2 - Sort-based permutation check
    // =========================================================================
    // Sort a copy of cycle; if the result equals [0, 1, ..., N-1] and it is
    // proven to be a rearrangement of cycle, then cycle is a permutation of
    // {0, ..., N-1}: every node is visited exactly once, every index in range.
    //
    // How sort_via works in a ZK circuit (Noir stdlib):
    //   a. An unconstrained quicksort runs during witness generation and
    //      produces `sorted`. This step contributes zero constrained gates.
    //   b. N-1 ordering constraints check sorted[i] <= sorted[i+1] for all i.
    //   c. check_shuffle (stdlib) links sorted back to cycle: it computes
    //      a permutation mapping unconstrained, then verifies it constrained
    //      using ~2N dynamic ROM lookups (arr[runtime_index] == value).
    //
    // Total constrained cost: O(N) -- a step change from the O(N^2)
    // pairwise approach in flat_full_pairwise.
    //
    // Note: the range check (cycle[i] < N) in GROUP 1 of flat_full_pairwise is
    // subsumed here. sorted == [0,...,N-1] and sorted ~ cycle (same multiset)
    // together imply cycle[i] in {0,...,N-1} for all i.
    let sorted = cycle.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..N {
        assert(sorted[i] == i as u32, "cycle is not a permutation of {0,...,N-1}");
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
