**Track A | AI Engineering Intern**


## AI Usage
Built using Claude Code as the primary coding agent for scaffolding, data generation, and implementation. Architecture design and problem scoping were done manually. The agent's LLM backend uses Gemini 3.1 flash preview for intent classification and reply generation.



## Time Log:

Architecture design & problem selection: ~90 min (longest phase — evaluated multiple approaches before settling on email triage with Skills pattern)
Data generation & project scaffolding: ~30 min (Claude Code)
Agent implementation & LangGraph wiring: ~40 min
Eval suite & debugging: ~20 min
Total: ~3 hours


## Evals

### Rubric
Each test case is scored on:
- **Intent accuracy**: Does the predicted intent match the expected intent?
- **Urgency accuracy**: Does the predicted urgency match? (off-by-one is noted, not penalized equally)
- **Schema validity**: Does the output pass Pydantic validation?

### Results Summary

| Metric | Score |
|---|---|
| Total test cases | 15 |
| Passed | 9/15 (60%) |
| Intent mismatches | 2 |
| Urgency mismatches | 4 |
| Schema validation failures | 0 |

### Per-Case Results

| Test | Intent | Urgency | Schema | Status |
|---|---|---|---|---|
| tc_001 | ✅ | ❌ (predicted high, expected medium) | ✅ | FAIL |
| tc_002 | ✅ | ✅ | ✅ | PASS |
| tc_003 | ✅ | ✅ | ✅ | PASS |
| tc_004 | ✅ | ✅ | ✅ | PASS |
| tc_005 | ✅ | ❌ (predicted high, expected medium) | ✅ | FAIL |
| tc_006 | ✅ | ❌ (predicted medium, expected low) | ✅ | FAIL |
| tc_007 | ✅ | ✅ | ✅ | PASS |
| tc_008 | ✅ | ✅ | ✅ | PASS |
| tc_009 | ✅ | ✅ | ✅ | PASS |
| tc_010 | ❌ (predicted general_inquiry, expected out_of_scope) | — | ✅ | FAIL |
| tc_011 | ✅ | ✅ | ✅ | PASS |
| tc_012 | ✅ | ✅ | ✅ | PASS |
| tc_013 | ❌ (predicted order_inquiry, expected return_request) | — | ✅ | FAIL |
| tc_014 | ✅ | ✅ | ✅ | PASS |
| tc_015 | ✅ | ❌ (predicted critical, expected high) | ✅ | FAIL |

### Failure Analysis

**Urgency calibration (4 failures):** The agent consistently rates urgency one 
level higher than human labels. After review, this is defensible — a customer-first 
approach should err toward higher urgency rather than under-triaging. In production, 
urgency thresholds would be calibrated with the CS team.

**Intent misclassification — tc_010:** Agent classified an out-of-scope email as 
general_inquiry. The email was borderline — agent tried to be helpful instead of 
refusing. Would fix by adding stricter out-of-scope rules in the classification prompt.

**Intent misclassification — tc_013:** Agent classified a return request as order_inquiry 
because the email mentioned both an order number and a return. The return intent should 
take priority. Would fix by adding intent priority rules.

**Schema validity: 15/15 (100%).** Every output passed Pydantic validation — no 
malformed JSON, no missing fields, no empty strings.



## Tradeoffs

**Why this problem:** Picked email triage over gift finder, review synthesizer, 
and product comparison because it's the most backend-heavy and naturally agentic
the agent classifies, routes, looks up data, and generates grounded replies. 

**What I rejected:** Gift finder was too narrow (single-tool RAG). Product 
comparison was mostly content generation, not agentic. Pediatric symptom triage 
would be a domain issue for me.

**Model choice:** Gemini 3.1 Flash Lite Preview: free, fast, good structured 
output support via LangChain's with_structured_output. Tradeoff: weaker Arabic 
generation compared to larger models like Qwen 2.5 72B, but sufficient for 
the prototype.

**Architecture choice:** LangGraph Skills pattern : the agent loads intent-specific 
SKILL.md files on demand instead of cramming all instructions into one system prompt. 
This keeps prompts small and makes adding new skills trivial (drop a markdown file). 
Tradeoff: adds one extra LLM-adjacent step (skill loading) but saves tokens on 
every request.

**Uncertainty handling:** Four layers : intent guardrail (out_of_scope classification), 
medical disclaimer trigger, confidence threshold (below 0.7 = request_more_info), 
and catalog boundary (won't fabricate orders or products that don't exist in the data).

**What I cut:** Multi-turn conversation memory, FAISS vector search (used keyword 
matching for simplicity), real email inbox integration, user authentication, 
analytics dashboard.

**What I'd build next:** Semantic search over policies with embeddings (currently my sample was small so didnt require that), multi-turn 
context (remembering previous emails from the same customer, real Mumzworld API integration.
