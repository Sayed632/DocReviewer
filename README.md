# DocReviewer – AI-Powered Pharmaceutical BPCR Reviewer

**Batch Production and Control Record (BPCR) Intelligent Review System**

An AI agent that reviews filled pharmaceutical Batch Production and Control Records with the same rigor as a trained QA reviewer.

## Core Purpose

The system can:

1. **Ingest** filled BPCRs via smartphone camera or uploaded scanned documents (PDF / images)
2. **Read** both printed and handwritten text accurately
3. **Understand** the document structure and standard instructions
4. **Check compliance** against ALCOA++ principles and the instructions printed on the form itself
5. **Extract** structured data into Excel for trending
6. **Perform Material Reconciliation** across multiple batches into a single Excel workbook (with automatic warning when sheet limits are approached)

## Key Features (MVP Roadmap)

### Phase 1 – Foundation (Current)
- Document upload (image / PDF)
- OCR + Handwriting Recognition (PaddleOCR)
- Basic text extraction and layout awareness
- Structured data model for BPCR
- Excel export of extracted data
- ALCOA++ rule engine (basic rules)

### Phase 2
- Full material reconciliation engine
- Multi-batch trending workbook
- Advanced ALCOA++ checks (Contemporaneous, Attributable signatures, etc.)
- Human-in-the-loop review interface
- Batch comparison & trend charts

### Phase 3
- Mobile-optimized capture flow
- Signature verification support
- Integration with existing QMS / LIMS (future)
- On-premise deployment option

## Tech Stack

| Layer              | Technology                          | Reason |
|--------------------|-------------------------------------|--------|
| OCR + HTR          | **PaddleOCR**                       | Strong handwriting recognition + multi-language |
| Backend API        | FastAPI                             | Fast, modern, easy to extend |
| Quick UI           | Streamlit                           | Rapid review interface for QA users |
| Data Handling      | pandas + openpyxl                   | Excel-centric pharmaceutical workflows |
| Document Processing| pdf2image, Pillow, opencv-python    | Robust image & PDF handling |
| Rules Engine       | Custom Python + optional LLM        | ALCOA++ compliance logic |

## Project Structure

```
DocReviewer/
├── app/
│   ├── api/                  # FastAPI routes
│   ├── core/                 # Core business logic
│   │   ├── ocr_engine.py
│   │   ├── document_parser.py
│   │   ├── alcoa_checker.py
│   │   ├── reconciliation.py
│   │   └── excel_exporter.py
│   ├── models/               # Pydantic schemas
│   └── utils/
├── streamlit_app.py          # Reviewer UI
├── data/
│   ├── samples/              # Sample BPCRs (anonymized)
│   └── exports/              # Generated Excel files
├── tests/
├── requirements.txt
└── README.md
```

## Getting Started

```bash
# 1. Clone
git clone https://github.com/Sayed632/DocReviewer.git
cd DocReviewer

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run Streamlit UI (recommended for first use)
streamlit run streamlit_app.py

# 5. Or run FastAPI
uvicorn app.main:app --reload
```

## ALCOA++ Compliance Focus

The system evaluates entries against:

- **A**ttributable
- **L**egible
- **C**ontemporaneous
- **O**riginal
- **A**ccurate
- **C**omplete
- **C**onsistent
- **E**nduring
- **A**vailable

Non-conformances are flagged with severity and suggested corrective action.

## Material Reconciliation

All batches are appended into a single Excel workbook by default.  
When approaching Excel practical limits (row count / performance), the system issues a clear warning and recommends starting a new sheet or workbook.

## Security Note

This repository may contain configuration for processing regulated documents.  
Do **not** commit real patient or commercial batch data. Use anonymized samples only.

## License

MIT License – see [LICENSE](LICENSE)

---

**Status**: Active development – Building from scratch (November 2026)
