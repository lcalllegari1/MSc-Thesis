/// Cross-validation: Rust Poseidon2 vs Noir Poseidon2 library
///
/// Verifies three things:
///   1. Smoke test: poseidon2_permutation([0,0,0,0]) matches the known vector
///      computed by nargo/bb at the same nargo release (v1.0.0-beta.20).
///   2. Two-input sponge: computes Poseidon2::hash([1, 2], 2) as Noir's poseidon
///      library would, and prints HASH_HEX so the shell harness can put it into
///      Prover.toml for the Noir circuit to assert.  (Merkle compression shape.)
///   3. Single-input sponge: computes Poseidon2::hash([c], 1) — the Variant A++
///      Fiat-Shamir challenge derivation — and prints SINGLE_IN + HASH_SINGLE_HEX
///      so the Noir circuit can assert it too.  This is the LOAD-BEARING hash for
///      A++ soundness; any Rust/Noir drift here breaks A++ silently, so it must be
///      cross-validated before the A++ circuits are written.
///
/// The binary also emits the full N=8, K=2 A++ reference table (chain h_0..h_8,
/// c, X, P_0, P_1, expected_product) and natively checks the grand-product
/// partition identity P_0 * P_1 == prod_{j=0..7}(X + j).  These values populate
/// HIER_FS_IMPL.md §11.
///
/// Sponge trace for hash(input, in_len), BN254 width-4, RATE=3:
///   iv    = in_len * 2^64
///   state = [in[0], in[1], ..., 0.., iv]   (rate slots filled, then capacity = iv)
///   hash  = permutation(state)[0]
/// For in_len=2: state = [left, right, 0, 2*2^64].
/// For in_len=1: state = [c,    0,     0, 1*2^64].
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

/// Two-input compression, matching Noir's Poseidon2::hash([left, right], 2).
///   iv = 2 * 2^64, state = [left, right, 0, iv], hash = permutation(state)[0].
/// Identical to pipeline/merkle_builder's poseidon2_compress (Merkle + A++ chain).
fn poseidon2_compress(left: FieldElement, right: FieldElement) -> FieldElement {
    let iv = FieldElement::from(2u128 * (1u128 << 64));
    let state = vec![left, right, FieldElement::zero(), iv];
    poseidon2_permutation(&state).expect("permutation failed")[0]
}

/// Single-input hash, matching Noir's Poseidon2::hash([c], 1).
///   iv = 1 * 2^64, state = [c, 0, 0, iv], hash = permutation(state)[0].
/// This is A++'s Fiat-Shamir challenge derivation X = Poseidon2(c).
fn poseidon2_hash_single(x: FieldElement) -> FieldElement {
    let iv = FieldElement::from(1u128 * (1u128 << 64));
    let state = vec![x, FieldElement::zero(), FieldElement::zero(), iv];
    poseidon2_permutation(&state).expect("permutation failed")[0]
}

fn main() {
    // ── 1. Smoke test ─────────────────────────────────────────────────────────
    let zeros = vec![FieldElement::zero(); 4];
    let perm = poseidon2_permutation(&zeros).expect("permutation failed");

    let mut smoke_ok = true;
    for (i, (got, want)) in perm.iter().zip(SMOKE_EXPECTED.iter()).enumerate() {
        if got.to_hex() != *want {
            eprintln!("SMOKE FAIL [{}]: got {} want {}", i, got.to_hex(), want);
            smoke_ok = false;
        }
    }
    if smoke_ok {
        eprintln!("SMOKE_TEST: OK");
    } else {
        eprintln!("SMOKE_TEST: FAIL");
        std::process::exit(1);
    }

    // ── 2. Two-input sponge hash of [1, 2] (Merkle compression shape) ──────────
    let two_input = poseidon2_compress(FieldElement::from(1u128), FieldElement::from(2u128));
    println!("HASH_HEX: {}", two_input.to_hex());

    // ── 3. A++ reference instance (N=8, K=2, M=4): chain, c, X, P_0, P_1 ───────
    // Cycle and edge costs match HIERARCHICAL_EXPLAINED.md §8.9 / §9.13.
    let cycle: [u64; 8] = [0, 5, 3, 2, 7, 4, 1, 6];

    // Hash chain: h_0 = 0, h_{j+1} = Poseidon2(h_j, cycle[j]) for j=0..7.  c = h_8.
    let mut h = [FieldElement::zero(); 9];
    for j in 0..8 {
        h[j + 1] = poseidon2_compress(h[j], FieldElement::from(cycle[j] as u128));
    }
    let c = h[8];

    // Fiat-Shamir challenge X = Poseidon2::hash([c], 1).
    let x = poseidon2_hash_single(c);

    // Per-segment grand products P_i = prod_j (X + cycle_segment_i[j]).
    let grand_product = |seg: &[u64]| -> FieldElement {
        let mut prod = FieldElement::one();
        for &node in seg {
            prod = prod * (x + FieldElement::from(node as u128));
        }
        prod
    };
    let p0 = grand_product(&cycle[0..4]); // {0,5,3,2}
    let p1 = grand_product(&cycle[4..8]); // {7,4,1,6}

    // expected_product = prod_{j=0..7}(X + j); the in-circuit RHS of glue G5.
    let mut expected = FieldElement::one();
    for j in 0u64..8 {
        expected = expected * (x + FieldElement::from(j as u128));
    }

    // Native partition identity: P_0 * P_1 == prod(X + j).  (Holds for ANY X when
    // the segment multisets tile {0..7}; this checks the partition math, NOT X.)
    let lhs = p0 * p1;
    let identity_ok = lhs == expected;

    // ── Emit the single-input cross-check inputs for the Noir circuit ──────────
    // single_in = c (a full-width Field, a strong test of the in_len=1 sponge);
    // expected1 = X = Poseidon2::hash([c], 1).
    println!("SINGLE_IN: {}", c.to_hex());
    println!("HASH_SINGLE_HEX: {}", x.to_hex());

    // ── Reference table (HIER_FS_IMPL.md §11) ──────────────────────────────────
    eprintln!("\n=== A++ reference values (N=8, K=2, M=4) ===");
    eprintln!("cycle = [0, 5, 3, 2, 7, 4, 1, 6]");
    for j in 0..9 {
        eprintln!("h_{} = 0x{}", j, h[j].to_hex());
    }
    eprintln!("c   = h_8 = 0x{}", c.to_hex());
    eprintln!("X   = Poseidon2([c],1) = 0x{}", x.to_hex());
    eprintln!("h_in_0  = 0x{}  (= h_0)", h[0].to_hex());
    eprintln!("h_out_0 = 0x{}  (= h_4 = h_in_1)", h[4].to_hex());
    eprintln!("h_out_1 = 0x{}  (= h_8 = c)", h[8].to_hex());
    eprintln!("P_0 = (X+0)(X+5)(X+3)(X+2) = 0x{}", p0.to_hex());
    eprintln!("P_1 = (X+7)(X+4)(X+1)(X+6) = 0x{}", p1.to_hex());
    eprintln!("expected_product = prod_(j=0..7)(X+j) = 0x{}", expected.to_hex());
    eprintln!("IDENTITY P_0*P_1 == expected_product: {}", if identity_ok { "OK" } else { "FAIL" });

    if !identity_ok {
        eprintln!("GRAND_PRODUCT_IDENTITY: FAIL");
        std::process::exit(1);
    }
    eprintln!("GRAND_PRODUCT_IDENTITY: OK");
}
