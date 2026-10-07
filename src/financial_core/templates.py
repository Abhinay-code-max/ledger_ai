"""Deterministic demo AP/AR proposals; never approvals or direct postings."""

from typing import Literal
from uuid import uuid5

from financial_core.money import AccountingError
from ledgerai_contracts.v1.journals import JournalProposal

Template = Literal["AP_INVOICE", "AP_PAYMENT", "AR_INVOICE", "AR_RECEIPT"]


def demo_proposal(
    source: JournalProposal,
    template: Template,
    document_key: str,
    debit_account: str,
    credit_account: str,
) -> JournalProposal:
    """Caller selects trusted chart accounts and supplies amount/evidence via source.

    AP_INVOICE: expense/payable; AP_PAYMENT: payable/cash;
    AR_INVOICE: receivable/revenue; AR_RECEIPT: cash/receivable.
    Same immutable source and key produce identical IDs and content.
    """
    if template not in ("AP_INVOICE", "AP_PAYMENT", "AR_INVOICE", "AR_RECEIPT"):
        raise AccountingError("UNKNOWN_TEMPLATE")
    if not document_key.strip() or debit_account == credit_account:
        raise AccountingError("INVALID_TEMPLATE_INPUT")
    payload = source.model_dump(mode="json")
    proposal_id = uuid5(source.proposal_id, f"{template}:{document_key}")
    payload.update(
        proposal_id=str(proposal_id),
        proposal_version=1,
        approval_decision=None,
        policy_decision=None,
        explanation=f"{template} demo: {document_key}",
        confidence=None,
    )
    payload["producer"] = {
        "producer_type": "RULE_ENGINE",
        "name": "financial_core.demo",
        "version": "1.0.0",
        "rule_or_policy_version": "demo-v1",
    }
    source_line = source.lines[0].model_dump(mode="json")
    payload["lines"] = [
        dict(
            source_line,
            line_id=str(uuid5(proposal_id, direction)),
            account_reference=account,
            direction=direction,
        )
        for direction, account in (("DEBIT", debit_account), ("CREDIT", credit_account))
    ]
    return JournalProposal.model_validate(payload)
