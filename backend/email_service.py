import smtplib
import os
import ssl
import time
import socket
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "60"))
SMTP_MAX_RETRIES = int(os.environ.get("SMTP_MAX_RETRIES", "3"))


def _get_smtp_config():
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "sender_name": os.environ.get("SMTP_SENDER_NAME", "Eventenergie Portal"),
    }


def _open_smtp_connection(cfg):
    """Open an SMTP_SSL connection with a longer timeout and retry on transient failures."""
    last_err = None
    # SSL-Context mit certifi CA-Bundle (Mozilla-Root-CAs). Ohne diesen greift
    # ssl.create_default_context() auf systemabhaengige Trust-Stores zurueck,
    # was auf Windows-Servern haeufig fehlt und "CERTIFICATE_VERIFY_FAILED"
    # aufwirft. certifi wird von httpx/requests bereits mit installiert.
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
    # Optionaler Escape-Hatch: SMTP_INSECURE_SSL=1 in .env deaktiviert die
    # Zertifikatspruefung komplett. Nur nutzen wenn certifi das Problem
    # nicht loest (z.B. selbstsigniertes Zertifikat auf dem eigenen MX).
    if os.environ.get("SMTP_INSECURE_SSL", "").lower() in ("1", "true", "yes"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        logger.warning("SMTP_INSECURE_SSL aktiv - SSL-Zertifikat wird NICHT geprueft (unsicher)")
    for attempt in range(1, SMTP_MAX_RETRIES + 1):
        try:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=SMTP_TIMEOUT, context=ctx)
            server.login(cfg["user"], cfg["password"])
            return server
        except ssl.SSLCertVerificationError as e:
            # Kein Retry - Zertifikatspruefung wird sich nicht magisch aendern
            logger.error(
                f"SMTP SSL-Zertifikatspruefung fehlgeschlagen: {e}. "
                f"Loesungen: 1) 'pip install --upgrade certifi', "
                f"2) SMTP_INSECURE_SSL=1 in .env setzen (nur als Notloesung)."
            )
            raise
        except (socket.timeout, ssl.SSLError, smtplib.SMTPServerDisconnected, ConnectionError, OSError) as e:
            last_err = e
            logger.warning(f"SMTP connect attempt {attempt}/{SMTP_MAX_RETRIES} failed: {e}")
            if attempt < SMTP_MAX_RETRIES:
                time.sleep(2 * attempt)  # 2s, 4s backoff
    raise last_err  # re-raise after retries exhausted


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    cfg = _get_smtp_config()
    if not all([cfg["host"], cfg["user"], cfg["password"]]):
        logger.error("SMTP not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg['sender_name']} <{cfg['user']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = _open_smtp_connection(cfg)
        try:
            server.sendmail(cfg["user"], to_email, msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                pass
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def send_email_with_attachment(to_email: str, subject: str, html_body: str, attachment_bytes: bytes, attachment_filename: str, bcc: list = None) -> bool:
    cfg = _get_smtp_config()
    if not all([cfg["host"], cfg["user"], cfg["password"]]):
        logger.error("SMTP not configured")
        raise Exception("SMTP nicht konfiguriert")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{cfg['sender_name']} <{cfg['user']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    att = MIMEApplication(attachment_bytes, _subtype="pdf", Name=attachment_filename)
    att.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
    msg.attach(att)

    # Open connection ONCE and reuse for main mail + BCC copies
    server = _open_smtp_connection(cfg)
    try:
        try:
            server.sendmail(cfg["user"], [to_email], msg.as_string())
            logger.info(f"Email with attachment sent to {to_email}")
        except Exception as e:
            logger.error(f"Email send with attachment failed: {e}")
            raise

        # BCC als separate E-Mail senden (zuverlaessiger als SMTP-BCC), reuse connection
        if bcc:
            for bcc_addr in bcc:
                try:
                    bcc_msg = MIMEMultipart("mixed")
                    bcc_msg["Subject"] = f"[Kopie] {subject}"
                    bcc_msg["From"] = f"{cfg['sender_name']} <{cfg['user']}>"
                    bcc_msg["To"] = bcc_addr
                    bcc_msg.attach(MIMEText(html_body, "html", "utf-8"))
                    bcc_att = MIMEApplication(attachment_bytes, _subtype="pdf", Name=attachment_filename)
                    bcc_att.add_header("Content-Disposition", f'attachment; filename="{attachment_filename}"')
                    bcc_msg.attach(bcc_att)

                    server.sendmail(cfg["user"], [bcc_addr], bcc_msg.as_string())
                    logger.info(f"BCC copy sent to {bcc_addr}")
                except Exception as e:
                    logger.error(f"BCC copy to {bcc_addr} failed: {e}")
                    # Connection may be dead; try to reopen for next BCC
                    try:
                        server.quit()
                    except Exception:
                        pass
                    try:
                        server = _open_smtp_connection(cfg)
                    except Exception as reopen_err:
                        logger.error(f"Could not reopen SMTP for further BCCs: {reopen_err}")
                        break
    finally:
        try:
            server.quit()
        except Exception:
            pass

    return True




def send_password_reset_email(to_email: str, user_name: str, reset_link: str) -> bool:
    subject = "Passwort zurücksetzen – Eventenergie Portal"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">
  <div style="background:#d946ef;padding:28px 32px;">
    <h1 style="margin:0;color:#fff;font-size:20px;">Eventenergie Portal</h1>
  </div>
  <div style="padding:32px;">
    <p style="color:#333;font-size:15px;line-height:1.6;">Hallo {user_name},</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Sie haben eine Anfrage zum Zurücksetzen Ihres Passworts gestellt.
      Klicken Sie auf den folgenden Button, um ein neues Passwort zu vergeben:
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{reset_link}" style="display:inline-block;background:#d946ef;color:#fff;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:600;">
        Passwort zurücksetzen
      </a>
    </div>
    <p style="color:#888;font-size:12px;line-height:1.5;">
      Dieser Link ist 24 Stunden gültig. Falls Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.
    </p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""
    return send_email(to_email, subject, html)


def send_admin_reset_email(to_email: str, user_name: str, reset_link: str) -> bool:
    subject = "Ihr Passwort wurde zurückgesetzt – Eventenergie Portal"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f5f5f5;">
<div style="max-width:520px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e5e5;">
  <div style="background:#d946ef;padding:28px 32px;">
    <h1 style="margin:0;color:#fff;font-size:20px;">Eventenergie Portal</h1>
  </div>
  <div style="padding:32px;">
    <p style="color:#333;font-size:15px;line-height:1.6;">Hallo {user_name},</p>
    <p style="color:#555;font-size:14px;line-height:1.6;">
      Ihr Administrator hat für Sie einen Link zum Zurücksetzen Ihres Passworts erstellt.
      Bitte klicken Sie auf den folgenden Button:
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{reset_link}" style="display:inline-block;background:#d946ef;color:#fff;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:600;">
        Neues Passwort vergeben
      </a>
    </div>
    <p style="color:#888;font-size:12px;line-height:1.5;">
      Dieser Link ist 24 Stunden gültig.
    </p>
  </div>
  <div style="background:#fafafa;padding:16px 32px;border-top:1px solid #eee;">
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""
    return send_email(to_email, subject, html)
