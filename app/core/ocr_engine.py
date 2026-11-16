"""OCR + Handwriting Recognition engine using PaddleOCR."""

from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import numpy as np
from loguru import logger

from app.config import settings


class OCREngine:
    """
    Wrapper around PaddleOCR for printed + handwritten text extraction.
    Designed for pharmaceutical form documents (BPCR).
    """

    def __init__(self):
        self._ocr = None
        self._initialized = False

    def _lazy_init(self):
        if self._initialized:
            return
        try:
            from paddleocr import PaddleOCR
            logger.info("Initializing PaddleOCR (this may take a moment on first run)...")
            self._ocr = PaddleOCR(
                use_angle_cls=True,
                lang=settings.OCR_LANG,
                use_gpu=settings.OCR_USE_GPU,
                show_log=False,
                det_db_thresh=0.3,
                det_db_box_thresh=0.5,
            )
            self._initialized = True
            logger.info("PaddleOCR initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise RuntimeError(
                "PaddleOCR initialization failed. "
                "Ensure paddlepaddle and paddleocr are installed correctly."
            ) from e

    def extract_from_image(
        self,
        image: Union[str, Path, np.ndarray],
        confidence_threshold: float = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract text blocks from a single image.

        Returns list of dicts:
        [
            {
                "text": "...",
                "confidence": 0.95,
                "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
                "is_handwritten": bool   # heuristic for now
            },
            ...
        ]
        """
        self._lazy_init()
        threshold = confidence_threshold or settings.OCR_CONFIDENCE_THRESHOLD

        result = self._ocr.ocr(str(image) if not isinstance(image, np.ndarray) else image, cls=True)

        blocks = []
        if not result or not result[0]:
            return blocks

        for line in result[0]:
            if not line:
                continue
            bbox, (text, conf) = line
            if conf < threshold:
                continue

            # Simple heuristic: lower confidence + irregular spacing often = handwriting
            is_handwritten = conf < 0.85  # can be improved later with a classifier

            blocks.append({
                "text": text.strip(),
                "confidence": round(float(conf), 4),
                "bbox": bbox,
                "is_handwritten": is_handwritten,
            })

        return blocks

    def extract_text_only(self, image: Union[str, Path, np.ndarray]) -> str:
        """Return concatenated plain text from an image."""
        blocks = self.extract_from_image(image)
        return "\n".join(b["text"] for b in blocks)

    def extract_from_pdf(self, pdf_path: Union[str, Path]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Convert PDF pages to images and run OCR on each.
        Returns {page_number: [blocks]}
        """
        from pdf2image import convert_from_path

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Converting PDF to images: {pdf_path.name}")
        pages = convert_from_path(str(pdf_path), dpi=200)

        results = {}
        for i, page_img in enumerate(pages, start=1):
            logger.info(f"OCR page {i}/{len(pages)}")
            # Convert PIL to numpy for PaddleOCR
            img_np = np.array(page_img)
            blocks = self.extract_from_image(img_np)
            results[i] = blocks

        return results

    def get_full_text_from_pdf(self, pdf_path: Union[str, Path]) -> Dict[int, str]:
        """Return {page_num: plain_text}."""
        page_blocks = self.extract_from_pdf(pdf_path)
        return {
            page: "\n".join(b["text"] for b in blocks)
            for page, blocks in page_blocks.items()
        }


# Singleton instance
ocr_engine = OCREngine()
