/// pipeline/merkle_builder/src/main.rs
///
/// Builds a Poseidon2 Merkle tree over the N^2 cost matrix and writes Prover.toml
/// for the flat_merkle_presence circuit.
///
/// ## Interface
///
///   JSON on stdin -> Prover.toml at --out <path>
///
/// ### Input JSON
/// ```json
/// {
///   "n":           5,
///   "flat_matrix": [0, 10, 20, ...],   // N*N values, row-major
///   "cycle":       [0, 2, 4, 1, 3],    // N node indices
///   "threshold":   1234,               // u64 cost upper bound
///   "cost":        1120                // u64 actual cycle cost (for annotation)
/// }
/// ```
///
/// ### Output (Prover.toml)
/// Follows the same format and commenting style as pipeline/format_inputs.py.
/// Fields written:
///   cycle       -- private: Hamiltonian cycle (u32 array)
///   edge_costs  -- private: cost of each cycle edge (u64 array)
///   siblings    -- private: Merkle siblings, flat row-major (Field array)
///   path_bits   -- private: path direction bits, flat row-major (bool array)
///   root        -- public:  Poseidon2 Merkle root of the cost matrix
///   threshold   -- public:  cycle cost upper bound (u64)
///
/// ## Merkle tree structure
///
///   Leaves: flat_matrix[0..N^2-1], padded with zeros to the next power of 2.
///   Internal nodes: parent = poseidon2_compress(left_child, right_child).
///   Compression function matches Noir's Poseidon2::hash([l, r], 2):
///     iv    = 2 * 2^64
///     state = [l, r, 0, iv]
///     node  = poseidon2_permutation(state)[0]
///
///   Tree stored 1-indexed:
///     nodes[1]              = root
///     nodes[2*i], nodes[2*i+1] = left/right children of nodes[i]
///     nodes[n_padded .. 2*n_padded-1] = leaves (0-indexed leaf k at nodes[n_padded+k])
///
///   DEPTH = n_padded.trailing_zeros()  where  n_padded = N^2.next_power_of_two()
///
/// ## Proof format (per edge)
///
///   Siblings and path bits are stored LSB-first (d=0 = leaf level, d=DEPTH-1 = just below root).
///   path_bits[d] = true  => the current node is a right child at level d
///                           (1-indexed position is odd: pos = 2*parent + 1)
///   path_bits[d] = false => the current node is a left child at level d
///                           (1-indexed position is even: pos = 2*parent)
///   Leaf index reconstruction: leaf_idx = sum(path_bits[d] * 2^d, d=0..DEPTH-1)
///   This is verified inside the Noir circuit (leaf index check in GROUP 3).
use acir::{AcirField, FieldElement};
use bn254_blackbox_solver::poseidon2_permutation;
use serde::Deserialize;
use std::io::{self, Read};
use std::path::PathBuf;

// ── Input schema ──────────────────────────────────────────────────────────────

#[derive(Deserialize)]
struct Input {
    n: usize,
    flat_matrix: Vec<u64>,
    cycle: Vec<usize>,
    threshold: u64,
    cost: u64,
}

// ── Poseidon2 compression ─────────────────────────────────────────────────────

/// Compression function for internal Merkle nodes.
/// Matches Noir's Poseidon2::hash([left, right], 2):
///   iv = 2 * 2^64, state = [left, right, 0, iv], hash = permutation(state)[0]
fn poseidon2_compress(left: FieldElement, right: FieldElement) -> FieldElement {
    let iv = FieldElement::from(2u128 * (1u128 << 64));
    let state = vec![left, right, FieldElement::zero(), iv];
    poseidon2_permutation(&state).expect("Poseidon2 permutation failed")[0]
}

// ── Merkle tree ───────────────────────────────────────────────────────────────

struct MerkleTree {
    /// 1-indexed flat array: nodes[1] = root, nodes[2i]/nodes[2i+1] = children of i.
    /// Leaves occupy nodes[n_padded .. 2*n_padded - 1].
    nodes: Vec<FieldElement>,
    /// n_padded = n_leaves.next_power_of_two(); leaf k is at nodes[n_padded + k].
    n_padded: usize,
    /// depth = log2(n_padded) = n_padded.trailing_zeros().
    depth: u32,
}

