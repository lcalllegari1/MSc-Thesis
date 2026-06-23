/// pipeline/merkle_builder/src/main.rs
///
/// Builds a Poseidon2 Merkle tree over the N^2 cost matrix and writes Prover.toml
/// for the flat_merkle circuits.  The same witness layout (cycle, edge_costs,
/// siblings, path_bits, root, threshold) serves both flat_merkle_sort (now the
/// default flat-merkle baseline -- sort matches the permutation check used in the
/// hierarchical variants) and flat_merkle_presence: the permutation method is
/// internal to the circuit and does not change the Prover.toml inputs.
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
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

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
/// Also reused for the Variant A++ hash-chain step Poseidon2([h_j, node], 2).
fn poseidon2_compress(left: FieldElement, right: FieldElement) -> FieldElement {
    let iv = FieldElement::from(2u128 * (1u128 << 64));
    let state = vec![left, right, FieldElement::zero(), iv];
    poseidon2_permutation(&state).expect("Poseidon2 permutation failed")[0]
}

/// Single-input hash for the Variant A++ Fiat-Shamir challenge X = Poseidon2(c).
/// Matches Noir's Poseidon2::hash([c], 1):
///   iv = 1 * 2^64, state = [c, 0, 0, iv], hash = permutation(state)[0]
/// Cross-validated against Noir by tests/hash_compat (the in_len=1 sponge).
fn poseidon2_hash_single(x: FieldElement) -> FieldElement {
    let iv = FieldElement::from(1u128 * (1u128 << 64));
    let state = vec![x, FieldElement::zero(), FieldElement::zero(), iv];
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

// ── Tree disk cache ───────────────────────────────────────────────────────────
//
// Building the Poseidon2 tree is O(N^2) hashes and is the dominant cost of this
// binary at large N.  The tree is a pure function of `flat_matrix`, so for a
// fixed instance every variant (flat / hier / hier-fs / hier-c / hier-cfs) and
// every benchmark run rebuilds the *identical* tree.  With `--tree-cache <path>`
// we build once, serialise the node array, and reload it on subsequent calls.
//
// Binary format (little-endian header, then the node array):
//   [0..4)   magic   = b"MTC1"
//   [4..8)   version : u32
//   [8..16)  n_leaves: u64   (= N*N; the un-padded leaf count)
//   [16..24) n_padded: u64
//   [24..28) depth   : u32
//   [28..36) checksum: u64   (FNV-1a over flat_matrix; guards against a stale
//                             cache after instance_gen / matrix changes)
//   [36..)   2*n_padded field elements, 32 big-endian bytes each
//
// A load that fails ANY header check (magic, version, n_leaves, checksum, or a
// truncated body) returns None so the caller rebuilds from scratch -- a stale
// tree must never silently corrupt a benchmark.
const TREE_CACHE_MAGIC: &[u8; 4] = b"MTC1";
const TREE_CACHE_VERSION: u32 = 1;
const FIELD_BYTES: usize = 32;
const TREE_HEADER_BYTES: usize = 36;

/// Fast non-cryptographic checksum (FNV-1a) over the raw leaf values.  Cheap
/// O(N^2) pass; only used to detect that a cached tree matches the input matrix.
fn matrix_checksum(flat_matrix: &[u64]) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for &v in flat_matrix {
        for b in v.to_le_bytes() {
            h ^= b as u64;
            h = h.wrapping_mul(0x100000001b3);
        }
    }
    h
}

impl MerkleTree {
    /// Serialise the tree to `path` (atomic: write to `<path>.tmp`, then rename).
    fn save(&self, path: &Path, n_leaves: usize, checksum: u64) -> io::Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let tmp = path.with_extension("tmp");
        {
            let f = std::fs::File::create(&tmp)?;
            let mut w = io::BufWriter::new(f);
            w.write_all(TREE_CACHE_MAGIC)?;
            w.write_all(&TREE_CACHE_VERSION.to_le_bytes())?;
            w.write_all(&(n_leaves as u64).to_le_bytes())?;
            w.write_all(&(self.n_padded as u64).to_le_bytes())?;
            w.write_all(&self.depth.to_le_bytes())?;
            w.write_all(&checksum.to_le_bytes())?;
            for node in &self.nodes {
                let be = node.to_be_bytes(); // 32 bytes for bn254
                w.write_all(&be)?;
            }
            w.flush()?;
        }
        std::fs::rename(&tmp, path)
    }

    /// Load a tree previously written by `save`, validating it against the input
    /// matrix.  Returns None (caller rebuilds) on any mismatch or read error.
    fn load(path: &Path, n_leaves: usize, checksum: u64) -> Option<MerkleTree> {
        let bytes = std::fs::read(path).ok()?;
        if bytes.len() < TREE_HEADER_BYTES || &bytes[0..4] != TREE_CACHE_MAGIC {
            return None;
        }
        let rd_u32 = |o: usize| u32::from_le_bytes(bytes[o..o + 4].try_into().unwrap());
        let rd_u64 = |o: usize| u64::from_le_bytes(bytes[o..o + 8].try_into().unwrap());
        if rd_u32(4) != TREE_CACHE_VERSION
            || rd_u64(8) != n_leaves as u64
            || rd_u64(28) != checksum
        {
            return None;
        }
        let n_padded = rd_u64(16) as usize;
        let depth = rd_u32(24);
        let n_nodes = 2 * n_padded;
        if bytes.len() != TREE_HEADER_BYTES + n_nodes * FIELD_BYTES {
            return None; // truncated / corrupt body
        }
        let mut nodes = Vec::with_capacity(n_nodes);
        let mut off = TREE_HEADER_BYTES;
        for _ in 0..n_nodes {
            nodes.push(FieldElement::from_be_bytes_reduce(&bytes[off..off + FIELD_BYTES]));
            off += FIELD_BYTES;
        }
        Some(MerkleTree { nodes, n_padded, depth })
    }
}

/// Build the Merkle tree, consulting the `--tree-cache <path>` argument if given.
/// On a cache hit the O(N^2) Poseidon2 build is skipped entirely; on a miss the
/// freshly built tree is written back (so the next variant/run reuses it).
fn get_tree(args: &[String], flat_matrix: &[u64]) -> MerkleTree {
    let cache_path = parse_named_arg(args, "--tree-cache").map(PathBuf::from);
    let checksum = cache_path.as_ref().map(|_| matrix_checksum(flat_matrix));

    if let (Some(path), Some(sum)) = (cache_path.as_ref(), checksum) {
        if let Some(tree) = MerkleTree::load(path, flat_matrix.len(), sum) {
            eprintln!("merkle_builder: tree cache HIT  ({})", path.display());
            return tree;
        }
    }

    let tree = MerkleTree::build(flat_matrix);

    if let (Some(path), Some(sum)) = (cache_path.as_ref(), checksum) {
        match tree.save(path, flat_matrix.len(), sum) {
            Ok(()) => eprintln!("merkle_builder: tree cache WRITE ({})", path.display()),
            Err(e) => eprintln!("merkle_builder: WARN could not write tree cache {}: {}", path.display(), e),
        }
    }
    tree
}

// ── Prover.toml writer ────────────────────────────────────────────────────────

/// Write Prover.toml for the flat_merkle circuits (sort/presence) in Noir's expected format.
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

