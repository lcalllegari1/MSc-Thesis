// Lightweight numbered theorem-like environments for the thesis.
// Built on ctheorems; plain (non-boxed) style to match the thesis aesthetic.
// Each kind keeps its own counter and numbers within the enclosing chapter /
// appendix (base_level: 1), e.g. "Theorem A.1", "Lemma A.3".
//
// Apply the show rule once where these are used (see include/appendices.typ):
//   #import "/thesis/chapters/_theorems.typ": *
//   #show: thmrules.with(qed-symbol: $square$)

#import "@preview/ctheorems:1.1.3": *

// numbering "A.1": the level-1 heading counter renders as the appendix letter
// (these environments are currently used only in the appendix). `numbering` is a
// parameter of the environment closure, so it is preset with `.with(...)`.
#let theorem    = thmplain("theorem",    "Theorem",    base_level: 1).with(numbering: "A.1")
#let definition = thmplain("definition", "Definition", base_level: 1).with(numbering: "A.1")
#let lemma      = thmplain("lemma",      "Lemma",      base_level: 1).with(numbering: "A.1")
#let assumption = thmplain("assumption", "Assumption", base_level: 1).with(numbering: "A.1")
#let proof      = thmproof("proof",      "Proof")
