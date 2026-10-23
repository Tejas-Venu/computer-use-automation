
from urllib.parse import urlparse
import re
from playwright.async_api import Page

from app.artifacts.schema import CheckpointSpec
from app.replay.locators import resolve_locator


class CheckpointFailed(Exception):
    pass


async def verify_checkpoint(
    page: Page,
    checkpoint: CheckpointSpec,
    inputs: dict[str, str] | None = None,
    timeout_ms: int = 5000,
) -> None:
    """
    Verify the expected UI state after an action.

    Raise CheckpointFailed if the expected state
    is not reached within the timeout.
    """

    inputs = inputs or {}

    expected = checkpoint.expected

    if expected is not None:
        for key, value in inputs.items():
            expected = expected.replace(
                "{{" + key + "}}",
                value,
            )

    try:
        if checkpoint.type == "url_path":
            from playwright.async_api import expect

            pattern = re.compile(
                rf"^https?://[^/?#]+{re.escape(expected)}(?:\?[^#]*)?(?:#.*)?$"
            )

            await expect(page).to_have_url(
                pattern,
                timeout=timeout_ms,
            )

        elif checkpoint.type == "text_visible":
            from playwright.async_api import expect

            await expect(
                page.get_by_text(
                    expected,
                    exact=False,
                ).first
            ).to_be_visible(
                timeout=timeout_ms,
            )

        elif checkpoint.type == "element_visible":
            from playwright.async_api import expect

            locator = resolve_locator(
                page,
                checkpoint.target,
            )

            await expect(locator).to_have_count(
                1,
                timeout=timeout_ms,
            )

            await expect(locator).to_be_visible(
                timeout=timeout_ms,
            )

        elif checkpoint.type == "input_value":
            from playwright.async_api import expect

            locator = resolve_locator(
                page,
                checkpoint.target,
            )

            await expect(locator).to_have_value(
                expected,
                timeout=timeout_ms,
            )

        else:
            raise CheckpointFailed(
                f"Unsupported checkpoint: {checkpoint.type}"
            )

    except Exception as exc:
        if isinstance(exc, CheckpointFailed):
            raise

        raise CheckpointFailed(
            f"Checkpoint {checkpoint.type} failed: {exc}"
        ) from exc