// ── Hierarchical Prover.toml writers (Variant A) ──────────────────────────────

/// Write Prover.toml for circuits/hierarchical_segment for one segment.
///
/// Field order matches the function signature in
/// circuits/hierarchical_segment/src/main.nr (private first, then public).
/// Noir matches by name not position, but consistent ordering keeps the file
/// readable and matches the public-input dump order used by verify_hier.py.
fn write_sub_prover_toml(
    out_path: &PathBuf,
    seg_idx: usize,
    cycle_segment: &[usize],
    edge_costs: &[u64],
    siblings_flat: &[FieldElement],
    path_bits_flat: &[bool],
    sorted_nodes: &[usize],
    start_node: usize,
    end_node: usize,
    partial_cost: u64,
    root: FieldElement,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    writeln!(out, "# hierarchical_segment Prover.toml -- segment {}", seg_idx).unwrap();
    writeln!(out, "# Variant A sub-circuit. Public: sorted_nodes, start_node, end_node, partial_cost, root.").unwrap();
    writeln!(out).unwrap();

    // ── cycle_segment (private) ──────────────────────────────────────────────
    writeln!(out, "# Private witness: segment node visit order (M entries)").unwrap();
    let seg_str = cycle_segment.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "cycle_segment = [{}]\n", seg_str).unwrap();

    // ── edge_costs (private) ──────────────────────────────────────────────────
    writeln!(out, "# Private witness: M-1 internal edge costs").unwrap();
    writeln!(out, "# edge_costs[i] = cost_matrix[cycle_segment[i]][cycle_segment[i+1]]").unwrap();
    let costs_str = edge_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "edge_costs = [{}]\n", costs_str).unwrap();

    // ── siblings (private) ────────────────────────────────────────────────────
    writeln!(out, "# Private witness: Poseidon2 Merkle siblings, flat row-major over (M-1) edge proofs").unwrap();
    let sibs_str = siblings_flat.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");
    writeln!(out, "siblings = [{}]\n", sibs_str).unwrap();

    // ── path_bits (private) ───────────────────────────────────────────────────
    writeln!(out, "# Private witness: LSB-first leaf-index encoding, flat row-major").unwrap();
    let bits_str = path_bits_flat.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "path_bits = [{}]\n", bits_str).unwrap();

    // ── sorted_nodes (public) ─────────────────────────────────────────────────
    writeln!(out, "# Public input: segment node set, sorted ascending (M entries)").unwrap();
    let sn_str = sorted_nodes.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "sorted_nodes = [{}]\n", sn_str).unwrap();

    // ── start_node / end_node (public) ────────────────────────────────────────
    writeln!(out, "# Public input: segment endpoints in cycle order").unwrap();
    writeln!(out, "start_node = \"{}\"", start_node).unwrap();
    writeln!(out, "end_node = \"{}\"\n", end_node).unwrap();

    // ── partial_cost (public) ─────────────────────────────────────────────────
    writeln!(out, "# Public input: sum of the M-1 internal edge costs").unwrap();
    writeln!(out, "partial_cost = \"{}\"\n", partial_cost).unwrap();

    // ── root (public) ─────────────────────────────────────────────────────────
    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"", root.to_hex()).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

/// Write Prover.toml for circuits/hierarchical_glue.
fn write_glue_prover_toml(
    out_path: &PathBuf,
    boundary_costs: &[u64],
    boundary_siblings: &[FieldElement],
    boundary_path_bits: &[bool],
    all_sorted_nodes: &[usize],
    starts: &[usize],
    ends: &[usize],
    partial_costs: &[u64],
    threshold: u64,
    cost: u64,
    root: FieldElement,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    writeln!(out, "# hierarchical_glue Prover.toml").unwrap();
    writeln!(out, "# Variant A glue. Public: all_sorted_nodes, starts, ends, partial_costs, threshold, root.").unwrap();
    writeln!(out).unwrap();

    // ── boundary_costs (private) ──────────────────────────────────────────────
    writeln!(out, "# Private witness: K boundary-edge costs").unwrap();
    writeln!(out, "# boundary_costs[i] = cost_matrix[ends[i]][starts[(i+1) % K]]").unwrap();
    let bc_str = boundary_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_costs = [{}]\n", bc_str).unwrap();

    // ── boundary_siblings (private) ───────────────────────────────────────────
    writeln!(out, "# Private witness: Poseidon2 Merkle siblings for the K boundary-edge proofs").unwrap();
    let sibs_str = boundary_siblings.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_siblings = [{}]\n", sibs_str).unwrap();

    // ── boundary_path_bits (private) ──────────────────────────────────────────
    writeln!(out, "# Private witness: LSB-first leaf-index encoding for boundary-edge proofs").unwrap();
    let bits_str = boundary_path_bits.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_path_bits = [{}]\n", bits_str).unwrap();

    // ── all_sorted_nodes (public) ─────────────────────────────────────────────
    writeln!(out, "# Public input: concatenation of K sub-proofs' sorted_nodes arrays").unwrap();
    writeln!(out, "# (length N, not yet globally sorted; glue G2 sorts in-circuit)").unwrap();
    let asn_str = all_sorted_nodes.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "all_sorted_nodes = [{}]\n", asn_str).unwrap();

    // ── starts (public) ──────────────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment start nodes (K entries)").unwrap();
    let s_str = starts.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "starts = [{}]\n", s_str).unwrap();

    // ── ends (public) ────────────────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment end nodes (K entries)").unwrap();
    let e_str = ends.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "ends = [{}]\n", e_str).unwrap();

    // ── partial_costs (public) ───────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment internal cost sums").unwrap();
    let pc_str = partial_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "partial_costs = [{}]\n", pc_str).unwrap();

    // ── threshold (public) ───────────────────────────────────────────────────
    writeln!(out, "# Public input: cycle cost upper bound").unwrap();
    writeln!(out, "# (actual cost = {}, threshold = {})", cost, threshold).unwrap();
    writeln!(out, "threshold = \"{}\"\n", threshold).unwrap();

    // ── root (public) ────────────────────────────────────────────────────────
    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"", root.to_hex()).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

// ── Hierarchical-fs Prover.toml writers (Variant A++) ─────────────────────────

