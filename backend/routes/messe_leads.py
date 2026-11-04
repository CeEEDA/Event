"""Messeprotokoll: Kontakte (Leads), die Messe-Team-Mitglieder am Stand erfassen - per QR/vCard-Scan, Visitenkarten-Foto (KI) oder manuell.
Auswertung unter Verwaltung / Messe / <Messe> / Messe Kontaktformular."""
import json
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from routes import mbox as _mbox
from routes.mbox import get_user

router = APIRouter(prefix="/api/messe", tags=["messe-leads"])
logger = logging.getLogger(__name__)
db = None

LEAD_FIELDS = ["company", "first_name", "last_name", "position", "phone", "mobile", "email", "website",
               "street", "zip", "city", "country", "interest", "products", "notes", "follow_up_date", "priority", "source"]
STATUS = ["offen", "kontaktiert", "termin", "angebot", "erledigt", "kein_interesse"]


def init_messe_leads_routes(database):
    global db
    db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _staff(user: dict):
    if user.get("role") not in ("admin", "mitarbeiter"):
        raise HTTPException(status_code=403, detail="Nur fuer Mitarbeiter")


async def _messe(messe_id: str) -> dict:
    m = await db.messen.find_one({"id": messe_id, "deleted_at": None}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Messe nicht gefunden")
    return m


async def _member(messe_id: str, user: dict) -> dict:
    """Protokoll fuehren darf nur, wer der Messe als Team zugeteilt ist."""
    m = await _messe(messe_id)
    if user["id"] not in (m.get("staff_ids") or []):
        raise HTTPException(status_code=403, detail="Du bist dieser Messe nicht als Team zugeteilt")
    return m


def _clean(body: dict) -> dict:
    out = {}
    for k in LEAD_FIELDS:
        if k in body:
            v = body.get(k)
            out[k] = (str(v).strip()[:500] if v is not None else "") if k != "notes" else (str(v or "")[:4000])
    return out


@router.get("/{messe_id}/leads")
async def list_leads(messe_id: str, user: dict = Depends(get_user)):
    _staff(user)
    await _messe(messe_id)
    rows = await db.messe_leads.find({"messe_id": messe_id, "deleted_at": None}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return {"leads": rows, "status_options": STATUS}


@router.post("/{messe_id}/leads")
async def create_lead(messe_id: str, body: dict, user: dict = Depends(get_user)):
    _staff(user)
    m = await _member(messe_id, user)
    doc = {"id": str(uuid.uuid4()), "messe_id": messe_id, "messe_name": m["name"], **{k: "" for k in LEAD_FIELDS}, **_clean(body),
           "status": "offen", "created_at": _now(), "created_by": user["id"], "created_by_name": user.get("name"),
           "updated_at": _now(), "deleted_at": None, "history": []}
    if not doc.get("source"):
        doc["source"] = "manuell"
    await db.messe_leads.insert_one(dict(doc))
    return doc


@router.patch("/{messe_id}/leads/{lead_id}")
async def update_lead(messe_id: str, lead_id: str, body: dict, user: dict = Depends(get_user)):
    _staff(user)
    await _messe(messe_id)
    upd = _clean(body)
    if "status" in body and body["status"] in STATUS:
        upd["status"] = body["status"]
    if "deleted" in body and body["deleted"] is True:
        upd["deleted_at"] = _now()
    if "call_note" in body and str(body["call_note"]).strip():
        await db.messe_leads.update_one({"id": lead_id, "messe_id": messe_id}, {"$push": {"history": {
            "at": _now(), "by": user.get("name"), "text": str(body["call_note"]).strip()[:2000], "status": upd.get("status")}}})
    if upd:
        upd["updated_at"] = _now()
        upd["updated_by_name"] = user.get("name")
        await db.messe_leads.update_one({"id": lead_id, "messe_id": messe_id}, {"$set": upd})
    doc = await db.messe_leads.find_one({"id": lead_id, "messe_id": messe_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Kontakt nicht gefunden")
    return doc


@router.get("/{messe_id}/leads/export.csv")
async def export_leads(messe_id: str, token: str = Query(...)):
    """Download-Link (kein Header moeglich) -> JWT als Query-Parameter."""
    payload = _mbox.decode_jwt_token(token)
    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    _staff(user)
    m = await _messe(messe_id)
    rows = await db.messe_leads.find({"messe_id": messe_id, "deleted_at": None}, {"_id": 0}).sort("created_at", 1).to_list(5000)
    cols = ["created_at", "created_by_name", "status"] + LEAD_FIELDS
    esc = lambda v: '"' + str(v if v is not None else "").replace('"', '""').replace("\n", " ") + '"'
    lines = [";".join(cols)] + [";".join(esc(r.get(c, "")) for c in cols) for r in rows]
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", m["name"])
    return Response(content="\ufeff" + "\r\n".join(lines), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="Messekontakte_{name}.csv"'})


def parse_vcard(text: str) -> dict:
    """vCard 2.1/3.0/4.0 oder MeCard (QR von Visitenkarten-Apps) -> Lead-Felder."""
    out: dict = {}
    t = text.strip()
    if t.upper().startswith("MECARD:"):
        for part in t[7:].split(";"):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            k = k.upper()
            if k == "N":
                ln, _, fn = v.partition(",")
                out["last_name"], out["first_name"] = ln.strip(), fn.strip()
            elif k == "TEL":
                out.setdefault("phone", v)
            elif k == "EMAIL":
                out["email"] = v
            elif k == "ORG":
                out["company"] = v
            elif k == "URL":
                out["website"] = v
            elif k == "ADR":
                out["street"] = v
            elif k == "NOTE":
                out["notes"] = v
        return out
    for raw in t.replace("\r", "").split("\n"):
        if ":" not in raw:
            continue
        key, val = raw.split(":", 1)
        base = key.split(";")[0].upper()
        params = key.upper()
        val = val.strip().replace("\\,", ",").replace("\\n", "\n")
        if base == "N":
            parts = val.split(";")
            out["last_name"] = parts[0].strip() if parts else ""
            out["first_name"] = parts[1].strip() if len(parts) > 1 else ""
        elif base == "FN" and not out.get("last_name"):
            fn = val.split(" ")
            out["first_name"], out["last_name"] = (" ".join(fn[:-1]), fn[-1]) if len(fn) > 1 else ("", val)
        elif base == "ORG":
            out["company"] = val.split(";")[0]
        elif base == "TITLE" or base == "ROLE":
            out.setdefault("position", val)
        elif base == "TEL":
            if "CELL" in params or "MOBILE" in params:
                out.setdefault("mobile", val)
            else:
                out.setdefault("phone", val)
        elif base == "EMAIL":
            out.setdefault("email", val)
        elif base == "URL":
            out.setdefault("website", val)
        elif base == "ADR":
            p = val.split(";")
            if len(p) >= 7:
                out["street"], out["city"], out["zip"], out["country"] = p[2], p[3], p[5], p[6]
            else:
                out["street"] = val.replace(";", " ").strip()
        elif base == "NOTE":
            out["notes"] = val
    return out


@router.post("/{messe_id}/leads/parse-qr")
async def parse_qr(messe_id: str, body: dict, user: dict = Depends(get_user)):
    _staff(user)
    await _member(messe_id, user)
    text = str(body.get("text") or "")
    data = parse_vcard(text)
    if not data and ("@" in text or text.startswith("http")):
        data = {"email": text} if "@" in text else {"website": text}
    if not data:
        raise HTTPException(status_code=422, detail="QR-Code enthaelt keine Kontaktdaten (vCard/MeCard erwartet)")
    return {"fields": data, "source": "qr"}


CARD_PROMPT = """Du liest eine fotografierte Visitenkarte. Gib NUR ein JSON-Objekt zurueck (kein Markdown) mit diesen Schluesseln:
company, first_name, last_name, position, phone, mobile, email, website, street, zip, city, country.
Unbekannte Felder als leerer String. Telefonnummern im Original-Format belassen. Keine Erklaerungen."""


@router.post("/{messe_id}/leads/scan-card")
async def scan_card(messe_id: str, file: UploadFile = File(...), user: dict = Depends(get_user)):
    """Visitenkarten-Foto -> Felder (Gemini Vision ueber Emergent-Key, gleiche Integration wie Dokumentenpruefung)."""
    _staff(user)
    await _member(messe_id, user)
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="KI-Schluessel nicht konfiguriert")
    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Foto groesser als 12 MB")
    mime = file.content_type or "image/jpeg"
    suffix = ".png" if "png" in mime else ".jpg"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, prefix="visitenkarte_", delete=False)
    with tmp:
        tmp.write(data)
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
        chat = LlmChat(api_key=key, session_id=f"card-{uuid.uuid4()}", system_message="Du extrahierst Kontaktdaten von Visitenkarten als JSON.") \
            .with_model("gemini", "gemini-2.5-flash")
        msg = UserMessage(text=CARD_PROMPT, file_contents=[FileContentWithMimeType(file_path=tmp.name, mime_type=mime)])
        raw = await chat.send_message(msg)
    except Exception as e:
        logger.warning(f"Visitenkarten-Scan: {e}")
        raise HTTPException(status_code=502, detail="Visitenkarte konnte nicht gelesen werden - bitte manuell eintragen")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    txt = str(raw).strip()
    mt = re.search(r"\{.*\}", txt, re.S)
    try:
        parsed = json.loads(mt.group(0) if mt else txt)
    except Exception:
        raise HTTPException(status_code=502, detail="KI-Antwort unlesbar - bitte manuell eintragen")
    fields = {k: str(parsed.get(k) or "").strip() for k in LEAD_FIELDS if k in parsed}
    return {"fields": fields, "source": "visitenkarte"}
