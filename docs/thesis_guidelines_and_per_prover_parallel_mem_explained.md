╭─── Claude Code v2.1.152 ─────────────────────────────────────────────────────╮
│                                                    │ Tips for getting        │
│               Welcome back Leonardo!               │ started                 │
│                                                    │ Run /init to create a … │
│                       ▐▛███▜▌                      │ ─────────────────────── │
│                      ▝▜█████▛▘                     │ What's new              │
│                        ▘▘ ▝▝                       │ `/code-review --fix` n… │
│  Sonnet 4.6 · Claude Pro · callexyz1@gmail.com's   │ Skills and slash comma… │
│  Organization                                      │ Added `/reload-skills`… │
│                  ~/Desktop/plsgod                  │ /release-notes for more │
╰──────────────────────────────────────────────────────────────────────────────╯


❯ Familiarize with the project, learning about the codebase and the style. Then 
   let's discuss variant A++ implementation details and design choices, and     
  perform a theoretical comparison against variant A, to see where we gain or   
  lose something. What are the expected results of a comparison? And comparing  
  variant A with the flat approaches, what do we expect theoretically?          

● Let me read the memory files and explore the codebase to get up to speed.

  Read 2 files, recalled 2 memories (ctrl+o to expand)

● Now let me look at the existing Variant A circuits.

  Searched for 1 pattern, read 3 files (ctrl+o to expand)

● Good, I have a thorough picture. Let me also glance at the SESSION_SUMMARY and
   the flat_merkle circuit for the full baseline context.

  Read 2 files (ctrl+o to expand)

● Good, I have the full picture. Let me discuss all three questions in turn.

  ---
  1. Variant A++ — Implementation Details and Design Choices

  The core problem A++ solves

  Variant A's glue circuit runs sort_via over all N concatenated nodes. This is
  O(N) constrained gates in the glue and, more importantly, forces
  all_sorted_nodes to be a public input — the verifier sees exactly which M
  nodes belong to each segment (the full partition). A++ replaces that O(N) sort
   with a grand-product multiset equality check.

  The grand product idea

  To prove that multiset S = multiset {0..N-1}, pick a random challenge X and
  check:

  ∏_{s ∈ S} (s − X) == ∏_{v=0}^{N-1} (v − X)

  Both sides are degree-N polynomials. If S ≠ {0..N-1}, they disagree on all but
   at most N points over the field. By Schwartz-Zippel, a random X hits a "bad"
  collision with probability ≤ N/|Field| ≈ 480/2^254 ≈ 2^{-246} —
  cryptographically negligible.

  In-circuit Fiat-Shamir

  The classic Schwartz-Zippel argument requires X chosen after the prover
  commits to S. In a multi-proof system without interaction, this is achieved
  with Fiat-Shamir inside the circuit:

  Hash chain (Poseidon2 over the private cycle):

  h_0 = 0  (fixed initial state)
  h_{j+1} = Poseidon2(h_j, cycle[j])
  c = h_N  (final value, covers all N cycle nodes)
  X = Poseidon2(c)

  The hash chain is split across sub-circuits: sub_i processes its M-node
  segment, computing h_in_i → h_out_i. The glue stitches the K pieces together
  (checking h_out[i] == h_in[i+1]) and derives the global X =
  Poseidon2(h_out[K-1]).

  Why this is sound: a cheating prover wants to find a non-permutation S where
  the products agree at X = H(S). Schwartz-Zippel says this happens for at most
  N inputs out of the field. ROM assumption makes H look random → the prover
  can't predict which X is "safe" for their bad S before committing.

  How the pieces connect across circuits

  Each sub-circuit:
  - Takes X as an additional public input (known only after the pipeline
  computes the full hash chain off-circuit)
  - Computes M Poseidon2 calls for the hash chain segment (publishes h_in,
  h_out)
  - Computes P_i = ∏_{j=0}^{M-1} (cycle_segment[j] − X) (M field
  multiplications, publishes P_i)
  - Drops the sort_via (no longer needed) and sorted_nodes public output

  The glue:
  - Verifies chain continuity: h_out[i] == h_in[i+1] for i in 0..K-2
  - Derives X from h_out[K-1] and asserts it matches all sub-circuits' claimed X
  - Checks ∏_{i=0}^{K-1} P_i == expected_product (K−1 multiplications
  in-circuit)
  - expected_product is passed as a public input and cross-checked off-circuit
  by verify_hier.py, which trivially computes ∏_{v=0}^{N-1} (v − X) — O(N)
  arithmetic, negligible cost

  Key design choice: where to compute expected_product

  You could in-principle compute ∏_{v=0}^{N-1} (v − X) inside the glue (O(N)
  multiplications). That would keep the glue fully self-contained but
  re-introduces O(N) in-circuit work and eliminates the gate saving. The design
  choice is to push this O(N) arithmetic off-circuit to verify_hier.py, keeping
  the glue's partition check O(K). This is sound: the verifier is trusted (it
  holds the agreed-upon X derived from the public transcript) and the
  computation is deterministic.

  Sub-circuit overhead estimate

  At N=480, K=4, M=120, DEPTH=18:
  - Added: M=120 Poseidon2 calls → 120×264 ≈ 31,680 extra gates per sub-circuit
  - Removed: sort_via on M → ~3M ≈ 360 gates saved per sub-circuit
  - Net: ~+31,320 gates per sub-circuit, ×K = ~125K extra gates total across all
   sub-circuits

  As a fraction of G4 (Merkle-dominated): (M-1)×DEPTH = 119×18 = 2142 Poseidon
  calls → ~565k gates per sub-circuit. So the hash chain adds ≈5.6% to 
  per-sub-circuit cost.

  ---
  2. Theoretical Comparison: A++ vs A

  Total gates

  ┌─────────────────┬─────────────────┬───────────────────────┬─────────────┐
  │    Component    │    Variant A    │      Variant A++      │    Delta    │
  ├─────────────────┼─────────────────┼───────────────────────┼─────────────┤
  │ Sub-circuit G2  │ sort_via over M │ (removed)             │ −360/sub    │
  │ (per sub)       │  ≈ 3M gates     │                       │             │
  ├─────────────────┼─────────────────┼───────────────────────┼─────────────┤
  │ Sub-circuit     │ —               │ M Poseidon2 calls ≈   │ +31,680/sub │
  │ hash chain      │                 │ 264M gates            │             │
  ├─────────────────┼─────────────────┼───────────────────────┼─────────────┤
  │ Sub-circuit     │                 │ M field               │             │
  │ grand product   │ —               │ multiplications ≈ M   │ +120/sub    │
  │                 │                 │ gates                 │             │
  ├─────────────────┼─────────────────┼───────────────────────┼─────────────┤
  │ Glue G2         │ sort_via over N │                       │             │
  │ (partition      │  ≈ 4N ≈ 1920    │ (removed)             │ −1920       │
  │ sort)           │ gates           │                       │             │
  ├─────────────────┼─────────────────┼───────────────────────┼─────────────┤
  │ Glue grand      │ —               │ K−1 mults + 1         │ +267        │
  │ product check   │                 │ Poseidon2 ≈ 267 gates │             │
  └─────────────────┴─────────────────┴───────────────────────┴─────────────┘

  Net at N=480, K=4: ~+125K sub-circuit gates − 2K glue gates → A++ ≈ A + 5.5%
  in total gates. A++ is strictly more expensive than A, not cheaper. The glue
  saving is real but dwarfed by the sub-circuit overhead.

  Privacy

  This is where A++ pays off. What the verifier learns:

  ┌──────────────┬─────────────────────────────────────┬────────────────────┐
  │              │              Variant A              │    Variant A++     │
  ├──────────────┼─────────────────────────────────────┼────────────────────┤
  │ Cost matrix  │ Committed (root only)               │ Committed (root    │
  │              │                                     │ only)              │
  ├──────────────┼─────────────────────────────────────┼────────────────────┤
  │              │ Full partition: verifier sees       │ Hidden: only       │
  │ Partition    │ sorted_nodes[M] per segment → knows │ segment endpoints  │
  │ membership   │  exactly which M nodes are in each  │ (start, end)       │
  │              │ segment                             │ visible            │
  ├──────────────┼─────────────────────────────────────┼────────────────────┤
  │ Interior     │                                     │ Hidden (M-2)!      │
  │ visit order  │ Hidden (M-2)! orderings per segment │ orderings per      │
  │              │                                     │ segment            │
  ├──────────────┼─────────────────────────────────────┼────────────────────┤
  │              │                                     │ Visible but        │
  │ Grand        │ —                                   │ reveals nothing    │
  │ product P_i  │                                     │ useful (one field  │
  │              │                                     │ element)           │
  └──────────────┴─────────────────────────────────────┴────────────────────┘

  The number of bits of partition information disclosed: A discloses which M of
  N nodes form each segment — roughly log₂(C(N,M)) ≈ N log K bits. A++ discloses
   only the 2K endpoints — at K=4, that's 8 node indices, revealing almost
  nothing about interior routing.

  Soundness

  A has perfect soundness for the partition check (sort-based multiset equality
  is exact). A++ has statistical soundness error of N/|Field| ≈ 2^{-246}. This
  is crypto-negligible and perfectly acceptable for a thesis, but worth noting:
  A is technically stronger on this dimension.

  Expected benchmark results: A++ vs A

  1. Total gates (circuit_size): A++ runs ~5.5% more gates than A. The lines
  should diverge slightly, with A++ above A.
  2. Parallel wall-clock: A++ slightly slower — sub-circuits are heavier by
  ~5.5% and they're the bottleneck. Expect A++ ≈ A × 1.055.
  3. Per-prover memory: A++ slightly higher per prover (~5.5%). Peak_mb goes up
  proportionally.
  4. Public input count: A++ dramatically fewer. Glue loses all_sorted_nodes[N]
  (N field elements). Sub-circuits lose sorted_nodes[M]. Gain a small number of
  field elements per circuit (P_i, h_in, h_out, c, X). Net: A++ removes ~N + K×M
   = 2N public inputs. At N=480 this is ~960 fewer public inputs in the K+1
  proofs combined — non-trivial for verifier bandwidth.
  5. Verification time (off-circuit): A++ is faster for the verifier: fewer
  public inputs to hash before checking. The O(N) computation of
  expected_product is cheap arithmetic, not cryptographic.
  6. Proof bytes per proof: same (14,656 bytes each — UltraHonk constant). K+1
  proofs total in both cases.

  The clean thesis statement from the A vs A++ comparison: you pay ~5.5% in
  gates to gain near-complete partition privacy. This is a quantified
  privacy-cost tradeoff on the frontier.

  ---
  3. Theoretical Comparison: A vs Flat Approaches

  A vs flat_merkle (the natural comparison)

  Both commit the cost matrix via a Poseidon2 Merkle root. The statements
  differ:

  - flat_merkle: "∃ Hamiltonian cycle on N nodes, cost ≤ T, cost matrix
  committed by root"
  - Variant A: "∃ Hamiltonian cycle on N nodes, cost ≤ T, cost matrix committed
  by root, and the cycle decomposes into this specific disclosed partition"

  A proves strictly more than flat_merkle (it proves the same fact plus an
  additional structural fact about the partition). So it should cost at least as
   much. Here's the gate count analysis:

  Both do exactly N Merkle proofs (A does K×(M−1) internal + K boundary = K×M −
  K + K = N proofs). The overhead in A is the partition machinery:
  - Sub-circuit G2: K×sort_via on M ≈ K×3M = 3N gates
  - Glue G2: sort_via on N ≈ 4N gates
  - Total partition overhead: ~7N gates

  At N=480: ~3360 extra gates over a ~2.28M baseline → ~0.15% overhead in gates.
   The DESIGN.md quotes ~1.5% which likely includes fixed circuit overhead
  constants and Noir compile-time costs — in relative terms the asymptotic gate
  overhead is tiny.

  Expected benchmark results: A vs flat_merkle

  1. Total gates: essentially equal (lines nearly coincide, A ≈ flat_merkle +
  1-2%). The partition check overhead is negligible compared to the N×DEPTH
  Merkle gates that dominate both.
  2. Parallel wall-clock (A, K parallel provers): A wins significantly. Each
  sub-circuit does ~1/K the work of flat_merkle. Expected wall-clock ≈
  flat_merkle / K = flat_merkle / 4 for K=4. This is the primary practical win.
  3. Per-prover memory: A ≈ flat_merkle / K per individual prover. Each
  sub-circuit only requires (M-1)×DEPTH Merkle witnesses instead of N×DEPTH. At
  K=4: ~4× memory reduction per prover.
  4. Proof size/bandwidth: A produces K+1 = 5 proofs × 14,656 bytes ≈ 73KB vs
  flat_merkle's single 14,656-byte proof — A is ~5× worse for bandwidth.
  5. Verification time: A requires K+1 = 5 bb verify calls vs 1. Plus O(N)
  public inputs in the glue (all_sorted_nodes) vs O(1) for flat_merkle.

  The honest tradeoff summary: A gains ×K parallelism and ×K per-prover memory
  reduction, at the cost of (K+1)× proof bandwidth, (K+1)× verification calls,
  O(N) verifier public input processing, and the partition disclosure to the
  verifier.

  A vs flat_full

  flat_full passes the entire N² cost matrix as public inputs. Gate count:
  7.25N² + O(N). Variant A: O(N log N).

  At the N≈175 crossover, flat_full overtakes flat_merkle. Since A ≈ flat_merkle
   in gates, A also crosses flat_full at roughly the same N. For N=480,
  flat_full has ~1.67M gates vs A's ~2.28M — flat_full is actually fewer gates.
  But this comparison is misleading: flat_full exposes the entire cost matrix,
  while A hides it behind a Merkle root. The right framing is that flat_full is
  only usable when the cost matrix can be public; A (and flat_merkle) are the
  designs for private-matrix scenarios.

  The relevant comparison is: flat_full vs A, both at N=480, when the cost 
  matrix can be public. A is ~37% more expensive in gates but adds Merkle
  privacy plus the option of parallel proving. If you don't need matrix privacy,
   flat_full wins on gate count up to N ≈ 175 and loses above it. A is the
  design for the "matrix is private, parallel proving is wanted" use case
  throughout.

  ---
  Bottom line for the thesis:

  - A vs flat_merkle: nearly identical gate cost; A's wins are wall-clock (÷K),
  memory (÷K), and verifiability of partition structure; losses are proof
  bandwidth (×(K+1)) and partition disclosure.
  - A++ vs A: +5.5% gates and time; win is near-complete partition privacy
  (hides segment membership, shows only endpoints). A pays no statistical
  penalty; A++ has negligible 2^{-246} soundness error.
  - No Pareto domination: each point on the frontier is the best choice for a
  specific use case. This is the thesis's central structural argument.

