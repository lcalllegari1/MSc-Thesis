// =============================================================================
// TSP Hamiltonian Cycle ZKP - Flat / Merkle Commitment / Grand-Product Perm Check
// =============================================================================
//
// What we prove (identical statement to flat_merkle_sort):
//   "I know a Hamiltonian cycle on a complete weighted graph G of N nodes,
//    where the edge costs are committed to by a Poseidon2 Merkle root,
//    and the total cycle cost <= threshold T."
//
// Public inputs:
//   root      - Poseidon2 Merkle root of the N*N cost matrix (flattened row-major)
//   threshold - declared upper bound on cycle cost
//
// Private witness (IDENTICAL to flat_merkle_sort -- same Prover.toml):
//   cycle, edge_costs, siblings, path_bits.
//
// Only difference from flat_merkle_sort: GROUP 2 (the permutation check).  Here
// it is a grand-product / multiset-equality argument with an IN-CIRCUIT
// Fiat-Shamir challenge, instead of an in-circuit sort.  GROUP 3 (Merkle edge
// proofs) and GROUP 4 (threshold) are byte-for-byte the same.  This is the flat,
// monolithic instance of the same grand-product gadget used by the hierarchical
// A++ segment (circuits/hierarchical_segment_fs) and the recursion outer
// (circuits/recursion) -- i.e. "A++ collapsed to K=1".  It completes the
// {flat, recursive} x {sort, grand-product} comparison grid (see
// NARRATIVE_FRAMING.md sec. 7-8): flat_merkle_sort and flat_merkle_grand_product
// share the SAME public surface {root, threshold}, so the pair isolates the
// permutation-mechanism cost (sort vs grand-product) with zero privacy delta.
//
// MEASURED (NARRATIVE_FRAMING.md sec. 8.5): this circuit has MORE constraints than
// flat_merkle_sort (+3.5..7.9%, the O(N) Fiat-Shamir hash chain; delta shrinks as the
// shared O(N*DEPTH) Merkle group grows) yet solves its witness FASTER (-17..-44% at
// large N).  Reason: GROUP 2 here is straight-line, statically-indexed arithmetic, so
// the witness solver does no dynamic-memory work; flat_merkle_sort's check_shuffle
// instead resolves ~2N data-dependent (dynamic-ROM) array reads at solve time.  Both
// land in the SAME UltraHonk dyadic (next-power-of-two) bucket, so prove time, peak
// memory, and proof size (14656 B) are identical -- only witness solving sees the delta.
//
// GROUP 2 soundness (why a cheating prover cannot fake a non-permutation):
//   Let P(Y) = prod_i (Y + cycle[i]) and Q(Y) = prod_{j=0}^{N-1} (Y + j).  Since
//   (Y + .) is a bijection, P == Q as polynomials IFF the multiset {cycle[i]}
//   equals {0,...,N-1} -- i.e. every node exactly once, all in range (so, as in
//   the sort variant, no explicit GROUP 1 range check is needed).  The circuit
//   tests the identity at ONE point X.  For a wrong multiset, D = P - Q is a
//   nonzero polynomial of degree <= N-1, so it has <= N-1 roots; the forgery
//   passes only if X is one of them.  X is NOT a free input: it is derived
//   in-circuit from the cycle via a Poseidon2 hash chain (X = Poseidon2([c],1),
//   c = h_N, h_{j+1} = Poseidon2([h_j, cycle[j]],2)).  Modelling Poseidon2 as a
//   random oracle, X is a uniform field element fixed by the committed cycle, so
//   a wrong-multiset prover hits a bad root with probability <= (N-1)/|F| per
//   attempt (~2^-246), negligible.  The load-bearing property: the SAME `cycle`
//   array feeds both the hash chain and the product, so X cannot be derived from
//   one transcript and the product run over another.
//
//   Flat vs hierarchical/recursive: here the challenge is derived and consumed in
//   ONE circuit over ONE witness, so the binding is automatic.  In the A++
//   segment the same X must be SHARED across K independent proofs, which needs
//   the published h_in/h_out/c/X anchors + glue stitching to reassemble one
//   global challenge from separate provers; recursion enforces that stitching
//   in-circuit and adds the in-circuit proof-verifier's own Fiat-Shamir on top.
//
// Merkle tree structure / GROUP 3 soundness: see flat_merkle_sort/src/main.nr.
// DEPTH = ceil(log2(N*N)).  Both N and DEPTH are compile-time globals, patched
// by the benchmark harness (pipeline/run.py) per N.
// =============================================================================

