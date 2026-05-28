// =============================================================================
// Variant A - Hierarchical TSP / Sub-circuit `hierarchical_segment`
// =============================================================================
//
// What this sub-circuit proves (for one segment of the global cycle):
//   "I know an M-node Hamiltonian path inside the segment, from start_node to
//    end_node in this order, whose internal edge costs sum to partial_cost
//    and are all committed by the Poseidon2 Merkle root over the N*N cost
//    matrix. The sorted multiset of segment nodes equals sorted_nodes."
//
// One UltraHonk proof of this sub-circuit covers one of the K segments.  K
// independent sub-proofs plus one glue proof together cover the full N-node
// Hamiltonian cycle.  See HIERARCHICAL_EXPLAINED.md sec. 8 for the full theory
// and the soundness chain.
//
// Public inputs (verifier sees these):
//   sorted_nodes  - the M nodes of this segment, sorted ascending. The glue
//                   concatenates all K sub-proofs' sorted_nodes and checks the
//                   global multiset equals {0..N-1}.
//   start_node    - cycle_segment[0]. The glue uses ends[i] -> starts[(i+1)%K]
//                   as the boundary-edge endpoints.
//   end_node      - cycle_segment[M-1]. Symmetric.
//   partial_cost  - sum of the M-1 internal edge costs in this segment. The
//                   glue's threshold check sums these plus the K boundary costs.
//   root          - the Poseidon2 Merkle root over the N*N cost matrix
//                   (flattened row-major). All K+1 proofs declare this same
//                   root; the verifier cross-checks the equality.
//
// Private witness (only the prover knows):
//   cycle_segment - the M nodes of this segment in actual visit order.  Hiding
//                   this is the privacy guarantee: the verifier learns which
//                   nodes are in the segment (via sorted_nodes) but not in what
//                   order.  At M >= 4, (M-2)! interior orderings remain hidden
//                   per segment.
//   edge_costs    - the M-1 internal edge costs.  Per-edge values are sensitive;
//                   only the aggregate partial_cost is exposed.
//   siblings      - Merkle sibling hashes for the M-1 internal-edge proofs,
//                   flat row-major over (edge i, level d).
//   path_bits     - LSB-first leaf-index encoding for the same proofs:
//                   leaf_idx[i] = sum_d path_bits[i*DEPTH+d] * 2^d.
//                   Private because leaf_idx = from*N + to encodes the cycle
//                   order; the in-circuit reconstruction in G4 binds them to
//                   the actual cycle without revealing the index.
//
// Compile-time globals.  The sub-circuit does NOT need K: a segment knows about
// itself, not how many siblings it has.  One compile per (N, M, DEPTH) tuple
// serves all K values that share the same M = N/K.
//
//   N      - total nodes in the instance (used for leaf-index calc and range)
//   M      - segment size = N/K
//   DEPTH  - ceil(log2(N*N)), Merkle-tree depth (depends only on N)
//
// Constraint groups (G1..G5):
//
//   G1 Range.            Every cycle_segment[i] < N.  Without this an
//                        out-of-range index could overflow `from*N + to` at
//                        large N or alias into the padded zero zone of the tree.
//
//   G2 Permutation.      sort(cycle_segment) == sorted_nodes element-wise.
//                        No strict-ascending check is needed in the sub-circuit:
//                        global distinctness across the K segments is enforced
//                        transitively by glue.G2 (sort(all_sorted_nodes) ==
//                        [0..N-1]).  A duplicate inside one segment would show
//                        up as a duplicate in the concatenation and be caught
//                        there.  See HIERARCHICAL_EXPLAINED.md sec. 8.2.G2.
//
//   G3 Endpoints.        start_node == cycle_segment[0],
//                        end_node   == cycle_segment[M-1].
//                        Without G3 the prover could publish endpoints not in
//                        this segment, making the glue's boundary edge connect
//                        to fake nodes.
//
//   G4 Internal Merkle.  For each of the M-1 internal edges (i in 0..M-2):
//     (a) leaf-index check: path_bits decode (LSB-first) to exactly
//         cycle_segment[i]*N + cycle_segment[i+1].  This blocks proof
//         substitution for a cheaper leaf elsewhere in the tree.
//     (b) hash chain: edge_costs[i] cast to Field, hashed up DEPTH levels with
//         siblings/path_bits, must equal root.  This binds edge_costs[i] to
//         the committed matrix entry (Poseidon2 collision resistance).
//
//   G5 Cost binding.     sum(edge_costs) == partial_cost.  Without G5 a prover
//                        could under-report per-segment cost and slip the
//                        glue's threshold sum below T.
//
// Gate-count estimate (M=120, DEPTH=18 -- N=480, K=4):
//   G4 dominates: (M-1)*DEPTH ~ 2100 Poseidon2 calls ~ 186k gates.
//   G1+G2+G3+G5 together <500 gates.
// =============================================================================

