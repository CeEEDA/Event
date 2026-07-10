"""Tests for the umlaut-free Software-Dossier PDF endpoint.

Verifies:
 1. GET /api/system/downloads/dossier returns 200, application/pdf, >800 KB
 2. PDF text layer contains NO German umlauts (ä ö ü Ä Ö Ü ß) on any page
 3. (Optional) OCR of rendered pages finds <= 5 umlaut-looking chars
    (OCR misreads tolerated; >5 would be problematic)
"""
import os
import io
import pytest
import requests
import fitz  # PyMuPDF

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read from frontend .env
    try:
        with open("/app/frontend/.env") as fh:
            for ln in fh:
                if ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

UMLAUTS = ["\u00e4", "\u00f6", "\u00fc", "\u00c4", "\u00d6", "\u00dc", "\u00df"]
PDF_URL = f"{BASE_URL}/api/system/downloads/dossier"


@pytest.fixture(scope="module")
def pdf_bytes():
    resp = requests.get(PDF_URL, timeout=60)
    assert resp.status_code == 200, f"Endpoint returned {resp.status_code}: {resp.text[:300]}"
    ct = resp.headers.get("content-type", "")
    assert "application/pdf" in ct, f"Wrong content-type: {ct}"
    return resp.content


class TestDossierEndpoint:
    def test_endpoint_returns_pdf(self, pdf_bytes):
        assert pdf_bytes[:4] == b"%PDF", "Response is not a PDF (missing %PDF header)"

    def test_pdf_size_over_800kb(self, pdf_bytes):
        size_kb = len(pdf_bytes) / 1024
        assert size_kb > 800, f"PDF is only {size_kb:.0f} KB, expected > 800 KB"


class TestDossierUmlautFree:
    def test_text_layer_has_no_umlauts(self, pdf_bytes):
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_with_umlauts = []
        for i, page in enumerate(doc, start=1):
            text = page.get_text()
            hits = {ch: text.count(ch) for ch in UMLAUTS if ch in text}
            if hits:
                # Grab a couple of sample lines for the report
                samples = []
                for line in text.splitlines():
                    if any(u in line for u in UMLAUTS):
                        samples.append(line.strip()[:160])
                        if len(samples) >= 3:
                            break
                pages_with_umlauts.append((i, hits, samples))
        n_pages = doc.page_count
        doc.close()

        if pages_with_umlauts:
            details = "\n".join(
                f"  Page {p}: {h} | samples={s}" for p, h, s in pages_with_umlauts
            )
            pytest.fail(
                f"Text layer contains umlauts on {len(pages_with_umlauts)}/{n_pages} page(s):\n{details}"
            )

    def test_ocr_umlauts_tolerance(self, pdf_bytes):
        """Optional OCR check - <=5 umlaut hits total tolerated (OCR misreads)."""
        try:
            import pytesseract  # noqa
            from PIL import Image  # noqa
        except Exception as e:
            pytest.skip(f"OCR dependencies missing: {e}")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_hits = 0
        per_page = []
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                text = pytesseract.image_to_string(img, lang="deu")
            except pytesseract.TesseractError:
                text = pytesseract.image_to_string(img)
            hits = sum(text.count(ch) for ch in UMLAUTS)
            if hits:
                per_page.append((i, hits))
            total_hits += hits
        doc.close()

        print(f"OCR umlaut hits total={total_hits}, per_page={per_page}")
        assert total_hits <= 5, (
            f"OCR found {total_hits} umlaut occurrences (tolerance 5). "
            f"Per-page: {per_page}"
        )
