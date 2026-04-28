import json
import re
from typing import Any, Literal, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from src.config import get_llm
from src.prompts import SYSTEM_PROMPT
from src.schemas import TriageOutput
from src.tools import load_skill, lookup_order, search_policy, search_products

_llm = get_llm()


class ClassificationResult(BaseModel):
    intent: Literal[
        "return_request",
        "order_inquiry",
        "product_question",
        "complaint_escalation",
        "general_inquiry",
        "out_of_scope",
    ]
    urgency: Literal["low", "medium", "high", "critical"]
    reasoning: str
    confidence: float


class ReplyResult(BaseModel):
    sub_intent: Optional[str] = None
    action: Literal["auto_respond", "escalate_to_human", "request_more_info"]
    escalation_reason: Optional[str] = None
    suggested_reply_en: str
    suggested_reply_ar: str


class AgentState(TypedDict, total=False):
    messages: list[dict[str, str]]
    email_input: str
    intent: str
    urgency: str
    language_detected: str
    reasoning: str
    confidence: float
    skill_loaded: str
    tool_context: dict[str, Any]
    triage_output: dict[str, Any]


INTENT_TO_SKILL = {
    "return_request": "return_request",
    "order_inquiry": "order_inquiry",
    "product_question": "product_question",
    "complaint_escalation": "complaint_escalation",
    "general_inquiry": "general_inquiry",
}


def _detect_language(text: str) -> Literal["en", "ar", "mixed"]:
    has_arabic = bool(re.search(r"[\u0600-\u06FF]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_arabic and has_latin:
        return "mixed"
    if has_arabic:
        return "ar"
    return "en"


def _extract_order_id(text: str) -> str | None:
    match = re.search(r"MW-\d{4}-\d{4}", text, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _classify_with_fallback(text: str) -> tuple[str, str, str, float]:
    lowered = text.lower()

    if any(token in lowered for token in ["lottery", "casino", "seo service", "crypto signal"]):
        return "out_of_scope", "low", "Likely spam or unrelated commercial outreach.", 0.93
    if any(token in lowered for token in ["refund", "return", "exchange", "broken", "defective", "damaged"]):
        return "return_request", "medium", "Customer is asking to return, refund, or replace an item.", 0.79
    if any(token in lowered for token in ["where is my order", "order status", "tracking", "shipped", "delivery update"]):
        return "order_inquiry", "medium", "Customer is asking for an order or delivery status update.", 0.8
    if any(token in lowered for token in ["recommend", "availability", "in stock", "size guide", "suitable", "which stroller", "which car seat"]):
        return "product_question", "low", "Customer is asking about product details or recommendations.", 0.76
    if any(token in lowered for token in ["terrible", "complaint", "lawyer", "legal", "angry", "frustrated", "ridiculous", "worst"]):
        urgency = "critical" if any(token in lowered for token in ["lawyer", "legal", "social media", "worst", "sue"]) else "high"
        return "complaint_escalation", urgency, "Customer message is strongly negative or escalatory.", 0.84
    if any(token in lowered for token in ["shipping", "payment", "store", "gift wrap", "gift wrapping", "working hours", "location"]):
        return "general_inquiry", "low", "Customer is asking a policy or operations question.", 0.74
    return "out_of_scope", "low", "Fallback classification because intent is unclear without an LLM.", 0.42


def classify_intent(state: AgentState) -> AgentState:
    email_text = state["email_input"]
    language = _detect_language(email_text)
    try:
        structured_llm = _llm.with_structured_output(ClassificationResult)
        result: ClassificationResult = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=email_text),
        ])
        intent, urgency, reasoning, confidence = (
            result.intent, result.urgency, result.reasoning, result.confidence
        )
    except Exception:
        intent, urgency, reasoning, confidence = _classify_with_fallback(email_text)
    return {
        **state,
        "intent": intent,
        "urgency": urgency,
        "language_detected": language,
        "reasoning": reasoning,
        "confidence": confidence,
    }


def load_skill_node(state: AgentState) -> AgentState:
    intent = state["intent"]
    if intent == "out_of_scope":
        return {**state, "skill_loaded": ""}
    skill_name = INTENT_TO_SKILL[intent]
    skill_content = load_skill.invoke(skill_name)
    return {**state, "skill_loaded": skill_content}


