"""Pytest configuration for tex2docx tests."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="module", params=("asyncio",))
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Limit AnyIO tests to the asyncio backend."""
    return request.param