impl MerkleTree {
    /// Build the tree from a flat slice of u64 leaf values.
    /// Values beyond `leaves.len()` are automatically zero-padded.
    fn build(leaves: &[u64]) -> Self {
        let n_leaves = leaves.len();
        let n_padded = if n_leaves <= 1 {
            1
        } else {
            n_leaves.next_power_of_two()
        };
        let depth = (n_padded as u32).trailing_zeros();

        // 1-indexed storage: index 0 unused, root at 1, leaves at [n_padded..2*n_padded).
        let mut nodes = vec![FieldElement::zero(); 2 * n_padded];

        // Copy leaves; padding leaves remain zero (already initialised above).
        for (k, &cost) in leaves.iter().enumerate() {
            nodes[n_padded + k] = FieldElement::from(cost as u128);
        }

        // Build internal nodes bottom-up from just-above-leaves to root.
        for i in (1..n_padded).rev() {
            nodes[i] = poseidon2_compress(nodes[2 * i], nodes[2 * i + 1]);
        }

        MerkleTree { nodes, n_padded, depth }
    }

    fn root(&self) -> FieldElement {
        self.nodes[1]
    }

    /// Return the Merkle proof for leaf at 0-indexed position `leaf_idx`.
    ///
    /// Returns `(siblings, path_bits)` ordered LSB-first (leaf level = index 0).
    /// path_bits[d] = true  => current node is a right child at level d (pos is odd).
    /// path_bits[d] = false => current node is a left child  at level d (pos is even).
    ///
    /// Leaf index reconstruction: leaf_idx == sum(path_bits[d] * 2^d, d=0..depth-1).
    fn proof(&self, leaf_idx: usize) -> (Vec<FieldElement>, Vec<bool>) {
        let mut siblings = Vec::with_capacity(self.depth as usize);
        let mut path_bits = Vec::with_capacity(self.depth as usize);

        let mut pos = self.n_padded + leaf_idx; // 1-indexed position of the leaf
        while pos > 1 {
            let is_right = pos % 2 == 1; // right child iff position is odd
            let sibling_pos = pos ^ 1;   // XOR with 1 flips the right/left bit
            siblings.push(self.nodes[sibling_pos]);
            path_bits.push(is_right);
            pos /= 2;
        }

        (siblings, path_bits)
    }
}

// ── Prover.toml writer ────────────────────────────────────────────────────────

