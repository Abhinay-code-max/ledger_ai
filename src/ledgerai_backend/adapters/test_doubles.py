"""Deterministic cross-role doubles; these are never production integrations."""

from __future__ import annotations

from uuid import UUID


class DeterministicRoleAdapters:
    def request_extraction(self, *, document_id: UUID, version_id: UUID) -> str:
        return f"role1:{document_id}:{version_id}"

    def submit_transactions(self, *, import_id: UUID, transaction_ids: list[UUID]) -> str:
        return f"role2:{import_id}:{len(transaction_ids)}"

    def request_reconciliation(self, *, transaction_ids: list[UUID]) -> str:
        return f"role3:{len(transaction_ids)}"

    def classify(self, *, evidence_reference: str) -> str:
        return f"role6:{evidence_reference}"
