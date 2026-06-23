// =============================================================================
// Variant A++ - Hierarchical TSP / Glue circuit `hierarchical_glue_fs`
// =============================================================================
//
// What this glue circuit proves (paired with K sub-proofs of
// hierarchical_segment_fs):
//   "The K segments jointly form a Hamiltonian cycle on N nodes whose total cost
//    (internal sums + K boundary edges, all bound to the committed Merkle root)
//    is at most threshold; the K segment node-multisets partition {0..N-1}
//    exactly; and the Fiat-Shamir challenge X is bound to the full-cycle chain
//    terminal c."
//
// A++ vs A glue: the public `all_sorted_nodes[N]` array and the O(N) in-circuit
// sort are GONE.  In their place:
//   - chain stitching over the per-segment anchors (G1-G3),
//   - in-circuit Fiat-Shamir binding X == Poseidon2([c],1) (G4),
//   - grand-product partition prod_i P_is[i] == prod_{j=0..N-1}(X + j) (G5),
//     with the RHS computed IN-CIRCUIT (no expected_product public input;
//     HIER_FS_IMPL D5 = Option B).
// The boundary Merkle (G6) and threshold (G7) are unchanged from A's glue.
// See HIERARCHICAL_EXPLAINED.md sec. 9 and HIER_FS_IMPL.md sec. 3.
//
// Public inputs (verifier sees these), in signature / public-input-dump order:
//   starts        - per-segment start nodes (verifier cross-checks vs sub_i).
//   ends          - per-segment end nodes (verifier cross-checks vs sub_i).
//   partial_costs - per-segment internal cost sums (cross-checked vs sub_i).
//   threshold     - cycle cost upper bound T.
//   root          - Poseidon2 Merkle root (cross-checked equal across K+1).
//   P_is          - per-segment grand products (cross-checked vs sub_i.P_i).
//   h_ins         - per-segment chain entry anchors (cross-checked vs sub_i).
//   h_outs        - per-segment chain exit anchors (cross-checked vs sub_i).
//   c             - full-cycle chain terminal (cross-checked equal across K+1).
//   X             - Fiat-Shamir challenge (cross-checked equal across K+1).
//
// Private witness (only the prover knows):
//   boundary_costs     - the K stitching-edge costs.
//   boundary_siblings  - Merkle siblings for the K boundary-edge proofs, flat.
//   boundary_path_bits - LSB-first leaf-index encoding for the same proofs.
//
// Compile-time globals:
//   N      - total nodes (used for from*N+to leaf index AND the G5 RHS loop).
//   K      - number of segments (>= 2).
//   DEPTH  - ceil(log2(N*N)).  (No M global: the glue never iterates per-node.)
//
// Constraint groups (G1..G7):
//   G1 Chain init.     h_ins[0] == 0.
//   G2 Chain stitch.   h_ins[i+1] == h_outs[i] for i = 0..K-2.
//   G3 Chain terminal. h_outs[K-1] == c.
//   G4 Challenge.      X == Poseidon2::hash([c], 1).  (Defense-in-depth.)
//   G5 Partition.      prod_i P_is[i] == prod_{j=0..N-1}(X + j).  In-circuit RHS.
//   G6 Boundary Merkle. K edge proofs against root (identical idiom to A's G3).
//   G7 Threshold.      sum(partial_costs) + sum(boundary_costs) <= threshold.
//
// Gate-count estimate (N=480, K=4, DEPTH=18): ~6,900 gates -- ~-67% vs A's glue.
// The O(N) sort is gone; the G5 RHS loop is ~N cheap field mults.
// =============================================================================

global N: u32 = 8;
global K: u32 = 2;
global DEPTH: u32 = 6;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: cost of each of the K boundary edges, in segment order.
    // boundary_costs[i] = cost_matrix[ends[i]][starts[(i+1) % K]].
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
    // PUBLIC: per-segment endpoints in segment order.
    // -------------------------------------------------------------------------
    starts: pub [u32; K],
    ends:   pub [u32; K],

    // -------------------------------------------------------------------------
    // PUBLIC: per-segment internal cost sums.
    // -------------------------------------------------------------------------
    partial_costs: pub [u64; K],

    // -------------------------------------------------------------------------
    // PUBLIC: cycle cost upper bound.
    // -------------------------------------------------------------------------
    threshold: pub u64,

    // -------------------------------------------------------------------------
    // PUBLIC: Poseidon2 Merkle root over the N*N cost matrix.
    // -------------------------------------------------------------------------
    root: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: per-segment grand products (factors of the partition check).
    // -------------------------------------------------------------------------
    P_is: pub [Field; K],

    // -------------------------------------------------------------------------
    // PUBLIC: per-segment chain anchors, stitched into one continuous chain.
    // -------------------------------------------------------------------------
    h_ins:  pub [Field; K],
    h_outs: pub [Field; K],

    // -------------------------------------------------------------------------
    // PUBLIC: full-cycle chain terminal c and FS challenge X.
    // -------------------------------------------------------------------------
    c: pub Field,
    X: pub Field,
) {
    // =========================================================================
    // G1 - Chain init
    // =========================================================================
    // The chain must start from the fixed constant 0.  If sub_0 could choose
    // h_in_0, the prover could grind starting values for a useful c.
    assert(h_ins[0] == 0, "chain must start from 0");

    // =========================================================================
    // G2 - Chain stitching (K-1 equalities; trivially handles K=2)
    // =========================================================================
    for i in 0..(K - 1) {
        assert(h_ins[i + 1] == h_outs[i], "chain not continuous");
    }

    // =========================================================================
    // G3 - Chain terminal
    // =========================================================================
    assert(h_outs[K - 1] == c, "chain does not terminate at c");

    // =========================================================================
    // G4 - Challenge consistency (defense-in-depth alongside each sub's G7)
    // =========================================================================
    let x_expected: Field = Poseidon2::hash([c], 1);
    assert(X == x_expected, "X != Poseidon2(c)");

    // =========================================================================
    // G5 - Grand-product partition (in-circuit RHS; HIER_FS_IMPL D5 Option B)
    // =========================================================================
    // LHS: product of the K sub-proofs' P_i values.
    let mut lhs: Field = 1;
    for i in 0..K {
        lhs = lhs * P_is[i];
    }
    // RHS: prod_{j=0..N-1}(X + j).  Computed in-circuit (~N cheap field mults),
    // so there is no expected_product public input and the verifier does no
    // field arithmetic.  By Schwartz-Zippel at the unforgeable X, LHS == RHS iff
    // the K segment multisets partition {0..N-1} exactly (error <= N / 2^254).
    let mut rhs: Field = 1;
    for j in 0..N {
        rhs = rhs * (X + j as Field);
    }
    assert(lhs == rhs, "grand-product partition mismatch");

    // =========================================================================
    // G6 - Boundary Merkle proofs (K edges) + cost accumulation
    // =========================================================================
    // Identical idiom to A's glue G3.  Boundary edge i is ends[i] ->
    // starts[(i+1) % K]; the wrap-around closes the K-1 -> 0 boundary.
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
