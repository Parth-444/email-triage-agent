# Autonomous Bilingual Email Triage & Inbox Automation Agent

A production-grade, bilingual (English/Arabic) AI email triage and automation agent built with **LangGraph**, **Gemini**, and **LangSmith**. It classifies customer intents, retrieves grounding knowledge on demand, generates validated bilingual replies, synchronizes hierarchical labels in **Gmail**, and routes actions between automated responses and human-in-the-loop drafts.

---

## Key Features

- **Multi-Criteria Intent & Urgency Routing:** Fast intent categorization and urgency scoring with high-confidence calibration.
- **Progressive Skill Disclosure (`SKILL.md`):** Dynamic context loading that injects only the required business/policy skills into the prompt on demand, keeping token overhead minimal.
- **Production Gmail Integration:**
  - **Hierarchical Auto-Labeling:** Automatically resolves, creates, and attaches structured label folders in Gmail (e.g., `Triage/Intent/<intent>`, `Triage/Urgency/<urgency>`, `Triage/Action/<action>`).
  - **Human-in-the-Loop Safety:** Generates pre-filled **Gmail Drafts** in the active thread for low-confidence or high-risk emails, and sends direct replies only for high-confidence FAQs.
- **Enterprise LLMOps & Observability (LangSmith):**
  - Continuous benchmark suite with versioned golden datasets.
  - Multi-dimensional custom evaluators (`intent_accuracy`, `urgency_score`, `action_match`, `confidence_calibration`, `schema_valid`).
  - Node-level execution tracing, latency profiling, and cost tracking across every graph state transition.
- **FastAPI Webhook & Local Ingestion:** Supports real-time Google Cloud Pub/Sub push webhooks as well as manual on-demand `/triage/unread` batch processing.

---

## Architecture Pipeline

```
Incoming Customer Email
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ LangGraph State Machine                                     │
│                                                             │
│  [classify_intent]  ──► Multi-criteria intent & urgency    │
│         │                                                   │
│  [load_skill_node]  ──► On-demand domain skill markdown     │
│         │                                                   │
│  [execute_tools]    ──► Dynamic order & policy retrieval    │
│         │                                                   │
│  [generate_reply]   ──► Gemini bilingual structured output  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
               TriageOutput (Pydantic)
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌──────────────────┐          ┌──────────────────────────────────┐
│ Gmail Labeling   │          │ Dispatch Action                  │
│ • Triage/Intent  │          │ • Confidence >= 0.90 ──► Reply   │
│ • Triage/Urgency │          │ • Low/Escalate       ──► Draft   │
│ • Triage/Action  │          └──────────────────────────────────┘
└──────────────────┘
```

---

## Setup & Configuration

### 1. Prerequisites
- Python 3.11+ / 3.14+
- Google Cloud Project with **Gmail API** enabled and OAuth 2.0 Desktop Credentials (`credentials.json`)
- Gemini API Key & LangSmith Account

### 2. Installation
```bash
# Clone the repository
git clone <your-repo-url>
cd email-triage-agent

# Set up virtual environment and dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables (`.env`)
Create a `.env` file in the project root:

```env
# Google Gemini LLM
GOOGLE_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-3.6-flash

# TypeSafe JEV Classifier
JEV_API=your_typesafe_api_key
JEV_MODEL_NAME=jev-latest

# LangSmith LLMOps & Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://apac.api.smith.langchain.com" # Or https://api.smith.langchain.com
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=email-triage-agent

# Action Dispatch Settings
ENABLE_AUTO_SEND=false  # Set to true for live automated sending, false for drafts only
```

### 4. Google OAuth Setup
Place your downloaded `credentials.json` in the project root directory. On first run, a secure browser window will open to authenticate your Gmail account and generate `token.json`.

---

## Usage

### 1. Run the FastAPI Webhook & Ingestion Server
```bash
python app_server.py
```
- **Interactive API Docs:** `http://localhost:8000/docs`
- **Health Check:** `GET http://localhost:8000/health`
- **Triage Unread Inbox Emails (Manual Trigger):**
  ```bash
  curl -X POST http://localhost:8000/triage/unread
  ```
- **Real-Time Webhook Endpoint:** `POST http://localhost:8000/webhook/gmail-pubsub`

---

### 2. Run the Streamlit Demo UI
```bash
streamlit run app.py
```
Open `http://localhost:8501` to test the triage agent interactively against sample emails with full schema visualization.

---

### 3. Run Benchmark Evaluations & LangSmith Experiments

Sync the golden evaluation dataset:
```bash
python evals/sync_dataset.py
```

Run the benchmark evaluation:
```bash
python evals/run_evals.py
```
View aggregate score matrices, regression deltas, latency, and node-level traces in your LangSmith dashboard.

Run standard unit tests via pytest:
```bash
pytest evals/test_agent.py
```

---

## Project Structure

```
├── app_server.py               # FastAPI server: OAuth, webhooks & inbox batch trigger
├── app.py                      # Streamlit interactive testing UI
├── credentials.json            # Google OAuth 2.0 client secrets (User provided)
├── token.json                  # Cached Google OAuth access token (Auto-generated)
├── src/
│   ├── agent.py                # LangGraph StateGraph orchestration & nodes
│   ├── config.py               # LLM configuration and environment loading
│   ├── gmail_service.py        # Gmail API client: OAuth, labels, drafts, and replies
│   ├── jev_client.py           # Classifier client for multi-criteria routing
│   ├── prompts.py              # System prompts & dynamic skill catalog loader
│   ├── schemas.py              # Pydantic schemas (TriageOutput, Order, Product)
│   └── tools.py                # Knowledge base tools (order, product, policy lookups)
├── skills/
│   ├── catalog.md              # Global skill index for initial routing
│   └── <intent>/SKILL.md       # On-demand domain skill execution instructions
├── data/
│   ├── orders.json             # Mock customer order data
│   ├── products.json           # Catalog product specifications
│   ├── emails.json             # Benchmark test emails
│   └── policies/               # Return, shipping, and FAQ policies
├── evals/
│   ├── run_evals.py            # LangSmith automated evaluation runner
│   ├── sync_dataset.py         # LangSmith managed dataset synchronization
│   ├── scoring.py              # Custom evaluation metrics & calibration scoring
│   ├── test_agent.py           # Pytest test suite
│   └── test_cases.json         # Golden dataset evaluation test cases
└── README.md
```

---

## Output Schema (`TriageOutput`)

Every incoming message is validated against a strict Pydantic model:

```python
class TriageOutput(BaseModel):
    intent: Literal[
        "return_request",
        "order_inquiry",
        "product_question",
        "complaint_escalation",
        "general_inquiry",
        "out_of_scope",
    ]
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

## Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Agent State Machine** | **LangGraph** | Cyclic state graph with modular, inspectable execution nodes |
| **LLM Inference** | **Google Gemini** | Bilingual reasoning with structured output schemas |
| **Fast Classification** | **TypeSafe JEV** | Multi-criteria intent & urgency routing with low token overhead |
| **LLMOps & Evals** | **LangSmith** | Experiment tracking, custom evaluators, and node-level tracing |
| **Mailbox Integration** | **Gmail API** | OAuth 2.0, hierarchical label management, drafts, and replies |
| **Backend & Webhooks** | **FastAPI + Uvicorn** | Async background execution and Pub/Sub webhook handling |
| **Data Validation** | **Pydantic V2** | Runtime type safety and schema validation |
| **Interactive UI** | **Streamlit** | Visual testing interface for demonstration |