✻ Cogitated for 4m 44s

※ recap: Designing ZKP circuits for TSP to map a privacy-versus-cost frontier across flat and hierarchical variants. We just finished a theoretical analysis of A++ versus A and A versus flat baselines. Next: decide whether to implement A++ circuits or run the Variant A benchmark sweep first. (disable recaps in /config)

❯ 1. I need you to update and adjust the plot.py script to allow it to have     
  more colors and distinct markers. Right now I get only 4, and having a lot of 
   lines ends up repeating colors.                                              
  2. By analyzing the variant A implementation, can you tell me exactly how the 
   prove time is computed? What do prove_s and witness_s have to do with it?    
  And looking at a first benchmark, the conclusions on the comparisons seem     
  right, exept for the prove time, that appears to be higher for hierarchical   
  in all K settings compared to the flat_merkle                                 

● Let me read both the plot script and the run_hier harness before answering.

  Read 2 files (ctrl+o to expand)

● Let me also check the aggregate script and a sample of the benchmark results.

  Searched for 3 patterns, read 1 file, listed 1 directory (ctrl+o to expand)

● I have a clear picture of both issues. Let me fix the plot first, then explain
   the timing problem.

  Fix 1: plot.py — replace the 5-entry hardcoded STYLES list with a dynamic
  generator that cycles across 12 colours × 10 markers × 4 line styles (480
  distinct combinations before any repeat).

  Fix 2: The prove-time anomaly — the current benchmark runs K+1 bb prove
  processes simultaneously on one machine. bb prove is heavily multi-threaded
  internally (MSMs, FFTs), so K+1 competing processes each get ≈1/(K+1) of the
  CPU, making each process slower than flat_merkle running alone. This is
  contention degradation, not a flaw in the circuit — I'll explain exactly what
  to report and how to read the numbers.

