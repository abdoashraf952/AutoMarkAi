"""
Unit tests for the pure routing and helper functions in app/graph/nodes.py

These functions have no I/O, no LLM calls, and no database access:
  - route_after_memory()
  - route_by_intent()
  - route_after_scoring()
  - _build_context_text()
  - _flatten_crm_data()
"""
import pytest

from src.crm.graph.nodes import (
    _build_context_text,
    _flatten_crm_data,
    route_after_memory,
    route_after_scoring,
    route_by_intent,
    VALID_INTENTS,
    ALREADY_ESCALATED_MESSAGE,
)


# ─────────────────────────────────────────────────────────────────────────────
# route_after_memory
# ─────────────────────────────────────────────────────────────────────────────

class TestRouteAfterMemory:
    def _state(self, status="active"):
        return {
            "user_id": "u1",
            "source": "messenger",
            "input_type": "text",
            "user_message": "hi",
            "metadata": {},
            "status": status,
        }

    def test_active_goes_to_intent_classify(self):
        assert route_after_memory(self._state("active")) == "intent_classify"

    def test_escalated_goes_to_already_escalated(self):
        assert route_after_memory(self._state("escalated")) == "already_escalated"

    def test_missing_status_goes_to_intent_classify(self):
        state = self._state()
        del state["status"]
        assert route_after_memory(state) == "intent_classify"

    def test_unknown_status_goes_to_intent_classify(self):
        assert route_after_memory(self._state("unknown_status")) == "intent_classify"


# ─────────────────────────────────────────────────────────────────────────────
# route_by_intent
# ─────────────────────────────────────────────────────────────────────────────

class TestRouteByIntent:
    def _state(self, intent):
        return {
            "user_id": "u1",
            "source": "messenger",
            "input_type": "text",
            "user_message": "hi",
            "metadata": {},
            "intent": intent,
        }

    def test_crm_request(self):
        assert route_by_intent(self._state("crm_request")) == "hubspot_node"

    def test_knowledge_question(self):
        assert route_by_intent(self._state("knowledge_question")) == "rag_node"

    def test_lead_qualification(self):
        assert route_by_intent(self._state("lead_qualification")) == "lead_scoring_node"

    def test_escalation(self):
        assert route_by_intent(self._state("escalation")) == "handoff_node"

    def test_general_conversation(self):
        assert route_by_intent(self._state("general_conversation")) == "generate_response"

    def test_unknown_intent_defaults_to_generate_response(self):
        assert route_by_intent(self._state("some_nonsense")) == "generate_response"

    def test_all_valid_intents_covered(self):
        expected_routes = {
            "crm_request": "hubspot_node",
            "knowledge_question": "rag_node",
            "lead_qualification": "lead_scoring_node",
            "escalation": "handoff_node",
            "general_conversation": "generate_response",
        }
        for intent, expected_node in expected_routes.items():
            assert route_by_intent(self._state(intent)) == expected_node

    def test_valid_intents_constant(self):
        assert VALID_INTENTS == {
            "crm_request",
            "knowledge_question",
            "lead_qualification",
            "escalation",
            "general_conversation",
        }


# ─────────────────────────────────────────────────────────────────────────────
# route_after_scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestRouteAfterScoring:
    def _state(self, temperature=None, score=None):
        lead = {}
        if temperature:
            lead["lead_temperature"] = temperature
        if score is not None:
            lead["lead_score"] = score
        return {
            "user_id": "u1",
            "source": "messenger",
            "input_type": "text",
            "user_message": "hi",
            "metadata": {},
            "lead_profile": lead,
        }

    def test_qualified_routes_to_handoff(self):
        assert route_after_scoring(self._state("qualified", 85)) == "handoff_node"

    def test_hot_routes_to_generate_response(self):
        assert route_after_scoring(self._state("hot", 70)) == "generate_response"

    def test_warm_routes_to_generate_response(self):
        assert route_after_scoring(self._state("warm", 45)) == "generate_response"

    def test_cold_routes_to_generate_response(self):
        assert route_after_scoring(self._state("cold", 10)) == "generate_response"

    def test_no_lead_profile_routes_to_generate_response(self):
        state = {
            "user_id": "u1",
            "source": "messenger",
            "input_type": "text",
            "user_message": "hi",
            "metadata": {},
        }
        assert route_after_scoring(state) == "generate_response"

    def test_empty_lead_profile_routes_to_generate_response(self):
        state = {
            "user_id": "u1",
            "source": "messenger",
            "input_type": "text",
            "user_message": "hi",
            "metadata": {},
            "lead_profile": {},
        }
        assert route_after_scoring(state) == "generate_response"


