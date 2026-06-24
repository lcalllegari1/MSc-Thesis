#!/usr/bin/env python3
"""
pipeline/plot_style_legend.py  --  Render the thesis figure visual language as a
single approval sheet, so the palette can be eyeballed before any real figure
uses it.  Writes plots/figures/00_style_legend.{pdf,png}.

    python pipeline/plot_style_legend.py
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import style as S

OUT = "plots/figures"
os.makedirs(OUT, exist_ok=True)

REGIMES = list(S.REGIME_HUE)            # flat, plain, committed, recursive
MECHS   = list(S.MECHANISM_MARKER)      # sort, product
KS      = [2, 4, 8]

fig, axgrid = plt.subplots(2, 2, figsize=(14, 10))
axes = axgrid.flat

# ── Panel 1: the grid (regime × mechanism), at base K ────────────────────────
ax = axes[0]
for ci, regime in enumerate(REGIMES):
    for ri, mech in enumerate(MECHS):
        name = f"{regime}-{mech}"
        s = S.style(name)
        ax.scatter(ci, ri, s=420, color=s["color"], marker=s["marker"],
                   edgecolor="k", lw=0.8, zorder=3)
ax.set_xticks(range(len(REGIMES))); ax.set_xticklabels(REGIMES, fontsize=10)
ax.set_yticks(range(len(MECHS)))
ax.set_yticklabels([f"{m}\n({S.MECHANISM_MARKER[m]})" for m in MECHS], fontsize=10)
ax.set_xlim(-0.5, len(REGIMES) - 0.5); ax.set_ylim(-0.5, len(MECHS) - 0.5)
ax.set_xlabel("stitching regime  →  HUE", fontsize=10)
ax.set_ylabel("mechanism  →  MARKER", fontsize=10)
ax.set_title("The grid: column = hue moves · row = marker moves\n"
             "(forbidden diagonal moves both)", fontsize=11)
ax.grid(True, ls="--", alpha=0.3)

# ── Panel 2: K shade + linestyle ramp, one example variant per regime ────────
ax = axes[1]
x = np.linspace(1, 10, 30)
yoff = 0
labels, ticks = [], []
for regime in REGIMES:
    name = f"{regime}-product"
    for k in KS:
        s = S.style(name, k=k)
        ax.plot(x, np.full_like(x, yoff) + 0.0, color=s["color"], ls=s["ls"],
                lw=2.2, marker=s["marker"], ms=s["ms"], markevery=8)
        ax.text(10.4, yoff, f"K={k}", va="center", fontsize=9, color=s["color"])
        yoff -= 1
    ticks.append(yoff + 2); labels.append(name)
    yoff -= 0.6
ax.set_yticks(ticks); ax.set_yticklabels(labels, fontsize=10)
ax.set_xlim(0.5, 11.5); ax.set_xticks([])
ax.set_title("K → shade (lighter) + linestyle (— -- ··)\n"
             "larger K reads lighter & more broken-up", fontsize=11)

# ── Panel 3: role channel (marker shape: diamond parts / mechanism total) ─────
ax = axes[2]
x = np.linspace(1, 10, 30)
name = "plain-product"        # product -> total drawn as a square (like flat-product)
for role, base_y in [("segment", 2.0), ("glue", 1.0), ("total", 0.0)]:
    rs = S.role_style(name, role, k=4)
    yv = np.full_like(x, base_y) + 0.18 * np.sin(x / 2)
    ax.plot(x, yv, color=rs["color"], ls=rs["ls"], lw=rs["lw"],
            marker=rs["marker"], ms=7.0, markevery=7,
            mfc=rs["mfc"], mec=rs["mec"], mew=rs["mew"])
    ax.text(10.4, base_y, rs["label"], va="center", fontsize=10, color=rs["color"])
ax.set_xlim(0.5, 13.5); ax.set_ylim(-0.8, 3.0); ax.set_xticks([]); ax.set_yticks([])
ax.set_title("Role = marker SHAPE (orthogonal to hue/shade)\n"
             "◇ open = part (segment/inner) · ◆ filled = stitch (glue/outer)\n"
             "total = mechanism marker (■ here), drawn like flat — no bold needed\n"
             "example: plain-product, K=4", fontsize=10.5)

# ── Panel 4: off-grid study variants + privacy palette ───────────────────────
ax = axes[3]
y = 0
ax.text(0, y, "flat representation study (off-grid):", fontsize=10,
        fontweight="bold"); y -= 1
for name in ("flat-full-sort", "flat-pairwise"):
    s = S.style(name)
    ax.scatter(0.3, y, s=300, color=s["color"], marker=s["marker"],
               edgecolor="k", lw=0.7)
    ax.text(0.6, y, name, va="center", fontsize=10); y -= 1
y -= 0.6
ax.text(0, y, "privacy palette (frontier figure only):", fontsize=10,
        fontweight="bold"); y -= 1
for cls, col in S.PRIV.items():
    ax.scatter(0.3, y, s=300, color=col, marker="o", edgecolor="k", lw=0.7)
    ax.text(0.6, y, cls, va="center", fontsize=10); y -= 1
ax.set_xlim(-0.2, 4); ax.set_ylim(y - 0.5, 1)
ax.axis("off")
ax.set_title("Non-grid palettes", fontsize=11)

fig.suptitle("Thesis figure visual language — hue = regime · marker = mechanism · "
             "shade+linestyle = K", y=1.02, fontsize=13, fontweight="bold")
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(OUT, f"00_style_legend.{ext}"), bbox_inches="tight")
plt.close(fig)
print("wrote", os.path.join(OUT, "00_style_legend.{pdf,png}"))
