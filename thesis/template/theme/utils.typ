#let inline(code) = text(
  font: "Libertinus Sans",
  fill: gray.darken(100%),
  code
)

#let ccal(ch) = text(font: "/assets/fonts/cmsy10", ch)
#let bigoh() = ccal("O")
#let lc(body) = text(fill: gray.darken(40%))[#body]   // gray comments / group headers
#let fn(name) = [#emph(name)#h(1pt)]

// =============================================================================
// _pseudocode.typ — one source of truth for how program objects render,
// in listings and in running prose alike.
//
// WHY: listings and prose both mention circuit objects (cycle, sorted, matrix,
// …) and relations over them (sorted[i] <= sorted[i+1]). Splicing these
// together with ad-hoc dollar signs (sorted$[$i$] <=$ sorted$[$i$+1]$) drifts
// and is unmaintainable. Instead, every such expression is written as ONE math
// span, and the identifiers are the let-bound symbols defined here. Typst math
// resolves multi-letter identifiers against the scope, so once `sorted` is
// bound below, `$sorted[i] <= sorted[i+1]$` renders the names upright in the
// listing face and the operators/indices as proper math — identically in a
// listing line and in prose.
//
// HOW TO USE — at the top of each chapter file that needs it:
//
//     #import "_pseudocode.typ": *
//
// CONVENTIONS (the whole style, in four rules):
//   1. Program arrays/scalars (multi-letter): the bound names below — upright,
//      listing face. In prose, mention them as `$sorted$`, never bare text.
//   2. Mathematical variables (i, j, v, p, N, T, X, h): bare math letters,
//      italic, as everywhere else in the document.
//   3. Operators always live inside the math span: =, <=, <, !=, dot,
//      arrow.l (assignment), pmod (the mod operator defined below).
//   4. Routine and circuit names stay in the existing devices: #fn[...] in
//      listings, #inline[...] in prose (they are code artifacts, not values).
//      Their argument lists are one math span: #fn[check_shuffle]$(cycle, sorted)$.
//
// To restyle every identifier at once, edit `pid` and nothing else.
// =============================================================================

// A program identifier: small caps, serif. The face is forced (not inherited)
// so the symbol renders identically everywhere it appears — in serif prose,
// where small caps make it unmistakably a program object rather than a word,
// and inside the sans listings. (Libertinus Sans has no small-caps feature, so
// inheriting would silently degrade to lowercase there.) Indices and operators
// around it stay italic math: $sorted[i] <= sorted[i+1]$.
#let pid(name) = smallcaps(text(font: "Libertinus Serif", name))

// The chapter-4 objects. Extend this list as later chapters introduce theirs.
#let cycle = pid("cycle")
#let sorted = pid("sorted")
#let invperm = pid("inv_perm")
#let idx = pid("idx")
#let matrix = pid("matrix")
#let visited = pid("visited")
#let total = pid("total")
#let lhs = pid("lhs")
#let rhs = pid("rhs")

// Index range for array declarations: $matrix[rng(0, N^2 - 1)]$
// renders as matrix[0 .. N²−1] with consistent spacing.
#let rng(a, b) = $#a med .. med #b$

// The mod operator with text-operator spacing: $(i+1) pmod N$.
#let pmod = math.op("mod")
