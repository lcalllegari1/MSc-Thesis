#import "colors.typ": colors

#let is-odd-page() = {
  calc.odd(here().page())
}

#let get-page-number() = {
  text(counter(page).display(), weight: "bold", fill: colors.primary)
}

#let next-chapter() = {
  query(
    selector(
      heading.where(level: 1)
    ).after(here())
  ).first(default: none)
}

#let prev-chapter() = {
  query(
    selector(
      heading.where(level: 1)
    ).before(here())
  ).last(default: none)
}

#let next-section() = {
  query(
    selector(
      heading.where(level: 2)
    ).after(here())
  ).first(default: none)
}

#let prev-section() = {
  query(
    selector(
      heading.where(level: 2)
    ).before(here())
  ).last(default: none)
}

#let get-section(section) = {
  if section != none {
    numbering(
      section.numbering,
      ..counter(heading).at(section.location())
    )
    h(0.5em)
    upper(
      text(section.body)
    )
  }
  h(1fr)
  get-page-number()
  v(-5pt)
  line(length: 100%)
}

#let get-chapter(chapter) = {
  get-page-number()
  h(1fr)
  if chapter != none {
    if chapter.numbering != none {
      [CHAPTER ]
      numbering(
        chapter.numbering,
        ..counter(heading).at(chapter.location())
      )
      [.]
    }
    h(0.5em)
    upper(
      text(chapter.body)
    )
  }
  v(-5pt)
  line(length: 100%)
}

#let left-header() = {
  get-chapter(prev-chapter())
}

#let right-header() = {
  if next-section() != none and next-section().location().page() == here().page() {
    get-section(next-section())
  } else {
    if (
      prev-chapter() != none and
      prev-section() != none and
      prev-section().location().page() >= prev-chapter().location().page()
    ) {
      get-section(prev-section())
    } else {
      get-section(none)
    }
  }
}

#let get-header() = {
  set text(font: "Libertinus Sans")
  if next-chapter() != none and next-chapter().location().page() == here().page() {
    return
  }

  if is-odd-page() {
    right-header()
  } else {
    left-header()
  }
}

#let get-footer() = {
  set text(font: "Libertinus Sans")
  if prev-chapter() != none and prev-chapter().location().page() == here().page() {
    align(
      center,
      get-page-number()
    )
  }
}