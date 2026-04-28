# MumzHelper — Email Triage Agent

A bilingual (English/Arabic) AI agent that triages inbound customer emails for Mumzworld. It classifies intent, fetches grounding data, and produces a structured response with suggested replies in both languages.

---

## Setup

**Prerequisites:** Python 3.14+, [uv](https://docs.astral.sh/uv/)

```bash
make setup
cp .env.example .env
```

Edit `.env`:
```
GOOGLE_API_KEY=<your-gemini-api-key>
MODEL_NAME=gemini-3.1-flash-lite-preview
```

---

## Usage

**Web UI:**
```bash
make run
# open http://localhost:8501
```

**Eval suite:**
```bash
make eval
```

**Terminal smoke test:**
```bash
uv run python -c "
from src.agent import run_triage
import json
print(json.dumps(run_triage('Where is my order MW-1234-5678?').model_dump(), indent=2, ensure_ascii=False))
"
```

---

## Project structure

```
mumzworld-email-triage/
├── app.py                  # Streamlit UI
├── src/
│   ├── agent.py            # LangGraph graph + all nodes
│   ├── config.py           # Gemini LLM setup
│   ├── prompts.py          # System prompt + skill catalog loader
│   ├── schemas.py          # Pydantic models (TriageOutput, Order, Product)
│   └── tools.py            # lookup_order, search_policy, search_products
├── skills/
│   ├── catalog.md          # Lightweight skill index injected into system prompt
│   └── <intent>/SKILL.md   # Full skill instructions loaded per detected intent
├── data/
│   ├── orders.json         # Mock order dataset (20 orders)
│   ├── products.json       # Product catalog (50 products)
│   ├── emails.json         # Sample emails used in evals
│   └── policies/           # Return, shipping, and FAQ policy markdown files
├── evals/
│   ├── test_agent.py       # Pytest eval suite (15 labelled test cases)
│   ├── test_cases.json     # Expected intent + urgency labels
│   └── scoring.py          # Scoring helpers (intent, urgency, calibration)
└── Makefile
```

---

## Pipeline

```
email
  │
  ▼
classify_intent        LLM → intent, urgency, reasoning, confidence
  │
  ├─ out_of_scope ───► out_of_scope_handler → escalate_to_human
  │
  ▼
load_skill_node        reads skills/<intent>/SKILL.md
  │
  ▼
execute_tools          lookup_order / search_policy / search_products
  │
  ▼
generate_reply         LLM → suggested_reply_en, suggested_reply_ar, action
  │
  ▼
TriageOutput           validated Pydantic model
```

---

## Output schema

```python
class TriageOutput(BaseModel):
    intent: str
    sub_intent: Optional[str]
    urgency: Literal["low", "medium", "high", "critical"]
    language_detected: Literal["en", "ar", "mixed"]
    reasoning: str
    confidence: float
    suggested_reply_en: str
    suggested_reply_ar: str
    action: Literal["auto_respond", "escalate_to_human", "request_more_info"]
    escalation_reason: Optional[str]
    referenced_order_id: Optional[str]
    referenced_products: Optional[list[str]]
```

---

## Skills pattern

The system prompt loads a lightweight `skills/catalog.md` so the LLM knows what skills exist. After classification, only the matching `skills/<intent>/SKILL.md` is loaded in full. This keeps every prompt small — intent-specific instructions are fetched on demand, not dumped in upfront.

---

## Evals

15 labelled test cases in `evals/test_cases.json`, each with an expected `intent` and `urgency`. `make eval` runs all 15 against the live agent and reports pass/fail per case.

---

## Tech stack

| | |
|---|---|
| **LangGraph** | Explicit state machine — inspectable, easy to extend with new nodes |
| **LangChain + Gemini** | `with_structured_output` enforces typed responses without prompt hacking |
| **Pydantic** | Schema validation at classification, reply generation, and final output |
| **Streamlit** | Lightweight UI for demos and manual testing |
| **uv** | Fast dependency management — `uv sync` reproduces the environment |

---

## Makefile

| Command | Description |
|---|---|
| `make setup` | Install dependencies |
| `make run` | Launch Streamlit app |
| `make eval` | Run eval suite |
| `make clean` | Remove caches and `.venv` |
