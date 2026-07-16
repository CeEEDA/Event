"""
Iteration 86 tests:
 - GET /api/incoming-invoices/bank-status
 - POST /api/incoming-invoices/bulk-mark-paid  (empty / bogus / real / >500)
 - Regression: single-doc mark-paid / mark-creditcard / mark-sepa
 - Regression: POST /api/incoming-invoices/fints/auto-match
 - ZUGFeRD end-to-end via analyze_document_fallback (in-process)
"""
import os
import sys
import io
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://fuel-truck-deploy.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

# Preview admin credentials (from /app/memory/test_credentials.md)
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password"


# ────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(api_client):
    r = api_client.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


# ────────────────────────────────────────────────
# GET /bank-status
# ────────────────────────────────────────────────
class TestBankStatus:
    def test_requires_token(self, api_client):
        r = api_client.get(f"{API}/incoming-invoices/bank-status", timeout=30)
        # FastAPI Query(...) mandatory → 422
        assert r.status_code in (401, 403, 422), f"unexpected status={r.status_code}"

    def test_bogus_token_rejected(self, api_client):
        r = api_client.get(
            f"{API}/incoming-invoices/bank-status",
            params={"token": "invalid-token-xyz"},
            timeout=30,
        )
        assert r.status_code in (401, 403), f"bogus token got {r.status_code}"

    def test_admin_returns_banks(self, api_client, token):
        r = api_client.get(
            f"{API}/incoming-invoices/bank-status",
            params={"token": token},
            timeout=30,
        )
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
        body = r.json()
        assert "banks" in body and isinstance(body["banks"], list), body
        assert "count" in body and isinstance(body["count"], int), body
        assert body["count"] == len(body["banks"])
        # each bank has core keys
        for b in body["banks"]:
            assert "key" in b
            assert "name" in b
            assert "enabled" in b
            assert "has_state" in b


# ────────────────────────────────────────────────
# POST /bulk-mark-paid
# ────────────────────────────────────────────────
class TestBulkMarkPaid:
    def test_empty_list_400(self, api_client, token):
        r = api_client.post(
            f"{API}/incoming-invoices/bulk-mark-paid",
            params={"token": token},
            json={"ids": []},
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"
        detail = (r.json() or {}).get("detail", "")
        assert "leer" in detail.lower(), f"detail={detail!r}"

    def test_bogus_id_returns_zero_updated(self, api_client, token):
        r = api_client.post(
            f"{API}/incoming-invoices/bulk-mark-paid",
            params={"token": token},
            json={"ids": ["nope-1"]},
            timeout=30,
        )
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        body = r.json()
        assert body.get("ok") is True
        assert body.get("requested") == 1
        assert body.get("updated") == 0

    def test_over_500_returns_400(self, api_client, token):
        ids = [f"dummy-{i}" for i in range(501)]
        r = api_client.post(
            f"{API}/incoming-invoices/bulk-mark-paid",
            params={"token": token},
            json={"ids": ids},
            timeout=60,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:200]}"

    def test_real_open_invoice_gets_marked_paid(self, api_client, token):
        # 1) List invoices
        rlist = api_client.get(
            f"{API}/incoming-invoices",
            params={"token": token},
            timeout=60,
        )
        assert rlist.status_code == 200, rlist.text[:300]
        invoices = rlist.json().get("invoices") or []
        # find an open (not paid, not cc, not sepa) invoice
        candidates = [
            i for i in invoices
            if i.get("status") in ("open", "overdue")
            and not i.get("paid")
            and not i.get("paid_by_creditcard")
            and not i.get("paid_by_sepa")
        ]
        if not candidates:
            pytest.skip("No open/overdue invoice available for bulk-mark-paid E2E test")

        target = candidates[0]
        target_id = target["id"]
        # 2) Bulk mark it paid
        rbulk = api_client.post(
            f"{API}/incoming-invoices/bulk-mark-paid",
            params={"token": token},
            json={"ids": [target_id]},
            timeout=30,
        )
        assert rbulk.status_code == 200, rbulk.text[:300]
        body = rbulk.json()
        assert body["ok"] is True
        assert body["requested"] == 1
        assert body["updated"] == 1
        # 3) GET list and confirm status=paid, paid=true
        rlist2 = api_client.get(
            f"{API}/incoming-invoices",
            params={"token": token},
            timeout=60,
        )
        assert rlist2.status_code == 200
        after = {i["id"]: i for i in (rlist2.json().get("invoices") or [])}
        assert target_id in after, f"target invoice {target_id} disappeared"
        assert after[target_id]["status"] == "paid"
        assert after[target_id]["paid"] is True
        assert (after[target_id].get("paid_source") or "").startswith("bulk-manuell")


