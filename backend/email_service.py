import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def _get_smtp_config():
    return {
        "host": os.environ.get("SMTP_HOST"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER"),
        "password": os.environ.get("SMTP_PASSWORD"),
        "sender_name": os.environ.get("SMTP_SENDER_NAME", "Eventenergie Portal"),
    }


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
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


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
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {__import__('datetime').datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
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
    <p style="margin:0;color:#aaa;font-size:11px;text-align:center;">&copy; {__import__('datetime').datetime.now().year} Eventenergie Deutschland GmbH &amp; Co. KG</p>
  </div>
</div>
</body></html>"""
    return send_email(to_email, subject, html)
