import logging

from typing import Optional

from llama_index.core.workflow import Event

from sandbox.common.logger import setup_logger

logger = setup_logger(__name__, level=logging.DEBUG)

class ProgressEvent(Event):
    correlation_id: Optional[str] = None
    data: dict = {}
