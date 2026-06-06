# Writing-Style Guide — for the Master Thesis (English)

This guide reconstructs the writing style of two source documents and fuses them into a
single target voice to use for the master thesis:

- **Source A** — *Bachelor thesis* (Italian): Set-Covering / Frank-Wolfe. Rigorous,
  didactic, "from first principles," but in a *reserved* Italian academic register.
- **Source B** — *Project report* (English): PCB drilling / TSP, SCF formulation + tabu
  search. Same first-principles rigor, but with a *warm, narrative, occasionally playful*
  voice.

**The target voice = A's logical scaffolding + B's temperature.** Formal where it matters
(definitions, models, theorems, claims about results), entertaining in the connective
tissue (chapter bridges, motivations, asides, the story of how the work actually went).

The hard part is that A is the *intellectual* model but is written in Italian, so its
prose must be *re-voiced*, not translated. See §11 for the Italian→English pitfalls.

---

## 1. The underlying philosophy (what the writing is *for*)

Both sources obey the same contract with the reader, and the thesis must too:

1. **Self-containment / first principles.** A motivated reader with general background
   should be able to follow without leaving the document. Every concept used later is
   introduced earlier, defined, and given just enough theory to be *used*. The Italian
   thesis literally builds optimization → LP → duality → Lagrangian relaxation → integer
   programming → Frank-Wolfe before it lets itself talk about Set-Covering. The report
   builds graph model → MILP/SCF formulation → why it's correct → implementation.
   - Corollary: *introduce notation the moment you need it, never before, and reuse it
     verbatim afterwards.*

2. **Motivate before you formalize.** The pattern is always **intuition → formal object →
   properties → consequence/connection**. Never drop a definition or equation cold; the
   sentence before it says *why we want it*. ("The intuition behind Lagrangian relaxation
   is to simplify a problem by removing some constraints and adding a penalty..." *then*
   the math.)

