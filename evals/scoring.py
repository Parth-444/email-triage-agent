from src.schemas import TriageOutput


URGENCY_LEVELS = ["low", "medium", "high", "critical"]


def score_intent(predicted: str, expected: str) -> int:
    return int(predicted == expected)


def score_urgency(predicted: str, expected: str) -> float:
    predicted_idx = URGENCY_LEVELS.index(predicted)
    expected_idx = URGENCY_LEVELS.index(expected)
    diff = abs(predicted_idx - expected_idx)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.5
    return 0.0


def score_schema_valid(output) -> int:
    try:
        TriageOutput.model_validate(output)
        return 1
    except Exception:
        return 0


def score_confidence_calibration(confidence: float, is_correct: bool) -> float:
    if is_correct:
        return round(confidence, 3)
    return round(max(0.0, 1.0 - confidence), 3)
