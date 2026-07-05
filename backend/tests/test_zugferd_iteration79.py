"""
ZUGFeRD / Factur-X parser integration tests (Iteration 79)

Tests:
1) Unit tests of parse_zugferd_xml() against /tmp/zugferd_test.pdf
2) E2E reanalyze of doc 25b74df5-6384-4eff-bbd4-7858fa7f449c (Normann ZUGFeRD-Rechnung)
3) Full-text search for 'Normann' - must return the doc
4) Regression: STEINIGKE doc (4e4870b2-3f49-43f2-88ac-e3e8d1ea42fa) still has sender=Steinigke...
"""
import os
import sys
import time
import pytest
import requests

# Backend base URL from env (public preview URL)
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://fuel-truck-deploy.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "christian.ecker@eventenergie-deutschland.de"
ADMIN_PASSWORD = "qivbeb-Wodha1-sewram"

ZUGFERD_DOC_ID = "25b74df5-6384-4eff-bbd4-7858fa7f449c"
STEINIGKE_DOC_ID = "4e4870b2-3f49-43f2-88ac-e3e8d1ea42fa"
ZUGFERD_LOCAL_PDF = "/tmp/zugferd_test.pdf"


# ────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(api_client):
    r = api_client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} - {r.text[:200]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def authed(api_client, auth_token):
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


# ────────────────────────────────────────────────────────────────
# 1) Unit tests: ZUGFeRD parser on local PDF
# ────────────────────────────────────────────────────────────────
class TestZugferdParserUnit:
    def _load_parser(self):
        # Ensure backend dir is on sys.path
        sys.path.insert(0, "/app/backend")
        from services.zugferd_parser import (
            is_zugferd_pdf,
            extract_zugferd_xml,
            parse_zugferd_xml,
            try_zugferd_parse,
            merge_zugferd_into_ai_result,
        )
        return dict(
            is_zugferd_pdf=is_zugferd_pdf,
            extract_zugferd_xml=extract_zugferd_xml,
            parse_zugferd_xml=parse_zugferd_xml,
            try_zugferd_parse=try_zugferd_parse,
            merge_zugferd_into_ai_result=merge_zugferd_into_ai_result,
        )

    def test_is_zugferd_pdf_true(self):
        assert os.path.exists(ZUGFERD_LOCAL_PDF), "Local test PDF /tmp/zugferd_test.pdf fehlt"
        m = self._load_parser()
        assert m["is_zugferd_pdf"](ZUGFERD_LOCAL_PDF) is True

    def test_extract_and_parse_core_fields(self):
        m = self._load_parser()
        xml = m["extract_zugferd_xml"](ZUGFERD_LOCAL_PDF)
        assert xml, "extract_zugferd_xml gab None zurueck"
        assert "<?xml" in xml or "CrossIndustryInvoice" in xml
        data = m["parse_zugferd_xml"](xml)
        assert data, "parse_zugferd_xml gab leeres dict zurueck"

        # Sender - Kernfeld (Mathias Normann)
        assert "Normann" in (data.get("sender") or ""), f"sender={data.get('sender')!r}"
        assert "Mathias Normann" in (data.get("sender") or "")

        # Recipient - Kernfeld (Eventenergie)
        assert "Eventenergie" in (data.get("recipient") or ""), f"recipient={data.get('recipient')!r}"

        # Invoice number
        assert data.get("invoice_number") == "263015", f"invoice_number={data.get('invoice_number')!r}"

        # Date
        assert data.get("date") == "2026-06-23", f"date={data.get('date')!r}"

        # Amount
        assert data.get("amount") is not None
        assert abs(float(data["amount"]) - 1496.12) < 0.01, f"amount={data.get('amount')!r}"

        # Tax amount
        if data.get("tax_amount") is not None:
            assert abs(float(data["tax_amount"]) - 238.88) < 0.01, f"tax_amount={data.get('tax_amount')!r}"

        # IBAN - beginnt mit DE71 5705 (formatiert)
        iban = (data.get("iban") or "").replace(" ", "")
        assert iban.startswith("DE71570501200002000792") or iban.startswith("DE715705"), f"iban={data.get('iban')!r}"

    def test_try_zugferd_parse_convenience(self):
        m = self._load_parser()
        d = m["try_zugferd_parse"](ZUGFERD_LOCAL_PDF)
        assert d.get("sender") and "Normann" in d["sender"]

    def test_merge_authoritative_fields_override(self):
        m = self._load_parser()
        # Simuliere Ollama-Fehlklassifikation
        ai_bad = {
            "sender": "Eventenergie Deutschland",   # falsch (LLM)
            "recipient": "Max Morlock Stadion",     # falsch (LLM)
            "amount": 999.0,
            "iban": None,
            "full_text": "Original LLM text",
            "keywords": ["Transport"],
        }
        zug = m["try_zugferd_parse"](ZUGFERD_LOCAL_PDF)
        merged = m["merge_zugferd_into_ai_result"](ai_bad.copy(), zug)
        assert "Normann" in merged["sender"], "merge muss LLM-Sender ueberschreiben"
        assert "Eventenergie" in merged["recipient"], "merge muss LLM-Recipient ueberschreiben"
        assert merged["iban"] and "DE71" in merged["iban"].replace(" ", "")
        assert "Normann" in merged["full_text"], "full_text muss ZUGFeRD-Block enthalten (fuer Suche)"
        assert "Mathias Normann" in " ".join(str(k) for k in merged["keywords"]), \
            "keywords muessen um Absender ergaenzt sein"

    def test_merge_no_zugferd_data_is_noop(self):
        m = self._load_parser()
        ai = {"sender": "Steinigke Showtechnic GmbH", "amount": 100.0, "full_text": "x", "keywords": ["a"]}
        merged = m["merge_zugferd_into_ai_result"](ai.copy(), {})
        assert merged["sender"] == "Steinigke Showtechnic GmbH"
        assert merged["full_text"] == "x"
        assert merged["keywords"] == ["a"]


# ────────────────────────────────────────────────────────────────
# 2) End-to-End: Reanalyze + verify ai_metadata
# ────────────────────────────────────────────────────────────────
class TestZugferdReanalyzeE2E:
    def test_reanalyze_zugferd_doc(self, authed):
        # Trigger reanalyze
        r = authed.post(f"{API}/documents/{ZUGFERD_DOC_ID}/reanalyze", timeout=30)
        assert r.status_code in (200, 202), f"reanalyze status={r.status_code} body={r.text[:300]}"

        # Poll for ai_status=completed (max ~180 s)
        deadline = time.time() + 240
        last = None
        while time.time() < deadline:
            g = authed.get(f"{API}/documents/{ZUGFERD_DOC_ID}", timeout=30)
            if g.status_code == 200:
                last = g.json()
                if last.get("ai_status") == "completed":
                    break
                if last.get("ai_status") == "failed":
                    pytest.fail(f"ai_status=failed: {last.get('ai_error')}")
            time.sleep(5)

        assert last is not None, "GET /documents lieferte nichts"
        assert last.get("ai_status") == "completed", f"ai_status={last.get('ai_status')} nach 240s"

        md = last.get("ai_metadata") or {}
        sender = md.get("sender") or ""
        recipient = md.get("recipient") or ""
        iban = (md.get("iban") or "").replace(" ", "")
        folder_id = last.get("folder_id") or ""

        assert "Normann" in sender, f"ai_metadata.sender={sender!r}"
        assert "Mathias Normann" in sender
        assert "Eventenergie" in recipient, f"ai_metadata.recipient={recipient!r}"
        assert iban.startswith("DE715705"), f"iban={md.get('iban')!r}"
        assert folder_id == "rechnungseingang_eventenergie_deutschland_2026_06", f"folder_id={folder_id!r}"


# ────────────────────────────────────────────────────────────────
# 3) Full-text search bug: 'Normann' must find the doc
# ────────────────────────────────────────────────────────────────
class TestZugferdSearch:
    def test_search_for_normann_finds_doc(self, authed):
        r = authed.get(f"{API}/documents/search", params={"q": "Normann"}, timeout=30)
        assert r.status_code == 200, f"search status={r.status_code}: {r.text[:300]}"
        body = r.json()
        # accept both list or {results: [...]}
        results = body if isinstance(body, list) else (body.get("results") or body.get("documents") or [])
        ids = [d.get("id") or d.get("doc_id") or d.get("_id") for d in results]
        assert ZUGFERD_DOC_ID in ids, f"Doc {ZUGFERD_DOC_ID} nicht in Suchergebnissen fuer 'Normann'. IDs={ids[:10]}"


# ────────────────────────────────────────────────────────────────
# 4) Regression: STEINIGKE (kein ZUGFeRD) - sender bleibt korrekt
# ────────────────────────────────────────────────────────────────
class TestZugferdRegression:
    def test_steinigke_sender_unchanged(self, authed):
        g = authed.get(f"{API}/documents/{STEINIGKE_DOC_ID}", timeout=30)
        assert g.status_code == 200, f"GET /{STEINIGKE_DOC_ID} status={g.status_code}"
        doc = g.json()
        md = doc.get("ai_metadata") or {}
        sender = md.get("sender") or ""
        assert "Steinigke" in sender, f"Regression: STEINIGKE sender={sender!r} (erwartete 'Steinigke Showtechnic GmbH')"