/// Write Prover.toml for flat_merkle_presence in Noir's expected format.
///
/// Follows the same commenting style as pipeline/format_inputs.py.
/// Field values (siblings, root) are written as "0x<64-hex-char>" strings.
/// u32/u64 values (cycle, edge_costs, threshold) are written as quoted decimals.
/// bool values (path_bits) are written as unquoted true/false.
fn write_prover_toml(
    out_path: &PathBuf,
    _n: usize,
    _depth: u32,
    cycle: &[usize],
    edge_costs: &[u64],
    siblings_flat: &[FieldElement],
    path_bits_flat: &[bool],
    root: FieldElement,
    threshold: u64,
    cost: u64,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    // ── cycle ─────────────────────────────────────────────────────────────────
    writeln!(out, "# Private witness: node visit order (Hamiltonian cycle)").unwrap();
    let cycle_str = cycle
        .iter()
        .map(|v| format!("\"{}\"", v))
        .collect::<Vec<_>>()
        .join(", ");
    writeln!(out, "cycle = [{}]\n", cycle_str).unwrap();

    // ── edge_costs ────────────────────────────────────────────────────────────
    writeln!(out, "# Private witness: cost of each directed cycle edge").unwrap();
    writeln!(out, "# edge_costs[i] = cost_matrix[cycle[i]][cycle[(i+1)%N]]").unwrap();
    let costs_str = edge_costs
        .iter()
        .map(|v| format!("\"{}\"", v))
        .collect::<Vec<_>>()
        .join(", ");
    writeln!(out, "edge_costs = [{}]\n", costs_str).unwrap();

    // ── siblings ──────────────────────────────────────────────────────────────
    writeln!(out, "# Private witness: Poseidon2 Merkle sibling hashes, flat row-major").unwrap();
    writeln!(out, "# siblings[i*DEPTH + d] = sibling at level d for edge i  (d=0 is leaf level)").unwrap();
    let sibs_str = siblings_flat
        .iter()
        .map(|f| format!("\"0x{}\"", f.to_hex()))
        .collect::<Vec<_>>()
        .join(", ");
    writeln!(out, "siblings = [{}]\n", sibs_str).unwrap();

    // ── path_bits ─────────────────────────────────────────────────────────────
    writeln!(out, "# Private witness: Merkle path direction bits, flat row-major").unwrap();
    writeln!(out, "# path_bits[i*DEPTH+d] = true => edge i is a right child at level d").unwrap();
    writeln!(out, "# LSB-first: leaf_idx = sum(path_bits[i*DEPTH+d] * 2^d, d=0..DEPTH-1)").unwrap();
    let bits_str = path_bits_flat
        .iter()
        .map(|b| if *b { "true" } else { "false" })
        .collect::<Vec<_>>()
        .join(", ");
    writeln!(out, "path_bits = [{}]\n", bits_str).unwrap();

    // ── root ──────────────────────────────────────────────────────────────────
    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix (row-major)").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    // ── threshold ─────────────────────────────────────────────────────────────
    writeln!(out, "# Public input: cycle cost upper bound").unwrap();
    writeln!(out, "# (actual cost = {}, threshold = {})", cost, threshold).unwrap();
    writeln!(out, "threshold = \"{}\"", threshold).unwrap();

    // Write to file (create or overwrite).
    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

// ── Main ──────────────────────────────────────────────────────────────────────

fn main() {
    // ── Parse --out flag ──────────────────────────────────────────────────────
    let args: Vec<String> = std::env::args().collect();
    let out_idx = args
        .iter()
        .position(|a| a == "--out")
        .unwrap_or_else(|| {
            eprintln!("Usage: merkle_builder --out <Prover.toml path>");
            std::process::exit(1);
        });
    let out_path = PathBuf::from(
        args.get(out_idx + 1).unwrap_or_else(|| {
            eprintln!("Error: --out flag requires an argument");
            std::process::exit(1);
        }),
    );

    // ── Read input JSON from stdin ────────────────────────────────────────────
    let mut json_buf = String::new();
    io::stdin()
        .read_to_string(&mut json_buf)
        .unwrap_or_else(|e| {
            eprintln!("Error reading stdin: {}", e);
            std::process::exit(1);
        });

    let input: Input = serde_json::from_str(&json_buf).unwrap_or_else(|e| {
        eprintln!("Error parsing input JSON: {}", e);
        std::process::exit(1);
    });

    // ── Validate ──────────────────────────────────────────────────────────────
    let n = input.n;
    if input.flat_matrix.len() != n * n {
        eprintln!(
            "Error: flat_matrix length {} != n*n={}",
            input.flat_matrix.len(),
            n * n
        );
        std::process::exit(1);
    }
    if input.cycle.len() != n {
        eprintln!(
            "Error: cycle length {} != n={}",
            input.cycle.len(),
            n
        );
        std::process::exit(1);
    }
    for (i, &v) in input.cycle.iter().enumerate() {
        if v >= n {
            eprintln!("Error: cycle[{}] = {} is out of range [0, {})", i, v, n);
            std::process::exit(1);
        }
    }

    // ── Build Merkle tree over the N^2 cost matrix ────────────────────────────
    let tree = MerkleTree::build(&input.flat_matrix);
    let root = tree.root();
    let depth = tree.depth;

    // ── Compute per-edge costs and Merkle proofs ──────────────────────────────
    let mut edge_costs: Vec<u64> = Vec::with_capacity(n);
    let mut siblings_flat: Vec<FieldElement> = Vec::with_capacity(n * depth as usize);
    let mut path_bits_flat: Vec<bool> = Vec::with_capacity(n * depth as usize);

    for i in 0..n {
        let from = input.cycle[i];
        let to = input.cycle[(i + 1) % n];
        let leaf_idx = from * n + to;

        edge_costs.push(input.flat_matrix[leaf_idx]);

        let (sibs, bits) = tree.proof(leaf_idx);
        siblings_flat.extend_from_slice(&sibs);
        path_bits_flat.extend_from_slice(&bits);
    }

    // ── Write Prover.toml ─────────────────────────────────────────────────────
    write_prover_toml(
        &out_path,
        n,
        depth,
        &input.cycle,
        &edge_costs,
        &siblings_flat,
        &path_bits_flat,
        root,
        input.threshold,
        input.cost,
    )
    .unwrap_or_else(|e| {
        eprintln!("Error writing {}: {}", out_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "merkle_builder: N={} DEPTH={} root=0x{} -> {}",
        n,
        depth,
        &root.to_hex()[..8],
        out_path.display()
    );
}

// ── Unit tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// For a 1-leaf tree the root IS the leaf; no siblings, no bits.
    #[test]
    fn single_leaf() {
        let tree = MerkleTree::build(&[42]);
        assert_eq!(tree.depth, 0);
        assert_eq!(tree.root(), FieldElement::from(42u128));
        let (sibs, bits) = tree.proof(0);
        assert!(sibs.is_empty());
        assert!(bits.is_empty());
    }

    /// For a 2-leaf tree the root is hash(leaf0, leaf1).
    #[test]
    fn two_leaf_root() {
        let l0 = FieldElement::from(1u128);
        let l1 = FieldElement::from(2u128);
        let expected_root = poseidon2_compress(l0, l1);
        let tree = MerkleTree::build(&[1, 2]);
        assert_eq!(tree.depth, 1);
        assert_eq!(tree.root(), expected_root);
    }

    /// Proof for leaf 0 in a 2-leaf tree: sibling is leaf 1, path_bit=false (left child).
    #[test]
    fn two_leaf_proof_left() {
        let tree = MerkleTree::build(&[10, 20]);
        let (sibs, bits) = tree.proof(0);
        assert_eq!(sibs.len(), 1);
        assert_eq!(bits, vec![false]); // left child
        assert_eq!(sibs[0], FieldElement::from(20u128));
        // Re-derive root from proof
        let derived = poseidon2_compress(FieldElement::from(10u128), sibs[0]);
        assert_eq!(derived, tree.root());
    }

    /// Proof for leaf 1 in a 2-leaf tree: sibling is leaf 0, path_bit=true (right child).
    #[test]
    fn two_leaf_proof_right() {
        let tree = MerkleTree::build(&[10, 20]);
        let (sibs, bits) = tree.proof(1);
        assert_eq!(sibs.len(), 1);
        assert_eq!(bits, vec![true]); // right child
        assert_eq!(sibs[0], FieldElement::from(10u128));
        // Re-derive root from proof
        let derived = poseidon2_compress(sibs[0], FieldElement::from(20u128));
        assert_eq!(derived, tree.root());
    }

    /// All proofs in a 4-leaf tree verify against the root.
    #[test]
    fn four_leaf_all_proofs() {
        let leaves = vec![100u64, 200, 300, 400];
        let tree = MerkleTree::build(&leaves);
        assert_eq!(tree.depth, 2);

        for k in 0..4usize {
            let (sibs, bits) = tree.proof(k);
            assert_eq!(sibs.len(), 2);
            assert_eq!(bits.len(), 2);

            // Re-derive root by walking up
            let mut current = FieldElement::from(leaves[k] as u128);
            for d in 0..2 {
                let (left, right) = if bits[d] {
                    (sibs[d], current)
                } else {
                    (current, sibs[d])
                };
                current = poseidon2_compress(left, right);
            }
            assert_eq!(current, tree.root(), "proof for leaf {k} failed");
        }
    }

    /// Leaf index reconstruction: sum(bits[d] * 2^d) == leaf_idx.
    #[test]
    fn leaf_index_from_path_bits() {
        // Use a depth-5 tree (32 leaves) to check several indices.
        let leaves: Vec<u64> = (0..25).collect();
        let tree = MerkleTree::build(&leaves); // padded to 32, depth=5

        for k in 0..25usize {
            let (_sibs, bits) = tree.proof(k);
            let reconstructed: usize = bits
                .iter()
                .enumerate()
                .map(|(d, &b)| if b { 1 << d } else { 0 })
                .sum();
            assert_eq!(reconstructed, k, "index mismatch for leaf {k}");
        }
    }
}
