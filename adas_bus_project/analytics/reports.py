"""PDF report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def generate_pdf(destination: Path, stats: dict, events: list[dict]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Install reportlab to generate PDF reports.") from exc

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm)
    story = [
        Paragraph("Crowd Track AI - Operational Report", styles["Title"]),
        Paragraph(f"Generated {datetime.now():%d %B %Y, %H:%M}", styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph("Educational and research prototype. Not a safety-certified automotive system.", styles["Italic"]),
        Spacer(1, 8 * mm),
    ]
    summary = [
        ["Metric", "Value"],
        ["Objects in current frame", str(stats.get("total", 0))],
        ["Current risk score", f'{stats.get("risk", 0)} / 100'],
        ["Logged alerts", str(len(events))],
        ["Average processing rate", f'{stats.get("fps", 0)} FPS'],
    ]
    table = Table(summary, colWidths=[95 * mm, 55 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16232E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#9CA7B0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 8 * mm), Paragraph("Recent Alerts", styles["Heading2"])])
    rows = [["Time", "Object", "Zone", "Risk", "Event"]]
    for event in events[:15]:
        rows.append([
            event["timestamp"].replace("T", " "),
            f'{event["object_type"]} #{event["track_id"]}',
            event["zone"],
            event["risk_level"],
            event["event_type"],
        ])
    events_table = Table(rows, colWidths=[34 * mm, 28 * mm, 39 * mm, 18 * mm, 51 * mm], repeatRows=1)
    events_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16232E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#AAB3BA")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(events_table)
    doc.build(story)
