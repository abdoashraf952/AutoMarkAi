"""
Unit tests for app/graph/state.py

Tests the AgentResponse Pydantic model and GraphState TypedDict structure.
No I/O or LLM calls required.
"""
from datetime import datetime, timezone

import pytest

from src.crm.graph.state import AgentResponse, GraphState


class TestAgentResponse:
    def test_minimal_construction(self):
        r = AgentResponse(user_id="u1", source="messenger", message="Hello")
        assert r.user_id == "u1"
        assert r.source == "messenger"
        assert r.message == "Hello"

    def test_default_tools_called_empty(self):
        r = AgentResponse(user_id="u1", source="vapi", message="Hi")
        assert r.tools_called == []

    def test_default_lead_updated_false(self):
        r = AgentResponse(user_id="u1", source="messenger", message="x")
        assert r.lead_updated is False

    def test_default_escalated_false(self):
        r = AgentResponse(user_id="u1", source="messenger", message="x")
        assert r.escalated is False

    def test_timestamp_is_utc(self):
        r = AgentResponse(user_id="u1", source="messenger", message="x")
        assert r.timestamp.tzinfo is not None

    def test_tools_called_list(self):
        r = AgentResponse(
            user_id="u2",
            source="facebook_comments",
            message="ok",
            tools_called=["search_knowledge_base", "score_lead"],
        )
        assert len(r.tools_called) == 2
        assert "score_lead" in r.tools_called

    def test_escalated_true(self):
        r = AgentResponse(user_id="u3", source="vapi", message="escalated", escalated=True)
        assert r.escalated is True

    def test_lead_updated_true(self):
        r = AgentResponse(user_id="u3", source="messenger", message="updated", lead_updated=True)
        assert r.lead_updated is True

    def test_model_fields(self):
        fields = AgentResponse.model_fields
        assert "user_id" in fields
        assert "source" in fields
        assert "message" in fields
        assert "tools_called" in fields
        assert "lead_updated" in fields
        assert "escalated" in fields
        assert "timestamp" in fields

    def test_serialization(self):
        r = AgentResponse(user_id="u4", source="messenger", message="test", tools_called=["crm_operation"])
        d = r.model_dump()
        assert d["user_id"] == "u4"
        assert d["tools_called"] == ["crm_operation"]
        assert "timestamp" in d


class TestGraphStateStructure:
    """Verify GraphState TypedDict has all expected keys documented in README."""

    def test_inbound_message_keys(self):
        state: GraphState = {
            "user_id": "abc",
            "source": "messenger",
            "input_type": "text",
            "user_message": "Hello",
            "metadata": {},
        }
        assert state["user_id"] == "abc"
        assert state["source"] == "messenger"
        assert state["input_type"] == "text"
        assert state["user_message"] == "Hello"

    def test_memory_keys(self):
        state: GraphState = {
            "user_id": "u",
            "source": "vapi",
            "input_type": "text",
            "user_message": "Hi",
            "metadata": {},
            "status": "active",
            "summary": "Prior summary text",
            "recent_messages": [{"role": "user", "content": "prev"}],
            "lead_profile": {"name": "John"},
        }
        assert state["status"] == "active"
        assert state["summary"] == "Prior summary text"
        assert len(state["recent_messages"]) == 1

    def test_routing_keys(self):
        state: GraphState = {
            "user_id": "u",
            "source": "messenger",
            "input_type": "text",
            "user_message": "x",
            "metadata": {},
            "intent": "knowledge_question",
            "intent_data": {"rag_query": "pricing"},
        }
        assert state["intent"] == "knowledge_question"
        assert state["intent_data"]["rag_query"] == "pricing"

    def test_output_keys(self):
        state: GraphState = {
            "user_id": "u",
            "source": "messenger",
            "input_type": "text",
            "user_message": "x",
            "metadata": {},
            "response": "Here is your answer",
            "escalated": False,
            "lead_updated": True,
            "tool_results": [{"tool": "score_lead", "result": {"score": 72}}],
            "tools_called": ["score_lead"],
        }
        assert state["response"] == "Here is your answer"
        assert state["escalated"] is False
        assert state["lead_updated"] is True
        assert state["tools_called"] == ["score_lead"]
