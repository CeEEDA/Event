"""Tests für Auto-Unassign abgelaufener Auftrags-Zuordnungen.

Testet `deployment_tracker.cleanup_expired_order_assignments` mit einer
In-Memory-Mock-DB, damit kein echter MongoDB-Roundtrip nötig ist.
"""
import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from deployment_tracker import cleanup_expired_order_assignments


class _MockCursor:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class _MockCollection:
    def __init__(self, docs):
        self.docs = list(docs)
        self.updates = []  # list of (filter, update)

    def find(self, query, projection=None):
        # Sehr einfache Filter-Logik (genug für den Test):
        result = []
        for d in self.docs:
            ok = True
            for k, v in (query or {}).items():
                if k.startswith("$"):
                    continue
                if isinstance(v, dict) and "$exists" in v:
                    has_key = k in d
                    if v["$exists"] and not has_key:
                        ok = False; break
                    if not v["$exists"] and has_key:
                        ok = False; break
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        ok = False; break
                elif isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        ok = False; break
                else:
                    if d.get(k) != v:
                        ok = False; break
            if ok:
                result.append(d)
        return _MockCursor(result)

    async def find_one(self, query, projection=None):
        for d in self.docs:
            ok = True
            for k, v in (query or {}).items():
                if k == "$or":
                    sub_ok = False
                    for cond in v:
                        if all(d.get(sk) == sv for sk, sv in cond.items()):
                            sub_ok = True; break
                    if not sub_ok:
                        ok = False; break
                else:
                    if d.get(k) != v:
                        ok = False; break
            if ok:
                return d
        return None

    async def update_one(self, q, update):
        self.updates.append((q, update))
        # Mutate in-place for $set
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not k.startswith("$")):
                set_part = update.get("$set", {})
                d.update(set_part)
                break


class _MockDB:
    def __init__(self):
        self.orders_cache = _MockCollection([])
        self.order_settings = _MockCollection([])
        self.deployment_history = _MockCollection([])


@pytest.mark.asyncio
async def test_expired_order_unassigns_and_closes():
    db = _MockDB()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()

    # Abgelaufener Auftrag
    db.orders_cache.docs.append({
        "primary_key": 100, "dispo_end": yesterday, "event": "Vergangenes Event",
    })
    # Aktiver Auftrag
    db.orders_cache.docs.append({
        "primary_key": 200, "dispo_end": tomorrow, "event": "Zukünftiges Event",
    })

    db.order_settings.docs.append({
        "order_pk": 100, "manual_generator_ids": ["gen-A", "gen-B"],
    })
    db.order_settings.docs.append({
        "order_pk": 200, "manual_generator_ids": ["gen-C"],
    })

    db.deployment_history.docs.append({
        "id": "dep-1", "order_pk": 100, "generator_id": "gen-A", "stopped_at": None,
    })
    db.deployment_history.docs.append({
        "id": "dep-2", "order_pk": 100, "generator_id": "gen-B", "stopped_at": None,
    })
    db.deployment_history.docs.append({
        "id": "dep-3", "order_pk": 200, "generator_id": "gen-C", "stopped_at": None,
    })

    result = await cleanup_expired_order_assignments(db)

    assert result["processed_orders"] == 1
    assert result["unassigned_generators"] == 2
    assert result["closed_deployments"] == 2

    # Abgelaufener Auftrag wurde aufgeräumt
    expired = await db.order_settings.find_one({"order_pk": 100})
    assert expired["manual_generator_ids"] == []

    # Aktiver Auftrag bleibt unverändert
    active = await db.order_settings.find_one({"order_pk": 200})
    assert active["manual_generator_ids"] == ["gen-C"]

    # Deployments geschlossen
    dep1 = await db.deployment_history.find_one({"id": "dep-1"})
    dep2 = await db.deployment_history.find_one({"id": "dep-2"})
    dep3 = await db.deployment_history.find_one({"id": "dep-3"})
    assert dep1["stopped_at"] is not None
    assert dep2["stopped_at"] is not None
    assert dep3["stopped_at"] is None  # aktiver Auftrag bleibt offen
    assert "Auftragsende" in dep1["notes"]


@pytest.mark.asyncio
async def test_no_expiry_means_no_action():
    db = _MockDB()
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    db.orders_cache.docs.append({
        "primary_key": 300, "dispo_end": tomorrow, "event": "Future",
    })
    db.order_settings.docs.append({
        "order_pk": 300, "manual_generator_ids": ["gen-X"],
    })

    result = await cleanup_expired_order_assignments(db)
    assert result["processed_orders"] == 0
    assert result["unassigned_generators"] == 0


@pytest.mark.asyncio
async def test_event_end_fallback_when_no_dispo_end():
    db = _MockDB()
    yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    db.orders_cache.docs.append({
        "primary_key": 400, "event_end": yesterday, "event": "EventOnly",
    })
    db.order_settings.docs.append({
        "order_pk": 400, "manual_generator_ids": ["gen-Y"],
    })
    db.deployment_history.docs.append({
        "id": "dep-4", "order_pk": 400, "generator_id": "gen-Y", "stopped_at": None,
    })

    result = await cleanup_expired_order_assignments(db)
    assert result["processed_orders"] == 1
    assert result["unassigned_generators"] == 1
    assert result["closed_deployments"] == 1
