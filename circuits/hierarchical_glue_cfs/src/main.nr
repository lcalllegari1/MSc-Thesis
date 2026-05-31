// =============================================================================
// Variant committed-A++ - Hierarchical TSP / Glue circuit `hierarchical_glue_cfs`
// =============================================================================
//
// What this glue circuit proves (paired with K sub-proofs of
// hierarchical_segment_cfs):
//   "The K segments jointly form a Hamiltonian cycle on N nodes whose total cost
//    (internal sums + K boundary edges, all bound to the committed Merkle root)
//    is at most threshold; the K segment node-multisets partition {0..N-1}
//    exactly; the Fiat-Shamir challenge X is bound to the full-cycle chain
//    terminal c; and each public commitment C_is[i] opens (under blinding r_i)
//    to the per-segment values (P_i, h_in, h_out, start, end, partial_cost)."
//
// committed-A++ vs A++ glue: the per-segment public arrays (starts, ends,
// partial_costs, P_is, h_ins, h_outs) and the chain terminal c are now PRIVATE
// witness.  The glue recomputes each commitment from the witness (G0) and
// asserts it equals the public C_is[i]; this is the only thing binding the
// hidden values across the K+1 proofs (the verifier separately cross-checks
// glue.C_is[i] == sub_i.C_i).  Everything else is the A++ glue, run on the
// now-private values.  See FRONTIER_REFRAME.md F6 and HIERARCHICAL_EXPLAINED.md
// sec. 9.11 for why this closes A++'s confirmation-oracle leak.
//
// Public inputs (verifier sees these), in signature / public-input-dump order:
//   root      - Poseidon2 Merkle root (cross-checked equal across K+1).
//   threshold - cycle cost upper bound T.
//   X         - Fiat-Shamir challenge (cross-checked equal across K+1).
//   C_is      - per-segment blinded commitments (cross-checked vs sub_i.C_i).
//
// Private witness (only the prover knows):
//   boundary_costs     - the K stitching-edge costs.
//   boundary_siblings  - Merkle siblings for the K boundary-edge proofs, flat.
//   boundary_path_bits - LSB-first leaf-index encoding for the same proofs.
//   starts, ends       - per-segment endpoints (private now; used for boundary
//                        edges and folded into the commitment recompute).
//   partial_costs      - per-segment internal cost sums (private now).
//   P_is               - per-segment grand products (private now).
//   h_ins, h_outs      - per-segment chain anchors (private now).
//   r_is               - per-segment blinding scalars (the commitment openings).
//   c                  - full-cycle chain terminal (private now).
//
// Compile-time globals:
//   N, K, DEPTH (as in hierarchical_glue_fs).
//
// Constraint groups:
//   G0 Commitment.    For each i, fold(r_is[i], [P_is[i], h_ins[i], h_outs[i],
//                     starts[i], ends[i], partial_costs[i]]) == C_is[i].
//   G1 Chain init.    h_ins[0] == 0.
//   G2 Chain stitch.  h_ins[i+1] == h_outs[i].
//   G3 Chain terminal.h_outs[K-1] == c.
//   G4 Challenge.     X == Poseidon2::hash([c], 1).
//   G5 Partition.     prod_i P_is[i] == prod_{j=0..N-1}(X + j).  In-circuit RHS.
//   G6 Boundary Merkle. K edge proofs against root (ends[i] -> starts[(i+1)%K]).
//   G7 Threshold.     sum(partial_costs) + sum(boundary_costs) <= threshold.
// =============================================================================

global N: u32 = 8;
global K: u32 = 2;
global DEPTH: u32 = 6;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: K boundary-edge costs.  boundary_costs[i] = M[ends[i]][starts[(i+1)%K]].
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
    // PRIVATE: per-segment values (public arrays in A++; witness here).
    // -------------------------------------------------------------------------
    starts:        [u32; K],
    ends:          [u32; K],
    partial_costs: [u64; K],
    P_is:          [Field; K],
    h_ins:         [Field; K],
    h_outs:        [Field; K],

    // -------------------------------------------------------------------------
    // PRIVATE: per-segment blinding scalars (commitment openings).
    // -------------------------------------------------------------------------
    r_is: [Field; K],

    // -------------------------------------------------------------------------
    // PRIVATE: full-cycle chain terminal c (public in A++; witness here).
    // -------------------------------------------------------------------------
    c: Field,

    // -------------------------------------------------------------------------
    // PUBLIC: Merkle root, threshold, FS challenge, per-segment commitments.
    // -------------------------------------------------------------------------
    root:      pub Field,
    threshold: pub u64,
    X:         pub Field,
    C_is:      pub [Field; K],
) {
    // =========================================================================
    // G0 - Commitment recompute + bind
    // =========================================================================
    // Recompute each C_i = fold(r_i, [P_i, h_in, h_out, start, end, partial_cost])
    // with the SAME fold the sub-circuit used, and assert it equals the public
    // C_is[i].  Binds the witnessed per-segment values to the commitments that
    // the verifier has cross-checked equal to the sub-proofs'.
    for i in 0..K {
        let mut acc: Field = r_is[i];
        acc = Poseidon2::hash([acc, P_is[i]], 2);
        acc = Poseidon2::hash([acc, h_ins[i]], 2);
        acc = Poseidon2::hash([acc, h_outs[i]], 2);
        acc = Poseidon2::hash([acc, starts[i] as Field], 2);
        acc = Poseidon2::hash([acc, ends[i] as Field], 2);
        acc = Poseidon2::hash([acc, partial_costs[i] as Field], 2);
        assert(acc == C_is[i], "commitment mismatch");
    }

    // =========================================================================
    // G1 - Chain init
    // =========================================================================
    assert(h_ins[0] == 0, "chain must start from 0");

    // =========================================================================
    // G2 - Chain stitching
    // =========================================================================
    for i in 0..(K - 1) {
        assert(h_ins[i + 1] == h_outs[i], "chain not continuous");
    }

    // =========================================================================
    // G3 - Chain terminal
    // =========================================================================
    assert(h_outs[K - 1] == c, "chain does not terminate at c");

    // =========================================================================
    // G4 - Challenge consistency
    // =========================================================================
    let x_expected: Field = Poseidon2::hash([c], 1);
    assert(X == x_expected, "X != Poseidon2(c)");

    // =========================================================================
    // G5 - Grand-product partition (in-circuit RHS)
    // =========================================================================
    let mut lhs: Field = 1;
    for i in 0..K {
        lhs = lhs * P_is[i];
    }
    let mut rhs: Field = 1;
    for j in 0..N {
        rhs = rhs * (X + j as Field);
    }
    assert(lhs == rhs, "grand-product partition mismatch");

    // =========================================================================
    // G6 - Boundary Merkle proofs (K edges) + cost accumulation
    // =========================================================================
    let mut boundary_sum: u64 = 0;
    for i in 0..K {
        let from: u32 = ends[i];
        let to:   u32 = starts[(i + 1) % K];
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
