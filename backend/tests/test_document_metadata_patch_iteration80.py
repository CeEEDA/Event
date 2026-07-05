"""Tests for PATCH /api/documents/{doc_id}/metadata (Iteration 80).

Feature: Inline-Edit von AI-Metadaten in der Dokumentenablage-Detailansicht.
Backend endpoint muss:
  - einzelne Felder aktualisieren, ohne andere zu ueberschreiben
  - manually_edited=True setzen
  - leere Strings / None entfernen das Feld
  - date und document_date synchron halten
"""
import copy
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "christian.ecker@eventenergie-deutschland.de"
ADMIN_PASSWORD = "qivbeb-Wodha1-sewram"

ZUGFERD_DOC_ID = "25b74df5-6384-4eff-bbd4-7858fa7f449c"
STEINIGKE_DOC_ID = "4e4870b2-3f49-43f2-88ac-e3e8d1ea42fa"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}


def _get_doc(doc_id, headers):
    r = requests.get(f"{API}/documents/{doc_id}", headers=headers, timeout=30)
    assert r.status_code == 200, f"GET doc {doc_id} failed: {r.text}"
    return r.json()


# --- Test: base PATCH updates single field, sets manually_edited, keeps others ---
def test_patch_updates_sender_only_and_marks_manually_edited(auth_headers):
    before = _get_doc(ZUGFERD_DOC_ID, auth_headers)
    original_meta = copy.deepcopy(before.get("ai_metadata") or {})

    new_sender = "Test Firma XY"
    r = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"sender": new_sender},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "updated"
    assert body.get("changed_fields") == ["sender"]
    updated_meta = body.get("ai_metadata")
    assert updated_meta is not None
    assert updated_meta.get("sender") == new_sender
    assert updated_meta.get("manually_edited") is True

    # Other important fields must be untouched
    for key in ("recipient", "iban", "invoice_number", "amount", "tax_amount", "bic", "reference"):
        if key in original_meta:
            assert updated_meta.get(key) == original_meta.get(key), \
                f"Field {key} was unexpectedly changed: {original_meta.get(key)} -> {updated_meta.get(key)}"

    # Restore original sender
    restore_val = original_meta.get("sender") or ""
    rr = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"sender": restore_val},
        timeout=30,
    )
    assert rr.status_code == 200


# --- Test: empty string removes field ---
def test_patch_empty_string_removes_field(auth_headers):
    # First set a scratch field (reference) to a known value
    r1 = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"reference": "TEST_REMOVE_ME"},
        timeout=30,
    )
    assert r1.status_code == 200
    assert r1.json()["ai_metadata"].get("reference") == "TEST_REMOVE_ME"

    # Now clear it via empty string
    r2 = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"reference": ""},
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    meta = r2.json()["ai_metadata"]
    assert "reference" not in meta, f"reference should be removed but is {meta.get('reference')}"

    # Restore original reference from ZUGFerd = '15111'
    requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"reference": "15111"},
        timeout=30,
    )


# --- Test: date and document_date stay in sync ---
def test_patch_date_syncs_document_date(auth_headers):
    before = _get_doc(ZUGFERD_DOC_ID, auth_headers)
    original_date = (before.get("ai_metadata") or {}).get("date")
    original_document_date = (before.get("ai_metadata") or {}).get("document_date")

    test_date = "2026-01-15"
    r = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"date": test_date},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    meta = r.json()["ai_metadata"]
    assert meta.get("date") == test_date
    assert meta.get("document_date") == test_date, \
        f"document_date not synced: {meta.get('document_date')}"

    # Restore
    if original_date:
        payload = {"date": original_date}
        if original_document_date and original_document_date != original_date:
            payload["document_date"] = original_document_date
        requests.patch(
            f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
            headers=auth_headers,
            json=payload,
            timeout=30,
        )


# --- Test: reverse direction - only document_date fills date ---
def test_patch_document_date_syncs_date(auth_headers):
    before = _get_doc(ZUGFERD_DOC_ID, auth_headers)
    original_date = (before.get("ai_metadata") or {}).get("date")

    test_date = "2025-12-31"
    r = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"document_date": test_date},
        timeout=30,
    )
    assert r.status_code == 200
    meta = r.json()["ai_metadata"]
    assert meta.get("document_date") == test_date
    assert meta.get("date") == test_date

    # Restore
    if original_date:
        requests.patch(
            f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
            headers=auth_headers,
            json={"date": original_date},
            timeout=30,
        )


# --- Regression: single-field PATCH must not clobber other fields (Steinigke doc) ---
def test_patch_amount_only_preserves_sender_on_steinigke(auth_headers):
    before = _get_doc(STEINIGKE_DOC_ID, auth_headers)
    orig_meta = copy.deepcopy(before.get("ai_metadata") or {})
    orig_amount = orig_meta.get("amount")
    orig_sender = orig_meta.get("sender")
    assert orig_sender == "Steinigke Showtechnic GmbH"

    r = requests.patch(
        f"{API}/documents/{STEINIGKE_DOC_ID}/metadata",
        headers=auth_headers,
        json={"amount": 999.99},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    meta = r.json()["ai_metadata"]
    assert meta.get("amount") == 999.99
    assert meta.get("sender") == orig_sender
    assert meta.get("recipient") == orig_meta.get("recipient")
    assert meta.get("invoice_number") == orig_meta.get("invoice_number")
    assert meta.get("manually_edited") is True

    # GET to verify persistence
    after = _get_doc(STEINIGKE_DOC_ID, auth_headers)
    after_meta = after.get("ai_metadata") or {}
    assert after_meta.get("amount") == 999.99
    assert after_meta.get("sender") == orig_sender

    # Restore original amount
    if orig_amount is not None:
        rr = requests.patch(
            f"{API}/documents/{STEINIGKE_DOC_ID}/metadata",
            headers=auth_headers,
            json={"amount": orig_amount},
            timeout=30,
        )
        assert rr.status_code == 200


# --- Test: unknown doc id returns 404 ---
def test_patch_unknown_doc_returns_404(auth_headers):
    r = requests.patch(
        f"{API}/documents/does-not-exist-id/metadata",
        headers=auth_headers,
        json={"sender": "X"},
        timeout=30,
    )
    assert r.status_code == 404


# --- Test: empty payload returns no_changes ---
def test_patch_empty_payload_no_changes(auth_headers):
    r = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "no_changes"
    assert "ai_metadata" in body


# --- Test: unknown fields are ignored (pydantic strict-ish) ---
def test_patch_ignores_unknown_field(auth_headers):
    before = _get_doc(ZUGFERD_DOC_ID, auth_headers)
    orig_meta = copy.deepcopy(before.get("ai_metadata") or {})
    r = requests.patch(
        f"{API}/documents/{ZUGFERD_DOC_ID}/metadata",
        headers=auth_headers,
        json={"totally_random_field": "abc"},
        timeout=30,
    )
    # Either accepted (status_code 200) with no field changed, or 422 (both acceptable)
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        meta = r.json().get("ai_metadata", {})
        assert "totally_random_field" not in meta
        # No documented fields should have changed either
        for key in ("sender", "recipient", "amount"):
            if key in orig_meta:
                assert meta.get(key) == orig_meta.get(key)