# ─────────────────────────────────────────────────────────────────────────────
# _build_context_text
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildContextText:
    def _base_state(self, messages=None, user_message="Hello"):
        return {
            "user_id": "u1",
            "source": "messenger",
            "input_type": "text",
            "user_message": user_message,
            "metadata": {},
            "recent_messages": messages or [],
        }

    def test_user_message_always_last(self):
        state = self._base_state(user_message="What is pricing?")
        ctx = _build_context_text(state, [])
        assert ctx.endswith("user: What is pricing?")

    def test_recent_messages_included(self):
        state = self._base_state(
            messages=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
            user_message="Next question",
        )
        ctx = _build_context_text(state, [])
        assert "user: Hi" in ctx
        assert "assistant: Hello" in ctx
        assert "user: Next question" in ctx

    def test_tool_results_included(self):
        state = self._base_state(user_message="Q")
        tool_results = [{"tool": "score_lead", "result": {"score": 72}}]
        ctx = _build_context_text(state, tool_results)
        assert "score_lead" in ctx
        assert "72" in ctx

    def test_empty_state_returns_user_message(self):
        state = self._base_state(user_message="Simple question")
        ctx = _build_context_text(state, [])
        assert "Simple question" in ctx

    def test_multiple_tool_results(self):
        state = self._base_state(user_message="Q")
        tool_results = [
            {"tool": "search_knowledge_base", "result": {"found": True, "answer": "Answer here"}},
            {"tool": "score_lead", "result": {"score": 45}},
        ]
        ctx = _build_context_text(state, tool_results)
        assert "search_knowledge_base" in ctx
        assert "score_lead" in ctx


# ─────────────────────────────────────────────────────────────────────────────
# _flatten_crm_data
# ─────────────────────────────────────────────────────────────────────────────

class TestFlattenCRMData:
    def test_none_returns_empty(self):
        assert _flatten_crm_data(None) == {}

    def test_empty_dict_returns_empty(self):
        assert _flatten_crm_data({}) == {}

    def test_dict_with_values(self):
        data = {"email": "a@b.com", "phone": "123", "company": None}
        result = _flatten_crm_data(data)
        assert result == {"email": "a@b.com", "phone": "123"}
        assert "company" not in result

    def test_none_values_stripped(self):
        data = {"firstname": "John", "lastname": None, "email": None}
        result = _flatten_crm_data(data)
        assert result == {"firstname": "John"}

    def test_pydantic_model_flattened(self):
        from pydantic import BaseModel
        from typing import Optional

        class MockModel(BaseModel):
            email: Optional[str] = None
            firstname: Optional[str] = None
            phone: Optional[str] = None

        model = MockModel(email="x@y.com", firstname="Bob", phone=None)
        result = _flatten_crm_data(model)
        assert result == {"email": "x@y.com", "firstname": "Bob"}
        assert "phone" not in result

    def test_all_none_returns_empty(self):
        data = {"a": None, "b": None}
        assert _flatten_crm_data(data) == {}


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

class TestConstants:
    def test_already_escalated_message_is_string(self):
        assert isinstance(ALREADY_ESCALATED_MESSAGE, str)
        assert len(ALREADY_ESCALATED_MESSAGE) > 0

    def test_already_escalated_message_content(self):
        msg = ALREADY_ESCALATED_MESSAGE.lower()
        assert "escalated" in msg
