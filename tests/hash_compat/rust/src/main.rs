/// Cross-validation: Rust Poseidon2 vs Noir Poseidon2 library
///
/// Verifies two things:
///   1. Smoke test: poseidon2_permutation([0,0,0,0]) matches the known vector
///      computed by nargo/bb at the same nargo release (v1.0.0-beta.20).
///   2. Sponge hash: computes Poseidon2::hash([1, 2], 2) as Noir's poseidon
///      library would, and prints the hex so the shell harness can put it into
///      Prover.toml for the Noir circuit to assert.
///
/// The sponge trace for hash([left, right], in_len=2):
///   iv    = in_len * 2^64 = 2 * 2^64
///   state = [left, right, 0, iv]   (partial fill, no full-rate chunk)
///   hash  = permutation(state)[0]
use acir::{AcirField, FieldElement};
use bn254_blackbox_solver::poseidon2_permutation;

/// Known output of poseidon2_permutation([0,0,0,0]) for BN254, width-4.
/// Produced by nargo/bb at v1.0.0-beta.20; used as a smoke test.
const SMOKE_EXPECTED: [&str; 4] = [
    "18dfb8dc9b82229cff974efefc8df78b1ce96d9d844236b496785c698bc6732e",
    "095c230d1d37a246e8d2d5a63b165fe0fade040d442f61e25f0590e5fb76f839",
    "0bb9545846e1afa4fa3c97414a60a20fc4949f537a68cceca34c5ce71e28aa59",
    "18a4f34c9c6f99335ff7638b82aeed9018026618358873c982bbdde265b2ed6d",
];

fn main() {
    // ── Smoke test ────────────────────────────────────────────────────────────
    let zeros = vec![FieldElement::zero(); 4];
    let perm = poseidon2_permutation(&zeros).expect("permutation failed");

    let mut smoke_ok = true;
    for (i, (got, want)) in perm.iter().zip(SMOKE_EXPECTED.iter()).enumerate() {
        let got_hex = got.to_hex();
        if got_hex != *want {
            eprintln!("SMOKE FAIL [{}]: got {} want {}", i, got_hex, want);
            smoke_ok = false;
        }
    }
    if smoke_ok {
        eprintln!("SMOKE_TEST: OK");
    } else {
        eprintln!("SMOKE_TEST: FAIL");
        std::process::exit(1);
    }

    // ── Sponge hash of [1, 2] ─────────────────────────────────────────────────
    // Matches poseidon::poseidon2::Poseidon2::hash([1, 2], 2) in Noir.
    //
    // Sponge trace (RATE=3, N=2, in_len=2):
    //   iv    = 2 * 2^64
    //   state = [0, 0, 0, iv]
    //   partial fill: state[0] += 1, state[1] += 2  (no full-rate chunk)
    //   state = [1, 2, 0, iv]
    //   final permute (because in_len % RATE != 0)
    //   hash  = state[0]
    let left: FieldElement = FieldElement::from(1u128);
    let right: FieldElement = FieldElement::from(2u128);
    // iv = 2 * 2^64; both operands fit in u128
    let iv: FieldElement = FieldElement::from(2u128 * (1u128 << 64));

    let state = vec![left, right, FieldElement::zero(), iv];
    let result = poseidon2_permutation(&state).expect("permutation failed");
    let hash_hex = result[0].to_hex();

    // Print in a format the shell harness can grep
    println!("HASH_HEX: {}", hash_hex);
}
