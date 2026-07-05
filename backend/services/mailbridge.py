"""Mailbridge - IMAP poller for the central document inbox (post@eventenergie.app).

Fetches UNSEEN messages, extracts PDF/image attachments, feeds them through the
existing document upload pipeline (AI categorisation, local filesystem, cloud
storage, DATEV forwarding). Messages are marked as \\Seen after processing.
Messages older than IMAP_RETENTION_DAYS are permanently deleted.

Runs as a background asyncio task, started from FastAPI's startup event.
"""
import os
import re
import asyncio
import logging
import email
import imaplib
import mimetypes
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}

# Subject-Keyword-Blacklist (case-insensitive, Wort-Grenzen).
# Bewusst konservativ: Woerter die in echten Rechnungen NIE vorkommen.
# "Angebot" NICHT dabei, weil das ein Kostenvoranschlag sein koennte.
SPAM_SUBJECT_KEYWORDS = [
    r"\bnewsletter\b",
    r"\bwerbung\b",
    r"\bprospekt\b",
    r"\bkatalog\b",
    r"\bsonderaktion\b",
    r"\bsonderpreis(e)?\b",
    r"\bgewinnspiel\b",
    r"\bumfrage\b",
    r"\bblack\s*friday\b",
    r"\bcyber\s*monday\b",
    r"\bdeal\s*of\s*the\s*day\b",
    r"\bnur\s+heute\b",
    r"\bexklusiv(e|es)?\s*angebot\b",
    r"\bsale\b",
    r"\brabatt(aktion)?\b",
    r"%\s*rabatt",
    r"\bfrohes?\s+(fest|weihnachten)\b",
    r"\bfrohe\s+ostern\b",
    r"\bwochen\s*newsletter\b",
    r"\bnews\s*letter\b",
    r"\bunsubscribe\b",
]
_SPAM_SUBJECT_RE = re.compile("|".join(SPAM_SUBJECT_KEYWORDS), re.IGNORECASE)

_mailbridge_task: asyncio.Task | None = None
_last_run_at: datetime | None = None
_last_run_status: str = "idle"
_last_run_stats: dict = {}


def _decode_mime_header(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        parts = decode_header(raw)
        out = []
        for text, enc in parts:
            if isinstance(text, bytes):
                out.append(text.decode(enc or "utf-8", errors="replace"))
            else:
                out.append(text)
        return "".join(out).strip()
    except Exception:
        return str(raw)


def _guess_content_type(filename: str, fallback: str | None) -> str:
    if fallback and fallback.lower() in ALLOWED_CONTENT_TYPES:
        return fallback.lower()
    guessed, _ = mimetypes.guess_type(filename)
    if guessed and guessed.lower() in ALLOWED_CONTENT_TYPES:
        return guessed.lower()
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    mapping = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }
    return mapping.get(ext, "")


def _extract_attachments(msg: email.message.Message) -> list[tuple[str, bytes, str]]:
    """Return list of (filename, raw_bytes, content_type) for supported REAL attachments.
    Signature images, logos etc. (Content-Disposition: inline, or Content-ID referenced)
    are explicitly ignored to prevent spam in the document folder."""
    out = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        # Only accept EXPLICIT attachments. Inline images (signatures, logos, icons)
        # are skipped - they are never what the user wants to archive.
        if "attachment" not in disposition:
            continue
        # Additional guard: parts with Content-ID are typically inline references
        # even if Disposition sloppily says "attachment" (some mail clients do this)
        if part.get("Content-ID") and "inline" in disposition:
            continue
        filename = _decode_mime_header(part.get_filename())
        if not filename:
            continue
        content_type = _guess_content_type(filename, part.get_content_type())
        if not content_type:
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception as e:
            logger.warning(f"Failed to decode attachment {filename}: {e}")
            continue
        if not payload:
            continue
        if len(payload) > 50 * 1024 * 1024:  # 50 MB cap, matches REST upload
            logger.warning(f"Skipping oversize attachment {filename} ({len(payload)} bytes)")
            continue
        # Filter out tiny attachments that are almost certainly decorative
        # (logos, signature icons, tracking pixels). Real docs are >= 15 KB.
        if len(payload) < 15 * 1024:
            logger.info(f"Mailbridge: Anhang '{filename}' nur {len(payload)} B - uebersprungen (zu klein, wahrscheinlich Logo/Signatur)")
            continue
        out.append((filename, payload, content_type))
    return out


