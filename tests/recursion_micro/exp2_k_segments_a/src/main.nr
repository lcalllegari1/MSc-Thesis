// =============================================================================
// Recursion micro-experiment 2 (A-INNER) - "recursive Variant A" glue (any K>=2)
// =============================================================================
//
// Counterpart of exp2_k_segments, but the inner is the Variant A sub-circuit
// (hierarchical_segment) and the partition is checked Variant-A style: a
// deterministic SORT over the concatenated segment node sets, asserting
// == [0..N-1].  No Fiat-Shamir, no grand product, no hash chain -- the A sub
// exposes each segment's sorted node set, so once all K are verified and held as
// witness the outer can check the partition directly.  Exposes only
// (root, threshold) -> perfect/information-theoretic hiding, same as the A++
// variant; the design difference (deterministic sort + O(M) public surface vs
// grand-product + Fiat-Shamir + O(1) surface) is what compare_inner.py measures.
//
// A sub_pub layout (ABI/public-input-dump order of hierarchical_segment):
//   [0 .. M-1]  sorted_nodes (segment node set, ascending)
//   [M]         start_node   [M+1] end_node   [M+2] partial_cost   [M+3] root
//
// Globals patched per (N, K) by the driver.  M = N/K; DEPTH = ceil(log2(N*N)).
// All K segments share ONE A circuit -> one VK -> one key_hash.
// =============================================================================

global N: u32 = 8;
global K: u32 = 2;
global M: u32 = 4;
global DEPTH: u32 = 6;

use poseidon::poseidon2::Poseidon2;
use bb_proof_verification::{UltraHonkZKProof, UltraHonkVerificationKey, verify_honk_proof};

fn main(
    // -- PRIVATE (witness): shared VK + hash, and the K segment proofs ---------
    sub_vk:   UltraHonkVerificationKey,       // [Field; 115]
    key_hash: Field,
    proofs:   [UltraHonkZKProof; K],          // [[Field; 458]; K]
    sub_pubs: [[Field; M + 4]; K],            // K segments' public inputs (M+4 each)

    // -- PRIVATE (witness): boundary-edge proof material (K edges) -------------
    boundary_costs:     [u64; K],
    boundary_siblings:  [Field; K * DEPTH],
    boundary_path_bits: [bool;  K * DEPTH],

    // -- PRIVATE (witness): integer mirrors of verified field values ----------
    // Bound to the sub_pub fields below (widening u->Field casts + equality, so
    // they are not free).  all_nodes is the concatenation of the K node sets,
    // used for the sort-partition.
    starts:        [u32; K],
    ends:          [u32; K],
    partial_costs: [u64; K],
    all_nodes:     [u32; N],

    // -- PUBLIC: the entire outer public surface (== flat_merkle) -------------
    root:      pub Field,
    threshold: pub u64,
) {
    // =========================================================================
    // (1) Recursive verification of all K segment proofs
    // =========================================================================
    for i in 0..K {
        verify_honk_proof(sub_vk, proofs[i], sub_pubs[i], key_hash);
    }

    // =========================================================================
    // (2) Bind integer mirrors to the (now trusted) verified field values
    // =========================================================================
    for i in 0..K {
        assert(starts[i]        as Field == sub_pubs[i][M],     "start bind");
        assert(ends[i]          as Field == sub_pubs[i][M + 1], "end bind");
        assert(partial_costs[i] as Field == sub_pubs[i][M + 2], "pcost bind");
        assert(sub_pubs[i][M + 3] == root,                      "root mismatch");
        // sorted_nodes[i][j] -> all_nodes[i*M + j]
        for j in 0..M {
            assert(all_nodes[i * M + j] as Field == sub_pubs[i][j], "node bind");
        }
    }

    // =========================================================================
    // (3) Partition (Variant A glue G2): sort(all_nodes) == [0..N-1]
    // =========================================================================
    // Each segment's nodes are already sorted within the segment (A sub G2); the
    // global sort + equality to i forces both cross-segment distinctness and full
    // coverage of {0..N-1}.  Deterministic -- no Fiat-Shamir / Schwartz-Zippel.
    let sorted = all_nodes.sort_via(|a: u32, b: u32| a <= b);
    for i in 0..N {
        assert(sorted[i] == i as u32, "partition does not cover {0..N-1}");
    }

    // =========================================================================
    // (4) Boundary Merkle proofs (glue G3): K edges ends[i] -> starts[(i+1)%K]
    // =========================================================================
    let mut boundary_sum: u64 = 0;
    for i in 0..K {
        let from: u32 = ends[i];
        let to:   u32 = starts[(i + 1) % K];
        let expected_idx: u32 = from * N + to;

        let mut recon: u32 = 0;
        let mut pow2:  u32 = 1;
        for d in 0..DEPTH {
            if boundary_path_bits[i * DEPTH + d] {
                recon += pow2;
            }
            pow2 *= 2;
        }
        assert(recon == expected_idx, "boundary path bits encode wrong leaf index");

        let mut current: Field = boundary_costs[i] as Field;
        for d in 0..DEPTH {
            let sib: Field = boundary_siblings[i * DEPTH + d];
            let (l, r) = if boundary_path_bits[i * DEPTH + d] {
                (sib, current)
            } else {
                (current, sib)
            };
            current = Poseidon2::hash([l, r], 2);
        }
        assert(current == root, "boundary Merkle proof does not match committed root");

        boundary_sum += boundary_costs[i];
    }

    // =========================================================================
    // (5) Threshold (glue G4)
    // =========================================================================
    let mut total: u64 = boundary_sum;
    for i in 0..K {
        total += partial_costs[i];
    }
    assert(total <= threshold, "cycle cost exceeds threshold");
}
