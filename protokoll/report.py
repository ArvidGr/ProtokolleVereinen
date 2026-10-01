"""Erzeugt das PDF-Prüfprotokoll (Layout wie ZOPF „TEST PROTOCOL“)."""
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.utils import ImageReader  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from . import config  # noqa: E402
from .parser import TestReport  # noqa: E402

NAVY = colors.Color(0.173, 0.2, 0.412)
ACCENT = colors.Color(0.357, 0.42, 0.71)
ROW_ALT = colors.Color(0.925, 0.933, 0.965)
GRID = colors.Color(0.69, 0.745, 0.773)
TEXT = colors.HexColor("#333333")
SUBTLE = colors.HexColor("#B0C4DE")
PASS_FG, PASS_BG = colors.HexColor("#2E7D32"), colors.HexColor("#E8F5E9")
FAIL_FG, FAIL_BG = colors.HexColor("#C62828"), colors.HexColor("#FFEBEE")

PAGE_W, PAGE_H = A4
MARGIN_X = 70.866
TABLE_W = PAGE_W - 2 * MARGIN_X
COL1_W = 141.73

CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, leading=10, textColor=TEXT)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("head", parent=CELL_B, textColor=colors.white)


def _fmt(v: float) -> str:
    return f"{v:.1f}"


# --- Tabellen / Boxen ---------------------------------------------------------

def _table(title: str, rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(title, HEAD), Paragraph("Value", HEAD)]]
    data += [[Paragraph(k, CELL_B), Paragraph(v, CELL)] for k, v in rows]
    t = Table(data, colWidths=[COL1_W, TABLE_W - COL1_W])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, NAVY),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, NAVY),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, NAVY),
    ]
    for i in range(1, len(data)):
        style.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT if i % 2 == 0 else colors.white))
    t.setStyle(TableStyle(style))
    return t


def _result_box(report: TestReport) -> Table:
    fg, bg = (PASS_FG, PASS_BG) if report.passed else (FAIL_FG, FAIL_BG)
    word = "PASSED" if report.passed else "FAILED"
    big = ParagraphStyle("res", fontName="Helvetica-Bold", fontSize=13, leading=16,
                         textColor=fg, alignment=TA_CENTER)
    cells = [[Paragraph(f"Overall Result: {word}", big)]]
    if not report.passed and report.error:
        small = ParagraphStyle("err", parent=CELL, textColor=fg, alignment=TA_CENTER)
        cells.append([Paragraph(_esc(report.error), small)])
    t = Table(cells, colWidths=[TABLE_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 2, fg),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _WideImage(Flowable):
    """Bild, das breiter als der Textrahmen sein darf (zentriert auf der Seite)."""

    def __init__(self, png: bytes, width: float, height: float):
        super().__init__()
        self.img = ImageReader(io.BytesIO(png))
        self.w, self.h = width, height

    BAR_H = 8

    def wrap(self, avail_w, avail_h):
        self._avail_w = avail_w
        return avail_w, self.h + self.BAR_H + 10

    def draw(self):
        x = (self._avail_w - self.w) / 2
        self.canv.drawImage(self.img, x, 0, self.w, self.h, mask="auto")
        self.canv.setFillColor(NAVY)
        self.canv.rect(x + 18, self.h + 10, self.w - 36, self.BAR_H, stroke=0, fill=1)


# --- Diagramm -----------------------------------------------------------------

def _chart_png(report: TestReport, width_pt: float, height_pt: float) -> bytes | None:
    mod = report.modules.get("TimeCycle")
    if mod is None:
        return None
    ch = mod.channels
    series = [
        (config.CH_VLINK, "V_DC_Link in V [V]", "#2C3369", "v"),
        (config.CH_TEMP_DUT, "DUT Temp1 in °C [°C]", "#F28C28", "t"),
        (config.CH_TEMP_AMBIENT, "Temp_Ambient in °C [°C]", "#2E8B3E", "t"),
        (config.CH_CURRENT, "DUT I_Phase in A_rms [A]", "#D62728", "i"),
    ]
    if not any(ch.get(name) for name, *_ in series):
        return None

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7})
    fig, ax_v = plt.subplots(figsize=(width_pt / 72, height_pt / 72), dpi=300)
    ax_t = ax_v.twinx()
    ax_i = ax_v.twinx()
    ax_i.spines["right"].set_position(("axes", 1.17))
    axes = {"v": ax_v, "t": ax_t, "i": ax_i}

    handles = []
    for name, label, color, axis in series:
        values = ch.get(name)
        if not values:
            continue
        x = [k * mod.interval_s for k in range(len(values))]
        (h,) = axes[axis].plot(x, values, color=color, linewidth=0.9, label=label)
        handles.append(h)

    ax_v.set_ylim(0, 1000)
    ax_i.set_ylim(bottom=0)
    ax_v.set_xlabel("Time [s]")
    ax_v.set_ylabel("[V]")
    ax_t.set_ylabel("[°C]")
    ax_i.set_ylabel("[A]")
    ax_v.grid(True, color="#E6E8F0", linewidth=0.5)
    ax_v.set_title("Measurement Data", color="#2C3369", fontweight="bold", fontsize=9)
    for a in axes.values():
        a.tick_params(colors="#444444", labelsize=6.5)
        for s in a.spines.values():
            s.set_color("#AAB4C0")
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=6.5,
               frameon=True, edgecolor="#AAB4C0")
    fig.tight_layout(rect=(0, 0.08, 1, 1))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300)
    plt.close(fig)
    return buf.getvalue()