/// Write Prover.toml for circuits/hierarchical_segment_fs for one segment.
///
/// Field order matches the function signature in
/// circuits/hierarchical_segment_fs/src/main.nr (private first, then public).
/// Variant A++ drops the public sorted_nodes and adds the five Field scalars
/// (P_i, h_in_i, h_out_i, c, X).
fn write_sub_fs_prover_toml(
    out_path: &PathBuf,
    seg_idx: usize,
    cycle_segment: &[usize],
    edge_costs: &[u64],
    siblings_flat: &[FieldElement],
    path_bits_flat: &[bool],
    start_node: usize,
    end_node: usize,
    partial_cost: u64,
    root: FieldElement,
    p_i: FieldElement,
    h_in: FieldElement,
    h_out: FieldElement,
    c: FieldElement,
    x: FieldElement,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    writeln!(out, "# hierarchical_segment_fs Prover.toml -- segment {}", seg_idx).unwrap();
    writeln!(out, "# Variant A++ sub-circuit. Public: start_node, end_node, partial_cost,").unwrap();
    writeln!(out, "# root, P_i, h_in_i, h_out_i, c, X. (No sorted_nodes: partition is hidden.)").unwrap();
    writeln!(out).unwrap();

    // ── cycle_segment (private) ──────────────────────────────────────────────
    writeln!(out, "# Private witness: segment node visit order (M entries)").unwrap();
    let seg_str = cycle_segment.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "cycle_segment = [{}]\n", seg_str).unwrap();

    // ── edge_costs (private) ──────────────────────────────────────────────────
    writeln!(out, "# Private witness: M-1 internal edge costs").unwrap();
    let costs_str = edge_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "edge_costs = [{}]\n", costs_str).unwrap();

    // ── siblings (private) ────────────────────────────────────────────────────
    writeln!(out, "# Private witness: Poseidon2 Merkle siblings, flat row-major over (M-1) edge proofs").unwrap();
    let sibs_str = siblings_flat.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");
    writeln!(out, "siblings = [{}]\n", sibs_str).unwrap();

    // ── path_bits (private) ───────────────────────────────────────────────────
    writeln!(out, "# Private witness: LSB-first leaf-index encoding, flat row-major").unwrap();
    let bits_str = path_bits_flat.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "path_bits = [{}]\n", bits_str).unwrap();

    // ── start_node / end_node (public) ────────────────────────────────────────
    writeln!(out, "# Public input: segment endpoints in cycle order").unwrap();
    writeln!(out, "start_node = \"{}\"", start_node).unwrap();
    writeln!(out, "end_node = \"{}\"\n", end_node).unwrap();

    // ── partial_cost (public) ─────────────────────────────────────────────────
    writeln!(out, "# Public input: sum of the M-1 internal edge costs").unwrap();
    writeln!(out, "partial_cost = \"{}\"\n", partial_cost).unwrap();

    // ── root (public) ─────────────────────────────────────────────────────────
    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    // ── P_i (public) ──────────────────────────────────────────────────────────
    writeln!(out, "# Public input: grand product prod_j (X + cycle_segment[j])").unwrap();
    writeln!(out, "P_i = \"0x{}\"\n", p_i.to_hex()).unwrap();

    // ── h_in_i / h_out_i (public) ─────────────────────────────────────────────
    writeln!(out, "# Public input: hash-chain anchors entering/leaving this segment").unwrap();
    writeln!(out, "h_in_i = \"0x{}\"", h_in.to_hex()).unwrap();
    writeln!(out, "h_out_i = \"0x{}\"\n", h_out.to_hex()).unwrap();

    // ── c / X (public) ────────────────────────────────────────────────────────
    writeln!(out, "# Public input: full-cycle chain terminal c and FS challenge X = Poseidon2([c],1)").unwrap();
    writeln!(out, "c = \"0x{}\"", c.to_hex()).unwrap();
    writeln!(out, "X = \"0x{}\"", x.to_hex()).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

/// Write Prover.toml for circuits/hierarchical_glue_fs.
fn write_glue_fs_prover_toml(
    out_path: &PathBuf,
    boundary_costs: &[u64],
    boundary_siblings: &[FieldElement],
    boundary_path_bits: &[bool],
    starts: &[usize],
    ends: &[usize],
    partial_costs: &[u64],
    threshold: u64,
    cost: u64,
    root: FieldElement,
    p_is: &[FieldElement],
    h_ins: &[FieldElement],
    h_outs: &[FieldElement],
    c: FieldElement,
    x: FieldElement,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    let hexvec = |v: &[FieldElement]| v.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");

    writeln!(out, "# hierarchical_glue_fs Prover.toml").unwrap();
    writeln!(out, "# Variant A++ glue. Public: starts, ends, partial_costs, threshold, root,").unwrap();
    writeln!(out, "# P_is, h_ins, h_outs, c, X. (No all_sorted_nodes: grand product replaces sort.)").unwrap();
    writeln!(out).unwrap();

    // ── boundary_costs (private) ──────────────────────────────────────────────
    writeln!(out, "# Private witness: K boundary-edge costs").unwrap();
    writeln!(out, "# boundary_costs[i] = cost_matrix[ends[i]][starts[(i+1) % K]]").unwrap();
    let bc_str = boundary_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_costs = [{}]\n", bc_str).unwrap();

    // ── boundary_siblings (private) ───────────────────────────────────────────
    writeln!(out, "# Private witness: Poseidon2 Merkle siblings for the K boundary-edge proofs").unwrap();
    writeln!(out, "boundary_siblings = [{}]\n", hexvec(boundary_siblings)).unwrap();

    // ── boundary_path_bits (private) ──────────────────────────────────────────
    writeln!(out, "# Private witness: LSB-first leaf-index encoding for boundary-edge proofs").unwrap();
    let bits_str = boundary_path_bits.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_path_bits = [{}]\n", bits_str).unwrap();

    // ── starts / ends (public) ────────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment start nodes (K entries)").unwrap();
    let s_str = starts.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "starts = [{}]\n", s_str).unwrap();
    writeln!(out, "# Public input: per-segment end nodes (K entries)").unwrap();
    let e_str = ends.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "ends = [{}]\n", e_str).unwrap();

    // ── partial_costs (public) ───────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment internal cost sums").unwrap();
    let pc_str = partial_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "partial_costs = [{}]\n", pc_str).unwrap();

    // ── threshold (public) ───────────────────────────────────────────────────
    writeln!(out, "# Public input: cycle cost upper bound").unwrap();
    writeln!(out, "# (actual cost = {}, threshold = {})", cost, threshold).unwrap();
    writeln!(out, "threshold = \"{}\"\n", threshold).unwrap();

    // ── root (public) ────────────────────────────────────────────────────────
    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    // ── P_is (public) ────────────────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment grand products (factors of the partition check)").unwrap();
    writeln!(out, "P_is = [{}]\n", hexvec(p_is)).unwrap();

    // ── h_ins / h_outs (public) ──────────────────────────────────────────────
    writeln!(out, "# Public input: per-segment chain anchors, stitched into one continuous chain").unwrap();
    writeln!(out, "h_ins = [{}]", hexvec(h_ins)).unwrap();
    writeln!(out, "h_outs = [{}]\n", hexvec(h_outs)).unwrap();

    // ── c / X (public) ───────────────────────────────────────────────────────
    writeln!(out, "# Public input: full-cycle chain terminal c and FS challenge X = Poseidon2([c],1)").unwrap();
    writeln!(out, "c = \"0x{}\"", c.to_hex()).unwrap();
    writeln!(out, "X = \"0x{}\"", x.to_hex()).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

