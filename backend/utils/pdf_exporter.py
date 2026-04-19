"""PDF report generator — professional multi-page layout."""
from __future__ import annotations

import io
import os
import pathlib
import tempfile
from datetime import datetime

# Logo: resolve relative to this file → project_root/frontend/public/logo.png
_HERE       = pathlib.Path(__file__).parent          # backend/utils/
_LOGO_PATH  = str(_HERE.parent.parent / "frontend" / "public" / "logo.png")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image,
    HRFlowable, KeepTogether, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as rl_canvas

# ── Constants ────────────────────────────────────────────────────────────────

ALL_TYPES = ["HSC", "MPP", "CMP", "CLP", "Myeloid", "Erythroid", "B_cell", "T_cell"]

# Same palette as App.jsx / CELL_COLOURS in the browser
TYPE_COLOURS = {
    "HSC":       "#1f77b4",
    "MPP":       "#aec7e8",
    "CMP":       "#ff7f0e",
    "CLP":       "#ffbb78",
    "Myeloid":   "#2ca02c",
    "Erythroid": "#98df8a",
    "B_cell":    "#d62728",
    "T_cell":    "#ff9896",
}

# Brand colours
C_ACCENT   = colors.HexColor("#1e40af")
C_ACCENT2  = colors.HexColor("#059669")
C_DARK     = colors.HexColor("#1f2937")
C_MID      = colors.HexColor("#6b7280")
C_LIGHT    = colors.HexColor("#f3f4f6")
C_BORDER   = colors.HexColor("#d1d5db")
C_HDR_BG   = colors.HexColor("#1e3a5f")
C_ALT_ROW  = colors.HexColor("#f0f4ff")
C_WHITE    = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Page template with header + footer ───────────────────────────────────────

class _ReportCanvas(rl_canvas.Canvas):
    """Adds persistent header (with logo) + footer on every page."""

    def __init__(self, *args, generated_at: str = "", logo_path: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._generated_at = generated_at
        self._logo_path    = logo_path
        self._saved_page_states: list = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_chrome(self._pageNumber, total)
            super().showPage()
        super().save()

    def _draw_chrome(self, page_num: int, total: int):
        self.saveState()
        w, h = A4

        # ── Header bar ──
        self.setFillColor(C_HDR_BG)
        self.rect(0, h - 14 * mm, w, 14 * mm, fill=1, stroke=0)

        # Logo in header (10×10 mm, vertically centered in 14 mm bar)
        if self._logo_path and os.path.exists(self._logo_path):
            logo_size = 10 * mm
            self.drawImage(
                self._logo_path,
                x=MARGIN,
                y=h - 14 * mm + (14 * mm - logo_size) / 2,
                width=logo_size, height=logo_size,
                preserveAspectRatio=True, mask="auto",
            )
            text_x = MARGIN + logo_size + 3 * mm
        else:
            text_x = MARGIN

        self.setFillColor(C_WHITE)
        self.setFont("Helvetica-Bold", 9)
        self.drawString(text_x, h - 9 * mm, "Hematopoiesis Simulator  v0.12")
        self.setFont("Helvetica", 9)
        self.drawRightString(w - MARGIN, h - 9 * mm, "Simulation Report")

        # ── Footer ──
        self.setStrokeColor(C_BORDER)
        self.setLineWidth(0.5)
        self.line(MARGIN, 12 * mm, w - MARGIN, 12 * mm)

        self.setFillColor(C_MID)
        self.setFont("Helvetica", 8)
        self.drawString(MARGIN, 7 * mm,
                        f"Hematopoiesis Simulator v0.12  ·  Generated: {self._generated_at}")
        self.drawRightString(w - MARGIN, 7 * mm, f"Page {page_num} of {total}")

        self.restoreState()


def _build_canvas_maker(generated_at: str, logo_path: str = ""):
    """Return a Canvas *class* (not a factory fn) with generated_at + logo baked in."""
    class _BoundCanvas(_ReportCanvas):
        def __init__(self, filename, **kwargs):
            kwargs.pop("doc", None)   # ReportLab injects this; Canvas rejects it
            super().__init__(filename, generated_at=generated_at,
                             logo_path=logo_path, **kwargs)
    return _BoundCanvas


# ── Matplotlib figures ────────────────────────────────────────────────────────

def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


DARK_BG   = "#111827"
GRID_COL  = "#374151"
TICK_COL  = "#9ca3af"

def _apply_dark_style(ax, fig):
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=TICK_COL, labelsize=9)
    ax.xaxis.label.set_color(TICK_COL)
    ax.yaxis.label.set_color(TICK_COL)
    ax.title.set_color("#e5e7eb")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_COL)
    ax.grid(color=GRID_COL, linewidth=0.5, linestyle="--", alpha=0.7)


