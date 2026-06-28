"""
shared/log_visualizer.py - Parse CRM JSON logs and render pipeline stats.

Usage:
    uvicorn main:app ... 2>&1 | python -m shared.log_visualizer
    python -m shared.log_visualizer crm.log

    # Programmatic (used by Analytics Streamlit):
    from shared.log_visualizer import parse_events, build_figure
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Optional

SEP  = "-" * 72
STEP_MAP = {
    "orchestrator.run_graph.start":  "[ START         ]",
    "graph.intent_classified":       "[ INTENT        ]",
    "graph.hubspot_node":            "[ HUBSPOT       ]",
    "graph.rag_node":                "[ RAG SEARCH    ]",
    "graph.lead_scoring_node":       "[ LEAD SCORE    ]",
    "graph.handoff_node":            "[ ESCALATION    ]",
    "graph.generate_response":       "[ RESPONSE GEN  ]",
    "messaging_tool.send_reply":     "[ SEND REPLY    ]",
    "messenger.message_sent":        "[ MSG DELIVERED ]",
    "fb_comments.reply_sent":        "[ CMT DELIVERED ]",
    "messenger.commenter_dm_sent":       "[ DM SENT       ]",
    "messaging_tool.messenger_reply_sent": "[ REPLY CONFIRM ]",
    "messaging_tool.fb_comment_reply_sent": "[ CMT CONFIRM   ]",
    "email_service.handoff_sent":    "[ EMAIL SENT    ]",
    "orchestrator.run_graph.done":   "[ DONE          ]",
}


def _ts(s: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_events(lines: list[str]) -> list[dict]:
    events = []
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "event" not in obj or "timestamp" not in obj:
            continue
        ts = _ts(obj["timestamp"])
        if ts:
            events.append({"event": obj["event"], "ts": ts, "raw": obj})

    if not events:
        return []
    t0 = events[0]["ts"]
    for e in events:
        e["ms"] = round((e["ts"] - t0).total_seconds() * 1000)
    return events


def _bar(ms: int, total_ms: int, width: int = 36) -> str:
    if total_ms == 0:
        return ""
    filled = round((ms / total_ms) * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def print_timeline(events: list[dict]) -> None:
    if not events:
        print("No CRM events found.")
        return

    total_ms = events[-1]["ms"]
    user_id  = events[0]["raw"].get("user_id", "unknown")
    source   = events[0]["raw"].get("source", "?")

    print()
    print(SEP)
    print(f"  ORCAST Pipeline  |  user={user_id[:20]}  source={source}")
    print(SEP)
    print(f"  {'Step':<18} {'t(ms)':>7}  {'delta':>6}  Timeline")
    print(SEP)

    prev_ms = 0
    for e in events:
        key   = e["event"]
        ms    = e["ms"]
        delta = ms - prev_ms
        label = STEP_MAP.get(key, f"[ {key[:16]:<16} ]")
        bar   = _bar(ms, total_ms)
        extra = ""
        if "intent" in e["raw"]:
            extra = f"  -> {e['raw']['intent']}"
        if e["raw"].get("escalated"):
            extra += "  ESCALATED!"
        if e["raw"].get("success") is False:
            extra += "  FAILED"
        print(f"  {label}  {ms:>6}ms  {delta:>5}ms  {bar}{extra}")
        prev_ms = ms

    print(SEP)
    intent    = next((e["raw"].get("intent","?") for e in events if "intent" in e["raw"]), "?")
    tools     = next((e["raw"].get("tools_called",[]) for e in events if "tools_called" in e["raw"]), [])
    escalated = any(e["raw"].get("escalated") for e in events)
    delivered = any(e["event"] in ("messenger.message_sent","fb_comments.reply_sent") for e in events)

    print(f"  Total    : {total_ms}ms  ({total_ms/1000:.2f}s)")
    print(f"  Intent   : {intent}")
    print(f"  Tools    : {', '.join(tools) if tools else 'none'}")
    print(f"  Escalated: {'YES' if escalated else 'no'}")
    print(f"  Delivered: {'YES' if delivered else 'no'}")
    print(SEP)
    print()


def build_figure(events: list[dict]):
    """Return a Plotly horizontal Gantt figure for the Analytics UI."""
    import plotly.graph_objects as go

    if not events:
        return go.Figure()

    labels, starts, durations, colours, texts = [], [], [], [], []
    prev_ms = 0
    for e in events:
        key   = e["event"]
        delta = e["ms"] - prev_ms
        label = STEP_MAP.get(key, key).strip("[] ").strip()
        labels.append(label)
        starts.append(prev_ms)
        durations.append(max(delta, 1))
        colours.append("#ef4444" if delta > 1500 else "#2563eb" if delta > 300 else "#22c55e")
        texts.append(f"{delta}ms")
        prev_ms = e["ms"]

    total_ms = events[-1]["ms"]
    intent   = next((e["raw"].get("intent","") for e in events if "intent" in e["raw"]), "")

    fig = go.Figure(go.Bar(
        x=durations, y=labels, base=starts,
        orientation="h",
        marker_color=colours,
        text=texts, textposition="inside",
        insidetextanchor="middle",
    ))
    fig.update_layout(
        title=f"ORCAST Pipeline  |  {total_ms}ms total  |  intent: {intent}",
        xaxis_title="Time elapsed (ms)",
        paper_bgcolor="#0f1117", plot_bgcolor="#161b27",
        font=dict(color="#e8eaf0", size=12),
        height=max(300, len(events) * 48),
        margin=dict(l=10, r=20, t=50, b=30),
        showlegend=False,
    )
    fig.update_xaxes(gridcolor="#1e2538", zeroline=False)
    fig.update_yaxes(gridcolor="#1e2538")
    return fig


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()
    print_timeline(parse_events(lines))
