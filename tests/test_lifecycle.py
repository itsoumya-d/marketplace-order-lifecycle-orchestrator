import pytest
from order_orchestrator.models import Order, OrderItem, OrderState
from order_orchestrator.engine import OrderLifecycleEngine, InvalidStateTransitionError


@pytest.fixture
def sample_order():
    return Order(
        order_id="ord-101",
        customer_id="cust-01",
        items=[
            OrderItem(item_id="it-1", sku="SKU-A", quantity=2, unit_price=45.0),
            OrderItem(item_id="it-2", sku="SKU-B", quantity=1, unit_price=110.0),
        ],
        total_amount=200.0,
        idempotency_key="idemp-key-101",
    )


def test_order_creation_emits_outbox_event(sample_order):
    engine = OrderLifecycleEngine()
    created = engine.create_order(sample_order)

    assert created.state == OrderState.DRAFT
    assert created.risk_score == 0.05
    assert len(engine.outbox) == 1
    assert engine.outbox[0].event_type == "ORDER_CREATED"
    assert engine.outbox[0].aggregate_id == "ord-101"


def test_idempotent_order_creation(sample_order):
    engine = OrderLifecycleEngine()
    first = engine.create_order(sample_order)
    second = engine.create_order(sample_order)

    assert first.order_id == second.order_id
    assert len(engine.outbox) == 1


def test_valid_lifecycle_transitions(sample_order):
    engine = OrderLifecycleEngine()
    engine.create_order(sample_order)

    # DRAFT -> PENDING_PAYMENT
    o1 = engine.transition("ord-101", OrderState.PENDING_PAYMENT)
    assert o1.state == OrderState.PENDING_PAYMENT

    # PENDING_PAYMENT -> PAID
    o2 = engine.transition("ord-101", OrderState.PAID)
    assert o2.state == OrderState.PAID

    # PAID -> PROCESSING
    o3 = engine.transition("ord-101", OrderState.PROCESSING)
    assert o3.state == OrderState.PROCESSING

    # PROCESSING -> FULFILLED
    o4 = engine.transition("ord-101", OrderState.FULFILLED)
    assert o4.state == OrderState.FULFILLED

    # Check outbox events emitted for each transition
    assert len(engine.outbox) == 5
    assert engine.outbox[-1].event_type == "ORDER_FULFILLED"


def test_invalid_lifecycle_transition_raises_error(sample_order):
    engine = OrderLifecycleEngine()
    engine.create_order(sample_order)

    # Cannot jump directly from DRAFT to FULFILLED
    with pytest.raises(InvalidStateTransitionError):
        engine.transition("ord-101", OrderState.FULFILLED)


def test_order_cancellation_from_pending_payment(sample_order):
    engine = OrderLifecycleEngine()
    engine.create_order(sample_order)
    engine.transition("ord-101", OrderState.PENDING_PAYMENT)
    cancelled = engine.transition("ord-101", OrderState.CANCELLED, reason="Customer cancelled")

    assert cancelled.state == OrderState.CANCELLED
    # Cancelled orders cannot be transitioned further
    with pytest.raises(InvalidStateTransitionError):
        engine.transition("ord-101", OrderState.PAID)


def test_high_value_order_elevates_risk_score():
    engine = OrderLifecycleEngine()
    order = Order(
        order_id="ord-high-risk",
        customer_id="cust-02",
        items=[OrderItem(item_id="it-3", sku="SKU-EXPENSIVE", quantity=60, unit_price=100.0)],
        total_amount=6000.0,
    )
    created = engine.create_order(order)
    assert created.risk_score >= 0.50


def test_transition_non_existent_order_raises_key_error():
    engine = OrderLifecycleEngine()
    with pytest.raises(KeyError):
        engine.transition("ord-nonexistent", OrderState.PAID)
