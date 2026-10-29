"""
Reporting and Export Module
Generates downloadable CSV manifests and executive PDF optimization audits.
"""

import io
import pandas as pd
from datetime import datetime
from typing import Tuple

def generate_inventory_csv(df: pd.DataFrame) -> bytes:
    """Exports the complete calculated inventory table to clean CSV bytes."""
    export_cols = [
        "sku", "name", "category", "supplier_name", "abc_class",
        "current_stock", "safety_stock", "reorder_point", "eoq",
        "optimal_target", "unit_cost", "unit_price", "current_valuation",
        "trapped_cash", "alert_status", "days_of_supply"
    ]
    available_cols = [c for c in export_cols if c in df.columns]
    csv_str = df[available_cols].to_csv(index=False)
    return csv_str.encode('utf-8')

def generate_forecast_error_csv(forecast_df: pd.DataFrame) -> bytes:
    """Exports demand history and forecast error metrics to CSV bytes."""
    cols = ["date", "sku", "actual_demand", "forecast_demand", "forecast_error", "abs_error", "abs_pct_error"]
    available_cols = [c for c in cols if c in forecast_df.columns]
    csv_str = forecast_df[available_cols].to_csv(index=False)
    return csv_str.encode('utf-8')

def generate_executive_pdf_report(
    kpis: dict,
    top_overstocked: pd.DataFrame,
    critical_items: pd.DataFrame
) -> Tuple[bytes, str]:
    """
    Generates an executive-level PDF audit report.
    Uses ReportLab if installed; otherwise falls back to a clean formatted text-based document.
    """
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#475569'),
            spaceAfter=14
        )
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#1e3a8a'),
            spaceBefore=12,
            spaceAfter=8
        )

        # Header
        story.append(Paragraph("<b>INVENTORY OPTIMIZATION & WORKING CAPITAL AUDIT</b>", title_style))
        story.append(Paragraph(f"Generated: {timestamp_str} | Enterprise Supply Chain Diagnostics", subtitle_style))
        story.append(Spacer(1, 10))

        # KPI Summary Table
        story.append(Paragraph("<b>1. Executive KPI Summary</b>", section_style))
        kpi_data = [
            ["Metric", "Value", "Operational Significance"],
            ["Total Inventory Valuation", f"₹{kpis.get('total_inventory_value', 0):,.2f}", f"{kpis.get('total_skus', 0)} Active Monitored Items"],
            ["Total Trapped Cash", f"₹{kpis.get('total_trapped_cash', 0):,.2f}", f"{kpis.get('trapped_pct', 0):.1f}% of capital recoverable"],
            ["Stockout Risk Rate", f"{kpis.get('stockout_risk_pct', 0):.1f}%", f"{kpis.get('critical_count', 0)} SKUs below Safety Stock"],
            ["Annual Turnover Rate", f"{kpis.get('turnover_rate', 0):.2f}x", "Velocity of capital rotation"]
        ]
        kpi_table = Table(kpi_data, colWidths=[160, 140, 240])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 14))

        # Critical Stockout Threats Table
        story.append(Paragraph("<b>2. Critical Stockout Hazards (Below Safety Stock)</b>", section_style))
        if not critical_items.empty:
            crit_data = [["SKU", "Name", "Stock", "Safety Stock", "Reorder Point", "Supplier"]]
            for _, r in critical_items.head(8).iterrows():
                crit_data.append([
                    str(r.get("sku", "")),
                    str(r.get("name", ""))[:20],
                    f"{int(r.get('current_stock', 0)):,}",
                    f"{float(r.get('safety_stock', 0)):.1f}",
                    f"{float(r.get('reorder_point', 0)):.1f}",
                    str(r.get("supplier_name", ""))[:18]
                ])
            crit_table = Table(crit_data, colWidths=[90, 130, 60, 80, 80, 100])
            crit_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#b91c1c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fef2f2')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(crit_table)
        else:
            story.append(Paragraph("Zero items currently operating below safety stock.", styles['Normal']))
        story.append(Spacer(1, 14))

        # Top Trapped Working Capital Table
        story.append(Paragraph("<b>3. Top Trapped Working Capital Recovery Opportunities</b>", section_style))
        if not top_overstocked.empty:
            over_data = [["SKU", "ABC", "Current Stock", "Optimal Target", "Trapped Cash (₹)", "Days Supply"]]
            for _, r in top_overstocked.head(8).iterrows():
                over_data.append([
                    str(r.get("sku", "")),
                    f"Class {r.get('abc_class', '')}",
                    f"{int(r.get('current_stock', 0)):,}",
                    f"{float(r.get('optimal_target', 0)):.0f}",
                    f"₹{float(r.get('trapped_cash', 0)):,.2f}",
                    f"{float(r.get('days_of_supply', 0)):.1f}d"
                ])
            over_table = Table(over_data, colWidths=[100, 60, 90, 90, 110, 90])
            over_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fdfa')]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(over_table)
        else:
            story.append(Paragraph("No significant trapped working capital detected.", styles['Normal']))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes, "application/pdf"

    except ImportError:
        # Graceful fallback: Formatted plain-text/markdown audit manifest
        text_report = f"""================================================================================
INVENTORY OPTIMIZATION & WORKING CAPITAL AUDIT REPORT
Generated: {timestamp_str}
================================================================================

1. EXECUTIVE KPI SUMMARY
--------------------------------------------------------------------------------
- Total Inventory Valuation:   ₹{kpis.get('total_inventory_value', 0):,.2f}
- Total Trapped Working Cash:  ₹{kpis.get('total_trapped_cash', 0):,.2f} ({kpis.get('trapped_pct', 0):.1f}% recoverable)
- Stockout Risk Percentage:    {kpis.get('stockout_risk_pct', 0):.1f}% ({kpis.get('critical_count', 0)} critical SKUs)
- Annual Inventory Turnover:   {kpis.get('turnover_rate', 0):.2f}x
- Total Active Monitored SKUs: {kpis.get('total_skus', 0)}

2. CRITICAL STOCKOUT THREATS (Current Stock <= Safety Stock)
--------------------------------------------------------------------------------
{critical_items[['sku', 'name', 'current_stock', 'safety_stock', 'reorder_point']].to_string() if not critical_items.empty else "Zero critical stockout hazards detected."}

3. TOP TRAPPED WORKING CAPITAL OPPORTUNITIES
--------------------------------------------------------------------------------
{top_overstocked[['sku', 'abc_class', 'current_stock', 'optimal_target', 'trapped_cash']].to_string() if not top_overstocked.empty else "Inventory is operating lean."}

================================================================================
End of Audit Report
"""
        return text_report.encode('utf-8'), "text/plain"
