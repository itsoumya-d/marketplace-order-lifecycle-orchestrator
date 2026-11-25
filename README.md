# marketplace-order-lifecycle-orchestrator

Deterministic transactional order lifecycle state machine and event-driven settlement orchestrator.

## Architecture

- **Finite State Machine (FSM)**: Strict invariant verification across order lifecycle transitions (`DRAFT` -> `PENDING_PAYMENT` -> `PAID` -> `PROCESSING` -> `FULFILLED` / `CANCELLED` / `REFUNDED`).
- **Idempotency & Concurrency**: Cryptographic signature validation preventing replay attacks and race conditions on payment captures.
- **Risk & Fraud Velocity**: Real-time order velocity evaluation and anomaly scoring before payment gateway dispatch.
- **Transactional Outbox**: Decoupled event staging ensuring reliable downstream inventory reservation and financial ledger synchronization.

## Verification

```bash
pip install -e ".[dev]"
pytest -v
```
