# ADR 0011: AI cannot post or bypass policy

- Status: Accepted
- Context: AI can interpret evidence but financial posting requires deterministic invariants, policy, and human review when risk warrants it.
- Decision: Models may propose actions only. They cannot post entries, assert deterministic validation, or bypass versioned policy and approval.
- Consequences: Proposals preserve confidence and provenance; posting needs a separately evidenced Role 2 validation and authorized decision.
- Alternatives considered: Model-triggered posting (unacceptable control risk); confidence threshold as authorization (confidence is not permission).
- Deferred production concerns: Threshold calibration, model risk management, policy governance, approval authorization, SoD enforcement, and override monitoring.

