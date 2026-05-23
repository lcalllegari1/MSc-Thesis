// Cross-validation: Noir Poseidon2 vs Rust bn254_blackbox_solver Poseidon2
//
// The circuit replicates what poseidon::poseidon2::Poseidon2::hash([left, right], 2)
// computes and asserts the result equals the value produced by the Rust binary.
//
// Public input `expected` is supplied from Prover.toml by the shell harness,
// which runs the Rust binary first and forwards its output.
//
// Sponge trace for hash([left, right], in_len=2):
//   RATE=3, N=2 (compile-time), in_len=2
//   iv    = 2 * 2^64 (= 36893488147419103232)
//   No full-rate chunk (N/RATE = 0), partial fill: state[0..2] += [left, right, 0]
//   Final permute (in_len % RATE != 0)
//   hash = permuted_state[0]
//
// The assert fires if the Rust implementation disagrees with Noir, proving they
// share the same Poseidon2 parameterisation on BN254.

use poseidon::poseidon2::Poseidon2;

fn main(
    left:     Field,
    right:    Field,
    expected: pub Field,
) {
    let hash = Poseidon2::hash([left, right], 2);
    assert(hash == expected, "Poseidon2 mismatch: Noir and Rust outputs differ");
}
