"""Reproducible benchmark harness for Role 6 model runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import statistics
import sys
from time import monotonic
from uuid import uuid4

from ledgerai_contracts.v1.model_runtime import (
    InferenceInput,
    ModelCapability,
    ModelInferenceRequest,
    SupportedInputType,
)
from ledgerai_contracts.v1.tenancy import EntityTenantContext
from ledgerai_role6.app import create_role6_app
from ledgerai_role6.config import Role6Settings


async def run_benchmark(
    *,
    requests_count: int = 50,
    warmup_count: int = 5,
    concurrency: int = 1,
) -> dict[str, object]:
    """Execute reproducible benchmarks and calculate real statistics."""
    settings = Role6Settings(
        active_backend="deterministic",
        environment="test",
    )
    app = create_role6_app(settings)
    backend = app.state.backend
    manifest = app.state.manifest

    await backend.initialize(manifest)

    tenant = EntityTenantContext(
        tenant_id=uuid4(),
        organization_id=uuid4(),
        legal_entity_id=uuid4(),
    )

    sample_doc = (
        "INVOICE NUMBER: INV-2026-BENCH-001\n"
        "SUPPLIER: Nova Benchmark Solutions\n"
        "TOTAL AMOUNT: USD 1250.00\n"
    )

    def make_req() -> ModelInferenceRequest:
        return ModelInferenceRequest(
            schema_version="1.0",
            tenant_context=tenant,
            operation_id=uuid4(),
            correlation_id=uuid4(),
            capability=ModelCapability.DOCUMENT_EXTRACTION,
            model_name=manifest.model_name,
            input_data=InferenceInput(
                media_type=SupportedInputType.TEXT,
                text_content=sample_doc,
                page_count=1,
            ),
        )

    # Warmup
    for _ in range(warmup_count):
        req = make_req()
        await backend.infer(req, manifest, warmup=True)

    latencies_ms: list[float] = []
    successes = 0
    failures = 0
    start_total = monotonic()

    semaphore = asyncio.Semaphore(concurrency)

    async def execute_one() -> None:
        nonlocal successes, failures
        async with semaphore:
            req = make_req()
            t0 = monotonic()
            try:
                _, meta = await backend.infer(req, manifest, warmup=False)
                t1 = monotonic()
                latencies_ms.append((t1 - t0) * 1000.0)
                successes += 1
            except Exception:
                failures += 1

    tasks = [asyncio.create_task(execute_one()) for _ in range(requests_count)]
    await asyncio.gather(*tasks)

    total_time_s = monotonic() - start_total
    throughput = round(requests_count / total_time_s, 2) if total_time_s > 0 else 0.0

    latencies_sorted = sorted(latencies_ms)
    p50 = round(statistics.median(latencies_sorted), 2) if latencies_sorted else 0.0
    p95_idx = int(0.95 * len(latencies_sorted))
    p95 = (
        round(latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)], 2)
        if latencies_sorted
        else 0.0
    )
    p99_idx = int(0.99 * len(latencies_sorted))
    p99 = (
        round(latencies_sorted[min(p99_idx, len(latencies_sorted) - 1)], 2)
        if latencies_sorted
        else 0.0
    )

    return {
        "benchmark_summary": {
            "backend_type": str(manifest.backend_type),
            "backend_label": "Deterministic Test Baseline",
            "model_name": manifest.model_name,
            "model_revision": manifest.immutable_revision,
            "preprocessing_revision": manifest.preprocessing_version,
            "device": backend.get_device(),
        },
        "execution_environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        },
        "metrics": {
            "total_requests": requests_count,
            "warmup_requests": warmup_count,
            "concurrency": concurrency,
            "success_count": successes,
            "failure_count": failures,
            "timeout_rate": 0.0,
            "total_duration_seconds": round(total_time_s, 4),
            "throughput_req_per_sec": throughput,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "latency_p99_ms": p99,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Role 6 Runtime Benchmark Harness")
    parser.add_argument("--requests", type=int, default=50, help="Number of measured requests")
    parser.add_argument("--warmup", type=int, default=5, help="Number of warmup requests")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrency level")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    if args.requests < 1 or args.warmup < 0 or args.concurrency < 1:
        print("Invalid benchmark arguments", file=sys.stderr)
        return 1

    results = asyncio.run(
        run_benchmark(
            requests_count=args.requests,
            warmup_count=args.warmup,
            concurrency=args.concurrency,
        )
    )

    rendered = json.dumps(results, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rendered + "\n")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
