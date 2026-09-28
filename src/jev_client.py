from dataclasses import dataclass
from typing import Any, Literal
from langsmith import traceable

from src.config import JEV_MODEL_NAME, TYPESAFE_API_KEY


Intent = Literal[
    "return_request",
    "order_inquiry",
    "product_question",
    "complaint_escalation",
    "general_inquiry",
    "out_of_scope",
]
Urgency = Literal["low", "medium", "high", "critical"]


class JevError(RuntimeError):
    pass


@dataclass(frozen=True)
class JevTriageDecision:
    intent: Intent
    urgency: Urgency
    reasoning: str
    confidence: float
    needs_human: bool
    needs_more_info: bool


INTENT_CRITERIA: dict[str, str] = {
    "return_request": "Customer wants a return, refund, exchange, replacement, or reports a damaged or defective item.",
    "order_inquiry": "Customer asks about order status, shipping, tracking, delivery timing, or a missing delivered order.",
    "product_question": "Customer asks about product details, availability, sizing, recommendations, suitability, or stock.",
    "complaint_escalation": "Customer is angry, threatening legal or public action, reports a repeated unresolved issue, or needs escalation.",
    "general_inquiry": "Customer asks about policies, payments, store operations, gift wrap, account help, or other support questions.",
    "out_of_scope": "Spam, unrelated commercial outreach, unclear content, or anything not about Mumzworld customer support.",
}

URGENCY_LEVELS = [
    "Low: calm message, informational question, no time pressure.",
    "Medium: normal support request, delivery concern, return request, or issue needing follow-up.",
    "High: frustrated customer, delayed or failed service, missing delivery, repeated issue, or strong time pressure.",
    "Critical: legal threat, public complaint threat, safety concern, severe anger, or immediate human escalation needed.",
]

@traceable(name="Evaluate email classification")
def evaluate_email_triage(email_text: str) -> JevTriageDecision:
    if not TYPESAFE_API_KEY:
        raise JevError("JEV_API or TYPESAFE_API_KEY is not configured.")

    classifier = _build_classifier()
    questions = _build_questions()
    response = classifier.invoke({
        "state": email_text,
        "questions": questions,
    })
    answers = _answers_from_response(response)

    intent_answer = _answer(answers, "intent")
    urgency_answer = _answer(answers, "urgency")
    needs_human_answer = _answer(answers, "needs_human")
    needs_more_info_answer = _answer(answers, "needs_more_info")

    intent = _choice_value(intent_answer, "out_of_scope")
    if intent not in INTENT_CRITERIA:
        intent = "out_of_scope"

    urgency = _urgency_from_score(urgency_answer)
    intent_confidence = _confidence(intent_answer)
    urgency_confidence = _confidence(urgency_answer)
    confidence = min(intent_confidence, urgency_confidence)

    needs_human = _noul_value(needs_human_answer) >= 0.65
    needs_more_info = _noul_value(needs_more_info_answer) >= 0.65
    if needs_human and intent != "out_of_scope":
        intent = "complaint_escalation"
        urgency = "critical" if urgency in {"high", "critical"} else "high"

    reasoning = (
        f"JEV selected intent '{intent}' with confidence {intent_confidence:.2f}; "
        f"urgency '{urgency}' with confidence {urgency_confidence:.2f}; "
        f"human escalation probability {_noul_value(needs_human_answer):.2f}; "
        f"missing-info probability {_noul_value(needs_more_info_answer):.2f}."
    )
    return JevTriageDecision(
        intent=intent,  # type: ignore[arg-type]
        urgency=urgency,
        reasoning=reasoning,
        confidence=confidence,
        needs_human=needs_human,
        needs_more_info=needs_more_info,
    )


def _build_questions() -> dict[str, Any]:
    try:
        from langchain_typesafe import Choice, Noul, Score
    except ImportError as exc:
        raise JevError("langchain-typesafe is not installed.") from exc

    return {
        "intent": Choice(
            instructions="Classify this inbound Mumzworld customer email into exactly one support intent.",
            criteria=INTENT_CRITERIA,
        ),
        "urgency": Score(
            instructions="Assess the customer support urgency using this ordered rubric.",
            criteria=URGENCY_LEVELS,
        ),
        "needs_human": Noul(
            instructions="Should this email be escalated to a human support agent before sending an automated reply?",
            criteria={
                "true": "Escalation is needed because of anger, legal risk, safety risk, repeated failure, or low automation confidence.",
                "false": "The request can likely be handled by the automated support flow.",
            },
        ),
        "needs_more_info": Noul(
            instructions="Does this email lack important details needed to answer correctly, such as an order id or product details?",
            criteria={
                "true": "Important details are missing and the customer should be asked for more information.",
                "false": "There is enough information to proceed with the support flow.",
            },
        ),
    }


def _build_classifier() -> Any:
    try:
        from langchain_typesafe import TypeSafeClassifier
    except ImportError as exc:
        raise JevError("langchain-typesafe is not installed.") from exc

    return TypeSafeClassifier(
        model=JEV_MODEL_NAME,
        api_key=TYPESAFE_API_KEY,
    )


def _answers_from_response(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        answers = response.get("answers") or response.get("results") or response.get("data")
    else:
        answers = getattr(response, "answers", None)
    if isinstance(answers, dict):
        return answers
    raise JevError(f"JEV response did not include an answers object: {response}")


def _answer(answers: dict[str, Any], key: str) -> Any:
    value = answers.get(key)
    if isinstance(value, dict) and isinstance(value.get("answer"), dict):
        value = value["answer"]
    if value is None:
        raise JevError(f"JEV response for '{key}' was missing or invalid: {value}")
    return value


def _field(answer: Any, key: str) -> Any:
    if isinstance(answer, dict):
        return answer.get(key)
    return getattr(answer, key, None)


def _choice_value(answer: Any, default: str) -> str:
    value = _field(answer, "choice") or _field(answer, "value") or _field(answer, "selected")
    return value if isinstance(value, str) else default


def _confidence(answer: Any) -> float:
    value = _field(answer, "confidence")
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    probabilities = _field(answer, "probabilities")
    if isinstance(probabilities, dict):
        numeric_values = [float(item) for item in probabilities.values() if isinstance(item, int | float)]
        if numeric_values:
            return max(0.0, min(1.0, max(numeric_values)))
    return 0.0


def _noul_value(answer: Any) -> float:
    value = _field(answer, "noul")
    if value is None:
        value = _field(answer, "probability")
    if value is None:
        value = _field(answer, "value")
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 0.0


def _urgency_from_score(answer: Any) -> Urgency:
    value = _field(answer, "score")
    if isinstance(value, int | float):
        score = float(value)
    else:
        probabilities = _field(answer, "probabilities")
        if isinstance(probabilities, dict) and probabilities:
            score = max(probabilities.items(), key=lambda item: float(item[1]))[0]
            score = float(score)
        else:
            score = 0.0

    if score < 0.75:
        return "low"
    if score < 1.75:
        return "medium"
    if score < 2.65:
        return "high"
    return "critical"
