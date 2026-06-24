# Merkle Leaf Design: Raw Cost Leaves vs Hashed Leaves

This note records the Merkle-tree design used for the committed cost matrix, the
main alternatives, and the justification for the current choice.

## Short Answer

The implementation uses **raw cost values as Merkle leaves**. Costs are not hashed
before the tree is built.

```rust
// export/pipeline/merkle_builder/src/main.rs
for (k, &cost) in leaves.iter().enumerate() {
    nodes[n_padded + k] = FieldElement::from(cost as u128);
}

for i in (1..n_padded).rev() {
    nodes[i] = poseidon2_compress(nodes[2 * i], nodes[2 * i + 1]);
}
```

So the bottom tree layer is:

```text
parent = H(cost_left, cost_right)
```

not:

```text
parent = H(H(cost_left), H(cost_right))
```

The Noir verifier matches this: it starts the Merkle proof from the raw private
edge cost and hashes upward through the siblings.

```noir
// export/circuits/monolithic_committed_sort/src/main.nr
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
```

This saves one Poseidon2 hash per opened edge.

## What the Merkle Check Must Prove

For each edge used by the hidden TSP cycle, the circuit must prove two separate
facts:

1. **Membership:** the supplied private cost is part of the matrix committed by
   the public Merkle root.
2. **Address binding:** that cost is at the exact matrix entry for the edge being
   charged, not at some cheaper entry elsewhere.

The matrix is flattened row-major:

```text
cost(from, to) is stored at leaf index from * N + to
```

The implementation handles the two obligations separately.

Membership is the Merkle path:

```text
edge_cost + siblings -> root
```

Address binding is an explicit constraint on the private path bits:

```noir
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
```

The path bits are read least-significant-bit first. They are both the Merkle
left/right directions and the binary encoding of the opened leaf index.

## Why the Index Check Is Load-Bearing

Without the index check, a dishonest prover could use a valid Merkle proof for a
different matrix cell.

Suppose the actual edge is:

```text
from = a
to = b
expected_idx = a * N + b
```

but a cheaper cost exists at:

```text
cheap_idx = c * N + d
```

The prover could try to supply:

```text
edge_cost = matrix[cheap_idx]
siblings/path_bits = Merkle proof for cheap_idx
```

The hash path would reach the root, so membership alone would pass. The explicit
index check rejects this because the path bits reconstruct to `cheap_idx`, not
`expected_idx`.

If the prover instead uses the path bits for `expected_idx` but places the cheap
cost at the bottom of the path, the hash chain will not reach the root unless the
prover can find a Poseidon2 collision or preimage. Thus the two checks together
close the substitution attack.

## Alternatives

### Alternative 1: Hash Only the Cost at the Leaf

The tree could be built as:

```text
leaf[index] = H(cost[index])
parent = H(left_child, right_child)
```

The Noir circuit would then start with something like:

```noir
let mut current = Poseidon2::hash([edge_cost as Field, 0], 2);
```

This does **not** remove the need for address binding. A proof for a cheaper leaf
elsewhere would still be valid unless the circuit also proves that the path opens
the correct position.

Comparison with the current design:

- Adds one Poseidon2 hash per opened edge.
- Still needs the explicit path-index check.
- Provides no meaningful privacy benefit in this ZK setting, because Merkle
  siblings and path bits are private witness values hidden by the SNARK.

For this project, this alternative is mostly worse.

### Alternative 2: Hash the Index and Cost at the Leaf

The tree could be built as:

```text
leaf[index] = H(index, cost[index])
parent = H(left_child, right_child)
```

The Noir circuit would compute:

```noir
let expected_idx = from * N + to;
let mut current =
    Poseidon2::hash([expected_idx as Field, edge_cost as Field], 2);
```

This bakes the address into the committed leaf. The proof for another leaf no
longer starts from the same value, because leaf `j` commits to `H(j, cost_j)`.

Comparison with the current design:

