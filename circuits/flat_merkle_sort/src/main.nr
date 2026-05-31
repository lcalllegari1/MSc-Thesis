// =============================================================================
// TSP Hamiltonian Cycle ZKP - Flat / Merkle Commitment / Sort-based Permutation Check
// =============================================================================
//
// What we prove:
//   "I know a Hamiltonian cycle on a complete weighted graph G of N nodes,
//    where the edge costs are committed to by a Poseidon2 Merkle root,
//    and the total cycle cost <= threshold T."
//
// Public inputs (the verifier knows these):
//   root      - Poseidon2 Merkle root of the N*N cost matrix (flattened row-major)
//   threshold - the declared upper bound on cycle cost
//
// Private witness (only the prover knows this):
//   cycle      - the ordered sequence of N node indices forming the cycle.
//                The closing edge is implicit: cycle[N-1] -> cycle[0].
//   edge_costs - the cost of each of the N directed edges in the cycle.
//                edge_costs[i] = cost_matrix[cycle[i]][cycle[(i+1)%N]].
//   siblings   - Merkle sibling hashes for all N edge proofs, flat row-major.
//                siblings[i*DEPTH .. (i+1)*DEPTH-1] are the DEPTH siblings
//                for edge i, ordered from leaf level (d=0) up to just below
//                the root (d=DEPTH-1).
//   path_bits  - path direction bits for all N edge proofs, flat row-major.
//                path_bits[i*DEPTH + d] = true  means edge i is a right child
//                                               at tree level d (sibling is left)
//                                       = false means edge i is a left child
//                                               at tree level d (sibling is right)
//                LSB-first encoding: leaf_idx = sum(path_bits[i*DEPTH+d] * 2^d,
//                                                   d = 0..DEPTH-1)
//
// Design choice - "Flat-Merkle":
//   The cost matrix is NOT passed as N^2 public inputs. Instead, the verifier
//   receives only the Poseidon2 Merkle root that commits to the entire matrix.
//   This reduces public input cost from O(N^2) to O(1), but adds O(N*DEPTH)
//   Poseidon2 calls in GROUP 3 -- one per edge level of each proof.
//
//   Crossover analysis: the N^2 public-input cost (7.25 gates per element)
//   dominates at large N; the O(N * DEPTH) = O(N * log N) Merkle cost grows
//   slower.  The estimated crossover is N ~400-600, beyond the N in {5..100}
//   benchmark range.  This circuit is benchmarked to measure the hash-overhead
//   constant and enable extrapolation of the crossover point.
//
// Merkle tree structure:
//   Leaves: flat_matrix[0..N^2-1], padded with zeros to the next power of 2.
//   leaf[from*N + to] = cost of directed edge from -> to.
//   Internal nodes: parent = Poseidon2::hash([left_child, right_child], 2).
//   DEPTH = ceil(log2(N^2)).  Examples: N=5->DEPTH=5, N=50->DEPTH=12.
//
//   Both N and DEPTH are compile-time globals.  The benchmark harness patches
//   both in src/main.nr and recompiles for each value of N under test.
//
// Soundness argument for GROUP 3 (why a cheating prover cannot fake edge costs):
//   1. `root` is a public input fixed by the verifier (once the matrix is known
//       and fixed) -- unalterable by the prover.
//   2. Poseidon2 collision resistance: producing the correct root from a wrong
//      leaf value requires inverting Poseidon2 (computationally infeasible).
//   3. Leaf index check: path_bits must reconstruct to exactly
//      cycle[i]*N + cycle[(i+1)%N], preventing the prover from using a proof
//      for a different leaf that might carry a more convenient cost.
//   Together, (2) and (3) force edge_costs[i] == cost_matrix[cycle[i]][cycle[(i+1)%N]].
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
//   full permutation proof.
//
//   Note: the explicit GROUP 1 range check present in flat_merkle_presence
//   is not needed here.  If sorted == [0,...,N-1] and sorted is proven to
//   be a permutation of cycle, the multiset of cycle must equal {0,...,N-1},
//   which implies every entry is already in range.
//
// Design choices shared with flat_full_sort:
//   GROUP 2 is identical (same sort-based permutation check; no explicit
//   GROUP 1 since the range check is subsumed by the sort argument).
//   GROUP 4 is identical (same threshold assertion).
//   Only GROUP 3 differs: flat_full_sort reads edge costs via a direct
//   dynamic ROM lookup into the public cost matrix, while this circuit
//   uses N Merkle proofs to bind each edge cost to the committed root.
//
// Instance size:
//   N and DEPTH are compile-time globals.  The benchmark harness patches both
//   and recompiles for each value of N.
// =============================================================================

global N: u32 = 1000;
global DEPTH: u32 = 20;

use poseidon::poseidon2::Poseidon2;

