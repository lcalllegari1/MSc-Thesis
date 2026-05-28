use bb_proof_verification::{
    UltraHonkProof,
    UltraHonkVerificationKey,
    verify_honk_proof_non_zk,
};

// Recursive verifier for the inner circuit (x^2 == y).
// Inputs are the serialised proof and VK produced by
//   bb prove -t noir-recursive-no-zk --output_format json
//   bb write_vk -t noir-recursive-no-zk --output_format json
//
// public_inputs has length 1: the single public output y of the inner circuit.
fn main(
    verification_key: UltraHonkVerificationKey,
    proof:            UltraHonkProof,
    public_inputs:    pub [Field; 1],
    key_hash:         Field,
) {
    verify_honk_proof_non_zk(verification_key, proof, public_inputs, key_hash);
}
