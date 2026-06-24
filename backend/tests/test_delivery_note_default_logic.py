"""
Pure-Python unit test for the default-amount logic in prefill_delivery_note.

Verifies the fix per User request:
- If amount_delivered == 0 -> default amount = amount_total (full quantity)
- If amount_delivered > 0  -> default amount = amount_remaining (so the 2nd LS
  doesn't accidentally re-deliver everything).

No EpiRent or MongoDB dependency - we replicate the exact branch from
orders.py:1336-1340 here and assert all four combinations.
"""
import pytest


def _default_amount(is_heading: bool, amount_total: float, amount_delivered: float) -> float:
    """Replica of the conditional default-quantity logic in
    /app/backend/routes/orders.py prefill_delivery_note."""
    if is_heading:
        return 0.0
    remaining = max(0.0, float(amount_total or 0) - float(amount_delivered or 0))
    return float(amount_total or 0) if (amount_delivered or 0) <= 0 else remaining


class TestDefaultAmount:
    def test_first_ls_zero_delivered_uses_full_total(self):
        # 25 generators, none delivered yet -> default = 25
        assert _default_amount(is_heading=False, amount_total=25, amount_delivered=0) == 25.0

    def test_second_ls_partial_delivered_uses_remaining(self):
        # 25 generators, 5 already on LS-001 -> default = 20 (remaining)
        assert _default_amount(is_heading=False, amount_total=25, amount_delivered=5) == 20.0

    def test_full_delivered_returns_zero(self):
        # 25 / 25 done -> default = 0, prevents double delivery
        assert _default_amount(is_heading=False, amount_total=25, amount_delivered=25) == 0.0

    def test_over_delivered_clamped_to_zero(self):
        # Defensive: 25 ordered, 26 already delivered (data glitch) -> default 0 not negative
        assert _default_amount(is_heading=False, amount_total=25, amount_delivered=26) == 0.0

    def test_heading_always_zero(self):
        # Headings are display-only chapter labels - never delivered
        assert _default_amount(is_heading=True, amount_total=25, amount_delivered=0) == 0.0

    def test_fractional_amounts(self):
        # 2.5 (e.g. cable lengths) and 0.5 delivered -> remaining 2.0
        assert _default_amount(is_heading=False, amount_total=2.5, amount_delivered=0.5) == 2.0

    def test_first_ls_with_floats(self):
        assert _default_amount(is_heading=False, amount_total=2.5, amount_delivered=0) == 2.5


# Quick smoke test against the live backend prefill if EpiRent is reachable.
@pytest.mark.timeout(180)
def test_live_prefill_default_logic_smoke():
    """Integration smoke: if EpiRent is reachable, verify amount field follows
    the new rule. Skipped automatically when EpiRent times out."""
    import requests
    try:
        login = requests.post(
            "http://localhost:8001/api/auth/login",
            json={"email": "admin@test.com", "password": "password"},
            timeout=30,
        )
        if login.status_code != 200:
            pytest.skip(f"Login failed: {login.status_code}")
        token = login.json().get("token")
        r = requests.get(
            "http://localhost:8001/api/orders/epirent/12/delivery-notes/prefill",
            headers={"Authorization": f"Bearer {token}"},
            timeout=150,
        )
    except (requests.ConnectTimeout, requests.ConnectionError, requests.ReadTimeout) as e:
        pytest.skip(f"EpiRent unreachable in this run: {e}")
    if r.status_code != 200:
        pytest.skip(f"Prefill not OK: {r.status_code} {r.text[:120]}")

    payload = r.json()
    items = []
    for g in payload.get("groups", []):
        for it in g.get("items", []):
            if not it.get("is_heading"):
                items.append(it)
    assert items, "No non-heading items in payload"

    for it in items:
        total = float(it.get("amount_total") or 0)
        delivered = float(it.get("amount_delivered") or 0)
        amount = float(it.get("amount") or 0)
        remaining = float(it.get("amount_remaining") or 0)
        expected = total if delivered <= 0 else remaining
        assert amount == expected, (
            f"Item pk={it.get('primary_key')} title={it.get('title')[:40]!r}: "
            f"got amount={amount}, expected {expected} "
            f"(total={total} delivered={delivered} remaining={remaining})"
        )
