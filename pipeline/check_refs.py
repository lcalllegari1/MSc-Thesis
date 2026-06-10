#!/usr/bin/env python3
"""
check_refs.py — cross-reference integrity report for the Typst thesis drafts.

Scans the Typst files for label definitions (<sec:x>) and references (@sec:x),
distinguishes real definitions from placeholders in _stubs.typ, and reports:

  DANGLING      @ref with no matching <label> anywhere        -> Typst compile error
  STUB-COVERED  @ref resolved only by a stub in _stubs.typ    -> section still owed
  DUPLICATE     a label defined more than once                -> e.g. leftover stub
  ORPHAN        a real <label> that nothing references        -> maybe a missing link

Optionally cross-checks the label set against the registry table in
docs/CROSSREFS.md (--ledger), to keep the ledger in sync with the actual files.

Comments (// and /* */) and raw code blocks (```...```) are stripped first, so
example labels inside doc-comments and operators like `i < j` are not miscounted.

Exit code: 0 if there are no DANGLING refs and no DUPLICATE labels; 1 otherwise.
(STUB-COVERED and ORPHAN are informational and do not fail the run.)

Usage:
  python3 pipeline/check_refs.py [--dir thesis/drafts] [--ledger docs/CROSSREFS.md]
"""
import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

# Labels follow the convention <prefix:name>, prefix in {chap,sec,sub,fig,tab,eq,app,...}.
# Requiring the colon avoids matching `i < j`, `< N`, etc.
LABEL_RE = re.compile(r"<([a-z][a-z0-9]*:[a-z0-9][a-z0-9_-]*)>")
REF_RE   = re.compile(r"(?<![A-Za-z0-9_])@([a-z][a-z0-9]*:[a-z0-9][a-z0-9_-]*)")

RAW_RE    = re.compile(r"```.*?```", re.DOTALL)   # raw/code blocks
BLOCKC_RE = re.compile(r"/\*.*?\*/", re.DOTALL)   # /* block comments */
LINEC_RE  = re.compile(r"(?<!:)//[^\n]*")         # // line comments (but not ://)

STUB_FILE = "_stubs.typ"


def strip(text: str) -> str:
    text = RAW_RE.sub("", text)
    text = BLOCKC_RE.sub("", text)
    text = LINEC_RE.sub("", text)
    return text


def scan(files):
    defs = defaultdict(list)  # label -> [(filename, is_stub)]
    refs = defaultdict(list)  # label -> [filename]
    for f in files:
        is_stub = f.name == STUB_FILE
        clean = strip(f.read_text(encoding="utf-8"))
        for m in LABEL_RE.finditer(clean):
            defs[m.group(1)].append((f.name, is_stub))
        for m in REF_RE.finditer(clean):
            refs[m.group(1)].append(f.name)
    return defs, refs


def ledger_labels(ledger_path: Path):
    # Registry entries are table rows whose FIRST cell is a backticked label,
    # e.g.  | `<sec:x>` | ... |.  Take only that first label per table row, so
    # labels merely *mentioned* in prose or other cells are not miscounted.
    labels = set()
    cell = re.compile(r"`<([a-z][a-z0-9]*:[a-z0-9][a-z0-9_-]*)>`")
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("|"):
            m = cell.search(line)
            if m:
                labels.add(m.group(1))
    return labels


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="thesis/drafts", help="directory of .typ files")
    ap.add_argument("--ledger", default=None, help="path to docs/CROSSREFS.md to cross-check")
    args = ap.parse_args()

    root = Path(args.dir)
    files = sorted(root.glob("*.typ"))
    if not files:
        print(f"no .typ files under {root}", file=sys.stderr)
        return 2

    defs, refs = scan(files)

    def real_defs(label):
        return [d for d in defs.get(label, []) if not d[1]]

    def stub_defs(label):
        return [d for d in defs.get(label, []) if d[1]]

    dangling, stub_covered, ok = [], [], []
    for label in sorted(refs):
        if label not in defs:
            dangling.append(label)
        elif not real_defs(label):
            stub_covered.append(label)
        else:
            ok.append(label)

    duplicates = sorted(l for l, ds in defs.items() if len(ds) > 1)
    orphans = sorted(l for l in defs
                     if real_defs(l) and l not in refs)

    # ---- report -----------------------------------------------------------
    W = 64
    print("=" * W)
    print(f" cross-reference report  ({len(files)} files under {root})")
    print("=" * W)

    def section(title, items, fmt):
        print(f"\n{title}  [{len(items)}]")
        if not items:
            print("  (none)")
        for it in items:
            print("  " + fmt(it))

    section("DANGLING (no label at all -> COMPILE ERROR)", dangling,
            lambda l: f"@{l}  referenced in {', '.join(sorted(set(refs[l])))}")
    section("STUB-COVERED (section owed; resolves via _stubs.typ)", stub_covered,
            lambda l: f"@{l}  <- {', '.join(sorted(set(refs[l])))}")
    section("DUPLICATE labels (delete leftover stub / rename)", duplicates,
            lambda l: f"<{l}>  defined in " +
                      ', '.join(f"{n}{' [stub]' if s else ''}" for n, s in defs[l]))
    section("ORPHAN labels (defined, never referenced — maybe a missing link)", orphans,
            lambda l: f"<{l}>  in {defs[l][0][0]}")
    section("RESOLVED (real target exists)", ok, lambda l: f"@{l}")

    if args.ledger:
        lp = Path(args.ledger)
        if lp.exists():
            led = ledger_labels(lp)
            typ = set(defs) | set(refs)
            missing_from_ledger = sorted(typ - led)
            missing_from_typ = sorted(led - typ)
            print("\n" + "-" * W)
            print(f" ledger sync vs {lp}")
            section("  in .typ but NOT in ledger (document it)", missing_from_ledger, lambda l: f"<{l}>")
            section("  in ledger but NOT in any .typ (future / typo?)", missing_from_typ, lambda l: f"<{l}>")
        else:
            print(f"\n(ledger not found: {lp})", file=sys.stderr)

    print("\n" + "=" * W)
    bad = bool(dangling) or bool(duplicates)
    print(f" status: {'FAIL' if bad else 'ok'}   "
          f"dangling={len(dangling)} duplicate={len(duplicates)} "
          f"stub-covered={len(stub_covered)} orphan={len(orphans)}")
    print("=" * W)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
