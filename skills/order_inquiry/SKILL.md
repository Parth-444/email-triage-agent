# Skill: Order Inquiry Handler

## When This Skill Is Active
You are handling a customer email asking about order status, delivery tracking, or shipment updates.

## Steps
1. Extract the order ID if mentioned. Call `lookup_order(order_id)` to get current status.
2. If no order ID found, set action to "request_more_info" and ask customer for order number.
3. Based on order status, generate appropriate response:
   - **processing**: "Your order is being prepared, expected to ship within 1-2 days"
   - **shipped**: "Your order is on its way! Estimated delivery: [date]"
   - **delivered**: "Our records show this was delivered on [date]. If you didn't receive it, please let us know."
   - **cancelled**: "This order was cancelled on [date]. If this wasn't intentional, we can help you reorder."
4. Call `search_policy("shipping")` if customer asks about delivery timelines.
5. Generate bilingual reply (EN + AR, native quality).

## Output Requirements
- Always reference the specific order ID and status
- If order not found in system → say so honestly, ask customer to double-check the order number
- If delivered but customer says not received → set urgency to "high", suggest escalation
- Confidence below 0.7 → set action to "request_more_info"
