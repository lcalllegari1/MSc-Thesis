"""
pipeline/style.py  --  Single source of truth for the visual language of every
comparison figure in the thesis.

The thesis is organised as a 2-D grid: a *stitching regime* (how segments are
bound) crossed with a *fingerprint mechanism* (how the permutation is checked),
parameterised by the segment count K.  The figures should let the reader *see*
that grid, so the visual channels are assigned to the grid axes, never to
anything incidental:

    hue        = stitching regime   (flat / plain / committed / recursive)
    marker     = fingerprint mechanism   (sort = circle 'o', product = square 's')
    shade + linestyle = K (segment count)   (lighter / dashed as K grows)

Consequence — the grid discipline is legible at a glance:
    * moving along a column (change regime)      -> the HUE moves, marker fixed
    * moving along a row    (change mechanism)   -> the MARKER moves, hue fixed
    * the forbidden diagonal (change both)       -> hue AND marker both move

Canonical variant keys are "{regime}-{mechanism}", e.g. "committed-product".
A handful of flat representation-study variants (flat-full, flat-pairwise) are
NOT grid members; they live in a desaturated slate sub-palette so they read as
"baseline scaffolding" rather than as a regime.

Import this everywhere instead of hand-rolling colours:

    from style import style, color_for, marker_for, linestyle_for, display_name
    s = style("committed-product", k=4)
    ax.plot(xs, ys, color=s["color"], marker=s["marker"], ls=s["ls"], label=s["label"])
"""

import matplotlib.colors as mcolors

# ── Grid axis 1: stitching regime -> hue ─────────────────────────────────────
# Ordered along the stitching-tax axis (none -> plain glue -> committed glue ->
# recursive fold).  These four are well-separated and colour-blind-distinguishable
# (they are also the first four slots of plot.py's generic palette, so the two
# plotters agree).
REGIME_HUE = {
    "flat":      "#1d4ed8",   # blue   — monolithic, no stitching
    "plain":     "#047857",   # green  — composite, partition disclosed
    "committed": "#b45309",   # amber  — composite, partition hidden
    "recursive": "#7c3aed",   # purple — composite, folded to O(1) verifier
}

# ── Grid axis 2: fingerprint mechanism -> marker ─────────────────────────────
MECHANISM_MARKER = {
    "sort":    "o",   # circle  — dynamic-ROM permutation check
    "product": "s",   # square  — grand-product / fingerprint check
}

# ── Parameter axis: K (segments) -> shade (tint) + linestyle ─────────────────
# K=1 is the flat (un-segmented) case and uses the base saturated hue.
# For composite regimes, larger K reads lighter and more broken-up.
_K_TINT = {1: 0.0, 2: 0.0, 4: 0.21, 8: 0.42}   # blend-toward-white amount
K_LINESTYLE = {1: "-", 2: "-", 4: "--", 8: ":"}

# ── Orthogonal channel: circuit role within ONE composite variant ────────────
# hue/shape/shade are pinned once you fix (regime, mechanism, K); to show a
# variant's sub-circuits in the same panel we need a free channel.  Role rides
# marker SHAPE:
#   the PARTS being summed -> DIAMOND   (open  = segment/inner, "a piece"
#                                        filled = glue/outer,   "the stitch")
#   the TOTAL (accumulation) -> the variant's MECHANISM marker (sort circle /
#       product square), i.e. drawn exactly like its flat counterpart, so the
#       sum reads as "the whole thing, comparable to flat" -- no bold needed.
# Diamond therefore means "sub-component" everywhere and never appears in a
# plain comparison figure; the mechanism marker means "a complete circuit".
# (Bars: role rides HATCH instead.)
ROLE = {
    "segment": {"marker": "D",  "fill": "open",   "lw": 1.5},
    "inner":   {"marker": "D",  "fill": "open",   "lw": 1.5},
    "glue":    {"marker": "D",  "fill": "filled", "lw": 1.6},
    "outer":   {"marker": "D",  "fill": "filled", "lw": 1.6},
    "total":   {"marker": None, "fill": "filled", "lw": 1.8},  # = mechanism marker
    "crit":    {"marker": None, "fill": "filled", "lw": 1.8},   # parallel critical path
}
ROLE_HATCH = {"segment": "", "inner": "", "glue": "////", "outer": "xxxx",
              "total": ""}

# ── Off-grid flat representation study (Ch6 §6.2 baseline) ───────────────────
# Distinct matrix representations of the *same* flat statement; deliberately
# desaturated so they don't compete with the regime hues.
STUDY = {
    "flat-full-sort":  {"color": "#475569", "marker": "v"},   # slate
    "flat-full":       {"color": "#475569", "marker": "v"},   # alias
    "flat-pairwise":   {"color": "#94a3b8", "marker": "^"},   # light slate
}

