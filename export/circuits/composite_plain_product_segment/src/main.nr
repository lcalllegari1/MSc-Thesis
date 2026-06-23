// =============================================================================
// Variant A++ - Hierarchical TSP / Sub-circuit `hierarchical_segment_fs`
// =============================================================================
//
// What this sub-circuit proves (for one segment of the global cycle):
//   "I know an M-node Hamiltonian path inside the segment, from start_node to
//    end_node in this order, whose internal edge costs sum to partial_cost and
//    are all committed by the Poseidon2 Merkle root over the N*N cost matrix.
//    I also fold my M segment nodes into a Poseidon2 hash chain from h_in_i to
//    h_out_i, and expose the grand product P_i = prod_j (X + node_j), where the
//    Fiat-Shamir challenge X = Poseidon2([c], 1) is bound to the full-cycle
//    chain terminal c."
//
// A++ vs A: the public `sorted_nodes[M]` array is GONE.  In its place are five
// Field scalars (P_i, h_in_i, h_out_i, c, X) and three new constraint groups
// (G5 chain link, G6 grand product, G7 challenge consistency).  The partition is
// no longer disclosed: the glue checks prod_i P_i == prod_j (X+j) instead of
// sorting a public node list.  Public-input pool shrinks from O(M) to O(1).
// See HIERARCHICAL_EXPLAINED.md sec. 9 and HIER_FS_IMPL.md sec. 2 for theory.
//
// Public inputs (verifier sees these), in signature / public-input-dump order:
//   start_node    - cycle_segment[0].
//   end_node      - cycle_segment[M-1].
//   partial_cost  - sum of the M-1 internal edge costs in this segment.
//   root          - Poseidon2 Merkle root over the N*N cost matrix.
//   P_i           - grand product prod_j (X + cycle_segment[j]) for this segment.
//   h_in_i        - hash-chain value entering this segment (= h_{i*M}).
//   h_out_i       - hash-chain value leaving this segment (= h_{(i+1)*M}).
//   c             - full-cycle chain terminal (= h_N); identical across all K+1
//                   proofs (verifier cross-checks equality).
//   X             - Fiat-Shamir challenge = Poseidon2::hash([c], 1); identical
//                   across all K+1 proofs (verifier cross-checks equality).
//
// Private witness (only the prover knows):
//   cycle_segment - the M nodes of this segment in actual visit order.
//   edge_costs    - the M-1 internal edge costs.
//   siblings      - Merkle siblings for the M-1 internal-edge proofs, flat.
//   path_bits     - LSB-first leaf-index encoding for the same proofs.
//
// Compile-time globals (the sub-circuit does NOT need K):
//   N      - total nodes in the instance.
//   M      - segment size = N/K.
//   DEPTH  - ceil(log2(N*N)), Merkle-tree depth.
//
// Constraint groups (G1..G7):
//   G1 Range.        Every cycle_segment[i] < N.
//   G2 Endpoints.    start_node == cycle_segment[0], end_node == cycle_segment[M-1].
//   G3 Internal Merkle.  M-1 edge proofs against root (identical idiom to A's G4).
//   G4 Cost binding. sum(edge_costs) == partial_cost.
//   G5 Chain link.   Fold M nodes from h_in_i to h_out_i via Poseidon2.  (NEW)
//   G6 Grand product. prod_j (X + cycle_segment[j]) == P_i.                (NEW)
//   G7 Challenge.    X == Poseidon2::hash([c], 1).  Defense-in-depth FS bind. (NEW)
//
// Gate-count estimate (M=120, DEPTH=18 -- N=480, K=4): ~198k gates, dominated by
// G3 Merkle (~186k); G5 chain adds ~10k, G6/G7 negligible.  ~+6% vs A's sub.
// =============================================================================

