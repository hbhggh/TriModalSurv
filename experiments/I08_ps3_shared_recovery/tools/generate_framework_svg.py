#!/usr/bin/env python3
"""Generate the publication-ready TriModalSurv (I08) framework diagram in vector SVG, PDF, and 300-DPI PNG.

Layout & scientific constraints (Stage 4 / Subagent P4):
1. Golden three-column visual ratio on a 1600 x 760 canvas:
   - Left column (~18% width): Frozen PS3-Style Backbone (I07) & D0 Hard Identity Bypass.
   - Middle column (~36% width): Module A (A1 Recovery-Oriented Orthogonal Subspace, r=32) &
     Module C (C1 Stage 2a Training-Only Alignment & Consistency Supervision).
   - Right column (~46% width): Module B (Stage 1 B1 Global Linear Trend + Stage 2 B6-LOO
     Post-Training Plug-in with Hat-Leverage LOO Residual Pool, Per-Modality Cosine Top-K Attention,
     and Parameter-Free IQR Density Gate) + Compact Merged Parameter-Free Decoding & Frozen Cox Head.
2. Strict code alignment:
   - D0 Hard Identity Bypass for complete input (Omega = M): bit-exact 0.681 Test / 0.678 Val.
   - A1 orthogonal decomposition into 32-d shared coordinates (kept, 37,152 total trainable params,
     87.5% reduction vs. 256-d) and 224-d orthogonal complement (truncated for missing u notin Omega;
     preserved for visible m in Omega via W1-4 passthrough).
   - C1 supervision arrow for L_cons explicitly targets Stage 1 B1 base linear output z_hat^{B1,Omega}_{i,u},
     never the post-training B6-LOO output.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _ensure_matplotlib() -> None:
    """Re-exec with the project conda environment Python if matplotlib is unavailable in current sys.executable."""
    try:
        import matplotlib  # noqa: F401
        return
    except ImportError:
        pass

    if os.environ.get("I08_FRAMEWORK_REEXEC") == "1":
        raise RuntimeError("matplotlib is not available even after re-exec.")

    candidates = [
        os.environ.get("PYTHON_BIN", ""),
        str(Path.home() / "miniconda3" / "envs" / "protomasksurv-exp1" / "bin" / "python"),
        str(Path.home() / "miniconda3" / "envs" / "tcga_env" / "bin" / "python"),
        "/opt/homebrew/Caskroom/miniconda/base/envs/protomasksurv-exp1/bin/python",
    ]
    for cand in candidates:
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            env = dict(os.environ)
            env["I08_FRAMEWORK_REEXEC"] = "1"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/pycache_p4")
            rc = subprocess.call([cand, str(Path(__file__).resolve()), *sys.argv[1:]], env=env)
            sys.exit(rc)
    raise RuntimeError("Could not find a Python interpreter with matplotlib installed.")


_ensure_matplotlib()

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


# Canvas dimensions (1600 x 760 academic widescreen aspect ratio)
W, H = 1600.0, 760.0


def configure_rc() -> None:
    """Configure deterministic, publication-grade typography and vector output settings."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "mathtext.fontset": "stixsans",
        "axes.unicode_minus": False,
        "svg.fonttype": "path",
        "svg.hashsalt": "trimodalsurv_i08_framework_v1",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def y_td(y_top: float, h: float = 0.0) -> float:
    """Convert top-down Y coordinate (0 at top, H at bottom) to matplotlib bottom-up Y coordinate."""
    return H - y_top - h


def draw_box(
    ax,
    x: float,
    y_top: float,
    w: float,
    h: float,
    *,
    fc: str = "#ffffff",
    ec: str = "#cbd5e1",
    lw: float = 1.2,
    ls: str = "-",
    r: float = 8.0,
    zorder: int = 2,
    alpha: float = 1.0,
):
    """Draw a rounded rectangle using top-down coordinates."""
    patch = FancyBboxPatch(
        (x, y_td(y_top, h)),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        linestyle=ls,
        alpha=alpha,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def draw_text(
    ax,
    x: float,
    y_top: float,
    s: str,
    *,
    fs: float = 9.0,
    color: str = "#0f172a",
    weight: str = "normal",
    ha: str = "left",
    va: str = "top",
    zorder: int = 5,
    linespacing: float = 1.28,
    style: str = "normal",
):
    """Draw text at top-down coordinates."""
    return ax.text(
        x,
        y_td(y_top, 0.0),
        s,
        fontsize=fs,
        color=color,
        fontweight=weight,
        fontstyle=style,
        ha=ha,
        va=va,
        zorder=zorder,
        linespacing=linespacing,
    )


def draw_badge(
    ax,
    x: float,
    y_top: float,
    w: float,
    h: float,
    label: str,
    *,
    fc: str = "#1e40af",
    ec: str = "none",
    tc: str = "#ffffff",
    fs: float = 7.8,
    r: float = 5.0,
    lw: float = 0.8,
    zorder: int = 6,
    weight: str = "bold",
):
    """Draw a pill/badge with centered label."""
    draw_box(ax, x, y_top, w, h, fc=fc, ec=ec, lw=lw, r=r, zorder=zorder)
    draw_text(
        ax,
        x + w / 2.0,
        y_top + h / 2.0,
        label,
        fs=fs,
        color=tc,
        weight=weight,
        ha="center",
        va="center",
        zorder=zorder + 1,
    )


def draw_arrow(
    ax,
    x1: float,
    y1_top: float,
    x2: float,
    y2_top: float,
    *,
    color: str = "#334155",
    lw: float = 1.5,
    ls: str = "-",
    ms: float = 11.0,
    zorder: int = 4,
    style: str = "-|>",
):
    """Draw a straight vector arrow between two top-down points."""
    arr = FancyArrowPatch(
        (x1, y_td(y1_top)),
        (x2, y_td(y2_top)),
        arrowstyle=style,
        mutation_scale=ms,
        color=color,
        linewidth=lw,
        linestyle=ls,
        zorder=zorder,
        shrinkA=0,
        shrinkB=0,
    )
    ax.add_patch(arr)
    return arr


def draw_polyline_arrow(
    ax,
    pts_td: list[tuple[float, float]],
    *,
    color: str = "#334155",
    lw: float = 1.6,
    ls: str = "-",
    ms: float = 11.0,
    zorder: int = 4,
):
    """Draw an orthogonal multi-segment polyline with an arrowhead on the final segment."""
    if len(pts_td) < 2:
        return
    xs = [p[0] for p in pts_td[:-1]]
    ys = [y_td(p[1]) for p in pts_td[:-1]]
    x_prev, y_prev = pts_td[-2]
    x_last, y_last = pts_td[-1]
    if len(pts_td) > 2:
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=lw,
            linestyle=ls,
            solid_capstyle="round",
            solid_joinstyle="round",
            zorder=zorder,
        )
    draw_arrow(
        ax,
        x_prev,
        y_prev,
        x_last,
        y_last,
        color=color,
        lw=lw,
        ls=ls,
        ms=ms,
        zorder=zorder,
    )


