"""
Agents package for sandbox.

Contains LlamaIndex workflow implementations:
- EchoWorkflow: Simple echo workflow for testing
- DashboardGenerationWorkflow: Generate HTML dashboards from JSON schemas
"""

from .echo import EchoWorkflow

__all__ = [
    'EchoWorkflow',
]
