"""Parse OCR text into structured BPCR data.

This is a heuristic-based parser for MVP.
Later versions can use layout analysis + LLM for higher accuracy.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

from app.models.schemas import (
    BPCRDocument,
    BPCRHeader,
    MaterialEntry,
    ProcessStep,
)
from app.core.ocr_engine import ocr_engine


class DocumentParser:
    """Extract structured fields from OCR output of a BPCR."""

    def parse_image_or_pdf(
        self,
        file_path: str,
        source_filename: str = None,
    ) -> BPCRDocument:
        """Main entry point: OCR + structure extraction."""
        from pathlib import Path
        path = Path(file_path)
        suffix = path.suffix.lower()

        page_texts: Dict[int, str] = {}
        all_blocks = []
        confidences = []

        if suffix == ".pdf":
            page_blocks = ocr_engine.extract_from_pdf(path)
            for page_num, blocks in page_blocks.items():
                page_texts[page_num] = "\n".join(b["text"] for b in blocks)
                all_blocks.extend(blocks)
                confidences.extend(b["confidence"] for b in blocks)
        else:
            # Image
            blocks = ocr_engine.extract_from_image(path)
            page_texts[1] = "\n".join(b["text"] for b in blocks)
            all_blocks = blocks
            confidences = [b["confidence"] for b in blocks]

        full_text = "\n\n".join(page_texts.values())
        avg_conf = sum(confidences) / len(confidences) if confidences else None

        doc = BPCRDocument(
            raw_text=full_text,
            page_texts=page_texts,
            source_filename=source_filename or path.name,
            ocr_confidence_avg=round(avg_conf, 4) if avg_conf else None,
        )

        # Extract structured sections
        doc.header = self._extract_header(full_text)
        doc.materials = self._extract_materials(full_text)
        doc.process_steps = self._extract_process_steps(full_text)

        logger.info(
            f"Parsed document: {doc.source_filename} | "
            f"Materials: {len(doc.materials)} | Steps: {len(doc.process_steps)} | "
            f"Avg OCR conf: {doc.ocr_confidence_avg}"
        )
        return doc

    def _extract_header(self, text: str) -> BPCRHeader:
        header = BPCRHeader()

        # Batch number patterns common in pharma
        batch_patterns = [
            r"(?:Batch\s*(?:No\.?|Number|#)\s*[:\-]?\s*)([A-Z0-9\-/]+)",
            r"(?:B\.?\s*No\.?\s*[:\-]?\s*)([A-Z0-9\-/]+)",
            r"(?:Lot\s*(?:No\.?|Number)\s*[:\-]?\s*)([A-Z0-9\-/]+)",
        ]
        for pat in batch_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                header.batch_number = m.group(1).strip()
                break

        # Product name / code
        prod_patterns = [
            r"(?:Product\s*(?:Name|Code)?\s*[:\-]?\s*)([A-Za-z0-9\s\-\(\)]{3,60})",
            r"(?:Item\s*(?:Code|Name)\s*[:\-]?\s*)([A-Za-z0-9\s\-]{3,40})",
        ]
        for pat in prod_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if len(val) > 3:
                    if any(c.isdigit() for c in val) and len(val) < 20:
                        header.product_code = val
                    else:
                        header.product_name = val
                    break

        # Dates
        date_patterns = [
            (r"(?:Mfg\.?\s*Date|Manufacturing\s*Date|Date\s*of\s*Manufacture)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", "mfg"),
            (r"(?:Exp\.?\s*Date|Expiry\s*Date|Expiration)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})", "exp"),
        ]
        for pat, kind in date_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    # Simple parse – improve later
                    raw = m.group(1)
                    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%m/%d/%Y"):
                        try:
                            dt = datetime.strptime(raw, fmt).date()
                            if kind == "mfg":
                                header.manufacturing_date = dt
                            else:
                                header.expiry_date = dt
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

        # Document number / revision
        doc_no = re.search(r"(?:Document\s*(?:No\.?|Number)|Doc\.?\s*No\.?)\s*[:\-]?\s*([A-Z0-9\-/]+)", text, re.I)
        if doc_no:
            header.document_number = doc_no.group(1).strip()

        rev = re.search(r"(?:Rev(?:ision)?\.?\s*(?:No\.?)?)\s*[:\-]?\s*([A-Z0-9\.]+)", text, re.I)
        if rev:
            header.revision = rev.group(1).strip()

        return header

    def _extract_materials(self, text: str) -> List[MaterialEntry]:
        """Very basic material table extraction – will be improved with layout models."""
        materials = []

        # Look for common material table headers
        # This is a placeholder heuristic. Real implementation needs table detection.
        lines = text.splitlines()
        in_material_section = False

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["material", "ingredient", "raw material", "rm code", "item code"]):
                in_material_section = True
                continue
            if in_material_section and any(k in lower for k in ["process", "step", "procedure", "equipment"]):
                break

            if in_material_section and len(line.strip()) > 5:
                # crude attempt to split
                parts = re.split(r"\s{2,}|\t", line.strip())
                if len(parts) >= 2:
                    entry = MaterialEntry(
                        material_name=parts[0] if parts else None,
                        material_code=parts[1] if len(parts) > 1 else None,
                    )
                    # try to find numbers
                    nums = re.findall(r"[\d\.]+", line)
                    if nums:
                        try:
                            entry.quantity_required = float(nums[0])
                            if len(nums) > 1:
                                entry.quantity_issued = float(nums[1])
                        except ValueError:
                            pass
                    materials.append(entry)

        return materials[:50]  # safety limit

    def _extract_process_steps(self, text: str) -> List[ProcessStep]:
        steps = []
        # Look for numbered steps
        step_pattern = re.compile(
            r"(?:Step\s*)?(\d+(?:\.\d+)*)[\.\)]\s+(.{10,120})",
            re.IGNORECASE
        )
        for m in step_pattern.finditer(text):
            steps.append(ProcessStep(
                step_number=m.group(1),
                description=m.group(2).strip()[:200],
            ))
        return steps[:100]


document_parser = DocumentParser()
