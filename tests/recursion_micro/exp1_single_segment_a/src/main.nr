// =============================================================================
// Recursion micro-experiment 1 (A-INNER) - verify ONE Variant A segment proof
// =============================================================================
//
// Counterpart of exp1_single_segment, but the inner is the Variant A sub-circuit
// (circuits/hierarchical_segment) instead of A++.  Purpose: isolate the cost of
// one in-circuit ZK verification when the inner exposes an O(M) public surface.
//
// A sub_pub layout (ABI/public-input-dump order of hierarchical_segment):
//   [0 .. M-1]  sorted_nodes (segment node set, ascending)
//   [M]         start_node
//   [M+1]       end_node
//   [M+2]       partial_cost
//   [M+3]       root
//
// vs A++'s fixed 9-field vector -- so the recursive verifier here absorbs M+4
// public inputs per proof rather than 9.  M is patched per (N, K) by the driver.
// =============================================================================

global M: u32 = 4;

use bb_proof_verification::{UltraHonkZKProof, UltraHonkVerificationKey, verify_honk_proof};

fn main(
    // -- PRIVATE (witness): the segment proof, its VK, and the VK hash --------
    verification_key: UltraHonkVerificationKey, // [Field; 115]
    proof:            UltraHonkZKProof,          // [Field; 458]
    key_hash:         Field,

    // -- PRIVATE (witness): the A segment's M+4 public inputs -----------------
    sub_pub: [Field; M + 4],

    // -- PUBLIC: the only thing the outer verifier learns ---------------------
    root: pub Field,
) {
    verify_honk_proof(verification_key, proof, sub_pub, key_hash);
    assert(sub_pub[M + 3] == root, "segment root mismatch");
}
