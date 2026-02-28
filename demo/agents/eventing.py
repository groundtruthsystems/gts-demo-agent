import asyncio
import logging

from llama_index.core.workflow import Workflow, Context, StartEvent, StopEvent, step

from demo.common.logger import setup_logger


# Set up logger
logger = setup_logger(__name__, level=logging.DEBUG)

class EventingWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    def __init__(self, config_data, **kwargs):
        super().__init__(**kwargs)
        self.config_data = config_data

    @step()
    async def sample(self, ctx: Context, ev: StartEvent) -> StopEvent:
        EventManager.push(AnalyticsEvent.new(correlation, "SAMPLE_START"))
        await asyncio.sleep(40)
        EventManager.push(AnalyticsEvent.new(correlation, "SAMPLE_PROCESSING"))
        await asyncio.sleep(40)
        EventManager.push(AnalyticsEvent.new(correlation, "SAMPLE_GOING"))
        await asyncio.sleep(40)
        return StopEvent(result={"hello": "world"})

