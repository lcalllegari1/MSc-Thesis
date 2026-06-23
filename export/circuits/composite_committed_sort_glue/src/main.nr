// =============================================================================
// Variant committed-A - Hierarchical TSP / Glue circuit `hierarchical_glue_c`
// =============================================================================
//
// What this glue circuit proves (paired with K sub-proofs of
// hierarchical_segment_c):
//   "The K segments jointly form a Hamiltonian cycle on N nodes whose total cost
//    (internal sums + K boundary edges, all bound to the committed Merkle root)
//    is at most threshold; the K segment node-multisets partition {0..N-1}
//    exactly; and each public commitment C_is[i] opens (under blinding r_i) to
//    the per-segment (node visit order, partial_cost)."
//
// committed-A vs A glue: the public all_sorted_nodes, starts, ends and
// partial_costs are now PRIVATE witness.  The glue recomputes each commitment
// from the witness (G0) and asserts it equals the public C_is[i] -- the only
// thing binding the hidden values across the K+1 proofs (the verifier separately
// cross-checks glue.C_is[i] == sub_i.C_i).  The partition is the same O(N) sort
// as plain A, now over the witnessed (commitment-bound) nodes.  See
// FRONTIER_REFRAME.md F6 and HIERARCHICAL_EXPLAINED.md sec. 8.4 (partition) / 9.11.
//
// Public inputs (verifier sees these), in signature / public-input-dump order:
//   root      - Poseidon2 Merkle root (cross-checked equal across K+1).
//   threshold - cycle cost upper bound T.
//   C_is      - per-segment blinded commitments (cross-checked vs sub_i.C_i).
//
// Private witness (only the prover knows):
//   boundary_costs     - the K stitching-edge costs.
//   boundary_siblings  - Merkle siblings for the K boundary-edge proofs, flat.
//   boundary_path_bits - LSB-first leaf-index encoding for the same proofs.
//   all_nodes          - concatenation of the K segments' node visit orders
//                        (length N; segment i is all_nodes[i*M .. (i+1)*M]).
//   partial_costs      - per-segment internal cost sums (private now).
//   r_is               - per-segment blinding scalars (the commitment openings).
//
// Compile-time globals:
//   N      - total nodes (length of all_nodes; partition RHS [0..N-1]).
//   K      - number of segments (>= 2).
//   M      - segment size = N/K (needed to slice all_nodes + derive endpoints).
//   DEPTH  - ceil(log2(N*N)).
//
// Constraint groups:
//   G0 Commitment.    For each i, fold(r_is[i], [all_nodes[i*M..(i+1)*M],
//                     partial_costs[i]]) == C_is[i].
//   G2 Partition.     sort(all_nodes) == [0..N-1].
//   G6 Boundary Merkle. K edge proofs against root; edge i is end_i -> start_{i+1},
//                     with start_i = all_nodes[i*M], end_i = all_nodes[i*M+M-1].
//   G7 Threshold.     sum(partial_costs) + sum(boundary_costs) <= threshold.
// =============================================================================

global N: u32 = 48;
global K: u32 = 4;
global M: u32 = 12;
global DEPTH: u32 = 12;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: K boundary-edge costs.  boundary_costs[i] = M[end_i][start_{i+1}].
    // -------------------------------------------------------------------------
    boundary_costs: [u64; K],

    // -------------------------------------------------------------------------
    // PRIVATE: Merkle siblings for the K boundary-edge proofs, flat row-major.
    // -------------------------------------------------------------------------
    boundary_siblings: [Field; K * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: LSB-first path bits for the same proofs.
    // -------------------------------------------------------------------------
    boundary_path_bits: [bool; K * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: concatenated segment node visit orders (length N).
    // -------------------------------------------------------------------------
    all_nodes: [u32; N],

    // -------------------------------------------------------------------------
    // PRIVATE: per-segment internal cost sums.
    // -------------------------------------------------------------------------
    partial_costs: [u64; K],

    // -------------------------------------------------------------------------
    // PRIVATE: per-segment blinding scalars (commitment openings).
    // -------------------------------------------------------------------------
    r_is: [Field; K],

    // -------------------------------------------------------------------------
    // PUBLIC: Merkle root, threshold, per-segment commitments.
    // -------------------------------------------------------------------------
    root:      pub Field,
    threshold: pub u64,
    C_is:      pub [Field; K],
) {
    // =========================================================================
    // G0 - Commitment recompute + bind
    // =========================================================================
    // Recompute each C_i = fold(r_i, [segment_nodes..., partial_cost]) with the
    // SAME fold the sub-circuit used, and assert it equals the public C_is[i].
    for i in 0..K {
        let mut acc: Field = r_is[i];
        for j in 0..M {
            acc = Poseidon2::hash([acc, all_nodes[i * M + j] as Field], 2);
        }
        acc = Poseidon2::hash([acc, partial_costs[i] as Field], 2);
        assert(acc == C_is[i], "commitment mismatch");
    }

    // =========================================================================
    // G2 - Partition check: sort(all_nodes) == [0..N-1]
    // =========================================================================
    // Enforces that the K segments' node sets exactly partition {0..N-1}: no
    // overlap, no missing node.  Also forces every node into [0, N), so no
    // separate range check is needed in the glue (the boundary leaf-index
    // reconstruction further constrains the endpoints).
    let sorted = all_nodes.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..N {
        assert(sorted[i] == i as u32, "partition does not cover {0..N-1}");
    }

    // =========================================================================
    // G6 - Boundary Merkle proofs (K edges) + cost accumulation
    // =========================================================================
    // Boundary edge i is end_i -> start_{(i+1)%K}, with the endpoints derived
    // from the witnessed (commitment-bound) segment nodes.
    let mut boundary_sum: u64 = 0;
    for i in 0..K {
        let from: u32 = all_nodes[i * M + M - 1];          // end_i
        let to:   u32 = all_nodes[((i + 1) % K) * M];      // start_{(i+1)%K}
        let expected_idx: u32 = from * N + to;

        let mut reconstructed_idx: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if boundary_path_bits[i * DEPTH + d] {
                reconstructed_idx += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed_idx == expected_idx, "boundary path bits encode wrong leaf index");

        let mut current: Field = boundary_costs[i] as Field;
        for d in 0..DEPTH {
            let sibling: Field = boundary_siblings[i * DEPTH + d];
            let (left, right) = if boundary_path_bits[i * DEPTH + d] {
                (sibling, current)
            } else {
                (current, sibling)
            };
            current = Poseidon2::hash([left, right], 2);
        }
        assert(current == root, "boundary Merkle proof does not match committed root");

        boundary_sum += boundary_costs[i];
    }

    // =========================================================================
    // G7 - Threshold check
    // =========================================================================
    let mut total: u64 = 0;
    for i in 0..K {
        total += partial_costs[i];
    }
    total += boundary_sum;
    assert(total <= threshold, "cycle cost exceeds threshold");
}
