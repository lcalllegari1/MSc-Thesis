// =============================================================================
// Variant committed-A++ - Hierarchical TSP / Sub-circuit `hierarchical_segment_cfs`
// =============================================================================
//
// What this sub-circuit proves (for one segment of the global cycle):
//   "I know an M-node Hamiltonian path inside the segment, from start to end in
//    this order, whose internal edge costs sum to partial_cost and are all
//    committed by the Poseidon2 Merkle root over the N*N cost matrix.  I fold my
//    M segment nodes into a Poseidon2 hash chain from h_in to h_out, expose the
//    grand product P_i = prod_j (X + node_j) for the FS challenge X, and publish
//    ONLY a blinded commitment C_i = fold(r, [P_i, h_in, h_out, start, end,
//    partial_cost]) to all of these per-segment values."
//
// committed-A++ vs A++ (the privacy upgrade): A++ exposed five Field scalars
// (P_i, h_in_i, h_out_i, c, X) plus start/end/partial_cost in the clear.  Two of
// those (P_i and the chain anchors) are *confirmation oracles* (HIERARCHICAL_
// EXPLAINED.md sec. 9.11): a verifier willing to do C(N,M) / (M-2)! work can
// factor P_i and brute-force the anchors to recover the partition + interior
// order.  committed-A++ folds every per-segment value into a SINGLE blinded
// commitment C_i and moves the cleartext to private witness.  With the blinding
// r secret and Poseidon2 modelled as a random oracle, C_i is hiding: a guessed
// segment cannot be confirmed without r.  The oracles close; the partition is
// hidden *computationally on the commitment scheme*, not merely behind a search.
// Residual public leak vs flat: the K commitments reveal K (segment count) and
// the hiding rests on Poseidon2 (one assumption below flat/recursion, which make
// the partition structurally absent).  See FRONTIER_REFRAME.md F6/F9/F10.
//
// Public inputs (verifier sees these), in signature / public-input-dump order:
//   root  - Poseidon2 Merkle root over the N*N cost matrix.
//   X     - Fiat-Shamir challenge; identical across all K+1 proofs (the verifier
//           cross-checks equality).  X = Poseidon2([c],1) over the now-PRIVATE
//           full-cycle chain terminal c; the X<->c binding is enforced in glue.
//   C_i   - blinded commitment to this segment's (P_i, h_in, h_out, start, end,
//           partial_cost).  The glue cross-binds this to the witnessed values.
//
// Private witness (only the prover knows):
//   cycle_segment - the M nodes of this segment in actual visit order.
//   edge_costs    - the M-1 internal edge costs.
//   siblings      - Merkle siblings for the M-1 internal-edge proofs, flat.
//   path_bits     - LSB-first leaf-index encoding for the same proofs.
//   h_in_i        - chain value entering this segment (private now; bound to the
//                   stitched global chain by the glue + the commitment equality).
//   r             - blinding scalar making C_i hiding.  Sampled uniformly.
//
// Compile-time globals (the sub-circuit does NOT need K):
//   N      - total nodes in the instance.
//   M      - segment size = N/K.
//   DEPTH  - ceil(log2(N*N)), Merkle-tree depth.
//
// Constraint groups:
//   G1 Range.        Every cycle_segment[i] < N.
//   G3 Internal Merkle + cost accumulation (identical idiom to A++ / A).
//   G5 Chain link.   Fold M nodes from h_in_i to h_out (Poseidon2).
//   G6 Grand product. prod_j (X + cycle_segment[j]) == P_i (local).
//   G8 Commitment.   C_i == fold(r, [P_i, h_in_i, h_out, start, end, partial_cost]).
// (G2 endpoints and G4 cost-binding are absorbed: start/end/partial_cost are now
//  local values folded into C_i, so binding them to the segment IS the commitment.
//  G7 challenge-consistency is dropped -- see header.)
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
    // PRIVATE: chain value entering this segment.  Public in A++; private here.
    // -------------------------------------------------------------------------
    h_in_i: Field,

    // -------------------------------------------------------------------------
    // PRIVATE: blinding scalar making C_i a hiding commitment.
    // -------------------------------------------------------------------------
    r: Field,

    // -------------------------------------------------------------------------
    // PUBLIC: Poseidon2 Merkle root over the N*N cost matrix.
    // -------------------------------------------------------------------------
    root: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: Fiat-Shamir challenge X (shared across all K+1 proofs).
    // -------------------------------------------------------------------------
    X: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: blinded commitment to this segment's per-segment values.
    // -------------------------------------------------------------------------
    C_i: pub Field,
) {
    // =========================================================================
    // G1 - Range check
    // =========================================================================
    for i in 0..M {
        assert(cycle_segment[i] < N, "node index out of range");
    }

    // Local endpoints (folded into the commitment, no longer public).
    let start_node: u32 = cycle_segment[0];
    let end_node:   u32 = cycle_segment[M - 1];

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
    let partial_cost: u64 = sum; // G4 absorbed: partial_cost is this local sum.

    // =========================================================================
    // G5 - Hash-chain link
    // =========================================================================
    // Fold this segment's M nodes (cycle order) into the Poseidon2 chain from
    // h_in_i; result is h_out.  Same shape as A++'s G5 (Poseidon2([h, node], 2)).
    let mut h: Field = h_in_i;
    for j in 0..M {
        h = Poseidon2::hash([h, cycle_segment[j] as Field], 2);
    }
    let h_out: Field = h;

    // =========================================================================
    // G6 - Grand product
    // =========================================================================
    let mut prod: Field = 1;
    for j in 0..M {
        prod = prod * (X + cycle_segment[j] as Field);
    }
    let p_i: Field = prod;

    // =========================================================================
    // G8 - Commitment
    // =========================================================================
    // C_i = fold(r, [P_i, h_in_i, h_out, start, end, partial_cost]) using the
    // 2-input Poseidon2 (cross-validated against the Rust builder in
    // tests/hash_compat).  Seeded by the secret r so the commitment is hiding.
    // The glue recomputes this exact fold over its witnessed values and asserts
    // equality, binding the hidden per-segment data across the K+1 proofs.
    let mut acc: Field = r;
    acc = Poseidon2::hash([acc, p_i], 2);
    acc = Poseidon2::hash([acc, h_in_i], 2);
    acc = Poseidon2::hash([acc, h_out], 2);
    acc = Poseidon2::hash([acc, start_node as Field], 2);
    acc = Poseidon2::hash([acc, end_node as Field], 2);
    acc = Poseidon2::hash([acc, partial_cost as Field], 2);
    assert(acc == C_i, "commitment mismatch");
}
