# Role 1 Phase 1 — bounded invoice vertical slice

The Phase 1 path uses the existing `role1.document-extraction.v1` shape as directed. The checkout has no Role 6 gateway implementation or document-store service, so `pipeline.py` defines narrow `DocumentStore` and `InvoiceModel` protocols for later binding. It does not modify the versioned shared schema.

## Provisional extraction contract

Version: `role1.document-extraction.v1` (schema uses JSON Schema Draft 2020-12).

The extraction includes document metadata, correlation ID, status, classification, model/pipeline version strings, named field observations, and line items. Classification supports `invoice`, `receipt`, `bank_statement`, `credit_note`, `purchase_order`, and `unknown`. Field states are `observed`, `missing`, `uncertain`, `conflicting`, and `human_corrected`; human corrections retain actor/time metadata. Missing values are null with `source: none` and a note. Conflicts keep a null selected value and at least two separately grounded candidates. Monetary field values and line-item unit/line totals use decimal strings plus ISO-like three-uppercase-letter currency codes; floats are rejected. Critical fields and line items need page/region provenance. Identifiers, metadata names, status names, provenance locators, and error shape remain subject to Role 4 review.

`process_invoice` retrieves by `(tenant_id, document_id)`, reads at most 20 MiB, verifies the immutable SHA-256 reference, and converts PDF/PNG/JPEG/TIFF pages in memory. Limits are 20 pages, 20 million pixels per page, and 60 million pixels per document. PDF conversion uses PyMuPDF; image conversion uses Pillow. The adapter receives converted page bytes and correlation ID. Document text is treated only as data. There is no model implementation in this repository: tests inject a deterministic fake adapter and do not measure extraction quality.

Invoice output covers vendor name, GSTIN, invoice number/date, currency, taxable amount, CGST, SGST, IGST, tax, total, and purchase-order reference. Missing fields remain `missing`; confidence below the conservative 0.90 review threshold becomes `uncertain`; either condition yields `review_required`. Unknown classification also yields `review_required`. Model output is checked for shape, provenance, confidence, and decimal-string money, then against both the JSON Schema and Python semantic validator. Processing errors return a failure envelope with a retriable flag and redacted messages. Conversion uses memory buffers; no source bytes are rewritten or persisted by Role 1.

## Validation behavior

The JSON Schema and `validate_extraction` enforce the same representable structure/status constraints: status-specific failure/unsupported members; success field states; explicit missing/conflicting/human-corrected semantics; candidate shape and count; known provenance sources; locator/quote/note types; critical locators; monetary strings/currencies; classification, line items, and model metadata. Monetary fields (`subtotal`, `tax`, `total`) and item amounts reference the shared `$defs.money` schema.

Intentional Python-only semantic checks:

- Any locator `page` (including field, conflict candidate, classification, and line-item provenance) must not exceed `document.page_count`. JSON Schema can require a positive integer but cannot compare two instance properties portably.
- `review_required` must contain at least one field in `missing`, `uncertain`, or `conflicting` state. Standard JSON Schema cannot express an existential condition over arbitrary object values cleanly; the schema therefore validates each field while Python enforces the cross-field condition.

## Evaluation pack

`fixtures/evaluation-v1.json` contains 13 synthetic cases: clean, nominal rotated-scan and multi-page examples, ambiguous conflict, unsupported, failure, all six classifications, itemized/table values, and reprocessing version metadata. These are fixtures for contract behavior only; they do not measure OCR, classification accuracy, rotation handling, page rendering, or model performance.

## Phase 1 checks

