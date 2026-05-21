"""
email_service.py — Resend.com integration for license delivery + invoices.

Resend free tier: 100 emails/day, 3000/month. Once you outgrow it ($20/mo for
50k emails), the API remains identical.

Set RESEND_API_KEY env var. Sender domain must be verified in Resend dashboard
(add DNS TXT records — instructions in deploy/ folder).
"""

import os
import json
from urllib.request import Request, urlopen
from datetime import datetime


RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_API_URL = "https://api.resend.com/emails"
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "FreeSystemDoctor <noreply@freesystemdoctor.pl>")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@freesystemdoctor.pl")


def _resend_send(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        print(f"[DEMO] would send to {to}: {subject}")
        return False
    payload = {
        "from": SENDER_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    req = Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Resend error: {e}")
        return False


def send_license_email(*, to: str, key: str, tier: str, period: str,
                       expiry_iso: str, devices_max: int) -> bool:
    tier_label = "Ultimate" if tier == "ultimate" else "Pro"
    period_label = "dożywotnia" if period == "lifetime" else "1 rok"
    expiry = (
        f"<p><strong>Wygasa:</strong> {expiry_iso[:10]}</p>"
        if expiry_iso else
        "<p><strong>Licencja dożywotnia</strong> — nie wygasa.</p>"
    )

    html = f"""
    <div style="font-family:'Segoe UI',sans-serif;background:#0a0d14;color:#f0f3f9;padding:30px;max-width:600px;margin:0 auto;border-radius:12px;">
      <div style="text-align:center;margin-bottom:24px;">
        <div style="font-size:32px;">⚕</div>
        <h1 style="margin:8px 0;">FreeSystemDoctor <span style="color:#ffc857;">{tier_label}</span></h1>
        <p style="color:#8993a8;">Dziękujemy za zakup!</p>
      </div>

      <div style="background:#14181f;border:1px solid #2a3040;border-radius:8px;padding:24px;margin:20px 0;">
        <p style="margin:0 0 10px;color:#8993a8;font-size:12px;letter-spacing:1px;text-transform:uppercase;">Twój klucz licencyjny</p>
        <code style="display:block;background:#0a0d14;padding:14px;border-radius:6px;font-size:18px;color:#ffc857;font-family:monospace;letter-spacing:1px;text-align:center;">{key}</code>
      </div>

      <div style="background:#14181f;border:1px solid #2a3040;border-radius:8px;padding:20px;">
        <p><strong>Tier:</strong> {tier_label}</p>
        <p><strong>Okres:</strong> {period_label}</p>
        <p><strong>Urządzenia:</strong> {devices_max}</p>
        {expiry}
      </div>

      <h2 style="margin-top:30px;">Jak aktywować</h2>
      <ol style="color:#f0f3f9;line-height:1.8;">
        <li>Pobierz FreeSystemDoctor PRO: <a href="https://caytec.github.io/freesystemdoctor-pro" style="color:#4f7ef8;">caytec.github.io/freesystemdoctor-pro</a></li>
        <li>Uruchom aplikację (UAC zaakceptuj)</li>
        <li>Wejdź w <strong>Settings → License</strong></li>
        <li>Wklej klucz: <code style="background:#1d222d;padding:2px 6px;border-radius:3px;">{key}</code></li>
        <li>Kliknij <strong>Activate</strong> — gotowe!</li>
      </ol>

      <div style="text-align:center;margin:30px 0;">
        <a href="https://caytec.github.io/freesystemdoctor-pro/download" style="background:linear-gradient(135deg,#ffc857,#d4a23a);color:#1a1207;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;display:inline-block;">⬇ Pobierz Pro</a>
      </div>

      <hr style="border:none;border-top:1px solid #2a3040;margin:30px 0;">

      <p style="color:#8993a8;font-size:13px;">
        Problem z aktywacją? Napisz na <a href="mailto:{SUPPORT_EMAIL}" style="color:#4f7ef8;">{SUPPORT_EMAIL}</a> — odpowiadamy w 24h.<br>
        Faktura VAT trafi w osobnym mailu.
      </p>
      <p style="color:#6b7a99;font-size:11px;text-align:center;margin-top:20px;">
        © 2026 caytec · FreeSystemDoctor · Polish-developed · Open source
      </p>
    </div>
    """

    return _resend_send(
        to=to,
        subject=f"🔑 Twój klucz FreeSystemDoctor {tier_label}",
        html=html,
    )


def send_invoice_email(*, to: str, tier: str, period: str,
                       amount: float, currency: str, transaction_id: str) -> bool:
    tier_label = "Ultimate" if tier == "ultimate" else "Pro"
    period_label = "Lifetime" if period == "lifetime" else "1 rok"
    net = round(amount / 1.23, 2)
    vat = round(amount - net, 2)
    date = datetime.utcnow().strftime("%Y-%m-%d")

    html = f"""
    <div style="font-family:'Segoe UI',sans-serif;background:#fff;color:#1a1a1a;padding:40px;max-width:700px;margin:0 auto;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td>
            <h1 style="color:#1a1a1a;margin:0;">Faktura VAT</h1>
            <p style="color:#666;margin:4px 0;">Nr {transaction_id[:12]}</p>
            <p style="color:#666;margin:4px 0;">Data wystawienia: {date}</p>
          </td>
          <td style="text-align:right;">
            <div style="font-size:24px;font-weight:700;">FreeSystemDoctor</div>
            <p style="color:#666;font-size:13px;margin:4px 0;">caytec</p>
            <p style="color:#666;font-size:13px;margin:4px 0;">NIP: [zaktualizuj]</p>
          </td>
        </tr>
      </table>

      <hr style="border:none;border-top:2px solid #1a1a1a;margin:24px 0;">

      <p><strong>Nabywca:</strong> {to}</p>

      <table style="width:100%;border-collapse:collapse;margin:30px 0;">
        <thead>
          <tr style="background:#f5f5f5;">
            <th style="text-align:left;padding:12px;border:1px solid #ddd;">Pozycja</th>
            <th style="text-align:right;padding:12px;border:1px solid #ddd;">Netto</th>
            <th style="text-align:right;padding:12px;border:1px solid #ddd;">VAT 23%</th>
            <th style="text-align:right;padding:12px;border:1px solid #ddd;">Brutto</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding:12px;border:1px solid #ddd;">FreeSystemDoctor {tier_label} ({period_label})</td>
            <td style="text-align:right;padding:12px;border:1px solid #ddd;">{net:.2f} {currency}</td>
            <td style="text-align:right;padding:12px;border:1px solid #ddd;">{vat:.2f} {currency}</td>
            <td style="text-align:right;padding:12px;border:1px solid #ddd;"><strong>{amount:.2f} {currency}</strong></td>
          </tr>
        </tbody>
      </table>

      <p style="text-align:right;font-size:18px;"><strong>Razem: {amount:.2f} {currency}</strong></p>

      <hr style="border:none;border-top:1px solid #ddd;margin:30px 0;">

      <p style="color:#666;font-size:12px;">
        Sposób płatności: Online · Status: Opłacone<br>
        Transakcja: {transaction_id}<br><br>
        Pytania? <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>
      </p>
    </div>
    """

    return _resend_send(
        to=to,
        subject=f"Faktura VAT — FreeSystemDoctor {tier_label}",
        html=html,
    )