/// Write Prover.toml for circuits/hierarchical_segment_c for one segment.
/// Public: root, C_i.  Everything else is private witness.
fn write_sub_c_prover_toml(
    out_path: &PathBuf,
    seg_idx: usize,
    cycle_segment: &[usize],
    edge_costs: &[u64],
    siblings_flat: &[FieldElement],
    path_bits_flat: &[bool],
    r: FieldElement,
    root: FieldElement,
    c_i: FieldElement,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    writeln!(out, "# hierarchical_segment_c Prover.toml -- segment {}", seg_idx).unwrap();
    writeln!(out, "# Variant committed-A sub-circuit. Public: root, C_i.").unwrap();
    writeln!(out, "# (cycle_segment + partial_cost are folded into the blinded C_i.)").unwrap();
    writeln!(out).unwrap();

    writeln!(out, "# Private witness: segment node visit order (M entries)").unwrap();
    let seg_str = cycle_segment.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "cycle_segment = [{}]\n", seg_str).unwrap();

    writeln!(out, "# Private witness: M-1 internal edge costs").unwrap();
    let costs_str = edge_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "edge_costs = [{}]\n", costs_str).unwrap();

    writeln!(out, "# Private witness: Poseidon2 Merkle siblings, flat row-major over (M-1) edge proofs").unwrap();
    let sibs_str = siblings_flat.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");
    writeln!(out, "siblings = [{}]\n", sibs_str).unwrap();

    writeln!(out, "# Private witness: LSB-first leaf-index encoding, flat row-major").unwrap();
    let bits_str = path_bits_flat.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "path_bits = [{}]\n", bits_str).unwrap();

    writeln!(out, "# Private witness: blinding scalar (makes C_i hiding)").unwrap();
    writeln!(out, "r = \"0x{}\"\n", r.to_hex()).unwrap();

    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    writeln!(out, "# Public input: blinded commitment to this segment's nodes + cost").unwrap();
    writeln!(out, "C_i = \"0x{}\"", c_i.to_hex()).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

/// Write Prover.toml for circuits/hierarchical_glue_c.
/// Public: root, threshold, C_is.  Everything else is private witness.
fn write_glue_c_prover_toml(
    out_path: &PathBuf,
    boundary_costs: &[u64],
    boundary_siblings: &[FieldElement],
    boundary_path_bits: &[bool],
    all_nodes: &[usize],
    partial_costs: &[u64],
    r_is: &[FieldElement],
    threshold: u64,
    cost: u64,
    root: FieldElement,
    c_is: &[FieldElement],
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    let hexvec = |v: &[FieldElement]| v.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");

    writeln!(out, "# hierarchical_glue_c Prover.toml").unwrap();
    writeln!(out, "# Variant committed-A glue. Public: root, threshold, C_is.").unwrap();
    writeln!(out, "# (all_nodes/partial_costs/r_is are private witness.)").unwrap();
    writeln!(out).unwrap();

    writeln!(out, "# Private witness: K boundary-edge costs").unwrap();
    let bc_str = boundary_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_costs = [{}]\n", bc_str).unwrap();

    writeln!(out, "# Private witness: Poseidon2 Merkle siblings for the K boundary-edge proofs").unwrap();
    writeln!(out, "boundary_siblings = [{}]\n", hexvec(boundary_siblings)).unwrap();

    writeln!(out, "# Private witness: LSB-first leaf-index encoding for boundary-edge proofs").unwrap();
    let bits_str = boundary_path_bits.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_path_bits = [{}]\n", bits_str).unwrap();

    writeln!(out, "# Private witness: concatenated segment node visit orders (length N)").unwrap();
    let an_str = all_nodes.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "all_nodes = [{}]\n", an_str).unwrap();

    writeln!(out, "# Private witness: per-segment internal cost sums").unwrap();
    let pc_str = partial_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "partial_costs = [{}]\n", pc_str).unwrap();

    writeln!(out, "# Private witness: per-segment blinding scalars (commitment openings)").unwrap();
    writeln!(out, "r_is = [{}]\n", hexvec(r_is)).unwrap();

    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    writeln!(out, "# Public input: cycle cost upper bound").unwrap();
    writeln!(out, "# (actual cost = {}, threshold = {})", cost, threshold).unwrap();
    writeln!(out, "threshold = \"{}\"\n", threshold).unwrap();

    writeln!(out, "# Public input: per-segment blinded commitments (cross-checked vs sub_i.C_i)").unwrap();
    writeln!(out, "C_is = [{}]", hexvec(c_is)).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

