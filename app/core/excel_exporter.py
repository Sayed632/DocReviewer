"""Excel export and multi-batch material reconciliation."""

from pathlib import Path
from datetime import datetime
from typing import List, Optional
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from loguru import logger

from app.config import settings
from app.models.schemas import BPCRDocument, MaterialEntry


class ExcelExporter:
    """Handles creation and appending of BPCR review data into Excel workbooks."""

    def __init__(self):
        self.exports_dir = settings.EXPORTS_DIR
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def export_single_review(
        self,
        document: BPCRDocument,
        filename: Optional[str] = None,
    ) -> Path:
        """Export one reviewed BPCR into a structured Excel file."""
        if not filename:
            batch = document.header.batch_number or "UNKNOWN"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"BPCR_Review_{batch}_{ts}.xlsx"

        path = self.exports_dir / filename

        wb = Workbook()

        # --- Summary sheet ---
        ws = wb.active
        ws.title = "Review Summary"

        header_font = Font(bold=True, size=12)
        title_font = Font(bold=True, size=14, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1F4E79")
        critical_fill = PatternFill("solid", fgColor="FF6B6B")
        major_fill = PatternFill("solid", fgColor="FFA500")
        ok_fill = PatternFill("solid", fgColor="90EE90")

        ws["A1"] = "BPCR Review Summary – DocReviewer"
        ws["A1"].font = title_font
        ws["A1"].fill = header_fill
        ws.merge_cells("A1:D1")

        summary_data = [
            ("Source File", document.source_filename),
            ("Batch Number", document.header.batch_number),
            ("Product", document.header.product_name or document.header.product_code),
            ("Manufacturing Date", str(document.header.manufacturing_date) if document.header.manufacturing_date else ""),
            ("Document No.", document.header.document_number),
            ("Revision", document.header.revision),
            ("Overall Status", document.overall_status),
            ("OCR Avg Confidence", document.ocr_confidence_avg),
            ("Review Timestamp (UTC)", document.review_timestamp.isoformat()),
            ("Total Findings", len(document.findings)),
        ]

        for i, (k, v) in enumerate(summary_data, start=3):
            ws[f"A{i}"] = k
            ws[f"A{i}"].font = header_font
            ws[f"B{i}"] = v

        # Findings sheet
        ws2 = wb.create_sheet("Findings")
        ws2.append(["Principle", "Severity", "Location", "Description", "Extracted Value", "Recommendation"])
        for cell in ws2[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.font = Font(bold=True, color="FFFFFF")

        for f in document.findings:
            ws2.append([
                f.principle.value,
                f.severity.value,
                f.location,
                f.description,
                f.extracted_value or "",
                f.recommendation or "",
            ])

        # Materials sheet
        ws3 = wb.create_sheet("Materials")
        mat_headers = [
            "Material Code", "Material Name", "Lot/Batch No",
            "Qty Required", "Qty Issued", "Qty Used", "Qty Returned",
            "Unit", "Reconciliation Status", "Remarks"
        ]
        ws3.append(mat_headers)
        for cell in ws3[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill

        for m in document.materials:
            ws3.append([
                m.material_code, m.material_name, m.batch_lot_no,
                m.quantity_required, m.quantity_issued, m.quantity_used,
                m.quantity_returned, m.unit, m.reconciliation_status, m.remarks
            ])

        # Process Steps
        ws4 = wb.create_sheet("Process Steps")
        step_headers = [
            "Step No", "Description", "Parameter", "Target", "Actual",
            "Unit", "Start Time", "End Time", "Operator", "Checked By", "Remarks"
        ]
        ws4.append(step_headers)
        for cell in ws4[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill

        for s in document.process_steps:
            ws4.append([
                s.step_number, s.description, s.parameter, s.target_value,
                s.actual_value, s.unit, s.start_time, s.end_time,
                s.operator, s.checked_by, s.remarks
            ])

        # Adjust column widths (basic)
        for ws in wb.worksheets:
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except Exception:
                        pass
                ws.column_dimensions[column].width = min(max_length + 2, 50)

        wb.save(path)
        logger.info(f"Exported single review → {path}")
        return path

    def append_to_reconciliation_workbook(
        self,
        document: BPCRDocument,
        workbook_path: Optional[Path] = None,
    ) -> Path:
        """
        Append material data of this batch into a multi-batch reconciliation Excel.
        Creates the file if it does not exist.
        Warns when approaching practical Excel limits.
        """
        if workbook_path is None:
            workbook_path = self.exports_dir / "Material_Reconciliation_All_Batches.xlsx"

        if not document.header.batch_number:
            logger.warning("Cannot append reconciliation – batch number missing.")
            return workbook_path

        # Prepare rows for this batch
        rows = []
        for m in document.materials:
            rows.append({
                "Batch Number": document.header.batch_number,
                "Product": document.header.product_name or document.header.product_code,
                "Mfg Date": document.header.manufacturing_date,
                "Material Code": m.material_code,
                "Material Name": m.material_name,
                "Material Lot": m.batch_lot_no,
                "Qty Required": m.quantity_required,
                "Qty Issued": m.quantity_issued,
                "Qty Used": m.quantity_used,
                "Qty Returned": m.quantity_returned,
                "Unit": m.unit,
                "Recon Status": m.reconciliation_status,
                "Remarks": m.remarks,
                "Review Timestamp": document.review_timestamp,
            })

        if not rows:
            logger.info("No materials to append for reconciliation.")
            return workbook_path

        df_new = pd.DataFrame(rows)

        if workbook_path.exists():
            # Append
            df_existing = pd.read_excel(workbook_path, sheet_name="All Batches")
            current_rows = len(df_existing)

            if current_rows + len(df_new) > settings.EXCEL_MAX_ROWS_HARD:
                raise RuntimeError(
                    f"Excel hard limit approached ({settings.EXCEL_MAX_ROWS_HARD} rows). "
                    "Please start a new reconciliation workbook."
                )

            if current_rows + len(df_new) > settings.EXCEL_MAX_ROWS_WARNING:
                logger.warning(
                    f"⚠ Approaching Excel practical limit. Current rows: {current_rows}. "
                    f"Consider starting a new sheet/workbook soon."
                )

            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_combined = df_new
            current_rows = 0

        # Write
        with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
            df_combined.to_excel(writer, sheet_name="All Batches", index=False)

            # Add a simple summary sheet
            summary = df_combined.groupby("Batch Number").agg(
                Material_Count=("Material Code", "count"),
                First_Review=("Review Timestamp", "min"),
            ).reset_index()
            summary.to_excel(writer, sheet_name="Batch Summary", index=False)

        logger.info(
            f"Appended {len(df_new)} material rows for batch {document.header.batch_number} "
            f"→ {workbook_path} (total rows now: {len(df_combined)})"
        )
        return workbook_path


excel_exporter = ExcelExporter()
