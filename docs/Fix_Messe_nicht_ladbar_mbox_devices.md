# Fix: „Messe nicht ladbar“ – `/api/mbox/devices` liefert 500

**Datum:** 04.11.2026
**Priorität:** P0 (Verwaltung → Messe → Messe öffnen ist komplett blockiert)
**Status:** Live auf dem Server per Hotfix behoben. Im Quellcode noch **nicht committet**. Bitte übernehmen und committen.

---

## Symptom

- Verwaltung → Messe (`/verwaltung/messe`) → eine Messe anklicken.
- Die Seite bleibt bei „Laden …“ stehen. Toast: **„Messe nicht ladbar“**.

## Ursache

`frontend/src/components/messe/MesseDetail.jsx` (Funktion `load`, ca. Zeile 22–29) lädt zwei Endpunkte parallel:

```js
await Promise.all([api.get(`/messe/${messeId}`), api.get("/mbox/devices")]);
```

`GET /api/messe/{id}` → **200**, `GET /api/mbox/devices` → **500 Internal Server Error**.
Weil einer der beiden Aufrufe fehlschlägt, bricht `Promise.all` ab, und die Detailseite lädt nie.

Backend-Log (`C:\Eventenergie\logs\backend-err.log`):

```
ValueError: [TypeError("'ObjectId' object is not iterable"), TypeError('vars() argument must have __dict__ attribute')]
```

Bei einem M-Box-Gerät (`devices.id = 187c2d6f-ae5c-4207-8687-41a93841942c`) ist ein Gerätebild hochgeladen.
Das Feld `image_gridfs_id` ist dort als **BSON-`ObjectId`** gespeichert (wird so in `routes/devices.py` beim Bild-Upload geschrieben, ca. Zeile 647).

- `routes/devices.py` wandelt dieses Feld vor jeder Ausgabe in einen String um (Zeilen ~326, 373, 407, 477, 534).
- `routes/mbox.py` → `_public()` gibt das Geräte-Dokument dagegen **ungefiltert** zurück. FastAPI kann die `ObjectId` nicht serialisieren → 500.

Betroffen sind alle Endpunkte, die `_public()` nutzen:

- `GET /api/mbox/devices`
- `GET /api/mbox/{device_id}/status`

Der Fehler tritt bei **jedem** M-Box-Gerät mit hochgeladenem Bild auf.

## Fix (so live eingespielt)

Datei: `backend/routes/mbox.py`, Funktion `_public` (ca. Zeile 509):

```python
def _public(device: dict) -> dict:
    d = {k: v for k, v in device.items() if k not in ("mbox_password", "pi_password", "mqtt_password", "mbox_pi_key_hash")}
    # Geraetebild (GridFS) ist als ObjectId gespeichert -> nicht JSON-faehig; wie in routes/devices.py als String ausgeben
    if d.get("image_gridfs_id"):
        d["image_gridfs_id"] = str(d["image_gridfs_id"])
    d["pi"] = mbox_pi.pi_state(device)
    d["position"] = mbox_pi.device_position(device)
    return d
```

Hinweis: Das Original-`device` wird nicht verändert (nur die Kopie `d`). Funktionen wie `_forward` usw. arbeiten weiter mit der echten ObjectId.

## Geprüft

- Syntax-Check ok. Dienst `EventenergieBackend` neu gestartet.
- `list_mbox_devices` direkt mit einem Admin-User aufgerufen: alle 6 M-Box-Geräte werden geliefert, `jsonable_encoder` + `json.dumps` laufen ohne Fehler.
- Ohne Login liefert der Endpunkt erwartungsgemäß 403.
- Ein Browser-Test der Seite steht noch aus.

## To-do für den Agenten

1. Die Änderung in `backend/routes/mbox.py` im Repo übernehmen bzw. prüfen und committen.
2. **Optional (empfohlen):** Weitere Stellen absichern, an denen ganze Geräte-Dokumente aus `db.devices` ohne Umwandlung zurückgegeben werden. Suche nach `db.devices.find` / `find_one` in:
   - `routes/messe.py`: nutzt aktuell `_device_brief` und ist damit sicher
   - `routes/energy_monitoring.py`
   - `routes/ota_updates.py`
   - `routes/tank_pi.py`

   Dort `image_gridfs_id` ebenfalls in einen String umwandeln, oder zentral einen Helper wie `serialize_device(d)` einführen.
3. **Optional:** In `MesseDetail.jsx` `/mbox/devices` getrennt laden (z. B. `Promise.allSettled`). Dann öffnet sich die Messe auch, wenn die M-Box-Liste einmal fehlschlägt; nur die Mastenauswahl bleibt leer.
4. **Regressionstest:** Gerät mit `device_type: "mbox"` und `image_gridfs_id: ObjectId()` anlegen → `GET /api/mbox/devices` als Admin → muss 200 liefern, `image_gridfs_id` als String.
