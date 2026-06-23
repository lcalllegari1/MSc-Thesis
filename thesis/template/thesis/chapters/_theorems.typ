// Lightweight numbered theorem-like environments for the thesis.
// Built on ctheorems; plain (non-boxed) style to match the thesis aesthetic.
// Each kind keeps its own counter and numbers within the enclosing chapter /
// appendix (base_level: 1), e.g. "Theorem A.1", "Lemma A.3".
//
// Apply the show rule once where these are used (see include/appendices.typ):
//   #import "/thesis/chapters/_theorems.typ": *
//   #show: thmrules.with(qed-symbol: $square$)

#import "@preview/ctheorems:1.1.3": *

#let theorem    = thmplain("theorem",    "Theorem",    base_level: 1)
#let definition = thmplain("definition", "Definition", base_level: 1)
#let lemma      = thmplain("lemma",      "Lemma",      base_level: 1)
#let assumption = thmplain("assumption", "Assumption", base_level: 1)
#let proof      = thmproof("proof",      "Proof")
