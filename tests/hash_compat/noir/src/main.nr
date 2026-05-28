// Cross-validation: Noir Poseidon2 vs Rust bn254_blackbox_solver Poseidon2
//
// The circuit replicates what poseidon::poseidon2::Poseidon2::hash(..) computes
// for two sponge shapes and asserts each equals the value produced by the Rust
// binary (forwarded into Prover.toml by the shell harness):
//
//   * Two-input  Poseidon2::hash([left, right], 2): Merkle compression shape,
//     also the A++ hash-chain step.  iv = 2 * 2^64, state = [left, right, 0, iv].
//   * Single-input Poseidon2::hash([single_in], 1): the A++ Fiat-Shamir
//     challenge derivation X = Poseidon2(c).  iv = 1 * 2^64, state = [c, 0, 0, iv].
//
// The single-input case is the load-bearing hash for Variant A++: the challenge X
// must be computed identically in Rust (off-circuit, in merkle_builder) and in
// Noir (in-circuit, sub-circuit G7 + glue G4).  Any drift breaks A++ soundness
// silently, so this assertion gates the A++ implementation.

use poseidon::poseidon2::Poseidon2;

fn main(
    left:      Field,
    right:     Field,
    expected2: pub Field, // == Poseidon2::hash([left, right], 2)
    single_in: Field,
    expected1: pub Field, // == Poseidon2::hash([single_in], 1)
) {
    let h2 = Poseidon2::hash([left, right], 2);
    assert(h2 == expected2, "Poseidon2 2-input mismatch: Noir and Rust differ");

    let h1 = Poseidon2::hash([single_in], 1);
    assert(h1 == expected1, "Poseidon2 1-input mismatch: Noir and Rust differ");
}
