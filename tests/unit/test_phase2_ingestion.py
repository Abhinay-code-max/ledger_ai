from __future__ import annotations

from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from ledgerai_backend.adapters.scanner import DeterministicMalwareScanner
from ledgerai_backend.ingestion.csv_parser import CsvStructureError, parse_bank_csv
from ledgerai_backend.ingestion.models import JobStatus, ProcessingJob
from ledgerai_backend.ingestion.schemas import CsvColumnMapping
from ledgerai_backend.ingestion.service import detect_media_type
from ledgerai_backend.ports import ScanOutcome
from ledgerai_backend.workflow.reliability import transition_job
from ledgerai_contracts.v1.tenancy import EntityTenantContext

TEST_CONTEXT = EntityTenantContext(
    tenant_id=UUID("10000000-0000-0000-0000-000000000001"),
    organization_id=UUID("10000000-0000-0000-0000-000000000002"),
    legal_entity_id=UUID("10000000-0000-0000-0000-000000000003"),
)
TEST_BANK_ACCOUNT = UUID("10000000-0000-0000-0000-000000000004")


def parse(content: bytes):  # type: ignore[no-untyped-def]
    return parse_bank_csv(
        content,
        mapping=CsvColumnMapping(),
        maximum_rows=10,
        maximum_columns=20,
        maximum_cell_chars=100,
        tenant_context=TEST_CONTEXT,
        bank_account_id=TEST_BANK_ACCOUNT,
        import_id=uuid4(),
        request_id=uuid4(),
        correlation_id=uuid4(),
    )


def test_csv_exact_money_bom_and_partial_success() -> None:
    content = (
        "\ufeffbooking_date,amount,currency,direction,narration\n"
        "2026-10-01,10.25,inr,DEBIT,Synthetic purchase\n"
        "bad,1.00,INR,CREDIT,Synthetic refund\n"
    ).encode()
    result = parse(content)
    assert len(result.rows) == 1
    assert str(result.rows[0].amount) == "10.25"
    assert result.rows[0].currency == "INR"
    assert len(result.errors) == 1


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (b"", "EMPTY_FILE"),
        (b"booking_date,amount,currency,direction\x00\n", "NUL_BYTE"),
        (b"\xff\xfe", "INVALID_ENCODING"),
        (b"booking_date,amount,amount,currency,direction\n", "DUPLICATE_HEADER"),
        (b"booking_date,amount,currency\n", "MISSING_REQUIRED_HEADER"),
        (b'booking_date,amount,currency,direction\n"unterminated', "MALFORMED_CSV"),
    ],
)
def test_csv_rejects_structural_attacks(content: bytes, code: str) -> None:
    with pytest.raises(CsvStructureError) as error:
        parse(content)
    assert error.value.code == code


@pytest.mark.parametrize("amount", ["1e3", "-1.00", "+1.00", "0", "01.2", "1."])
def test_csv_rejects_ambiguous_or_nonpositive_money(amount: str) -> None:
    result = parse(
        f"booking_date,amount,currency,direction\n2026-10-01,{amount},INR,DEBIT\n".encode()
    )
    assert not result.rows
    assert result.errors[0].error_code == "INVALID_ROW"


def test_csv_rejects_formula_prefixed_cells() -> None:
    result = parse(
        b"booking_date,amount,currency,direction,narration\n2026-10-01,1.00,INR,DEBIT,=CMD()\n"
    )
    assert not result.rows


def test_row_fingerprint_is_stable_and_reordering_does_not_change_it() -> None:
    first = parse(
        b"booking_date,amount,currency,direction,reference\n2026-10-01,1.00,INR,DEBIT,A\n2026-10-02,2.00,INR,CREDIT,B\n"
    )
    second = parse(
        b"booking_date,amount,currency,direction,reference\n2026-10-02,2.00,INR,CREDIT,B\n2026-10-01,1.00,INR,DEBIT,A\n"
    )
    assert {row.source_fingerprint for row in first.rows} == {
        row.source_fingerprint for row in second.rows
    }


@pytest.mark.parametrize(
    ("prefix", "media_type"),
    [
        (b"%PDF-1.7", "application/pdf"),
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
    ],
)
def test_magic_byte_detection(prefix: bytes, media_type: str) -> None:
    assert detect_media_type(prefix + b"synthetic") == media_type
    assert detect_media_type(b"MZ executable") is None


def test_deterministic_scanner_never_marks_bad_hash_clean() -> None:
    scanner = DeterministicMalwareScanner()
    content = b"synthetic clean evidence"
    assert (
        scanner.scan(content, expected_sha256=sha256(content).hexdigest()).outcome
        == ScanOutcome.CLEAN
    )
    assert scanner.scan(content, expected_sha256="0" * 64).outcome == ScanOutcome.ERROR
    infected = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    assert (
        scanner.scan(infected, expected_sha256=sha256(infected).hexdigest()).outcome
        == ScanOutcome.INFECTED
    )
    for marker, expected in (
        (b"LEDGERAI-SUSPICIOUS", ScanOutcome.SUSPICIOUS),
        (b"LEDGERAI-SCANNER-UNAVAILABLE", ScanOutcome.UNAVAILABLE),
        (b"LEDGERAI-SCANNER-ERROR", ScanOutcome.ERROR),
        (b"LEDGERAI-SCANNER-TIMEOUT", ScanOutcome.TIMEOUT),
    ):
        assert scanner.scan(marker, expected_sha256=sha256(marker).hexdigest()).outcome == expected


def job() -> ProcessingJob:
    return ProcessingJob(
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
        job_type="synthetic",
        handler_version="1",
        status=JobStatus.QUEUED,
        attempt_number=0,
        maximum_attempts=3,
        input_reference="document:synthetic",
        queue_name="ledgerai.workflow",
        correlation_id=uuid4(),
        version=1,
    )


def test_job_state_machine_rejects_illegal_and_stale_transitions() -> None:
    item = job()
    transition_job(item, JobStatus.PROCESSING, expected_version=1)
    assert item.attempt_number == 1
    with pytest.raises(ValueError, match="stale"):
        transition_job(item, JobStatus.COMPLETED, expected_version=1)
    transition_job(item, JobStatus.COMPLETED, expected_version=2)
    with pytest.raises(ValueError, match="illegal"):
        transition_job(item, JobStatus.QUEUED, expected_version=3)

    exhausted = job()
    exhausted.attempt_number = exhausted.maximum_attempts
    with pytest.raises(ValueError, match="attempt limit"):
        transition_job(exhausted, JobStatus.PROCESSING, expected_version=1)


def test_column_mapping_is_bounded() -> None:
    with pytest.raises(ValidationError):
        CsvColumnMapping(booking_date="x" * 81)
