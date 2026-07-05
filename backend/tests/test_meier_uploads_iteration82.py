"""
Iteration 82: Verify 2 Meier KG uploaded ZUGFeRD PDFs (RG + GU) landed correctly
- Backend list endpoint
- Backend search endpoint
- Folder tree verification (Juni exists under 2026)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://fuel-truck-deploy.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "christian.ecker@eventenergie-deutschland.de"
ADMIN_PASSWORD = "qivbeb-Wodha1-sewram"

RG_FILENAME = "RG_490_015230_5993421.pdf"
GU_FILENAME = "GU_490_015230_5993613.pdf"
TARGET_FOLDER = "rechnungseingang_eventenergie_deutschland_2026_06"


@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD
    }, timeout=30)
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    j = resp.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- List endpoint ---
def test_list_target_folder_contains_both_docs(headers):
    resp = requests.get(f"{BASE_URL}/api/documents/list",
                        params={"folder_id": TARGET_FOLDER},
                        headers=headers, timeout=30)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    docs = data.get("documents") if isinstance(data, dict) else data
    assert isinstance(docs, list), f"Unexpected response: {data}"
    filenames = [d.get("original_filename") or d.get("filename") for d in docs]
    assert RG_FILENAME in filenames, f"RG not in {filenames}"
    assert GU_FILENAME in filenames, f"GU not in {filenames}"


# --- Folder tree ---
def test_folders_endpoint_contains_juni_2026(headers):
    resp = requests.get(f"{BASE_URL}/api/documents/folders",
                        headers=headers, timeout=30)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # flatten - could be tree or flat list
    flat = []

    def walk(nodes):
        if isinstance(nodes, dict):
            nodes = nodes.get("folders") or nodes.get("items") or []
        for n in nodes or []:
            flat.append(n)
            walk(n.get("children") or n.get("subfolders") or [])

    walk(data)
    ids = [f.get("id") for f in flat]
    assert TARGET_FOLDER in ids, f"Target folder id not in tree; sample ids: {ids[:20]}"
    # verify name is 'Juni'
    juni = next((f for f in flat if f.get("id") == TARGET_FOLDER), None)
    assert juni is not None
    assert juni.get("name") == "Juni", f"Expected name 'Juni' got {juni.get('name')}"


# --- Umlaut-free naming ---
def test_folders_have_no_umlauts(headers):
    resp = requests.get(f"{BASE_URL}/api/documents/folders",
                        headers=headers, timeout=30)
    assert resp.status_code == 200
    data = resp.json()
    flat = []

    def walk(nodes):
        if isinstance(nodes, dict):
            nodes = nodes.get("folders") or nodes.get("items") or []
        for n in nodes or []:
            flat.append(n)
            walk(n.get("children") or n.get("subfolders") or [])

    walk(data)
    bad = []
    for f in flat:
        nm = f.get("name") or ""
        if any(ch in nm for ch in "äöüÄÖÜß"):
            bad.append(nm)
    assert not bad, f"Folders with umlauts found: {bad}"


# --- Search endpoint ---
def test_search_meier_finds_both_docs(headers):
    resp = requests.get(f"{BASE_URL}/api/documents/search",
                        params={"q": "Meier"}, headers=headers, timeout=30)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    docs = data.get("documents") or data.get("results") or (data if isinstance(data, list) else [])
    filenames = [d.get("original_filename") or d.get("filename") for d in docs]
    assert RG_FILENAME in filenames, f"RG not found via search Meier. Got: {filenames}"
    assert GU_FILENAME in filenames, f"GU not found via search Meier. Got: {filenames}"


# --- Detail: verify metadata via GET /api/documents/{id} ---
def test_rg_detail_metadata(headers):
    doc_id = "d3194e9a-31b5-4bac-bcdc-83701826eb52"
    resp = requests.get(f"{BASE_URL}/api/documents/{doc_id}", headers=headers, timeout=30)
    assert resp.status_code == 200, resp.text
    d = resp.json()
    meta = d.get("ai_metadata") or {}
    assert d.get("ai_status") == "completed"
    assert d.get("folder_id") == TARGET_FOLDER
    assert "Meier" in (meta.get("sender") or "")
    assert float(meta.get("amount")) == 2635.14
    assert meta.get("document_type") == "rechnung"
    assert (meta.get("iban") or "").startswith("DE19 5705")


def test_gu_detail_metadata(headers):
    doc_id = "eba6c25c-cbaf-433f-b2a4-744e1e74722e"
    resp = requests.get(f"{BASE_URL}/api/documents/{doc_id}", headers=headers, timeout=30)
    assert resp.status_code == 200, resp.text
    d = resp.json()
    meta = d.get("ai_metadata") or {}
    assert d.get("ai_status") == "completed"
    assert d.get("folder_id") == TARGET_FOLDER
    assert "Meier" in (meta.get("sender") or "")
    assert float(meta.get("amount")) == 2710.92
    assert meta.get("document_type") == "gutschrift"
    assert (meta.get("iban") or "").startswith("DE19 5705")