fn run_hierarchical_c(args: &[String], input: Input, k: usize) {
    let out_dir = PathBuf::from(parse_named_arg(args, "--out-dir").unwrap_or_else(|| {
        eprintln!("Usage (hierarchical-c): merkle_builder --hierarchical-c K --out-dir <dir>");
        std::process::exit(1);
    }));

    let n = input.n;
    if k < 2 {
        eprintln!("Error: --hierarchical-c K requires K >= 2 (got {})", k);
        std::process::exit(1);
    }
    if n % k != 0 {
        eprintln!("Error: N={} must be divisible by K={} (got remainder {})", n, k, n % k);
        std::process::exit(1);
    }
    let m = n / k;

    let tree = get_tree(args, &input.flat_matrix);
    let root = tree.root();
    let depth = tree.depth;

    let mut all_nodes: Vec<usize>     = Vec::with_capacity(n);
    let mut starts: Vec<usize>        = Vec::with_capacity(k);
    let mut ends: Vec<usize>          = Vec::with_capacity(k);
    let mut partial_costs: Vec<u64>   = Vec::with_capacity(k);
    let mut r_is: Vec<FieldElement>   = Vec::with_capacity(k);
    let mut c_is: Vec<FieldElement>   = Vec::with_capacity(k);

    for seg in 0..k {
        let cycle_segment: Vec<usize> = input.cycle[seg * m..(seg + 1) * m].to_vec();
        let start_node = cycle_segment[0];
        let end_node   = cycle_segment[m - 1];

        let mut seg_edge_costs: Vec<u64> = Vec::with_capacity(m - 1);
        let mut seg_sibs: Vec<FieldElement> = Vec::with_capacity((m - 1) * depth as usize);
        let mut seg_bits: Vec<bool>         = Vec::with_capacity((m - 1) * depth as usize);
        for j in 0..(m - 1) {
            let from = cycle_segment[j];
            let to   = cycle_segment[j + 1];
            let leaf_idx = from * n + to;
            seg_edge_costs.push(input.flat_matrix[leaf_idx]);
            let (sibs, bits) = tree.proof(leaf_idx);
            seg_sibs.extend_from_slice(&sibs);
            seg_bits.extend_from_slice(&bits);
        }
        let partial_cost: u64 = seg_edge_costs.iter().sum();

        // Blinded commitment: fold(r, [cycle_segment..., partial_cost]).
        let r = random_field();
        let mut fold_vals: Vec<FieldElement> =
            cycle_segment.iter().map(|&v| FieldElement::from(v as u128)).collect();
        fold_vals.push(FieldElement::from(partial_cost as u128));
        let c_i = commit_fold(r, &fold_vals);

        all_nodes.extend_from_slice(&cycle_segment);
        starts.push(start_node);
        ends.push(end_node);
        partial_costs.push(partial_cost);
        r_is.push(r);
        c_is.push(c_i);

        let sub_path = out_dir.join(format!("sub_{}", seg)).join("Prover.toml");
        write_sub_c_prover_toml(
            &sub_path, seg,
            &cycle_segment, &seg_edge_costs, &seg_sibs, &seg_bits,
            r, root, c_i,
        )
        .unwrap_or_else(|e| {
            eprintln!("Error writing {}: {}", sub_path.display(), e);
            std::process::exit(1);
        });
    }

    // Glue: K boundary edges ends[i] -> starts[(i+1) % K].
    let mut boundary_costs: Vec<u64>          = Vec::with_capacity(k);
    let mut boundary_sibs:  Vec<FieldElement> = Vec::with_capacity(k * depth as usize);
    let mut boundary_bits:  Vec<bool>         = Vec::with_capacity(k * depth as usize);
    for i in 0..k {
        let from = ends[i];
        let to   = starts[(i + 1) % k];
        let leaf_idx = from * n + to;
        boundary_costs.push(input.flat_matrix[leaf_idx]);
        let (sibs, bits) = tree.proof(leaf_idx);
        boundary_sibs.extend_from_slice(&sibs);
        boundary_bits.extend_from_slice(&bits);
    }

    let glue_path = out_dir.join("glue").join("Prover.toml");
    write_glue_c_prover_toml(
        &glue_path,
        &boundary_costs, &boundary_sibs, &boundary_bits,
        &all_nodes, &partial_costs, &r_is,
        input.threshold, input.cost, root, &c_is,
    )
    .unwrap_or_else(|e| {
        eprintln!("Error writing {}: {}", glue_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "merkle_builder [hier-c K={}]: N={} M={} DEPTH={} root=0x{} -> {}/{{sub_0..sub_{},glue}}/Prover.toml",
        k, n, m, depth, &root.to_hex()[..8], out_dir.display(), k - 1
    );
}

fn run_hierarchical_cfs(args: &[String], input: Input, k: usize) {
    let out_dir = PathBuf::from(parse_named_arg(args, "--out-dir").unwrap_or_else(|| {
        eprintln!("Usage (hierarchical-cfs): merkle_builder --hierarchical-cfs K --out-dir <dir>");
        std::process::exit(1);
    }));

    let n = input.n;
    if k < 2 {
        eprintln!("Error: --hierarchical-cfs K requires K >= 2 (got {})", k);
        std::process::exit(1);
    }
    if n % k != 0 {
        eprintln!("Error: N={} must be divisible by K={} (got remainder {})", n, k, n % k);
        std::process::exit(1);
    }
    let m = n / k;

    let tree = get_tree(args, &input.flat_matrix);
    let root = tree.root();
    let depth = tree.depth;

    // Fiat-Shamir prelude (identical to run_hierarchical_fs): chain over the full
    // cycle, then X = Poseidon2([c],1).  c is now PRIVATE (folded into the glue).
    let mut h = vec![FieldElement::zero(); n + 1];
    for j in 0..n {
        h[j + 1] = poseidon2_compress(h[j], FieldElement::from(input.cycle[j] as u128));
    }
    let c = h[n];
    let x = poseidon2_hash_single(c);

    let mut starts: Vec<usize>        = Vec::with_capacity(k);
    let mut ends: Vec<usize>          = Vec::with_capacity(k);
    let mut partial_costs: Vec<u64>   = Vec::with_capacity(k);
    let mut p_is: Vec<FieldElement>   = Vec::with_capacity(k);
    let mut h_ins: Vec<FieldElement>  = Vec::with_capacity(k);
    let mut h_outs: Vec<FieldElement> = Vec::with_capacity(k);
    let mut r_is: Vec<FieldElement>   = Vec::with_capacity(k);
    let mut c_is: Vec<FieldElement>   = Vec::with_capacity(k);

    for seg in 0..k {
        let cycle_segment: Vec<usize> = input.cycle[seg * m..(seg + 1) * m].to_vec();
        let start_node = cycle_segment[0];
        let end_node   = cycle_segment[m - 1];

        let mut seg_edge_costs: Vec<u64> = Vec::with_capacity(m - 1);
        let mut seg_sibs: Vec<FieldElement> = Vec::with_capacity((m - 1) * depth as usize);
        let mut seg_bits: Vec<bool>         = Vec::with_capacity((m - 1) * depth as usize);
        for j in 0..(m - 1) {
            let from = cycle_segment[j];
            let to   = cycle_segment[j + 1];
            let leaf_idx = from * n + to;
            seg_edge_costs.push(input.flat_matrix[leaf_idx]);
            let (sibs, bits) = tree.proof(leaf_idx);
            seg_sibs.extend_from_slice(&sibs);
            seg_bits.extend_from_slice(&bits);
        }
        let partial_cost: u64 = seg_edge_costs.iter().sum();

        let mut p_i = FieldElement::one();
        for &node in &cycle_segment {
            p_i = p_i * (x + FieldElement::from(node as u128));
        }

        let h_in  = h[seg * m];
        let h_out = h[(seg + 1) * m];

        // Blinded commitment: fold(r, [P_i, h_in, h_out, start, end, partial_cost]).
        let r = random_field();
        let c_i = commit_fold(
            r,
            &[
                p_i,
                h_in,
                h_out,
                FieldElement::from(start_node as u128),
                FieldElement::from(end_node as u128),
                FieldElement::from(partial_cost as u128),
            ],
        );

        starts.push(start_node);
        ends.push(end_node);
        partial_costs.push(partial_cost);
        p_is.push(p_i);
        h_ins.push(h_in);
        h_outs.push(h_out);
        r_is.push(r);
        c_is.push(c_i);

        let sub_path = out_dir.join(format!("sub_{}", seg)).join("Prover.toml");
        write_sub_cfs_prover_toml(
            &sub_path, seg,
            &cycle_segment, &seg_edge_costs, &seg_sibs, &seg_bits,
            h_in, r, root, x, c_i,
        )
        .unwrap_or_else(|e| {
            eprintln!("Error writing {}: {}", sub_path.display(), e);
            std::process::exit(1);
        });
    }

    // Glue: K boundary edges ends[i] -> starts[(i+1) % K].
    let mut boundary_costs: Vec<u64>          = Vec::with_capacity(k);
    let mut boundary_sibs:  Vec<FieldElement> = Vec::with_capacity(k * depth as usize);
    let mut boundary_bits:  Vec<bool>         = Vec::with_capacity(k * depth as usize);
    for i in 0..k {
        let from = ends[i];
        let to   = starts[(i + 1) % k];
        let leaf_idx = from * n + to;
        boundary_costs.push(input.flat_matrix[leaf_idx]);
        let (sibs, bits) = tree.proof(leaf_idx);
        boundary_sibs.extend_from_slice(&sibs);
        boundary_bits.extend_from_slice(&bits);
    }

    let glue_path = out_dir.join("glue").join("Prover.toml");
    write_glue_cfs_prover_toml(
        &glue_path,
        &boundary_costs, &boundary_sibs, &boundary_bits,
        &starts, &ends, &partial_costs,
        &p_is, &h_ins, &h_outs, &r_is, c,
        input.threshold, input.cost, root, x, &c_is,
    )
    .unwrap_or_else(|e| {
        eprintln!("Error writing {}: {}", glue_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "merkle_builder [hier-cfs K={}]: N={} M={} DEPTH={} root=0x{} X=0x{} -> {}/{{sub_0..sub_{},glue}}/Prover.toml",
        k, n, m, depth, &root.to_hex()[..8], &x.to_hex()[..8], out_dir.display(), k - 1
    );
}

// ── committed-A++ helpers + Prover.toml writers ──────────────────────────────

/// Blinded commitment fold matching the Noir circuits' G8/G0:
///   acc = r; for v in vals { acc = Poseidon2::hash([acc, v], 2) }
/// Uses only the 2-input compression cross-validated in tests/hash_compat.
fn commit_fold(r: FieldElement, vals: &[FieldElement]) -> FieldElement {
    let mut acc = r;
    for &v in vals {
        acc = poseidon2_compress(acc, v);
    }
    acc
}

/// Sample a uniform blinding scalar from /dev/urandom (128 bits of entropy is
/// ample to make the commitment hiding; reduced into the field via from(u128)).
/// Dependency-free: the builder has no `rand` crate.
fn random_field() -> FieldElement {
    use std::io::Read;
    let mut buf = [0u8; 16];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut buf))
        .expect("read /dev/urandom for blinding");
    FieldElement::from(u128::from_le_bytes(buf))
}

/// Write Prover.toml for circuits/hierarchical_segment_cfs for one segment.
/// Public: root, X, C_i.  Everything else is private witness.
fn write_sub_cfs_prover_toml(
    out_path: &PathBuf,
    seg_idx: usize,
    cycle_segment: &[usize],
    edge_costs: &[u64],
    siblings_flat: &[FieldElement],
    path_bits_flat: &[bool],
    h_in: FieldElement,
    r: FieldElement,
    root: FieldElement,
    x: FieldElement,
    c_i: FieldElement,
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    writeln!(out, "# hierarchical_segment_cfs Prover.toml -- segment {}", seg_idx).unwrap();
    writeln!(out, "# Variant committed-A++ sub-circuit. Public: root, X, C_i.").unwrap();
    writeln!(out, "# (start/end/partial_cost/P_i/h_in/h_out are folded into the blinded C_i.)").unwrap();
    writeln!(out).unwrap();

    writeln!(out, "# Private witness: segment node visit order (M entries)").unwrap();
    let seg_str = cycle_segment.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "cycle_segment = [{}]\n", seg_str).unwrap();

    writeln!(out, "# Private witness: M-1 internal edge costs").unwrap();
    let costs_str = edge_costs.iter().map(|v| format!("\"{}\"", v)).collect::<Vec<_>>().join(", ");
    writeln!(out, "edge_costs = [{}]\n", costs_str).unwrap();

    writeln!(out, "# Private witness: Poseidon2 Merkle siblings, flat row-major over (M-1) edge proofs").unwrap();
    let sibs_str = siblings_flat.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");
    writeln!(out, "siblings = [{}]\n", sibs_str).unwrap();

    writeln!(out, "# Private witness: LSB-first leaf-index encoding, flat row-major").unwrap();
    let bits_str = path_bits_flat.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "path_bits = [{}]\n", bits_str).unwrap();

    writeln!(out, "# Private witness: chain value entering this segment").unwrap();
    writeln!(out, "h_in_i = \"0x{}\"\n", h_in.to_hex()).unwrap();

    writeln!(out, "# Private witness: blinding scalar (makes C_i hiding)").unwrap();
    writeln!(out, "r = \"0x{}\"\n", r.to_hex()).unwrap();

    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    writeln!(out, "# Public input: Fiat-Shamir challenge X = Poseidon2([c],1) (shared across K+1)").unwrap();
    writeln!(out, "X = \"0x{}\"\n", x.to_hex()).unwrap();

    writeln!(out, "# Public input: blinded commitment to this segment's values").unwrap();
    writeln!(out, "C_i = \"0x{}\"", c_i.to_hex()).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

/// Write Prover.toml for circuits/hierarchical_glue_cfs.
/// Public: root, threshold, X, C_is.  Everything else is private witness.
fn write_glue_cfs_prover_toml(
    out_path: &PathBuf,
    boundary_costs: &[u64],
    boundary_siblings: &[FieldElement],
    boundary_path_bits: &[bool],
    starts: &[usize],
    ends: &[usize],
    partial_costs: &[u64],
    p_is: &[FieldElement],
    h_ins: &[FieldElement],
    h_outs: &[FieldElement],
    r_is: &[FieldElement],
    c: FieldElement,
    threshold: u64,
    cost: u64,
    root: FieldElement,
    x: FieldElement,
    c_is: &[FieldElement],
) -> io::Result<()> {
    use std::fmt::Write as FmtWrite;
    let mut out = String::new();

    let hexvec = |v: &[FieldElement]| v.iter().map(|f| format!("\"0x{}\"", f.to_hex())).collect::<Vec<_>>().join(", ");
    let decvec = |v: &[usize]| v.iter().map(|x| format!("\"{}\"", x)).collect::<Vec<_>>().join(", ");
    let decvec64 = |v: &[u64]| v.iter().map(|x| format!("\"{}\"", x)).collect::<Vec<_>>().join(", ");

    writeln!(out, "# hierarchical_glue_cfs Prover.toml").unwrap();
    writeln!(out, "# Variant committed-A++ glue. Public: root, threshold, X, C_is.").unwrap();
    writeln!(out, "# (starts/ends/partial_costs/P_is/h_ins/h_outs/c are private witness.)").unwrap();
    writeln!(out).unwrap();

    writeln!(out, "# Private witness: K boundary-edge costs").unwrap();
    writeln!(out, "boundary_costs = [{}]\n", decvec64(boundary_costs)).unwrap();

    writeln!(out, "# Private witness: Poseidon2 Merkle siblings for the K boundary-edge proofs").unwrap();
    writeln!(out, "boundary_siblings = [{}]\n", hexvec(boundary_siblings)).unwrap();

    writeln!(out, "# Private witness: LSB-first leaf-index encoding for boundary-edge proofs").unwrap();
    let bits_str = boundary_path_bits.iter().map(|b| if *b { "true" } else { "false" }).collect::<Vec<_>>().join(", ");
    writeln!(out, "boundary_path_bits = [{}]\n", bits_str).unwrap();

    writeln!(out, "# Private witness: per-segment endpoints").unwrap();
    writeln!(out, "starts = [{}]", decvec(starts)).unwrap();
    writeln!(out, "ends = [{}]\n", decvec(ends)).unwrap();

    writeln!(out, "# Private witness: per-segment internal cost sums").unwrap();
    writeln!(out, "partial_costs = [{}]\n", decvec64(partial_costs)).unwrap();

    writeln!(out, "# Private witness: per-segment grand products").unwrap();
    writeln!(out, "P_is = [{}]\n", hexvec(p_is)).unwrap();

    writeln!(out, "# Private witness: per-segment chain anchors").unwrap();
    writeln!(out, "h_ins = [{}]", hexvec(h_ins)).unwrap();
    writeln!(out, "h_outs = [{}]\n", hexvec(h_outs)).unwrap();

    writeln!(out, "# Private witness: per-segment blinding scalars (commitment openings)").unwrap();
    writeln!(out, "r_is = [{}]\n", hexvec(r_is)).unwrap();

    writeln!(out, "# Private witness: full-cycle chain terminal c").unwrap();
    writeln!(out, "c = \"0x{}\"\n", c.to_hex()).unwrap();

    writeln!(out, "# Public input: Poseidon2 Merkle root of the N*N cost matrix").unwrap();
    writeln!(out, "root = \"0x{}\"\n", root.to_hex()).unwrap();

    writeln!(out, "# Public input: cycle cost upper bound").unwrap();
    writeln!(out, "# (actual cost = {}, threshold = {})", cost, threshold).unwrap();
    writeln!(out, "threshold = \"{}\"\n", threshold).unwrap();

    writeln!(out, "# Public input: Fiat-Shamir challenge X = Poseidon2([c],1)").unwrap();
    writeln!(out, "X = \"0x{}\"\n", x.to_hex()).unwrap();

    writeln!(out, "# Public input: per-segment blinded commitments (cross-checked vs sub_i.C_i)").unwrap();
    writeln!(out, "C_is = [{}]", hexvec(c_is)).unwrap();

    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out_path, out)?;
    Ok(())
}

