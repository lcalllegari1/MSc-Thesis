// =============================================================================
// Variant committed-A - Hierarchical TSP / Sub-circuit `hierarchical_segment_c`
// =============================================================================
//
// What this sub-circuit proves (for one segment of the global cycle):
//   "I know an M-node Hamiltonian path inside the segment whose internal edge
//    costs sum to partial_cost and are all committed by the Poseidon2 Merkle root
//    over the N*N cost matrix.  I publish ONLY a blinded commitment
//    C_i = fold(r, [cycle_segment..., partial_cost]) to my segment's node visit
//    order and cost sum."
//
// committed-A vs A (the privacy upgrade): plain A exposed the segment's node set
// (`sorted_nodes`), endpoints and `partial_cost` in the clear -- an unconditional
// partition disclosure.  committed-A folds the segment nodes + cost into a single
// blinded commitment and moves them to private witness.  With r secret and
// Poseidon2 modelled as a random oracle, C_i is hiding.  The glue recomputes C_i
// over witnessed values, sorts the concatenation of all K segments to enforce the
// partition, and derives the boundary endpoints from the witnessed nodes.
// Residual public leak vs flat: the K commitments reveal K (segment count) and
// hiding rests on Poseidon2 -- one assumption below flat/recursion, identical
// privacy class to committed-A++ (they differ only in glue mechanism: O(N) sort
// here vs distributed grand-product there).  See FRONTIER_REFRAME.md F6/F7/F9.
//
// Public inputs (verifier sees these), in signature / public-input-dump order:
//   root  - Poseidon2 Merkle root over the N*N cost matrix.
//   C_i   - blinded commitment to (cycle_segment, partial_cost).  The glue
//           cross-binds this to the witnessed values.
//
// Private witness (only the prover knows):
//   cycle_segment - the M nodes of this segment in actual visit order.
//   edge_costs    - the M-1 internal edge costs.
//   siblings      - Merkle siblings for the M-1 internal-edge proofs, flat.
//   path_bits     - LSB-first leaf-index encoding for the same proofs.
//   r             - blinding scalar making C_i hiding.  Sampled uniformly.
//
// Compile-time globals: N, M = N/K, DEPTH = ceil(log2(N*N)).
//
// Constraint groups:
//   G1 Range.        Every cycle_segment[i] < N.
//   G3 Internal Merkle + cost accumulation (identical idiom to A).
//   G8 Commitment.   C_i == fold(r, [cycle_segment..., partial_cost]).
// (G2 sort and the public endpoints are absorbed: the glue owns the partition
//  sort and derives endpoints from the witnessed, commitment-bound nodes.)
// =============================================================================

global N: u32 = 5000;
global M: u32 = 625;
global DEPTH: u32 = 25;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: nodes of this segment in cycle order.  Hidden (committed in C_i).
    // -------------------------------------------------------------------------
    cycle_segment: [u32; M],

    // -------------------------------------------------------------------------
    // PRIVATE: cost of each of the M-1 internal edges, in cycle order.
    // -------------------------------------------------------------------------
    edge_costs: [u64; M - 1],

    // -------------------------------------------------------------------------
    // PRIVATE: Merkle siblings for the M-1 internal-edge proofs, flat row-major.
    // -------------------------------------------------------------------------
    siblings: [Field; (M - 1) * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: LSB-first path bits for the same proofs.
    // -------------------------------------------------------------------------
    path_bits: [bool; (M - 1) * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: blinding scalar making C_i a hiding commitment.
    // -------------------------------------------------------------------------
    r: Field,

    // -------------------------------------------------------------------------
    // PUBLIC: Poseidon2 Merkle root over the N*N cost matrix.
    // -------------------------------------------------------------------------
    root: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: blinded commitment to this segment's node order + cost sum.
    // -------------------------------------------------------------------------
    C_i: pub Field,
) {
    // =========================================================================
    // G1 - Range check
    // =========================================================================
    for i in 0..M {
        assert(cycle_segment[i] < N, "node index out of range");
    }

    // =========================================================================
    // G3 - Internal Merkle proofs (M-1 edges) + cost accumulation
    // =========================================================================
    let mut sum: u64 = 0;
    for i in 0..(M - 1) {
        let from: u32 = cycle_segment[i];
        let to:   u32 = cycle_segment[i + 1];
        let expected_idx: u32 = from * N + to;

        let mut reconstructed_idx: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if path_bits[i * DEPTH + d] {
                reconstructed_idx += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed_idx == expected_idx, "path bits encode wrong leaf index");

        let mut current: Field = edge_costs[i] as Field;
        for d in 0..DEPTH {
            let sibling: Field = siblings[i * DEPTH + d];
            let (left, right) = if path_bits[i * DEPTH + d] {
                (sibling, current)
            } else {
                (current, sibling)
            };
            current = Poseidon2::hash([left, right], 2);
        }
        assert(current == root, "Merkle proof does not match committed root");

        sum += edge_costs[i];
    }
    let partial_cost: u64 = sum;

    // =========================================================================
    // G8 - Commitment
    // =========================================================================
    // C_i = fold(r, [cycle_segment[0], .., cycle_segment[M-1], partial_cost]) using
    // the 2-input Poseidon2 (cross-validated against the Rust builder in
    // tests/hash_compat), seeded by the secret r so the commitment is hiding.
    // The glue recomputes this exact fold over its witnessed nodes and asserts
    // equality, binding the hidden segment across the K+1 proofs.
    let mut acc: Field = r;
    for j in 0..M {
        acc = Poseidon2::hash([acc, cycle_segment[j] as Field], 2);
    }
    acc = Poseidon2::hash([acc, partial_cost as Field], 2);
    assert(acc == C_i, "commitment mismatch");
}
