"""
app/services/email_service.py — AutoMark AI CRM Agent (ORCAST)

Sends handoff-escalation notification emails.

Delivery order (first success wins):
  1. Gmail REST API over HTTPS port 443  — works on any network, no firewall issues
  2. SMTP port 587 STARTTLS              — standard, firewall-friendly
  3. SMTP port 465 SSL                   — fallback
  4. Local JSON file in CRM/handoffs/    — guaranteed capture even if all else fails
"""

from __future__ import annotations

import asyncio
import base64
import json
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)

_SMTP_HOST      = "smtp.gmail.com"
_SMTP_PORT_TLS  = 587
_SMTP_PORT_SSL  = 465
_RESEND_API     = "https://api.resend.com/emails"
_HANDOFFS_DIR   = Path(__file__).resolve().parents[3] / "handoffs"


# ── Strategy 1: Resend API (HTTPS port 443 — no firewall issues) ─────────────

async def _send_via_resend(subject: str, html_body: str, text_body: str) -> None:
    """
    Send via Resend.com REST API (https://resend.com).
    Works over port 443 — passes every firewall.
    Free tier: 3 000 emails / month.
    Requires: RESEND_API_KEY (set in .env as RESEND_API_KEY=re_xxx).
    """
    if not settings.RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY not configured")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            _RESEND_API,
            json={
                "from":    settings.GMAIL_SENDER,
                "to":      [settings.GMAIL_RECIPIENT],
                "subject": subject,
                "html":    html_body,
                "text":    text_body,
            },
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )
        resp.raise_for_status()


# ── Strategy 2 & 3: SMTP (ports 587 / 465) ───────────────────────────────────

def _send_via_smtp(subject: str, html_body: str, text_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.GMAIL_SENDER
    msg["To"]      = settings.GMAIL_RECIPIENT
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    ctx = ssl.create_default_context()
    raw = msg.as_string()

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT_TLS, timeout=10) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
            s.login(settings.GMAIL_SENDER, settings.GMAIL_APP_PASSWORD)
            s.sendmail(settings.GMAIL_SENDER, settings.GMAIL_RECIPIENT, raw)
        return
    except (OSError, smtplib.SMTPException):
        pass

    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT_SSL, context=ctx, timeout=10) as s:
        s.login(settings.GMAIL_SENDER, settings.GMAIL_APP_PASSWORD)
        s.sendmail(settings.GMAIL_SENDER, settings.GMAIL_RECIPIENT, raw)


# ── Strategy 4: Local JSON file (guaranteed backup) ──────────────────────────

