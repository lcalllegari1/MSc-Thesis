// =============================================================================
// TSP Hamiltonian Cycle ZKP - Flat / Full Matrix / Pairwise Permutation Check
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
//   The entire cost matrix is passed as public input rather than committed via
//   a hash. This avoids cryptographic overhead but means the verifier must
//   receive N^2 field elements. We benchmark this variant against a Merkle-
//   commitment variant later; the crossover point is part of the research.
//
// Design choice - "Pairwise" permutation check:
//   We prove the cycle visits every node exactly once by asserting that every
//   pair of positions (i, j) with i != j carries distinct node indices.
//   Constraint count: N*(N-1)/2 -- quadratic in N.
//   We will implement O(N log N) and O(N) variants for comparison.
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
    // Without this, the prover could fabricate out-of-range indices that
    // look "distinct" in the permutation check but do not correspond to any
    // real node in the graph.
    // The lower bound (>= 0) is free because cycle entries are u32.
    // Cost: N range assertions (each a single u32 comparison in UltraHonk).
    for i in 0..N {
        assert(cycle[i] < N, "node index out of range");
    }

    // =========================================================================
    // CONSTRAINT GROUP 2 - Pairwise distinctness (permutation check)
    // =========================================================================
    // For every pair of positions (i, j) with i < j, the node indices must
    // differ. Together with the range check above, this guarantees the cycle
    // is a permutation of {0, 1, ..., N-1}: every node is visited exactly once.
    //
    // How assert(a != b) works in a ZK circuit:
    //   The circuit witnesses the modular inverse of (a - b). That inverse
    //   exists if and only if (a - b) != 0, so the constraint
    //   (a - b) * inv == 1 proves a != b without revealing a or b.
    //
    // Cost: N*(N-1)/2 multiply-and-constrain gates -- O(N^2).
    for i in 0..N {
        for j in (i + 1)..N {
            assert(cycle[i] != cycle[j], "duplicate node in cycle");
        }
    }

    // =========================================================================
    // CONSTRAINT GROUP 3 - Cycle cost computation
    // =========================================================================
    // Accumulate the cost of all N directed edges, including the return edge.
    //
    // (i+1) % N is a *compile-time* expression (both N and the loop variable i
    // are comptime), so cycle[(i+1)%N] is a static array access -- free.
    //
    // cost_matrix[from * N + to] is a *runtime* (dynamic) lookup: `from` and
    // `to` come from the private witness. In UltraHonk, dynamic reads from a
    // fixed public array are handled via ROM (read-only memory) lookup tables.
    // Cost: N dynamic ROM lookups + N additions.
    //
    // We accumulate into u64 to prevent overflow for large N and large costs.
    // Worst case for our benchmarks: N=200, max edge ~1,414,000 =>
    // total <= 200 * 1,414,000 = 282,800,000, well within u64 range.
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
