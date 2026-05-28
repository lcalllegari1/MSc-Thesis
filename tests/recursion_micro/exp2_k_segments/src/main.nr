// =============================================================================
// Recursion micro-experiment 2 - outer circuit: "recursive A++" glue (any K>=2)
// =============================================================================
//
// Purpose: a COMPLETE recursive proof of a K-segment Hamiltonian cycle.  The
// outer circuit (1) recursively verifies all K hierarchical_segment_fs proofs
// in-circuit, then (2) re-runs the entire hierarchical_glue_fs logic with the
// per-segment values read from the verified inner proofs instead of from public
// inputs.  Because those values are inner-proof public inputs taken here as
// WITNESS, they never reach the outer proof's public surface.  Only (root,
// threshold) are exposed -- the same public surface as flat_merkle, i.e.
// perfect/information-theoretic hiding.  This is the equal-ground recursive
// counterpart of Variant A / A++ at the same K.
//
// Two purposes this serves:
//   * Cost scaling: K in-circuit verifications dominate (~7e5 gates each); the
//     glue logic below is tiny (~a few thousand gates), so total ~ K x Exp 1
//     plus a small glue tax.  Compare K=2 vs K=4 to see the ~K x aggregation
//     cost (the layer that dwarfs the actual TSP logic).
//   * Equal-ground vs A / A++ at the same K: identical statement (valid cycle,
//     cost <= threshold, against `root`), one proof, intermediates hidden.
//
// A lovely corollary (analysis transcript): once all segments' values are
// witness here, the grand-product + Fiat-Shamir machinery is hidden anyway --
// recursion would let us drop it.  We keep it so the proven statement is
// byte-for-byte the A++ statement (true equal-ground), not a simplified one.
//
// ZK path: verify_honk_proof + UltraHonkZKProof (len 458), matching `bb prove -t
// noir-recursive` on the inners.  ZK inners hide each segment's witness from the
// aggregator who runs THIS prover; the outer being a ZK proof hides everything
// from the final verifier.
//
// sub_pub layout (ABI/public-input-dump order of hierarchical_segment_fs):
//   [0] start_node   [1] end_node   [2] partial_cost   [3] root   [4] P_i
//   [5] h_in_i       [6] h_out_i    [7] c              [8] X
//
// Globals are patched per (N, K) by the driver.  DEPTH = ceil(log2(N*N)).
// All K segments share ONE circuit -> one VK -> one key_hash.
// =============================================================================

global N: u32 = 48;
global K: u32 = 4;
global DEPTH: u32 = 12;

use poseidon::poseidon2::Poseidon2;
use bb_proof_verification::{UltraHonkZKProof, UltraHonkVerificationKey, verify_honk_proof};

fn main(
    // -- PRIVATE (witness): shared VK + hash, and the K segment proofs ---------
    sub_vk:   UltraHonkVerificationKey,       // [Field; 115]
    key_hash: Field,
    proofs:   [UltraHonkZKProof; K],          // [[Field; 458]; K]
    sub_pubs: [[Field; 9]; K],                // K segments' public inputs

    // -- PRIVATE (witness): boundary-edge proof material (K edges) -------------
    boundary_costs:     [u64; K],
    boundary_siblings:  [Field; K * DEPTH],
    boundary_path_bits: [bool;  K * DEPTH],

    // -- PRIVATE (witness): integer mirrors of verified field values ----------
    // The inner public inputs arrive as Field; we need u32 for leaf indices and
    // u64 for the threshold sum.  Each is bound to its sub_pub Field below, so
    // the integers are not free -- they must equal the verified values.
    starts:        [u32; K],
    ends:          [u32; K],
    partial_costs: [u64; K],

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
        assert(starts[i]        as Field == sub_pubs[i][0], "start bind");
        assert(ends[i]          as Field == sub_pubs[i][1], "end bind");
        assert(partial_costs[i] as Field == sub_pubs[i][2], "pcost bind");
    }

    // =========================================================================
    // (3) Shared root / c / X across all segments
    // =========================================================================
    let c: Field = sub_pubs[0][7];
    let x: Field = sub_pubs[0][8];
    for i in 0..K {
        assert(sub_pubs[i][3] == root, "root mismatch");
        assert(sub_pubs[i][7] == c,    "c not shared");
        assert(sub_pubs[i][8] == x,    "X not shared");
    }

    // =========================================================================
    // (4) Hash-chain stitching (glue G1-G3): h_in_0==0, h_in_{i+1}==h_out_i,
    //     h_out_{K-1}==c.
    // =========================================================================
    assert(sub_pubs[0][5] == 0, "chain must start from 0");
    for i in 0..(K - 1) {
        assert(sub_pubs[i + 1][5] == sub_pubs[i][6], "chain not continuous");
    }
    assert(sub_pubs[K - 1][6] == c, "chain does not terminate at c");

    // =========================================================================
    // (5) Fiat-Shamir bind (glue G4): X == Poseidon2([c], 1)
    // =========================================================================
    assert(x == Poseidon2::hash([c], 1), "X != Poseidon2(c)");

    // =========================================================================
    // (6) Grand-product partition (glue G5): prod_i P_i == prod_{j=0..N-1}(X + j)
    // =========================================================================
    let mut lhs: Field = 1;
    for i in 0..K {
        lhs = lhs * sub_pubs[i][4];
    }
    let mut rhs: Field = 1;
    for j in 0..N {
        rhs = rhs * (x + j as Field);
    }
    assert(lhs == rhs, "grand-product partition mismatch");

    // =========================================================================
    // (7) Boundary Merkle proofs (glue G6): K edges ends[i] -> starts[(i+1)%K]
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
    // (8) Threshold (glue G7)
    // =========================================================================
    let mut total: u64 = boundary_sum;
    for i in 0..K {
        total += partial_costs[i];
    }
    assert(total <= threshold, "cycle cost exceeds threshold");
}