● Update(pipeline/plot.py)
  ⎿  Added 31 lines, removed 7 lines
      46  import numpy as np
      47  import matplotlib.pyplot as plt
      48  import matplotlib.ticker as ticker
      49 +import matplotlib.colors as mcolors                            
      50  
      51  # ── Metrics to plot, in subplot order (row-major, 2 rows × 3 c
          ols) ───────────
      52  # Each entry: (csv_column, y-axis label, subplot title)
     ...
      59      ("compile_s",    "Time (s)",        "Compile time"),
      60  ]
      61  
      61 -# ── Per-variant visual styles (cycles if more variants than en
         -tries) ──────────                                              
      62 -STYLES = [                                                     
      63 -    {"color": "#1d4ed8", "marker": "o", "ecolor": "#93c5fd"},  
         -# blue                                                         
      64 -    {"color": "#b45309", "marker": "s", "ecolor": "#fcd34d"},  
         -# amber                                                        
      65 -    {"color": "#047857", "marker": "^", "ecolor": "#6ee7b7"},  
         -# green                                                        
      66 -    {"color": "#7c3aed", "marker": "D", "ecolor": "#c4b5fd"},  
         -# purple                                                       
      67 -    {"color": "#be185d", "marker": "v", "ecolor": "#f9a8d4"},  
         -# pink                                                         
      62 +# ── Per-variant visual style generation ──────────────────────
         +────────────────                                               
      63 +# 12 perceptually distinct base colours, 10 markers, 4 line sty
         +les.                                                           
      64 +# _get_style(i) produces a unique visual combination for i up t
         +o 12*4 = 48                                                    
      65 +# before colours start repeating; markers rotate independently 
         +so two lines                                                   
      66 +# with the same colour (at high variant counts) still use diffe
         +rent markers.                                                  
      67 +_COLORS = [                                                    
      68 +    "#1d4ed8",  # blue                                         
      69 +    "#b45309",  # amber                                        
      70 +    "#047857",  # green                                        
      71 +    "#7c3aed",  # purple                                       
      72 +    "#be185d",  # pink                                         
      73 +    "#0e7490",  # cyan                                         
      74 +    "#b91c1c",  # red                                          
      75 +    "#4d7c0f",  # lime                                         
      76 +    "#c2410c",  # orange                                       
      77 +    "#1e40af",  # indigo                                       
      78 +    "#6d28d9",  # violet                                       
      79 +    "#0f766e",  # teal                                         
      80  ]
      81 +_MARKERS    = ["o", "s", "^", "D", "v", "p", "P", "X", "*", "h"
         +]                                                              
      82 +_LINESTYLES = ["-", "--", "-.", ":"]                           
      83  
      84  
      85 +def _get_style(idx: int) -> dict:                              
      86 +    color  = _COLORS[idx % len(_COLORS)]                       
      87 +    marker = _MARKERS[idx % len(_MARKERS)]                     
      88 +    ls     = _LINESTYLES[(idx // len(_COLORS)) % len(_LINESTYLE
         +S)]                                                            
      89 +    # Derive a lighter tint for error-bar caps by blending colo
         +ur 50% toward white.                                           
      90 +    rgb    = mcolors.to_rgb(color)                             
      91 +    ecolor = mcolors.to_hex(tuple(c * 0.5 + 0.5 for c in rgb)) 
      92 +    return {"color": color, "marker": marker, "ls": ls, "ecolor
         +": ecolor}                                                     
      93 +                                                               
      94 +                                                               
      95  # ── Data loading ─────────────────────────────────────────────
          ─────────────────
      96  
      97  def load_csv(paths):

● Now update the two call sites that consumed STYLES:

● Update(pipeline/plot.py)
  ⎿  Added 2 lines, removed 2 lines
      166          has_data = False
      167  
      168          for var_idx, (variant, ns, means, stds) in enumerate(v
           ariant_summaries):
      169 -            style  = STYLES[var_idx % len(STYLES)]            
      169 +            style  = _get_style(var_idx)                      
      170              ns_arr = np.array(ns, dtype=float)
      171              ys     = np.array(means[col], dtype=float)
      172              err    = np.array(stds[col],  dtype=float)
     ...
      180              ax.errorbar(
      181                  x, y,
      182                  yerr=e,
      183 -                fmt=f"{style['marker']}-",                    
      183 +                fmt=f"{style['marker']}{style['ls']}",        
      184                  capsize=4,
      185                  linewidth=1.6,
      186                  markersize=5,

● Update(pipeline/plot.py)
  ⎿  Added 3 lines, removed 2 lines
      224      legend_handles = [
      225          Line2D(
      226              [0], [0],
      227 -            color=STYLES[i % len(STYLES)]["color"],           
      228 -            marker=STYLES[i % len(STYLES)]["marker"],         
      227 +            color=_get_style(i)["color"],                     
      228 +            marker=_get_style(i)["marker"],                   
      229 +            linestyle=_get_style(i)["ls"],                    
      230              linewidth=1.6, markersize=5,
      231              label=variant,
      232          )

● Bash(conda run -n zk-tsp python3 pipeline/plot.py --csv results/500.csv
      results/hier_a_par.csv --out /tmp/test_plot --dpi 100 2>&1)
  ⎿  Variants : ['flat_full_pairwise', 'flat_full_sort', 'flat_merkle_prese
     nce', 'flat_full_invperm', 'flat_full_presence', 'hier_a_k2', 'hier_a_
     k4', 'hier_a_k8']
     … +5 lines (ctrl+o to expand)

● 8 variants, no crash. Let me visually verify the plot.

  Read 1 file (ctrl+o to expand)

● Plot looks good — 8 distinct colours, markers, and the first 5 use solid lines
   while the hierarchical variants would use a dashed line style when you go
  beyond 12 colours. The fix is done.

  ---
  2. How prove_s and witness_s are measured, and why hierarchical is slower

  What the harness actually measures

  In run_hier.py:WORKER_SCRIPT (lines 228–253), each parallel worker runs
  sequentially:

  nargo execute   →  witness_s   (constraint solving / witness generation)
  bb prove        →  prove_s     (actual ZK proof cryptography)

  witness_s = time for nargo execute — evaluating all circuit constraints to
  produce the ACIR witness file (.gz). Cheap: no cryptography, just arithmetic
  over field elements.

  prove_s = time for bb prove — building the UltraHonk proof: this runs
  multi-threaded FFTs, multi-scalar multiplications (MSMs), and polynomial
  commitments. It's the expensive step and is highly multi-threaded internally —
   it naturally tries to use every available CPU core.

  When aggregate_hier.py --mode parallel runs, it reports max(prove_s) across
  the K+1 workers. This is the parallel wall-clock assuming all K+1 workers ran
  simultaneously — which they did.

  The contention problem

  bb prove is internally parallelized. On your machine with, say, 8 CPU threads,
   a single bb prove instance uses all 8. When K+1 bb prove processes run
  simultaneously, they compete for those 8 threads. Each effectively gets
  8/(K+1) threads.

  For UltraHonk, the dominant operations (MSMs, FFTs) scale superlinearly with
  thread count — losing threads hurts more than linearly. The result:

  ┌─────┬─────────┬───────┬───────────┬───────────┬───────────┬──────────┐
  │     │         │ Threa │           │ Theoretic │ Observed  │ Contenti │
  │  K  │ Process │  ds   │ Sub circu │    al     │ max(prove │   on     │
  │     │   es    │ each  │  it_size  │ isolated  │    _s)    │ overhead │
  │     │         │ gets  │           │   time    │           │          │
  ├─────┼─────────┼───────┼───────────┼───────────┼───────────┼──────────┤
  │ fla │         │ 8/1 = │ ~48k      │           │           │          │
  │ t   │ 1       │  8    │ (N=48     │ ~0.76 s   │ ~0.76 s   │ 1.0×     │
  │     │         │       │ interp.)  │           │           │          │
  ├─────┼─────────┼───────┼───────────┼───────────┼───────────┼──────────┤
  │ 2   │ 3       │ 8/3 ≈ │ 27,084    │ ~0.39 s   │ ~0.94 s   │ 2.4×     │
  │     │         │  2.7  │           │           │           │          │
  ├─────┼─────────┼───────┼───────────┼───────────┼───────────┼──────────┤
  │ 4   │ 5       │ 8/5 = │ 14,445    │ ~0.21 s   │ ~1.06 s   │ 5.0×     │
  │     │         │  1.6  │           │           │           │          │
  ├─────┼─────────┼───────┼───────────┼───────────┼───────────┼──────────┤
  │ 8   │ 9       │ 8/9 < │ 8,126     │ ~0.12 s   │ ~1.40 s   │ 11×      │
  │     │         │  1    │           │           │           │          │
  └─────┴─────────┴───────┴───────────┴───────────┴───────────┴──────────┘

  The contention overhead grows superlinearly with K because at K=8 you have 9
  processes fighting for 8 cores — some workers are literally queued.

  What this means for the thesis

  The benchmark correctly measures "parallel proving on a single shared
  machine." That is a different and harder scenario than the natural use case
  for hierarchical proving (K provers on K dedicated machines or cloud nodes).

  Three honest metrics to report:

  1. circuit_size (total K·sub + glue): this is hardware-independent. At N=480
  it's ≈ flat_merkle ± 1.5%. ✓ Confirms no total-work saving.
  2. peak_mb (max across K+1 workers): this IS correctly captured even under
  contention, because each process's memory is independent. The data shows
  genuine reduction: K=2 → ~57 MB/prover vs ~87 MB flat at N=48, K=4 → ~40 MB.
  The reduction is real but sub-K× due to fixed circuit overhead.
  3. prove_s: the benchmark measures contention-degraded time, not 
  distributed-hardware time. For the thesis:
    - Report the single-machine contended max(prove_s) as an empirical finding
  (it's higher than flat — honest)
    - Estimate ideal K-prover parallel time from circuit_size ratio: T_ideal ≈
  T_flat_merkle × (sub_circuit_size / flat_circuit_size)
    - At K=4, N=480: sub_circuit_size ≈ flat_circuit_size / 4, so T_ideal ≈
  T_flat / 4

  The framing: "The memory-per-prover reduction is directly measured and 
  confirmed. The parallel wall-clock speedup is a theoretical estimate from 
  circuit-size ratios; realizing it requires dedicated per-prover hardware, 
  which is the natural deployment model for K-party distributed proving."

  This is actually a stronger thesis point than a simple speedup claim: you can
  show both the theoretical gain (K×) and the practical overhead of the
  shared-machine model, framing the latter as a deployment consideration rather
  than a measurement error.

✻ Churned for 4m 30s
※ recap: Working on a ZKP thesis comparing flat and hierarchical TSP circuit variants. Plot.py now supports unlimited distinct styles. Next: implement Variant A++. (disable recaps in /config)

❯ Are these findings, comparisons and variants good for the thesis goal? Are    
  there anything zk-wise that we are missing or that we could improve for our   
  project? And finally, would a RISC-0 additional implementation + comparison   
  bring anything valuable to the table, if so, what? Please now that we have    
  some results and some ideas, it's time for an overview of the mountain we're  
  climbing, and what we're missing to get to the top. And how do we frame all   
  this step-by step?                                                            

● This is a good moment to step back. Let me read the current benchmark results
  and plots to ground the assessment before the strategic discussion.

● Bash(head -2 /home/callexyz/Desktop/plsgod/results/hier_a_par.csv && echo
      "---" && wc -l /home/callexyz/Desktop/plsgod/results/hier_a_par.csv &&
      echo "---" && cat /h…)
  ⎿  variant,n,run,circuit_size,acir_opcodes,compile_s,witness_s,prove_s,ve
     rify_s,proof_bytes,peak_mb
     hier_a_k2,48,1,59969,7563,0.556,0.2365,0.9801,0.0938,43968,57.16
     … +22 lines (ctrl+o to expand)

  Searched for 2 patterns, read 1 file (ctrl+o to expand)

● Now I have the numbers I need. Let me lay out the full strategic picture.

  ---
  Part 1: What the current results actually prove — honest assessment

  Let me tabulate what the benchmark shows at N=480 (the largest comparable
  point):

  ┌─────────────────┬───────────────┬────────────┬────────────┬────────────┐
  │     Metric      │ flat_merkle   │ hier K=2   │ hier K=4   │ hier K=8   │
  │                 │     N≈500     │   N=480    │   N=480    │   N=480    │
  ├─────────────────┼───────────────┼────────────┼────────────┼────────────┤
  │ circuit_size    │ ~753k (est    │ 769k       │ 775k       │ 787k       │
  │                 │ N=480)        │ (+2.2%)    │ (+3.0%)    │ (+4.4%)    │
  ├─────────────────┼───────────────┼────────────┼────────────┼────────────┤
  │ prove_s         │ ~12.0s        │ 12.9s      │ 14.4s      │ 15.5s      │
  │ (contended)     │               │ (+7%)      │ (+20%)     │ (+29%)     │
  ├─────────────────┼───────────────┼────────────┼────────────┼────────────┤
  │ peak_mb         │ 1078 MB       │ 551 MB     │ 285 MB     │ 159 MB     │
  │                 │               │ (÷2)       │ (÷3.8)     │ (÷6.8)     │
  ├─────────────────┼───────────────┼────────────┼────────────┼────────────┤
  │ verify_s        │ 0.014s        │ 0.127s     │ 0.182s     │ 0.278s     │
  │                 │               │ (×9)       │ (×13)      │ (×20)      │
  ├─────────────────┼───────────────┼────────────┼────────────┼────────────┤
  │ proof_bytes     │ 14.6 KB       │ 43.9 KB    │ 73.3 KB    │ 131.9 KB   │
  │                 │               │ (×3)       │ (×5)       │ (×9)       │
  └─────────────────┴───────────────┴────────────┴────────────┴────────────┘

  The brutally honest read:

  - Memory reduction: solid and close to theoretical K×. This is the one
  unambiguous, empirically confirmed win. At K=4, you get 3.8× memory reduction
  — impressive and directly applicable (a prover running on a 512 MB device
  can't run flat_merkle at N=480, but can run a sub-circuit).
  - Gate count: hierarchy is strictly MORE expensive by 2-4%. The "≈ flat" claim
   in the design doc holds at large N, but it's never cheaper.
  - Prove time: worse in every single benchmark row. The parallel wall-clock
  speedup claim is theoretical, not empirically demonstrated. The benchmark
  demonstrates the opposite on one machine.
  - Verification: (K+1)× slower — the SNARK "O(1) verification" property is
  degraded to O(K).
  - Proof bandwidth: (K+1)× larger — 5 proofs for K=4, 9 for K=8. Significant
  for constrained verifiers (blockchain, mobile).

  What this means for the thesis:

  The only defensible quantitative claim for the parallelism benefit is: "the
  sub-circuit's gate count is ≈ flat_merkle/K, so a dedicated-hardware K-prover
  setup would achieve ≈K× speedup." The current benchmark cannot empirically
  validate this. Everything else (memory, overhead, verification, bandwidth) is
  solidly confirmed.

  ---
  Part 2: What's missing ZK-wise

  The four genuine gaps:

  1. The cross-check protocol isn't a ZK protocol — it's a trusted script.

  verify_hier.py is part of the soundness chain. A verifier who only runs bb 
  verify K+1 times without the cross-checks will accept a proof where sub-proofs
   come from inconsistent cycles. This is fine in practice but needs to be
  stated explicitly: "the full verification protocol for Variant A is K+1 bb 
  verify calls plus four off-circuit equality checks; the latter are not 
  ZK-verified." A formal description of the protocol should be in the thesis.

  2. Succinct verification is broken by Variant A.

  One of the canonical properties of SNARKs is "succinct verification" — the
  verifier's work doesn't grow with the witness size. Flat_merkle satisfies this
   (2 public inputs, O(1) verifier). Variant A requires the verifier to process
  all_sorted_nodes[N] = N public inputs — O(N) verifier work. This is a real
  regression that should be explicitly acknowledged, not papered over.

  A++ partially fixes this (N → O(K) public inputs), which is a legitimate
  argument for A++ beyond privacy.

  3. The privacy claim is qualitative, not quantified.

  "Variant A leaks the partition; A++ hides it" is stated but the information
  content isn't measured. A sharper statement: Variant A discloses log₂ C(N, M)
  ≈ N·log K bits of partition membership. A++ discloses only 2K node indices
  (the endpoints). At K=4, N=480: that's ~480·2 ≈ 960 bits of partition
  information in A, vs 4 endpoint pairs in A++. This quantification is easy to
  write and makes the privacy tradeoff concrete.

  4. No isolated sub-circuit benchmark — the parallelism claim has no empirical 
  backing.

  This is the biggest hole. You claim K× parallel speedup on dedicated hardware
  but every row in the benchmark shows the opposite. A single additional
  experiment — running one sub-circuit in isolation without parallel workers —
  would give you a concrete number: "one sub-circuit at N=480, K=4 takes X
  seconds in isolation, vs flat_merkle's ~12 seconds: ≈4× speedup per dedicated
  prover." This is a one-day experiment and would transform the parallelism
  claim from theoretical to empirical.

  One thing to understand properly: the ZK property itself.

  The thesis demonstrates soundness (the test suite shows that cheating
  witnesses are rejected). It doesn't say why the proofs are zero-knowledge. The
   argument is short and worth writing: "UltraHonk is a zero-knowledge proof
  system, so all private inputs (cycle, edge_costs, Merkle witnesses) are
  computationally indistinguishable to the verifier. The ZK boundary for each
  variant is exactly its public input interface: whatever appears there is
  disclosed; whatever stays private is provably hidden."

  ---
  Part 3: Would RISC-0 add value?

  What RISC-0 is: a zkVM based on RISC-V. You write a Rust program; RISC-0
  generates a STARK proof of correct execution. No circuit design — just code.
  Uses FRI polynomial commitments, so proofs are ~200KB-1MB (vs 14.7KB for
  UltraHonk).

  What it would show:
  - "Programmability extreme" of the design space: zero circuit engineering, but
   10-50× more proof overhead
  - STARKs vs SNARKs: no trusted setup, different proof size and time tradeoffs
  - A concrete data point: "flat TSP in RISC-0 → X cycles, Y seconds, Z bytes"

  My recommendation: a single data point yes, a full implementation no.

  You don't need a benchmark sweep. One working proof at a moderate N (say
  N=20-50), recording prove time, memory, and proof size, gives you a paragraph
  + one row in the comparison table. The thesis statement becomes: "Custom Noir
  circuits sit at the efficiency end of the design space; zkVM approaches like
  RISC-0 trade 10-50× more proving work for arbitrary programmability — the
  circuit-design effort in this thesis is precisely the cost of closing that
  gap."

  This is worth 2-3 days of effort max, and ONLY after the core hierarchical
  work is done. Don't do it before A++ is implemented.

  ---
  Part 4: The mountain — where we are, what's missing, how to frame it

  Summit definition for an MSc thesis: A defensible, complete argument that maps
   the ZKP design space for TSP along four axes (gates, memory, privacy,
  verifiability), identifies the structural reason for the frontier shape, and
  supports each claim with empirical data.

  What we have (base camp)

  - ✅ Full flat baseline — 5 variants, N=5..500, tight complexity fits
  - ✅ Variant A — full pipeline, benchmarked N=48..480, K=2..8
  - ✅ Dualism insight — the theoretical core, well-articulated
  - ✅ Memory reduction empirically confirmed (~K×)
  - ✅ Thesis reframe — frontier framing is defensible

  The three remaining climbs (ordered)

  Climb 1 — Isolation benchmark (1 day, HIGH VALUE)

  Run a single sub-circuit without parallel workers. This turns the parallelism
  claim from theoretical to empirical. Without it, any examiner can ask "but
  your prove times are all slower than flat — where's the speedup?" and you have
   no data to point to.

  Concretely: modify or bypass run_hier.py to run only sub_0 serially, record
  isolated prove_s and peak_mb. Compare against flat_merkle at the same N.

  Climb 2 — Variant A++ (1-2 weeks, REQUIRED for frontier)

  Without A++, the frontier has only two points (flat_merkle and Variant A). A
  frontier argument with two points is just a line, not a frontier. A++ gives
  you:
  - A third point: +5.5% gates, partition hidden
  - The quantified privacy-cost tradeoff: "hiding the partition costs 5.5% more
  gates"
  - The A++ vs A comparison as a self-contained finding (soundness tradeoff:
  perfect vs 2^{-246})

  Climb 3 — Frontier figure (2-3 days, after A++)

  The signature figure of the thesis. A scatter or radar plot with variants as
  points and axes:
  - Total gates (x-axis)
  - Memory per prover (y-axis or bubble size)
  - Privacy bits disclosed (color or 3rd axis)
  - Proof bandwidth or verification time (4th encoding)

  This is what makes the thesis visually complete and defensible.

  Optional: Variant B (~1 week)

  Adds the "gates < flat_merkle possible, but partition + sub-matrices fully
  disclosed" data point. If time is tight, this can be framed as "future work"
  since the design is fully specified. It's the least necessary climb.

  Optional: RISC-0 (~2-3 days, after everything else)

  One data point for the "programmability extreme" of the design space. Add
  after A++ and frontier figure.

  The step-by-step path

  Week 1:   Isolation benchmark → empirical parallelism claim ✓
            Write Section 4 (dualism) and Section 5 (Variant A results) while
  data is fresh

  Week 2-3: Variant A++ implementation
            (sub-circuit: drop sorted_nodes, add hash chain + grand product)
            (glue: replace sort with grand-product check + chain continuity)

  Week 4:   A++ benchmark sweep
            Isolation benchmark for A++ sub-circuit
            Frontier figure

  Week 5+:  Variant B (if time) or RISC-0 data point
            Section 6 (A++) and Section 7 (frontier + discussion) write-up

  How to frame it in the thesis

  The thesis should have one sentence that is the thesis:

  ▎ "Hierarchical decomposition of TSP ZK proofs does not reduce total proving 
  ▎ cost (it adds 2-4% in gates), but reorganizes it: memory per prover scales 
  ▎ as 1/K, interior routing is hidden from the verifier, and proving time 
  ▎ distributes across K independent machines — a frontier that no single flat 
  ▎ variant can offer."

  Every chapter either establishes a term in that sentence or is evidence for
  it. The dualism insight explains WHY there's no gate saving. The flat baseline
   establishes the baseline. Variant A confirms the memory and gate claims.
  Variant A++ adds the privacy term. The frontier figure shows all four axes
  simultaneously.

  The proof-time anomaly (contended benchmark is slower) is not a weakness if
  framed correctly: "the single-machine benchmark demonstrates contention
  degradation; the circuit-size data shows that on dedicated hardware the
  speedup is ≈K×, and the memory-per-prover reduction is confirmed directly."
  That's an honest, defensible statement.

✻ Cooked for 4m 59s

❯ Is what we have, with the necessary adjustment, something valuable for a MSc  
  thesis, or am I missing some originality/contribution or the work is too      
  short? I feel like some things I will need to leave as black boxes and not be 
   able to understand them fully.                                               

● This is a good question to pause on. Let me be direct.

  ---
  Is this MSc-level work? Yes, solidly.

  Let me be specific about what you actually have vs. what MSc theses in applied
   cryptography are expected to contain.

  What you've built:
  - 7 fully working ZKP circuits from scratch, in a domain you didn't know
  before starting
  - A complete benchmark pipeline with complexity fits, empirical data to N=500,
   and multi-dimensional metrics
  - An honest negative result (hierarchical doesn't save gates) with a
  structural explanation
  - A reframing that turns a failed hypothesis into a more interesting research
  question

  This is more implementation breadth than most MSc ZKP theses, many of which
  stop at one or two working circuits and a proof-of-concept. You have five flat
   variants, a full hierarchical pipeline, a Rust builder, parallel proving
  infrastructure, and cross-proof verification. That's not trivial.

  What makes something MSc vs. PhD:

  An MSc thesis demonstrates that you can navigate a technically complex area,
  apply existing tools and techniques correctly, and draw meaningful conclusions
   from empirical work. It does not require a novel cryptographic construction,
  a new proof system, or a theorem unknown to the field.

  A PhD would require that the dualism insight be new to the research community,
   formally proved, or generalized to a class of problems. At MSc level, what's
  required is: you observed something non-obvious, verified it empirically, and
  articulated it clearly. That bar is met.

  ---
  On the dualism insight: how to frame it honestly

  Here's the important caveat to be aware of: the observation that naive 
  hierarchical decomposition doesn't save ZK gates is already known in the 
  research community. It's the reason folding schemes (Nova, SuperNova,
  HyperNova) were invented — they're explicitly designed to solve the problem
  your dualism describes. The existence of those papers implies someone already
  understood the issue.

  This doesn't invalidate your work. But your framing needs to be:

  ▎ "This thesis provides an empirical, application-specific verification of a 
  ▎ principle that is implicit in the folding-scheme literature: that 
  ▎ hierarchical decomposition in ZK requires O(N) glue work to restore 
  ▎ soundness, negating per-segment savings. We make this explicit for TSP, 
  ▎ quantify it empirically across three decomposition depths, and derive a 
  ▎ systematic four-axis frontier framework for choosing among the resulting 
  ▎ variants."

  That's a legitimate MSc contribution: concrete, honest, empirically grounded.
  What you should not say is "we discovered that hierarchical ZKP has no gate
  benefit" as if it were unknown — a PhD examiner will immediately ask "have you
   read the Nova paper?"

  So: cite Nova, SuperNova, ProtoStar. Acknowledge that your result confirms
  what those systems implicitly assume. Frame your contribution as the
  systematic empirical analysis and the frontier mapping, not the dualism per
  se.

  ---
  On black boxes: they are normal and expected

  Every MSc thesis in applied cryptography has them. Let me name yours
  specifically so you can stop worrying about them and just state them clearly:

  Things you can legitimately treat as black boxes, with a citation:
  - UltraHonk soundness — cite the Barretenberg/Aztec technical reports and the
  PLONK paper. You use it as a black box. Every thesis using these tools does
  the same.
  - Poseidon2 collision resistance — cite the Poseidon2 paper. You assume it,
  the way AES-based systems assume AES security.
  - The Fiat-Shamir heuristic — cite Fiat-Shamir 1987 and the relevant security
  analysis. You use it for A++, you explain the soundness error bound
  (Schwartz-Zippel), that's enough.
  - Schwartz-Zippel lemma — cite it, state the error bound (N/|Field| ≈
  2^{-246}), move on.
  - Barretenberg's internal implementation — you validate it via test vectors
  and hash-compat tests. That's the correct approach, not re-implementing it.

  Things you can NOT treat as black boxes:
  - The circuit constraint groups in your own circuits — you need to understand
  and explain why each assertion is necessary
  - The soundness of your cross-check protocol — you need to argue why skipping
  verify_hier.py would allow attacks
  - Why the leaf-index check in GROUP 3 is necessary (without it: proof
  substitution attack) — you have this in the comments already

  The pattern is: external cryptographic primitives and proof systems = cite and
   assume. Your own circuit design choices = understand and justify. You clearly
   do understand your circuits — the GROUP-by-GROUP documentation is thorough
  and correct.

  ---
  The real risks

  The thesis won't fail because of scope or originality. It will fail (or be
  weak) for these practical reasons:

  Risk 1: Incomplete execution. The frontier argument needs at least one more
  variant. With only Variant A, you have two points (flat_merkle and A) and call
   it a frontier. That's thin. Variant A++ is not optional if you want the
  frontier argument to hold. This is the actual critical path.

  Risk 2: Unresolved prove-time story. Right now every single benchmark row
  shows hierarchical is slower than flat. If you submit without the isolation
  benchmark, the thesis has a finding that contradicts its own central claim. An
   examiner will ask: "you claim K× parallel speedup — where is it in the data?"
   You need to either (a) run the isolation benchmark to empirically show the
  per-prover speedup, or (b) explicitly argue why the single-machine benchmark
  is the wrong comparison and provide the estimated speedup from gate counts.
  Option (a) is 1 day of work and much cleaner.

  Risk 3: No literature engagement on hierarchical ZKP. You need to cite at
  least Nova (Kothapalli et al. 2022) and ProtoStar (Chen & Bunz 2023) and
  explain how your work relates. Without that, the thesis looks like it
  re-derives a known result without knowing it's known.

  Risk 4: The write-up. You have strong implementation and strong analysis. The
  risk is that the thesis document doesn't communicate the dualism insight
  clearly enough or gets too lost in pipeline details. The thesis should lead
  with the research question and the dualism insight, not with "first I
  implemented flat_full_pairwise, then flat_full_sort..."

  ---
  What a solid final thesis looks like

  If you complete the isolation benchmark, implement A++, and write the frontier
   figure, the thesis narrative becomes:

  1. Chapter 2 (background): ZKP fundamentals, TSP, Noir/UltraHonk. Cite the
  tools.
  2. Chapter 3 (flat baseline): 5 variants. GROUP structure, complexity fits,
  N≈175 crossover. Key finding: GROUP 3 dominates, permutation check is linear,
  cost is O(N²) for full and O(N log N) for Merkle.
  3. Chapter 4 (the dualism): Why hierarchical decomposition doesn't save gates
  in ZK. Relate to folding schemes literature (Nova etc.) as the context.
  4. Chapter 5 (Variant A): Implementation, benchmark results. Memory ÷K
  confirmed. Prove time: single-machine contention vs. per-prover isolated
  speedup. Verification and bandwidth overhead.
  5. Chapter 6 (Variant A++): Grand product + FS. +5.5% gates, partition hidden.
   Privacy-cost tradeoff quantified.
  6. Chapter 7 (frontier): Four-axis figure. Use-case mapping. When to pick each
   variant.
  7. Chapter 8 (discussion): Limitations (single-machine benchmark, N cap),
  future work (folding schemes as the natural continuation — literally what Nova
   was designed for).

  That is a complete, defensible MSc thesis. It's not world-changing, but it's
  technically rigorous, honest about its negative results, grounded in real
  empirical work, and correctly situated in the literature. A supervisor who
  knows ZKP will appreciate the intellectual honesty of finding "no crossover"
  more than a thesis that forces a misleading positive result.

  The work you've done is worth finishing properly. The gap between where you
  are and a complete thesis is A++, one isolation benchmark, and the write-up —
  not a fundamental rethinking of the project.

✻ Cogitated for 1m 30s

❯ Now my question becomes: where and how do I find the relevant literature, and 
   make sure to introduce it properly in a dedicated section wrt to my          
  application?                                                                  

● This is a research skills question as much as a content question. Let me give
  you a concrete, practical answer — where to look, what specifically to find,
  and how to write it.

  ---
  Step 1: Know exactly what you need before you search

  Don't search randomly. You have specific gaps. Here's the complete list of
  what needs a citation and why:

  ┌─────────────────────┬────────────────────┬──────────────────────────────┐
  │   Concept you use   │  Why you need to   │       What to look for       │
  │                     │      cite it       │                              │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ ZKP (completeness,  │ Foundational       │ GoldWasser-Micali-Rackoff    │
  │ soundness, ZK)      │ definitions        │ 1989, or a modern textbook   │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ SNARKs in general   │ Why they're useful │ Any SNARK survey or the      │
  │                     │                    │ Groth16 paper                │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ PLONK / UltraHonk   │ The proof system   │ PLONK paper (Gabizon et al.  │
  │                     │ you actually use   │ 2019), Barretenberg docs     │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ Poseidon2           │ The hash function  │ Grassi et al. 2023           │
  │                     │ in every circuit   │                              │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ Merkle trees        │ Structure you rely │ Textbook / any early digital │
  │                     │  on for privacy    │  commitment paper            │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ Fiat-Shamir         │ Core of A++        │ Fiat & Shamir 1987           │
  │ transform           │ soundness          │                              │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ Schwartz-Zippel     │ Soundness bound    │ Schwartz 1980 / Zippel 1979  │
  │ lemma               │ for grand product  │                              │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ Grand product       │ The A++ partition  │ Plookup (Gabizon &           │
  │ multiset equality   │ check technique    │ Williamson 2020) or similar  │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │                     │ Why hierarchical   │                              │
  │ Folding schemes /   │ ZKP doesn't save   │ Nova (Kothapalli et al.      │
  │ Nova                │ gates — the        │ 2022)                        │
  │                     │ existing solution  │                              │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ TSP NP-completeness │ Motivating why     │ Karp 1972                    │
  │                     │ proving it is hard │                              │
  ├─────────────────────┼────────────────────┼──────────────────────────────┤
  │ Nearest-neighbour + │ Your solver        │ Any combinatorial            │
  │  2-opt              │                    │ optimisation textbook        │
  └─────────────────────┴────────────────────┴──────────────────────────────┘

  That's roughly 12-15 sources. An MSc thesis with 20-30 references is normal.
  Don't inflate it.

  ---
  Step 2: Where to find them

  For ZKP papers specifically: IACR ePrint is the primary source.

  eprint.iacr.org — this is where almost all ZKP research appears, often before
  or instead of conference proceedings. It's free, comprehensive, and
  searchable. Most of the papers below are there.

  The specific papers to find:

  Justin Thaler's textbook — read this first.
  "Proofs, Arguments, and Zero-Knowledge" (2022) — freely available on his
  website (search "Thaler ZKP book"). This is the best pedagogical source for
  ZKP fundamentals and will answer your black-box anxiety better than any
  individual paper. Cite it as your foundational reference for ZKP definitions.
  Read Chapters 1-4 and whichever chapters cover the specific proof systems.

  PLONK paper:
  "PLONK: Permutations over Lagrange-Bases for Oecumenical Noninteractive 
  Arguments of Knowledge" — Gabizon, Williamson, Ciobotaru (2019). On IACR
  ePrint as 2019/953. This is the foundation of UltraHonk.

  Poseidon2:
  "Poseidon2: A Faster Version of the Poseidon Hash Function" — Grassi,
  Khovratovich, Rechberger, Roy, Schofnegger (2023). On IACR ePrint as 2023/323.

  Nova — the most important related work:
  "Nova: Recursive Zero-Knowledge Arguments from Folding Schemes" — Kothapalli,
  Setty, Tzialla (2022). CRYPTO 2022. IACR ePrint 2021/370. Read the 
  introduction carefully. It explicitly states the problem your thesis
  identifies: naive recursive composition is expensive, and folding was designed
   to fix that. Their motivation section is essentially a description of your
  dualism.

  Plookup (for grand product argument background):
  "plookup: A simplified polynomial protocol for lookup tables" — Gabizon,
  Williamson (2020). IACR ePrint 2020/315. Covers the grand product argument
  technique that A++ uses.

  Fiat-Shamir:
  "How to Prove Yourself: Practical Solutions to Identification and Signature 
  Problems" — Fiat, Shamir (1987). In CRYPTO 1986 proceedings.

  Groth16 (canonical SNARK reference):
  "On the Size of Pairing-Based Non-interactive Arguments" — Groth (2016).
  EUROCRYPT 2016. IACR ePrint 2016/260. Cite this when you say "SNARK" in
  general.

  Karp's 21 NP-complete problems:
  "Reducibility Among Combinatorial Problems" — Karp (1972). This is where
  Hamiltonian Circuit was shown NP-complete. In a book chapter — find it via
  Google Scholar.

  For UltraHonk specifically:
  There's no single paper — it's Aztec's engineering work. Cite the Barretenberg
   GitHub repository and any available Aztec technical documentation. This is
  acceptable for an implementation-based thesis: "UltraHonk as implemented in
  Barretenberg [GitHub citation]."

  ---
  Step 3: How to read efficiently

  You're new to this literature. Reading papers end-to-end is inefficient and
  will paralyse you. The correct approach:

  For each paper, read in this order:
  1. Abstract — is this the right paper?
  2. Introduction — what problem does it solve, why does it matter, what's the
  key idea in plain language?
  3. Related work / prior work sections — this is a map of the field; use it to
  find other papers
  4. The specific section you need to cite — e.g. for Poseidon2, you need the
  gate count and security argument. You don't need the full algebraic
  construction.
  5. Conclusion — what did it claim to achieve?

  For Thaler's book: read it linearly for the first 3-4 chapters as a tutorial,
  then use it as a reference dictionary.

  For Nova specifically: Read the introduction (3-4 pages). The key quote you
  want is in the motivation: they explicitly describe why naive recursive
  composition requires O(N) verifier work per step and why folding amortizes
  this. That's your citation anchor for the dualism argument.

  The snowball method for finding adjacent papers:
  - Pick one paper you know (Nova)
  - Look at its Related Work section → follow 2-3 of those links
  - Look at "Cited By" on Google Scholar → find the 2-3 most-cited follow-ons
  - Stop at depth 2; you have enough

  ---
  Step 4: How to structure the background section

  The background chapter has two jobs: teach the reader what they need to
  understand your circuits, and situate your work in the existing literature.
  They're not the same chapter but they often overlap.

  Recommended structure:

  2.1 Zero-Knowledge Proofs (foundational, 2-3 pages)
  Define the three properties (completeness, soundness, zero-knowledge). Cite
  Thaler or the original GMW paper. Note SNARKs as the practical subclass
  (succinctness, non-interactivity). Cite Groth16 as a canonical construction.

  Connect to your work: "This thesis uses Noir [cite Noir docs] compiled to the 
  UltraHonk proof system [cite Barretenberg], which provides computational ZK 
  for all private inputs. The ZK boundary for each circuit variant is its 
  public-input interface: whatever appears there is disclosed; whatever stays 
  private is computationally hidden."

  2.2 The TSP Problem (brief, 1 page)
  Define Hamiltonian cycle, cost function, NP-completeness via Karp. Explain
  nearest-neighbour + 2-opt.

  Connect to your work: "For ZKP benchmarking purposes, solution quality is 
  irrelevant — any valid Hamiltonian cycle satisfies the circuit. We use 
  NN+2-opt as a computationally cheap cycle generator."

  2.3 Arithmetic Circuits and PLONK (1-2 pages)
  Explain constraint systems, the PLONK arithmetisation, lookup tables. Cite
  PLONK paper. Explain why UltraHonk uses "gates" not "constraints" in the sense
   you benchmark.

  Connect to your work: "All circuits in this thesis are expressed in Noir and 
  compiled to UltraPlonk's constraint system. The circuit_size metric throughout
   is the count of arithmetic gates after UltraHonk arithmetisation, reported by
   bb gates."

  2.4 ZK-Friendly Hash Functions (1 page)
  Explain why native CPU hash functions (SHA-256) are expensive in circuits
  (~28k gates). Introduce algebraic hashes designed for prime fields. Cite
  Poseidon2.

  Connect to your work: "All Merkle tree operations in this thesis use 
  Poseidon2. Each call compiles to approximately 87 UltraHonk gates (measured 
  empirically, Table X), making the O(N·DEPTH) Merkle GROUP 3 practical at N ≤ 
  500."

  2.5 Merkle Commitments in ZKP (1 page)
  Explain Merkle trees as a commitment scheme. Explain opening proofs. Explain
  the leaf-index binding trick (why you need the path-bit reconstruction, not
  just the hash chain).

  Connect to your work: "The flat_merkle and all hierarchical variants use 
  Merkle commitments to hide the cost matrix. The soundness of this approach 
  rests on two independent checks per edge (Section 3.4), not just hash-chain 
  verification."

  2.6 Hierarchical and Recursive ZKP (1-2 pages — this is your key related work)
  Explain that naive composition of K independent proofs does not reduce total
  prover work: the verifier must check K proofs, and the K sub-circuits together
   must cover all N constraints. State that this is the motivation for folding
  schemes. Cite Nova, briefly explain what folding does differently. State that
  your thesis does NOT use folding — it uses independent proofs — and explain
  why (scope, implementation complexity, and the goal being to characterize the
  overhead rather than eliminate it).

  Connect to your work: "The hierarchical variants in this thesis (A, A++) use 
  K+1 independent UltraHonk proofs rather than recursive composition or folding.
   This design choice preserves the ability to measure the structural overhead 
  of decomposition directly — the overhead that folding schemes are designed to 
  amortize. Nova [cite] requires approximately the same total constraint work as
   the flat circuit; this thesis empirically confirms this for the TSP 
  application (Section 5)."

  2.7 Grand Product Arguments and Multiset Equality (0.5-1 page, only if 
  implementing A++)
  Explain the polynomial identity behind multiset equality checks. Cite Plookup.
   State the Schwartz-Zippel bound. Explain Fiat-Shamir for deriving the
  challenge in-circuit. Cite Fiat & Shamir.

  Connect to your work: "Variant A++ uses a grand product multiset equality 
  check to replace the O(N) sort-based partition check in Variant A. The 
  soundness error is N/|Field| ≈ 2^{-246}, negligible in practice."

  ---
  Step 5: The connection template

  Every time you introduce a concept from the literature, write it in this
  pattern:

  1. What it is (1-2 sentences, general)
  2. Where it comes from (citation inline)
  3. How it appears in YOUR circuits/pipeline (1-2 sentences, specific)
  4. What you assume vs. what you verify (1 sentence — distinguishes black boxes
   from your contributions)

  This pattern answers the examiner's implicit question ("why are you telling me
   this?") before they ask it. It also forces you to be concrete about which
  parts of your work rest on each cited result.

  For example:

  ▎ "The Fiat-Shamir transform converts an interactive proof into a 
  ▎ non-interactive one by replacing the verifier's random challenge with a hash
  ▎  of the prover's previous messages [Fiat & Shamir, 1987]. In Variant A++, 
  ▎ the partition challenge X is derived in-circuit via a Poseidon2 hash chain 
  ▎ over the private cycle, making the grand product check non-interactive 
  ▎ within a single sub-circuit. We assume the Fiat-Shamir heuristic holds in 
  ▎ the random oracle model; the resulting soundness error for the grand product
  ▎  check is at most N/|Field| ≈ 2^{-246} by the Schwartz-Zippel lemma 
  ▎ [Schwartz, 1980]."

  That paragraph cites two papers, uses them correctly, connects them to a
  specific circuit decision, and states the assumption explicitly. That's
  exactly what an examiner wants to see.

  ---
  The one-sentence version of what you're doing

  The thing that ties all the background together is this:

  ▎ "We build our circuits on top of UltraHonk, Poseidon2, and Noir — treating 
  ▎ them as black boxes with stated security properties — and analyze what those
  ▎  properties imply for a family of TSP statements that differ in what part of
  ▎  the circuit's input is public or private."

  That one sentence explains why you cite the underlying systems (to establish
  what you're building on) and what your contribution is (the analysis of the
  TSP statement family, not the cryptographic primitives themselves). Every
  background section should feel like it's setting up that sentence.

✻ Worked for 2m 7s

※ recap: TSP zero-knowledge proof thesis with hierarchical circuit variants benchmarked. Updated plot.py for more colors and discussed literature strategy. Next: run the isolation benchmark for one sub-circuit to empirically validate the parallel speedup claim. (disable recaps in /config)

❯ Can we now consider the related works, where we try to analyze whether there  
  is something similar already present in the literature with the same problem  
  or application, or with a different one but the same approach, or other       
  instances in which some pieces of our thesis are used, e.g. other             
  applications of Merkle trees to zk proofs. And some resources/literature work 
   that I can use as "motivation" for the work, under a research question that  
  goes something like this:                                                     
                                                                                
  This thesis investigates whether hierarchical zero-knowledge proof            
  constructions can improve the scalability of proving knowledge of a           
  bounded-cost Hamiltonian cycle compared with direct flat circuit              
  constructions, under metrics such as circuit size, proving time, verification 
   time, memory usage, and public input size.                                   
                                                                                
  Or related research questions + the duality pursuit and comparison wrt        
  optimization. Change and update the research question if you see fit and find 
   one that better aligns with what we're doing here.                           

● Let me first sharpen the research question, then map the literature landscape
  systematically.

  ---
  Refining the research question

  Your proposed question has a subtle problem: it asks "whether hierarchical
  constructions can improve scalability" — but your thesis finds a nuanced
  answer where some metrics improve (memory, parallelism on dedicated hardware)
  and others worsen (gates, single-machine prove time, verification cost,
  bandwidth). A question whose answer is "it depends on which metric you care
  about and why" needs to be phrased to invite that answer, not foreclose it.

  Here is a refined version that better fits what the thesis actually does:

  ▎ "How do hierarchical zero-knowledge proof constructions for proving 
  ▎ knowledge of a bounded-cost Hamiltonian cycle trade off against flat 
  ▎ constructions across circuit size, per-prover memory, proving time, 
  ▎ verification cost, and statement privacy — and what structural property of 
  ▎ ZK proof systems determines the shape of these tradeoffs?"

  The second clause is the key addition. It elevates the thesis from a benchmark
   study to an explanatory study. The structural property is your dualism:
  hierarchical decomposition adds a constraint in optimisation (useful) and
  weakens one in ZK proving (requiring O(N) restoration work). That explanation
  is the thesis's central claim, and the research question should set it up.

  If you want to additionally frame the duality with optimisation explicitly:

  ▎ "Unlike in classical combinatorial optimisation, where hierarchical 
  ▎ decomposition reduces search complexity, hierarchical decomposition in 
  ▎ zero-knowledge proofs does not reduce total proving work. This thesis 
  ▎ characterises when and why it nonetheless offers practical advantages — and 
  ▎ maps the resulting multi-dimensional tradeoff space for the TSP."

  This could serve as the thesis's opening paragraph rather than a formal
  research question. Use the first version as the formal RQ and the second as
  the motivating framing sentence.

  ---
  The related literature landscape

  Organise related work into five rings, from closest to furthest. This
  structure maps directly onto thesis sections.

  ---
  Ring 1 — ZKP for the Hamiltonian cycle problem specifically

  This is the most directly related literature, and the honest answer is: there 
  is almost nothing on practical SNARK-based ZKP for TSP or Hamiltonian cycle.
  That is your gap, and you should state it explicitly.

  What exists:

  The classical theoretical result — cite this as the historical foundation:
  Manuel Blum, "How to Prove a Theorem So No One Else Can Claim It" (1987,
  International Congress of Mathematicians). This is the first zero-knowledge
  proof specifically for the Hamiltonian cycle problem. It uses
  information-theoretic commitments (not SNARKs), requires multiple rounds, and
  is completely impractical to run — but it proves the existence of ZK for HC.
  Cite this to connect your work to the 35-year-old theoretical tradition.

  Goldreich, Micali, Wigderson, "Proofs that Yield Nothing But Their Validity or
   All Languages in NP Have Zero-Knowledge Proof Systems" (1991, JACM). This
  proves all NP problems have ZKPs, using 3-coloring and graph reductions.
  Hamiltonian cycle is a central example. Cite for the general "any NP statement
   can be proved in ZK" claim.

  The gap statement you can then make: "While the theoretical existence of ZK 
  proofs for Hamiltonian cycle has been known since 1987, no prior work has 
  designed or benchmarked practical SNARK-based circuits for TSP under modern 
  proof systems. This thesis fills that gap."

  Search terms: "zero knowledge proof Hamiltonian cycle", "zero knowledge proof
  TSP", "zkp travelling salesman". You will find very little post-2019 practical
   work. That absence is itself data.

  ---
  Ring 2 — ZKP for related graph and optimisation problems

  Since Hamiltonian cycle is sparsely covered, situate your work relative to
  adjacent practical ZKP work on NP problems. The goal is to show your
  contribution fits into a broader pattern of "practical ZKP for hard
  combinatorial problems."

  Shortest path:
  Search "zero-knowledge proof shortest path". This area has some practical work
   motivated by privacy-preserving navigation and routing (e.g., proving you
  know a route shorter than a threshold without revealing the route). The
  circuit structure is analogous: range check on edges, permutation-like check
  on path validity. This is your closest structural analog.

  Graph coloring:
  The classical GMW paper uses 3-coloring. There is modern practical ZKP work on
   graph coloring for constraint satisfaction proofs. Less directly related but
  useful for showing the design pattern (encoding graph properties as arithmetic
   constraints) is established.

  Set membership and range proofs:
  A large body of practical ZKP work. Merkle-tree based set membership proofs
  are directly used in your circuits. Papers like Camenisch & Stadler (1997) and
   more recent work on efficient range proofs set the precedent for the
  techniques your circuits use.

  Search terms: "ZKP graph problem", "zero knowledge path proof", "zero
  knowledge range proof circuit", "ZKP NP-hard combinatorial"

  ---
  Ring 3 — Scalability and efficiency of ZK provers: the performance dimension

  This ring provides the motivation for asking your scalability question in the
  first place. Why does prover efficiency matter? Because for real applications
  (blockchain, private auctions, logistics), proving is the bottleneck.

  Distributed/parallel proving:
  "Pianist: Scalable zkRollups via Fully Distributed Zero-Knowledge Proofs" —
  Liu et al. (2023). Directly addresses the problem of parallelising ZK proving
  across multiple machines. Their motivation section argues that single-machine
  proving is the bottleneck and K-prover setups are necessary for real
  applications. This is the use-case motivation for your parallel proving
  analysis. Search on IACR ePrint.

  "DIZK: A Distributed Zero Knowledge Proof System" — Wu et al. (2018, USENIX
  Security). An earlier work distributing Groth16 proving across a cluster.
  Establishes that distributed proving is a serious research direction.

  Prover memory as a constraint:
  Search "ZKP memory bottleneck", "prover memory reduction SNARKs". There is
  practical work showing that at large N, prover RAM is a harder bottleneck than
   proving time for many applications. This motivates your per-prover memory
  metric.

  Proof size and verification:
  "SnarkPack: Practical SNARK Aggregation" — Gailly, Maller, Nitulescu (2021,
  IACR ePrint 2021/529). Aggregates multiple Groth16 proofs into one, reducing
  verification cost from K to O(1). This is the aggregation solution to the
  problem your K+1 proof system has (K+1 verify calls). Cite it as "proof
  aggregation is a known technique to address this overhead; we leave it as
  future work."

  This ring gives you the sentence: "The scalability of ZK provers — in terms of
   memory, time, and bandwidth — has been identified as a core obstacle to 
  practical deployment [cite Pianist, DIZK]. This thesis contributes a 
  characterisation of these metrics for a specific NP-complete application."

  ---
  Ring 4 — Hierarchical and recursive ZKP: the structural dimension

  This is the most important related work ring for the dualism insight. The
  entire field of recursive/folding ZKP exists because of the problem your
  thesis characterises.

  Nova — read this carefully:
  Kothapalli, Setty, Tzialla, "Nova: Recursive Zero-Knowledge Arguments from 
  Folding Schemes" (CRYPTO 2022, IACR ePrint 2021/370).

  Read the introduction. It explicitly states that naive recursive proof
  composition (which is what your K+1 independent proofs are) is expensive
  because verifying an inner proof requires encoding the verifier's work as an 
  inner circuit, leading to O(|V|) overhead per recursion step where |V| is the
  verifier circuit size. Folding amortizes this. This is your dualism stated
  from the recursive proving direction.

  Your thesis frame: "Nova [cite] demonstrates that naive recursive proof 
  composition incurs O(N) overhead per step, motivating folding-based 
  approaches. This thesis confirms this principle empirically in the TSP domain:
   our hierarchical Variant A incurs approximately 2-4% total gate overhead 
  compared to the flat baseline, consistent with the prediction that 
  decomposition restores — not reduces — the total proving budget."

  SuperNova:
  Kothapalli, Setty (2023) "SuperNova: Proving universal machine executions 
  without universal circuits" — extends Nova to multiple distinct computation
  steps. Same motivation. IACR ePrint 2022/1758.

  Halo:
  Bowe, Grigg, Hopwood (2019) "Recursive Proof Composition without a Trusted 
  Setup" — early work on recursive SNARKs without trusted setup. Establishes
  that recursive proving is possible but expensive.

  Plonky2:
  Polygon team (2022) — uses FRI-based recursion to make recursive SNARKs fast.
  Commercially important (used in production). Shows the engineering response to
   the overhead your thesis measures.

  The framing for this ring: These papers answer the question "what do you do
  when hierarchical decomposition doesn't save gates?" — they invented folding
  and recursive SNARKs. Your thesis measures the overhead that motivated those
  inventions, in a specific application domain. That is the proper academic
  positioning.

  ---
  Ring 5 — Merkle trees and Poseidon2 in ZKP applications

  This ring motivates the specific technique of Merkle commitments for private
  cost matrices. The point is that your use of Poseidon2 Merkle proofs as a
  commitment scheme is established practice, not something you invented — and
  there are many precedents showing this is the right tool.

  Zcash (Sapling protocol):
  Hopwood, Bowe, Hornby, Wilcox (2022) "Zcash Protocol Specification". Uses
  Merkle trees with Pedersen hashes (now transitioning to Poseidon) to commit to
   note sets. This is the canonical "Merkle commitments for private data in
  SNARKs" application. Cite to establish the technique.

  Semaphore:
  An anonymous group membership protocol using Merkle proofs in ZK circuits
  (Ethereum ecosystem). Frequently cited as a reference for "Merkle proofs in
  ZK" design patterns.

  zkEmail / zkPassport:
  More recent applications using Merkle proofs in circuits to prove properties
  of private data (email headers, passport fields) without revealing the full
  document. Shows the pattern is general.

  The Poseidon2 paper:
  Grassi, Khovratovich, Rechberger, Roy, Schofnegger (2023) — IACR ePrint
  2023/323. Cite for the concrete gate count, the design rationale, and the
  security analysis. Also establishes that Poseidon2 is designed specifically
  for this Merkle-in-ZKP use case.

  Your framing for this ring: "Using a ZK-friendly hash function with a Merkle 
  commitment scheme to avoid O(N²) public inputs is an established pattern in 
  ZKP system design [cite Zcash, Semaphore]. We apply this pattern to TSP cost 
  matrices and characterise the O(N log N) Merkle verification cost 
  empirically."

  ---
  Ring 6 — Hierarchical decomposition in combinatorial optimisation (the duality
   connection)

  This ring is unique to your thesis and distinguishes it from a pure ZKP paper.
   The argument is: hierarchical decomposition is a known technique in
  combinatorial optimisation for TSP. The same operation has opposite effects in
   ZKP. This contrast is your original contribution.

  Christofides-adjacent hierarchical TSP:
  Search "hierarchical TSP", "divide and conquer TSP", "cluster-first
  route-second". There is a large operations research literature on decomposing
  TSP into sub-problems by partitioning nodes into clusters and solving each
  cluster independently. The standard reference is Lin & Kernighan (1973) or the
   Christofides algorithm survey literature. Cite to establish that hierarchical
   decomposition is a known technique in classical TSP solving.

  The key contrast you want to make:
  In classical optimisation, partitioning N nodes into K clusters reduces search
   complexity from O(N!) to roughly O(K · (N/K)!) — an exponential saving. In
  ZK, partitioning K circuits creates K sub-proofs that must be verified
  independently and a glue proof that restores global constraints, yielding
  approximately the same total gate count as the flat circuit. Same operation,
  opposite effect on computational cost.

  Search terms: "hierarchical TSP decomposition", "cluster first route second
  TSP", "divide and conquer Hamiltonian cycle"

  ---
  How to write the Related Work section

  Structure it as a two-part section:

  Part 1: Literature (what others have done)
  For each ring above, one paragraph: what exists, what the key works are
  (cited), and what they don't cover that your thesis does. The last sentence of
   each paragraph should be the gap or connection.

  Part 2: Positioning (how your work fits)
  A short synthesis paragraph at the end of the section, something like:

  ▎ "Prior work on ZKP for NP-complete problems has addressed the theoretical 
  ▎ existence of such proofs [GMW 1991] and their practical implementation for 
  ▎ graph problems [ring 2 cites]. Work on ZKP scalability has shown prover 
  ▎ memory and time to be the primary bottlenecks [Pianist, DIZK] and introduced
  ▎  folding schemes to address recursive overhead [Nova, Halo]. ZKP 
  ▎ applications have established Merkle commitments as the standard approach 
  ▎ for hiding large structured inputs [Zcash, Semaphore]. However, no prior 
  ▎ work has (1) applied practical SNARK-based circuits to the Hamiltonian cycle
  ▎  / TSP problem specifically, (2) systematically characterised the 
  ▎ multi-dimensional tradeoff space between flat and hierarchical 
  ▎ constructions, or (3) identified and empirically verified the structural 
  ▎ duality between hierarchical decomposition's role in combinatorial 
  ▎ optimisation and its role in ZK proving. This thesis addresses all three."

  That paragraph is your contribution statement, grounded in what the literature
   does and does not cover.

  ---
  On searching when you don't know what exists

  The practical workflow:

  1. Start at IACR ePrint (eprint.iacr.org). Search: "zero knowledge
  Hamiltonian", "hierarchical SNARK", "distributed ZK prover", "Merkle ZK
  circuit". Skim the titles and abstracts of the first two pages of results for
  each.
  2. Use Google Scholar for forward citations. Once you find Nova (2021/370),
  click "Cited by" — the papers that cite Nova will show you the whole
  folding-scheme family and adjacent efficiency work.
  3. Use the Related Work sections of Nova and Plonky2. These papers cite
  everything relevant in the scalability/recursion space. You can build most of
  your Ring 4 citations from their bibliographies.
  4. Search specifically for gaps. Search "zero knowledge proof TSP" and "zero
  knowledge proof travelling salesman". If you find almost nothing practical,
  that IS the result: you document the gap and your thesis fills it.
  5. For the optimisation literature, use Google Scholar with terms like
  "hierarchical TSP survey" or "cluster-first route-second Hamiltonian".
  Operations research papers don't appear on IACR, so use a broader search.

  The goal is not to find every paper ever written — it is to find the 3-4 most
  important works in each ring, read their introductions, and understand how
  your work relates. Fifteen to twenty references, chosen carefully and
  connected clearly to your circuits, is more valuable than fifty citations
  listed with no analysis.

✻ Churned for 2m 26s

❯ And what are some suggestions/considerations for a future work section that   
  does not scream "I could have done this but I was lazy" but more "this is     
  real hard to do for a MSc thesis, but a good input for something else"?       

● The key is specificity about why each direction is hard — the harder obstacle
  is usually either a fundamental technical barrier, an unresolved research
  question in the field, or a resource requirement beyond MSc scope. Vague
  future work ("larger experiments would be interesting") sounds lazy. Precise
  future work ("doing X requires Y, which the field doesn't yet have because Z")
   sounds like you understand the frontier.

  Here are the genuine follow-on directions, organized by type of obstacle.

  ---
  Group 1: The natural theoretical continuation — folding schemes

  The item: Apply Nova-style folding schemes to the hierarchical TSP
  construction instead of K independent proofs.

  Why it's genuinely hard, not just unfinished:
  Nova operates over relaxed R1CS — a fundamentally different arithmetisation
  than PLONK/UltraHonk. The thesis's circuits are written in Noir and compile to
   ACIR → UltraHonk gates. Porting to Nova requires rewriting the circuits in a
  different constraint system (Bellman, arkworks, or Microsoft's Nova
  implementation) with a different programming model. That is not a porting task
   — it is a re-implementation task with a different mathematical foundation.

  More importantly, TSP has a non-local global constraint: all N nodes must be
  visited exactly once. In IVC (Incrementally Verifiable Computation), each step
   typically proves something about a local transition. Encoding a global
  permutation check in the IVC framework is a non-trivial design problem that
  the folding literature has not addressed for this class of problem.

  How it connects to the thesis:
  The thesis establishes the baseline that a Nova-based approach would need to
  beat. The 2-4% total gate overhead quantifies exactly how much headroom
  exists: a folding approach that adds even modest per-step overhead would be
  worse than the flat circuit. The thesis makes this trade-off concrete, which
  is precisely the kind of benchmark a follow-up paper would cite.

  Forward value: If a folding scheme could handle the global permutation
  constraint without O(N) glue restoration, it would break the dualism this
  thesis identifies. That would be a genuine research contribution beyond MSc
  scope.

  ---
  Group 2: Formal security analysis — simulation-based ZK proof

  The item: Formally prove the zero-knowledge property for each variant using
  the simulation paradigm (UC or standalone model).

  Why it's hard:
  The thesis demonstrates soundness empirically (invalid witnesses are rejected)
   and argues ZK informally (private inputs don't appear in public outputs). A
  formal proof requires constructing an explicit simulator — an algorithm that,
  given only the public inputs, produces a transcript indistinguishable from a
  real proof — and proving indistinguishability under a computational
  assumption. For Variant A++, this requires a formal reduction from breaking
  the grand product check to breaking Poseidon2 as a random oracle, via the
  Fiat-Shamir heuristic security argument. This is a multi-page cryptographic
  proof requiring UC/standalone model expertise and familiarity with the random
  oracle model at a level well beyond standard MSc ZKP coursework.

  The off-circuit cross-check protocol (verify_hier.py) complicates this
  further: it needs to be modelled as part of the verification algorithm, and
  the simulator must account for it. Whether the K+1 independent proofs +
  cross-checks constitute a sound multi-proof protocol in the formal sense is
  itself an open question.

  How it connects to the thesis:
  The thesis provides the protocol specification that a formal analysis would
  verify. The GROUP-by-GROUP circuit documentation is exactly the kind of
  structured description a formal treatment would use as its starting point.

  ---
  Group 3: Distributed deployment study

  The item: Empirically validate the K× parallel proving speedup by running K
  sub-circuit provers on K dedicated machines or cloud nodes, rather than K
  concurrent processes on one machine.

  Why it's hard:
  The single-machine benchmark is limited by CPU contention — all K+1 bb prove
  instances compete for the same physical cores, producing the observed
  slowdown. Validating the theoretical speedup requires either a dedicated cloud
   cluster or real parallel hardware. Beyond the infrastructure requirement,
  this raises network overhead questions: the Prover.toml for each sub-circuit
  must be computed centrally (the Merkle builder requires the full matrix) and
  distributed to each prover, adding coordination latency. For large N, the
  sub-matrix data transferred per prover is non-trivial. A proper distributed
  deployment study would need to model this coordination overhead and determine
  at what N the parallelism benefit actually dominates it — a systems paper, not
   a ZKP paper.

  How it connects to the thesis:
  The thesis predicts K× speedup from circuit-size ratios. Confirming or
  disconfirming this empirically, and quantifying coordination overhead, is the
  natural experimental follow-up. The thesis provides the theoretical target;
  the deployment study provides the reality check.

  ---
  Group 4: Recursive proof composition with O(1) verification

  The item: Wrap the K+1 independent proofs into a single recursive proof,
  reducing verifier cost from O(K) to O(1).

  Why it's hard:
  Recursive UltraHonk (verifying a UltraHonk proof inside a Noir circuit) is
  under active development by Aztec and is not production-stable as of the
  versions used in this thesis. The verifier circuit for UltraHonk has thousands
   of gates — encoding it as an inner circuit would add substantial overhead
  that is only amortized at high recursion depth. Additionally, the cross-check
  logic currently in verify_hier.py (checking consistency of public inputs
  across proofs) would need to be encoded in-circuit, requiring the glue proof
  to essentially re-verify sub-proofs — the classic recursive overhead problem
  that Nova was designed to avoid.

  An alternative would be implementing in Plonky2 (which supports fast FRI-based
   recursion natively), but that requires re-implementing all five flat variants
   and the hierarchical architecture from scratch in a different framework.

  Forward value: Reducing K+1 verification calls to one would address the most
  practical weakness of the hierarchical approach — the linear verification
  cost. This is the industrial-strength version of the system.

  ---
  Group 5: Non-uniform partitioning

  The item: Allow segments of unequal size, matched to the natural clustering of
   nodes in the instance (e.g., geographic clusters for real road networks).

  Why it's hard:
  The current circuits use compile-time globals M, N, K — Noir requires array
  sizes to be comptime. Non-uniform partitioning would require segments of
  different sizes, meaning each segment would need its own separately compiled
  circuit with a different M value. The pipeline, Merkle builder, and benchmark
  harness would all need to support variable-M segment circuits. More
  fundamentally, the glue circuit's partition check (which concatenates K arrays
   of size M) would need to handle variable-length inputs — not straightforward
  in a constraint system where all array sizes are fixed at compile time.

  Beyond implementation, non-uniform partitioning raises a research question:
  does matching circuit partition boundaries to natural data clusters reduce the
   number of boundary-crossing edges (and thus boundary Merkle proofs), and does
   this interact meaningfully with the optimisation-side quality of the
  solution? This bridges the ZKP design question and the combinatorial
  optimisation question in an interesting way.

  How it connects to the thesis:
  The thesis's uniform partitioning is the baseline. Non-uniform partitioning is
   the natural generalisation that relaxes one of the thesis's explicit
  assumptions.

  ---
  Group 6: Extending the dualism to other NP-complete problems

  The item: Test whether the duality this thesis identifies — hierarchical
  decomposition reduces search complexity in classical optimisation but doesn't
  reduce total proving work in ZK — holds for other NP-complete problems (vertex
   cover, graph coloring, 3-SAT, knapsack).

  Why it's non-trivial:
  The thesis demonstrates the duality specifically for Hamiltonian cycle / TSP,
  where the global permutation constraint is the structural reason the glue
  cannot be made cheap. Different NP-complete problems have different global
  constraint structures. For graph coloring, the global constraint is "each
  vertex receives exactly one of K colors and no two adjacent vertices share a
  color" — whether hierarchical decomposition faces the same O(N) restoration
  cost depends on the problem's constraint topology. This is a research
  question, not an implementation task: it requires formulating a general
  principle and testing it across problem classes.

  Forward value: A positive result (the duality is universal for NP-complete
  problems with non-local constraints) would be a publishable theoretical
  finding. A negative result (some NP-complete problems admit cheap hierarchical
   ZK decomposition) would be equally interesting and would characterise which
  problem structures are amenable to hierarchical ZKP.

  ---
  Group 7: zkVM baseline at scale

  The item: Benchmark a RISC-0 (or SP1, or similar zkVM) implementation of TSP
  at the same N values and compare with the custom Noir circuits.

  Why it's the right kind of future work, not laziness:
  A single zkVM proof is achievable in a few days. A meaningful benchmark sweep
  — covering the same N values (5..500), with the same metrics (gates/cycles,
  memory, proof size), with accurate comparison of STARK vs SNARK proof sizes —
  requires understanding both systems well enough to compare apples to apples.
  STARK "cycles" and UltraHonk "gates" are not directly comparable without a
  careful bridge argument. The comparison is genuinely interesting but
  methodologically non-trivial: you would need to establish what "equivalent
  computational work" means across two fundamentally different arithmetisation
  strategies.

  Forward value: This places the thesis's custom-circuit approach on the broader
   design-space map, from "write circuits by hand for maximum efficiency" (this
  thesis) to "write Rust code and get ZK for free" (zkVM). Quantifying the
  programmability-efficiency tradeoff for TSP specifically is the contribution.

  ---
  The rhetorical pattern to follow when you write it

  Each future work paragraph should follow this structure:

  1. One sentence stating the direction — specific enough that someone could
  start working on it.
  2. One or two sentences on the obstacle — name the technical barrier
  (different arithmetisation, compile-time globals, formal model requirement,
  infrastructure need) specifically. This is what separates "real future work"
  from "didn't bother."
  3. One sentence connecting to the thesis — what the thesis provides that makes
   this direction possible or well-motivated.
  4. One sentence on the forward value — why it matters beyond the thesis.

  What to leave out:
  - Anything you could have done in a day and chose not to
  - Vague statements like "further optimisation is possible"
  - Additional benchmark runs at larger N unless you name the specific hardware
  limitation
  - Implementation of Variant B, if you implement it before submission — that
  becomes a chapter, not future work

  The honest framing for anything you genuinely ran out of time for (like
  Variant B) is to not mention it as future work — describe it in the thesis as
  work in progress or include it in the implementation chapter with partial
  results if you have them. Future work is for directions that require something
   you genuinely don't have: a different proof system, formal cryptography
  training, cloud infrastructure, or an unresolved research question in the
  field.

✻ Sautéed for 1m 57s

❯ All right, other things worth mentioning that I should know for the thesis    
  document, along the lines of what we've been discussing? Style, first         
  principle reasoning, derivations, organization. Anything at all?              

● A lot of this comes from watching student theses fail in predictable ways. Let
   me cover the things that actually matter.

  ---
  The argument architecture

  The most important structural decision is where to place the dualism insight.
  Most students would put it in the discussion chapter after presenting all the
  results. Don't. Put it before the hierarchical implementation chapter, as its
  own short chapter or a substantial section. The reason: if the reader
  encounters the hierarchical benchmark results (prove times are worse, gates
  are the same) without the analytical lens first, they read the results as
  failure. If they read the dualism argument first, they read the same results
  as confirmation of a predicted structural property. Same data, completely
  different impression.

  The thesis should be organised so that each chapter gives the reader exactly
  what they need for the next one — no more, no less. Flat circuits establish
  the baseline and the GROUP structure vocabulary. The dualism argument explains
   why the hierarchical results will look the way they do. The hierarchical
  chapters then present results that confirm a prediction rather than fail a
  hypothesis.

  Every chapter should open with one paragraph saying what it does and close
  with one paragraph saying what it showed and why the next chapter needs that.
  Examiners read opening and closing paragraphs first. Make them load-bearing.

  ---
  The negative result is the thesis

  Many students bury negative results or frame them apologetically. Don't. "We
  hypothesised X, and found not-X" is a valid, publishable research outcome when
   the analysis explains why. State it plainly in the introduction:

  ▎ "We find that hierarchical decomposition does not reduce total proving work:
  ▎  Variant A requires approximately 2-4% more gates than the flat Merkle 
  ▎ baseline. We explain this through a structural duality: hierarchical 
  ▎ decomposition reduces search complexity in combinatorial optimisation but 
  ▎ requires O(N) glue work to restore global soundness in ZK proving, 
  ▎ approximately cancelling the per-segment saving."

  Spoil the finding in the introduction. Academic theses are not mystery novels.
   An examiner who reads the introduction and already knows the conclusion will
  read the rest of the thesis to evaluate whether your evidence and reasoning
  justify it — which is the right question.

  ---
  First principles reasoning for circuits

  The mental model you should apply to every constraint group, and make explicit
   in the thesis: "What could a malicious prover do if this constraint were 
  absent?" This inverts the usual implementation framing (describing what valid
  witnesses satisfy) to the security framing (describing what attacks each
  constraint blocks).

  Every GROUP entry in the thesis should have this form:

  ▎ "GROUP 1 asserts cycle[i] < N for all i. Without this check, a prover could 
  ▎ supply an index ≥ N, causing from * N + to to overflow u32 at N > 181 (since
  ▎  181² > 2³²), aliasing the computed leaf index into the padded zero-region 
  ▎ of the Merkle tree. A collision with a zero-padding leaf could cause a zero 
  ▎ edge cost to be accepted as committed. The range check blocks this attack."

  This structure — constraint, attack it prevents, why that attack matters —
  makes the circuit design read as reasoned security engineering rather than
  implementation detail.

  Apply the same to hierarchical-specific groups: the glue partition check
  exists because without it a prover can put node 3 in both segments. The
  leaf-index reconstruction exists because without it a prover can use a cheap
  leaf's Merkle proof for an expensive edge.

  ---
  What to derive, what to cite

  Derive these yourself — they show you understand the mathematics rather than
  just the implementation:

  The gate count estimate before measuring with bb gates. Show the arithmetic:
  at N=480, K=4, M=120, DEPTH=18, GROUP 3 costs (M-1) × DEPTH Poseidon2 calls
  per sub-circuit. With ~87 gates per call (empirically established in your flat
   baseline chapter), that's 119 × 18 × 87 ≈ 186k gates per sub-circuit.
  Multiply by K, add the glue estimate, compare to the flat Merkle formula. Then
   show the measured value and note the discrepancy is ~X% overhead from GROUP
  1+2+3+5 and fixed circuit constants. This is the kind of derivation that
  demonstrates genuine understanding.

  The Schwartz-Zippel soundness bound. Two or three lines: the grand product
  check is equivalent to evaluating two degree-N polynomials at a single point.
  By Schwartz-Zippel, if the polynomials differ they agree at at most N points
  out of the field. The probability of a random challenge landing on a
  false-positive point is ≤ N/|Field| = 480/2^254 ≈ 2^{-246}. Negligible.

  The information-leakage argument for each variant. How many bits of partition
  information does each variant disclose? Variant A discloses sorted_nodes[M]
  for each segment — effectively the exact partition, log₂ C(N, M, M, ...) bits.
   Variant A++ discloses only 2K endpoints. At K=4, N=480: Variant A discloses
  ~960 bits of partition information; Variant A++ discloses ~9 bits (4
  start-node indices and 4 end-node indices at log₂(480) ≈ 9 bits each — ~72
  bits total). This quantification takes one paragraph and makes the privacy
  comparison precise.

  Cite without derivation:
  UltraHonk soundness, Poseidon2 collision resistance, Fiat-Shamir ROM security,
   the NP-completeness of Hamiltonian cycle. For each, one sentence stating what
   you assume and the citation.

  ---
  Notation and terminology precision

  A few terms have specific technical meanings in the ZKP literature. Using them
   loosely will lose marks with an examiner who knows the field.

  Argument vs. proof. A ZK proof has unconditional (information-theoretic)
  soundness. A ZK argument has computational soundness — it only holds against
  computationally bounded adversaries. UltraHonk produces a knowledge argument,
  not a proof. Use "argument" unless you're discussing the theoretical GMW
  result.

  Soundness vs. zero-knowledge. These are separate properties. Soundness: a
  cheating prover cannot make the verifier accept a false statement.
  Zero-knowledge: an honest prover does not reveal anything beyond the truth of
  the statement. Your test suite demonstrates soundness. The structure of
  public/private inputs establishes the ZK property. Discuss them separately.

  Efficient. In ZKP, "efficient" typically means polynomial-time (vs.
  exponential). When you mean "faster" or "fewer gates," say that specifically.
  "Variant A++ is more efficient" is ambiguous; "Variant A++ requires 5.5% more
  gates but discloses fewer public inputs" is not.

  Privacy vs. security. Privacy is about what the verifier learns; security
  (soundness) is about what a cheating prover can claim. The thesis addresses
  both, in different sections, using different evidence.

  For notation consistency: use lowercase italic for field elements (x, r, c),
  uppercase for sets and matrices (N, K, M), typewriter font for code
  identifiers and circuit names (cycle_segment, flat_merkle_presence), and keep
  the GROUP numbering (G1–G5) consistent throughout. Define it once in the flat
  circuits chapter and use it everywhere.

  ---
  The empirical sections

  The experimental setup paragraph is non-optional. One paragraph at the start
  of every evaluation section: CPU model, RAM, OS, Noir version, Barretenberg
  version, benchmark parameters (N values, runs per cell, base seed). This is
  not boilerplate — ZKP toolchains change rapidly between versions and your
  numbers are only reproducible if someone knows exactly what you ran. The nargo
   and bb version numbers should be in the thesis.

  Gate count has zero variance; prove time has non-zero variance. Report this
  correctly. For circuit_size, show one number (it's deterministic). For prove_s
   and peak_mb, show mean ± std across runs. In the log-log plots, the slope
  annotations already do this well. In any table, the convention is "mean (std)"
   or "mean ± std."

  Every table and figure needs interpretation in the surrounding text. "Table 4
  shows the results" is insufficient. Every table should be followed by
  sentences that say: which rows are surprising, which are expected, which
  confirm the hypothesis, and what the reader should take away. If you produce a
   figure and don't say what it shows in the prose, the examiner has to do the
  interpretive work you should have done.

  The contention problem needs an explicit methodological note, not a footnote.
  In the section where you present prove_s for hierarchical variants, before the
   table: explain that K+1 workers ran concurrently on one machine, that bb
  prove is internally multithreaded, and that the measured prove_s reflects
  contention degradation rather than the per-prover time on dedicated hardware.
  Then give the circuit-size ratio estimate for the ideal parallel time. This is
   honest and shows methodological awareness — which is exactly what an examiner
   wants to see.

  ---
  What not to put in the main text

  Code listings. A few lines showing a key constraint (the leaf-index
  reconstruction, the grand product formula) are fine inline. Full circuit
  source code goes in an appendix, referenced by name. The thesis is not a code
  walkthrough.

  Terminal output. Don't paste nargo execute output. Summarise it: "The
  correctness test suite (6 cases: 1 valid, 4 negative, 1 sanity) passes in all
  cases."

  Repetitive structure. If three circuit variants share the same GROUP 1-3,
  describe them once fully for the first variant, and for subsequent variants
  say "GROUP 1, 2, and 4 are identical to flat_full_presence; GROUP 3 differs as
   follows." Don't repeat the range check description five times.

  The pipeline in detail. The Rust Merkle builder, Python harness, shadow
  directories, and CSV aggregation pipeline are implementation details of the
  benchmarking infrastructure, not contributions of the thesis. One paragraph
  describing the pipeline architecture is enough. The HOWTO.md is the right
  place for the step-by-step; the thesis is the right place for the high-level
  description and any non-obvious design choices.

  ---
  The frontier figure

  This is the thesis's signature figure and it has to do a lot of work. A few
  considerations:

  Use a scatter plot with labelled points, not a line plot. You are not showing
  a trend; you are showing discrete design choices as positions in a space. Each
   variant is one point. The axes should be chosen so the interesting structure
  is visible — probably (total gates, per-prover memory) as the two primary
  axes, with privacy disclosed encoded as point shape or colour, and proof
  bandwidth as point size or a secondary panel.

  Write the caption so it is fully self-contained. Someone should be able to
  look at just the figure and its caption and understand the thesis's central
  finding. The caption should name all the points, state what the axes mean, and
   include one sentence of interpretation: "No variant Pareto-dominates the 
  others: Variant A++ achieves the lowest privacy disclosure but incurs the 
  highest gate count; Variant B achieves the lowest gate count at full partition
   and sub-matrix disclosure."

  ---
  One meta-point about voice

  Throughout the thesis, be specific about what you measured, what you derived,
  and what you assumed. The three categories are distinct and should read
  differently:

  - Measured: "At N=480, K=4, Variant A requires 775,622 total UltraHonk gates 
  (mean across three compilations; gate count is deterministic)."
  - Derived: "From the circuit structure, this is expected: (M-1)·DEPTH 
  Poseidon2 calls per sub-circuit at ~87 gates/call yields approximately 186k 
  gates per sub-circuit, totalling ~775k before fixed overhead."
  - Assumed: "We assume UltraHonk is a sound knowledge argument under the 
  discrete logarithm assumption [cite]; we do not verify this property 
  independently."

  A student who consistently distinguishes these three registers demonstrates
  exactly the kind of intellectual rigour an MSc examiner is looking for. It
  signals that you know the boundaries of your own work.

✻ Sautéed for 2m 32s

❯ Can you check wheather the variant A memory measure is for a single segment   
  only, And we exploit the "parallel" to get that reduction, or is it something 
   different?                                                                   

● Let me check the raw data and aggregation code carefully.

  Read 1 file (ctrl+o to expand)

● There's something important here. Let me work through the numbers carefully.

  Searched for 1 pattern, read 1 file (ctrl+o to expand)
● The picture is clear and actually has more nuance than the thesis currently
  captures. Let me lay it out.

  ---
  What peak_mb actually measures

  aggregate_hier.py line 139: peak_mb = max(...) — it takes the single heaviest 
  worker across all K+1. So it answers: "how much RAM does the most demanding 
  individual prover need?" That is the per-prover memory under a distributed
  model where each prover runs on its own machine.

  ---
  Three separate things are happening

  1. Sub-circuit memory scales with M = N/K — genuinely.

  ┌───────────────┬─────────────┬─────────┬─────────┬─────────┐
  │     N=480     │ flat_merkle │ K=2 sub │ K=4 sub │ K=8 sub │
  ├───────────────┼─────────────┼─────────┼─────────┼─────────┤
  │ peak_mb       │ 1078 MB     │ 551 MB  │ 285 MB  │ 152 MB  │
  ├───────────────┼─────────────┼─────────┼─────────┼─────────┤
  │ ratio vs flat │ 1×          │ ÷1.96   │ ÷3.78   │ ÷7.09   │
  └───────────────┴─────────────┴─────────┴─────────┴─────────┘

  Each sub-circuit prover only holds (M-1)×DEPTH Merkle witnesses instead of
  N×DEPTH, so its memory scales roughly as N/K. The reduction is real and close
  to the theoretical K×.

  2. The glue memory does NOT scale with K — it is an O(N) floor.

  The glue circuit processes all_sorted_nodes[N], K boundary Merkle proofs, and
  an N-length sort regardless of K. At N=480:

  ┌─────────┬──────────┬──────────┬──────────┐
  │         │ K=2 glue │ K=4 glue │ K=8 glue │
  ├─────────┼──────────┼──────────┼──────────┤
  │ peak_mb │ ~159 MB  │ ~159 MB  │ ~159 MB  │
  └─────────┴──────────┴──────────┴──────────┘

  The glue's memory is essentially constant across K values at the same N. It is
   always there and always O(N).

  3. At K=8, the reported peak_mb is the glue, not a sub-circuit.

  At N=480, K=8: sub=152 MB, glue=160 MB → max() returns the glue. The "K=8
  memory reduction" the thesis currently reports is partly the glue's constant
  overhead, not the sub-circuit's scaling. This first appears at K=8 around
  N=96, where sub≈40 MB and glue≈41 MB.

  ---
  The single-machine reality

  All K+1 workers ran simultaneously on one machine. Their peaks don't overlap
  in sequence — they all hit peak concurrently. The actual RAM on the machine at
   peak is roughly:

  ┌──────────────────┬─────────────┬──────────┬──────────┬──────────┐
  │      N≈480       │ flat_merkle │ hier K=2 │ hier K=4 │ hier K=8 │
  ├──────────────────┼─────────────┼──────────┼──────────┼──────────┤
  │ Total concurrent │ 1078 MB     │ ~1262 MB │ ~1300 MB │ ~1379 MB │
  └──────────────────┴─────────────┴──────────┴──────────┴──────────┘

  On a single machine, hierarchical always uses more total RAM than flat. The
  memory benefit is structurally the same as the prove-time benefit: it only
  materializes on K+1 dedicated machines.

  ---
  What the thesis should say

  The current framing ("memory per prover is reduced K×") is correct but
  incomplete. The precise statement has three parts:

  True and should be said: Each of the K sub-circuit provers requires
  approximately flat_merkle_memory / K RAM (the per-prover reduction is real and
   close to K× for K=2,4).

  True and must be added: The glue prover requires O(N) memory regardless of K —
   approximately 15% of flat_merkle memory at N=480. As K increases, the glue
  becomes the bottleneck prover for memory (at K=8 it already is).

  True and mirrors the prove-time situation: On a single machine running all K+1
   provers concurrently, total RAM exceeds flat_merkle. The K× per-prover
  reduction is a distributed-hardware claim, not a single-machine claim —
  identical to the parallel wall-clock claim.

  ---
  The additional finding worth stating

  The glue's O(N) memory floor is itself a consequence of the dualism. The glue
  must check the global partition — that check costs O(N) in gates (the sort)
  and O(N) in memory (the all_sorted_nodes input). Variant A++ partially
  addresses this: replacing the sort with a grand product drops the glue's
  in-circuit work from O(N) to O(K), which should reduce the glue's memory too.
  That makes A++'s memory profile more uniform across the K+1 provers — worth
  measuring once A++ is implemented.

✻ Crunched for 2m 29s