// ── Main ──────────────────────────────────────────────────────────────────────

fn parse_named_arg(args: &[String], name: &str) -> Option<String> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1).cloned())
}

fn run_flat(args: &[String], input: Input) {
    let out_path = PathBuf::from(parse_named_arg(args, "--out").unwrap_or_else(|| {
        eprintln!("Usage (flat): merkle_builder --out <Prover.toml path>");
        std::process::exit(1);
    }));

    let n = input.n;
    let tree = get_tree(args, &input.flat_matrix);
    let root = tree.root();
    let depth = tree.depth;

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

    write_prover_toml(
        &out_path, n, depth,
        &input.cycle, &edge_costs, &siblings_flat, &path_bits_flat,
        root, input.threshold, input.cost,
    )
    .unwrap_or_else(|e| {
        eprintln!("Error writing {}: {}", out_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "merkle_builder [flat]: N={} DEPTH={} root=0x{} -> {}",
        n, depth, &root.to_hex()[..8], out_path.display()
    );
}

fn run_hierarchical(args: &[String], input: Input, k: usize) {
    let out_dir = PathBuf::from(parse_named_arg(args, "--out-dir").unwrap_or_else(|| {
        eprintln!("Usage (hierarchical): merkle_builder --hierarchical K --out-dir <dir>");
        std::process::exit(1);
    }));

    let n = input.n;
    if k < 2 {
        eprintln!("Error: --hierarchical K requires K >= 2 (got {})", k);
        std::process::exit(1);
    }
    if n % k != 0 {
        eprintln!("Error: N={} must be divisible by K={} (got remainder {})", n, k, n % k);
        std::process::exit(1);
    }
    let m = n / k;

    let tree = get_tree(args, &input.flat_matrix);
    let root = tree.root();
    let depth = tree.depth;

    // Per-segment outputs.
    let mut all_sorted_nodes: Vec<usize> = Vec::with_capacity(n);
    let mut starts: Vec<usize>            = Vec::with_capacity(k);
    let mut ends: Vec<usize>              = Vec::with_capacity(k);
    let mut partial_costs: Vec<u64>       = Vec::with_capacity(k);

    for seg in 0..k {
        // cycle_segment = cycle[seg*M .. (seg+1)*M]
        let cycle_segment: Vec<usize> = input.cycle[seg * m..(seg + 1) * m].to_vec();
        let start_node = cycle_segment[0];
        let end_node   = cycle_segment[m - 1];

        // Internal edges: M-1 per segment.
        let mut seg_edge_costs: Vec<u64> = Vec::with_capacity(m - 1);
        let mut seg_sibs: Vec<FieldElement> = Vec::with_capacity((m - 1) * depth as usize);
        let mut seg_bits: Vec<bool>         = Vec::with_capacity((m - 1) * depth as usize);
        for j in 0..(m - 1) {
            let from = cycle_segment[j];
            let to   = cycle_segment[j + 1];
            let leaf_idx = from * n + to;
            seg_edge_costs.push(input.flat_matrix[leaf_idx]);
            let (sibs, bits) = tree.proof(leaf_idx);
            seg_sibs.extend_from_slice(&sibs);
            seg_bits.extend_from_slice(&bits);
        }
        let partial_cost: u64 = seg_edge_costs.iter().sum();

        // sorted_nodes = sorted(cycle_segment) ascending.
        let mut sorted_nodes = cycle_segment.clone();
        sorted_nodes.sort_unstable();

        // Stash for the glue file.
        all_sorted_nodes.extend_from_slice(&sorted_nodes);
        starts.push(start_node);
        ends.push(end_node);
        partial_costs.push(partial_cost);

        // Write sub_<seg>/Prover.toml.
        let sub_path = out_dir.join(format!("sub_{}", seg)).join("Prover.toml");
        write_sub_prover_toml(
            &sub_path, seg,
            &cycle_segment, &seg_edge_costs, &seg_sibs, &seg_bits,
            &sorted_nodes, start_node, end_node, partial_cost, root,
        )
        .unwrap_or_else(|e| {
            eprintln!("Error writing {}: {}", sub_path.display(), e);
            std::process::exit(1);
        });
    }

    // Glue: K boundary edges ends[i] -> starts[(i+1) % K].
    let mut boundary_costs: Vec<u64>         = Vec::with_capacity(k);
    let mut boundary_sibs:  Vec<FieldElement> = Vec::with_capacity(k * depth as usize);
    let mut boundary_bits:  Vec<bool>         = Vec::with_capacity(k * depth as usize);
    for i in 0..k {
        let from = ends[i];
        let to   = starts[(i + 1) % k];
        let leaf_idx = from * n + to;
        boundary_costs.push(input.flat_matrix[leaf_idx]);
        let (sibs, bits) = tree.proof(leaf_idx);
        boundary_sibs.extend_from_slice(&sibs);
        boundary_bits.extend_from_slice(&bits);
    }

    let glue_path = out_dir.join("glue").join("Prover.toml");
    write_glue_prover_toml(
        &glue_path,
        &boundary_costs, &boundary_sibs, &boundary_bits,
        &all_sorted_nodes, &starts, &ends, &partial_costs,
        input.threshold, input.cost, root,
    )
    .unwrap_or_else(|e| {
        eprintln!("Error writing {}: {}", glue_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "merkle_builder [hier K={}]: N={} M={} DEPTH={} root=0x{} -> {}/{{sub_0..sub_{},glue}}/Prover.toml",
        k, n, m, depth, &root.to_hex()[..8], out_dir.display(), k - 1
    );
}

fn run_hierarchical_fs(args: &[String], input: Input, k: usize) {
    let out_dir = PathBuf::from(parse_named_arg(args, "--out-dir").unwrap_or_else(|| {
        eprintln!("Usage (hierarchical-fs): merkle_builder --hierarchical-fs K --out-dir <dir>");
        std::process::exit(1);
    }));

    let n = input.n;
    if k < 2 {
        eprintln!("Error: --hierarchical-fs K requires K >= 2 (got {})", k);
        std::process::exit(1);
    }
    if n % k != 0 {
        eprintln!("Error: N={} must be divisible by K={} (got remainder {})", n, k, n % k);
        std::process::exit(1);
    }
    let m = n / k;

    let tree = get_tree(args, &input.flat_matrix);
    let root = tree.root();
    let depth = tree.depth;

    // ── Fiat-Shamir prelude: hash chain over the full cycle, then challenge X ──
    // h[0] = 0; h[j+1] = Poseidon2(h[j], cycle[j]); c = h[N]; X = Poseidon2([c],1).
    let mut h = vec![FieldElement::zero(); n + 1];
    for j in 0..n {
        h[j + 1] = poseidon2_compress(h[j], FieldElement::from(input.cycle[j] as u128));
    }
    let c = h[n];
    let x = poseidon2_hash_single(c);

    // Per-segment outputs (mirrors run_hierarchical; adds P_i, h_in, h_out).
    let mut starts: Vec<usize>            = Vec::with_capacity(k);
    let mut ends: Vec<usize>              = Vec::with_capacity(k);
    let mut partial_costs: Vec<u64>       = Vec::with_capacity(k);
    let mut p_is: Vec<FieldElement>       = Vec::with_capacity(k);
    let mut h_ins: Vec<FieldElement>      = Vec::with_capacity(k);
    let mut h_outs: Vec<FieldElement>     = Vec::with_capacity(k);

    for seg in 0..k {
        let cycle_segment: Vec<usize> = input.cycle[seg * m..(seg + 1) * m].to_vec();
        let start_node = cycle_segment[0];
        let end_node   = cycle_segment[m - 1];

        // Internal edges: M-1 per segment (identical to run_hierarchical).
        let mut seg_edge_costs: Vec<u64> = Vec::with_capacity(m - 1);
        let mut seg_sibs: Vec<FieldElement> = Vec::with_capacity((m - 1) * depth as usize);
        let mut seg_bits: Vec<bool>         = Vec::with_capacity((m - 1) * depth as usize);
        for j in 0..(m - 1) {
            let from = cycle_segment[j];
            let to   = cycle_segment[j + 1];
            let leaf_idx = from * n + to;
            seg_edge_costs.push(input.flat_matrix[leaf_idx]);
            let (sibs, bits) = tree.proof(leaf_idx);
            seg_sibs.extend_from_slice(&sibs);
            seg_bits.extend_from_slice(&bits);
        }
        let partial_cost: u64 = seg_edge_costs.iter().sum();

        // Grand product P_i = prod_j (X + cycle_segment[j]).
        let mut p_i = FieldElement::one();
        for &node in &cycle_segment {
            p_i = p_i * (x + FieldElement::from(node as u128));
        }

        // Chain anchors: h_in = h[seg*M], h_out = h[(seg+1)*M].
        let h_in  = h[seg * m];
        let h_out = h[(seg + 1) * m];

        starts.push(start_node);
        ends.push(end_node);
        partial_costs.push(partial_cost);
        p_is.push(p_i);
        h_ins.push(h_in);
        h_outs.push(h_out);

        let sub_path = out_dir.join(format!("sub_{}", seg)).join("Prover.toml");
        write_sub_fs_prover_toml(
            &sub_path, seg,
            &cycle_segment, &seg_edge_costs, &seg_sibs, &seg_bits,
            start_node, end_node, partial_cost, root,
            p_i, h_in, h_out, c, x,
        )
        .unwrap_or_else(|e| {
            eprintln!("Error writing {}: {}", sub_path.display(), e);
            std::process::exit(1);
        });
    }

    // Glue: K boundary edges ends[i] -> starts[(i+1) % K] (identical to run_hierarchical).
    let mut boundary_costs: Vec<u64>          = Vec::with_capacity(k);
    let mut boundary_sibs:  Vec<FieldElement> = Vec::with_capacity(k * depth as usize);
    let mut boundary_bits:  Vec<bool>         = Vec::with_capacity(k * depth as usize);
    for i in 0..k {
        let from = ends[i];
        let to   = starts[(i + 1) % k];
        let leaf_idx = from * n + to;
        boundary_costs.push(input.flat_matrix[leaf_idx]);
        let (sibs, bits) = tree.proof(leaf_idx);
        boundary_sibs.extend_from_slice(&sibs);
        boundary_bits.extend_from_slice(&bits);
    }

    let glue_path = out_dir.join("glue").join("Prover.toml");
    write_glue_fs_prover_toml(
        &glue_path,
        &boundary_costs, &boundary_sibs, &boundary_bits,
        &starts, &ends, &partial_costs,
        input.threshold, input.cost, root,
        &p_is, &h_ins, &h_outs, c, x,
    )
    .unwrap_or_else(|e| {
        eprintln!("Error writing {}: {}", glue_path.display(), e);
        std::process::exit(1);
    });

    eprintln!(
        "merkle_builder [hier-fs K={}]: N={} M={} DEPTH={} root=0x{} c=0x{} X=0x{} -> {}/{{sub_0..sub_{},glue}}/Prover.toml",
        k, n, m, depth, &root.to_hex()[..8], &c.to_hex()[..8], &x.to_hex()[..8], out_dir.display(), k - 1
    );
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    // ── Read input JSON from stdin (shared by both modes) ────────────────────
    let mut json_buf = String::new();
    io::stdin().read_to_string(&mut json_buf).unwrap_or_else(|e| {
        eprintln!("Error reading stdin: {}", e);
        std::process::exit(1);
    });
    let input: Input = serde_json::from_str(&json_buf).unwrap_or_else(|e| {
        eprintln!("Error parsing input JSON: {}", e);
        std::process::exit(1);
    });

    // ── Validate (shared) ────────────────────────────────────────────────────
    let n = input.n;
    if input.flat_matrix.len() != n * n {
        eprintln!("Error: flat_matrix length {} != n*n={}", input.flat_matrix.len(), n * n);
        std::process::exit(1);
    }
    if input.cycle.len() != n {
        eprintln!("Error: cycle length {} != n={}", input.cycle.len(), n);
        std::process::exit(1);
    }
    for (i, &v) in input.cycle.iter().enumerate() {
        if v >= n {
            eprintln!("Error: cycle[{}] = {} is out of range [0, {})", i, v, n);
            std::process::exit(1);
        }
    }

    // ── Dispatch on --hierarchical-fs K / --hierarchical K / flat ────────────
    if let Some(k_str) = parse_named_arg(&args, "--hierarchical-cfs") {
        let k: usize = k_str.parse().unwrap_or_else(|_| {
            eprintln!("Error: --hierarchical-cfs expects a positive integer K (got {:?})", k_str);
            std::process::exit(1);
        });
        run_hierarchical_cfs(&args, input, k);
    } else if let Some(k_str) = parse_named_arg(&args, "--hierarchical-c") {
        let k: usize = k_str.parse().unwrap_or_else(|_| {
            eprintln!("Error: --hierarchical-c expects a positive integer K (got {:?})", k_str);
            std::process::exit(1);
        });
        run_hierarchical_c(&args, input, k);
    } else if let Some(k_str) = parse_named_arg(&args, "--hierarchical-fs") {
        let k: usize = k_str.parse().unwrap_or_else(|_| {
            eprintln!("Error: --hierarchical-fs expects a positive integer K (got {:?})", k_str);
            std::process::exit(1);
        });
        run_hierarchical_fs(&args, input, k);
    } else if let Some(k_str) = parse_named_arg(&args, "--hierarchical") {
        let k: usize = k_str.parse().unwrap_or_else(|_| {
            eprintln!("Error: --hierarchical expects a positive integer K (got {:?})", k_str);
            std::process::exit(1);
        });
        run_hierarchical(&args, input, k);
    } else {
        run_flat(&args, input);
    }
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
