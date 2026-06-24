// =============================================================================
// _stubs.typ — placeholder labels for not-yet-written sections.
//
// WHY: chapters are drafted out of order, so a chapter often forward-references a
// section (`@sec:x`) that does not exist yet. An unresolved `@ref` is a Typst
// compile error. This file registers a placeholder label for each such target so
// the document keeps compiling, and serves as the running list of "labels we owe".
//
// HOW TO USE — in the master document (main-matter.typ), near the top:
//
//     #import "/thesis/chapters/_stubs.typ": setup
//     #show: setup            // must be a `show: setup`, NOT `#include`
//
// (A `show ref` rule does not propagate through `#include`, so the rule lives in
// `setup` and is applied document-wide via `#show: setup`.)
//
//   - When you reference a not-yet-written section, add a `stub(...) <sec:x>` line
//     in `setup` below.
//   - When you DRAFT that section and give it its real `<sec:x>` label, DELETE its
//     stub line here. You cannot forget: a leftover stub makes the label appear
//     twice, and Typst errors with "label occurs multiple times".
//
// RENDERING: a `@ref` whose only target is a stub renders as bold red
// "[TBD: <description>]" so unresolved forward-refs are obvious in the output.
// Once the real section exists, the ref renders normally.
// =============================================================================

#let stub(desc) = metadata(desc)

#let setup(body) = {
  // --- LABELS WE OWE (delete each line when its section defines the label) ----
  // Ch 2 — Background sections (the chapter exists as a placeholder; its
  // sections are not written yet). The chapter label <chap:background> is
  // already defined by chapter2.typ, so it is NOT stubbed here.
  [#stub("§2.x / §3.x — factorial oracle / brute-force baseline")<sec:factorial>]

  // Ch 3 — Evaluation methodology / metrics (not yet migrated).
  [#stub("§3.x — fairness: privacy-equalized comparison conditions")<sec:fairness>]

  // Ch 6 — Results sections not yet drafted (delete each when its section lands).
  // §6.1 (fairness controls) and §6.2 (flat baseline, <sec:flat-eval>) are drafted.
  [#stub("§6.8 — the frontier figure")<sec:frontier-figure>]
  [#stub("Fig — mechanism witness-time plot")<fig:mech-witness-plot>]

  // Appendix — full per-construction negative-test dump (not yet written).
  [#stub("Appendix — full negative-test battery")<app:negative-tests>]

  // Ch 7 — Conclusion (not yet migrated).
  [#stub("§7.x — future work")<sec:future-work>]

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