global N: u32 = 480;
global M: u32 = 60;
global DEPTH: u32 = 18;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: nodes of this segment in cycle order.
    // The glue learns only sorted_nodes, never this ordering, preserving the
    // (M-2)! interior visit-order orderings per segment as the privacy bound.
    // -------------------------------------------------------------------------
    cycle_segment: [u32; M],

    // -------------------------------------------------------------------------
    // PRIVATE: cost of each of the M-1 internal edges, in cycle order.
    // edge_costs[i] = cost_matrix[cycle_segment[i]][cycle_segment[i+1]].
    // -------------------------------------------------------------------------
    edge_costs: [u64; M - 1],

    // -------------------------------------------------------------------------
    // PRIVATE: Merkle siblings for the M-1 internal-edge proofs, flat
    // row-major.  siblings[i*DEPTH + d] is the level-d sibling for edge i.
    // -------------------------------------------------------------------------
    siblings: [Field; (M - 1) * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: LSB-first path bits for the same proofs.
    // path_bits[i*DEPTH + d] = true  => edge i is a right child at level d.
    // Leaf-index reconstruction: leaf_idx[i] = sum_d (path_bits[i*DEPTH+d] * 2^d).
    // -------------------------------------------------------------------------
    path_bits: [bool; (M - 1) * DEPTH],

    // -------------------------------------------------------------------------
    // PUBLIC: the segment's node set, sorted ascending.
    // The glue's partition check operates on the concatenation of K of these.
    // -------------------------------------------------------------------------
    sorted_nodes: pub [u32; M],

    // -------------------------------------------------------------------------
    // PUBLIC: segment endpoints in cycle order.
    // Boundary edge into this segment terminates at start_node;
    // boundary edge out of this segment originates at end_node.
    // -------------------------------------------------------------------------
    start_node: pub u32,
    end_node:   pub u32,

    // -------------------------------------------------------------------------
    // PUBLIC: sum of the M-1 internal edge costs.
    // -------------------------------------------------------------------------
    partial_cost: pub u64,

    // -------------------------------------------------------------------------
    // PUBLIC: Poseidon2 Merkle root over the N*N cost matrix (row-major,
    // padded to next power of two).  Cross-checked equal across all K+1 proofs
    // by the off-circuit verifier (pipeline/verify_hier.py).
    // -------------------------------------------------------------------------
    root: pub Field,
) {
    // =========================================================================
    // G1 - Range check
    // =========================================================================
    // Every segment node is a valid TSP node index in [0, N).  Required before
    // G4 multiplies cycle_segment[i] * N to form the leaf index, since at
    // large N (from*N) overflows u32 once from >= 2^32 / N.
    for i in 0..M {
        assert(cycle_segment[i] < N, "node index out of range");
    }

    // =========================================================================
    // G2 - Permutation: sort(cycle_segment) == sorted_nodes
    // =========================================================================
    // Noir's sort_via produces the non-decreasing sort with a constrained
    // permutation check (~2M ROM lookups via stdlib check_shuffle plus M-1
    // ordering constraints).  We then bind the result to sorted_nodes
    // element-wise.  No strict-ascending check: a duplicate inside this
    // segment would surface in the glue's all_sorted_nodes concatenation and
    // be caught by glue G2.  Dropping strict-ascending saves M-1 gates.
    let sorted = cycle_segment.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..M {
        assert(sorted[i] == sorted_nodes[i], "sorted_nodes does not match sorted segment");
    }

    // =========================================================================
    // G3 - Endpoint binding
    // =========================================================================
    // Pins the publicly declared endpoints to the actual segment's first and
    // last entries in cycle order.  Blocks the "lie about boundary nodes"
    // attack described in HIERARCHICAL_EXPLAINED.md sec. 8.2.G3.
    assert(start_node == cycle_segment[0],     "start_node mismatch");
    assert(end_node   == cycle_segment[M - 1], "end_node mismatch");

    // =========================================================================
    // G4 - Internal Merkle proofs (M-1 edges)
    // =========================================================================
    // For each internal edge i in 0..M-2:
    //   (a) Reconstruct leaf_idx from path_bits (LSB-first) and assert it
    //       equals from*N + to.  Without this the prover could submit a valid
    //       proof for a cheaper leaf elsewhere in the tree (proof substitution).
    //   (b) Hash edge_costs[i] up DEPTH levels using siblings + path_bits and
    //       assert the final hash equals root.  Binds the cost to the
    //       committed matrix by Poseidon2 collision resistance.
    // Cost accumulation for G5 piggybacks on this loop.
    let mut sum: u64 = 0;
    for i in 0..(M - 1) {
        let from: u32 = cycle_segment[i];
        let to:   u32 = cycle_segment[i + 1];
        let expected_idx: u32 = from * N + to;

        // (a) Leaf-index reconstruction.
        let mut reconstructed_idx: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if path_bits[i * DEPTH + d] {
                reconstructed_idx += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed_idx == expected_idx, "path bits encode wrong leaf index");

        // (b) Hash chain up to the committed root.
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
    // G5 - Cost binding
    // =========================================================================
    // partial_cost is exactly the sum of the M-1 verified internal edge costs.
    // Without G5 a prover could publish partial_cost < real internal sum,
    // making the glue's threshold check pass on an actually-too-expensive
    // cycle.
    assert(sum == partial_cost, "partial_cost does not match sum of internal edge costs");
}
