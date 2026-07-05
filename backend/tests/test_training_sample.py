"""
Test cases for POST /api/documents/{doc_id}/save-as-training-sample
Feature: 'Als Beispiel lernen' - saves manually corrected doc as AI training sample.
Verification is done via direct MongoDB queries (because GET /api/documents/ai-training-samples
is currently shadowed by /{doc_id} route → 404).
"""
import os
import json
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

ADMIN_EMAIL = "christian.ecker@eventenergie-deutschland.de"
ADMIN_PASSWORD = "qivbeb-Wodha1-sewram"

DOC_MANUAL = "25b74df5-6384-4eff-bbd4-7858fa7f449c"     # manually_edited=True
DOC_NOT_MANUAL = "afbdd21a-9420-416f-8c38-8cca3344921e"  # Rechnung_RE-2026-0310.pdf, no manually_edited, local file exists
DOC_NONEXISTENT = "nonexistent-id-xyz"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in response: {r.json()}"
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def created_sample_ids(db):
    ids = []
    yield ids
    # teardown: delete via API + fallback DB
    for sid in ids:
        try:
            requests.delete(f"{BASE_URL}/api/documents/ai-training-samples/{sid}", timeout=15)
        except Exception:
            pass
        try:
            db.ai_training_samples.delete_one({"id": sid})
        except Exception:
            pass


class TestSaveAsTrainingSamplePositive:
    def test_positive_creates_sample_with_all_fields(self, auth_headers, db, created_sample_ids):
        r = requests.post(
            f"{BASE_URL}/api/documents/{DOC_MANUAL}/save-as-training-sample",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, f"unexpected: {r.status_code} {r.text}"
        data = r.json()
        assert "id" in data
        assert "filename" in data
        assert data.get("status") == "created"
        assert data["filename"] == "263015.pdf"
        sid = data["id"]
        created_sample_ids.append(sid)

        # Verify in DB
        sample = db.ai_training_samples.find_one({"id": sid}, {"_id": 0})
        assert sample is not None, "sample not persisted"
        assert sample["source_doc_id"] == DOC_MANUAL
        assert sample["target_folder_id"] == "rechnungseingang_eventenergie_deutschland_2026_06"
        assert sample["file_size"] > 0, "file_size must be > 0"
        # File-Content: original test says ~5.7MB
        assert sample["file_size"] > 1000, "file_size suspiciously small"

        # correction is JSON string without manually_edited
        correction_raw = sample.get("correction")
        assert correction_raw, "correction empty"
        correction = json.loads(correction_raw)
        assert isinstance(correction, dict)
        assert "manually_edited" not in correction
        assert len(correction) >= 5, f"too few metadata fields: {list(correction.keys())}"
        # Verify Normann sender still present (indicates real corrected data)
        assert "Normann" in correction.get("sender", ""), \
            f"sender doesn't match expected: {correction.get('sender')}"


class TestSaveAsTrainingSampleNegative:
    def test_negative_not_manually_edited_returns_400(self, auth_headers):
        """DOC_NOT_MANUAL is DEEP-SEA-5510-MANUAL.pdf - no manually_edited flag."""
        r = requests.post(
            f"{BASE_URL}/api/documents/{DOC_NOT_MANUAL}/save-as-training-sample",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "manuell" in detail, f"unexpected detail: {detail}"

    def test_negative_nonexistent_doc_returns_404(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/documents/{DOC_NONEXISTENT}/save-as-training-sample",
            headers=auth_headers, timeout=30,
        )
        assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"
