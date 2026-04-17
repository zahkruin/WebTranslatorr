"""
Pytest configuration and fixtures.
"""

import pytest
from app.providers.registry import ProviderRegistry
from app.routing.smart_router import SmartRouter


@pytest.fixture
def empty_registry():
    """Returns an empty provider registry."""
    registry = ProviderRegistry()
    registry.clear()
    return registry


@pytest.fixture
def router(empty_registry):
    """Returns a smart router with empty registry."""
    return SmartRouter(empty_registry)
