"""FastAPI application entry point for DocReviewer."""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
import tempfile
from loguru import logger

from app.config import settings
from app.models.schemas import ReviewResponse, BPCRDocument
from app.core.document_parser import document_parser
from app.core.alcoa_checker import ALCOAChecker
from app.core.excel_exporter import excel_exporter

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Pharmaceutical BPCR (Batch Production and Control Record) Reviewer",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "message": "Upload a BPCR (PDF or image) to /review",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/review", response_model=ReviewResponse)
async def review_bpcr(
    file: UploadFile = File(...),
    strict_alcoa: bool = True,
    export_excel: bool = True,
    append_reconciliation: bool = True,
):
    """
    Main endpoint: Upload a filled BPCR (PDF or image) and receive structured review.
    """
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported file type: {suffix}. Allowed: {allowed}")

    # Save temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        logger.info(f"Processing uploaded file: {file.filename}")

        # 1. Parse (OCR + structure)
        document = document_parser.parse_image_or_pdf(
            tmp_path,
            source_filename=file.filename,
        )

        # 2. ALCOA++ checks
        checker = ALCOAChecker(strict=strict_alcoa)
        checker.check(document)

        excel_path = None
        recon_path = None

        # 3. Export
        if export_excel:
            excel_path = str(excel_exporter.export_single_review(document))

        if append_reconciliation:
            recon_path = str(excel_exporter.append_to_reconciliation_workbook(document))

        return ReviewResponse(
            success=True,
            document=document,
            message=f"Review completed. Status: {document.overall_status}. "
                    f"Findings: {len(document.findings)}",
            excel_path=excel_path,
        )

    except Exception as e:
        logger.exception("Review failed")
        raise HTTPException(500, f"Review failed: {str(e)}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/exports")
def list_exports():
    """List available exported Excel files."""
    files = list(settings.EXPORTS_DIR.glob("*.xlsx"))
    return {
        "count": len(files),
        "files": [f.name for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)],
    }