Install the declared dependencies in an isolated environment, then run the suite from the workspace root:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r role1\requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s role1\tests -v
.\.venv\Scripts\python.exe -c 'import sys; from importlib.metadata import version; from jsonschema import Draft202012Validator; print(sys.version); print(version("jsonschema")); print(Draft202012Validator.META_SCHEMA["$schema"])'
```

The suite covers existing Phase 0 schema parity and Phase 1 PDF/PNG, tenant forwarding, missing values, unknown classification, low confidence, unsupported media, malformed input, hash mismatch, and invalid model output. These are implementation checks with synthetic documents and a fake model, not model-quality evidence. `role1/check-fixtures.ps1` remains a JSON parsing and fixture-coverage smoke check only.

## Phase 1 gate evidence and limits

The source path, format conversion, immutable hash check, adapter call, and contract validation are implemented and covered by tests. The Role 6 gateway and production tenant document store are not present, so binding and real-service behavior remain outside this checkout. No OCR/VLM quality, accuracy, compliance, or performance claim is made. The 0.90 confidence cutoff is a conservative review policy for this slice, not a measured calibration result.

## Phase 2 — confidence, provenance, and deterministic validation

The invoice normalizer requires classification confidence and page/region provenance for every observed field. Missing values remain null with `missing` state and `source: none`; low confidence, noncanonical/invalid dates, invalid GSTIN format, and arithmetic or currency inconsistencies remain explicitly reviewable as `uncertain`, with the original model value retained and an explanation in provenance. A strict `conflicting` model response accepts 2–10 independently located candidates, selects no value, and requires review. Malformed candidates, absent provenance, invalid confidence, and malformed model fields return terminal `INVALID_MODEL_OUTPUT` failures. Monetary arithmetic uses `Decimal` and an expanded local precision context; it never rewrites source amounts.

The existing v1 contract can represent conflict candidates and a null field confidence, but it cannot carry a separate confidence on each candidate. The normalizer validates each candidate confidence and emits null for the conflict field confidence rather than combining candidate scores. Role 4 review is needed before adding candidate-level confidence to the shared schema. The schema remains unchanged in this phase.

Phase 2 checks are in `tests/test_role1_pipeline.py` (missing provenance rejection, low-confidence review, distinct conflict candidates, retained values and totals/currency warnings, deterministic date/GSTIN warnings) and `tests/test_role1_contract.py` (candidate provenance and contract rejection). Python suite execution is required for the Phase 2 exit gate; the fixture PowerShell script is only a JSON/coverage smoke check.

## Phase 3 — async Role 4 adapter seam and failure handling

`async_service.py` is the Role 1-owned async boundary. `ProcessingRequest` is an internal normalized context object. `role4_adapter.py` provides `Role4RequestAdapter` with an injected `ApprovedRequestMapper`; the Role 4 binding maps its approved request into tenant ID, document ID, request ID, correlation ID, extraction ID, expected contract version, immutable document hash, media type, and page count. The service rejects a version mismatch and enforces identifier, page (20), active request (128), concurrency (4 by default), retry (3 attempts maximum), and timeout (120 seconds by default) bounds. The underlying document reader still enforces the 20 MiB limit. No Role 4 table access is used.

`EventPublisher` is a Role 1 protocol seam, not a replacement for the approved Role 4 event contract. Its binding must map `publish_result` to that contract and pass the required idempotency key to a receiver that deduplicates it. Operational metadata contains hashed tenant/request/correlation tags, bounded duration, attempt count, status, and failure code; raw IDs, extracted values, document text, and exception text are not logged. Every processor result is checked against both `validate_extraction` and the versioned JSON Schema, then checked against the input tenant/document/hash/media/page/correlation/extraction context before publication.

Same-process retries with the same `(tenant_id, request_id)` and same request fingerprint coalesce while active and reuse completed results. Reusing the key with different input is a terminal `IDEMPOTENCY_KEY_REUSED` failure. Retriable failures can be resubmitted with the same request key. The event idempotency key is `role1:<full tenant SHA-256>:<full request SHA-256>:<full result SHA-256>`: repeated delivery of one result deduplicates, while a changed retry result (such as transient failure followed by success) remains deliverable. The transport receiver must deduplicate by this key. This in-memory request cache is bounded and is not durable across process restart. A Role 4 durable request store/outbox or equivalent remains necessary for crash-safe idempotency and delivery. No exactly-once guarantee is claimed.

Each active job receives a unique tenant-tagged temporary directory; source bytes and converted pages remain in memory and are not copied there. The directory is removed when the job exits. POSIX hosts set mode `0700`; Windows inherits the host temporary directory ACL. A production Windows host must provision an appropriately restricted temporary root before storing any tenant data there. The synchronous extraction pipeline runs in a worker thread. A timeout returns terminal `PROCESSING_TIMEOUT` because Python cannot safely cancel that worker thread; terminal classification prevents a retry from starting a duplicate extraction under the same key. Other transient failures are retried with bounded backoff. The Role 6 adapter should enforce network/model timeouts itself. Reclassifying sync-worker timeouts as retriable requires a cancellable async gateway/processor contract.

The checkout does not contain Role 4's approved request or event schema, so the seam is not yet bound to the production interfaces. No shared contract was edited. Role 4 review is requested to confirm request field mapping, event envelope/ack semantics, durable idempotency key scope, and whether it can deduplicate the supplied key. Phase 3 local checks are in `tests/test_role1_async.py`; run all checks with `python -m unittest discover -s role1\\tests -v`. These fake-adapter tests verify same-process coalescing, tenant separation, configured concurrency and retry bounds, failure classification, context validation, and redaction, but do not establish cross-process behavior or production Role 4 integration.
