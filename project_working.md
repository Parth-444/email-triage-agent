# MumzHelper — Email Triage Agent

## What it does

MumzHelper is a bilingual (English/Arabic) customer service agent for Mumzworld, a Middle East baby products e-commerce platform. It takes a raw inbound customer email, classifies the intent, fetches relevant grounding data, and produces a structured response including a suggested reply in both languages — all without a human having to read the email first.

---

## The pipeline

Every email goes through a **LangGraph state machine** with five nodes:

```
email → classify_intent → load_skill → execute_tools → generate_reply
                ↓
          out_of_scope_handler (short-circuits if spam/unclear)
```

**1. `classify_intent`**
Sends the email to Gemini (via `langchain-google-genai`) with a system prompt that describes the five valid intents. Uses `with_structured_output(ClassificationResult)` so the model is forced to return typed fields — `intent`, `urgency`, `reasoning`, `confidence` — no freeform text to parse. If the LLM call fails for any reason, it falls back to a keyword matcher so the graph never hard-crashes.

**2. `load_skill_node`**
Reads a markdown file from `skills/<intent>/SKILL.md` — a short, intent-specific instruction set (e.g. the return request skill tells the model what questions to ask, what policy to cite, when to escalate). The system prompt already contains a lightweight `catalog.md` so the LLM knows what skills exist — the full skill file is only loaded for the detected intent. This is progressive disclosure: you avoid dumping all skill docs into every prompt.

**3. `execute_tools`**
Fetches grounding data based on intent:
- Extracts order IDs via regex (`MW-XXXX-XXXX`) and calls `lookup_order` against `data/orders.json`
- Calls `search_policy` — keyword search over markdown policy files — for return/shipping/complaint intents
- Calls `search_products` — scored keyword search over `data/products.json` — for product questions

This is the anti-hallucination layer. The LLM never invents prices, stock levels, or order statuses — it only sees real data retrieved here.

**4. `generate_reply`**
Builds a prompt from everything collected — the email, classified intent, skill instructions, and tool context — then calls Gemini again with `with_structured_output(ReplyResult)` to produce `suggested_reply_en`, `suggested_reply_ar`, `action`, `sub_intent`, and `escalation_reason`. Falls back to a human escalation message if the LLM fails.

**5. `out_of_scope_handler`**
Short-circuits the graph for spam or unclassifiable emails — skips tool calls entirely and returns a neutral escalation-to-human response.

---

## Output schema

Every run produces a validated `TriageOutput` Pydantic model:

```
intent, sub_intent, urgency, language_detected,
reasoning, confidence,
suggested_reply_en, suggested_reply_ar,
action, escalation_reason,
referenced_order_id, referenced_products
```

The `action` field drives downstream routing — `auto_respond` means the reply can be sent automatically, `escalate_to_human` means a support agent needs to review it, `request_more_info` means the email was too ambiguous.

---

## Tech stack & why

| Choice | Reason |
|---|---|
| **LangGraph** | State machine gives explicit, inspectable control flow — easier to debug than a chain, easier to extend with new nodes |
| **LangChain Google GenAI** | Official LangChain integration for Gemini; `with_structured_output` handles JSON schema enforcement without prompt engineering |
| **Pydantic** | Schema validation at every boundary — classification result, reply result, and final output are all typed and validated |
| **Streamlit** | Fast UI for demoing and manual testing without building a full frontend |
| **uv** | Fast dependency management — single `uv sync` to reproduce the environment |

---

## Eval setup

There are 15 labelled test cases in `evals/test_cases.json`. Each has an expected `intent` and `urgency`. Running `make eval` fires the live agent against all 15 and asserts the outputs match — this gives a concrete accuracy number you can track as you iterate on prompts or swap models.
