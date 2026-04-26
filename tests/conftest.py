"""pytest configuration for the Watts Home test suite."""


def pytest_configure(config: object) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
