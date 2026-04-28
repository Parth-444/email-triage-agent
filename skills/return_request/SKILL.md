# Skill: Return Request Handler

## When This Skill Is Active
You are handling a customer email about returning, exchanging, or getting a refund for a product.

## Steps
1. Extract the order ID if mentioned. Call `lookup_order(order_id)` to get order details.
2. Call `search_policy("return")` to get the return policy.
3. Determine the return type:
   - **refund**: Customer explicitly wants money back
   - **exchange**: Customer wants a different product/size
   - **store_credit**: Customer is open to store credit
   - **escalate**: Item is outside return window, or situation is complex
4. Check eligibility against the return policy (return window, item condition).
5. Generate a suggested reply that:
   - Acknowledges the customer's issue with empathy
   - States whether the return is eligible and why
   - Explains next steps (how to ship back, refund timeline, etc.)
   - If NOT eligible, explain why clearly and offer alternatives
   - Generate in BOTH English and Arabic (native, not translated)

## Output Requirements
- sub_intent must be one of: "refund", "exchange", "store_credit", "escalate"
- If order is outside return window → still respond helpfully, suggest store credit or escalation
- If item category is non-returnable (opened formula/diapers) → explain policy, suggest contacting support
- Always include the order ID in the reply if available
- Confidence below 0.7 → set action to "request_more_info"
