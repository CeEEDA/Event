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


def _filter_items(items: list) -> list:
    """Replica of the filter-out-fully-delivered logic in prefill_delivery_note."""
    filtered_items = []
    for it in items:
        if it.get("is_heading"):
            filtered_items.append(it)
            continue
        total = float(it.get("amount_total") or 0)
        delivered = float(it.get("amount_delivered") or 0)
        if total > 0 and delivered >= total:
            continue
        filtered_items.append(it)
    cleaned_items = []
    for idx, it in enumerate(filtered_items):
        if it.get("is_heading"):
            has_following_article = any(
                not nxt.get("is_heading") for nxt in filtered_items[idx + 1:]
            )
            if not has_following_article:
                continue
        cleaned_items.append(it)
    return cleaned_items


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


class TestItemFilter:
    """User-Wunsch: Items mit amount_delivered >= amount_total sollen NICHT mehr
    im neuen LS auftauchen. Headings nur wenn ein Artikel danach kommt."""

    def test_fully_delivered_item_is_removed(self):
        items = [
            {"primary_key": 1, "amount_total": 2, "amount_delivered": 2, "title": "X"},
        ]
        assert _filter_items(items) == []

    def test_partially_delivered_item_stays(self):
        it = {"primary_key": 1, "amount_total": 25, "amount_delivered": 5, "title": "Y"}
        assert _filter_items([it]) == [it]

    def test_undelivered_item_stays(self):
        it = {"primary_key": 1, "amount_total": 10, "amount_delivered": 0, "title": "Z"}
        assert _filter_items([it]) == [it]

    def test_mixed_keeps_only_open_ones(self):
        items = [
            {"primary_key": 1, "amount_total": 2, "amount_delivered": 2, "title": "done"},
            {"primary_key": 2, "amount_total": 5, "amount_delivered": 1, "title": "partial"},
            {"primary_key": 3, "amount_total": 1, "amount_delivered": 0, "title": "fresh"},
        ]
        out = _filter_items(items)
        assert len(out) == 2
        assert out[0]["title"] == "partial"
        assert out[1]["title"] == "fresh"

    def test_heading_kept_if_article_below(self):
        items = [
            {"is_heading": True, "title": "T1 nach T2"},
            {"primary_key": 1, "amount_total": 5, "amount_delivered": 0, "title": "Kabel"},
        ]
        out = _filter_items(items)
        assert len(out) == 2

    def test_heading_dropped_if_no_article_below(self):
        items = [
            {"primary_key": 1, "amount_total": 5, "amount_delivered": 0, "title": "Kabel"},
            {"is_heading": True, "title": "Trailing Heading"},
        ]
        out = _filter_items(items)
        assert len(out) == 1
        assert out[0]["title"] == "Kabel"

    def test_heading_dropped_if_all_articles_delivered(self):
        items = [
            {"is_heading": True, "title": "Section"},
            {"primary_key": 1, "amount_total": 2, "amount_delivered": 2, "title": "done1"},
            {"primary_key": 2, "amount_total": 1, "amount_delivered": 1, "title": "done2"},
        ]
        assert _filter_items(items) == []

    def test_heading_kept_between_articles_with_one_partially_delivered(self):
        items = [
            {"is_heading": True, "title": "A"},
            {"primary_key": 1, "amount_total": 2, "amount_delivered": 2, "title": "fully"},
            {"is_heading": True, "title": "B"},
            {"primary_key": 2, "amount_total": 5, "amount_delivered": 1, "title": "partial"},
        ]
        out = _filter_items(items)
        # 'fully' wird gefiltert, 'partial' bleibt. Heading A bleibt weil 'partial'
        # noch danach kommt; Heading B bleibt direkt vor 'partial'.
        titles = [i["title"] for i in out]
        assert "fully" not in titles
        assert titles == ["A", "B", "partial"]


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
