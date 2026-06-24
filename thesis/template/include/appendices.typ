#import "/thesis/chapters/_theorems.typ": *
#show: thmrules.with(qed-symbol: $square$)

#set heading(numbering: "A.1", supplement: [Appendix])
#counter(heading).update(0)

// Equations in the appendix number as (A.1), matching the appendix letter
// rather than the body's "(1.1)" chapter form.
#set math.equation(numbering: n => {
  set text(font: "Libertinus Sans")
  numbering("(A.1)", counter(heading).at(here()).first(), n)
})

#include "/thesis/chapters/appendix_soundness.typ"
#include "/thesis/chapters/appendix_negative_tests.typ"
