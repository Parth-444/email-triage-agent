import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()

DATASET_NAME = "mumzworld-email-triage-benchmark"


def sync_dataset():
    client = Client()
    root_dir = Path(__file__).resolve().parent.parent
    test_cases_path = root_dir / "evals" / "test_cases.json"
    emails_path = root_dir / "data" / "emails.json"

    if not test_cases_path.exists() or not emails_path.exists():
        raise FileNotFoundError("test_cases.json or emails.json not found.")

    test_cases = json.loads(test_cases_path.read_text(encoding="utf-8"))
    emails = {e["id"]: e for e in json.loads(emails_path.read_text(encoding="utf-8"))}

    # Delete existing dataset if we want a fresh sync, or read it
    if client.has_dataset(dataset_name=DATASET_NAME):
        print(f"Dataset '{DATASET_NAME}' already exists. Reading existing dataset...")
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
    else:
        print(f"Creating new dataset: '{DATASET_NAME}'...")
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="Golden evaluation dataset for Mumzworld Customer Support Email Triage.",
        )

    # Fetch existing examples to avoid duplicates
    existing_examples = list(client.list_examples(dataset_id=dataset.id))
    existing_ids = {
        ex.metadata.get("test_case_id") for ex in existing_examples if ex.metadata
    }

    uploaded_count = 0
    for case in test_cases:
        case_id = case["id"]
        if case_id in existing_ids:
            continue

        email = emails[case["email_id"]]
        email_text = f"Subject: {email['subject']}\n\n{email['body']}"

        client.create_example(
            inputs={"email_input": email_text},
            outputs={
                "expected_intent": case["expected_intent"],
                "expected_urgency": case["expected_urgency"],
                "expected_action": case.get("expected_action"),
                "expected_sub_intent": case.get("expected_sub_intent"),
            },
            metadata={
                "test_case_id": case["id"],
                "email_id": case["email_id"],
                "description": case.get("description", ""),
                "notes": case.get("notes", ""),
            },
            dataset_id=dataset.id,
        )
        uploaded_count += 1

    print(
        f"Sync completed! {uploaded_count} new test cases added. Total dataset examples: {len(test_cases)}"
    )
    return dataset


if __name__ == "__main__":
    sync_dataset()
