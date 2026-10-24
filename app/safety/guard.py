
from urllib.parse import urljoin

from playwright.async_api import Page, Locator

from app.safety.policy import (
    PolicyViolation,
    SafetyPolicy,
)


class ActionGuard:
    """
    Validate browser actions before execution.

    This version is restricted to the mock banking app.
    """

    def __init__(self, policy: SafetyPolicy):
        self.policy = policy

    async def validate(
        self,
        page: Page,
        locator: Locator,
        action: str,
    ) -> None:
        # Validate the current page.
        self.policy.validate_url(page.url)

        # Validate the requested action.
        self.policy.validate_action(action)

        # Require exactly one target.
        count = await locator.count()

        if count != 1:
            raise PolicyViolation(
                "Action target must be unique"
            )

        element = locator

        tag = await element.evaluate(
            "el => el.tagName.toLowerCase()"
        )

        # Validate fill actions.
        if action == "fill":
            if tag not in ("input", "textarea"):
                raise PolicyViolation(
                    "Fill requires an editable control"
                )

            input_type = await element.get_attribute("type")

            if input_type in (
                "password",
                "hidden",
                "file",
            ):
                raise PolicyViolation(
                    "Sensitive input type is blocked"
                )

            if not await element.is_editable():
                raise PolicyViolation(
                    "Control is not editable"
                )

            return

        # Validate click actions.
        if action == "click":
            if tag not in ("button", "a"):
                raise PolicyViolation(
                    "Only buttons and links may be clicked"
                )

            label = (
                await element.get_attribute("aria-label")
                or await element.inner_text()
            ).strip()

            self.policy.validate_action(
                action="click",
                target_name=label,
            )

            # Check navigation destinations for links.
            if tag == "a":
                href = await element.get_attribute("href")

                if not href:
                    raise PolicyViolation(
                        "Link destination is missing"
                    )

                destination = urljoin(page.url, href)

                self.policy.validate_url(destination)

            # Restrict buttons to the known search form.
            if tag == "button":
                button_type = (
                    await element.get_attribute("type")
                    or "submit"
                ).lower()

                if button_type != "submit":
                    raise PolicyViolation(
                        "Unapproved button type"
                    )

                form_info = await element.evaluate("""
                    el => {
                        const form = el.closest("form");
                        if (!form) return null;

                        return {
                            action: form.getAttribute("action"),
                            method: form.getAttribute("method")
                        };
                    }
                """)

                if not form_info:
                    raise PolicyViolation(
                        "Button is not inside an approved form"
                    )

                destination = urljoin(
                    page.url,
                    form_info["action"] or page.url,
                )

                self.policy.validate_url(destination)

                if (
                    form_info["method"] or "get"
                ).lower() != "post":
                    raise PolicyViolation(
                        "Unexpected form method"
                    )

                if label != "Search" or (
                    destination !=
                    "http://mock-bank:8000/search"
                ):
                    raise PolicyViolation(
                        "Only member search submission is approved"
                    )

            return

        raise PolicyViolation(
            f"Unsupported browser action: {action}"
        )
