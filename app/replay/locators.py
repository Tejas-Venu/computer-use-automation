
import json
import re

from playwright.async_api import Page, Locator

from app.artifacts.schema import LocatorSpec


def resolve_locator(
    page: Page,
    spec: LocatorSpec,
) -> Locator:
    """
    Convert a saved locator specification into
    a Playwright locator.
    """

    if spec.strategy == "attribute":
        if not re.fullmatch(
            r"[a-zA-Z][a-zA-Z0-9_-]*",
            spec.tag,
        ):
            raise ValueError("Invalid tag")

        if not re.fullmatch(
            r"[a-zA-Z_:][a-zA-Z0-9_:.-]*",
            spec.attribute,
        ):
            raise ValueError("Invalid attribute")

        quoted_value = json.dumps(spec.value)

        return page.locator(
            f"{spec.tag}[{spec.attribute}={quoted_value}]"
        )

    elif spec.strategy == "role":
        return page.get_by_role(
            spec.role,
            name=spec.name,
            exact=True,
        )

    elif spec.strategy == "text":
        return page.get_by_text(
            spec.value,
            exact=True,
        )

    elif spec.strategy == "css":
        return page.locator(spec.selector)

    else:
        raise ValueError(
            f"Unsupported locator strategy: {spec.strategy}"
        )
