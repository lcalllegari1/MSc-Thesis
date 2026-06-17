// =============================================================================
// _stubs.typ — placeholder labels for not-yet-written sections.
//
// WHY: chapters are drafted out of order, so a chapter often forward-references a
// section (`@sec:x`) that does not exist yet. An unresolved `@ref` is a Typst
// compile error. This file registers a placeholder label for each such target so
// the document keeps compiling, and serves as the running list of "labels we owe".
//
// HOW TO USE — in the MASTER document, near the top:
//
//     #import "drafts/_stubs.typ": setup
//     #show: setup            // must be a `show: setup`, NOT `#include`
//
// (A `show ref` rule does not propagate through `#include`, so the rule lives in
// `setup` and is applied document-wide via `#show: setup`.)
//
//   - When you reference a not-yet-written section, add a `stub(...) <sec:x>` line
//     in `setup` below (and a row in docs/CROSSREFS.md).
//   - When you DRAFT that section and give it its real `<sec:x>` label, DELETE its
//     stub line here. You cannot forget: a leftover stub makes the label appear
//     twice, and Typst errors with "label occurs multiple times".
//
// RENDERING: a `@ref` whose only target is a stub renders as bold red
// "[TBD: <description>]" so unresolved forward-refs are obvious in the output.
// Once the real section exists, the ref renders normally.
//
// NOTE: if your template already sets a `show ref` rule, merge the branch below
// into it instead of applying a second `#show: setup`.
// =============================================================================

#let stub(desc) = metadata(desc)

#let setup(body) = {
  // --- LABELS WE OWE (delete each line when its section defines the label) ----
  // Keep in sync with docs/CROSSREFS.md (the cross-reference ledger).
  [#stub("Ch 2 — Background (chapter)")<chap:background>]
  [#stub("§2.2 — SNARKs / arithmetic circuits: fixed loop-free graph + offline memory checking (ROM)")<sec:snarks>]
  [#stub("§2.5 — TSP-ZKP problem statement / formulation (renumbered from §2.6, 2026-06-10)")<sec:prob-formulation>]
  [#stub("§2.1 — Fiat–Shamir transform / random-oracle challenge (+ Schwartz–Zippel)")<sec:fiat-shamir>]
  [#stub("§4.3 — matrix representation: flat-full vs Merkle")<sec:representation>]
  [#stub("§4.5 — the witness-time inversion")<sec:witness-inversion>]
  [#stub("Ch 5 — Hierarchical and Recursive Constructions (chapter)")<chap:hierarchical>]

  // A @ref to a stub-only label renders as a visible TBD marker; everything else
  // (real targets) renders normally. A leftover stub alongside a real target makes
  // the label ambiguous -> Typst errors, forcing you to delete the stub.
  show ref: it => {
    let els = query(it.target)
    let real = els.filter(e => e.func() != metadata)
    if real.len() == 0 and els.len() > 0 {
      text(fill: red, weight: "bold")[[TBD: #els.first().value]]
    } else {
      it
    }
  }

  body
}
