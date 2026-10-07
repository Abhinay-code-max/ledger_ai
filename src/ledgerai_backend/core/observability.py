"""Low-cardinality OpenTelemetry instruments for backend and ingestion operations."""

from opentelemetry import metrics, trace

tracer = trace.get_tracer("ledgerai.backend")
meter = metrics.get_meter("ledgerai.backend")

upload_operations = meter.create_counter("ledgerai.upload.operations")
upload_bytes = meter.create_counter("ledgerai.upload.bytes")
scan_outcomes = meter.create_counter("ledgerai.scan.outcomes")
csv_rows = meter.create_counter("ledgerai.csv.rows")
import_duration = meter.create_histogram("ledgerai.import.duration", unit="s")
job_transitions = meter.create_counter("ledgerai.job.transitions")
job_duration = meter.create_histogram("ledgerai.job.duration", unit="s")
queue_dispatches = meter.create_counter("ledgerai.queue.dispatches")
outbox_publications = meter.create_counter("ledgerai.outbox.publications")
outbox_pending_age = meter.create_histogram("ledgerai.outbox.pending_age", unit="s")
publish_retries = meter.create_counter("ledgerai.outbox.publish_retries")
inbox_duplicates = meter.create_counter("ledgerai.inbox.duplicates")
dead_letters = meter.create_counter("ledgerai.dead_letters")
dependency_failures = meter.create_counter("ledgerai.dependency.failures")