# ────────────────────────────────────────────────
# Regression: single-doc mark endpoints
# ────────────────────────────────────────────────
class TestRegressionSingleMark:
    def test_mark_paid_missing_doc_404(self, api_client, token):
        r = api_client.post(
            f"{API}/incoming-invoices/does-not-exist-xyz/mark-paid",
            params={"token": token},
            timeout=30,
        )
        assert r.status_code == 404

    def test_mark_creditcard_missing_doc_404(self, api_client, token):
        r = api_client.post(
            f"{API}/incoming-invoices/does-not-exist-xyz/mark-creditcard",
            params={"token": token, "remember_sender": "false"},
            timeout=30,
        )
        assert r.status_code == 404

    def test_mark_sepa_missing_doc_404(self, api_client, token):
        r = api_client.post(
            f"{API}/incoming-invoices/does-not-exist-xyz/mark-sepa",
            params={"token": token, "remember_sender": "false"},
            timeout=30,
        )
        assert r.status_code == 404


# ────────────────────────────────────────────────
# Regression: fints/auto-match callable, no 500
# ────────────────────────────────────────────────
class TestFintsAutoMatch:
    def test_no_500(self, api_client, token):
        r = api_client.post(
            f"{API}/incoming-invoices/fints/auto-match",
            params={"token": token, "days_back": 7},
            timeout=90,
        )
        # May return 200 (OK) or 400 (no FinTS config), but not 500
        assert r.status_code != 500, f"500 error: {r.text[:500]}"
        assert r.status_code in (200, 400, 403), f"unexpected status={r.status_code}: {r.text[:300]}"


# ────────────────────────────────────────────────
# ZUGFeRD end-to-end via analyze_document_fallback
# ────────────────────────────────────────────────
class TestZugferdEnd2End:
    def _build_pdf(self) -> bytes:
        import fitz
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rsm:CrossIndustryInvoice '
            'xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" '
            'xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100" '
            'xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">\n'
            '  <rsm:ExchangedDocument>\n'
            '    <ram:ID>RE-2026-042</ram:ID>\n'
            '    <ram:TypeCode>380</ram:TypeCode>\n'
            '    <ram:IssueDateTime><udt:DateTimeString format="102">20260212</udt:DateTimeString></ram:IssueDateTime>\n'
            '  </rsm:ExchangedDocument>\n'
            '  <rsm:SupplyChainTradeTransaction>\n'
            '    <ram:ApplicableHeaderTradeAgreement>\n'
            '      <ram:SellerTradeParty>\n'
            '        <ram:Name>Mathias Normann Elektrotechnik</ram:Name>\n'
            '      </ram:SellerTradeParty>\n'
            '      <ram:BuyerTradeParty>\n'
            '        <ram:Name>Eventenergie Deutschland GmbH &amp; Co. KG</ram:Name>\n'
            '      </ram:BuyerTradeParty>\n'
            '    </ram:ApplicableHeaderTradeAgreement>\n'
            '    <ram:ApplicableHeaderTradeSettlement>\n'
            '      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>\n'
            '      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>\n'
            '        <ram:GrandTotalAmount>1234.56</ram:GrandTotalAmount>\n'
            '      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>\n'
            '    </ram:ApplicableHeaderTradeSettlement>\n'
            '  </rsm:SupplyChainTradeTransaction>\n'
            '</rsm:CrossIndustryInvoice>\n'
        ).encode("utf-8")

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "ZUGFeRD Test Invoice")
        doc.embfile_add(
            "factur-x.xml",
            xml,
            filename="factur-x.xml",
            ufilename="factur-x.xml",
            desc="Factur-X",
        )
        buf = doc.tobytes()
        doc.close()
        return buf

    def test_analyze_document_fallback_uses_zugferd(self):
        sys.path.insert(0, "/app/backend")
        from services.heuristic_analyzer import analyze_document_fallback

        pdf_bytes = self._build_pdf()
        r = analyze_document_fallback(pdf_bytes, "test.pdf")

        assert r.get("_authoritative_source") == "zugferd_xml", r
        assert r.get("sender") == "Mathias Normann Elektrotechnik", r.get("sender")
        assert r.get("recipient") and "Eventenergie Deutschland" in r["recipient"], r.get("recipient")
        assert abs(float(r.get("amount") or 0) - 1234.56) < 0.01, r.get("amount")
        assert r.get("invoice_number") == "RE-2026-042", r.get("invoice_number")
        assert r.get("date") == "2026-02-12", r.get("date")
        assert r.get("suggested_folder") == "rechnungseingang_eventenergie_deutschland", r.get("suggested_folder")
