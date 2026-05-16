"""Iteration 67: Tests for POST /api/orders/epirent/{order_pk}/copy-to
Verifies admin copy of assets and generators from a source order into a target order.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://kirmes-billing-1.preview.emergentagent.com").rstrip("/")
SOURCE_PK = 6
TARGET_PK = 7
ADMIN_EMAIL = "admin@test.com"
ADMIN_PW = "password"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def ensure_source_has_asset(headers):
    """Source order pk=6 must have at least one asset (Lichtmast) for tests.
    Creates one if missing. Cleanup happens in cleanup test at the end."""
    r = requests.get(f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/assets", headers=headers, timeout=30)
    data = r.json() if r.status_code == 200 else {}
    items = data.get("assets") if isinstance(data, dict) else data
    items = items or []
    created_id = None
    if not items:
        payload = {
            "asset_type": "Lichtmast",
            "latitude": 51.95,
            "longitude": 7.6,
            "label": "TEST_Lichtmast Copy Source",
            "plus_code": "9F296X00+00",
        }
        cr = requests.post(
            f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/assets",
            headers=headers, json=payload, timeout=30,
        )
        assert cr.status_code in (200, 201), f"seed asset failed: {cr.status_code} {cr.text}"
        created_id = cr.json().get("id")
    yield created_id
    # Cleanup the seed if we created it
    if created_id:
        requests.delete(
            f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/assets/{created_id}",
            headers=headers, timeout=30,
        )


def _get_assets(headers, order_pk):
    r = requests.get(f"{BASE_URL}/api/orders/epirent/{order_pk}/assets", headers=headers, timeout=30)
    assert r.status_code == 200, f"assets fetch failed pk={order_pk}: {r.status_code}"
    data = r.json()
    return data if isinstance(data, list) else data.get("assets") or data.get("items") or []


def _get_generators(headers, order_pk):
    # get generators in radius / assigned to order
    r = requests.get(f"{BASE_URL}/api/orders/epirent/{order_pk}/generators", headers=headers, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    if isinstance(data, list):
        return data
    return data.get("generators") or data.get("items") or []


def test_login_works(admin_token):
    assert admin_token, "missing token"


def test_source_order_has_assets(headers):
    assets = _get_assets(headers, SOURCE_PK)
    assert len(assets) >= 1, f"source order {SOURCE_PK} expected at least 1 asset"


def test_copy_to_self_returns_400(headers):
    r = requests.post(
        f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/copy-to",
        headers=headers,
        json={"target_order_pk": SOURCE_PK, "asset_ids": [], "generator_ids": []},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


def test_copy_empty_payload_returns_400(headers):
    r = requests.post(
        f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/copy-to",
        headers=headers,
        json={"target_order_pk": TARGET_PK, "asset_ids": [], "generator_ids": []},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


def test_copy_unknown_target_returns_404(headers):
    r = requests.post(
        f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/copy-to",
        headers=headers,
        json={"target_order_pk": 99999999, "asset_ids": ["nonexistent"], "generator_ids": []},
        timeout=30,
    )
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


@pytest.fixture(scope="module")
def copy_state(headers):
    """Pre-fetch state needed across copy tests."""
    src_assets = _get_assets(headers, SOURCE_PK)
    tgt_before = _get_assets(headers, TARGET_PK)
    return {
        "src_assets": src_assets,
        "tgt_before_count": len(tgt_before),
        "tgt_before_ids": {a.get("id") for a in tgt_before},
        "created_asset_ids": [],
    }


def test_copy_one_asset_increments_target(headers, copy_state):
    src_assets = copy_state["src_assets"]
    assert src_assets, "no source assets"
    asset_id = src_assets[0]["id"]
    r = requests.post(
        f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/copy-to",
        headers=headers,
        json={"target_order_pk": TARGET_PK, "asset_ids": [asset_id], "generator_ids": []},
        timeout=60,
    )
    assert r.status_code == 200, f"copy failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("ok") is True
    assert body.get("copied_assets") == 1, f"expected 1 copied_assets, got {body}"

    # Verify target has the new asset (count +1)
    tgt_after = _get_assets(headers, TARGET_PK)
    assert len(tgt_after) == copy_state["tgt_before_count"] + 1, (
        f"target count expected {copy_state['tgt_before_count']+1}, got {len(tgt_after)}"
    )
    new_ids = [a.get("id") for a in tgt_after if a.get("id") not in copy_state["tgt_before_ids"]]
    assert len(new_ids) == 1, f"expected exactly 1 new asset id, got {new_ids}"
    copy_state["created_asset_ids"].extend(new_ids)


def test_source_assets_unchanged_after_copy(headers, copy_state):
    src_now = _get_assets(headers, SOURCE_PK)
    assert len(src_now) == len(copy_state["src_assets"]), "source order asset count must not change (copy, not move)"


def test_copy_generator_idempotent(headers):
    gens = _get_generators(headers, SOURCE_PK)
    # If no generators assigned in source we just skip the generator part - this is preview env data dependent
    if not gens:
        pytest.skip("source order has no generators in this env")
    gid = gens[0].get("id") or gens[0].get("generator_id")
    if not gid:
        pytest.skip("generator without id field")

    # First copy
    r1 = requests.post(
        f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/copy-to",
        headers=headers,
        json={"target_order_pk": TARGET_PK, "asset_ids": [], "generator_ids": [gid]},
        timeout=60,
    )
    assert r1.status_code == 200, f"copy gen failed: {r1.status_code} {r1.text}"
    first_count = r1.json().get("copied_generators", 0)

    # Re-copy should be idempotent -> 0
    r2 = requests.post(
        f"{BASE_URL}/api/orders/epirent/{SOURCE_PK}/copy-to",
        headers=headers,
        json={"target_order_pk": TARGET_PK, "asset_ids": [], "generator_ids": [gid]},
        timeout=60,
    )
    assert r2.status_code == 200
    assert r2.json().get("copied_generators") == 0, f"expected 0 on regen copy, got {r2.json()}"
    assert first_count in (0, 1)


def test_cleanup_copied_assets(headers, copy_state):
    """Cleanup: delete every asset we created in target during this run."""
    for aid in copy_state.get("created_asset_ids", []):
        r = requests.delete(f"{BASE_URL}/api/orders/epirent/{TARGET_PK}/assets/{aid}", headers=headers, timeout=30)
        assert r.status_code in (200, 204, 404), f"cleanup failed for {aid}: {r.status_code} {r.text}"
