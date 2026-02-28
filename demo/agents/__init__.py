"""
Agents package for sandbox.

Contains LlamaIndex workflow implementations:
- EchoWorkflow: Simple echo workflow for testing
- DashboardGenerationWorkflow: Generate HTML dashboards from JSON schemas
"""

from .echo import EchoWorkflow
from .err import ErrorWorkflow
from .eventing import EventingWorkflow

__all__ = [
    'EchoWorkflow',
    'ErrorWorkflow',
    'EventingWorkflow',
]
