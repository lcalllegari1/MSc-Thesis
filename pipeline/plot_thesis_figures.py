#!/usr/bin/env python3
"""
Thesis figure generator — reads results/*.csv directly and emits the curated
body figure set + key diagnostics. All styling comes from pipeline/style.py
(the single source of truth: hue=regime, marker=mechanism, shade+linestyle=K),
so every figure is consistent by construction.

Outputs (so the thesis never embeds a stale hand copy):
    plots/figures/<name>.png            quick raster preview / docs
    plots/figures/<name>.pdf            vector copy for the gallery
    thesis/template/assets/figures/<name>.pdf   the PDF the thesis embeds

Self-contained: does its own aggregation (no dependence on aggregate_*.py
intermediates). Run from repo root in the zk-tsp env:
    python pipeline/plot_thesis_figures.py
"""
import csv, statistics as st, os
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RES = "results"
OUT = "plots/figures"                       # PNG gallery + PDF copies (preview / docs)
ASSETS = "thesis/template/assets/figures"   # vector PDFs the thesis actually embeds
for _d in (OUT, ASSETS):
    os.makedirs(_d, exist_ok=True)
PROOF = 14656  # bytes per ZK proof (pinned across all variants)

plt.rcParams.update({
    "figure.dpi": 120, "savefig.dpi": 200, "font.size": 11,
    "axes.grid": True, "grid.alpha": 0.3, "axes.axisbelow": True,
    "legend.frameon": False, "figure.autolayout": True,
})

# Colour / marker conventions come from the single source of truth (style.py):
# hue = stitching regime, marker = mechanism, shade+linestyle = K, fill = role.
# C[name] -> (base_hue, marker); PRIV[class] -> colour (frontier only).
from style import C, PRIV, color_for, role_style  # noqa: E402

def load(f):
    p = os.path.join(RES, f)
    if not os.path.exists(p): return []
    with open(p) as fh: return list(csv.DictReader(fh))

def fnum(x):
    try: return float(x)
    except: return None

def save(fig, name):
    # PNG for quick preview; vector PDF into BOTH the gallery and the thesis assets
    # dir, so the embedded figures are always freshly generated from style.py and
    # never a stale hand copy. Run from repo root in the zk-tsp env.
    fig.savefig(os.path.join(OUT, f"{name}.png"), bbox_inches="tight")
    for d in (OUT, ASSETS):
        fig.savefig(os.path.join(d, f"{name}.pdf"), bbox_inches="tight")
    plt.close(fig)
    print("  wrote", name)

# ---------------------------------------------------------------- FLAT
flat = load("flat.csv") + load("flat_large.csv")
FB = defaultdict(lambda: defaultdict(list))
for r in flat:
    for c in ("circuit_size","witness_s","prove_s","verify_s","peak_mb","acir_opcodes"):
        v = fnum(r[c])
        if v is not None: FB[(r["variant"], int(r["n"]))][c].append(v)
def fb(v, n, c):
    x = FB[(v, n)][c]; return st.mean(x) if x else None
def fb_ns(v):
    return sorted({n for (vv, n) in FB if vv == v})

