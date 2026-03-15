import logging

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from lunchbox.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app=None, engine=None) -> None:
    """Configure OpenTelemetry. No-op if OTLP endpoint not set."""
    if not settings.otel_exporter_otlp_endpoint:
        logger.info("OTLP endpoint not configured, telemetry disabled")
        return

    # Import OTLP exporters only when needed (they require grpc)
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter,
    )

    resource = Resource.create({"service.name": settings.otel_service_name})

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation
    if app:
        FastAPIInstrumentor.instrument_app(app)
    if engine:
        SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "OpenTelemetry configured, exporting to %s",
        settings.otel_exporter_otlp_endpoint,
    )


def get_tracer(name: str = "lunchbox") -> trace.Tracer:
    return trace.get_tracer(name)


def get_meter(name: str = "lunchbox") -> metrics.Meter:
    return metrics.get_meter(name)