# --- Seite --------------------------------------------------------------------

def _draw_page(canvas, doc, report: TestReport, date_str: str) -> None:
    canvas.saveState()
    # Kopfband
    canvas.setFillColor(NAVY)
    canvas.rect(0, PAGE_H - 90.7, PAGE_W, 90.7, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H - 93.5, PAGE_W, 2.8, stroke=0, fill=1)
    logo = config.asset_path("zopf_logo.png")
    if logo.exists():
        canvas.drawImage(str(logo), 39.7, PAGE_H - 72.4, 141.7, 40, mask="auto")
    right = PAGE_W - 39.7
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawRightString(right, PAGE_H - 36, "TEST PROTOCOL")
    canvas.setFillColor(SUBTLE)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(right, PAGE_H - 55, f"DUT: {report.dut_name}  |  Test Module: TimeCycle")
    canvas.drawRightString(right, PAGE_H - 75, f"Date: {date_str}")
    # Fußband
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, PAGE_W, 39.7, stroke=0, fill=1)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 39.7, PAGE_W, 1.4, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 7)
    for i, line in enumerate(config.FOOTER_LINES):
        canvas.drawString(39.7, 24 - i * 11, line)
    if doc.page > 1 or getattr(doc, "_multi_page", False):
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawRightString(right, 18, f"Page {doc.page}")
    canvas.restoreState()


def _story(report: TestReport, date_str: str) -> list:
    story: list = [
        _table("General Information", [
            ("Date", date_str),
            ("DUT", report.dut_name),
            ("Item No", report.item_no),
            ("Serial No", report.serial_no),
            ("Operator", report.operator),
        ]),
        Spacer(1, 7),
        _result_box(report),
        Spacer(1, 6),
    ]

    tc = report.modules.get("TimeCycle")
    prep = report.modules.get("Preparation")
    p = tc.parameters if tc else {}
    rows = [
        ("Number of Cycles", p.get("NumberCycles", "")),
        ("Vlink", prep.parameters.get("Vlink", "") if prep else ""),
        ("F_Switch in Hz", p.get("Fsw", "")),
        ("F_Out in Hz", p.get("Ffund", "")),
        ("Duration High Load in s", p.get("HIGH.Time", "")),
        ("I_Phase High Load in A_rms", p.get("HIGH.Iphase", "")),
        ("Duration Low Load in s", p.get("LOW.Time", "")),
        ("Current Low Load in A_rms", p.get("LOW.Iphase", "")),
    ]
    rows = [r for r in rows if r[1] != ""]
    if rows:
        story += [_table("Parameters", rows), Spacer(1, 8.5)]

    if tc:
        amb = tc.channels.get(config.CH_TEMP_AMBIENT)
        dut = tc.channels.get(config.CH_TEMP_DUT)
        if amb and dut:
            story += [_table("Temperature Data", [
                (f"Max Temp in °C ({config.TEMP_MARGIN_K} K above T_amb)",
                 _fmt(max(amb) + config.TEMP_MARGIN_K)),
                ("Temperature Measured in °C", _fmt(max(dut))),
            ])]

    chart_w, chart_h = 496.06, 249.45
    png = _chart_png(report, chart_w, chart_h)
    if png:
        story += [Spacer(1, 18), KeepTogether(_WideImage(png, chart_w, chart_h))]
    return story


def build_pdf(report: TestReport, out_path: Path) -> None:
    date_str = report.start_time.strftime("%d.%m.%Y %H:%M:%S") if report.start_time else ""
    story = _story(report, date_str)

    def make_doc(target):
        return SimpleDocTemplate(
            target, pagesize=A4,
            leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=130.7, bottomMargin=50,
            title=f"Test Protocol {report.serial_no}", author="ZOPF Energieanlagen GmbH",
            subject=f"{report.dut_name} {report.serial_no}",
        )

    def on_page(c, d):
        _draw_page(c, d, report, date_str)

    # Erst probeweise rendern, um zu wissen, ob es mehrere Seiten werden
    # (dann bekommt auch Seite 1 eine Seitenzahl).
    probe = make_doc(io.BytesIO())
    probe.build(list(story), onFirstPage=on_page, onLaterPages=on_page)
    multi = probe.page > 1

    doc = make_doc(str(out_path))
    doc._multi_page = multi
    doc.build(_story(report, date_str), onFirstPage=on_page, onLaterPages=on_page)