# ---------------------------------------------------------------- HIER (isolated)
HIER_FILES = {
    "plain-sort":        "hier_sort_iso.csv",
    "plain-product":     "hier_gp_iso.csv",
    "committed-sort":    "hier_committed_sort_iso.csv",
    "committed-product": "hier_committed_gp_iso.csv",
}
HIER = {}  # name -> (n,k) -> metrics
for name, f in HIER_FILES.items():
    g = defaultdict(lambda: {"subs": [], "glue": None, "sp": [], "gp": None,
                             "spk": [], "gpk": None, "vh": None})
    for r in load(f):
        n, k, run, circ = int(r["n"]), int(r["k"]), r["run"], r["circuit"]
        cs, pv, pk = fnum(r["circuit_size"]), fnum(r["prove_s"]), fnum(r["peak_mb"])
        key = (n, k, run)
        if circ == "glue":
            g[key]["glue"], g[key]["gp"], g[key]["gpk"] = cs, pv, pk
            g[key]["vh"] = fnum(r["verify_hier_s"])
        else:
            g[key]["subs"].append(cs); g[key]["sp"].append(pv); g[key]["spk"].append(pk)
    nk = defaultdict(lambda: defaultdict(list))
    for (n, k, run), d in g.items():
        if not d["subs"] or d["glue"] is None: continue
        nk[(n, k)]["sub"].append(d["subs"][0])
        nk[(n, k)]["glue"].append(d["glue"])
        nk[(n, k)]["total"].append(sum(d["subs"]) + d["glue"])
        nk[(n, k)]["crit"].append(max(d["sp"]) + d["gp"])        # ideal-parallel wall-clock
        nk[(n, k)]["peak"].append(max(max(d["spk"]), d["gpk"]))  # per-prover footprint
        if d["vh"] is not None: nk[(n, k)]["vh"].append(d["vh"])
    HIER[name] = {kk: {m: st.mean(v) for m, v in dd.items() if v} for kk, dd in nk.items()}

# ---------------------------------------------------------------- RECURSION
def rec(*files):
    g = defaultdict(lambda: {"inner": [], "outer": [], "op": [], "opk": [], "ov": [], "ip": []})
    for f in files:
        for r in load(f):
            n, k, run = int(r["n"]), int(r["k"]), r["run"]
            gates, pv, pk, vv = fnum(r["gates"]), fnum(r["prove_s"]), fnum(r["peak_mb"]), fnum(r["verify_s"])
            key = (n, k)
            if r["role"] == "outer_recursive":
                g[key]["outer"].append(gates); g[key]["op"].append(pv)
                g[key]["opk"].append(pk)
                if vv is not None: g[key]["ov"].append(vv)
            else:
                g[key]["inner"].append(gates); g[key]["ip"].append(pv)
    out = {}
    for key, d in g.items():
        if not d["outer"]: continue
        K = key[1]
        out[key] = {
            "inner": st.mean(d["inner"]), "outer": st.mean(d["outer"]),
            "per_seg": st.mean(d["outer"]) / K,
            "outer_prove": st.mean(d["op"]), "outer_peak": st.mean(d["opk"]),
            "outer_verify": st.mean(d["ov"]) if d["ov"] else None,
            "total": K * st.mean(d["inner"]) + st.mean(d["outer"]),
            "crit": (max(d["ip"]) if d["ip"] else 0) + st.mean(d["op"]),  # serial outer tail
        }
    return out
REC = {
    "recursive-product": rec("recursive_gp_raw.csv", "recursive_gp_large_raw.csv"),
    "recursive-sort":    rec("recursive_sort_raw.csv", "recursive_sort_large_raw.csv"),
}

# ================================================================= FIGURES