# ── Privacy palette (used ONLY by the frontier figure) ───────────────────────
# The frontier's message is about *privacy*, so there colour encodes the privacy
# class and shape encodes the architecture family — a deliberately different
# encoding from the grid figures.  Kept here so all colour decisions live in one
# place; harmonised with the regime hues where the mapping is natural
# (structural~recursive purple, computational~committed amber, disclosed~plain).
PRIV = {
    "structural":    "#7c3aed",   # partition absent  (recursive / flat)   purple
    "computational": "#dc2626",   # hash / Pedersen hiding (committed)      red
    "oracle":        "#f97316",   # product P_i oracle leak                 orange
    "disclosed":     "#047857",   # partition in plaintext (plain-sort)     green
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tint(hex_color: str, amount: float) -> str:
    """Blend a colour toward white by `amount` in [0,1] (0 = unchanged)."""
    r, g, b = mcolors.to_rgb(hex_color)
    return mcolors.to_hex((r + (1 - r) * amount,
                           g + (1 - g) * amount,
                           b + (1 - b) * amount))


def parse_variant(variant: str):
    """('committed-product') -> ('committed', 'product').  None if not on-grid."""
    for regime in REGIME_HUE:
        for mech in MECHANISM_MARKER:
            if variant == f"{regime}-{mech}":
                return regime, mech
    return None


def color_for(variant: str, k=None) -> str:
    """Hue for the variant's regime, tinted by K.  Falls back to STUDY/black."""
    parsed = parse_variant(variant)
    if parsed is None:
        if variant in STUDY:
            return _tint(STUDY[variant]["color"], _K_TINT.get(k, 0.0))
        return "#222222"
    regime, _ = parsed
    return _tint(REGIME_HUE[regime], _K_TINT.get(k, 0.0))


def marker_for(variant: str) -> str:
    parsed = parse_variant(variant)
    if parsed is None:
        return STUDY.get(variant, {}).get("marker", "o")
    _, mech = parsed
    return MECHANISM_MARKER[mech]


def linestyle_for(k=None) -> str:
    return K_LINESTYLE.get(k, "-")


def markersize_for(k=None) -> float:
    """Marker shrinks slightly as K grows, so denser families stay readable."""
    return {1: 6.0, 2: 6.0, 4: 5.3, 8: 4.6}.get(k, 5.5)


def display_name(variant: str, k=None) -> str:
    return variant if k in (None, 1) else f"{variant}  (K={k})"


def style(variant: str, k=None) -> dict:
    """Full per-line style bundle for a (variant, K).

    Keys: color, marker, ls, ms, ecolor (lightened error-bar colour), label.
    """
    color = color_for(variant, k)
    rgb = mcolors.to_rgb(color)
    ecolor = mcolors.to_hex(tuple(c * 0.5 + 0.5 for c in rgb))
    return {
        "color":  color,
        "marker": marker_for(variant),
        "ls":     linestyle_for(k),
        "ms":     markersize_for(k),
        "ecolor": ecolor,
        "label":  display_name(variant, k),
    }


def role_style(variant: str, role: str, k=None) -> dict:
    """Style for one sub-circuit (role) of a variant, on the orthogonal fill
    channel.  Adds mfc/mec/mew (open vs filled marker), role-aware lw, and a
    `hatch` for bar charts.  hue/shape/shade still come from (variant, k)."""
    base = style(variant, k)
    r = ROLE.get(role, {"marker": None, "fill": "filled", "lw": 1.6})
    filled = r["fill"] == "filled"
    base.update({
        "marker": r.get("marker") or base["marker"],   # diamond for parts; mechanism marker for total
        "mfc":   base["color"] if filled else "white",
        "mec":   base["color"],
        "mew":   1.3,
        "lw":    r["lw"],
        "hatch": ROLE_HATCH.get(role, ""),
        "label": display_name(variant, k) + ("" if role == "total" else f" {role}"),
    })
    return base


def role_legend_handles(roles=("segment", "glue", "total"), color="#444444",
                        total_marker="s"):
    """Neutral-grey proxy handles explaining the role shape language for a panel.

    `total_marker` is the mechanism marker of the variant(s) shown (sort 'o' /
    product 's'), so the legend's "total" swatch matches the figure.
    """
    from matplotlib.lines import Line2D
    spec = {"segment": ("D", "open",   "segment / inner (a part)"),
            "inner":   ("D", "open",   "segment / inner (a part)"),
            "glue":    ("D", "filled", "glue / outer (the stitch)"),
            "outer":   ("D", "filled", "glue / outer (the stitch)"),
            "total":   (total_marker, "filled", "total (same marker as flat)")}
    out = []
    for role in roles:
        marker, fill, label = spec.get(role, ("o", "filled", role))
        filled = fill == "filled"
        out.append(Line2D([0], [0], marker=marker, color=color,
                          lw=ROLE.get(role, {}).get("lw", 1.6),
                          mfc=color if filled else "white", mec=color, mew=1.3,
                          label=label))
    return out


# ── Back-compat shim for plot_thesis_figures.py ──────────────────────────────
# That module reads a dict `C[name] -> (color, marker)`.  Rebuild it from the
# grid so its colours become the canonical, grid-encoded ones.  K is handled
# there via linestyle, so the base (K-untinted) hue is the right value here.
def _C():
    out = {}
    for regime in REGIME_HUE:
        for mech in MECHANISM_MARKER:
            name = f"{regime}-{mech}"
            out[name] = (color_for(name), marker_for(name))
    for name, d in STUDY.items():
        out[name] = (d["color"], d["marker"])
    return out


C = _C()