def _imap_connect():
    host = os.environ.get("IMAP_HOST")
    port = int(os.environ.get("IMAP_PORT", "993"))
    user = os.environ.get("IMAP_USER")
    pw = os.environ.get("IMAP_PASSWORD")
    folder = os.environ.get("IMAP_FOLDER", "INBOX")
    if not (host and user and pw):
        raise RuntimeError("IMAP credentials incomplete (IMAP_HOST/IMAP_USER/IMAP_PASSWORD)")
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(user, pw)
    mail.select(folder)
    return mail


async def _log_spam(subject: str, sender_email: str, reason: str) -> None:
    """Loggt gefilterte Mails in die 'spam_log' Collection.
    Damit kann der Admin nachschauen was rausgefiltert wurde und ggf. eingreifen."""
    try:
        from server import db as _db_ref
        await _db_ref.spam_log.insert_one({
            "subject": subject or "(kein Betreff)",
            "sender_email": sender_email,
            "reason": reason,
            "filtered_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"spam_log insert failed: {e}")


async def _process_once() -> dict:
    """Single poll cycle: fetch UNSEEN messages, upload attachments, mark as read.
    Also purge messages older than IMAP_RETENTION_DAYS."""
    global _last_run_at, _last_run_status, _last_run_stats
    _last_run_at = datetime.now(timezone.utc)
    stats = {"fetched": 0, "attachments_uploaded": 0, "deleted_old": 0, "errors": 0}

    try:
        mail = await asyncio.to_thread(_imap_connect)
    except Exception as e:
        logger.error(f"Mailbridge IMAP connect failed: {e}")
        _last_run_status = f"error: {e}"
        return stats

    try:
        # ── Fetch unread messages ───────────────────────────────────────
        typ, data = await asyncio.to_thread(mail.search, None, "UNSEEN")
        if typ != "OK":
            raise RuntimeError(f"IMAP SEARCH UNSEEN failed: {typ}")
        uids = data[0].split() if data and data[0] else []
        logger.info(f"Mailbridge: {len(uids)} neue Mails gefunden")

        from routes.documents import create_document_from_bytes

        # Load learned spam senders/domains (from user "Als Spam markieren" clicks).
        # Lazy import to avoid circular dependency at module load.
        try:
            from server import db as _db_ref
            spam_entries = [d async for d in _db_ref.spam_blacklist.find({}, {"_id": 0})]
        except Exception:
            spam_entries = []
        blocked_domains = {e.get("sender_domain", "").lower() for e in spam_entries if e.get("sender_domain")}
        blocked_emails = {e.get("sender_email", "").lower() for e in spam_entries if e.get("sender_email")}

        for uid in uids:
            try:
                typ, msg_data = await asyncio.to_thread(mail.fetch, uid, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    stats["errors"] += 1
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                subject = _decode_mime_header(msg.get("Subject"))
                sender_raw = _decode_mime_header(msg.get("From"))
                _, sender_email = parseaddr(sender_raw)
                sender_email = (sender_email or "").lower()
                sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
                stats["fetched"] += 1

                # ─── SPAM-FILTER ────────────────────────────────────────
                # Layer 1: List-Unsubscribe Header (Newsletter/Marketing MUSS diesen setzen)
                if msg.get("List-Unsubscribe") or msg.get("List-Unsubscribe-Post"):
                    logger.info(f"Mailbridge: Newsletter erkannt (List-Unsubscribe) - '{subject}' von {sender_email} - uebersprungen")
                    await _log_spam(subject, sender_email, "list_unsubscribe")
                    stats.setdefault("spam_filtered", 0)
                    stats["spam_filtered"] += 1
                    await asyncio.to_thread(mail.store, uid, "+FLAGS", "\\Seen")
                    continue

                # Layer 3: Subject-Keyword-Blacklist
                if subject and _SPAM_SUBJECT_RE.search(subject):
                    matched = _SPAM_SUBJECT_RE.search(subject).group(0)
                    logger.info(f"Mailbridge: Spam-Keyword '{matched}' im Betreff - '{subject}' von {sender_email} - uebersprungen")
                    await _log_spam(subject, sender_email, f"keyword:{matched}")
                    stats.setdefault("spam_filtered", 0)
                    stats["spam_filtered"] += 1
                    await asyncio.to_thread(mail.store, uid, "+FLAGS", "\\Seen")
                    continue

                # Gelernte Spam-Absender (durch "Als Spam markieren"-Button trainiert)
                if sender_email and sender_email in blocked_emails:
                    logger.info(f"Mailbridge: Absender {sender_email} auf Blacklist - '{subject}' uebersprungen")
                    await _log_spam(subject, sender_email, "learned_email")
                    stats.setdefault("spam_filtered", 0)
                    stats["spam_filtered"] += 1
                    await asyncio.to_thread(mail.store, uid, "+FLAGS", "\\Seen")
                    continue
                if sender_domain and sender_domain in blocked_domains:
                    logger.info(f"Mailbridge: Domain {sender_domain} auf Blacklist - '{subject}' uebersprungen")
                    await _log_spam(subject, sender_email, "learned_domain")
                    stats.setdefault("spam_filtered", 0)
                    stats["spam_filtered"] += 1
                    await asyncio.to_thread(mail.store, uid, "+FLAGS", "\\Seen")
                    continue

                attachments = _extract_attachments(msg)
                if not attachments:
                    logger.info(f"Mailbridge: Mail ohne unterstuetzte Anhaenge - '{subject}' von {sender_email}")
                else:
                    for fname, payload, ctype in attachments:
                        try:
                            await create_document_from_bytes(
                                payload, fname, ctype, folder_id="unbekannt", source="mailbridge"
                            )
                            stats["attachments_uploaded"] += 1
                            logger.info(f"Mailbridge: Anhang importiert '{fname}' ({ctype}) aus Mail '{subject}'")
                        except Exception as e:
                            logger.error(f"Mailbridge: Upload von '{fname}' gescheitert: {e}")
                            stats["errors"] += 1
                # Mark as read regardless (even if no attachments - avoid re-processing)
                await asyncio.to_thread(mail.store, uid, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.error(f"Mailbridge: Mail-Verarbeitung gescheitert: {e}")
                stats["errors"] += 1

        # ── Purge old mails (> retention days) ──────────────────────────
        retention_days = int(os.environ.get("IMAP_RETENTION_DAYS", "30"))
        if retention_days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%d-%b-%Y")
            typ, data = await asyncio.to_thread(mail.search, None, f'(BEFORE {cutoff})')
            if typ == "OK" and data and data[0]:
                old_uids = data[0].split()
                for uid in old_uids:
                    try:
                        await asyncio.to_thread(mail.store, uid, "+FLAGS", "\\Deleted")
                        stats["deleted_old"] += 1
                    except Exception as e:
                        logger.warning(f"Mailbridge: \\Deleted fuer UID {uid} fehlgeschlagen: {e}")
                if stats["deleted_old"]:
                    await asyncio.to_thread(mail.expunge)
                    logger.info(f"Mailbridge: {stats['deleted_old']} alte Mails (>{retention_days}d) geloescht")

        _last_run_status = "ok"
    except Exception as e:
        logger.error(f"Mailbridge run failed: {e}")
        _last_run_status = f"error: {e}"
        stats["errors"] += 1
    finally:
        try:
            await asyncio.to_thread(mail.logout)
        except Exception:
            pass

    _last_run_stats = stats
    return stats


async def _poll_loop():
    """Endless loop: process once, sleep for IMAP_POLL_INTERVAL seconds."""
    interval = int(os.environ.get("IMAP_POLL_INTERVAL", "300"))
    logger.info(f"Mailbridge poll loop gestartet (Intervall: {interval}s)")
    while True:
        try:
            if os.environ.get("IMAP_PASSWORD"):
                await _process_once()
            else:
                logger.debug("Mailbridge: IMAP_PASSWORD leer - uebersprungen")
        except Exception as e:
            logger.error(f"Mailbridge poll iteration failed: {e}")
        await asyncio.sleep(interval)


def start_mailbridge():
    """Start the background poll task. Idempotent."""
    global _mailbridge_task
    if _mailbridge_task and not _mailbridge_task.done():
        return
    if not os.environ.get("IMAP_HOST") or not os.environ.get("IMAP_USER"):
        logger.info("Mailbridge: IMAP nicht konfiguriert - Service nicht gestartet")
        return
    loop = asyncio.get_event_loop()
    _mailbridge_task = loop.create_task(_poll_loop())
    logger.info("Mailbridge-Service gestartet")


def get_status() -> dict:
    return {
        "running": bool(_mailbridge_task and not _mailbridge_task.done()),
        "configured": bool(os.environ.get("IMAP_HOST") and os.environ.get("IMAP_USER")),
        "password_set": bool(os.environ.get("IMAP_PASSWORD")),
        "host": os.environ.get("IMAP_HOST"),
        "user": os.environ.get("IMAP_USER"),
        "folder": os.environ.get("IMAP_FOLDER", "INBOX"),
        "poll_interval_seconds": int(os.environ.get("IMAP_POLL_INTERVAL", "300")),
        "retention_days": int(os.environ.get("IMAP_RETENTION_DAYS", "30")),
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "last_run_status": _last_run_status,
        "last_run_stats": _last_run_stats,
    }


async def trigger_now() -> dict:
    """Manually trigger a single poll cycle (used by admin endpoint)."""
    return await _process_once()
