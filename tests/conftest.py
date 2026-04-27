"""pytest configuration for the Watts Home test suite."""
from __future__ import annotations

from pathlib import Path

import pytest


def pytest_configure(config: object) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


# Point HA's config dir at the project root so it can find custom_components/.
@pytest.fixture(scope="session")
def hass_config_dir() -> str:
    return str(Path(__file__).parent.parent)