global N: u32 = 4000;
global DEPTH: u32 = 24;

use poseidon::poseidon2::Poseidon2;

fn main(
    // PRIVATE: the Hamiltonian cycle (i-th node visited, zero-indexed).
    // The closing edge cycle[N-1] -> cycle[0] is implicit.
    cycle: [u32; N],

    // PRIVATE: cost of each directed edge in the cycle.
    // edge_costs[i] = cost_matrix[cycle[i]][cycle[(i+1)%N]].
    edge_costs: [u64; N],

    // PRIVATE: Merkle sibling hashes, flat row-major over N edge proofs.
    // siblings[i*DEPTH + d] is the level-d sibling for edge i (d=0 leaf level).
    siblings: [Field; N * DEPTH],

    // PRIVATE: Merkle path direction bits, flat row-major over N edge proofs.
    // path_bits[i*DEPTH + d] = true => edge i is a right child at level d.
    // LSB-first: leaf_idx = sum(path_bits[i*DEPTH+d] * 2^d, d=0..DEPTH-1).
    path_bits: [bool; N * DEPTH],

    // PUBLIC: Poseidon2 Merkle root of the N*N cost matrix (row-major).
    root: pub Field,

    // PUBLIC: cost upper bound.
    threshold: pub u64,
) {
    // =========================================================================
    // CONSTRAINT GROUP 2 - Grand-product permutation check (in-circuit Fiat-Shamir)
    // =========================================================================
    // (a) Derive the challenge X from the WHOLE cycle so the prover cannot pick
    //     the cycle after seeing X.  Same hash shape as the Merkle step:
    //     h_0 = 0; h_{j+1} = Poseidon2([h_j, cycle[j]], 2); c = h_N;
    //     X = Poseidon2([c], 1).
    let mut h: Field = 0;
    for j in 0..N {
        h = Poseidon2::hash([h, cycle[j] as Field], 2);
    }
    let c: Field = h;
    let x: Field = Poseidon2::hash([c], 1);

    // (b) Multiset equality via grand product:
    //     prod_i (X + cycle[i]) == prod_j (X + j),  j = 0..N-1.
    //     Equal iff {cycle} == {0,...,N-1} as multisets (see header soundness
    //     note); this subsumes the range check.
    let mut lhs: Field = 1;
    for i in 0..N {
        lhs = lhs * (x + cycle[i] as Field);
    }
    let mut rhs: Field = 1;
    for j in 0..N {
        rhs = rhs * (x + j as Field);
    }
    assert(lhs == rhs, "cycle is not a permutation of {0,...,N-1}");

    // =========================================================================
    // CONSTRAINT GROUP 3 - Merkle proof verification + cost accumulation
    // =========================================================================
    // Identical to flat_merkle_sort: for each edge, (a) reconstruct the leaf
    // index from path_bits and assert it == cycle[i]*N + cycle[(i+1)%N], (b) hash
    // edge_costs[i] upward through DEPTH siblings and assert the result == root,
    // (c) accumulate the cost.
    let mut total_cost: u64 = 0;

    for i in 0..N {
        let from: u32 = cycle[i];
        let to: u32 = cycle[(i + 1) % N]; // comptime index: wraps to 0 at i=N-1

        // a. Leaf index check
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
        let mut current: Field = edge_costs[i] as Field;
        for d in 0..DEPTH {
            let sibling: Field = siblings[i * DEPTH + d];
            let (left, right) = if path_bits[i * DEPTH + d] {
                (sibling, current)
            } else {
                (current, sibling)
            };
            current = Poseidon2::hash([left, right], 2);
        }
        assert(current == root, "Merkle proof does not match committed root");

        // c. Cost accumulation
        total_cost += edge_costs[i];
    }

    // =========================================================================
    // CONSTRAINT GROUP 4 - Threshold check (identical to flat_merkle_sort)
    // =========================================================================
    assert(total_cost <= threshold, "cycle cost exceeds threshold");
}
