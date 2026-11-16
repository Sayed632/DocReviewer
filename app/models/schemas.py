"""Pydantic models for BPCR data and review results."""

from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    OBSERVATION = "observation"
    INFO = "info"


class ALCOAPrinciple(str, Enum):
    ATTRIBUTABLE = "Attributable"
    LEGIBLE = "Legible"
    CONTEMPORANEOUS = "Contemporaneous"
    ORIGINAL = "Original"
    ACCURATE = "Accurate"
    COMPLETE = "Complete"
    CONSISTENT = "Consistent"
    ENDURING = "Enduring"
    AVAILABLE = "Available"


class Finding(BaseModel):
    """Single non-compliance or observation."""
    principle: ALCOAPrinciple
    severity: Severity
    location: str                          # e.g. "Page 3 / Step 4.2 / Operator Signature"
    description: str
    extracted_value: Optional[str] = None
    expected: Optional[str] = None
    recommendation: Optional[str] = None


class MaterialEntry(BaseModel):
    """Single material used in a batch."""
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    batch_lot_no: Optional[str] = None
    quantity_required: Optional[float] = None
    quantity_issued: Optional[float] = None
    quantity_used: Optional[float] = None
    quantity_returned: Optional[float] = None
    unit: Optional[str] = None
    reconciliation_status: Optional[str] = None   # OK / Discrepancy
    remarks: Optional[str] = None


class ProcessStep(BaseModel):
    """One manufacturing / process step."""
    step_number: Optional[str] = None
    description: Optional[str] = None
    parameter: Optional[str] = None
    target_value: Optional[str] = None
    actual_value: Optional[str] = None
    unit: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    operator: Optional[str] = None
    checked_by: Optional[str] = None
    remarks: Optional[str] = None


class BPCRHeader(BaseModel):
    """Header information of a Batch Production and Control Record."""
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    batch_number: Optional[str] = None
    batch_size: Optional[str] = None
    manufacturing_date: Optional[date] = None
    expiry_date: Optional[date] = None
    manufacturing_site: Optional[str] = None
    document_number: Optional[str] = None
    revision: Optional[str] = None
    page_count: Optional[int] = None


class BPCRDocument(BaseModel):
    """Full structured representation of a reviewed BPCR."""
    header: BPCRHeader = Field(default_factory=BPCRHeader)
    materials: List[MaterialEntry] = Field(default_factory=list)
    process_steps: List[ProcessStep] = Field(default_factory=list)
    raw_text: Optional[str] = None
    page_texts: Dict[int, str] = Field(default_factory=dict)
    findings: List[Finding] = Field(default_factory=list)
    overall_status: str = "Pending Review"   # Compliant / Non-Compliant / Needs Review
    review_timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_filename: Optional[str] = None
    ocr_confidence_avg: Optional[float] = None


class ReviewRequest(BaseModel):
    """API request for reviewing a document."""
    strict_alcoa: bool = True
    extract_materials: bool = True
    extract_steps: bool = True


class ReviewResponse(BaseModel):
    """API response after review."""
    success: bool
    document: Optional[BPCRDocument] = None
    message: str = ""
    excel_path: Optional[str] = None
