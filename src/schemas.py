from typing import Literal, Optional

from pydantic import BaseModel, Field


class EmailInput(BaseModel):
    id: str
    from_address: str = Field(alias="from")
    subject: str
    body: str
    language: Optional[str] = None


class TriageOutput(BaseModel):
    intent: Literal[
        "return_request",
        "order_inquiry",
        "product_question",
        "complaint_escalation",
        "general_inquiry",
        "out_of_scope",
    ]
    sub_intent: Optional[str] = None
    urgency: Literal["low", "medium", "high", "critical"]
    language_detected: Literal["en", "ar", "mixed"]
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_reply_en: str
    suggested_reply_ar: str
    action: Literal["auto_respond", "escalate_to_human", "request_more_info"]
    escalation_reason: Optional[str] = None
    referenced_order_id: Optional[str] = None
    referenced_products: Optional[list[str]] = None


class Order(BaseModel):
    order_id: str
    customer_name: str
    customer_email: str
    status: Literal["processing", "shipped", "delivered", "cancelled", "returned"]
    items: list[dict]
    order_date: str
    delivery_date: Optional[str] = None
    total_aed: float
    country: str
    payment_method: str


class Product(BaseModel):
    id: str
    name_en: str
    name_ar: str
    category: str
    subcategory: str
    brand: str
    price_aed: float
    age_range: str
    description_en: str
    description_ar: str
    in_stock: bool
    url: str
