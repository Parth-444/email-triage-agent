import json
from pathlib import Path

import pytest

from src.agent import run_triage
from src.schemas import TriageOutput


ROOT_DIR = Path(__file__).resolve().parent.parent
TEST_CASES_PATH = ROOT_DIR / "evals" / "test_cases.json"
EMAILS_PATH = ROOT_DIR / "data" / "emails.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


TEST_CASES = load_json(TEST_CASES_PATH)
EMAILS = {email["id"]: email for email in load_json(EMAILS_PATH)}


@pytest.mark.parametrize("test_case", TEST_CASES, ids=[case["id"] for case in TEST_CASES])
def test_run_triage_against_expected_labels(test_case):
    email = EMAILS[test_case["email_id"]]
    email_text = f"Subject: {email['subject']}\n\n{email['body']}"

    result = run_triage(email_text)
    validated = TriageOutput.model_validate(result.model_dump())

    assert validated.intent == test_case["expected_intent"]
    assert validated.urgency == test_case["expected_urgency"]
    assert isinstance(validated, TriageOutput)