def _make_population_figure(history: list[dict], target: int) -> str:
    step = max(1, len(history) // 1200)
    hist = history[::step]
    times  = [s["time"]  for s in hist]
    totals = [s["total"] for s in hist]

    # 6.7 × 3.6 in — extra height gives room for 2-row legend without clipping
    fig, ax = plt.subplots(figsize=(6.7, 3.6))
    _apply_dark_style(ax, fig)

    for ct in ALL_TYPES:
        vals = [s["population"].get(ct, 0) for s in hist]
        ax.plot(times, vals, color=TYPE_COLOURS[ct], lw=1.6, label=ct, alpha=0.9)

    ax.plot(times, totals, color="#e5e7eb", lw=2.2, ls="--", label="Total", zorder=5)

    if target and target < 999_990:
        ax.axhline(target, color="#6b7280", lw=1, ls=":", label=f"Target ({target:,})")

    ax.set_xlabel("Time (h)", fontsize=9)
    ax.set_ylabel("Cell count", fontsize=9)
    ax.set_title("Population over Time", fontsize=11, fontweight="bold", pad=6)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{int(v/1000)}k" if v >= 1000 else str(int(v))))

    handles, labels = ax.get_legend_handles_labels()
    leg = ax.legend(handles, labels, fontsize=7.5, ncol=5,
                    loc="upper center", bbox_to_anchor=(0.5, -0.28),
                    framealpha=0.15, labelcolor=TICK_COL, edgecolor=GRID_COL)
    leg.get_frame().set_facecolor(DARK_BG)

    # bottom=0.38 reserves ~1.37in for legend (2 rows at 7.5pt fit comfortably)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.38)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    fig.savefig(path, dpi=150, facecolor=DARK_BG)
    plt.close(fig)
    return path


def _make_stacked_figure(history: list[dict]) -> str:
    step = max(1, len(history) // 800)
    hist = history[::step]

    times  = [s["time"] for s in hist]
    totals = np.array([max(s["total"], 1) for s in hist], dtype=float)
    stacks = {ct: np.array([s["population"].get(ct, 0) for s in hist], dtype=float)
              for ct in ALL_TYPES}

    fig, ax = plt.subplots(figsize=(6.7, 3.2))
    _apply_dark_style(ax, fig)

    bottom = np.zeros(len(times))
    for ct in ALL_TYPES:
        frac = stacks[ct] / totals * 100
        ax.fill_between(times, bottom, bottom + frac,
                        color=_hex(TYPE_COLOURS[ct]), alpha=0.88, label=ct)
        bottom += frac

    ax.set_xlabel("Time (h)", fontsize=9)
    ax.set_ylabel("Fraction (%)", fontsize=9)
    ax.set_title("Cell-Type Composition", fontsize=11, fontweight="bold", pad=6)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}%"))

    patches = [mpatches.Patch(color=_hex(TYPE_COLOURS[ct]), label=ct) for ct in ALL_TYPES]
    leg = ax.legend(handles=patches, fontsize=7.5, ncol=4,
                    loc="upper center", bbox_to_anchor=(0.5, -0.28),
                    framealpha=0.15, labelcolor=TICK_COL, edgecolor=GRID_COL)
    leg.get_frame().set_facecolor(DARK_BG)

    fig.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.35)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)
    return path


# ── Table helpers ─────────────────────────────────────────────────────────────

