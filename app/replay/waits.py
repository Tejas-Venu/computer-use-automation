
import asyncio
import time

from playwright.async_api import Page, Locator

from app.artifacts.schema import CapabilityArtifact
from app.replay.outcomes import detect_business_outcome


class BusinessOutcomeDetected(Exception):
    def __init__(self, outcome: str):
        self.outcome = outcome
        super().__init__(outcome)


class LocatorTimeoutError(Exception):
    pass


async def wait_for_control(
    page: Page,
    locator: Locator,
    artifact: CapabilityArtifact,
    timeout: float = 5.0,
) -> None:
    """
    Wait until exactly one visible matching control exists.

    Detect known business outcomes while waiting.
    Reject ambiguous locators rather than selecting
    an arbitrary matching element.
    """

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        page_text = await page.locator("body").inner_text()

        outcome = detect_business_outcome(
            page_text=page_text,
            artifact=artifact,
        )

        if outcome is not None:
            raise BusinessOutcomeDetected(outcome)

        count = await locator.count()

        if count > 1:
            raise RuntimeError(
                f"Ambiguous locator: {count} matches"
            )

        if count == 1 and await locator.is_visible():
            return

        await asyncio.sleep(0.1)

    raise LocatorTimeoutError(
        f"Control not available within {timeout} seconds"
    )
