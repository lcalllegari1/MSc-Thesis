#import "theme/colors.typ": colors 
#import "theme/headings.typ" 
#import "theme/marginals.typ" 

#let compose(
  front-matter, 
  main-matter, 
  appendices,
  references,
) = {

  // ===== GLOBALS =====

  set page(
    paper: "a4",
    flipped: false,
    margin: (
      inside: 4.5cm,
      outside: 3.5cm,
      top: 4.5cm,
      bottom: 3.5cm,
    ),
    binding: left,
    columns: 1,
    fill: none,
    background: none,
    foreground: none,
    numbering: none,
    supplement: [Page],
    header-ascent: 20%,
    footer-descent: 20%,
    header: context marginals.get-header(),
    footer: context marginals.get-footer(),
  )

  set text(
    size: 12pt,
    font: "Libertinus Serif",
    lang: "en",
    region: "US",
  )
  
  set par(
    leading: 0.8em,
    spacing: 0.8em,
    justify: true,
    justification-limits: (
      spacing: (
        min: 66.67% + 0pt, 
        max: 150% + 0pt
      ), 
      tracking: (
        min: -0.01em, 
        max: 0.02em
      ), 
    ),
    linebreaks: "optimized",
    first-line-indent: (amount: 1.5em, all: false),
  )

  // HEADINGS 
  show heading: set text(font: "Libertinus Sans")

  show heading.where(level: 1): chapter => {
    {
       set page(header: none, footer: none)
       pagebreak(weak: true, to: "odd")
    }
    v(2cm)
    if chapter.numbering == none {
      headings.plain(chapter)
    } else {
      headings.numbered(chapter)
    }
    v(1.5em)
  }

  show heading.where(level: 2): section => {
    set text(size: 16pt)
    block(
      above: 2em,
      below: 1em
    )[
      #text(
        numbering(
          section.numbering,
          ..counter(heading).at(here())
        ),
        fill: colors.primary
      )
      #h(0.5em)
      #text(section.body)
    ]
  }

  show heading.where(level: 3): section => {
    set text(size: 14pt)
    block(
      above: 1.5em,
      below: 1em
    )[
      #text(
        numbering(
          section.numbering,
          ..counter(heading).at(here())
        ),
        fill: colors.primary
      )
      #h(0.5em)
      #text(section.body)
    ]
  }

  // FIGURES AND TABLES 

  let custom-caption(caption) = {
    set text(size: 11pt)
    set par(leading: 0.5em, spacing: 0.5em)
    layout(size => context {
      let prefix = [#caption.supplement~#numbering(
        marginals.prev-chapter().numbering + "." + caption.numbering,
        ..((counter(heading).at(here()).first(), )) + caption.counter.get()
      )]
      let prefix-size = measure(prefix + caption.separator)
      
      let full-caption = prefix + caption.body
      let caption-size = measure(full-caption)

      if caption-size.width < size.width { 
        align(
          center,
          text(
            prefix, fill: colors.primary, font: "Libertinus Sans"
          ) + h(1pt) + caption.separator + caption.body
        )
      } else {
        grid(
          columns: (prefix-size.width + 1pt + measure(caption.separator).width, 1fr),
          rows: 1,
          align: left,
          column-gutter: -3pt,
        )[
          #text(
            prefix, fill: colors.primary, font: "Libertinus Sans"
          )#h(1pt)#caption.separator
        ][
          #caption.body
        ]
      }
    })
  }
  
  show figure: set block(above: 2em, below: 2em)
  set figure(gap: 1.5em)

  show figure.where(kind: image): image => {
    set figure.caption(position: bottom)
    show figure.caption: caption => custom-caption(caption)
    image
  }

  show figure.where(kind: "listing"): code => {
    set figure.caption(position: bottom)
    show figure.caption: caption => custom-caption(caption)
    code
  }

  show figure.where(kind: table): table => {
    set figure.caption(position: top)
    show figure.caption: caption => custom-caption(caption)
    table
  }

  show ref: ref => {
    if ref.element != none and ref.element.func() == figure {
      link(ref.element.location(), 
        ref.element.supplement + " " + 
        numbering(
          marginals.prev-chapter().numbering + "." + ref.element.numbering,
          ..counter(heading.where(level: 1)).get(),
          ..ref.element.counter.at(ref.element.location())
        )
      )
    } else {
      ref
    }
  }

  // BULLET LIST STYLING
  set list(
    marker: (
      text(sym.diamond.filled, fill: colors.primary),
      text(sym.diamond.stroked.medium, fill: colors.primary),
      text(sym.miny, fill: colors.primary)
    ),
    spacing: 0.8em,
    indent: 1em,
    body-indent: 8pt
  )
  
  
  show list: set block(above: 1.5em, below: 1.5em)
  show list: it => {
    set list(indent: 0em)
    it
  }

  // EQUATIONS
  show math.equation: set text(font: "Libertinus Math")
  show math.equation: set block(above: 1.5em, below: 1.5em)

  set math.equation(
    block: true, 
    supplement: [],
    number-align: right,
    numbering: n => {
      set text(font: "Libertinus Sans")
      numbering("(1.1)", counter(heading).at(here()).first(), n)
    }
  )

  // RAW

  show raw: set text(font: "JetBrains Mono")
  
  // ===== FRONT MATTER =====

  set page(numbering: "i")

  front-matter

  show outline: set heading(outlined: true)
  show outline.entry: set text(font: "Libertinus Sans")

  // TABLE OF CONTENTS STYLING
  set outline.entry(fill: repeat([.], gap: 0.3em))
  
  show outline.entry.where(level: 1): chapter => {
    set block(above: 1.5em, below: 0.5em)
    set text(size: 14pt, weight: "bold", fill: colors.primary)
    link(
      chapter.element.location(),
      chapter.indented(
        chapter.prefix() + if chapter.prefix() != none {
          // [.]
        }, chapter.element.body + h(1fr) + chapter.page(),
        gap: 8pt,
      )
    )
  }

  show outline.entry.where(level: 2): section => {
    set block(above: 0.7em, below: 0.5em)
    set text(size: 12pt, fill: black)
    link(
      section.element.location(),
      section.indented(
        section.prefix(), section.inner(),
        gap: 8pt,
      )
    )
  }

  show outline.entry.where(level: 3): subsection => {
    set block(above: 0.7em, below: 0.5em)
    set text(size: 12pt, fill: black)
    link(
      subsection.element.location(),
      subsection.indented(
        subsection.prefix(), subsection.inner(),
        gap: 8pt,
      )
    )
  } 
  
  outline() // TABLE OF CONTENTS
 
  // LIST OF FIGURES & TABLES STYLING

  let custom-entry(entry, kind) = {
    let number = numbering(
      query(
        selector(
          heading.where(level: 1)
      ).before(entry.element.location())).last().numbering + "." + entry.element.numbering,
      ..((counter(heading).at(entry.element.location()).first(), ) + counter(figure.where(kind: kind)).at(entry.element.location()))
    )

    let prefix = entry.element.supplement + " " + number + h(1pt)

    let prefix-size = measure(prefix)

    grid(
      columns: (prefix-size.width + measure(entry.element.caption.separator).width, 1fr, 8%),
      rows: 1,
      align: left,
    )[
      #link(
        entry.element.location(),
        text(fill: colors.primary, prefix) + entry.element.caption.separator 
      )
    ][
      #set par(justify: true)
      #set text(font: "Libertinus Serif")
      #entry.element.caption.body
    ][
      #align(
        bottom + right, 
          link(
          entry.element.location(),
          entry.page()
        )
      )
    ]    
  }

  show outline.entry: it => custom-entry(it, image)
  outline(target: figure.where(kind: image), title: [List of Figures])

  show outline.entry: it => custom-entry(it, table)
  outline(target: figure.where(kind: table), title: [List of Tables])

  show outline.entry: it => custom-entry(it, "listing")
  outline(target: figure.where(kind: "listing"), title: [List of Listings])
  
  // ===== MAIN MATTER =====
  
  set page(numbering: "1")
  set heading(numbering: "1.1.1")

  counter(page).update(0)
  
  main-matter

  // ===== APPENDICES =====

  set heading(numbering: "A.1.1")

  counter(heading).update(0)

  appendices

  // ===== REFERENCES =====

  references
}