def draw_truncation_marker(ax, cx: float, cy_top: float, *, radius: float = 8.0, zorder: int = 8) -> None:
    """Draw a crisp circular truncation / stop symbol (otimes) at top-down center (cx, cy_top)."""
    cy = y_td(cy_top)
    circ = mpatches.Circle(
        (cx, cy),
        radius=radius,
        facecolor="#fef2f2",
        edgecolor="#dc2626",
        linewidth=1.6,
        zorder=zorder,
    )
    ax.add_patch(circ)
    d = radius * 0.62
    ax.plot([cx - d, cx + d], [cy - d, cy + d], color="#dc2626", linewidth=1.8, zorder=zorder + 1)
    ax.plot([cx - d, cx + d], [cy + d, cy - d], color="#dc2626", zorder=zorder + 1, linewidth=1.8)


def build_figure() -> plt.Figure:
    """Build the complete TriModalSurv (I08) framework diagram."""
    configure_rc()
    fig = plt.figure(figsize=(16.0, 7.6), dpi=100, facecolor="#ffffff")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], frameon=False)
    ax.set_xlim(0.0, W)
    ax.set_ylim(0.0, H)
    ax.set_xticks([])
    ax.set_yticks([])

    # Background canvas
    draw_box(ax, 0, 0, W, H, fc="#ffffff", ec="none", r=0, zorder=0)

    # =========================================================================
    # 0. TOP TITLE & LEGEND BAR (Y_top = 8 .. 38)
    # =========================================================================
    draw_text(
        ax,
        22,
        12,
        "TriModalSurv (I08): Patient-Level Dynamic Missing-Modality Recovery in Orthogonal Shared Subspaces",
        fs=11.8,
        weight="bold",
        color="#0f172a",
    )

    # Compact legend badges on top-right
    draw_badge(
        ax, 845, 10, 152, 22,
        "Frozen I07 Backbone & Head",
        fc="#f1f5f9", ec="#64748b", tc="#334155", fs=7.2, lw=1.0,
    )
    draw_badge(
        ax, 1005, 10, 188, 22,
        "Stage 2a Trainable: A1 + B1 (37,152)",
        fc="#eff6ff", ec="#2563eb", tc="#1e40af", fs=7.2, lw=1.0,
    )
    draw_badge(
        ax, 1201, 10, 168, 22,
        "Stage 2a Supervision Only: C1",
        fc="#fff1f2", ec="#e11d48", tc="#be123c", fs=7.2, lw=1.0,
    )
    draw_badge(
        ax, 1377, 10, 205, 22,
        "Stage 2b Plug-in: B6-LOO (0 Retrain)",
        fc="#fffbeb", ec="#d97706", tc="#b45309", fs=7.2, lw=1.0,
    )

    # =========================================================================
    # 1. TOP D0 HARD IDENTITY BYPASS LANE (Y_top = 42 .. 84)
    # =========================================================================
    draw_box(
        ax, 22, 42, 1560, 42,
        fc="#eff6ff", ec="#1d4ed8", lw=1.4, r=7.0, zorder=2,
    )
    draw_badge(
        ax, 32, 49, 212, 28,
        r"D0 Hard Identity Bypass ($\Omega = \mathcal{M}$)",
        fc="#1d4ed8", ec="none", tc="#ffffff", fs=8.0, r=5.0,
    )
    draw_text(
        ax,
        256,
        54,
        r"Complete Input $\Omega = \mathcal{M} = \{R, W, T\}$:  Direct Frozen I07 Forward  "
        r"$p_{i,m}^F \in \mathbb{R}^{256} \;\longrightarrow\; h_i^F = \sum_{m\in\mathcal{M}} w_m^\top p_{i,m}^F + b_{\mathrm{risk}}$"
        "   (Bypasses A1 / B1 / B6-LOO)",
        fs=8.4,
        weight="bold",
        color="#1e3a8a",
    )
    draw_badge(
        ax, 1268, 48, 304, 30,
        r"Bit-Exact Complete Risk $h_i^F$:  0.681 Test / 0.678 Val",
        fc="#dbeafe", ec="#1d4ed8", tc="#1e3a8a", fs=8.0, lw=1.1, r=5.0,
    )
    draw_arrow(ax, 1226, 63, 1264, 63, color="#1d4ed8", lw=1.6, ms=11)

    # =========================================================================
    # 2. LEFT COLUMN (~18% WIDTH: X = 22 .. 288, W = 266): FROZEN BACKBONE & ROUTING
    # =========================================================================
    col1_x, col1_y, col1_w, col1_h = 22.0, 94.0, 266.0, 614.0
    draw_box(ax, col1_x, col1_y, col1_w, col1_h, fc="#f8fafc", ec="#94a3b8", lw=1.4, r=10.0, zorder=1)

    # Column 1 Header
    draw_box(ax, col1_x, col1_y, col1_w, 42, fc="#e2e8f0", ec="#94a3b8", lw=1.2, r=10.0, zorder=2)
    draw_text(
        ax, col1_x + 10, col1_y + 7,
        "Left (~18%): Frozen Backbone & Routing",
        fs=8.8, weight="bold", color="#0f172a",
    )
    draw_text(
        ax, col1_x + 10, col1_y + 23,
        "I07 PS3-Style Backbone (eval, requires_grad=False)",
        fs=7.2, color="#475569",
    )

    # Block 1.1: Patient Trimodal Input & Pattern Router (Y_top = 144 .. 264)
    draw_box(ax, 30, 144, 250, 120, fc="#ffffff", ec="#cbd5e1", lw=1.1, r=7.0, zorder=3)
    draw_text(
        ax, 38, 150,
        r"1. Trimodal Input $\mathcal{M}=\{R, W, T\}$",
        fs=8.4, weight="bold", color="#0f172a",
    )
    # Three compact modality chips
    draw_badge(ax, 38, 170, 74, 22, "R: RNA (50)", fc="#ecfdf5", ec="#10b981", tc="#065f46", fs=7.3, lw=0.9)
    draw_badge(ax, 117, 170, 76, 22, "W: WSI (128)", fc="#eff6ff", ec="#3b82f6", tc="#1e40af", fs=7.3, lw=0.9)
    draw_badge(ax, 198, 170, 74, 22, "T: Text (F)", fc="#fff7ed", ec="#f97316", tc="#9a3412", fs=7.3, lw=0.9)

    # Observation Pattern Check box
    draw_box(ax, 38, 200, 234, 56, fc="#fefce8", ec="#eab308", lw=1.1, r=6.0, zorder=4)
    draw_text(
        ax, 155, 205,
        r"Observation Pattern Check: $\Omega \subseteq \mathcal{M}$",
        fs=7.9, weight="bold", color="#854d0e", ha="center",
    )
    draw_text(
        ax, 155, 222,
        r"• Complete ($\Omega = \mathcal{M}$) $\rightarrow$ Top D0 Bypass",
        fs=7.3, color="#1d4ed8", weight="bold", ha="center",
    )
    draw_text(
        ax, 155, 238,
        r"• Missing ($\Omega \subset \mathcal{M}$, 6 patterns) $\downarrow$ Frozen I07",
        fs=7.3, color="#b91c1c", weight="bold", ha="center",
    )
    # Clean left-margin route from Pattern Check up to D0 Bypass Lane (NEVER crosses Col 1 header!)
    draw_polyline_arrow(
        ax,
        [(38, 225), (10, 225), (10, 63), (22, 63)],
        color="#1d4ed8", lw=1.7, ms=10,
    )
    draw_badge(
        ax, 2, 132, 18, 42,
        "$\\Omega$\n$=$\n$\\mathcal{M}$",
        fc="#dbeafe", ec="#1d4ed8", tc="#1e3a8a", fs=6.5, lw=0.8, r=3.0,
    )

    # Arrow down to Block 1.2
    draw_arrow(ax, 155, 264, 155, 282, color="#b91c1c", lw=1.5, ms=10)
    draw_text(ax, 162, 266, r"$\Omega \subset \mathcal{M}$ ($|\Omega|\in\{1,2\}$)", fs=7.2, weight="bold", color="#b91c1c")

    # Block 1.2: Frozen I07 PS3-Style Encoder (Y_top = 282 .. 412)
    draw_box(ax, 30, 282, 250, 130, fc="#ffffff", ec="#94a3b8", lw=1.1, r=7.0, zorder=3)
    draw_text(
        ax, 38, 288,
        "2. Frozen I07 PS3-Style Encoder",
        fs=8.4, weight="bold", color="#0f172a",
    )
    draw_text(
        ax, 38, 306,
        r"• Missing $u \notin \Omega$: no tokens generated"
        "\n  (zero attention mask pollution)\n"
        r"• 9-block cross-modal attention + $f_\beta$"
        "\n  -> LayerNorm -> valid-token mean pool",
        fs=7.35, color="#334155", linespacing=1.24,
    )
    draw_box(ax, 38, 368, 234, 36, fc="#f1f5f9", ec="#64748b", lw=0.9, r=5.0, zorder=4)
    draw_text(
        ax, 155, 373,
        r"Visible Pooled: $p_{i,m}^\Omega \in \mathbb{R}^{256}$ ($m \in \Omega$)",
        fs=7.8, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 155, 389,
        r"(Train full target: $p_{i,m}^F \in \mathbb{R}^{256}$, $m \in \mathcal{M}$)",
        fs=7.0, color="#475569", ha="center",
    )

    draw_arrow(ax, 155, 412, 155, 430, color="#334155", lw=1.5, ms=10)

    # Block 1.3: Pattern-Specific Centering (Y_top = 430 .. 558)
    draw_box(ax, 30, 430, 250, 128, fc="#ffffff", ec="#94a3b8", lw=1.1, r=7.0, zorder=3)
    draw_text(
        ax, 38, 436,
        "3. Pattern-Specific Centering (Eq. 1)",
        fs=8.4, weight="bold", color="#0f172a",
    )
    draw_text(
        ax, 38, 454,
        r"Fold-train means $\mu_{\Omega,m}^\Omega, \mu_m^F \in \mathbb{R}^{256}$ ($\mathcal{D}_{\mathrm{train}}$ only):",
        fs=7.2, color="#475569",
    )
    draw_box(ax, 38, 474, 234, 44, fc="#eff6ff", ec="#3b82f6", lw=1.0, r=5.0, zorder=4)
    draw_text(
        ax, 155, 479,
        r"$x_{i,m}^\Omega = p_{i,m}^\Omega - \mu_{\Omega,m}^\Omega \in \mathbb{R}^{256}$ ($m \in \Omega$)",
        fs=7.9, weight="bold", color="#1e3a8a", ha="center",
    )
    draw_text(
        ax, 155, 498,
        r"$x_{i,m}^F = p_{i,m}^F - \mu_m^F \in \mathbb{R}^{256}$ (Stage 2a target)",
        fs=7.2, color="#be123c", ha="center",
    )
    draw_text(
        ax, 38, 524,
        r"• Absorbs context shift ($p_m^\Omega \neq p_m^F$) before"
        "\n"
        r"  projecting into shared subspace $U_m$",
        fs=7.2, color="#334155", linespacing=1.22,
    )

    # Block 1.4: Visible Modality Passthrough W1-4 (Y_top = 574 .. 696)
    draw_box(ax, 30, 574, 250, 122, fc="#ecfdf5", ec="#059669", lw=1.3, r=7.0, zorder=3)
    draw_text(
        ax, 38, 580,
        "4. Visible Feature Passthrough (W1-4)",
        fs=8.4, weight="bold", color="#065f46",
    )
    draw_text(
        ax, 38, 598,
        r"• Visible $p_{i,m}^\Omega \in \mathbb{R}^{256}$ ($m \in \Omega$) is 100% preserved"
        "\n  without low-rank compression loss\n"
        r"• Identity $p_m^{\mathrm{sha}} + p_m^{\mathrm{res}} \equiv p_m$ holds"
        "\n  for all observed modalities\n"
        "• Routes directly to final slot assembly",
        fs=7.25, color="#064e3b", linespacing=1.24,
    )

    # =========================================================================
    # 3. MIDDLE COLUMN (~36% WIDTH: X = 310 .. 874, W = 564): MODULE A (A1) & MODULE C (C1)
    # =========================================================================
    col2_x, col2_w = 310.0, 564.0

    # -------------------------------------------------------------------------
    # 3A. MODULE A: A1 Recovery-Oriented Orthogonal Subspace (Y_top = 94 .. 412)
    # -------------------------------------------------------------------------
    draw_box(ax, col2_x, 94, col2_w, 318, fc="#f0f9ff", ec="#0284c7", lw=1.5, r=10.0, zorder=1)
    draw_box(ax, col2_x, 94, col2_w, 40, fc="#e0f2fe", ec="#0284c7", lw=1.2, r=10.0, zorder=2)
    draw_text(
        ax, col2_x + 12, 100,
        "Module A (A1): Recovery-Oriented Orthogonal Subspace",
        fs=8.6, weight="bold", color="#0c4a6e",
    )
    draw_text(
        ax, col2_x + 12, 116,
        "Middle Top (~36%) · Anti-aliasing projection (25/25 folds locked at r = 32)",
        fs=7.1, color="#0369a1",
    )
    draw_badge(
        ax, 672, 100, 192, 27,
        "37,152 params · 87.5% reduction",
        fc="#0284c7", ec="none", tc="#ffffff", fs=7.5, r=5.0,
    )

    # Arrow from Left Column Block 1.3 (x_{i,m}^Omega) into A1 Cayley Basis
    draw_polyline_arrow(
        ax,
        [(280, 488), (299, 488), (299, 255), (322, 255)],
        color="#0284c7", lw=1.8, ms=11,
    )
    draw_badge(
        ax, 286, 336, 26, 22,
        "$x_{i,m}^\\Omega$",
        fc="#e0f2fe", ec="#0284c7", tc="#0c4a6e", fs=7.2, lw=0.8, r=3.5,
    )

    # Sub-box A1-Left: Cayley Orthogonal Basis U_m (X = 322, Y_top = 142, W = 194, H = 260)
    draw_box(ax, 322, 142, 194, 260, fc="#ffffff", ec="#0284c7", lw=1.3, r=8.0, zorder=3)
    draw_text(
        ax, 419, 149,
        "Cayley Orthogonal Basis",
        fs=8.6, weight="bold", color="#0c4a6e", ha="center",
    )
    draw_box(ax, 332, 169, 174, 50, fc="#f0f9ff", ec="#38bdf8", lw=1.0, r=5.0, zorder=4)
    draw_text(
        ax, 419, 174,
        r"$U_m \in \mathbb{R}^{256 \times 32}$ ($m \in \{R,W,T\}$)",
        fs=8.0, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 419, 195,
        r"$U_m^\top U_m = I_{32}$   (Eq. 2, $r=32$)",
        fs=8.0, weight="bold", color="#0284c7", ha="center",
    )
    draw_text(
        ax, 332, 228,
        r"• Exact column orthogonality via"
        "\n"
        r"  float64 Cayley ($\|U^\top U - I\| < 10^{-6}$)"
        "\n• Fold-train SVD/PCA initialization\n"
        r"• Basis params: $3\times 256\times 32 = 24,576$"
        "\n  (+ B1 12,576 = 37,152 total,\n"
        "   12.5% of 256-d 296,448 params)",
        fs=7.15, color="#334155", linespacing=1.22,
    )
    draw_box(ax, 332, 338, 174, 54, fc="#f8fafc", ec="#94a3b8", lw=0.9, r=5.0, zorder=4)
    draw_text(
        ax, 419, 343,
        r"$x_{i,m}^\Omega = p_{i,m}^{\mathrm{sha},\Omega} + x_{i,m}^{\mathrm{res},\Omega}$ (Eq. 3)",
        fs=7.5, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 419, 363,
        r"$\langle p_{i,m}^{\mathrm{sha},\Omega},\, x_{i,m}^{\mathrm{res},\Omega} \rangle \equiv 0$",
        fs=7.6, weight="bold", color="#0369a1", ha="center",
    )
    draw_text(
        ax, 419, 379,
        "Strict structural anti-aliasing",
        fs=6.8, color="#475569", ha="center",
    )

    # Orthogonal split arrows from U_m box to Upper Branch and Lower Branch
    draw_polyline_arrow(
        ax,
        [(516, 205), (544, 205)],
        color="#059669", lw=2.0, ms=11,
    )
    draw_polyline_arrow(
        ax,
        [(516, 340), (544, 340)],
        color="#64748b", lw=1.6, ls="--", ms=11,
    )
    draw_truncation_marker(ax, 530, 340, radius=7.5, zorder=9)

    # Sub-box A1-Upper Branch: 32-d Shared Coordinates (X = 544, Y_top = 142, W = 318, H = 126)
    draw_box(ax, 544, 142, 318, 126, fc="#ecfdf5", ec="#059669", lw=1.6, r=8.0, zorder=3)
    draw_badge(
        ax, 550, 149, 306, 22,
        "Upper Branch: 32-d Cross-Modal Shared Subspace (KEPT)",
        fc="#059669", ec="none", tc="#ffffff", fs=7.1, r=4.0,
    )
    draw_text(
        ax, 703, 177,
        r"$z_{i,m}^\Omega = U_m^\top x_{i,m}^\Omega \in \mathbb{R}^{32}, \quad "
        r"p_{i,m}^{\mathrm{sha},\Omega} = U_m z_{i,m}^\Omega \in \mathbb{R}^{256}$  (Eq. 4)",
        fs=8.0, weight="bold", color="#064e3b", ha="center",
    )
    draw_text(
        ax, 556, 201,
        r"• Retains cross-modal predictable prognostic coordinates in $\mathbb{R}^{32}$"
        "\n• Eliminates high-dimensional estimation burden (37,152 params,\n"
        "  87.5% parameter reduction vs. 256-d full-space recovery)\n"
        "• Forwarded to Module B (B1 + B6-LOO) for dynamic recovery",
        fs=7.2, color="#065f46", linespacing=1.22,
    )

    # Sub-box A1-Lower Branch: 224-d Orthogonal Residual (X = 544, Y_top = 276, W = 318, H = 126)
    draw_box(ax, 544, 276, 318, 126, fc="#f1f5f9", ec="#64748b", lw=1.4, ls="--", r=8.0, zorder=3)
    draw_badge(
        ax, 550, 283, 306, 22,
        r"Lower Branch: 224-d Orthogonal Complement (TRUNCATED $\otimes$)",
        fc="#475569", ec="none", tc="#ffffff", fs=6.9, r=4.0,
    )
    draw_text(
        ax, 703, 311,
        r"$x_{i,m}^{\mathrm{res},\Omega} = (I_{256} - U_m U_m^\top) x_{i,m}^\Omega \in \mathbb{R}^{256}$  (224-d nullspace)",
        fs=7.9, weight="bold", color="#334155", ha="center",
    )
    draw_text(
        ax, 556, 335,
        r"• Truncated ($= 0$) for missing $u \notin \Omega$ to block 224-d hallucination"
        "\n  and modality-private noise injection (staining / batch artifacts)\n"
        r"• Preserved for visible $m \in \Omega$ via raw $p_{i,m}^\Omega$ passthrough (W1-4)"
        "\n• Avoids 256-d negative transfer (M7@default 0.6406 < 0.6519)",
        fs=7.15, color="#334155", linespacing=1.22,
    )

    # -------------------------------------------------------------------------
    # 3C. MODULE C: C1 Stage 2a Training-Only Supervision (Y_top = 436 .. 708)
    # -------------------------------------------------------------------------
    draw_box(ax, col2_x, 436, col2_w, 272, fc="#fff1f2", ec="#e11d48", lw=1.6, ls="--", r=10.0, zorder=1)
    draw_box(ax, col2_x, 436, col2_w, 38, fc="#ffe4e6", ec="#e11d48", lw=1.2, ls="--", r=10.0, zorder=2)
    draw_text(
        ax, col2_x + 12, 441,
        "Module C (C1): Alignment & Consistency Supervision",
        fs=8.6, weight="bold", color="#881337",
    )
    draw_text(
        ax, col2_x + 12, 456,
        r"Middle Bottom (~36%) · Rotates $U_m$ toward survival-relevant directions",
        fs=7.1, color="#9f1239",
    )
    draw_badge(
        ax, 684, 441, 180, 27,
        "Stage 2a Only · No Test Overhead",
        fc="#e11d48", ec="none", tc="#ffffff", fs=7.35, r=5.0,
    )

    # Dashed arrow from Left Column Block 1.3 (x_{i,m}^F) into C1
    draw_polyline_arrow(
        ax,
        [(280, 502), (310, 502)],
        color="#e11d48", lw=1.6, ls="--", ms=10,
    )
    draw_badge(
        ax, 283, 478, 25, 20,
        "$x_{i,m}^F$",
        fc="#ffe4e6", ec="#e11d48", tc="#9f1239", fs=7.1, lw=0.8, r=3.0,
    )

    # Dashed arrow from A1 U_m down to C1 top border (Y_top = 402 -> 436, cleanly in gap!)
    draw_arrow(ax, 419, 402, 419, 436, color="#e11d48", lw=1.6, ls="--", ms=10)
    draw_badge(
        ax, 428, 414, 114, 19,
        r"$z_{i,m}^F = U_m^\top x_{i,m}^F \in \mathbb{R}^{32}$",
        fc="#ffe4e6", ec="#e11d48", tc="#9f1239", fs=6.9, lw=0.8, r=3.5,
    )

    # Card C1-1: L_anchor (X = 320, Y_top = 480, W = 175, H = 160)
    draw_box(ax, 320, 480, 175, 160, fc="#ffffff", ec="#f43f5e", lw=1.1, r=7.0, zorder=3)
    draw_badge(
        ax, 328, 486, 159, 20,
        r"(1) Subspace Anchor  $\mathcal{L}_{\mathrm{anchor}}$",
        fc="#ffe4e6", ec="#e11d48", tc="#9f1239", fs=7.3, lw=0.8,
    )
    draw_text(
        ax, 407.5, 511,
        r"$\mathcal{L}_{\mathrm{anchor}} = \frac{1}{3 N_{\mathrm{train}} d}\sum_{m,i}$",
        fs=7.6, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 407.5, 539,
        r"$\|x_{i,m}^F - U_m U_m^\top x_{i,m}^F\|_2^2$",
        fs=7.9, weight="bold", color="#be123c", ha="center",
    )
    draw_text(
        ax, 328, 563,
        r"• Weight: $\lambda_a = 1.0$ (Eq. 13)"
        "\n• Exact losses.py:28 formula\n"
        r"• Anchors $U_m$ to preserve"
        "\n"
        r"  high-energy variance in $\mathbb{R}^{256}$",
        fs=7.05, color="#334155", linespacing=1.20,
    )

    # Card C1-2: L_modal (X = 503, Y_top = 480, W = 175, H = 160)
    draw_box(ax, 503, 480, 175, 160, fc="#ffffff", ec="#f43f5e", lw=1.1, r=7.0, zorder=3)
    draw_badge(
        ax, 511, 486, 159, 20,
        r"(2) Cosine Alignment  $\mathcal{L}_{\mathrm{modal}}$",
        fc="#ffe4e6", ec="#e11d48", tc="#9f1239", fs=7.3, lw=0.8,
    )
    draw_text(
        ax, 590.5, 511,
        r"$\mathcal{L}_{\mathrm{modal}} = \frac{1}{3 N_{\mathrm{train}}}\sum_{i,(m,n)\in\mathcal{P}}$",
        fs=7.6, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 590.5, 539,
        r"$(1 - \cos(z_{i,m}^F,\, z_{i,n}^F))$",
        fs=7.9, weight="bold", color="#be123c", ha="center",
    )
    draw_text(
        ax, 511, 563,
        r"• Weight: $\lambda_m = 0.1$ (Eq. 11)"
        "\n"
        r"• Pairs $\mathcal{P}=\{(R,W),(R,T),(W,T)\}$"
        "\n• Aligns full-pass shared\n"
        "  coordinates across modalities",
        fs=7.05, color="#334155", linespacing=1.20,
    )

    # Card C1-3: L_cons (X = 686, Y_top = 480, W = 176, H = 160)
    draw_box(ax, 686, 480, 176, 160, fc="#ffffff", ec="#e11d48", lw=1.4, r=7.0, zorder=3)
    draw_badge(
        ax, 694, 486, 160, 20,
        r"(3) Consistency  $\mathcal{L}_{\mathrm{cons}}$ ($\rightarrow$ B1)",
        fc="#e11d48", ec="none", tc="#ffffff", fs=7.3,
    )
    draw_text(
        ax, 774, 511,
        r"$\mathcal{L}_{\mathrm{cons}} = \frac{1}{9 N_{\mathrm{train}} r}\sum_{\Omega,u\notin\Omega,i}$",
        fs=7.6, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 774, 539,
        r"$\|\hat{z}_{i,u}^{\mathrm{B1},\Omega} - \mathrm{sg}(z_{i,u}^F)\|_2^2$",
        fs=7.9, weight="bold", color="#be123c", ha="center",
    )
    draw_text(
        ax, 694, 563,
        r"• Weight: $\lambda_c = 1.0$ (Eq. 12)"
        "\n"
        r"• Asymmetric stop_grad on $z_{i,u}^F$"
        "\n• Explicitly supervises Stage 1\n"
        r"  B1 output $\hat{z}_{i,u}^{\mathrm{B1},\Omega}$ (NEVER B6!)",
        fs=7.05, color="#881337", weight="bold", linespacing=1.20,
    )

    # Bottom Joint Stage 2a Objective Bar in C1 (X = 320, Y_top = 648, W = 542, H = 50)
    draw_box(ax, 320, 648, 542, 50, fc="#ffe4e6", ec="#e11d48", lw=1.1, r=6.0, zorder=3)
    draw_text(
        ax, 591, 653,
        r"Stage 2a Joint Objective (Eq. 14):   "
        r"$\mathcal{L}_{\mathrm{total}} = \mathcal{L}_{\mathrm{Cox}}^{\mathrm{missing}} + "
        r"\lambda_a \mathcal{L}_{\mathrm{anchor}} + \lambda_m \mathcal{L}_{\mathrm{modal}} + \lambda_c \mathcal{L}_{\mathrm{cons}}$"
        r"   ($\lambda_a=1.0, \lambda_m=0.1, \lambda_c=1.0$)",
        fs=7.6, weight="bold", color="#881337", ha="center",
    )
    draw_text(
        ax, 591, 674,
        r"Gradients update ONLY A1 ($U_m$) & Stage 1 B1 ($R_{\Omega\to u}, b_{\Omega,u}$); "
        "Stage 2 B6-LOO is a post-training plug-in outside the backprop loop",
        fs=6.85, color="#9f1239", ha="center",
    )

    # =========================================================================
    # 4. RIGHT COLUMN (~46% WIDTH: X = 896 .. 1582, W = 686):
    #    MODULE B (B1 + B6-LOO) + COMPACT MERGED DECODING & FROZEN COX HEAD
    # =========================================================================
    col3_x, col3_w = 896.0, 686.0
    draw_box(ax, col3_x, 94, col3_w, 614, fc="#fffbeb", ec="#d97706", lw=1.5, r=10.0, zorder=1)
    draw_box(ax, col3_x, 94, col3_w, 40, fc="#fef3c7", ec="#d97706", lw=1.2, r=10.0, zorder=2)
    draw_text(
        ax, col3_x + 12, 100,
        "Right (~46%): Module B (B1 + B6-LOO Dynamic Recovery) & Merged Decoding + Cox Head",
        fs=8.9, weight="bold", color="#78350f",
    )
    draw_text(
        ax, col3_x + 12, 116,
        "Two-stage fixed-subspace recovery: global linear trend (B1) + LOO leverage residual retrieval & IQR gate (B6-LOO)",
        fs=7.2, color="#92400e",
    )

    # -------------------------------------------------------------------------
    # 4A. STAGE 1 (B1): Pattern-Specific Global Linear Trend (X = 908, Y_top = 142, W = 424, H = 136)
    # -------------------------------------------------------------------------
    draw_box(ax, 908, 142, 424, 136, fc="#ffffff", ec="#2563eb", lw=1.4, r=8.0, zorder=3)
    draw_box(ax, 908, 142, 424, 28, fc="#dbeafe", ec="#2563eb", lw=1.1, r=8.0, zorder=4)
    draw_text(
        ax, 918, 149,
        "Stage 1 (B1): Pattern-Specific Linear Trend",
        fs=8.3, weight="bold", color="#1e3a8a",
    )
    draw_badge(
        ax, 1190, 145, 134, 22,
        "Trainable · 12,576 params",
        fc="#2563eb", ec="none", tc="#ffffff", fs=7.1, r=4.0,
    )

    # Arrow from A1 Upper Branch (z_{i,m}^Omega) into Stage 1 B1
    draw_arrow(ax, 862, 196, 908, 196, color="#059669", lw=2.0, ms=11)
    draw_badge(
        ax, 872, 173, 28, 20,
        "$z_{i,m}^\\Omega$",
        fc="#ecfdf5", ec="#059669", tc="#065f46", fs=7.2, lw=0.8, r=3.0,
    )

    draw_text(
        ax, 918, 175,
        r"Concatenate visible shared coords ($k = |\Omega| \in \{1,2\}$):  "
        r"$b_{i,\mathrm{in}}^\Omega = \mathrm{Concat}_{m\in\Omega}(z_{i,m}^\Omega) \in \mathbb{R}^{32|\Omega|}$",
        fs=7.45, color="#0f172a",
    )
    draw_box(ax, 918, 194, 262, 54, fc="#eff6ff", ec="#60a5fa", lw=1.0, r=6.0, zorder=4)
    draw_text(
        ax, 1049, 199,
        r"$\hat{z}_{i,u}^{\mathrm{B1},\Omega} = R_{\Omega\to u}\, b_{i,\mathrm{in}}^\Omega + b_{\Omega,u} \in \mathbb{R}^{32}$  (Eq. 7)",
        fs=8.0, weight="bold", color="#1e3a8a", ha="center",
    )
    draw_text(
        ax, 1049, 219,
        r"9 pattern-target maps ($\Omega \to u,\; u \notin \Omega$) · Zero-initialized",
        fs=7.0, color="#334155", ha="center",
    )
    draw_text(
        ax, 1049, 233,
        r"Captures population-level global linear trend in $\mathbb{R}^{32}$",
        fs=6.9, color="#475569", ha="center",
    )

    # Highlighted B1 Output Node (Target of C1 L_cons supervision!)
    draw_box(ax, 1188, 194, 134, 54, fc="#fff1f2", ec="#e11d48", lw=1.6, r=6.0, zorder=5)
    draw_text(
        ax, 1255, 198,
        "B1 Base Output",
        fs=7.6, weight="bold", color="#881337", ha="center",
    )
    draw_text(
        ax, 1255, 213,
        r"$\hat{z}_{i,u}^{\mathrm{B1},\Omega} \in \mathbb{R}^{32}$",
        fs=8.5, weight="bold", color="#be123c", ha="center",
    )
    draw_text(
        ax, 1255, 233,
        r"Supervised by $\mathcal{L}_{\mathrm{cons}}$",
        fs=6.85, weight="bold", color="#e11d48", ha="center",
    )
    draw_arrow(ax, 1180, 221, 1188, 221, color="#1e3a8a", lw=1.4, ms=9)

    # CRITICAL CODE ALIGNMENT: C1 L_cons dashed supervision arrow -> bottom of B1 Base Output z_hat^{B1,Omega}_{i,u}
    # Routes along dedicated bottom channel y=263 (completely below the y=194..248 formula box!)
    draw_polyline_arrow(
        ax,
        [(862, 535), (885, 535), (885, 263), (1255, 263), (1255, 248)],
        color="#e11d48", lw=1.8, ls="--", ms=10,
    )
    draw_badge(
        ax, 918, 253, 262, 19,
        r"$\mathcal{L}_{\mathrm{cons}}$ supervises B1 output $\hat{z}_{i,u}^{\mathrm{B1},\Omega}$ ONLY (Stage 2a)",
        fc="#ffe4e6", ec="#e11d48", tc="#be123c", fs=6.8, lw=0.9, r=3.5,
    )

    # -------------------------------------------------------------------------
    # 4B. STAGE 2 (B6-LOO): Post-Training Plug-in (X = 908, Y_top = 292, W = 424, H = 404)
    # -------------------------------------------------------------------------
    draw_box(ax, 908, 292, 424, 404, fc="#ffffff", ec="#d97706", lw=1.6, r=8.0, zorder=3)
    draw_box(ax, 908, 292, 424, 34, fc="#fef3c7", ec="#d97706", lw=1.2, r=8.0, zorder=4)
    draw_text(
        ax, 916, 297,
        "Stage 2 (B6-LOO): Dynamic Recovery",
        fs=8.0, weight="bold", color="#78350f",
    )
    draw_text(
        ax, 916, 311,
        "LOO leverage residual kernel calibration",
        fs=6.8, color="#92400e",
    )
    draw_badge(
        ax, 1130, 296, 194, 25,
        "Post-Training Plug-in · Zero Retraining",
        fc="#d97706", ec="none", tc="#ffffff", fs=7.1, r=4.5,
    )

    # Arrow from B1 Base Output (right side) down into Stage 2 B6-LOO top border (avoids crossing badge!)
    draw_polyline_arrow(
        ax,
        [(1295, 248), (1295, 292)],
        color="#1e3a8a", lw=1.7, ms=10,
    )
    draw_text(ax, 1314, 264, r"$\hat{z}_{i,u}^{\mathrm{B1},\Omega}$", fs=7.6, weight="bold", color="#1e3a8a", ha="center")

    # Sub-block B6-1: Hat-Leverage LOO Residual Pool (X = 918, Y_top = 332, W = 404, H = 110)
    draw_box(ax, 918, 332, 404, 110, fc="#fffbeb", ec="#f59e0b", lw=1.1, r=6.0, zorder=4)
    draw_badge(
        ax, 926, 337, 290, 19,
        r"(1) Hat-Leverage Debiased LOO Residual Pool ($\mathcal{D}_{\mathrm{train}}$)",
        fc="#fef3c7", ec="#d97706", tc="#78350f", fs=7.05, lw=0.8,
    )
    draw_text(
        ax, 1120, 360,
        r"$H_{jj} = [X_c(X_c^\top X_c + \lambda_{\mathrm{hat}} I)^{-1}X_c^\top]_{jj} + \frac{1}{N_{\mathrm{train}}}, \quad "
        r"e_{j,u}^{\mathrm{LOO},\Omega} = \frac{z_{j,u}^F - \hat{z}_{j,u}^{\mathrm{B1},\Omega}}{\max(1 - H_{jj},\, 10^{-4})} \in \mathbb{R}^{32}$",
        fs=7.4, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 926, 393,
        r"• Closed-form ridge Hat diagonal $H_{jj}$ ($\lambda_{\mathrm{hat}} = 1.0$, Eq. 8, operators.py:248)"
        "\n"
        r"• Debiases in-sample training residual shrinkage via PRESS factor $(1 - H_{jj})^{-1}$"
        "\n• Built on fold train_part only; zero test leakage, zero extra trainable parameters",
        fs=6.95, color="#334155", linespacing=1.18,
    )

    # Sub-block B6-2: Per-Modality Cosine Similarity & Top-K Attention (X = 918, Y_top = 450, W = 404, H = 110)
    draw_box(ax, 918, 450, 404, 110, fc="#fffbeb", ec="#f59e0b", lw=1.1, r=6.0, zorder=4)
    draw_badge(
        ax, 926, 455, 308, 19,
        "(2) Per-Modality Cosine Similarity & Top-K Softmax Attention",
        fc="#fef3c7", ec="#d97706", tc="#78350f", fs=7.05, lw=0.8,
    )
    draw_text(
        ax, 1120, 478,
        r"$s_{ij}^\Omega = \frac{1}{|\Omega|}\sum_{m\in\Omega}\cos(z_{i,m}^\Omega, z_{j,m}^\Omega) \;\;(\mathrm{id}(i)\neq\mathrm{id}(j))"
        r"\;\longrightarrow\; a_{ij}^\Omega = \mathrm{Softmax}_{l\in\mathcal{N}_K(i;\Omega)}(s_{il}^\Omega / \tau)$",
        fs=7.45, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 926, 510,
        r"• Self-query strictly masked ($\mathrm{id}(i) = \mathrm{id}(j) \Rightarrow s_{ij}^\Omega = -\infty$) to prevent identity shortcut"
        "\n"
        r"• Retrieves $K = 10$ nearest fold-train donors $\mathcal{N}_K(i; \Omega)$ with $a_{ij}^\Omega = \exp(s_{ij}^\Omega/\tau)/\sum_l \exp(s_{il}^\Omega/\tau)$"
        "\n• Captures local patient-level nonlinear survival patterns missed by global linear B1",
        fs=6.95, color="#334155", linespacing=1.18,
    )

    # Sub-block B6-3: Parameter-Free IQR Density Gate & Dynamic Synthesis (X = 918, Y_top = 568, W = 404, H = 120)
    draw_box(ax, 918, 568, 404, 120, fc="#ecfdf5", ec="#059669", lw=1.4, r=6.0, zorder=4)
    draw_badge(
        ax, 926, 573, 308, 19,
        "(3) Parameter-Free IQR Density Gate & Dynamic Synthesis",
        fc="#059669", ec="none", tc="#ffffff", fs=7.05,
    )
    draw_text(
        ax, 1120, 596,
        r"$\alpha_i^\Omega = \alpha_{\max}\,\sigma(\gamma_\Omega(s_{i,(1)}^\Omega - \delta_\Omega)) \in [0, \alpha_{\max}], \quad "
        r"\hat{z}_{i,u}^{\mathrm{B6},\Omega} = \hat{z}_{i,u}^{\mathrm{B1},\Omega} + \alpha_i^\Omega \sum_{j\in\mathcal{N}_K(i)} a_{ij}^\Omega\, e_{j,u}^{\mathrm{LOO},\Omega} \in \mathbb{R}^{32}$",
        fs=7.4, weight="bold", color="#064e3b", ha="center",
    )
    draw_text(
        ax, 926, 626,
        r"• Zero learned gate params: $\delta_\Omega = \mathrm{Median}_{q\in\mathcal{D}_{\mathrm{train}}}(s_{q,(1)}^{\mathrm{LOO},\Omega})$, "
        r"$\gamma_\Omega = \mathrm{clip}(1.349/\mathrm{IQR}_\Omega, 5, 30)$ (Eq. 9–10)"
        "\n"
        r"• Outlier protection ($s_{i,(1)}^\Omega \ll \delta_\Omega \Rightarrow \alpha_i^\Omega \to 0$); exact fallback to B1 when $\alpha_{\max} = 0$"
        "\n"
        r"• Jaccard $0.6845\pm 0.0046$ ($20\times 80\%$); Top-1 erasure $\Delta = 0.01296$ vs. $0.00423$ ($p=0.00$)",
        fs=6.8, color="#065f46", linespacing=1.19,
    )

    # Arrows connecting B6-1 and B6-2 into B6-3
    draw_arrow(ax, 1120, 442, 1120, 450, color="#d97706", lw=1.3, ms=9)
    draw_arrow(ax, 1120, 560, 1120, 568, color="#059669", lw=1.4, ms=9)

    # -------------------------------------------------------------------------
    # 4C. MERGED PARAMETER-FREE DECODING & FROZEN COX RISK HEAD
    #     (X = 1358, Y_top = 142, W = 214, H = 554)
    # -------------------------------------------------------------------------
    draw_box(ax, 1358, 142, 214, 554, fc="#f8fafc", ec="#475569", lw=1.5, r=8.0, zorder=3)
    draw_box(ax, 1358, 142, 214, 36, fc="#e2e8f0", ec="#475569", lw=1.2, r=8.0, zorder=4)
    draw_text(
        ax, 1465, 148,
        "Merged Decoding & Cox Head",
        fs=8.3, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 1465, 163,
        "Zero New Trainable Parameters",
        fs=7.0, weight="bold", color="#475569", ha="center",
    )

    # Arrow from B6-3 output (z_hat^{B6,Omega}_{i,u}) up the corridor X=1345 into Step 1 Decoding
    draw_polyline_arrow(
        ax,
        [(1322, 620), (1345, 620), (1345, 240), (1366, 240)],
        color="#059669", lw=1.9, ms=11,
    )
    draw_badge(
        ax, 1333, 392, 24, 46,
        "$\\hat{z}^{\\mathrm{B6}}$\n$\\mathbb{R}^{32}$",
        fc="#ecfdf5", ec="#059669", tc="#065f46", fs=6.4, lw=0.9, r=3.5,
    )

    # Step 1 inside Merged Block: Parameter-Free Decoding (Y_top = 188 .. 326)
    draw_box(ax, 1366, 188, 198, 138, fc="#ffffff", ec="#0284c7", lw=1.2, r=6.0, zorder=4)
    draw_badge(
        ax, 1374, 194, 182, 20,
        "1. Parameter-Free Decoding (Eq. 5)",
        fc="#e0f2fe", ec="#0284c7", tc="#0c4a6e", fs=7.1, lw=0.8,
    )
    draw_text(
        ax, 1465, 222,
        r"$\hat{p}_{i,u}^\Omega = \mu_u^F + U_u\, \hat{z}_{i,u}^{\mathrm{B6},\Omega} \in \mathbb{R}^{256}$",
        fs=7.9, weight="bold", color="#0c4a6e", ha="center",
    )
    draw_text(
        ax, 1374, 247,
        r"• Reuses basis $U_u \in \mathbb{R}^{256\times 32}$"
        "\n"
        r"  and fold-train mean $\mu_u^F$"
        "\n"
        r"• Only missing $u \notin \Omega$ decoded"
        "\n• 224-d residual stays 0",
        fs=7.1, color="#334155", linespacing=1.22,
    )

    draw_arrow(ax, 1465, 326, 1465, 342, color="#0284c7", lw=1.5, ms=10)

    # Step 2 inside Merged Block: Trimodal Slot Assembly W1-4 (Y_top = 342 .. 494)
    draw_box(ax, 1366, 342, 198, 152, fc="#ffffff", ec="#059669", lw=1.2, r=6.0, zorder=4)
    draw_badge(
        ax, 1374, 348, 182, 20,
        "2. Slot Assembly W1-4 (Eq. 5)",
        fc="#ecfdf5", ec="#059669", tc="#065f46", fs=7.1, lw=0.8,
    )
    draw_text(
        ax, 1465, 375,
        r"$\tilde{p}_i^\Omega = [\tilde{p}_{i,R}^\Omega \;\Vert\; \tilde{p}_{i,W}^\Omega \;\Vert\; \tilde{p}_{i,T}^\Omega] \in \mathbb{R}^{768}$",
        fs=7.8, weight="bold", color="#064e3b", ha="center",
    )
    draw_box(ax, 1374, 397, 182, 46, fc="#f8fafc", ec="#94a3b8", lw=0.8, r=4.0, zorder=5)
    draw_text(
        ax, 1465, 402,
        r"Visible $m \in \Omega$:  $\tilde{p}_{i,m}^\Omega = p_{i,m}^\Omega$ (Raw)",
        fs=7.15, weight="bold", color="#059669", ha="center",
    )
    draw_text(
        ax, 1465, 421,
        r"Missing $u \notin \Omega$:  $\tilde{p}_{i,u}^\Omega = \hat{p}_{i,u}^\Omega$ (Rec.)",
        fs=7.15, weight="bold", color="#0284c7", ha="center",
    )
    draw_text(
        ax, 1374, 451,
        "Fixed order [RNA | WSI | Text]\n"
        "Zero distortion on visible slots",
        fs=7.05, color="#334155", linespacing=1.22,
    )

    draw_arrow(ax, 1465, 494, 1465, 510, color="#334155", lw=1.5, ms=10)

    # Step 3 inside Merged Block: Frozen I07 Linear Cox Risk Head (Y_top = 510 .. 686)
    draw_box(ax, 1366, 510, 198, 176, fc="#ffffff", ec="#1e293b", lw=1.4, r=6.0, zorder=4)
    draw_badge(
        ax, 1374, 516, 182, 20,
        "3. Frozen I07 Cox Head (Eq. 6)",
        fc="#e2e8f0", ec="#475569", tc="#0f172a", fs=7.1, lw=0.8,
    )
    draw_text(
        ax, 1465, 542,
        r"$\hat{h}_i^\Omega = w^\top \tilde{p}_i^\Omega + b_{\mathrm{risk}} \in \mathbb{R}$",
        fs=8.1, weight="bold", color="#0f172a", ha="center",
    )
    draw_text(
        ax, 1465, 562,
        r"$w = [w_R;\, w_W;\, w_T] \in \mathbb{R}^{768}$ (Frozen)",
        fs=7.1, color="#475569", ha="center",
    )
    draw_text(
        ax, 1465, 580,
        r"$\sum_{m\in\Omega} w_m^\top p_{i,m}^\Omega + \sum_{u\notin\Omega} w_u^\top \hat{p}_{i,u}^\Omega + b_{\mathrm{risk}}$",
        fs=6.95, color="#334155", ha="center",
    )

    # Final Performance Summary Box inside Step 3
    draw_box(ax, 1374, 604, 182, 74, fc="#1e3a8a", ec="#1d4ed8", lw=1.0, r=5.0, zorder=5)
    draw_text(
        ax, 1465, 610,
        "Ours (M6-a) 6-Missing Avg:",
        fs=7.3, weight="bold", color="#bfdbfe", ha="center",
    )
    draw_text(
        ax, 1465, 626,
        "C-index = 0.6657 (+1.38%)",
        fs=8.1, weight="bold", color="#ffffff", ha="center",
    )
    draw_text(
        ax, 1465, 644,
        "Wins 22 / 25 Folds vs. Zero-Fill",
        fs=7.0, weight="bold", color="#fde68a", ha="center",
    )
    draw_text(
        ax, 1465, 660,
        "All 5 TCGA Cohorts Positive",
        fs=6.95, color="#e0f2fe", ha="center",
    )

    # =========================================================================
    # 5. BOTTOM PASSTHROUGH LANE (W1-4 VISIBLE FEATURES: Y_top = 716 .. 748)
    # =========================================================================
    # Left segment from Block 1.4 into the W1-4 label pill
    draw_polyline_arrow(
        ax,
        [(155, 696), (155, 732), (242, 732)],
        color="#059669", lw=1.9, ms=10,
    )
    # Center W1-4 Passthrough Pill (text sits cleanly inside without any line striking through it!)
    draw_box(ax, 242, 716, 1146, 32, fc="#ecfdf5", ec="#059669", lw=1.3, r=6.0, zorder=3)
    draw_text(
        ax, 815, 724,
        r"W1-4 Visible Modality Direct Passthrough:  Observed $p_{i,m}^\Omega \in \mathbb{R}^{256}$ ($m \in \Omega$) "
        r"routes directly into Trimodal Slot Assembly $[\tilde{p}_{i,R}^\Omega \Vert \tilde{p}_{i,W}^\Omega \Vert \tilde{p}_{i,T}^\Omega]$ "
        "with zero low-rank projection loss",
        fs=7.9, weight="bold", color="#065f46", ha="center", zorder=5,
    )
    # Right segment from W1-4 label pill up along right margin into Step 2 Slot Assembly
    draw_polyline_arrow(
        ax,
        [(1388, 732), (1590, 732), (1590, 420), (1564, 420)],
        color="#059669", lw=1.9, ms=11,
    )

    return fig


def export_all(out_dir: Path) -> dict[str, Path]:
    """Generate framework.svg, framework.pdf, and 300-DPI framework.png in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "framework.svg"
    pdf_path = out_dir / "framework.pdf"
    png_path = out_dir / "framework.png"

    fig = build_figure()
    fig.savefig(svg_path, format="svg", metadata={"Date": None})
    fig.savefig(pdf_path, format="pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(png_path, format="png", dpi=300, metadata={"Software": None})
    plt.close(fig)
    return {"svg": svg_path, "pdf": pdf_path, "png": png_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TriModalSurv (I08) framework SVG, PDF, and PNG.")
    default_out = Path(__file__).resolve().parents[3] / "manuscript" / "bmc_initial_draft" / "figures"
    parser.add_argument("--out-dir", type=Path, default=default_out, help="Output directory for figures.")
    args = parser.parse_args()

    paths = export_all(args.out_dir)
    for fmt, p in paths.items():
        if not p.exists() or p.stat().st_size == 0:
            raise RuntimeError(f"Failed to generate {fmt}: {p}")
        print(f"[OK] {fmt.upper()}: {p} ({p.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
