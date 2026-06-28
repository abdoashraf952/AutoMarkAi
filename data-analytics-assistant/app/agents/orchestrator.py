"""Orchestrator Agent: handles conversational follow-up queries."""
from __future__ import annotations

import traceback

from app.schemas.state import AnalyticsState
from app.schemas.chat import ChatMessage
from app.services.gemini_service import get_gemini_service
from app.prompts.chat_prompt import CHAT_SYSTEM, CHAT_PROMPT


def chat_orchestrator_agent(state: AnalyticsState) -> dict:
    """
    LangGraph node: responds to follow-up queries using full analysis context.
    Appends the assistant reply to chat_history.
    """
    try:
        if not state.follow_up_query:
            return {"current_step": "complete"}

        summary = state.dataset_summary
        profiling = state.profiling_result

        kpis_summary = "\n".join(
            f"  [{k.priority}] {k.name}: {k.business_definition} | Value: {k.current_value or 'N/A'} {k.unit or ''}"
            for k in state.kpis
        )

        insights_summary = "\n".join(
            f"  [{i.priority}] {i.title}: {i.executive_summary}\n    → {i.recommendation}"
            for i in state.insights
        )

        history_str = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in state.chat_history[-10:]
        )

        prompt = CHAT_PROMPT.format(
            business_domain=state.business_domain,
            file_name=state.file_name,
            row_count=summary.row_count if summary else 0,
            columns=", ".join(summary.columns[:20]) if summary else "",
            kpis_summary=kpis_summary or "No KPIs generated yet",
            insights_summary=insights_summary or "No insights generated yet",
            chat_history=history_str or "No prior conversation",
            user_query=state.follow_up_query,
        )

        gemini = get_gemini_service()
        response = gemini.generate(prompt, system_instruction=CHAT_SYSTEM, temperature=0.5)

        # Append to chat history
        user_msg = ChatMessage(role="user", content=state.follow_up_query)
        assistant_msg = ChatMessage(role="assistant", content=response, message_type="analysis")

        new_history = list(state.chat_history) + [user_msg, assistant_msg]

        return {
            "chat_history": new_history,
            "current_step": "complete",
            "error_message": None,
        }

    except Exception as exc:
        return {
            "error_message": f"Chat orchestrator failed: {exc}\n{traceback.format_exc()}",
            "current_step": "error",
        }
