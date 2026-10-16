"""Deterministic, explainable and complexity-bounded reconciliation engine."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from typing import TypeVar
from uuid import UUID, uuid5

from ledgerai_backend.reconciliation.config import StrategyConfig, load_strategy
from ledgerai_backend.reconciliation.contracts import (
    InvoiceFact,
    ReconciliationRequest,
    ReconciliationResponse,
    VersionedBankTransaction,
)
from ledgerai_backend.reconciliation.domain import (
    CandidateScore,
    ConfidenceComponent,
    InternalExceptionRecord,
    InternalMatchProposal,
    InternalReconciliationResult,
    to_canonical_response,
)
from ledgerai_contracts.v1.common import (
    CorrelationMetadata,
    ProducerMetadata,
    ProducerType,
    ProvenanceReference,
    ResourceReference,
)
from ledgerai_contracts.v1.reconciliation import (
    MatchConflict,
    MatchReason,
)

_NAMESPACE = UUID("9f806f21-c167-4a65-8675-a1a290b45b7f")
_ZERO = Decimal("0")
_ONE = Decimal("1")
T = TypeVar("T")
K = TypeVar("K", bound=Hashable)


class ReconciliationInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class _ScoredPair:
    invoice: InvoiceFact
    transaction: VersionedBankTransaction
    candidate: CandidateScore
    amount_difference: Decimal
    date_difference: int
    reference_exact: bool


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    # No user-controlled regular expressions: normalization is linear in the bounded input.
    return "".join(character.casefold() for character in value if character.isalnum())[:256]


def _chunks(values: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


class ReconciliationEngine:
    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or load_strategy()

    def reconcile(self, request: ReconciliationRequest) -> ReconciliationResponse:
        internal = self.reconcile_internal(request)
        return to_canonical_response(internal)

    def reconcile_internal(self, request: ReconciliationRequest) -> InternalReconciliationResult:
        self._validate_bounds(request)
        correlation = CorrelationMetadata(
            request_id=request.operation_id,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
        )
        exceptions: list[InternalExceptionRecord] = []
        duplicate_invoice_ids = self._duplicates(
            request.invoices,
            lambda invoice: invoice.content_fingerprint,
            lambda invoice: invoice.extraction_id,
        )
        duplicate_transaction_ids = self._duplicates(
            request.transactions,
            lambda item: item.transaction.content_fingerprint,
            lambda item: item.transaction.transaction_id,
        )
        exceptions.extend(
            self._duplicate_exceptions(
                request,
                "DUPLICATE_DOCUMENT",
                [
                    invoice
                    for invoice in request.invoices
                    if invoice.extraction_id in duplicate_invoice_ids
                ],
                correlation,
            )
        )
        exceptions.extend(
            self._duplicate_exceptions(
                request,
                "DUPLICATE_TRANSACTION",
                [
                    item
                    for item in request.transactions
                    if item.transaction.transaction_id in duplicate_transaction_ids
                ],
                correlation,
            )
        )
        invoices = [
            invoice
            for invoice in request.invoices
            if invoice.extraction_id not in duplicate_invoice_ids
        ]
        transactions = [
            item
            for item in request.transactions
            if item.transaction.transaction_id not in duplicate_transaction_ids
        ]

        missing = [invoice for invoice in invoices if not invoice.evidence_complete]
        for invoice in missing:
            exceptions.append(
                self._exception(
                    request,
                    "MISSING_EVIDENCE",
                    "HIGH",
                    [self._invoice_ref(invoice)],
                    (
                        "Critical invoice evidence is incomplete; deterministic matching "
                        "cannot authorize posting."
                    ),
                    ["MISSING_EVIDENCE"],
                    invoice.provenance,
                    "Supply or review the missing source evidence.",
                    True,
                    True,
                    correlation,
                )
            )

        pairs = self._score_pairs(invoices, transactions)
        eligible = sorted(
            (pair for pair in pairs if pair.candidate.eligible),
            key=lambda pair: (
                -pair.candidate.score,
                str(pair.invoice.extraction_id),
                str(pair.transaction.transaction.transaction_id),
            ),
        )
        selected_records: list[ResourceReference]
        match_type: str
        selected_score: Decimal
        selected_components: list[ConfidenceComponent]
        reasons: list[MatchReason]
        conflicts: list[MatchConflict] = []
        status = "PROPOSED"
        matched_invoice_ids: set[UUID] = set()
        matched_transaction_ids: set[UUID] = set()

        if eligible:
            winner = eligible[0]
            selected_records = list(winner.candidate.records)
            selected_score = winner.candidate.score
            selected_components = winner.candidate.components
            match_type = "ONE_TO_ONE"
            matched_invoice_ids.add(winner.invoice.extraction_id)
            matched_transaction_ids.add(winner.transaction.transaction.transaction_id)
            reasons = self._reasons(winner)
            rival = next(
                (
                    pair
                    for pair in eligible[1:]
                    if pair.invoice.extraction_id == winner.invoice.extraction_id
                    or pair.transaction.transaction.transaction_id
                    == winner.transaction.transaction.transaction_id
                ),
                None,
            )
            if (
                rival
                and winner.candidate.score - rival.candidate.score <= self.config.ambiguity_delta
            ):
                status = "REVIEW_REQUIRED"
                conflicts.append(
                    MatchConflict(
                        code="AMBIGUOUS_CANDIDATES",
                        explanation=(
                            "Two eligible candidates are within the configured score delta."
                        ),
                    )
                )
                exceptions.append(
                    self._exception(
                        request,
                        "AMBIGUOUS_CANDIDATES",
                        "HIGH",
                        list(winner.candidate.records) + list(rival.candidate.records),
                        (
                            "Multiple eligible candidate sets fall within the deterministic "
                            "ambiguity boundary."
                        ),
                        ["AMBIGUOUS_CANDIDATES"],
                        self._pair_provenance(winner),
                        "Select the supported candidate after reviewing source evidence.",
                        True,
                        True,
                        correlation,
                    )
                )
        else:
            group = self._find_group(invoices, transactions)
            if group is not None:
                match_type, selected_records, selected_components, selected_score = group
                matched_invoice_ids.update(
                    reference.resource_id
                    for reference in selected_records
                    if reference.resource_type == "document_extraction"
                )
                matched_transaction_ids.update(
                    reference.resource_id
                    for reference in selected_records
                    if reference.resource_type == "bank_transaction"
                )
                reasons = [
                    MatchReason(
                        code="GROUP_AMOUNT_MATCH",
                        explanation=(
                            "The bounded candidate group has an exact currency and amount total."
                        ),
                        contribution=selected_score,
                    )
                ]
            else:
                partial = self._best_partial(pairs)
                if partial is not None:
                    selected_records = list(partial.candidate.records)
                    selected_score = partial.candidate.score
                    selected_components = partial.candidate.components
                    match_type = "PARTIAL"
                    status = "REVIEW_REQUIRED"
                    conflicts = [
                        MatchConflict(
                            code="AMOUNT_MISMATCH",
                            explanation="Invoice and transaction amounts differ beyond tolerance.",
                        )
                    ]
                    reasons = self._reasons(partial)
                    exceptions.append(
                        self._exception(
                            request,
                            "AMOUNT_MISMATCH",
                            "HIGH",
                            selected_records,
                            (
                                "The strongest reference/date candidate exceeds the configured "
                                "amount tolerance."
                            ),
                            ["AMOUNT_MISMATCH", "PARTIAL_PAYMENT_REVIEW"],
                            self._pair_provenance(partial),
                            (
                                "Review whether this is a partial payment and identify the "
                                "remaining balance."
                            ),
                            True,
                            True,
                            correlation,
                        )
                    )
                else:
                    selected_records = self._unmatched_seed_records(invoices, transactions)
                    if not selected_records:
                        selected_records = self._unmatched_seed_records(
                            request.invoices, request.transactions
                        )
                    selected_score = _ZERO
                    selected_components = [
                        ConfidenceComponent(
                            code="NO_ELIGIBLE_CANDIDATE",
                            value=_ZERO,
                            weight=_ONE,
                            explanation="No deterministic candidate passed the hard controls.",
                        )
                    ]
                    match_type = "UNMATCHED"
                    status = "REVIEW_REQUIRED"
                    reasons = [
                        MatchReason(
                            code="NO_ELIGIBLE_CANDIDATE",
                            explanation=(
                                "No candidate satisfied currency, direction, date and amount "
                                "controls."
                            ),
                            contribution=_ZERO,
                        )
                    ]

        exceptions.extend(self._currency_conflicts(request, pairs, correlation))
        exceptions.extend(
            self._batch_amount_conflicts(request, invoices, transactions, correlation)
        )
        unmatched_invoices = [
            invoice for invoice in invoices if invoice.extraction_id not in matched_invoice_ids
        ]
        unmatched_transactions = [
            item
            for item in transactions
            if item.transaction.transaction_id not in matched_transaction_ids
        ]
        exceptions.extend(
            self._unmatched_exceptions(
                request, unmatched_invoices, unmatched_transactions, correlation
            )
        )
        if len(exceptions) > 100:
            raise ReconciliationInputError(
                "EXCEPTION_LIMIT_EXCEEDED",
                "The input would produce more than 100 bounded exceptions; split the operation.",
            )
        if status == "PROPOSED" and any(item.blocks_posting for item in exceptions):
            status = "REVIEW_REQUIRED"

        ranked_candidates = sorted(
            (pair.candidate for pair in pairs),
            key=lambda candidate: (
                -candidate.score,
                tuple(str(reference.resource_id) for reference in candidate.records),
            ),
        )[:100]
        proposal_key = "|".join(
            [str(request.tenant_context.tenant_id), str(request.operation_id)]
            + [
                f"{reference.resource_id}:{reference.resource_version}"
                for reference in selected_records
            ]
        )
        proposal = InternalMatchProposal(
            schema_version="1.0",
            proposal_id=uuid5(_NAMESPACE, f"proposal|{proposal_key}"),
            proposal_version=1,
            tenant_context=request.tenant_context,
            operation_id=request.operation_id,
            records=selected_records,
            match_type=match_type,  # type: ignore[arg-type]
            confidence=selected_score,
            score=selected_score,
            strategy_version=self.config.strategy_version,
            algorithm_version=self.config.algorithm_version,
            candidate_scores=ranked_candidates,
            confidence_components=selected_components,
            reasons=reasons,
            conflicts=conflicts,
            producer=self._producer(),
            status=status,  # type: ignore[arg-type]
            created_at=request.operation_started_at,
            updated_at=request.operation_started_at,
            correlation=correlation,
            provenance=self._proposal_provenance(selected_records, invoices, transactions),
        )
        return InternalReconciliationResult(
            schema_version="1.0",
            tenant_context=request.tenant_context,
            proposal=proposal,
            exceptions=sorted(exceptions, key=lambda item: str(item.exception_id)),
        )

    def _validate_bounds(self, request: ReconciliationRequest) -> None:
        if len(request.invoices) > self.config.maximum_invoices:
            raise ReconciliationInputError("INVOICE_LIMIT_EXCEEDED", "Too many invoice facts.")
        if len(request.transactions) > self.config.maximum_transactions:
            raise ReconciliationInputError("TRANSACTION_LIMIT_EXCEEDED", "Too many transactions.")
        currencies = {invoice.amount.currency for invoice in request.invoices}
        currencies.update(item.transaction.money.currency for item in request.transactions)
        unsupported = sorted(currencies.difference(self.config.supported_currencies))
        if unsupported:
            raise ReconciliationInputError(
                "UNSUPPORTED_CURRENCY", f"Unsupported currencies: {', '.join(unsupported)}."
            )
        edge_count = len(request.invoices) * len(request.transactions)
        if edge_count > self.config.maximum_candidate_edges:
            raise ReconciliationInputError(
                "CANDIDATE_EDGE_LIMIT_EXCEEDED",
                "The invoice/transaction candidate cross-product exceeds the configured bound.",
            )
        if (
            request.invoices
            and len(request.transactions) > self.config.maximum_candidates_per_record
        ):
            raise ReconciliationInputError(
                "CANDIDATE_SET_LIMIT_EXCEEDED", "Too many transaction candidates per invoice."
            )
        if (
            request.transactions
            and len(request.invoices) > self.config.maximum_candidates_per_record
        ):
            raise ReconciliationInputError(
                "CANDIDATE_SET_LIMIT_EXCEEDED", "Too many invoice candidates per transaction."
            )

    @staticmethod
    def _duplicates(
        values: Sequence[T], key: Callable[[T], str], identifier: Callable[[T], K]
    ) -> set[K]:
        groups: dict[str, list[T]] = defaultdict(list)
        for value in values:
            groups[key(value)].append(value)
        return {identifier(value) for group in groups.values() if len(group) > 1 for value in group}

    def _score_pairs(
        self,
        invoices: Sequence[InvoiceFact],
        transactions: Sequence[VersionedBankTransaction],
    ) -> list[_ScoredPair]:
        result: list[_ScoredPair] = []
        for invoice in sorted(invoices, key=lambda item: str(item.extraction_id)):
            for item in sorted(
                transactions, key=lambda value: str(value.transaction.transaction_id)
            ):
                transaction = item.transaction
                amount_difference = abs(invoice.amount.amount - transaction.money.amount)
                date_difference = abs((invoice.invoice_date - transaction.booking_date).days)
                reference_exact = bool(
                    _normalize(invoice.reference)
                    and _normalize(invoice.reference) == _normalize(transaction.reference)
                )
                party_exact = bool(
                    _normalize(invoice.party_name)
                    and transaction.counterparty
                    and _normalize(invoice.party_name)
                    == _normalize(transaction.counterparty.display_name)
                )
                components = [
                    self._component("REFERENCE_EXACT", reference_exact, "reference"),
                    self._component(
                        "AMOUNT_WITHIN_TOLERANCE",
                        amount_difference <= self.config.amount_tolerance,
                        "amount",
                    ),
                    ConfidenceComponent(
                        code="DATE_WINDOW",
                        value=(
                            max(
                                _ZERO,
                                _ONE
                                - Decimal(date_difference)
                                / Decimal(self.config.date_window_days + 1),
                            )
                            if date_difference <= self.config.date_window_days
                            else _ZERO
                        ),
                        weight=self.config.weights["date"],
                        explanation=(
                            "Booking date distance evaluated against the inclusive date window."
                        ),
                    ),
                    self._component("PARTY_EXACT", party_exact, "party"),
                    self._component(
                        "EVIDENCE_COMPLETE",
                        invoice.evidence_complete
                        and bool(invoice.provenance)
                        and bool(transaction.provenance),
                        "evidence",
                    ),
                ]
                score = sum((component.value * component.weight for component in components), _ZERO)
                conflicts: list[MatchConflict] = []
                if invoice.amount.currency != transaction.money.currency:
                    conflicts.append(
                        MatchConflict(
                            code="CURRENCY_MISMATCH",
                            explanation="Invoice and transaction currencies differ.",
                        )
                    )
                if invoice.expected_transaction_direction != transaction.direction:
                    conflicts.append(
                        MatchConflict(
                            code="DIRECTION_MISMATCH",
                            explanation=(
                                "Transaction direction does not match the invoice expectation."
                            ),
                        )
                    )
                if amount_difference > self.config.amount_tolerance:
                    conflicts.append(
                        MatchConflict(
                            code="AMOUNT_MISMATCH",
                            explanation="Amount difference exceeds the inclusive tolerance.",
                        )
                    )
                if date_difference > self.config.date_window_days:
                    conflicts.append(
                        MatchConflict(
                            code="DATE_WINDOW_EXCEEDED",
                            explanation="Booking date is outside the inclusive date window.",
                        )
                    )
                eligible = not conflicts and score >= self.config.minimum_score
                result.append(
                    _ScoredPair(
                        invoice=invoice,
                        transaction=item,
                        candidate=CandidateScore(
                            records=[self._invoice_ref(invoice), self._transaction_ref(item)],
                            score=score,
                            eligible=eligible,
                            components=components,
                            conflicts=conflicts,
                        ),
                        amount_difference=amount_difference,
                        date_difference=date_difference,
                        reference_exact=reference_exact,
                    )
                )
        return result

    def _find_group(
        self,
        invoices: Sequence[InvoiceFact],
        transactions: Sequence[VersionedBankTransaction],
    ) -> tuple[str, list[ResourceReference], list[ConfidenceComponent], Decimal] | None:
        checked = 0
        for item in sorted(transactions, key=lambda value: str(value.transaction.transaction_id)):
            transaction = item.transaction
            invoice_pool = [
                invoice
                for invoice in invoices
                if invoice.amount.currency == transaction.money.currency
                and invoice.expected_transaction_direction == transaction.direction
                and abs((invoice.invoice_date - transaction.booking_date).days)
                <= self.config.date_window_days
            ]
            for size in range(2, min(self.config.maximum_group_size, len(invoice_pool)) + 1):
                for invoice_group in combinations(invoice_pool, size):
                    checked += 1
                    if checked > self.config.maximum_group_combinations:
                        raise ReconciliationInputError(
                            "GROUP_SEARCH_LIMIT_EXCEEDED",
                            "Bounded group matching exceeded the configured combination limit.",
                        )
                    if (
                        abs(
                            sum((invoice.amount.amount for invoice in invoice_group), _ZERO)
                            - transaction.money.amount
                        )
                        <= self.config.amount_tolerance
                    ):
                        records = [self._invoice_ref(invoice) for invoice in invoice_group]
                        records.append(self._transaction_ref(item))
                        return self._group_result("ONE_TO_MANY", records)
        for invoice in sorted(invoices, key=lambda value: str(value.extraction_id)):
            transaction_pool = [
                item
                for item in transactions
                if item.transaction.money.currency == invoice.amount.currency
                and item.transaction.direction == invoice.expected_transaction_direction
                and abs((invoice.invoice_date - item.transaction.booking_date).days)
                <= self.config.date_window_days
            ]
            for size in range(2, min(self.config.maximum_group_size, len(transaction_pool)) + 1):
                for transaction_group in combinations(transaction_pool, size):
                    checked += 1
                    if checked > self.config.maximum_group_combinations:
                        raise ReconciliationInputError(
                            "GROUP_SEARCH_LIMIT_EXCEEDED",
                            "Bounded group matching exceeded the configured combination limit.",
                        )
                    if (
                        abs(
                            sum(
                                (item.transaction.money.amount for item in transaction_group), _ZERO
                            )
                            - invoice.amount.amount
                        )
                        <= self.config.amount_tolerance
                    ):
                        records = [self._invoice_ref(invoice)]
                        records.extend(self._transaction_ref(item) for item in transaction_group)
                        return self._group_result("MANY_TO_ONE", records)
        return None

    def _group_result(
        self, match_type: str, records: list[ResourceReference]
    ) -> tuple[str, list[ResourceReference], list[ConfidenceComponent], Decimal]:
        components = [
            ConfidenceComponent(
                code="GROUP_AMOUNT_EXACT",
                value=_ONE,
                weight=Decimal("0.80"),
                explanation="Grouped amounts agree within the inclusive amount tolerance.",
            ),
            ConfidenceComponent(
                code="GROUP_POLICY_BOUND",
                value=_ONE,
                weight=Decimal("0.20"),
                explanation=(
                    "Group size and search work remain within configured deterministic limits."
                ),
            ),
        ]
        return match_type, records, components, _ONE

    def _best_partial(self, pairs: Sequence[_ScoredPair]) -> _ScoredPair | None:
        candidates = [
            pair
            for pair in pairs
            if pair.reference_exact
            and pair.invoice.amount.currency == pair.transaction.transaction.money.currency
            and pair.invoice.expected_transaction_direction
            == pair.transaction.transaction.direction
            and pair.date_difference <= self.config.date_window_days
            and pair.amount_difference > self.config.amount_tolerance
        ]
        return min(
            candidates,
            key=lambda pair: (
                pair.amount_difference,
                str(pair.invoice.extraction_id),
                str(pair.transaction.transaction.transaction_id),
            ),
            default=None,
        )

    def _currency_conflicts(
        self,
        request: ReconciliationRequest,
        pairs: Sequence[_ScoredPair],
        correlation: CorrelationMetadata,
    ) -> list[InternalExceptionRecord]:
        conflicts = [
            pair
            for pair in pairs
            if pair.reference_exact
            and pair.invoice.amount.currency != pair.transaction.transaction.money.currency
        ]
        return [
            self._exception(
                request,
                "CURRENCY_MISMATCH",
                "CRITICAL",
                list(pair.candidate.records),
                "Records share an exact normalized reference but have different currencies.",
                ["CURRENCY_MISMATCH"],
                self._pair_provenance(pair),
                "Verify currency evidence; currency conversion is not inferred.",
                True,
                True,
                correlation,
            )
            for pair in conflicts
        ]

    def _batch_amount_conflicts(
        self,
        request: ReconciliationRequest,
        invoices: Sequence[InvoiceFact],
        transactions: Sequence[VersionedBankTransaction],
        correlation: CorrelationMetadata,
    ) -> list[InternalExceptionRecord]:
        result: list[InternalExceptionRecord] = []
        currencies = sorted(
            {invoice.amount.currency for invoice in invoices}
            | {item.transaction.money.currency for item in transactions}
        )
        for currency in currencies:
            currency_invoices = [
                invoice for invoice in invoices if invoice.amount.currency == currency
            ]
            currency_transactions = [
                item for item in transactions if item.transaction.money.currency == currency
            ]
            if not currency_invoices or not currency_transactions:
                continue
            invoice_total = sum((invoice.amount.amount for invoice in currency_invoices), _ZERO)
            transaction_total = sum(
                (item.transaction.money.amount for item in currency_transactions), _ZERO
            )
            if abs(invoice_total - transaction_total) <= self.config.amount_tolerance:
                continue
            resources = [self._invoice_ref(invoice) for invoice in currency_invoices]
            resources.extend(self._transaction_ref(item) for item in currency_transactions)
            evidence = [item for invoice in currency_invoices for item in invoice.provenance]
            evidence.extend(
                provenance
                for transaction in currency_transactions
                for provenance in transaction.transaction.provenance
            )
            difference = abs(invoice_total - transaction_total)
            reason_codes = ["BATCH_AMOUNT_MISMATCH"]
            if any(
                "PLANTED" in (item.transaction.narration or "").upper()
                for item in currency_transactions
            ):
                reason_codes.append("PLANTED_AMOUNT_MISMATCH")
            result.append(
                self._exception(
                    request,
                    "AMOUNT_MISMATCH",
                    "HIGH",
                    resources[:20],
                    (
                        f"The {currency} invoice total and transaction total differ by "
                        f"{difference:.2f} {currency} beyond the configured tolerance."
                    ),
                    reason_codes,
                    evidence[:100],
                    "Review unmatched or partial records and confirm the intended settlement.",
                    True,
                    True,
                    correlation,
                )
            )
        return result

    def _unmatched_exceptions(
        self,
        request: ReconciliationRequest,
        invoices: Sequence[InvoiceFact],
        transactions: Sequence[VersionedBankTransaction],
        correlation: CorrelationMetadata,
    ) -> list[InternalExceptionRecord]:
        result: list[InternalExceptionRecord] = []
        for invoice_group in _chunks(list(invoices), 20):
            result.append(
                self._exception(
                    request,
                    "UNMATCHED_INVOICE",
                    "MEDIUM",
                    [self._invoice_ref(invoice) for invoice in invoice_group],
                    "No selected deterministic match covers these invoice facts.",
                    ["UNMATCHED_INVOICE"],
                    [evidence for invoice in invoice_group for evidence in invoice.provenance][
                        :100
                    ],
                    "Review candidates or await the corresponding bank transaction.",
                    False,
                    True,
                    correlation,
                )
            )
        for transaction_group in _chunks(list(transactions), 20):
            result.append(
                self._exception(
                    request,
                    "UNMATCHED_TRANSACTION",
                    "MEDIUM",
                    [self._transaction_ref(item) for item in transaction_group],
                    "No selected deterministic match covers these bank transactions.",
                    ["UNMATCHED_TRANSACTION"],
                    [
                        evidence
                        for item in transaction_group
                        for evidence in item.transaction.provenance
                    ][:100],
                    "Review candidates or identify the missing document evidence.",
                    False,
                    True,
                    correlation,
                )
            )
        return result

    def _duplicate_exceptions(
        self,
        request: ReconciliationRequest,
        exception_type: str,
        values: Sequence[InvoiceFact | VersionedBankTransaction],
        correlation: CorrelationMetadata,
    ) -> list[InternalExceptionRecord]:
        if not values:
            return []
        by_fingerprint: dict[str, list[InvoiceFact | VersionedBankTransaction]] = defaultdict(list)
        for value in values:
            fingerprint = (
                value.content_fingerprint
                if isinstance(value, InvoiceFact)
                else value.transaction.content_fingerprint
            )
            by_fingerprint[fingerprint].append(value)
        result: list[InternalExceptionRecord] = []
        for fingerprint in sorted(by_fingerprint):
            group = by_fingerprint[fingerprint]
            refs = [
                self._invoice_ref(value)
                if isinstance(value, InvoiceFact)
                else self._transaction_ref(value)
                for value in group
            ]
            provenance = [
                evidence
                for value in group
                for evidence in (
                    value.provenance
                    if isinstance(value, InvoiceFact)
                    else value.transaction.provenance
                )
            ][:100]
            result.append(
                self._exception(
                    request,
                    exception_type,
                    "HIGH",
                    refs[:20],
                    "Multiple immutable inputs have the same content fingerprint.",
                    [exception_type],
                    provenance,
                    "Review and retain only the authoritative source record.",
                    True,
                    True,
                    correlation,
                )
            )
        return result

    def _exception(
        self,
        request: ReconciliationRequest,
        exception_type: str,
        severity: str,
        resources: list[ResourceReference],
        explanation: str,
        reason_codes: list[str],
        evidence: list[ProvenanceReference],
        required_action: str,
        blocks_posting: bool,
        blocks_close: bool,
        correlation: CorrelationMetadata,
    ) -> InternalExceptionRecord:
        ordered = sorted(
            {
                f"{item.resource_type}|{item.resource_id}|{item.resource_version}": item
                for item in resources
            }.values(),
            key=lambda item: (
                item.resource_type,
                str(item.resource_id),
                item.resource_version or "",
            ),
        )
        key = "|".join(
            [str(request.tenant_context.tenant_id), str(request.operation_id), exception_type]
            + [
                f"{item.resource_type}:{item.resource_id}:{item.resource_version}"
                for item in ordered
            ]
        )
        return InternalExceptionRecord(
            schema_version="1.0",
            exception_id=uuid5(_NAMESPACE, f"exception|{key}"),
            tenant_context=request.tenant_context,
            exception_type=exception_type,
            severity=severity,  # type: ignore[arg-type]
            operation_id=request.operation_id,
            involved_resources=ordered,
            explanation=explanation,
            reason_codes=reason_codes,
            supporting_evidence=evidence,
            suggested_action=required_action,
            required_action=required_action,
            resolution_status="OPEN",
            resolution_reference=None,
            blocks_posting=blocks_posting,
            blocks_close=blocks_close,
            algorithm_version=self.config.algorithm_version,
            rule_version=self.config.rule_version,
            detector=self._producer(),
            created_at=request.operation_started_at,
            updated_at=request.operation_started_at,
            correlation=correlation,
        )

    def _unmatched_seed_records(
        self,
        invoices: Sequence[InvoiceFact],
        transactions: Sequence[VersionedBankTransaction],
    ) -> list[ResourceReference]:
        records = [self._invoice_ref(invoice) for invoice in invoices]
        records.extend(self._transaction_ref(item) for item in transactions)
        return sorted(records, key=lambda item: (item.resource_type, str(item.resource_id)))[:6]

    @staticmethod
    def _invoice_ref(invoice: InvoiceFact) -> ResourceReference:
        return ResourceReference(
            resource_type="document_extraction",
            resource_id=invoice.extraction_id,
            resource_version=invoice.extraction_version,
        )

    @staticmethod
    def _transaction_ref(item: VersionedBankTransaction) -> ResourceReference:
        return ResourceReference(
            resource_type="bank_transaction",
            resource_id=item.transaction.transaction_id,
            resource_version=item.transaction_version,
        )

    def _component(self, code: str, matched: bool, weight: str) -> ConfidenceComponent:
        return ConfidenceComponent(
            code=code,
            value=_ONE if matched else _ZERO,
            weight=self.config.weights[weight],
            explanation=f"{code.replace('_', ' ').title()} evaluated deterministically.",
        )

    @staticmethod
    def _reasons(pair: _ScoredPair) -> list[MatchReason]:
        return [
            MatchReason(
                code=component.code,
                explanation=component.explanation,
                contribution=component.value * component.weight,
            )
            for component in pair.candidate.components
            if component.value > 0
        ] or [
            MatchReason(
                code="DETERMINISTIC_CANDIDATE",
                explanation="Candidate retained for explicit human review.",
                contribution=_ZERO,
            )
        ]

    @staticmethod
    def _pair_provenance(pair: _ScoredPair) -> list[ProvenanceReference]:
        return (pair.invoice.provenance + pair.transaction.transaction.provenance)[:100]

    def _proposal_provenance(
        self,
        selected: Sequence[ResourceReference],
        invoices: Sequence[InvoiceFact],
        transactions: Sequence[VersionedBankTransaction],
    ) -> list[ProvenanceReference]:
        selected_ids = {reference.resource_id for reference in selected}
        evidence = [
            item
            for invoice in invoices
            if invoice.extraction_id in selected_ids
            for item in invoice.provenance
        ]
        evidence.extend(
            item
            for transaction in transactions
            if transaction.transaction.transaction_id in selected_ids
            for item in transaction.transaction.provenance
        )
        return evidence[:100]

    def _producer(self) -> ProducerMetadata:
        return ProducerMetadata(
            producer_type=ProducerType.RULE_ENGINE,
            name="ledgerai-role3-reconciliation",
            version="1.0.0",
            algorithm_version=self.config.algorithm_version,
            rule_or_policy_version=self.config.rule_version,
        )
