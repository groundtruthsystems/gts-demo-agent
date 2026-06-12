import json
import logging
import os
import sys
import asyncio
import contextlib
import uuid
from datetime import datetime
from importlib.metadata import version

from demo.agents.common import ProgressEvent
from demo.agents.echo import EchoWorkflow
from demo.agents.err import ErrorWorkflow
from demo.agents.eventing import EventingWorkflow

from demo.common.event_manager import EventManager, AnalyticsEvent
from demo.common.input import Input
from demo.common.config import Config
from demo.common.logger import setup_logger
from demo.common.observability import OtelObservability

from llama_index.core.workflow import Context

logger = setup_logger(__name__, level=logging.DEBUG)

async def process_data(config_data: Config, input_data, tracer=None):
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

        # Open a root span around the run so the workflow's step tasks (which
        # copy the active context at creation) inherit it. Without an active
        # span here, logs emitted inside the steps get trace_id=0 and cannot be
        # correlated with the trace. OpenInference's step spans nest underneath.
        span_ctx = (
            tracer.start_as_current_span(f"agent.{team}")
            if tracer is not None else contextlib.nullcontext()
        )
        with span_ctx as span:
            if span is not None:
                span.set_attribute("agent.team", team)
                span.set_attribute("agent.correlation_id", correlation)

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

        team = input_data["arguments"]["team"]
        service_name = f"gts-{team}"
        os.environ.setdefault("OTEL_SERVICE_NAME", service_name)

        try:
            service_version = version('gts-demo-agent')
        except Exception:
            service_version = 'unknown-0'

        # OTLP logs+traces export and the Langfuse client, all authenticated via
        # the control_plane (Keycloak) client credentials when configured.
        observability = OtelObservability.from_config(
            config_data, service_name, service_version, logger=logger
        )
        tracer = observability.init()
        langfuse = observability.build_langfuse_client()

        # Process the data
        output_data = await process_data(Config(config_data=config_data), input_data, tracer=tracer)

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