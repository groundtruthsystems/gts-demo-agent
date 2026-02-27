import json
import logging
import os
import sys
import asyncio
from datetime import datetime

from demo.agents.common import ProgressEvent
from demo.agents.echo import EchoWorkflow
from demo.agents.err import ErrorWorkflow

from demo.common.event_manager import EventManager, AnalyticsEvent
from demo.common.input import Input
from demo.common.config import Config
from demo.common.logger import setup_logger

from llama_index.core.workflow import Context

from openinference.instrumentation.llama_index import LlamaIndexInstrumentor

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



    correlation = input_data["arguments"]["correlation"]

    EventManager.push(AnalyticsEvent.new(correlation, "AGENT_STARTING"))

    team = input_data["arguments"]["team"]
    workflow = None

    if team == "echo":
        workflow = EchoWorkflow(config_data)
    elif team == "error":
        workflow = ErrorWorkflow(config_data)

    if workflow:
        _input = Input(input_data=input_data)
        _context = Context(workflow=workflow)
        await _context.store.set('correlation', input_data["arguments"]["correlation"])
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

        LlamaIndexInstrumentor().instrument()

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