- Cleaner membership story: the opened value carries its own address.
- The explicit path-index check becomes redundant for the cost-substitution
  attack, though it may still be useful as a consistency check.
- Adds one Poseidon2 hash per opened edge.
- Replaces cheap arithmetic address binding with an expensive hash.

This is the strongest direct alternative, but it costs more in-circuit hashing.
The current design gets the same intended address-binding property by checking
the path position explicitly.

### Alternative 3: Fully Domain-Separated Leaves and Internal Nodes

A more general cryptographic-library design would be:

```text
leaf[index] = H(LEAF_TAG, index, cost[index])
internal = H(NODE_TAG, left_child, right_child)
```

This separates leaf encodings from internal-node encodings and prevents ambiguity
between different tree levels or value types.

Comparison with the current design:

- Most conventional for a reusable Merkle API.
- Strongest domain-separation hygiene.
- Requires extra hashing and extra encoding/tagging logic.
- Overkill for the current fixed-depth, in-circuit lookup setting where the leaf
  address is already constrained and all hash inputs have fixed roles.

This would be a good default for a general-purpose commitment library, but it is
not the best cost point for these benchmark circuits.

## Cost Comparison

Let `N` be the number of TSP nodes. The cycle opens `N` edge costs in the flat
proof. The Merkle tree has:

```text
DEPTH = ceil(log2(N^2 padded to a power of two)) ~= 2 log2(N)
```

Current design:

```text
N * DEPTH Poseidon2 hashes
+ N * DEPTH cheap bit/index arithmetic
```

Hashed-leaf design:

```text
N * (DEPTH + 1) Poseidon2 hashes
```

For `N = 480`, `DEPTH = 18`:

```text
current:
  480 * 18 = 8640 Poseidon2 hashes

H(index, cost) leaves:
  480 * 19 = 9120 Poseidon2 hashes

extra:
  480 Poseidon2 hashes
```

In the composite variants, the opened internal and boundary edges are distributed
between segment and glue circuits, but the total number of opened edges is still
the cycle length. The same one-extra-hash-per-opened-edge overhead applies.

Since Poseidon2 calls dominate the Merkle-check cost, avoiding that extra leaf
hash is a meaningful circuit-size and proving-cost saving.

## Why the Current Choice Is Defensible

The current design is:

```text
leaf[index] = cost[index]
root = Merkle tree over raw costs

proof checks:
  1. path bits reconstruct to from * N + to
  2. raw edge_cost hashes upward to root
```

This separates address binding from Merkle membership. That separation is safe
because both constraints are enforced inside the same circuit over the same
witness values.

The thesis-ready justification is:

> We deliberately use raw cost values as Merkle leaves and enforce the leaf
> address in-circuit. This saves one Poseidon2 call per opened edge compared with
> hashing `(index, cost)` into each leaf. Soundness is not weakened, because a
> valid opening must satisfy both the Merkle root check and the independent
> constraint that the path bits encode exactly `from * N + to`. Thus a proof for
> a cheaper leaf at a different address is rejected by the index check, while a
> forged value at the correct address would require breaking Poseidon2 collision
> or preimage resistance.

## When We Would Choose Differently

The raw-leaf design is appropriate for this project because:

- the Merkle opening is checked inside a ZK circuit;
- the path bits are private witness but constrained;
- the matrix layout is fixed and simple;
- the tree is used for a single typed object: cost-matrix entries;
- Poseidon2 hashes are the dominant cost we want to minimize.

We would prefer `H(index, cost)` or fully domain-separated leaves if:

- the Merkle proofs were verified outside a circuit by independent software;
- leaves could contain multiple object types;
- the tree API were reused across protocols;
- path positions were not explicitly constrained;
- the extra hash per opening was negligible relative to the rest of the protocol.

For the benchmark circuits, the raw-leaf plus explicit-index-check design is the
right engineering tradeoff: cheaper than hashed leaves, explicit enough to audit,
and sound under the same Poseidon2 assumptions already used by the Merkle path.