def _save_local(user_id: str, reason: str, priority: str,
                lead: dict, escalation_id: Optional[int],
                summary: Optional[str], text_body: str) -> None:
    _HANDOFFS_DIR.mkdir(exist_ok=True)
    ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = _HANDOFFS_DIR / f"{ts}_{user_id[:12]}.json"
    out.write_text(json.dumps({
        "timestamp":    ts,
        "user_id":      user_id,
        "priority":     priority,
        "reason":       reason,
        "escalation_id":escalation_id,
        "lead":         lead,
        "summary":      summary,
        "text":         text_body,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("email_service.saved_local", path=str(out))


# ── Public entry point ────────────────────────────────────────────────────────

async def send_handoff_email(
    user_id: str,
    reason: str,
    priority: str,
    lead: dict[str, Any],
    escalation_id: Optional[int] = None,
    notes: Optional[str] = None,
    summary: Optional[str] = None,
    recent_messages: Optional[list[dict[str, Any]]] = None,
) -> None:
    if not all([settings.GMAIL_SENDER, settings.GMAIL_APP_PASSWORD, settings.GMAIL_RECIPIENT]):
        logger.debug("email_service.skipped_no_config")
        return

    lead = lead or {}
    name    = lead.get("name") or user_id[:12]
    score   = f" · score {lead['lead_score']}/100" if lead.get("lead_score") is not None else ""
    subject = f"[{priority.upper()}] Handoff: {name}{score}"   # short, no emoji

    html_body = _build_html(user_id, reason, priority, lead,
                            escalation_id, notes, summary, recent_messages or [])
    text_body = _build_text(user_id, reason, priority, lead,
                            escalation_id, notes, summary, recent_messages or [])

    # 1. Resend API (HTTPS port 443 — works everywhere)
    try:
        await _send_via_resend(subject, html_body, text_body)
        logger.info("email_service.sent_via_resend", user_id=user_id, to=settings.GMAIL_RECIPIENT)
        return
    except Exception as exc:
        err = str(exc)
        hint = ""
        if "403" in err:
            hint = (
                "Resend 403: the sender domain is not verified. "
                "Go to resend.com → Domains → Add your domain, OR "
                "set RESEND_API_KEY= (empty) in .env to skip Resend and use Gmail SMTP directly."
            )
        logger.warning("email_service.resend_failed", error=err[:120], hint=hint or None)

    # 2. SMTP port 587 / 465 fallback
    try:
        await asyncio.to_thread(_send_via_smtp, subject, html_body, text_body)
        logger.info("email_service.sent_via_smtp", user_id=user_id)
        return
    except Exception as exc:
        logger.warning("email_service.smtp_failed", error=str(exc)[:120])

    # 3. Local JSON file — handoff is never lost
    try:
        _save_local(user_id, reason, priority, lead, escalation_id, summary, text_body)
        logger.warning(
            "email_service.saved_locally",
            user_id=user_id,
            path=str(_HANDOFFS_DIR),
            hint="Add RESEND_API_KEY to .env for email delivery (free at resend.com)",
        )
    except Exception as exc:
        logger.error("email_service.all_delivery_failed", error=str(exc), user_id=user_id)


# ── HTML builder ──────────────────────────────────────────────────────────────

def _build_html(
    user_id: str, reason: str, priority: str,
    lead: dict[str, Any], escalation_id: Optional[int], notes: Optional[str],
    summary: Optional[str] = None, recent_messages: Optional[list[dict[str, Any]]] = None,
) -> str:
    badge_color = {"high": "#dc2626", "urgent": "#7c3aed", "medium": "#d97706", "low": "#16a34a"}.get(priority, "#d97706")

    def td(label: str, value: Any) -> str:
        if not value:
            return ""
        return (f"<tr><td style='padding:5px 12px;color:#6b7280;font-size:13px;white-space:nowrap'>{label}</td>"
                f"<td style='padding:5px 12px;color:#111827;font-size:13px'>{value}</td></tr>")

    lead_rows = (
        td("Name",   lead.get("name"))
        + td("Email",  lead.get("email"))
        + td("Phone",  lead.get("phone"))
        + td("Company",lead.get("company"))
        + td("Score",  f"{lead['lead_score']}/100 ({lead.get('lead_temperature')})" if lead.get("lead_score") is not None else None)
        + td("Budget", lead.get("budget"))
        + td("HubSpot",lead.get("hubspot_contact_id"))
    )

    # ── Conversation summary (main content) ──────────────────────────────────
    summary_block = ""
    if summary:
        summary_block = f"""
      <div style="margin-bottom:20px">
        <div style="font-size:12px;font-weight:700;color:#6b7280;text-transform:uppercase;
                    letter-spacing:.05em;margin-bottom:8px">Conversation Summary</div>
        <div style="background:#f0f9ff;border-left:4px solid #2563eb;padding:12px 16px;
                    font-size:14px;color:#1e3a5f;line-height:1.7;white-space:pre-wrap">{summary}</div>
      </div>"""

    # ── Recent messages transcript ────────────────────────────────────────────
    transcript_block = ""
    msgs = recent_messages or []
    if msgs:
        bubbles = []
        for m in msgs[-10:]:
            role    = m.get("role", "user")
            content = m.get("content", "")[:400]
            is_user = role == "user"
            align   = "right" if is_user else "left"
            bg      = "#dbeafe" if is_user else "#f1f5f9"
            label   = "Customer" if is_user else "Agent"
            bubbles.append(
                f"<div style='text-align:{align};margin:6px 0'>"
                f"<span style='font-size:10px;color:#9ca3af;display:block'>{label}</span>"
                f"<span style='display:inline-block;background:{bg};border-radius:10px;"
                f"padding:8px 12px;font-size:13px;color:#1f2937;max-width:85%;text-align:left'>{content}</span>"
                f"</div>"
            )
        transcript_block = f"""
      <div>
        <div style="font-size:12px;font-weight:700;color:#6b7280;text-transform:uppercase;
                    letter-spacing:.05em;margin-bottom:8px">Conversation ({len(msgs)} turns)</div>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px 14px">
          {"".join(bubbles)}
        </div>
      </div>"""

    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;background:#f3f4f6;padding:24px;margin:0">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:10px;
            border:1px solid #e5e7eb;overflow:hidden">

  <!-- Header -->
  <div style="background:{badge_color};padding:18px 24px;display:flex;align-items:center">
    <span style="background:rgba(255,255,255,.2);color:#fff;font-size:11px;font-weight:700;
                 padding:3px 8px;border-radius:4px;text-transform:uppercase;margin-right:10px">{priority}</span>
    <span style="color:#fff;font-size:16px;font-weight:600">Human Handoff — {lead.get("name") or user_id[:12]}</span>
  </div>

  <!-- Reason + Lead quick-view -->
  <div style="padding:20px 24px 0">
    <div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;
                padding:10px 14px;font-size:14px;color:#713f12;margin-bottom:16px">
      <strong>Reason:</strong> {reason}
    </div>
    <table style="border-collapse:collapse;width:100%">{lead_rows}</table>
  </div>

  <!-- Summary + Transcript -->
  <div style="padding:20px 24px">
    {summary_block}
    {transcript_block}
  </div>

  <!-- Footer -->
  <div style="padding:10px 24px;background:#f9fafb;font-size:11px;color:#9ca3af;
              border-top:1px solid #e5e7eb">
    AutoMark AI · Escalation #{escalation_id} · User {user_id}
  </div>
</div>
</body></html>"""


# ── Text builder ──────────────────────────────────────────────────────────────

def _build_text(
    user_id: str, reason: str, priority: str,
    lead: dict[str, Any], escalation_id: Optional[int], notes: Optional[str],
    summary: Optional[str] = None, recent_messages: Optional[list[dict[str, Any]]] = None,
) -> str:
    lines = ["HUMAN HANDOFF REQUEST", "=" * 40,
             f"Priority:  {priority.upper()}", f"User ID:   {user_id}"]
    if escalation_id:
        lines.append(f"Escalation: #{escalation_id}")
    lines.append(f"Reason:    {reason}")
    for k, v in [("Name", lead.get("name")), ("Email", lead.get("email")),
                 ("Phone", lead.get("phone")), ("Company", lead.get("company"))]:
        if v:
            lines.append(f"{k}:   {v}")
    if lead.get("lead_score") is not None:
        lines.append(f"Score:     {lead['lead_score']}/100 ({lead.get('lead_temperature')})")
    if notes:
        lines.append(f"Notes:     {notes}")
    if summary:
        lines += ["", "=" * 40, "CONVERSATION SUMMARY", "=" * 40, summary]
    msgs = recent_messages or []
    if msgs:
        lines += ["", "=" * 40, f"RECENT CONVERSATION ({len(msgs)} turns)", "=" * 40]
        for m in msgs[-10:]:
            role    = "Customer" if m.get("role") == "user" else "Agent"
            content = m.get("content", "")[:400]
            lines.append(f"[{role}] {content}")
    return "\n".join(lines)
