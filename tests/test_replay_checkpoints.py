
import pytest

from app.artifacts.schema import (
    CheckpointSpec,
    LocatorSpec,
)
from app.replay.checkpoints import (
    CheckpointFailed,
    verify_checkpoint,
)
from app.surface.browser import BrowserSurface


@pytest.mark.asyncio
async def test_input_value_checkpoint():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        locator = surface.page.locator(
            'input[name="member_id"]'
        )

        await locator.fill("12345")

        checkpoint = CheckpointSpec(
            type="input_value",
            expected="{{member_id}}",
            target=LocatorSpec(
                strategy="attribute",
                tag="input",
                attribute="name",
                value="member_id",
            ),
        )

        await verify_checkpoint(
            page=surface.page,
            checkpoint=checkpoint,
            inputs={"member_id": "12345"},
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_url_checkpoint():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        await surface.page.locator(
            'input[name="member_id"]'
        ).fill("12345")

        await surface.page.get_by_role(
            "button",
            name="Search",
        ).click()

        checkpoint = CheckpointSpec(
            type="url_path",
            expected="/search",
        )

        await verify_checkpoint(
            page=surface.page,
            checkpoint=checkpoint,
        )

    finally:
        await surface.close()


@pytest.mark.asyncio
async def test_failed_checkpoint():
    surface = BrowserSurface()

    try:
        await surface.start()
        await surface.navigate("http://mock-bank:8000")

        checkpoint = CheckpointSpec(
            type="text_visible",
            expected="This text does not exist",
        )

        with pytest.raises(CheckpointFailed):
            await verify_checkpoint(
                page=surface.page,
                checkpoint=checkpoint,
                timeout_ms=500,
            )

    finally:
        await surface.close()