def _table(rows, col_widths=None, header_bg=C_HDR_BG, alt=C_ALT_ROW, font_size=9):
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    style = [
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), font_size),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  6),
        ("TOPPADDING",    (0, 0), (-1, 0),  6),
        # Data rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, alt]),
        ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
        ("BOTTOMPADDING",  (0, 1), (-1, -1), 4),
        ("TOPPADDING",     (0, 1), (-1, -1), 4),
        # Grid
        ("GRID",     (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",(0, 0), (-1, 0),  1.0, header_bg),
        # Alignment
        ("VALIGN",   (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",    (1, 1), (-1, -1), "RIGHT"),
    ]
    t.setStyle(TableStyle(style))
    return t


def _section_heading(text: str, styles) -> list:
    """Returns [Spacer, heading paragraph, HR]."""
    return [
        Spacer(1, 6 * mm),
        Paragraph(text, styles["h2"]),
        HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceAfter=4),
    ]


def _coloured_dot(ct: str) -> str:
    """Inline HTML-style coloured square for cell type labels."""
    return f'<font color="{TYPE_COLOURS[ct]}">■</font>  {ct}'


# ── Main generator ────────────────────────────────────────────────────────────

def generate_pdf(session_data: dict) -> bytes:
    buf          = io.BytesIO()
    generated_at = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # ── Document setup ────────────────────────────────────────────────────────
    # Tight margins: header bar=14mm at top, footer text at 7mm from bottom.
    # Reduced from 34/28 mm → 20/16 mm, gaining ~26mm on page 2 so both
    # graphs + explain texts fit on a single page (~260mm content, 261mm available).
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=14 * mm + 6 * mm,   # 20mm: 14mm header bar + 6mm gap
        bottomMargin=8 * mm + 8 * mm, # 16mm: 8mm footer zone + 8mm gap
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame])])

    # ── Styles ────────────────────────────────────────────────────────────────
    base = getSampleStyleSheet()
    S = {
        "title": ParagraphStyle("title", parent=base["Normal"],
                                fontName="Helvetica-Bold", fontSize=22,
                                textColor=C_DARK, alignment=TA_CENTER,
                                spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"],
                                   fontName="Helvetica", fontSize=12,
                                   textColor=C_MID, alignment=TA_CENTER,
                                   spaceAfter=3),
        "badge": ParagraphStyle("badge", parent=base["Normal"],
                                fontName="Helvetica-Bold", fontSize=10,
                                textColor=C_ACCENT2, alignment=TA_CENTER,
                                spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Normal"],
                             fontName="Helvetica-Bold", fontSize=13,
                             textColor=C_ACCENT, spaceBefore=2, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=base["Normal"],
                             fontName="Helvetica-Bold", fontSize=10,
                             textColor=C_DARK, spaceBefore=4, spaceAfter=2),
        "normal": ParagraphStyle("normal", parent=base["Normal"],
                                 fontName="Helvetica", fontSize=10,
                                 textColor=C_DARK, spaceAfter=2),
        "small":  ParagraphStyle("small", parent=base["Normal"],
                                 fontName="Helvetica", fontSize=8,
                                 textColor=C_MID),
        "cell":   ParagraphStyle("cell", parent=base["Normal"],
                                 fontName="Helvetica", fontSize=9,
                                 textColor=C_DARK),
        "explain": ParagraphStyle("explain", parent=base["Normal"],
                                  fontName="Helvetica-Oblique", fontSize=9,
                                  textColor=colors.HexColor("#555555"),
                                  leading=13, spaceAfter=4),
    }

    EXPLAIN = {
        "params": (
            "Configuration parameters used in this simulation. These values control the dynamics "
            "of hematopoietic stem cell differentiation, including population regulation mechanisms "
            "(density control, niche signalling) and cell-state evolution (stress accumulation, "
            "epigenetic inheritance)."
        ),
        "results": (
            "Summary statistics of the final population state at the end of simulation. "
            "Total Cells is the final population size. "
            "Mean Stemness indicates average self-renewal capacity — higher values correspond to "
            "more primitive, stem-like cells. Mean Stress reflects cumulative division history "
            "and cellular ageing."
        ),
        "population": (
            "Temporal evolution of all eight cell types and total population. HSC (haematopoietic "
            "stem cells) are long-term repopulating cells; MPP (multipotent progenitors) have "
            "limited self-renewal. Downstream progenitors (CMP, CLP) and terminal effector cells "
            "are produced continuously. The dashed white line shows total cell count; the dotted "
            "grey line marks the homeostatic target."
        ),
        "composition": (
            "Stacked area chart showing the relative abundance (%) of each cell type over time. "
            "The full vertical extent represents 100 % of the population. Transitions between "
            "areas reflect changes in cell-type balance driven by asymmetric differentiation, "
            "symmetric commitment, and selective apoptosis."
        ),
        "summary": (
            "Detailed breakdown of final cell counts by type. Fraction (%) shows the proportion "
            "each type contributes to the total. Mean Stemness and Mean Stress are averaged across "
            "all cells of that type at simulation end. Terminal types (Myeloid, Erythroid, B_cell, "
            "T_cell) do not self-renew and are continuously produced and cleared."
        ),
    }

    story: list = []

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — Title + Parameters + Results
    # ══════════════════════════════════════════════════════════════════════════

    # ── Cover block ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("HEMATOPOIESIS SIMULATION", S["title"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Stochastic Cell Differentiation Model  ·  v0.12", S["subtitle"]))
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT))
    story.append(Spacer(1, 5 * mm))

    # Meta info row
    t_max = session_data.get("t_max", 0)
    final_time = session_data.get("final_time", 0)
    status_txt = "Completed Successfully" if session_data.get("final_time") else "Incomplete"
    meta_rows = [
        ["Generated", generated_at,   "Session ID", session_data.get("session_id", "—")],
        ["Duration",  f"{t_max} h",   "Final time", f"{final_time:.2f} h"],
        ["Seed",      str(session_data.get("seed", "—")), "Status", status_txt],
    ]
    meta_t = _table(meta_rows,
                    col_widths=[30*mm, 55*mm, 30*mm, 55*mm],
                    header_bg=C_HDR_BG, alt=C_ALT_ROW)
    story.append(meta_t)

    # ── Parameters ───────────────────────────────────────────────────────────
    story += _section_heading("Simulation Parameters", S)
    story.append(Paragraph(EXPLAIN["params"], S["explain"]))
    story.append(Spacer(1, 2 * mm))
    params = session_data.get("params", {})

    PARAM_LABELS = {
        "seed":                    "Random Seed",
        "t_max":                   "Duration (hours)",
        "target_population_size":  "Target Population Size",
        "inheritance_mode":        "Inheritance Mode",
        "stress_accumulation_rate":"Stress Accumulation Rate",
        "enable_target_population":"Target Population",
        "density_gamma":           "Density Strength (γ)",
        "density_beta":            "Density Beta (β)",
        "niche_strength":          "Niche Strength (k)",
        "crowding_threshold":      "Crowding Threshold",
        "crowding_apoptosis_rate": "Emergency Apoptosis Rate",
        "self_renewal_weight":     "HSC Self-Renewal Weight",
    }

    def _fmt(v):
        if isinstance(v, bool):
            return "Enabled" if v else "Disabled"
        if isinstance(v, float):
            return f"{v:.4g}"
        return str(v)

    param_rows  = [["Parameter", "Value", "Parameter", "Value"]]
    keys = list(PARAM_LABELS.keys())
    # Merge session-level seed/t_max with params dict
    combined = {"seed": session_data.get("seed", "—"),
                "t_max": t_max, **params}
    for i in range(0, len(keys), 2):
        k1, k2 = keys[i], keys[i+1] if i+1 < len(keys) else None
        v1 = _fmt(combined.get(k1, "—"))
        row = [PARAM_LABELS[k1], v1]
        if k2:
            row += [PARAM_LABELS[k2], _fmt(combined.get(k2, "—"))]
        else:
            row += ["", ""]
        param_rows.append(row)

    story.append(_table(param_rows, col_widths=[52*mm, 38*mm, 52*mm, 28*mm]))

    # ── Results summary ───────────────────────────────────────────────────────
    story += _section_heading("Final Results", S)
    story.append(Paragraph(EXPLAIN["results"], S["explain"]))
    story.append(Spacer(1, 2 * mm))
    stats = session_data.get("summary_stats", {})
    pop   = session_data.get("final_population", {})
    total = sum(pop.values()) or 1

    stat_rows = [
        ["Metric", "Value"],
        ["Total Cells",   f"{total:,}"],
        ["Mean Stemness", f"{stats.get('mean_stemness', 0):.4f}"],
        ["Mean Stress",   f"{stats.get('mean_stress',   0):.4f}"],
        ["Mean Bias",     f"{stats.get('mean_bias',     0):.4f}"],
    ]
    story.append(_table(stat_rows, col_widths=[80*mm, 90*mm]))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Graphs
    # ══════════════════════════════════════════════════════════════════════════
    history = session_data.get("history", [])
    tmp_files: list[str] = []

    # ── Compact graph-page styles (no leading Spacer/HR — keeps both charts on p.2) ──
    gh = ParagraphStyle("gh", parent=S["h2"], spaceBefore=0, spaceAfter=3)
    gc = ParagraphStyle("gc", parent=S["explain"], fontSize=8, leading=11, spaceAfter=2)

    # Available content height on A4 with current margins:
    #   297 - (20+14) top - (20+8) bottom = 235 mm
    # Layout budget:
    #   heading×2 ≈ 8mm, caption×2 ≈ 6mm, spacers ≈ 8mm → ~22mm overhead
    #   images: 110 + 100 = 210mm   total ≈ 232mm  ✓

    if history:
        story.append(Paragraph("Population Dynamics", gh))
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceAfter=3))
        story.append(Paragraph(EXPLAIN["population"], gc))

        target = int(params.get("target_population_size", 1000))
        pop_fig = _make_population_figure(history, target)
        tmp_files.append(pop_fig)
        story.append(Image(pop_fig, width=CONTENT_W, height=100 * mm))
        story.append(Spacer(1, 3 * mm))

        story.append(Paragraph("Cell-Type Composition", gh))
        story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceAfter=3))
        story.append(Paragraph(EXPLAIN["composition"], gc))

        stk_fig = _make_stacked_figure(history)
        tmp_files.append(stk_fig)
        story.append(Image(stk_fig, width=CONTENT_W, height=90 * mm))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — Detailed Cell Count Table
    # ══════════════════════════════════════════════════════════════════════════
    story += _section_heading("Cell Count Summary", S)
    story.append(Paragraph(EXPLAIN["summary"], S["explain"]))
    story.append(Spacer(1, 3 * mm))

    # Per-cell-type internal state means — computed from live population in SimulationSession
    per_type_stats = session_data.get("per_type_stats", {})

    det_rows = [["Cell Type", "Count", "Fraction", "Mean Stemness", "Mean Stress"]]
    for ct in ALL_TYPES:
        n    = pop.get(ct, 0)
        pct  = f"{n / total * 100:.1f}%"
        ct_s = per_type_stats.get(ct, {})
        if ct_s:
            mean_stem   = f"{ct_s.get('mean_stemness', 0):.3f}"
            mean_stress = f"{ct_s.get('mean_stress',   0):.3f}"
        else:
            mean_stem   = "—"
            mean_stress = "—"
        # Colour the cell type name
        ct_para = Paragraph(_coloured_dot(ct), S["cell"])
        det_rows.append([ct_para, f"{n:,}", pct, mean_stem, mean_stress])

    # Total row
    det_rows.append([
        Paragraph("<b>TOTAL</b>", S["cell"]),
        f"{total:,}", "100%", "—", "—",
    ])

    det_t = _table(det_rows,
                   col_widths=[48*mm, 28*mm, 28*mm, 38*mm, 28*mm],
                   header_bg=C_HDR_BG, alt=C_ALT_ROW, font_size=9)
    # Bold total row
    det_t.setStyle(TableStyle([
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e0e7ff")),
        ("LINEABOVE",  (0, -1), (-1, -1), 1.2, C_ACCENT),
    ]))
    story.append(det_t)

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "Generated by Hematopoiesis Simulator v0.12 — Stochastic CTMC Model",
        S["small"]))

    # ── Build ─────────────────────────────────────────────────────────────────
    canvas_maker = _build_canvas_maker(generated_at, logo_path=_LOGO_PATH)
    doc.build(story, canvasmaker=canvas_maker)

    total_pages = doc.page
    if total_pages >= 3:
        print(f"[PDF] ✓ {total_pages} pages — graphs fit on page 2, table on page 3")
    elif total_pages == 2:
        print(f"[PDF] ⚠ Only {total_pages} pages — graphs on page 2 but no table page!")
    else:
        print(f"[PDF] ✗ {total_pages} page(s) — graphs spilled past page 2, reduce heights!")

    pdf_bytes = buf.getvalue()
    for p in tmp_files:
        try:
            os.unlink(p)
        except OSError:
            pass
    return pdf_bytes
