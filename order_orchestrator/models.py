from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderState(str, Enum):
    DRAFT = "DRAFT"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    PROCESSING = "PROCESSING"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class OrderItem(BaseModel):
    item_id: str
    sku: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0.0)


class Order(BaseModel):
    order_id: str
    customer_id: str
    items: List[OrderItem]
    total_amount: float = Field(ge=0.0)
    state: OrderState = OrderState.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: Optional[str] = None
    risk_score: float = 0.0


class OutboxEvent(BaseModel):
    event_id: str
    aggregate_id: str
    event_type: str
    payload: dict
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    dispatched: bool = False
