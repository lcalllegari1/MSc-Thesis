"""
pipeline/plot_recursion_lines.py -- plot.py with a recursion-aware palette.

Same line charts as pipeline/plot.py (one line per variant, mean +/- std over
runs, linear + log-log, grid or --separate), but with a colour/marker scheme
designed for the recursion component variants emitted by
`aggregate_recursion.py --split-components`:

  * COLOUR is keyed by K  -- every series for the same K (combined, _seg, _outer)
    shares one hue, so the eye groups by K.  Colours are pinned to the K *value*
    (K=2 blue, K=4 orange, K=8 green, ...), stable across figures regardless of
    which Ks are present.
  * MARKER + LINESTYLE are keyed by the component -- combined / seg / outer / glue
    -- so within one K the three series are told apart by glyph, not by a
    confusingly-similar shade.

      combined (full variant)  o  solid
      _seg                     s  dashed
      _outer                   ^  dotted
      _glue (hier reuse)       D  dash-dot

Input is the AGGREGATED CSV (e.g. results/recursive_par.csv produced with
--split-components), the same input pipeline/plot.py takes -- this is the
line-chart counterpart of pipeline/plot_recursion_stack.py (which takes the raw
CSV and draws component bars).

It reuses plot.py's plotting wholesale (so every flag below is plot.py's:
--csv --out --metrics --variants --min-n --max-n --separate --format --legend
--no-title --title --dpi) and only overrides the per-variant style + legend label.

Note: plot ONE aggregation mode per figure.  If you used --mode-in-name (variants
like recursion_k2_parallel vs _total), filter to one with e.g.
--variants 'recursion_*_parallel'; the palette keys on K + component only, so the
two modes of one (K, component) would otherwise draw identical styles.

Usage:
    PY=/home/callexyz/anaconda3/envs/zk-tsp/bin/python
    # full + components, all sharing a hue per K:
    $PY pipeline/plot_recursion_lines.py --csv results/recursive_par.csv \\
        --out plots/recursion_lines --metrics circuit_size prove_s peak_mb

    # just the seg-vs-outer split for K in {2,4,8}:
    $PY pipeline/plot_recursion_lines.py --csv results/recursive_par.csv \\
        --variants 'recursion_k*_seg' 'recursion_k*_outer' \\
        --out plots/recursion_split --separate --format pdf --no-title
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib.colors as mcolors

# plot.py lives in the same directory; import it and override its style hooks.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plot as P  # noqa: E402

# ── Palette ───────────────────────────────────────────────────────────────────
# Colour pinned to the K VALUE (not to plot order), so a K keeps its hue across
# every figure.  CANON_K[i] -> K_COLORS[i]; unknown Ks fall back to a name hash.
CANON_K  = [1, 2, 4, 8, 16, 32, 3, 6, 12, 24]
K_COLORS = [
    "#6b7280",  # 1  (grey -- the off-frontier single-segment diagnostic)
    "#1d4ed8",  # 2  blue
    "#ea580c",  # 4  orange
    "#059669",  # 8  green
    "#9333ea",  # 16 purple
    "#dc2626",  # 32 red
    "#0891b2",  # 3  cyan
    "#b45309",  # 6  amber
    "#4d7c0f",  # 12 olive
    "#be185d",  # 24 magenta
]
# component -> (marker, linestyle)
COMPONENT_STYLE = {
    "combined": ("o", "-"),
    "seg":      ("s", "--"),
    "outer":    ("^", ":"),
    "glue":     ("D", "-."),
}

_MODE_RE = re.compile(r"_(parallel|total)$")
_COMP_RE = re.compile(r"_(seg|outer|glue)$")


def parse_variant(variant: str):
    """Return (k:int|None, component:str, mode:str|None) from a variant name."""
    v = variant
    mode = None
    m = _MODE_RE.search(v)
    if m:
        mode = m.group(1)
        v = v[:m.start()]
    component = "combined"
    c = _COMP_RE.search(v)
    if c:
        component = c.group(1)
        v = v[:c.start()]
    k = None
    km = re.search(r"_k(\d+)$", v)
    if km:
        k = int(km.group(1))
    elif v.endswith("1seg"):
        k = 1
    return k, component, mode


def _color_for_k(k):
    if k in CANON_K:
        return K_COLORS[CANON_K.index(k) % len(K_COLORS)]
    # Unknown / non-recursion variant: fall back to plot.py's stable name hash.
    return None


def recursion_style(variant: str) -> dict:
    k, component, _mode = parse_variant(variant)
    color = _color_for_k(k)
    if color is None:                       # not a recursion variant -> default
        return P._orig_stable_style(variant)
    marker, ls = COMPONENT_STYLE.get(component, ("o", "-"))
    rgb    = mcolors.to_rgb(color)
    ecolor = mcolors.to_hex(tuple(c * 0.5 + 0.5 for c in rgb))
    return {"color": color, "marker": marker, "ls": ls, "ecolor": ecolor}


def recursion_display(variant: str) -> str:
    k, component, mode = parse_variant(variant)
    if k is None:
        return P.DISPLAY_NAMES.get(variant, variant)
    head = "1-seg" if k == 1 else f"K={k}"
    label = head if component == "combined" else f"{head} {component}"
    if mode:
        label += f" ({mode})"
    return label


def main():
    # Keep a handle to the original style so non-recursion variants still work.
    P._orig_stable_style = P._stable_style
    P._stable_style = recursion_style
    P._display = recursion_display
    P.main()


if __name__ == "__main__":
    main()