def execute_tools(state: AgentState) -> AgentState:
    email_text = state["email_input"]
    intent = state["intent"]
    order_id = _extract_order_id(email_text)
    tool_context: dict[str, Any] = {"order_id": order_id, "order": None, "policy": "", "products": []}

    if order_id:
        tool_context["order"] = lookup_order.invoke(order_id)

    if intent == "return_request":
        tool_context["policy"] = search_policy.invoke("return refund exchange damaged")
    elif intent == "order_inquiry":
        tool_context["policy"] = search_policy.invoke("shipping delivery tracking")
    elif intent == "product_question":
        tool_context["products"] = search_products.invoke(email_text)
    elif intent == "general_inquiry":
        tool_context["policy"] = search_policy.invoke(email_text)

    return {**state, "tool_context": tool_context}


def _human_intervention_fallback(state: AgentState) -> dict[str, Any]:
    tool_context = state.get("tool_context", {})
    return {
        "intent": state.get("intent", "out_of_scope"),
        "sub_intent": None,
        "urgency": state.get("urgency", "low"),
        "language_detected": state.get("language_detected", "en"),
        "reasoning": state.get("reasoning", ""),
        "confidence": state.get("confidence", 0.0),
        "suggested_reply_en": "Thank you for contacting Mumzworld. A team member will review your message and get back to you shortly.",
        "suggested_reply_ar": "شكرًا لتواصلكم مع ممزورلد. سيقوم أحد أعضاء فريقنا بمراجعة رسالتكم والرد عليكم قريباً.",
        "action": "escalate_to_human",
        "escalation_reason": "Automated processing failed; routed to human review.",
        "referenced_order_id": tool_context.get("order_id"),
        "referenced_products": None,
    }


def _build_reply_prompt(state: AgentState) -> str:
    tool_context = state.get("tool_context", {})
    parts = [
        f"Customer email:\n{state['email_input']}",
        f"Intent: {state['intent']} | Urgency: {state['urgency']} | Language: {state['language_detected']}",
    ]
    if state.get("skill_loaded"):
        parts.append(f"Skill instructions:\n{state['skill_loaded']}")
    if tool_context.get("order"):
        parts.append(f"Order data:\n{json.dumps(tool_context['order'], indent=2)}")
    if tool_context.get("policy"):
        parts.append(f"Relevant policy:\n{tool_context['policy']}")
    if tool_context.get("products"):
        parts.append(f"Matching products:\n{json.dumps(tool_context['products'], indent=2)}")
    return "\n\n---\n\n".join(parts)


def generate_reply(state: AgentState) -> AgentState:
    try:
        structured_llm = _llm.with_structured_output(ReplyResult)
        result: ReplyResult = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_reply_prompt(state)),
        ])
        tool_context = state.get("tool_context", {})
        products = tool_context.get("products", [])
        triage_output: dict[str, Any] = {
            "intent": state["intent"],
            "sub_intent": result.sub_intent,
            "urgency": state["urgency"],
            "language_detected": state["language_detected"],
            "reasoning": state["reasoning"],
            "confidence": state["confidence"],
            "suggested_reply_en": result.suggested_reply_en,
            "suggested_reply_ar": result.suggested_reply_ar,
            "action": result.action,
            "escalation_reason": result.escalation_reason,
            "referenced_order_id": tool_context.get("order_id"),
            "referenced_products": [p["id"] for p in products] or None,
        }
    except Exception:
        triage_output = _human_intervention_fallback(state)
    return {**state, "triage_output": triage_output}


def out_of_scope_handler(state: AgentState) -> AgentState:
    triage_output = _human_intervention_fallback({**state, "intent": "out_of_scope"})
    return {**state, "triage_output": triage_output}


def route_after_classification(state: AgentState) -> str:
    if state["intent"] == "out_of_scope":
        return "out_of_scope_handler"
    return "load_skill_node"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("load_skill_node", load_skill_node)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("generate_reply", generate_reply)
    graph.add_node("out_of_scope_handler", out_of_scope_handler)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_after_classification,
        {
            "load_skill_node": "load_skill_node",
            "out_of_scope_handler": "out_of_scope_handler",
        },
    )
    graph.add_edge("load_skill_node", "execute_tools")
    graph.add_edge("execute_tools", "generate_reply")
    graph.add_edge("generate_reply", END)
    graph.add_edge("out_of_scope_handler", END)
    return graph.compile()


GRAPH = build_graph()


def run_triage(email_text: str) -> TriageOutput:
    initial_state: AgentState = {
        "messages": [],
        "email_input": email_text,
    }
    result = GRAPH.invoke(initial_state)
    return TriageOutput.model_validate(result["triage_output"])
