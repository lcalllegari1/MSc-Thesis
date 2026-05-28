// =============================================================================
// Recursion micro-experiment 1 - outer circuit: verify ONE segment proof
// =============================================================================
//
// Purpose: isolate the cost of recursively verifying a single
// hierarchical_segment_fs proof (the Variant A++ sub-circuit) in-circuit.  The
// `bb gates` count of THIS circuit is the per-segment recursion overhead the
// thesis frontier needs (the "~10^5-10^6 gates of non-native field arithmetic"
// number).  Because the in-circuit Honk verifier verifies a fixed-size proof
// (458 fields) against a fixed-size VK (115 fields), this cost is essentially
// independent of the inner segment's own size (N, M, DEPTH).
//
// ZK path (NOT the toy's non_zk path): we use `verify_honk_proof` with
// UltraHonkZKProof (RECURSIVE_ZK_PROOF_LENGTH = 458), matching `bb prove -t
// noir-recursive` on the inner.  The library comment is explicit that ZK is the
// intended default; `verify_honk_proof_non_zk` is the opt-out.
//
// Privacy shape: the inner segment's 9 public inputs are taken here as WITNESS
// (not pub), so they never appear on the outer proof's public surface.  Only
// `root` is exposed -- a meaningful statement ("a valid segment exists against
// this committed matrix") with none of A++'s per-segment leakage (P_i, chain
// anchors, endpoints).  For the outer proof to actually HIDE that witness it
// must itself be a ZK proof; `bb prove` produces one.
//
// sub_pub layout (ABI/public-input-dump order of hierarchical_segment_fs):
//   [0] start_node   [1] end_node   [2] partial_cost   [3] root   [4] P_i
//   [5] h_in_i       [6] h_out_i    [7] c              [8] X
// =============================================================================

use bb_proof_verification::{UltraHonkZKProof, UltraHonkVerificationKey, verify_honk_proof};

fn main(
    // -- PRIVATE (witness): the segment proof, its VK, and the VK hash --------
    verification_key: UltraHonkVerificationKey, // [Field; 115]
    proof:            UltraHonkZKProof,          // [Field; 458]
    key_hash:         Field,

    // -- PRIVATE (witness): the segment's 9 public inputs ---------------------
    // Verified against the proof by verify_honk_proof, but never exposed.
    sub_pub: [Field; 9],

    // -- PUBLIC: the only thing the outer verifier learns ---------------------
    root: pub Field,
) {
    // Recursive verification: unsatisfiable unless `proof` is a valid ZK
    // UltraHonk proof of hierarchical_segment_fs for public inputs `sub_pub`.
    verify_honk_proof(verification_key, proof, sub_pub, key_hash);

    // Bind the exposed root to the (now trusted, still private) segment root.
    assert(sub_pub[3] == root, "segment root mismatch");
}
