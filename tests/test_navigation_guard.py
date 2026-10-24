
import pytest

from app.safety.navigation import install_navigation_guard
from app.safety.policy import SafetyPolicy
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_allowed_navigation():
    surface = BrowserSurface()

    try:
        await surface.start()

        await install_navigation_guard(
            surface.context,
            SafetyPolicy(),
        )

        await surface.navigate(
            "http://mock-bank:8000/"
        )

        assert "Bank Administration" in (
            await surface.page.title()
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_external_navigation_blocked():
    surface = BrowserSurface()

    try:
        await surface.start()

        await install_navigation_guard(
            surface.context,
            SafetyPolicy(),
        )

        with pytest.raises(Exception):
            await surface.navigate(
                "https://example.com/"
            )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_unapproved_route_blocked():
    surface = BrowserSurface()

    try:
        await surface.start()

        await install_navigation_guard(
            surface.context,
            SafetyPolicy(),
        )

        with pytest.raises(Exception):
            await surface.navigate(
                "http://mock-bank:8000/admin/delete"
            )

    finally:
        await surface.close()
