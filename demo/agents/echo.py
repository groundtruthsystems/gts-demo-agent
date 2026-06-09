import asyncio
import logging

from llama_index.core.workflow import Workflow, Context, StartEvent, StopEvent, step

from demo.common.event_manager import EventManager, AnalyticsEvent
from demo.common.logger import setup_logger


# Set up logger
logger = setup_logger(__name__, level=logging.DEBUG)

class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    def __init__(self, config_data, **kwargs):
        super().__init__(**kwargs)
        self.config_data = config_data

    @step()
    async def sample(self, ctx: Context, ev: StartEvent) -> StopEvent:
        logger.debug("Enter sample")
        await asyncio.sleep(40)
        EventManager.push(AnalyticsEvent.new("", "AGENT_CONFIG", self.config_data.config_data))
        return StopEvent(result="Pong")

