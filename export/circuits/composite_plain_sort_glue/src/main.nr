// =============================================================================
// Variant A - Hierarchical TSP / Glue circuit `hierarchical_glue`
// =============================================================================
//
// What this glue circuit proves (paired with K sub-proofs):
//   "The K segments described by the public arrays (sorted_nodes chunks,
//    starts, ends, partial_costs) jointly form a Hamiltonian cycle on N
//    nodes whose total cost (internal sums + K boundary edges, all bound to
//    the committed Merkle root) is at most threshold."
//
// One UltraHonk proof of this glue plus K independent sub-proofs of
// hierarchical_segment together cover the full statement.  The verifier runs
// `bb verify` K+1 times and additionally checks (via pipeline/verify_hier.py)
// that the public-input fields the proofs claim to share actually agree.
// See HIERARCHICAL_EXPLAINED.md sec. 8 for the full theory.
//
// Public inputs (verifier sees these):
//   all_sorted_nodes  - concatenation of the K sub-proofs' sorted_nodes arrays
//                       (M values each).  NOT yet globally sorted; G2 sorts
//                       in-circuit.  The verifier cross-checks each chunk
//                       equals the corresponding sub-proof's sorted_nodes.
//   starts            - per-segment start nodes in segment order; boundary
//                       edges terminate at these (verifier cross-checks each
//                       starts[i] == sub_i.start_node).
//   ends              - per-segment end nodes in segment order; boundary
//                       edges originate from these (verifier cross-checks
//                       each ends[i] == sub_i.end_node).
//   partial_costs     - per-segment internal cost sums (verifier cross-checks
//                       each partial_costs[i] == sub_i.partial_cost).  Glue
//                       G4 sums these plus the K boundary costs against
//                       threshold.
//   threshold         - the cycle cost upper bound T.
//   root              - the same Poseidon2 Merkle root declared by all K
//                       sub-proofs (verifier cross-checks equality across
//                       all K+1 proofs).
//
// Private witness (only the prover knows):
//   boundary_costs    - the K stitching-edge costs.  Per-edge values are
//                       sensitive; the threshold sum (public, derivable from
//                       inputs) is the only aggregate exposed.
//   boundary_siblings - Merkle siblings for the K boundary-edge proofs,
//                       flat row-major over (edge i, level d).
//   boundary_path_bits- LSB-first leaf-index encoding for the same proofs.
//                       The encoded index ends[i]*N + starts[(i+1)%K] is
//                       technically derivable from the public starts/ends,
//                       so these bits are "private for consistency" with the
//                       sub-circuit's internal proofs rather than for secrecy.
//
// Compile-time globals:
//   N      - total nodes in the instance (also length of all_sorted_nodes)
//   K      - number of segments (>= 2; cycle is closed by K boundary edges)
//   DEPTH  - ceil(log2(N*N))
// (No M global: M = N/K is implicit in the segment-size of all_sorted_nodes
//  chunks but the glue itself never indexes by M; cross-checks in
//  verify_hier.py split all_sorted_nodes into K = N/M chunks off-circuit.)
//
// Constraint groups (G1..G4):
//
//   G1 Structural.    Indexing convention: boundary edge i is ends[i] ->
//                     starts[(i+1) % K].  The (i+1)%K wrap-around closes the
//                     cycle at the K-1 -> 0 boundary.  No constraint emitted.
//
//   G2 Partition.     sort(all_sorted_nodes) == [0..N-1].  Enforces that the
//                     K segments' node sets exactly partition {0..N-1}: no
//                     overlap, no missing node.  This is the LOAD-BEARING
//                     global-distinctness check; sub-circuit G2 only
//                     guarantees in-segment sorting, not cross-segment
//                     disjointness.  See HIERARCHICAL_EXPLAINED.md sec.
//                     8.4.G2 for the overlap counterexample.
//
//   G3 Boundary Merkle. Same construction as sub-circuit G4, applied to K
//                       boundary edges.  Two checks per boundary edge i:
//                       (a) leaf_idx reconstruction equals
//                           ends[i] * N + starts[(i+1) % K]
//                       (b) hash chain edge_cost -> root matches the
//                           committed root.
//                       Cost accumulation for G4 piggybacks here.
//
//   G4 Threshold.    sum(partial_costs) + sum(boundary_costs) <= threshold.
//                    The headline statement of the proof: total cycle cost is
//                    bounded.  partial_costs are taken as given here; they
//                    are bound to per-segment internal sums by sub-circuit G5
//                    and to the glue's published values by the verifier
//                    cross-check.
//
// Gate-count estimate (N=480, K=4, DEPTH=18):
//   G2 sort_via over N: ~4N = 1920 gates.
//   G3 K Poseidon2 hash chains: K*DEPTH*~264 ~ 19,000 gates.
//   G4 K+1 u64 additions + 1 comparison: O(64) gates.
//   Total ~21k gates -- dominated by sub-circuit cost at runtime.
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
    // boundary_siblings[i*DEPTH + d] is the level-d sibling for boundary i.
    // -------------------------------------------------------------------------
    boundary_siblings: [Field; K * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: LSB-first path bits for the same proofs.
    // -------------------------------------------------------------------------
    boundary_path_bits: [bool; K * DEPTH],

    // -------------------------------------------------------------------------
    // PUBLIC: concatenation of K sub-proofs' sorted_nodes arrays.
    // Length N.  Not yet globally sorted; G2 sorts it in-circuit.
    // -------------------------------------------------------------------------
    all_sorted_nodes: pub [u32; N],

    // -------------------------------------------------------------------------
    // PUBLIC: per-segment start nodes in segment order.
    // -------------------------------------------------------------------------
    starts: pub [u32; K],

    // -------------------------------------------------------------------------
    // PUBLIC: per-segment end nodes in segment order.
    // -------------------------------------------------------------------------
    ends: pub [u32; K],

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
) {
    // =========================================================================
    // G2 - Partition check: sort(all_sorted_nodes) == [0..N-1]
    // =========================================================================
    // The K segments' node sets must exactly partition {0..N-1}.  Sub-circuit
    // G2 only enforces in-segment sorting binding; only this check catches
    // cross-segment overlap (e.g., node 3 in two segments) or missing nodes.
    // sort_via gives the constrained non-decreasing sort; equality to i forces
    // both global distinctness and full coverage in one shot.
    let sorted = all_sorted_nodes.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..N {
        assert(sorted[i] == i as u32, "partition does not cover {0..N-1}");
    }

    // =========================================================================
    // G3 - Boundary Merkle proofs (K edges)
    // =========================================================================
    // For each boundary edge i in 0..K-1, two checks (structurally identical
    // to sub-circuit G4):
    //   (a) leaf_idx reconstruction (LSB-first) equals
    //       ends[i] * N + starts[(i+1) % K].
    //   (b) hash chain boundary_costs[i] -> root matches the committed root.
    // The wrap-around (i + 1) % K closes the K-1 -> 0 boundary.
    // Cost accumulation for G4 piggybacks here.
    let mut boundary_sum: u64 = 0;
    for i in 0..K {
        let from: u32 = ends[i];
        let to:   u32 = starts[(i + 1) % K];
        let expected_idx: u32 = from * N + to;

        // (a) Leaf-index reconstruction.
        let mut reconstructed_idx: u32 = 0;
        let mut pow2: u32 = 1;
        for d in 0..DEPTH {
            if boundary_path_bits[i * DEPTH + d] {
                reconstructed_idx += pow2;
            }
            pow2 *= 2;
        }
        assert(reconstructed_idx == expected_idx, "boundary path bits encode wrong leaf index");

        // (b) Hash chain up to the committed root.
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
    // G4 - Threshold check
    // =========================================================================
    // total = sum(partial_costs) + sum(boundary_costs) must be <= threshold.
    // partial_costs[i] are taken as given here; they are bound to per-segment
    // internal sums by sub-circuit G5 and to glue's published values by the
    // off-circuit verifier cross-check.
    let mut total: u64 = 0;
    for i in 0..K {
        total += partial_costs[i];
    }
    total += boundary_sum;
    assert(total <= threshold, "cycle cost exceeds threshold");
}
