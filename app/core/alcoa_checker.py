"""ALCOA++ compliance rule engine for BPCR documents."""

from typing import List
from loguru import logger

from app.models.schemas import (
    BPCRDocument,
    Finding,
    Severity,
    ALCOAPrinciple,
)


class ALCOAChecker:
    """
    Rule-based ALCOA++ checker.
    Designed to be extended with more sophisticated LLM-assisted checks later.
    """

    def __init__(self, strict: bool = True):
        self.strict = strict

    def check(self, document: BPCRDocument) -> List[Finding]:
        findings: List[Finding] = []

        findings.extend(self._check_header(document))
        findings.extend(self._check_legibility(document))
        findings.extend(self._check_completeness(document))
        findings.extend(self._check_materials(document))
        findings.extend(self._check_process_steps(document))

        # Overall status
        critical_or_major = any(
            f.severity in (Severity.CRITICAL, Severity.MAJOR) for f in findings
        )
        if critical_or_major:
            document.overall_status = "Non-Compliant"
        elif findings:
            document.overall_status = "Needs Review"
        else:
            document.overall_status = "Compliant"

        document.findings = findings
        logger.info(f"ALCOA++ check completed. Findings: {len(findings)}. Status: {document.overall_status}")
        return findings

    def _check_header(self, doc: BPCRDocument) -> List[Finding]:
        findings = []
        h = doc.header

        if not h.batch_number:
            findings.append(Finding(
                principle=ALCOAPrinciple.COMPLETE,
                severity=Severity.CRITICAL,
                location="Header / Batch Number",
                description="Batch number is missing or could not be extracted.",
                recommendation="Ensure batch number is clearly written and legible.",
            ))

        if not h.product_name and not h.product_code:
            findings.append(Finding(
                principle=ALCOAPrinciple.COMPLETE,
                severity=Severity.MAJOR,
                location="Header / Product Identification",
                description="Product name or code is missing.",
            ))

        if not h.manufacturing_date:
            findings.append(Finding(
                principle=ALCOAPrinciple.COMPLETE,
                severity=Severity.MAJOR,
                location="Header / Manufacturing Date",
                description="Manufacturing date is missing or unreadable.",
            ))

        return findings

    def _check_legibility(self, doc: BPCRDocument) -> List[Finding]:
        """Basic legibility checks based on OCR confidence."""
        findings = []

        if doc.ocr_confidence_avg is not None and doc.ocr_confidence_avg < 0.65:
            findings.append(Finding(
                principle=ALCOAPrinciple.LEGIBLE,
                severity=Severity.MAJOR,
                location="Document overall",
                description=f"Average OCR confidence is low ({doc.ocr_confidence_avg:.2f}). "
                            "Significant portions of the document may be illegible or poorly scanned.",
                recommendation="Re-scan the document at higher resolution or ensure handwriting is clear.",
            ))

        return findings

    def _check_completeness(self, doc: BPCRDocument) -> List[Finding]:
        findings = []

        if not doc.materials:
            findings.append(Finding(
                principle=ALCOAPrinciple.COMPLETE,
                severity=Severity.MAJOR if self.strict else Severity.MINOR,
                location="Material section",
                description="No material entries could be extracted. Material reconciliation may be incomplete.",
            ))

        if not doc.process_steps:
            findings.append(Finding(
                principle=ALCOAPrinciple.COMPLETE,
                severity=Severity.MAJOR if self.strict else Severity.OBSERVATION,
                location="Process steps",
                description="No process steps extracted. Key manufacturing data may be missing.",
            ))

        return findings

    def _check_materials(self, doc: BPCRDocument) -> List[Finding]:
        findings = []

        for i, mat in enumerate(doc.materials, start=1):
            loc = f"Material #{i} ({mat.material_name or mat.material_code or 'Unknown'})"

            # Quantity reconciliation check
            if (
                mat.quantity_issued is not None
                and mat.quantity_used is not None
                and mat.quantity_returned is not None
            ):
                calculated = mat.quantity_issued - mat.quantity_used - mat.quantity_returned
                if abs(calculated) > 0.01:  # tolerance
                    findings.append(Finding(
                        principle=ALCOAPrinciple.ACCURATE,
                        severity=Severity.MAJOR,
                        location=loc,
                        description=f"Material reconciliation discrepancy detected. "
                                    f"Issued ({mat.quantity_issued}) - Used ({mat.quantity_used}) "
                                    f"- Returned ({mat.quantity_returned}) ≠ 0",
                        extracted_value=str(calculated),
                        recommendation="Investigate and document the difference.",
                    ))

            if not mat.batch_lot_no:
                findings.append(Finding(
                    principle=ALCOAPrinciple.ATTRIBUTABLE,
                    severity=Severity.MINOR,
                    location=loc,
                    description="Material lot/batch number is missing.",
                ))

        return findings

    def _check_process_steps(self, doc: BPCRDocument) -> List[Finding]:
        findings = []

        for i, step in enumerate(doc.process_steps, start=1):
            loc = f"Step {step.step_number or i}"

            if step.actual_value is None and step.target_value is not None:
                findings.append(Finding(
                    principle=ALCOAPrinciple.COMPLETE,
                    severity=Severity.MAJOR,
                    location=loc,
                    description="Actual value is missing while a target value exists.",
                ))

            if not step.operator and self.strict:
                findings.append(Finding(
                    principle=ALCOAPrinciple.ATTRIBUTABLE,
                    severity=Severity.MINOR,
                    location=loc,
                    description="Operator identification is missing for this step.",
                ))

        return findings


alcoa_checker = ALCOAChecker()
