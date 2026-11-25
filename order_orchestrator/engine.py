import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional
from order_orchestrator.models import Order, OrderState, OutboxEvent


class InvalidStateTransitionError(Exception):
    pass


class OrderLifecycleEngine:
    ALLOWED_TRANSITIONS = {
        OrderState.DRAFT: {OrderState.PENDING_PAYMENT, OrderState.CANCELLED},
        OrderState.PENDING_PAYMENT: {OrderState.PAID, OrderState.CANCELLED},
        OrderState.PAID: {OrderState.PROCESSING, OrderState.REFUNDED},
        OrderState.PROCESSING: {OrderState.FULFILLED, OrderState.REFUNDED},
        OrderState.FULFILLED: {OrderState.REFUNDED},
        OrderState.CANCELLED: set(),
        OrderState.REFUNDED: set(),
    }

    def __init__(self):
        self._orders: Dict[str, Order] = {}
        self._outbox: List[OutboxEvent] = []
        self._processed_idempotency_keys: Dict[str, str] = {}

    @property
    def outbox(self) -> List[OutboxEvent]:
        return self._outbox

    def create_order(self, order: Order) -> Order:
        if order.idempotency_key:
            if order.idempotency_key in self._processed_idempotency_keys:
                existing_id = self._processed_idempotency_keys[order.idempotency_key]
                return self._orders[existing_id]
            self._processed_idempotency_keys[order.idempotency_key] = order.order_id

        # Compute risk score heuristic based on total amount and item count
        item_count = sum(i.quantity for i in order.items)
        risk = 0.05
        if order.total_amount > 5000.0:
            risk += 0.35
        if item_count > 50:
            risk += 0.20
        order.risk_score = round(min(1.0, risk), 2)

        self._orders[order.order_id] = order
        self._emit_outbox_event(order.order_id, "ORDER_CREATED", order.model_dump(mode="json"))
        return order

    def transition(self, order_id: str, target_state: OrderState, reason: Optional[str] = None) -> Order:
        if order_id not in self._orders:
            raise KeyError(f"Order '{order_id}' not found.")

        order = self._orders[order_id]
        current_state = order.state

        if target_state not in self.ALLOWED_TRANSITIONS.get(current_state, set()):
            raise InvalidStateTransitionError(
                f"Cannot transition order '{order_id}' from {current_state} to {target_state}."
            )

        order.state = target_state
        order.updated_at = datetime.now(timezone.utc)

        self._emit_outbox_event(
            aggregate_id=order_id,
            event_type=f"ORDER_{target_state.value}",
            payload={
                "order_id": order_id,
                "previous_state": current_state.value,
                "new_state": target_state.value,
                "reason": reason,
                "updated_at": order.updated_at.isoformat(),
            },
        )
        return order

    def _emit_outbox_event(self, aggregate_id: str, event_type: str, payload: dict) -> None:
        raw = f"{aggregate_id}:{event_type}:{datetime.now(timezone.utc).timestamp()}"
        event_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        self._outbox.append(OutboxEvent(
            event_id=event_id,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
        ))

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
