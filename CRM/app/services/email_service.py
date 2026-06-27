"""
app/services/email_service.py — AutoMark AI CRM Agent (ORCAST)

Sends handoff-escalation notification emails via Gmail SMTP.
Uses Python's built-in smtplib so no extra dependencies are needed.
Runs the blocking SMTP call in a thread so it doesn't block the event loop.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

import structlog

from config import settings

logger = structlog.get_logger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 465  # SSL


def _send_sync(subject: str, html_body: str, text_body: str) -> None:
    """Blocking SMTP send — called via asyncio.to_thread()."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.GMAIL_SENDER
    msg["To"] = settings.GMAIL_RECIPIENT

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, context=ctx) as server:
        server.login(settings.GMAIL_SENDER, settings.GMAIL_APP_PASSWORD)
        server.sendmail(settings.GMAIL_SENDER, settings.GMAIL_RECIPIENT, msg.as_string())


async def send_handoff_email(
    user_id: str,
    reason: str,
    priority: str,
    lead: dict[str, Any],
    escalation_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> None:
    """
    Send a handoff notification email. Silently skips if Gmail is not
    configured (GMAIL_SENDER / GMAIL_APP_PASSWORD / GMAIL_RECIPIENT missing).
    """
    if not all([settings.GMAIL_SENDER, settings.GMAIL_APP_PASSWORD, settings.GMAIL_RECIPIENT]):
        logger.debug("email_service.skipped_no_config")
        return

    priority_emoji = {"high": "🔴", "urgent": "🚨", "medium": "🟡", "low": "🟢"}.get(priority, "🟡")
    subject = f"{priority_emoji} [{priority.upper()}] Human Handoff Request — {lead.get('name') or user_id}"

    html_body = _build_html(user_id, reason, priority, priority_emoji, lead, escalation_id, notes)
    text_body = _build_text(user_id, reason, priority, lead, escalation_id, notes)

    try:
        await asyncio.to_thread(_send_sync, subject, html_body, text_body)
        logger.info("email_service.handoff_sent", user_id=user_id, recipient=settings.GMAIL_RECIPIENT)
    except Exception as exc:
        logger.error("email_service.send_failed", error=str(exc), user_id=user_id)


def _build_html(
    user_id: str,
    reason: str,
    priority: str,
    priority_emoji: str,
    lead: dict[str, Any],
    escalation_id: Optional[int],
    notes: Optional[str],
) -> str:
    rows = []

    def row(label: str, value: Any) -> None:
        if value:
            rows.append(
                f"<tr><td style='padding:6px 12px;color:#6b7280;font-weight:600;white-space:nowrap'>{label}</td>"
                f"<td style='padding:6px 12px;color:#111827'>{value}</td></tr>"
            )

    row("Priority", f"{priority_emoji} {priority.upper()}")
    row("User ID", user_id)
    row("Escalation ID", escalation_id)
    row("Reason", reason)
    row("Name", lead.get("name"))
    row("Email", lead.get("email"))
    row("Phone", lead.get("phone"))
    row("Company", lead.get("company"))
    row("Lead Score", f"{lead['lead_score']}/100 ({lead.get('lead_temperature')})" if lead.get("lead_score") is not None else None)
    row("Budget", lead.get("budget"))
    row("Authority", lead.get("authority"))
    row("HubSpot Contact", lead.get("hubspot_contact_id"))
    row("HubSpot Deal", lead.get("hubspot_deal_id"))
    row("Notes", notes)

    table = "\n".join(rows)
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;background:#f9fafb;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;
              border:1px solid #e5e7eb;overflow:hidden">
    <div style="background:#1e40af;padding:20px 24px">
      <h1 style="margin:0;color:#fff;font-size:18px">
        {priority_emoji} Human Handoff Request
      </h1>
    </div>
    <div style="padding:24px">
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        {table}
      </table>
    </div>
    <div style="padding:12px 24px;background:#f3f4f6;font-size:12px;color:#9ca3af">
      AutoMark AI CRM — ORCAST Escalation System
    </div>
  </div>
</body>
</html>
"""


def _build_text(
    user_id: str,
    reason: str,
    priority: str,
    lead: dict[str, Any],
    escalation_id: Optional[int],
    notes: Optional[str],
) -> str:
    lines = [
        "HUMAN HANDOFF REQUEST",
        "=" * 40,
        f"Priority:     {priority.upper()}",
        f"User ID:      {user_id}",
    ]
    if escalation_id:
        lines.append(f"Escalation:   #{escalation_id}")
    lines.append(f"Reason:       {reason}")
    if lead.get("name"):
        lines.append(f"Name:         {lead['name']}")
    if lead.get("email"):
        lines.append(f"Email:        {lead['email']}")
    if lead.get("phone"):
        lines.append(f"Phone:        {lead['phone']}")
    if lead.get("company"):
        lines.append(f"Company:      {lead['company']}")
    if lead.get("lead_score") is not None:
        lines.append(f"Lead Score:   {lead['lead_score']}/100 ({lead.get('lead_temperature')})")
    if lead.get("hubspot_contact_id"):
        lines.append(f"HubSpot ID:   {lead['hubspot_contact_id']}")
    if notes:
        lines.append(f"Notes:        {notes}")
    return "\n".join(lines)
