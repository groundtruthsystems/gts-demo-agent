import json
import logging
import os
import sys
import asyncio
import uuid
from datetime import datetime

from demo.agents.common import ProgressEvent
from demo.agents.echo import EchoWorkflow
from demo.agents.err import ErrorWorkflow
from demo.agents.eventing import EventingWorkflow

from demo.common.event_manager import EventManager, AnalyticsEvent
from demo.common.input import Input
from demo.common.config import Config
from demo.common.logger import setup_logger

from llama_index.core.workflow import Context

from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from langfuse import get_client

logger = setup_logger(__name__, level=logging.DEBUG)

async def process_data(config_data: Config, input_data):
    """
    Args:
        config_data (dict): The loaded JSON data from config file
        input_data (dict): The loaded JSON data from input file

    Returns:
        output_data
    """
    # Create a copy of the input data for the main output
    output_data = {
        "processed": True,
        "timestamp": datetime.now().isoformat()
    }



    correlation = input_data["arguments"].get("correlation", str(uuid.uuid4()))

    EventManager.push(AnalyticsEvent.new(correlation, "AGENT_STARTING"))

    team = input_data["arguments"]["team"]
    workflow = None

    if team == "echo":
        workflow = EchoWorkflow(config_data, timeout=120)
    elif team == "error":
        workflow = ErrorWorkflow(config_data)
    elif team == "event":
        workflow = EventingWorkflow(config_data, timeout=240)

    if workflow:
        _input = Input(input_data=input_data)
        _context = Context(workflow=workflow)
        await _context.store.set('correlation', correlation)
        await _context.store.set('request', input_data)

        handler = workflow.run(ctx=_context, correlation=correlation, input=_input)

        async for event in handler.stream_events():
            logger.debug("Got event: %s", event)
            if isinstance(event, ProgressEvent):
                progress_event: ProgressEvent = event
                EventManager.push(AnalyticsEvent.new(progress_event.correlation_id, 'PROGRESS', progress_event.data))

        output_data["response"] = await handler
    else:
        output_data["message"] = "No agent found"

    return output_data

async def main():
    # Define file paths
    config_file = os.environ.get("AGENT_CONFIG", "config.json")
    input_file = "input.json"
    output_file = "output.json"
    events_file = "events.json"

    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return

    try:
        # Read input JSON file
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        # Read input JSON file
        with open(config_file, 'r') as f:
            config_data = json.load(f)

        langfuse_config = config_data.get('observability', {}).get('langfuse', None)
        if langfuse_config is not None:
            os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_config.get('public_key')
            os.environ["LANGFUSE_SECRET_KEY"] = langfuse_config.get('secret_key')
            os.environ["LANGFUSE_BASE_URL"] = langfuse_config.get('host')

            langfuse = get_client()

        # Initialize LoggerProvider and OTLPLogExporter to publish logs to the collector
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        import atexit
        import base64
        import urllib.parse

        logger_provider = LoggerProvider()
        set_logger_provider(logger_provider)
        try:
            host = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("LANGFUSE_BASE_URL")
            headers = {}

            # Parse standard OTel headers if set
            otel_headers = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS")
            if otel_headers:
                for item in otel_headers.split(","):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        headers[k.strip()] = v.strip()

            # Add Basic Auth header if Langfuse credentials exist
            public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
            secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
            if public_key and secret_key and "Authorization" not in headers:
                auth_str = f"{public_key}:{secret_key}"
                auth_bytes = auth_str.encode('utf-8')
                auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
                headers["Authorization"] = f"Basic {auth_b64}"

            # Build OTLP logs endpoint URL
            endpoint = os.environ.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
            if not endpoint and host:
                if host.endswith("/api/public/otel/v1/logs"):
                    endpoint = host
                else:
                    # Langfuse OTLP logs signal endpoint. urljoin would drop any
                    # base path, so join explicitly against the configured host.
                    endpoint = host.rstrip("/") + "/api/public/otel/v1/logs"

            exporter_kwargs = {}
            if endpoint:
                exporter_kwargs["endpoint"] = endpoint
            if headers:
                exporter_kwargs["headers"] = headers

            exporter = OTLPLogExporter(**exporter_kwargs)
            logger_provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
            atexit.register(logger_provider.shutdown)
        except Exception as e:
            logger.warning("Failed to initialize OTLP log exporter: %s", e)

        LlamaIndexInstrumentor().instrument()
        # LoggingInstrumentor only injects trace/span IDs into log records for
        # correlation; it does NOT export logs. Attach a LoggingHandler bound to
        # our LoggerProvider so standard `logging` records are emitted over OTLP.
        LoggingInstrumentor().instrument()

        from opentelemetry.sdk._logs import LoggingHandler

        otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        logging.getLogger().addHandler(otel_handler)

        # Process the data
        output_data = await process_data(Config(config_data=config_data), input_data)

        # Write output JSON file
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=4)

        print(f"Successfully processed '{input_file}'.")
        print(f"Output written to '{output_file}'.")
        print(f"Events written to '{events_file}'.")

    except json.JSONDecodeError:
        print(f"Error: '{input_file}' is not a valid JSON file.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())