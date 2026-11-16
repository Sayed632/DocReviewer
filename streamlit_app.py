"""
DocReviewer – Streamlit UI
Quick interface for pharmaceutical QA reviewers to upload and review BPCRs.
"""

import streamlit as st
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from app.config import settings
from app.core.document_parser import document_parser
from app.core.alcoa_checker import ALCOAChecker
from app.core.excel_exporter import excel_exporter
from app.models.schemas import Severity

st.set_page_config(
    page_title="DocReviewer – BPCR Reviewer",
    page_icon="📋",
    layout="wide",
)

st.title("📋 DocReviewer")
st.caption("AI-Powered Pharmaceutical Batch Production & Control Record Reviewer")

# Sidebar
with st.sidebar:
    st.header("Settings")
    strict_mode = st.checkbox("Strict ALCOA++ mode", value=True)
    export_excel = st.checkbox("Export Excel review", value=True)
    append_recon = st.checkbox("Append to Material Reconciliation workbook", value=True)
    st.markdown("---")
    st.markdown("**Supported formats**")
    st.markdown("PDF, PNG, JPG, TIFF, BMP")
    st.markdown("---")
    st.markdown(f"Version `{settings.APP_VERSION}`")

# Main upload
uploaded = st.file_uploader(
    "Upload filled BPCR (scanned PDF or image)",
    type=["pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp"],
)

if uploaded is not None:
    st.info(f"File: **{uploaded.name}** ({uploaded.size / 1024:.1f} KB)")

    if st.button("🔍 Start Review", type="primary", use_container_width=True):
        with st.spinner("Running OCR + ALCOA++ checks... This may take 20–60 seconds depending on document size."):
            # Save temp
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name

            try:
                # Parse
                document = document_parser.parse_image_or_pdf(
                    tmp_path,
                    source_filename=uploaded.name,
                )

                # ALCOA
                checker = ALCOAChecker(strict=strict_mode)
                checker.check(document)

                # Export
                excel_path = None
                if export_excel:
                    excel_path = excel_exporter.export_single_review(document)

                if append_recon:
                    excel_exporter.append_to_reconciliation_workbook(document)

                # ===== Results =====
                st.success(f"Review completed — **{document.overall_status}**")

                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Batch Number", document.header.batch_number or "—")
                col2.metric("Findings", len(document.findings))
                col3.metric("OCR Confidence", f"{document.ocr_confidence_avg:.0%}" if document.ocr_confidence_avg else "—")
                col4.metric("Materials Extracted", len(document.materials))

                # Header details
                with st.expander("📄 Document Header", expanded=True):
                    h = document.header
                    st.write({
                        "Product": h.product_name or h.product_code,
                        "Batch Number": h.batch_number,
                        "Manufacturing Date": str(h.manufacturing_date) if h.manufacturing_date else None,
                        "Expiry Date": str(h.expiry_date) if h.expiry_date else None,
                        "Document No.": h.document_number,
                        "Revision": h.revision,
                    })

                # Findings
                st.subheader("ALCOA++ Findings")
                if not document.findings:
                    st.success("No findings – document appears compliant under current rules.")
                else:
                    for f in document.findings:
                        color = {
                            Severity.CRITICAL: "🔴",
                            Severity.MAJOR: "🟠",
                            Severity.MINOR: "🟡",
                            Severity.OBSERVATION: "🔵",
                            Severity.INFO: "⚪",
                        }.get(f.severity, "⚪")

                        with st.container():
                            st.markdown(
                                f"{color} **{f.severity.value.upper()}** | "
                                f"`{f.principle.value}` | **{f.location}**"
                            )
                            st.write(f.description)
                            if f.recommendation:
                                st.caption(f"💡 {f.recommendation}")
                            st.divider()

                # Materials table
                if document.materials:
                    st.subheader("Materials Extracted")
                    import pandas as pd
                    mat_data = [
                        {
                            "Code": m.material_code,
                            "Name": m.material_name,
                            "Lot": m.batch_lot_no,
                            "Required": m.quantity_required,
                            "Issued": m.quantity_issued,
                            "Used": m.quantity_used,
                            "Returned": m.quantity_returned,
                            "Unit": m.unit,
                        }
                        for m in document.materials
                    ]
                    st.dataframe(pd.DataFrame(mat_data), use_container_width=True)

                # Download
                if excel_path:
                    with open(excel_path, "rb") as f:
                        st.download_button(
                            label="📥 Download Full Excel Review",
                            data=f,
                            file_name=Path(excel_path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

                # Raw text (debug)
                with st.expander("🔤 Raw OCR Text (for debugging)"):
                    st.text(document.raw_text[:5000] if document.raw_text else "No text extracted")

            except Exception as e:
                st.error(f"Review failed: {e}")
                st.exception(e)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

else:
    st.markdown("""
    ### How to use
    1. Upload a scanned BPCR (PDF preferred, or clear photo/scan of pages)
    2. Click **Start Review**
    3. Review the ALCOA++ findings and extracted data
    4. Download the Excel report for trending / records

    ### Current MVP Capabilities
    - OCR + handwriting recognition (PaddleOCR)
    - Header field extraction (batch no, product, dates…)
    - Basic material & process step extraction
    - ALCOA++ rule engine (Complete, Legible, Accurate, Attributable…)
    - Single-batch Excel report
    - Multi-batch Material Reconciliation workbook (auto-append)

    > **Note**: Extraction accuracy depends heavily on scan quality and handwriting clarity.
    > This is the foundation – we will continuously improve the parser and rules.
    """)
