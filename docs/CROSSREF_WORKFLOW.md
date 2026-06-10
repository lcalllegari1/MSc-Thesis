# Cross-Reference Workflow

Operating manual for managing labels and forward/back references across the thesis,
which is drafted **out of order** (Ch 4 → Ch 5 → Ch 2 → …). The aim: keep the document
compiling at all times, never lose track of an intended link, and make the final
cross-reference pass *verification*, not rediscovery.

If you read one thing: the **ledger** `docs/CROSSREFS.md` is the source of truth; the
**stub file** keeps it compiling; the **checker** keeps it honest.

---

## The three pieces

| Piece | File | Role |
|---|---|---|
| **Ledger** | `docs/CROSSREFS.md` | Source of truth. Label registry (✅ defined / 🔲 stub / ⚠️ attention) + the *intended* cross-references (links we've decided on, wired or not) + what each unwritten section owes. |
| **Stub file** | `thesis/drafts/_stubs.typ` | Placeholder labels so `@ref` to an unwritten section still compiles. A ref to a stub renders red `[TBD: …]`. Also the running "labels we owe" list. |
| **Checker** | `pipeline/check_refs.py` | Mechanical report: dangling / stub-covered / duplicate / orphan refs, plus a sync check against the ledger. |

---

## One-time setup (master document)

A `show ref` rule does **not** propagate through `#include`, so the stub mechanism is
applied via a wrapper. In the master document, near the top:

```typst
#import "drafts/_stubs.typ": setup
#show: setup
```

If your template already defines its own `show ref` rule, **merge** the stub branch from
`_stubs.typ` into it rather than applying a second `#show: setup`.

---

## The four everyday actions

### 1. You write a reference to a section that doesn't exist yet
Use the **real** label in prose — e.g. `@sec:permcheck` — never a coarse `@chap:` stand-in.
Then register it in two places:
- `thesis/drafts/_stubs.typ` → add a line inside `setup`:
  `[#stub("§4.2 — permutation-mechanism study")<sec:permcheck>]`
- `docs/CROSSREFS.md` §1 → add a `🔲 stub` row (label, home section, purpose, who refs it).

It now compiles; the ref renders red `[TBD: §4.2 …]` so the gap is visible in the PDF.

### 2. You draft the section that a stub was standing in for
- Give its heading the label: `#section([Permutation …], label: <sec:permcheck>)`.
- **Delete its stub line** from `_stubs.typ`. (If you forget, Typst errors *"label occurs
  multiple times"* — the forcing function. You can't ship a stale stub.)
- Flip its row in `CROSSREFS.md` §1 from 🔲 → ✅.
- Check `CROSSREFS.md` §2 for any intended links involving this section and **wire them now**
  (this is where you add the back-references you decided on earlier).

### 3. You decide two passages should be linked
Add a row to `CROSSREFS.md` **§2 (Intended cross-references)** *immediately*, even if one or
both ends aren't written yet. Mark `Wired?` as 🔲. This is the single most important habit —
it's the only record of links that live in intent rather than in the text, and it's what makes
the final pass tractable. Wire the actual `@ref` when both ends exist; flip `Wired?` to ✅.

### 4. You finish a chapter
1. Update `CROSSREFS.md` §1 (new labels) and §2 (new intended links).
2. Delete from `_stubs.typ` any stubs this chapter now defines.
3. Run the checker (below). Resolve every **DANGLING** and **DUPLICATE**.
4. Read the chapter once against `CROSSREFS.md` §2 — does every decided link exist in the text?

---

## Running the checker

```bash
python3 pipeline/check_refs.py --ledger docs/CROSSREFS.md
```

Reads every `thesis/drafts/*.typ` (stripping comments and raw code blocks first, so
doc-comment examples and operators like `i < j` aren't miscounted). Categories:

| Category | Meaning | Action |
|---|---|---|
| **DANGLING** | `@ref` with no label anywhere | **Must fix** — this is a compile error. Add a stub or define the section. |
| **STUB-COVERED** | `@ref` resolved only by a stub | Informational — the list of sections still owed. |
| **DUPLICATE** | a label defined more than once | **Must fix** — usually a leftover stub beside a now-real label; delete the stub. |
| **ORPHAN** | a real label nothing references | Informational — usually fine (most headings aren't referenced); occasionally a hint that a planned back-ref was forgotten. |
| **ledger sync** | labels in `.typ` not in the ledger, and vice-versa | Keep both empty — document new labels in the ledger; remove ledger typos / future-only labels. |

Exit code is **0** when there are no DANGLING and no DUPLICATE; **1** otherwise (so it can
gate a commit or CI step). STUB-COVERED and ORPHAN never fail the run.

---

## Conventions

- **Label form:** `<prefix:name>`, prefix ∈ `chap` / `sec` / `sub` / `fig` (extend as
  needed: `tab`, `eq`, `app`). The colon is what lets the checker tell labels from `< N`.
  Names are lower-case, hyphen-separated (`flat-pairwise`, `witness-inversion`).
- **Always reference with the real `@sec:` label**, never a `@chap:` placeholder. Compile
  safety comes from the stub, not from coarsening the reference.
- **One source of truth:** the ledger. Don't copy its tables into other docs — point to it
  (`Thesis_Outline.md` and `DOCS_INDEX.md` already do).

---

## Gotchas

- **`#show: setup`, not `#include`.** A `show ref` rule set inside an included file applies
  only within that file; the wrapper is why the rule reaches the whole document.
- **"cannot reference metadata"** on a `@ref` means the `show: setup` wrapper isn't active
  (or the label has no stub and no real target). Check the master wiring.
- **"label occurs multiple times"** is *intended* when a stub outlives its real section —
  delete the stub.
- **Bare heading refs** ("cannot reference heading without numbering") come from a document
  with no `#set heading(numbering: …)`. The real template sets numbering; a minimal test
  harness must add it.
- Verified on **Typst 0.14.2**. If a future Typst version changes `query`/`metadata`/show-rule
  semantics, the suspect lines are `query(it.target)` and `els.first().value` in `_stubs.typ`.

---

## Quick reference

```bash
# integrity + ledger sync report
python3 pipeline/check_refs.py --ledger docs/CROSSREFS.md
```

**Per chapter, on completion:** update ledger §1/§2 → delete resolved stubs → run checker
(fix DANGLING + DUPLICATE) → read the chapter against ledger §2.

**Files:** ledger `docs/CROSSREFS.md` · stubs `thesis/drafts/_stubs.typ` · checker
`pipeline/check_refs.py` · this manual `docs/CROSSREF_WORKFLOW.md`.