# --- FIG 1: flat scaling, circuit_size vs N (log-log + linear) -------------
def fig_flat_scaling():
    variants = [("flat_full_pairwise","flat-pairwise","flat-full pairwise  O(n²)"),
                ("flat_full_sort","flat-full-sort","flat-full sort"),
                ("flat_merkle_sort","flat-sort","flat-Merkle sort"),
                ("flat_merkle_grand_product","flat-product","flat-Merkle product")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for ax, logscale in zip(axes, (True, False)):
        for var, key, lab in variants:
            ns = fb_ns(var)
            ys = [fb(var, n, "circuit_size") for n in ns]
            col, mk = C[key]
            ax.plot(ns, ys, mk + "-", ms=3.5, lw=1.4, color=col, label=lab)
        if logscale:
            ax.set_xscale("log"); ax.set_yscale("log"); ax.set_title("log–log (slope = complexity exponent)")
        else:
            ax.set_title("linear (absolute magnitude)")
        ax.set_xlabel("n (nodes)"); ax.set_ylabel("circuit size (UltraHonk gates)")
    axes[0].legend(loc="upper left", fontsize=9)
    # No suptitle: the Typst #figure caption carries the figure-level description.
    save(fig, "01_flat_scaling")

# --- FIG 2: flat-full vs flat-Merkle crossover (N≈176) ---------------------
def fig_flat_crossover():
    ns = fb_ns("flat_merkle_sort")
    full = [fb("flat_full_sort", n, "circuit_size") for n in ns]
    mkl  = [fb("flat_merkle_sort", n, "circuit_size") for n in ns]
    fig, ax = plt.subplots(figsize=(7.2, 5))
    ax.plot(ns, full, "v-", ms=4, color=C["flat-full-sort"][0], label="flat-full (matrix public, O(n²) inputs)")
    ax.plot(ns, mkl,  "o-", ms=4, color=C["flat-sort"][0], label="flat-Merkle (committed, O(n·log n) hashing)")
    # crossover marker
    cx = None
    for i in range(1, len(ns)):
        if (full[i-1] < mkl[i-1]) and (full[i] >= mkl[i]):
            cx = ns[i]; break
    if cx:
        ax.axvline(cx, ls=":", color="k", alpha=.6)
        ax.annotate(f"crossover  n≈{cx}\n(full overtakes Merkle)", xy=(cx, mkl[ns.index(cx)]),
                    xytext=(cx*1.15, mkl[ns.index(cx)]*0.45), fontsize=9,
                    arrowprops=dict(arrowstyle="->", color="k", alpha=.6))
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("n (nodes)"); ax.set_ylabel("circuit size (gates)")
    # No in-figure title: the Typst #figure caption carries the description.
    ax.legend(loc="upper left")
    save(fig, "02_flat_full_vs_merkle_crossover")

# --- FIG 3: witness-time inversion (sort vs product) -----------------------
def fig_witness_inversion():
    ns = [n for n in fb_ns("flat_merkle_sort") if fb("flat_merkle_grand_product", n, "circuit_size")]
    dg = [100*(fb("flat_merkle_grand_product",n,"circuit_size")-fb("flat_merkle_sort",n,"circuit_size"))
          /fb("flat_merkle_sort",n,"circuit_size") for n in ns]
    sw = [fb("flat_merkle_sort",n,"witness_s") for n in ns]
    gw = [fb("flat_merkle_grand_product",n,"witness_s") for n in ns]
    dw = [100*(g-s)/s for s,g in zip(sw,gw)]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    ax = axes[0]
    ax.plot(ns, dg, "s-", ms=3.5, color="#d62728", label="Δ circuit size  (product − sort)")
    ax.plot(ns, dw, "o-", ms=3.5, color="#1f77b4", label="Δ witness time  (product − sort)")
    ax.axhline(0, color="k", lw=.8)
    ax.set_xscale("log"); ax.set_xlabel("N"); ax.set_ylabel("relative difference (%)")
    ax.set_title("The inversion: product costs MORE gates, LESS witness time")
    ax.legend(loc="center left")
    ax = axes[1]
    ax.plot(ns, sw, "o-", ms=3.5, color=C["flat-sort"][0], label="sort  (dynamic-ROM check_shuffle)")
    ax.plot(ns, gw, "s-", ms=3.5, color=C["flat-product"][0], label="product  (straight-line arithmetic)")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("N"); ax.set_ylabel("witness-solve time (s)")
    ax.set_title("Absolute witness time — the gap widens with N")
    ax.legend(loc="upper left")
    fig.suptitle("Witness-time inversion (flat row: identical statement, Merkle backbone & Prover.toml)", y=1.02)
    save(fig, "03_witness_time_inversion")

# --- FIG 4: dualism — total gates as % of flat vs N ------------------------
def fig_dualism():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    panels = [("sort","flat_merkle_sort",["plain-sort","committed-sort"]),
              ("product","flat_merkle_grand_product",["plain-product","committed-product"])]
    for ax,(mech,flatv,names) in zip(axes,panels):
        ns = sorted({n for (n,k) in HIER[names[0]]})
        for name in names:
            for k,ls in zip((2,4,8),("-","--",":")):
                xs=[n for n in ns if (n,k) in HIER[name] and fb(flatv,n,"circuit_size")]
                ys=[100*HIER[name][(n,k)]["total"]/fb(flatv,n,"circuit_size") for n in xs]
                col=C[name][0]
                ax.plot(xs,ys,ls,color=col,lw=1.4,label=f"{name} K={k}")
        ax.axhline(100,color="k",lw=1,ls="-",alpha=.7)
        ax.set_xscale("log"); ax.set_xlabel("n")
        ax.set_title(f"{mech} mechanism")
        ax.legend(fontsize=8,ncol=2)
    axes[0].set_ylabel("total hierarchical gates as % of flat")
    axes[0].text(0.02,0.97,"100% = flat (the conservation floor)\nall curves sit ABOVE → no total-work win",
                 transform=axes[0].transAxes,va="top",fontsize=8,color="dimgray")
    # No suptitle: the Typst #figure caption carries the figure-level description.
    save(fig, "04_dualism_total_work")

# --- FIG 5: fingerprint lever — glue size sort vs product ------------------
def fig_lever():
    fig, ax = plt.subplots(figsize=(7.6, 5))
    ns = sorted({n for (n,k) in HIER["plain-sort"]})
    # plain-sort and plain-product share the plain hue, so the mechanism rides the
    # marker (sort circle / product square); K rides linestyle+shade.
    for name in ("plain-sort","plain-product"):
        col,mk=C[name]
        for k,ls in zip((2,4,8),("-","--",":")):
            xs=[n for n in ns if (n,k) in HIER[name]]
            ax.plot(xs,[HIER[name][(n,k)]["glue"] for n in xs],ls,
                    color=color_for(name,k),marker=mk,ms=4,markevery=3,lw=1.5,
                    label=f"{name} glue  K={k}")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("n"); ax.set_ylabel("glue circuit size (gates)")
    # No in-figure title: caption carries it. (Both glues are O(n); the lever cuts
    # the per-node slope ~7x, sort ~19/node vs product ~2.8/node -- it does not turn
    # the coverage check into O(K).)
    ax.legend(fontsize=8.5)
    save(fig, "05_fingerprint_lever_glue")

# --- FIG 6: F7 — plain-sort vs plain-product total (sort cheaper) ----------
def fig_f7():
    fig, ax = plt.subplots(figsize=(7.4,5))
    ns=sorted({n for (n,k) in HIER["plain-sort"]})
    for k,ls in zip((2,4,8),("-","--",":")):
        xs=[n for n in ns if (n,k) in HIER["plain-sort"] and (n,k) in HIER["plain-product"]]
        ratio=[100*(HIER["plain-product"][(n,k)]["total"]/HIER["plain-sort"][(n,k)]["total"]-1) for n in xs]
        ax.plot(xs,ratio,ls,color="#8c564b",lw=1.5,label=f"K={k}")
    ax.axhline(0,color="k",lw=1)
    ax.set_xscale("log"); ax.set_xlabel("N")
    ax.set_ylabel("plain-product total gates over plain-sort (%)")
    ax.set_title("F7 — neither dominates: plain-sort is cheaper on TOTAL gates at every (N,K)")
    ax.legend(title="segments")
    save(fig, "06_F7_sort_not_dominated")

# --- FIG 7: speedup vs K (isolated, ideal-parallel) ------------------------
def fig_speedup_vs_k():
    # Mechanism split at fixed n: product glue is negligible so both speedup and
    # per-prover memory approach K×; the sort glue is a serial, memory-heavy O(n)
    # tail that caps both. hue = regime, marker = mechanism (style grammar).
    N=3000
    FLATREF={"plain-product":"flat_merkle_grand_product","committed-product":"flat_merkle_grand_product",
             "plain-sort":"flat_merkle_sort","committed-sort":"flat_merkle_sort"}
    variants=["plain-product","committed-product","plain-sort","committed-sort"]
    fig, axes = plt.subplots(1,2,figsize=(12,4.8))
    ax=axes[0]
    for name in variants:
        col,mk=C[name]
        sp=[(fb(FLATREF[name],N,"prove_s")/HIER[name][(N,k)]["crit"]) if (N,k) in HIER[name] else np.nan
            for k in (2,4,8)]
        ax.plot((2,4,8),sp,mk+"-",ms=6,color=col,lw=1.6,label=name)
    ax.plot((2,4,8),(2,4,8),"k:",lw=1.2,label="ideal K×")
    ax.set_xlabel("K (segments)"); ax.set_ylabel("speedup vs flat (×)")
    ax.set_title("Parallel speedup  (critical path = slowest segment + glue)")
    ax.set_xticks((2,4,8)); ax.legend(fontsize=8.5)
    ax=axes[1]
    for name in variants:
        col,mk=C[name]
        red=[(fb(FLATREF[name],N,"peak_mb")/HIER[name][(N,k)]["peak"]) if (N,k) in HIER[name] else np.nan
             for k in (2,4,8)]
        ax.plot((2,4,8),red,mk+"-",ms=6,color=col,lw=1.6,label=name)
    ax.plot((2,4,8),(2,4,8),"k:",lw=1.2,label="ideal K×")
    ax.set_xlabel("K (segments)"); ax.set_ylabel("per-prover peak memory reduction (×)")
    ax.set_title("Per-prover peak memory reduction")
    ax.set_xticks((2,4,8)); ax.legend(fontsize=8.5)
    save(fig, "07_speedup_and_memory_vs_K")

# --- FIG 8: recursion M-independence (the gem) -----------------------------
def fig_recursion_m_independence():
    fig, axes = plt.subplots(1,2,figsize=(12,4.8))
    # recursive-sort and recursive-product share the recursive hue, so mechanism
    # rides the marker (sort circle / product square) and K rides linestyle+shade.
    LAB={"recursive-product":"product inner (O(1) surface)",
         "recursive-sort":"sort inner (O(M) surface)"}
    klines=[plt.Line2D([0],[0],color="dimgray",ls=ls,lw=1.3,label=f"K={k}")
            for k,ls in zip((2,4,8),("-","--",":"))]
    ax=axes[0]
    for name in ("recursive-product","recursive-sort"):
        col,mk=C[name]
        for k,ls in zip((2,4,8),("-","--",":")):
            xs=sorted({n for (n,kk) in REC[name] if kk==k})
            ys=[REC[name][(n,k)]["per_seg"]/1e3 for n in xs]
            ax.plot(xs,ys,ls,marker=mk,ms=4,markevery=2,color=color_for(name,k),lw=1.3,
                    label=(LAB[name] if k==2 else None))
    ax.set_xscale("log"); ax.set_xlabel("N"); ax.set_ylabel("outer gates per segment (×10³)")
    ax.set_title("Outer gates per segment")
    mleg=ax.legend(fontsize=9,loc="upper left")
    ax.add_artist(mleg); ax.legend(handles=klines,fontsize=8,loc="lower right",title="segments")
    ax=axes[1]
    for name in ("recursive-product","recursive-sort"):
        col,mk=C[name]
        for k,ls in zip((2,4,8),("-","--",":")):
            xs=sorted({n for (n,kk) in REC[name] if kk==k})
            ys=[REC[name][(n,k)]["outer_peak"]/1e3 for n in xs]
            ax.plot(xs,ys,ls,marker=mk,ms=4,markevery=2,color=color_for(name,k),lw=1.3,
                    label=(name if k==2 else None))
    ax.set_xscale("log"); ax.set_xlabel("N"); ax.set_ylabel("outer prover peak memory (GB)")
    ax.set_title("Outer prover peak memory")
    ax.legend(fontsize=9)
    fig.suptitle("Why recursive-product ships — product inner keeps the outer flat; sort inner grows (gates ↑17%, memory ~6×)", y=1.03)
    save(fig, "08_recursion_M_independence")

# --- FIG 9: verifier tax — J1, all three families vs K ---------------------
def fig_verifier_tax():
    fig, axes = plt.subplots(1,2,figsize=(12,4.8))
    N=1000
    Ks=(2,4,8)
    # proof_bytes (verifier download)
    ax=axes[0]
    ax.axhline(PROOF/1024,color=C["flat-sort"][0],lw=2,label="flat  (1 proof, O(1))")
    for name,col in [("plain-product",C["plain-product"][0]),("committed-product",C["committed-product"][0])]:
        ax.plot(Ks,[(k+1)*PROOF/1024 for k in Ks],"s-",color=col,label=f"{name}  (K+1 proofs, O(K))")
    ax.plot(Ks,[PROOF/1024]*3,"s--",color=C["recursive-product"][0],label="recursion  (1 proof, O(1))")
    ax.set_xlabel("K"); ax.set_ylabel("verifier download (KB)"); ax.set_xticks(Ks)
    ax.set_title(f"Proof bytes the verifier must check (N={N})"); ax.legend(fontsize=9)
    # verify_s
    ax=axes[1]
    fv=fb("flat_merkle_grand_product",N,"verify_s")
    ax.axhline(fv,color=C["flat-sort"][0],lw=2,label="flat")
    for name,col in [("plain-product",C["plain-product"][0]),("committed-product",C["committed-product"][0])]:
        ys=[HIER[name][(N,k)]["vh"] for k in Ks if (N,k) in HIER[name] and "vh" in HIER[name][(N,k)]]
        ax.plot(Ks[:len(ys)],ys,"s-",color=col,label=f"{name}  (O(K))")
    rv=[REC["recursive-product"][(N,k)]["outer_verify"] for k in Ks if (N,k) in REC["recursive-product"]]
    ax.plot(Ks[:len(rv)],rv,"s--",color=C["recursive-product"][0],label="recursion  (O(1))")
    ax.set_xlabel("K"); ax.set_ylabel("verification time (s)"); ax.set_xticks(Ks)
    ax.set_title("Verifier wall-clock"); ax.legend(fontsize=9)
    fig.suptitle("The verifier-side stitching tax — hierarchical pays O(K); recursion buys it back to O(1)", y=1.02)
    save(fig, "09_verifier_tax_vs_K")

# --- FIG 10: three-corner frontier (Pareto) at fixed N ---------------------
def fig_frontier():
    N, K = 1000, 4
    # (label, family, total_gates, verifier_bytes, parallel_wallclock, per_prover_peak, privacy)
    pts=[]
    fg=fb("flat_merkle_grand_product",N,"circuit_size")
    pts.append(("flat-prod","flat", fg, PROOF, fb("flat_merkle_grand_product",N,"prove_s"),
                fb("flat_merkle_grand_product",N,"peak_mb"),"structural"))
    fgs=fb("flat_merkle_sort",N,"circuit_size")
    pts.append(("flat-sort","flat", fgs, PROOF, fb("flat_merkle_sort",N,"prove_s"),
                fb("flat_merkle_sort",N,"peak_mb"),"structural"))
    privmap={"plain-sort":("plain-sort","disclosed"),"plain-product":("plain-prod","oracle"),
             "committed-sort":("comm-sort","computational"),"committed-product":("comm-prod","computational")}
    for name,(short,priv) in privmap.items():
        d=HIER[name].get((N,K))
        if not d: continue
        pts.append((short,"hier", d["total"], (K+1)*PROOF, d["crit"], d["peak"], priv))
    for name,short in (("recursive-product","rec-prod"),("recursive-sort","rec-sort")):
        d=REC[name].get((N,K))
        if not d: continue
        pts.append((short,"rec", d["total"], PROOF, d["crit"], d["outer_peak"],"structural"))
    # architecture family -> shape (well-separated even when points crowd);
    # mechanism -> marker size (sort small, product large = "more gates");
    # privacy class -> colour (PRIV).  Three orthogonal categoricals + position.
    FAM={"flat":"h","hier":"P","rec":"X"}
    MECH_SIZE={"sort":80,"product":165}
    def msize(lab): return MECH_SIZE["sort" if "sort" in lab else "product"]
    # manual label offsets (points), keyed by short label, per panel.  Crowded
    # structural-purple corner (flat/rec) gets leader-line annotations below.
    offA={"flat-prod":(9,5),"flat-sort":(9,-13),"rec-prod":(-30,10),"rec-sort":(9,-4),
          "plain-sort":(7,6),"plain-prod":(7,-13),"comm-sort":(7,8),"comm-prod":(7,-14)}
    offB={"flat-prod":(9,5),"flat-sort":(9,-13),"rec-prod":(-12,-16),"rec-sort":(-46,4),
          "plain-sort":(7,8),"plain-prod":(7,-7),"comm-sort":(7,8),"comm-prod":(7,-14)}
    lead={"flat-prod","flat-sort","rec-prod"}   # crowded -> draw a short leader line

    fig, axes = plt.subplots(1,2,figsize=(13.5,5.6))
    ax=axes[0]
    for lab,fam,tg,vb,wc,pk,priv in pts:
        ax.scatter(vb/1024, tg/1e6, s=msize(lab), marker=FAM[fam], color=PRIV[priv],
                   edgecolor="k", lw=.8, zorder=3)
        dx,dy=offA.get(lab,(6,4))
        ax.annotate(lab,(vb/1024,tg/1e6),xytext=(dx,dy),textcoords="offset points",fontsize=8.5,
                    arrowprops=dict(arrowstyle="-",color="0.5",lw=.6) if lab in lead else None)
    ax.set_xlabel("verifier download (KB, log scale)"); ax.set_ylabel("total prover work (M gates)")
    ax.set_xscale("log"); ax.set_xlim(10,120); ax.set_ylim(1.4,5.2)
    ax.set_title("Verifier cost  vs  total prover work")
    ax.text(0.5,0.93,"← recursion & flat: O(1) verifier   |   hierarchical: O(K) →",
            transform=ax.transAxes,ha="center",fontsize=8,color="dimgray")
    ax=axes[1]
    for lab,fam,tg,vb,wc,pk,priv in pts:
        ax.scatter(tg/1e6, wc, s=msize(lab), marker=FAM[fam], color=PRIV[priv],
                   edgecolor="k", lw=.8, zorder=3)
        dx,dy=offB.get(lab,(6,4))
        ax.annotate(lab,(tg/1e6,wc),xytext=(dx,dy),textcoords="offset points",fontsize=8.5,
                    arrowprops=dict(arrowstyle="-",color="0.5",lw=.6) if lab in lead else None)
    ax.set_xlabel("total prover work (M gates)"); ax.set_ylabel("parallel wall-clock (s)")
    ax.set_xlim(1.4,5.2); ax.set_ylim(0,52)
    ax.set_title("Total work  vs  parallel wall-clock")
    ax.text(0.5,0.06,"hierarchical wins wall-clock; recursion's serial outer caps it",
            transform=ax.transAxes,ha="center",fontsize=8,color="dimgray")
    # legends: privacy (colour) + architecture (shape) + mechanism (size)
    ph=[plt.Line2D([0],[0],marker="o",ls="",mfc=col,mec="k",label=p) for p,col in PRIV.items()]
    fh=[plt.Line2D([0],[0],marker=m,ls="",mfc="0.7",mec="k",ms=9,label=f) for f,m in
        {"flat (K=1)":"h","hierarchical":"P","recursion":"X"}.items()]
    mh=[plt.Line2D([0],[0],marker="o",ls="",mfc="0.7",mec="k",ms=ms,label=lab) for lab,ms in
        (("sort",6),("product",11))]
    leg1=fig.legend(handles=ph,title="partition privacy",loc="lower center",ncol=4,bbox_to_anchor=(0.27,-0.07))
    leg2=fig.legend(handles=fh,title="architecture",loc="lower center",ncol=3,bbox_to_anchor=(0.66,-0.07))
    fig.legend(handles=mh,title="mechanism (size)",loc="lower center",ncol=2,bbox_to_anchor=(0.90,-0.07))
    fig.add_artist(leg1); fig.add_artist(leg2)
    fig.suptitle(f"The frontier — three non-dominated corners at N={N}, K={K}", y=1.0)
    save(fig, "10_frontier_pareto")

# --- FIG 11: pick-two triangle (radar) -------------------------------------
def fig_pick_two():
    # qualitative 0/1 scores on three axes
    axes_lab=["P\n(parallel +\nlow per-prover mem)","V\n(O(1) verifier)","C\n(low prover\noverhead)"]
    families={"flat":[0,1,1],"hierarchical":[1,0,1],"recursion":[1,1,0],"folding (future)":[1,1,1]}
    cols={"flat":C["flat-sort"][0],"hierarchical":C["plain-product"][0],
          "recursion":C["recursive-product"][0],"folding (future)":"#bbbbbb"}
    ang=np.linspace(0,2*np.pi,3,endpoint=False).tolist(); ang+=ang[:1]
    fig,axs=plt.subplots(1,4,figsize=(14,3.8),subplot_kw=dict(polar=True))
    for ax,(fam,sc) in zip(axs,families.items()):
        v=sc+sc[:1]
        ax.plot(ang,v,color=cols[fam],lw=2); ax.fill(ang,v,color=cols[fam],alpha=.25)
        ax.set_xticks(ang[:-1]); ax.set_xticklabels(axes_lab,fontsize=8)
        ax.set_yticks([0,1]); ax.set_yticklabels([]); ax.set_ylim(0,1)
        ax.set_title(fam,fontsize=11,pad=14)
    fig.suptitle("The pick-two triangle — each architecture gets two corners (folding breaks it)", y=1.08)
    save(fig, "11_pick_two_triangle")

# --- FIG 12: privacy ladder (slopegraph) -----------------------------------
def fig_privacy_ladder():
    rungs=[("flat-full / Variant B","disclosed",0),
           ("plain-sort","disclosed (partition plaintext)",0),
           ("plain-product","computational — P_i oracle",1),
           ("committed-* (Poseidon)","computational — hash hiding",2),
           ("committed-* (Pedersen)","unconditional content",3),
           ("recursion / flat","structural — partition absent",4)]
    fig,ax=plt.subplots(figsize=(8.5,5))
    for i,(name,desc,lvl) in enumerate(rungs):
        ax.plot([0,1],[i,i],color="#cccccc",lw=.8,zorder=1)
        ax.scatter(0.12,i,s=70,color=plt.cm.viridis(lvl/4),zorder=3,edgecolor="k",lw=.5)
        ax.text(0.16,i,name,va="center",fontsize=10,fontweight="bold")
        ax.text(0.62,i,desc,va="center",fontsize=9,color="dimgray")
    ax.set_ylim(-0.6,len(rungs)-0.4); ax.set_xlim(0,1.05); ax.axis("off")
    ax.annotate("",xy=(0.04,len(rungs)-0.6),xytext=(0.04,-0.4),
                arrowprops=dict(arrowstyle="->",color="k"))
    ax.text(0.0,len(rungs)/2-0.5,"assumptions decreasing  →",rotation=90,va="center",fontsize=9)
    ax.set_title("The privacy ladder — assumption-decreasing partition hiding",pad=12)
    save(fig, "12_privacy_ladder")

if __name__ == "__main__":
    print("Generating thesis figures into", OUT)
    fig_flat_scaling()
    fig_flat_crossover()
    fig_witness_inversion()
    fig_dualism()
    fig_lever()
    fig_f7()
    fig_speedup_vs_k()
    fig_recursion_m_independence()
    fig_verifier_tax()
    fig_frontier()
    fig_pick_two()
    fig_privacy_ladder()
    print("done.")