global N: u32 = 8;
global M: u32 = 4;
global DEPTH: u32 = 6;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: nodes of this segment in cycle order.  The verifier learns
    // neither this ordering nor the segment's node set (the grand product P_i
    // hides the multiset modulo a C(N,M) confirmation oracle; see
    // HIERARCHICAL_EXPLAINED.md sec. 9.11).
    // -------------------------------------------------------------------------
    cycle_segment: [u32; M],

    // -------------------------------------------------------------------------
    // PRIVATE: cost of each of the M-1 internal edges, in cycle order.
    // edge_costs[i] = cost_matrix[cycle_segment[i]][cycle_segment[i+1]].
    // -------------------------------------------------------------------------
    edge_costs: [u64; M - 1],

    // -------------------------------------------------------------------------
    // PRIVATE: Merkle siblings for the M-1 internal-edge proofs, flat row-major.
    // siblings[i*DEPTH + d] is the level-d sibling for edge i.
    // -------------------------------------------------------------------------
    siblings: [Field; (M - 1) * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: LSB-first path bits for the same proofs.
    // -------------------------------------------------------------------------
    path_bits: [bool; (M - 1) * DEPTH],

    // -------------------------------------------------------------------------
    // PUBLIC: segment endpoints in cycle order.
    // -------------------------------------------------------------------------
    start_node: pub u32,
    end_node:   pub u32,

    // -------------------------------------------------------------------------
    // PUBLIC: sum of the M-1 internal edge costs.
    // -------------------------------------------------------------------------
    partial_cost: pub u64,

    // -------------------------------------------------------------------------
    // PUBLIC: Poseidon2 Merkle root over the N*N cost matrix.  Cross-checked
    // equal across all K+1 proofs by pipeline/verify_hier_fs.py.
    // -------------------------------------------------------------------------
    root: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: grand product prod_j (X + cycle_segment[j]) for this segment.
    // The glue multiplies the K P_i values and compares to prod_j (X+j).
    // -------------------------------------------------------------------------
    P_i: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: hash-chain anchors for this segment.  h_in_i is the chain value
    // entering the segment, h_out_i the value leaving it.  The glue stitches
    // h_ins[i+1] == h_outs[i] and h_outs[K-1] == c.  (These are public because
    // the cross-check binds them across separate proofs; this makes the
    // interior order recoverable in ~(M-2)! work -- see sec. 9.11.)
    // -------------------------------------------------------------------------
    h_in_i:  pub Field,
    h_out_i: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: full-cycle chain terminal c (= h_N) and FS challenge X.  Both are
    // identical across all K+1 proofs; the verifier cross-checks equality.
    // -------------------------------------------------------------------------
    c: pub Field,
    X: pub Field,
) {
    // =========================================================================
    // G1 - Range check
    // =========================================================================
    for i in 0..M {
        assert(cycle_segment[i] < N, "node index out of range");
    }

    // =========================================================================
    // G2 - Endpoint binding
    // =========================================================================
    // No sort-based permutation check in A++: the grand product (G6) plus the
    // glue's partition check handle the multiset globally.
    assert(start_node == cycle_segment[0],     "start_node mismatch");
    assert(end_node   == cycle_segment[M - 1], "end_node mismatch");

    // =========================================================================
    // G3 - Internal Merkle proofs (M-1 edges) + cost accumulation
    // =========================================================================
    // Identical idiom to Variant A's G4.  For each internal edge i:
    //   (a) reconstruct leaf_idx from path_bits (LSB-first); assert == from*N+to.
    //   (b) hash edge_costs[i] up DEPTH levels to root.
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

    // =========================================================================
    // G4 - Cost binding
    // =========================================================================
    assert(sum == partial_cost, "partial_cost does not match sum of internal edge costs");

    // =========================================================================
    // G5 - Hash-chain link (NEW)
    // =========================================================================
    // Fold this segment's M nodes (in cycle order) into the Poseidon2 hash chain
    // starting from h_in_i; the result must equal h_out_i.  Same hash shape as
    // the Merkle step: Poseidon2::hash([h, node], 2), with h as the LEFT input
    // and the node index as the RIGHT input (matches the Rust builder's
    // poseidon2_compress and the chain step in HIER_FS_IMPL.md sec. 4.2).
    let mut h: Field = h_in_i;
    for j in 0..M {
        h = Poseidon2::hash([h, cycle_segment[j] as Field], 2);
    }
    assert(h == h_out_i, "chain link mismatch");

    // =========================================================================
    // G6 - Grand product (NEW)
    // =========================================================================
    // Compute prod_j (X + cycle_segment[j]) step by step; assert it equals P_i.
    // M field multiplications.  This is the per-segment factor of the global
    // multiset-equality argument enforced in the glue (G5).
    let mut prod: Field = 1;
    for j in 0..M {
        prod = prod * (X + cycle_segment[j] as Field);
    }
    assert(prod == P_i, "P_i mismatch");

    // =========================================================================
    // G7 - Challenge consistency (NEW)
    // =========================================================================
    // X must be the single-input Poseidon2 hash of c.  Enforced independently in
    // every sub-circuit AND in the glue (defense-in-depth, HIER_FS_IMPL D2): a
    // cryptographic binding of X to c in each proof, not relying solely on the
    // verifier's software cross-check that all proofs share the same X.
    let x_expected: Field = Poseidon2::hash([c], 1);
    assert(X == x_expected, "X != Poseidon2(c)");
}
