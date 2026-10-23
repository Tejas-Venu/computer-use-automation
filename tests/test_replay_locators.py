
import pytest

from app.artifacts.schema import LocatorSpec
from app.replay.locators import resolve_locator
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_attribute_locator():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        spec = LocatorSpec(
            strategy="attribute",
            tag="input",
            attribute="name",
            value="member_id",
        )

        locator = resolve_locator(surface.page, spec)

        assert await locator.count() == 1
        assert await locator.is_visible()

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_role_locator():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        spec = LocatorSpec(
            strategy="role",
            role="button",
            name="Search",
        )

        locator = resolve_locator(surface.page, spec)

        assert await locator.count() == 1
        assert await locator.is_visible()

    finally:
        await surface.close()
