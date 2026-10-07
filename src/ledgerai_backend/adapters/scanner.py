"""Explicit development/test malware-scanning adapter."""

from __future__ import annotations

from hashlib import sha256

from ledgerai_backend.ports import ScanOutcome, ScanResult


class DeterministicMalwareScanner:
    """A non-production scanner whose outcomes are deterministic and testable."""

    def scan(self, content: bytes, *, expected_sha256: str) -> ScanResult:
        if sha256(content).hexdigest() != expected_sha256:
            return ScanResult(ScanOutcome.ERROR, "deterministic", "1", None, "HASH_MISMATCH")
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
            return ScanResult(ScanOutcome.INFECTED, "deterministic", "1", "test", "MALWARE")
        synthetic_outcomes = {
            b"LEDGERAI-SUSPICIOUS": (ScanOutcome.SUSPICIOUS, "SUSPICIOUS_CONTENT"),
            b"LEDGERAI-SCANNER-UNAVAILABLE": (ScanOutcome.UNAVAILABLE, "SCAN_UNAVAILABLE"),
            b"LEDGERAI-SCANNER-ERROR": (ScanOutcome.ERROR, "SCAN_ERROR"),
            b"LEDGERAI-SCANNER-TIMEOUT": (ScanOutcome.TIMEOUT, "SCAN_TIMEOUT"),
        }
        for marker, (outcome, reason) in synthetic_outcomes.items():
            if marker in content:
                return ScanResult(outcome, "deterministic", "1", "test", reason)
        return ScanResult(ScanOutcome.CLEAN, "deterministic", "1", "test", "CLEAN")