fn main(
    // -------------------------------------------------------------------------
    // PRIVATE: the Hamiltonian cycle.
    // cycle[i] is the i-th node visited (zero-indexed).
    // Positions 0..N-1 cover all N nodes; the edge cycle[N-1] -> cycle[0] is
    // the return edge closing the cycle. NOT stored explicitly.
    // -------------------------------------------------------------------------
    cycle: [u32; N],

    // -------------------------------------------------------------------------
    // PRIVATE: cost of each directed edge in the cycle.
    // edge_costs[i] = cost_matrix[cycle[i]][cycle[(i+1)%N]].
    // The prover computes these from the cost matrix off-circuit.
    // GROUP 3 binds each value to the committed matrix via the Merkle proof.
    // -------------------------------------------------------------------------
    edge_costs: [u64; N],

    // -------------------------------------------------------------------------
    // PRIVATE: Merkle sibling hashes, flat row-major over N edge proofs.
    // siblings[i*DEPTH + d] is the sibling at level d for edge i's proof.
    // Ordering: leaf level d=0 first, just-below-root d=DEPTH-1 last.
    // -------------------------------------------------------------------------
    siblings: [Field; N * DEPTH],

    // -------------------------------------------------------------------------
    // PRIVATE: Merkle path direction bits, flat row-major over N edge proofs.
    // path_bits[i*DEPTH + d] = true  => edge i is a right child at level d
    //                        = false => edge i is a left child  at level d
    // LSB-first: leaf_idx = sum(path_bits[i*DEPTH+d] * 2^d, d=0..DEPTH-1).
    // The prover supplies these; the leaf index check in GROUP 3 verifies them.
    // -------------------------------------------------------------------------
    path_bits: [bool; N * DEPTH],

    // -------------------------------------------------------------------------
    // PUBLIC: Poseidon2 Merkle root of the N*N cost matrix, flattened row-major.
    // The verifier computes this from the agreed cost matrix and supplies it.
    // All N Merkle proofs in GROUP 3 must hash up to this root.
    // -------------------------------------------------------------------------
    root: pub Field,

    // -------------------------------------------------------------------------
    // PUBLIC: cost upper bound.
    // The prover claims the cycle costs at most this much.
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
    // CONSTRAINT GROUP 3 - Merkle proof verification + cost accumulation
    // =========================================================================
    // For each of the N edges in the cycle, three steps:
    //
    //   a. Leaf index check:
    //      Reconstruct the leaf index from path_bits (LSB-first) and assert it
    //      equals the expected index cycle[i]*N + cycle[(i+1)%N].
    //      This is the load-bearing soundness check: without it, a prover could
    //      substitute a valid proof for a different leaf that carries a more
    //      convenient cost value.
    //
    //   b. Merkle path verification:
    //      Start from edge_costs[i] (cast to Field) and hash upward through
    //      DEPTH levels.  At each level d, path_bits[i*DEPTH+d] determines
    //      whether the current hash is a left child (false) or right child
    //      (true) of its parent.  The final hash must equal `root`.
    //      This binds edge_costs[i] to the committed value at that leaf.
    //
    //   c. Cost accumulation:
    //      Add the verified edge cost to total_cost.
    //
    // Cost analysis:
    //   N and DEPTH are comptime globals, so both inner loops unroll fully at
    //   compile time.  The siblings/path_bits accesses at index i*DEPTH+d are
    //   static (comptime index), not dynamic ROM lookups.  The Poseidon2 calls
    //   are the dominant cost: N * DEPTH calls * ~264 gates each = O(N*log N).
    //   The leaf index reconstruction adds O(N*DEPTH) cheap arithmetic gates.
    let mut total_cost: u64 = 0;

    for i in 0..N {
        let from: u32 = cycle[i];
        let to: u32 = cycle[(i + 1) % N]; // comptime index: wraps to 0 at i=N-1

        // a. Leaf index check 
        // The path bits encode the leaf index in LSB-first order:
        //   leaf_idx = path_bits[d=0]*1 + path_bits[d=1]*2 + ... + path_bits[d=DEPTH-1]*2^(DEPTH-1)
        // Reconstruct and assert it equals the expected matrix index.
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

        // b. Merkle path verification 
        // Hash the raw cost value upward through DEPTH siblings.
        // At each level d, path_bits selects left/right child ordering.
        let mut current: Field = edge_costs[i] as Field;
        for d in 0..DEPTH {
            let sibling: Field = siblings[i * DEPTH + d];
            let (left, right) = if path_bits[i * DEPTH + d] {
                (sibling, current) // current is right child; sibling goes left
            } else {
                (current, sibling) // current is left child; sibling goes right
            };
            current = Poseidon2::hash([left, right], 2);
        }
        assert(current == root, "Merkle proof does not match committed root");

        // c. Cost accumulation
        total_cost += edge_costs[i];
    }

    // =========================================================================
    // CONSTRAINT GROUP 4 - Threshold check
    // =========================================================================
    // Identical to flat_full_sort.
    // u64 comparison decomposes into a range check on the difference,
    // costing O(64) boolean gates regardless of the actual cost values.
    assert(total_cost <= threshold, "cycle cost exceeds threshold");
}
