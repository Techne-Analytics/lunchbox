import logging

from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from lunchbox.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(engine=None) -> None:
    """Configure OpenTelemetry traces. No-op if OTLP endpoint not set.

    Call at module level before app creation. Metrics removed for serverless
    (Grafana derives metrics from traces).
    """
    if not settings.otel_exporter_otlp_endpoint:
        logger.info("OTLP endpoint not configured, telemetry disabled")
        return

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        resource = Resource.create(
            {
                "service.name": settings.otel_service_name,
                "host.name": "vercel-serverless",
            }
        )

        # Traces — SimpleSpanProcessor for serverless (synchronous export per span)
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(tracer_provider)

        # Auto-instrumentation (SQLAlchemy + HTTPX)
        if engine:
            SQLAlchemyInstrumentor().instrument(engine=engine)
        HTTPXClientInstrumentor().instrument()

        logger.info(
            "OpenTelemetry configured, exporting to %s",
            settings.otel_exporter_otlp_endpoint,
        )
    except Exception:
        logger.exception(
            "Failed to initialize OpenTelemetry — app will continue without tracing"
        )


def instrument_app(app) -> None:
    """Instrument FastAPI app. Call after app creation."""
    if not settings.otel_exporter_otlp_endpoint:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str = "lunchbox") -> trace.Tracer:
    return trace.get_tracer(name)
