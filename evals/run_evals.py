import sys
from pathlib import Path

# Add project root to sys.path so imports work regardless of execution location
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from langsmith.evaluation import evaluate

from evals.scoring import (
    score_confidence_calibration,
    score_intent,
    score_schema_valid,
    score_urgency,
)
from src.agent import run_triage
from src.config import MODEL_NAME

load_dotenv()

DATASET_NAME = "mumzworld-email-triage-benchmark"


def predict(inputs: dict) -> dict:
    """Wrapper function to execute the triage agent for a given input."""
    email_text = inputs["email_input"]
    result = run_triage(email_text)
    return result.model_dump()


def intent_accuracy_evaluator(run, example) -> dict:
    predicted_intent = run.outputs.get("intent")
    expected_intent = example.outputs.get("expected_intent")
    score = score_intent(predicted_intent, expected_intent)
    return {
        "key": "intent_accuracy",
        "score": score,
        "comment": f"Predicted: {predicted_intent} | Expected: {expected_intent}",
    }


def urgency_calibration_evaluator(run, example) -> dict:
    predicted_urgency = run.outputs.get("urgency")
    expected_urgency = example.outputs.get("expected_urgency")
    score = score_urgency(predicted_urgency, expected_urgency)
    return {
        "key": "urgency_score",
        "score": score,
        "comment": f"Predicted: {predicted_urgency} | Expected: {expected_urgency}",
    }


def action_match_evaluator(run, example) -> dict:
    predicted_action = run.outputs.get("action")
    expected_action = example.outputs.get("expected_action")
    if expected_action is None:
        return {"key": "action_match", "score": 1.0}
    score = int(predicted_action == expected_action)
    return {
        "key": "action_match",
        "score": score,
        "comment": f"Predicted: {predicted_action} | Expected: {expected_action}",
    }


def confidence_evaluator(run, example) -> dict:
    predicted_intent = run.outputs.get("intent")
    expected_intent = example.outputs.get("expected_intent")
    confidence = float(run.outputs.get("confidence", 0.0))
    is_correct = predicted_intent == expected_intent
    score = score_confidence_calibration(confidence, is_correct)
    return {
        "key": "confidence_calibration",
        "score": score,
    }


def schema_valid_evaluator(run, example) -> dict:
    score = score_schema_valid(run.outputs)
    return {
        "key": "schema_valid",
        "score": score,
    }


def run_benchmark(experiment_name: str | None = None):
    prefix = experiment_name or f"triage-eval-{MODEL_NAME}"
    print(f"Starting LangSmith Evaluation Experiment on dataset '{DATASET_NAME}'...")
    print(f"Experiment prefix: {prefix}")

    results = evaluate(
        predict,
        data=DATASET_NAME,
        evaluators=[
            intent_accuracy_evaluator,
            urgency_calibration_evaluator,
            action_match_evaluator,
            confidence_evaluator,
            schema_valid_evaluator,
        ],
        experiment_prefix=prefix,
        metadata={
            "model": MODEL_NAME,
            "agent_architecture": "LangGraph StateGraph",
            "environment": "development",
        },
    )

    print("\nBenchmark experiment completed!")
    return results


if __name__ == "__main__":
    run_benchmark()
