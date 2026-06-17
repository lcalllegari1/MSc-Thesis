#import "colors.typ": colors

#let chapter(title, label: none) = {
  counter(figure.where(kind: image)).update(0)
  counter(figure.where(kind: table)).update(0)
  counter(math.equation).update(0)
  [
    #heading(
      depth: 1,
      offset: 0,
      supplement: [Chapter],
      outlined: true,
    )[#title] #label
  ]
}

#let section(title, label: none) = {
  [
    #heading(
      depth: 2,
      offset: 0,
      supplement: [Section],
      outlined: true,
    )[#title] #label
  ]
}

#let subsection(title, label: none) = {
  [
    #heading(
      depth: 3,
      offset: 0,
      supplement: [Section],
      outlined: true,
    )[#title] #label
  ]
}


#let plain(chapter) = {
  align(
    right, 
    text(
      fill: colors.primary, 
      size: 28pt,
      chapter
    )
  )
}

#let numbered(chapter) = {
  grid(
    rows: 1,
    columns: (auto, 1fr, auto),
    align: horizon
  )[
    #box(
      text(
        numbering(
          chapter.numbering,
          ..counter(heading).at(here())
        ),
        size: 40pt,
        fill: white,
      ),
      fill: colors.primary,
      inset: 25%,
      width: 80pt,
    )
    #h(-5pt)
    #box(
      hide(
        text("", size: 40pt),
      ),
      fill: colors.secondary,
      width: 8pt,
      inset: 25%
    )
  ][][
    #text(
      chapter.body,
      fill: colors.primary,
      size: 28pt
    )
  ]
}