3. **Justify every choice, and admit the cost.** Both texts explain *why* a decision was
   made and what it trades away. The report is explicit about trade-offs ("The downside is
   higher computational complexity... This trade-off was deemed acceptable") and even
   about arbitrary choices ("This choice is admittedly arbitrary and not supported by a
   strong theoretical justification"). Honesty is part of the voice.

4. **Forward/backward signposting.** Sections constantly reference each other ("as
   anticipated in 2.5", "the considerations made in 1.3.5", "which we will implement in
   Chapter 3"). The reader always knows where a thread was opened and where it pays off.

5. **Earn the result.** Results chapters don't dump tables; they state what question each
   experiment answers, then read the trend in plain language ("there is an initial phase
   where the bounds are poor, followed by rapid improvement, then they stabilize").

---

## 2. Macro-structure

### 2.1 Chapter openers = a one-paragraph roadmap
Every chapter starts with a short italic-free paragraph stating *what this chapter does*,
usually in a "first… then… finally" shape.

- Thesis: *"The objective of this chapter is to present the basic concepts used in the
  rest of this work..."*
- Report: *"This chapter introduces the problem, beginning with a real-world scenario. We
  then present a graph-based framework for its formal definition and conclude by developing
  a mathematical model..."*

**Target:** keep this. Make it a genuine map, 2–4 sentences, "We first X, then Y, and
finally Z." It's allowed to be slightly playful in the last clause.

### 2.2 Section bridges = hand-offs, not full stops
Sections end by pointing at the next one, and begin by recalling the last.
- Closing a section: *"This result constitutes the theoretical basis of the solution
  algorithm we will implement in Chapter 3."*
- Opening: *"In the previous chapter we addressed Lagrangian relaxation... in this section
  we can exploit those arguments to apply the concept to..."*

**Target:** never let a section just stop. One bridging sentence out, one recalling
sentence in.

### 2.3 Chapter closers
End chapters/the thesis by *retelling the journey* compactly: "we started from X, did Y,
used Z to measure W, and found…". The thesis conclusion is a model of this — it
reconstructs the whole arc in one page and states the headline findings in plain words.

---

## 3. The argument engine (paragraph-level logic)

The reusable template for introducing *any* new object (a model, a relaxation, an
algorithm, a data structure):

1. **Why we want it / what problem it solves** (one or two sentences of intuition).
2. **The formal object** — definition, formulation, or equation, with all symbols typed.
3. **Immediate properties** — "it is easy to verify that…", bounds, special cases, what
   happens at the extremes (empty set, all-zeros, λ=0/1, etc.).
4. **Connection** — how it feeds the next step or an earlier promise.

Worked example of the rhythm (report, on the SCF model): high-level idea of routing
n−1 units of flow → sets/parameters/variables listed → objective → constraints one at a
time, each prefaced by what it enforces → *then* a remark that one constraint is redundant
and *why* → the clean final model → an interpretation paragraph on what the variables
"mean" physically.

Notice three habits worth stealing:
- **Constraints/steps introduced one at a time, each with its purpose stated first**
  ("Now we enforce (i) for all other nodes, which requires …").
- **Redundancy / simplification called out explicitly** ("we notice that constraint (1.2)
  is redundant. Indeed, constraint (1.3) implicitly enforces…").
- **A semantics paragraph** after the math, translating symbols back to the real object
  ("the binary variables define the physical topology of the tour… the flow variables
  represent a fictitious commodity used solely to enforce connectivity").

---

## 4. Voice and person

- **First-person plural "we" is the default** in both sources, used for *intellectual
  moves*: "we consider", "we notice", "we can limit ourselves to", "we define", "we now
  proceed to". It signals author + reader walking together. Keep this as the backbone.
- **Second-person "you" appears in how-to / operational passages** in the report ("you can
  simply run the following commands", "By modifying these parameters, you can construct…").
  Use "you" for instructions to the reader (compilation, running solvers, configuring),
  "we" for reasoning.
- **Impersonal/passive is used sparingly**, mostly for established facts ("it can be shown
  that…", "the matrix is stored in a separate .dat file"). Don't let it dominate — Italian
  academic prose over-uses the impersonal; English should lean active.

---

## 5. Self-containment & notation discipline

- Define each symbol *at first use*, inline, with its type: "let \(n = |\mathcal N|\)",
  "\(c_{ij} \in \mathbb R_{\ge 0}\)". Both texts are meticulous about domains/types.
- After defining a compact form, **reuse the compact form** ("In compact matrix–vector
  notation we can rewrite … as \(L(u)=\min\{c^Tx+u^T(b-Ax)\}\)" — then that's what's used).
- Number every displayed equation that is referenced later; refer back by number.
- When two formulations are equivalent, **say so and say why you switch** ("it is
  convenient to consider an alternative, fully equivalent formulation, obtained by
  transforming constraint (2.4) into…").
- Put central definitions/theorems/problem statements in **named, boxed callouts**
  (Definition 1.1, Theorem 1.2). In the report this device is also where the *fun* lives —
  the problem statement box is titled **"The Travelling Drillman's Holey Grail"**. Use
  boxes for the load-bearing formal content; they can carry a witty title.

---

## 6. The dual register — where to be formal, where to be fun

This is the crux of what you asked for. Treat the document as having two layers:

**Formal layer (keep it precise, no jokes inside):**
- Definitions, theorems, problem statements, model formulations, equations.
- Claims about correctness, complexity, optimality.
- Statements of experimental results and what they show.

**Warm layer (this is where personality goes):**
- Chapter/section openers and bridges.
- Motivations ("why would anyone want this?").
- Asides and disclaimers to the reader.
- The narrative of *how the work went* — false starts, fixes, trade-offs.
- Section *titles* (the report uses these as comic relief: "Beyond Numbers",
  "Speedup & (Pessimistic) Optimality Gaps", "Improving Clustering to Mitigate the Price
  of Hierarchy", "Stitching the Cluster Tours", "Polishing the Stitched Global Tour").

Rule of thumb: **be entertaining in the connective tissue, exact in the load-bearing
walls.** A reader should never be unsure whether a sentence is a joke or a claim. Wit
lives in framing, never inside a theorem.

**Locked calibration (this thesis).** The agreed dial is *dry wit and understatement*,
with the warmth coming from honesty, narrative momentum, and well-aimed phrasing rather
than jokes. Two source-native devices are explicitly **kept** so this calibration does not
flatten into a technical report: (1) **witty section titles** (the "Holey Grail" / "Price
of Hierarchy" register), and (2) **the rare reader-directed aside, only at a chapter
seam** — one every few pages at most, never inside exposition. Everything else stays sober.
Most voice lives in Chapters 1, 8, 11, 12; Chapters 2, 5, 6, the soundness sections, and
the results tables stay flat.

---

## 7. The narrative-of-discovery device (the report's signature move)

The report frequently tells the story of a sub-problem as a small drama:

> naive idea → *why it disappoints* → the better idea → *why it works* → the cost it
> carries.

Examples to imitate:
- Cluster geometry: "Our first attempt relied on centroids… While conceptually simple, it
  performed poorly in practice… To address this, we switched to a minimum-boundary
  distance approach… The downside is higher computational complexity… This trade-off was
  deemed acceptable."
- Stitching tours: "A first natural idea is a greedy constructive approach… While
  appealing in its simplicity, this strategy performs poorly in practice. The underlying
  issue stems from… A more effective approach exploits a simple but crucial observation…"

This is *gold* for a master thesis: it makes the work feel earned and human, shows you
understand *why* the final design is what it is, and is intrinsically more readable than a
flat description of the finished artifact. Use it for every non-trivial design decision.
Pair it with named vivid problems ("chicken-and-egg dependency", "the price of hierarchy")
so the reader has a handle to remember.

---

## 8. Reader-directed asides and honesty (use sparingly, deliberately)

The report earns goodwill with occasional direct address:
- A disclaimer when scope is cut: *"A brief disclaimer is in order. The final algorithm…
  is the result of many hours of development, including numerous failed attempts… a fully
  detailed description of every design choice is no longer feasible within the scope of
  this report."*
- A wink at the slog: *"With the SCF model implemented, tested, and a fair amount of sleep
  deprivation behind us (hoping none of this has been too boring) we can now move on to a
  slightly more entertaining part…"*
- Candor about arbitrariness: *"This choice is admittedly arbitrary…"*

Guidelines:
- One genuine aside every few pages, never two in a row. They work because they're rare.
- Keep them in parentheses or as a short separate sentence at a *transition*, never inside
  technical exposition.
- A master thesis tolerates slightly *less* of this than an internal report, since it's
  examined. Calibrate: keep the warmth and the discovery-narrative everywhere; ration the
  overt jokes/sleep-deprivation gags to chapter seams. When in doubt, the *wit goes in the
  section title and the framing sentence*, not in the body.

---

## 9. Sentence-level mechanics

- **Connectives, but varied.** Both texts lean on logical connectors. In English, rotate
  them and don't calque the Italian density:
  - consequence: *therefore, as a result, consequently, this means that, so* (avoid
    starting every other sentence with "Therefore"; the Italian "Di conseguenza" tic).
  - addition: *moreover, in addition, also, on top of this*.
  - contrast: *however, that said, nevertheless, on the other hand*.
  - restatement: *in other words, put differently, that is*.
  - emphasis/justification: *indeed, in fact, after all* — **use these much less than the
    Italian "Infatti/In effetti"** would suggest (see §11).
- **Sentence length: vary it.** Italian academic prose runs to long periodic sentences;
  English reads better when a long explanatory sentence is followed by a short punchy one.
  The report does this ("…performs poorly in practice." full stop, new thought).
- **Signature signposting phrases** (these are *on-brand*, reuse freely):
  - "It is worth emphasizing that…", "It is important to note that…", "Note that…",
    "Notice how…", "Observe that…", "Recall that…".
  - "To take a concrete example…", "As a concrete example…", "Concretely…".
  - "The idea is to…", "The intuition behind X is…", "The underlying issue is…",
    "The central question then becomes…".
  - "Without loss of generality (and for simplicity), we assume…".
  - "It is easy to verify that…", "One can show that…".
- **Hedge precisely, not vaguely.** Quantify when you can ("its gap never exceeds 1.5%",
  "on the order of \(\mathcal O(n^2)\)") and hedge honestly when you can't ("this is likely
  suboptimal for certain classes of instances").
- **Lists for parallel structure.** Both use numbered/bulleted lists for: enumerated
  options (the three movement modes), step procedures, sets/parameters/variables,
  configuration parameters. Use lists when items are parallel; prose when they're a chain
  of reasoning.

---

## 10. Math & results presentation conventions

- Display equations on their own line, numbered if referenced. Keep a clean
  `min / s.t.` block for the full model, with all variables on the LHS and constants on
  the RHS — and *say* you did that and why ("we arranged the terms so that all variables
  appear on the LHS… useful when translating the model into the CPLEX APIs").
- Introduce **algorithms as high-level numbered pseudocode** ("the steps are summarized in
  the high-level specification below"), and explicitly note termination conditions ("an
  implementation must set a stopping condition to prevent the algorithm from iterating
  indefinitely").
- When code is too long, **say you're abbreviating and why**, and show pseudocode or a
  partial listing instead ("rather than presenting lengthy and distracting source code, we
  provide only a high-level pseudocode description… keeping the focus on the algorithmic
  insight").
- **Results reading.** For each figure/table: (1) one sentence naming what varies and what
  is measured, (2) the qualitative trend in words, (3) the interpretation / caveat.
  - The thesis reads convergence plots as a *phased story*: "poor initial phase → rapid
    improvement → plateau."
  - The report adds a **"beyond the numbers"** section that interprets *what the solution
    looks like*, not just its cost, and warns when a metric is misleading ("relative gaps
    are highly sensitive to the scale of the objective… can look worse than the actual
    quality difference"). Steal this: always sanity-check what a number *means*.
- Normalize/standardize metrics and state the baseline ("values normalized with respect to
  the optimum obtained by the simplex algorithm").

---

## 11. Italian → English: re-voicing, not translating

The thesis is the intellectual template but its *prose habits* are Italian. When porting
the style to English, actively counter these calques:

| Italian habit | What it produces if translated literally | Do instead |
|---|---|---|
| "Di conseguenza" every few sentences | "Therefore/Consequently" overload | Rotate connectives; sometimes just start the sentence with the fact |
| "Infatti", "In effetti" | "Indeed", "In fact" overuse (sounds defensive) | Drop most; keep "indeed" rare and earned |
| "Naturalmente" | "Naturally/Of course" (can sound condescending) | Use "of course" sparingly; often delete |
| Heavy nominalization ("l'ottenimento della formulazione") | "the obtainment of the formulation" | Use verbs: "obtaining the formulation lets us…" |
| Long periodic sentences with multiple subordinate clauses | run-ons | Split into 2–3 sentences; alternate long/short |
| Impersonal "si dimostra che", "si verifica immediatamente" | passive everywhere | Prefer active "we can show that", "one can verify" |
| "Tale", "quest'ultimo/a" as referents | "such", "the latter" everywhere | Repeat the noun or use "this/that X" |
| "permette di + infinitive" | "allows to do" (ungrammatical) | "allows us to", "lets us", "makes it possible to" |
| Abstract throat-clearing openers | "It is important to underline how…" | Keep *some* (it's on-brand) but vary and tighten |

Keep from the Italian: the **didactic patience**, the **intuition-first ordering**, the
**"we" companion voice**, the **define-then-use discipline**, the **explicit
property-checking** ("if R is infeasible, then P is infeasible; the converse does not
hold"). Lose: the connective density, the nominalizations, the uniform formality.

---

## 12. Do / Don't checklist

**Do**
- Open each chapter with a roadmap; close it by retelling the arc.
- Motivate before formalizing; give the intuition, then the math, then the properties.
- Tell the story of hard design decisions (naive → flawed → fixed → cost).
- Name your villains ("chicken-and-egg dependency", "the price of hierarchy").
- Justify choices and admit trade-offs and arbitrary calls.
- Put wit in section titles and framing sentences.
- Keep "we" for reasoning, "you" for instructions.
- Vary sentence length; vary connectives.
- Sanity-check what every metric actually means before trusting it.
- Reuse notation verbatim once introduced.

**Don't**
- Drop a definition, equation, or table without a "why" before it.
- Put a joke inside a theorem, a claim, or a results statement.
- Stack asides — one per few pages, at seams only.
- Calque Italian connectives ("Therefore… Indeed… Naturally…").
- Let passive/impersonal constructions dominate.
- Introduce notation you don't use, or use notation you didn't introduce.
- Dump results without reading the trend in plain language.

---

## 13. A short worked example in the target voice

> *(Section opener, warm layer — roadmap + a light touch)*
> Having a model is one thing; trusting it is another. This section builds that trust the
> cheap way first: before we throw thousands of holes at the solver, we hand it a problem
> so small we already know the answer.
>
> *(Motivation → formal object, formal layer)*
> Concretely, we construct a 5×5 cost matrix in which exactly one tour is cheap and every
> alternative is prohibitively expensive. If the solver is correct, it must return that
> tour — and only that tour. The instance is stored as `sanity_check.dat`.
>
> *(Result reading, formal layer)*
> Running the solver yields the sequence \(0\to1\to2\to3\to4\to0\) with objective value 5,
> in roughly 2.6 ms. Both the path and its cost match the construction, so variables,
> constraints, and the reconstruction logic all behave as intended.
>
> *(Interpretation + honest caveat, warm layer)*
> A caveat is worth stating plainly: these "costs" make no physical sense as drilling
> distances. They only have to be *adversarial* — a setting where the cheap transitions
> are the only convenient moves and any deviation is punished. Which is, really, the whole
> point: the solver never sees a board. It sees numbers, and it minimizes. That it does so
> here, on a problem we can check by eye, is exactly the confidence we needed before
> scaling up.

This shows the full rhythm in miniature: warm opener → precise setup → precise result →
warm, honest interpretation that doubles as a transition.

---

## 14. Project-specific application (ZK-for-TSP)

§§1–13 reconstruct the *general* target voice from two optimization sources. This section
instantiates that voice with **this thesis's subject matter**, so a draft can be checked
against it directly. When §§1–13 and §14 seem to disagree, §14 wins — it is the localized
contract.

### 14.1 The discovery narrative is the spine, not a flourish
The report's narrative-of-discovery device (§7: *naive idea → why it disappoints → the
better idea → why it works → the cost it carries*) is not one technique among many here —
it **is the thesis**. The whole document descends from one real false start: the original
question *"at what N does hierarchical decomposition beat flat?"*, the gate-count analysis
showing hierarchical-Merkle is ~1.5% **worse** (the crossover does not exist), and the
reframe that negative result forced. Use the device at three scales: the **whole thesis**
(Ch 1 trailer → Ch 8 film), each **chapter**, and each **non-trivial design decision**.
Honesty about the dead end is the source of both rigor and charm; do not sand it down into
"here is the finished framework."

### 14.2 The dual register, in project nouns (extends §6)
- **Formal layer (precise, no wit inside):** circuit definitions; the four CONSTRAINT
  GROUPs (range / permutation / edge-cost / threshold); soundness statements and the
  per-variant ε-bounds (ε ≤ ε_SNARK + ε_FS + ε_SZ + ε_bind); measured numbers
  (gate counts, times, bytes, MB); the public/private input partition of every circuit.
- **Warm layer (personality):** the discovery narrative (the cancellation); chapter
  openers/bridges; the motivation (Sudoku → logistics, Ch 1); section titles; the honest
  caveats.

### 14.3 Named handles — our "villains" (this is the §7/§12 "name your villains" device)
Define each **once**, then reuse the exact phrase (notation discipline, §5, applied to
*concepts*). Do not invent decorative synonyms; do not let them drift. The canonical set:
- **the dualism** — decomposition buys no ZK speedup, only parallelism / per-prover memory.
- **the stitching tax** — the cost of stitching independent sub-proofs back into one
  statement; one cost felt along three angles (what the seam leaks / the verifier's burden /
  the bookkeeping outside the proofs), whose severity is *not* fixed but set by two decisions
  (*where* the stitching is enforced × *what it is made of*) — the three angles ease or bite
  together as those decisions change. **Terminology rule:** use *stitch / stitching* for
  the recombination act, and reserve *binding / hiding* exclusively for commitment-scheme
  properties — they must never collide. (The internal planning docs still call this "the
  binding tax"; in thesis prose it is the *stitching tax*.)
- **the fingerprint lever** — sort → grand-product+Fiat–Shamir; an O(1) distributable
  partition fingerprint bought at the price of a soundness flavour.
- **the pick-two triangle** — P (parallel + low per-prover memory) / V (O(1) verifier) /
  C (low prover overhead); each architecture gives two; folding is the empty corner.
- **the forbidden diagonal** — the comparison that changes two variables at once; naming it
  off-limits is half the methodology.
- **the controlled walk** — Ch 9's one-variable-per-step march down the stitching axis.
- **the trailer/film split** — Ch 1 previews (≈1 page), Ch 8 proves in full; same fact,
  two depths, cross-referenced.

These coinages are *load-bearing*, so they survive the "minimal metaphor" rule (§6/§12):
the rule forbids decorative or extended metaphor, **not** these named handles.

### 14.4 Self-containment for ZK (the §1/§5 first-principles contract)
Source A builds optimization from scratch before Set-Covering; we build **zero-knowledge
from scratch** before TSP. Chapter 1 motivates intuitively (the paradox; *prove without
revealing*), Chapter 2 defines formally (interactive proofs; completeness / soundness /
zero-knowledge; Fiat–Shamir; arithmetic circuits; UltraHonk; Poseidon2; Merkle). The
boundary is strict: **§1.1 makes the reader *want* ZK and *believe* it is possible; Ch 2
makes them *understand* it.** No formalism in Ch 1; forward-reference Ch 2 instead.

### 14.5 Code → pseudocode convention (the §10 "abbreviate code" rule, for Noir)
Full Noir source lives in **Appendix A**; the body shows **high-level pseudocode** that
exposes the *logic and constraint mapping*, not the syntax. Conventions:
- `require P` for an assertion/constraint (a relation the witness must satisfy), **not**
  `assert` — a circuit constraint is declarative, not control flow.
- `x ← e` for a witness assignment (`let`); omit type-casts (`as Field`, u32/u64) as noise.
- State the public/private split as a **signature** (`public:` / `private:`), since that is
  the privacy surface and a load-bearing object in this thesis.
- Abstract gadgets to named operators: `H(·)` for Poseidon2, `sort(·)`, `∏`. Put the
  gadget's *cost* in a complexity table or prose, never inside the listing.
- Say you are abbreviating and why (per §10), and cross-reference the appendix listing.

### 14.6 Results-reading + sanity-check the metric (extends §10)
Read every figure/table as: (1) what varies and what is measured, (2) the trend in plain
words, (3) interpretation + caveat. The metric vocabulary is fixed: `circuit_size` (gates),
`witness_s`, `prove_s`, `verify_s`, `proof_bytes`, `peak_mb`; note the deterministic→noisy
funnel (gate counts are exact; wall-clock is variance-prone — report runs/means). Our
signature *"sanity-check what the number means"* moment (the report's analogue: *relative
gaps are highly sensitive to scale*) is **ACIR opcodes as a misleading metric** — the
N≈30 vs N≈175 discrepancy that shows opcode counts do not track UltraHonk gates. Always
ask what a number physically *is* before trusting it.

### 14.7 The honesty refrains (the §3 "admit the cost" rule, made concrete)
Repeat these, plainly, wherever they apply — they are the project's standing caveats:
- **Total work is conserved** — hierarchical never beats flat on *total* gates; the win is
  parallelizability of the same work (the dualism).
- **A++ is never sold on hiding** — it still leaks (the P_i oracle); it earns its place on
  surface + soundness + the recursion bridge.
- **"Perfect hiding" is *structural*, not information-theoretic** — UltraHonk-ZK is
  computational/statistical and identical across all variants; it is not a discriminator.
- **The K× parallel speedup is projected, not yet measured** — pending the isolation
  benchmark; state this every time the speedup is invoked.

### 14.8 Boxed, witty-titled artifacts (the §5 / "Holey Grail" device)
Use a named callout box for each load-bearing formal object: the **TSP-ZKP problem
statement** (a "Holey Grail"-style title is welcome on the box; the statement inside stays
exact), the **binding-tax definition**, and each **soundness ε-bound theorem**. Wit on the
lid, precision in the box.

### 14.9 Author L1 guard (the §11 calque list is *your own* habits)
The Italian source is the author's prior work, so §11 is not hypothetical — it is a list of
**your** default reflexes in English. Actively counter, every draft: *Di conseguenza* →
rotate connectives; *Infatti/In effetti* → drop most; *Naturalmente* → usually delete;
heavy nominalizations → verbs; long periodic run-ons → split + alternate long/short;
impersonal *si dimostra* → active *we show*; *permette di* → *lets us / makes it possible
to*. Keep the Italian *gifts*: didactic patience, intuition-first ordering, the "we"
companion voice, define-then-use, explicit property-checking at the extremes.

### 14.10 Locked conventions
- **American spelling** ("optimization", "behavior", "modeling", "analyze", "skeptical",
  "favor", "center") — the author's natural register and the field norm; standardize
  throughout and enforce with a spell-check pass. Note `-ize`/`-ization` is valid in both
  standards, so most technical vocabulary is unaffected; the live tells are `-or` vs
  `-our`, `-er` vs `-re`, single vs double `-l-`, and `analyze`/`skeptical`.
- **"we"** for reasoning; **"you"** only for operational instructions (build / prove /
  verify / run commands).
- **N, K, M, DEPTH, T, c, X, P_i, h_i, C_i, r** — introduce at first use, reuse verbatim
  (candidate Appendix D notation index).

### 14.11 Draft output format (how prose is delivered in chat)
When delivering thesis prose in a session, present it so it is trivial to copy:
- Fence the prose with a line containing only `===` **before** and **after** the passage;
  nothing but the draft sits between the fences.
- Render the prose itself in *italics*.
- Use `---` for em-dashes, with **no surrounding spaces** (`word---word`, not `word --- word`).
- Keep all commentary, notes, and questions **outside** the `===` fences.
