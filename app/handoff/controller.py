
import asyncio

from app.handoff.session import BrowserSession
from app.safety.guard import ActionGuard
from app.safety.policy import SafetyPolicy
from app.replay.locators import resolve_locator
from app.artifacts.schema import LocatorSpec


class SharedBrowserController:
    """
    Coordinates browser actions between automation
    and a human operator.

    Both use the same Playwright page.
    """

    def __init__(
        self,
        session: BrowserSession,
        policy: SafetyPolicy,
    ):
        self.session = session
        self.guard = ActionGuard(policy)
        self._action_lock = session.action_lock

    async def automation_action(
        self,
        action: str,
        target: LocatorSpec,
        value: str | None = None,
    ):
        async with self._action_lock:
            self.session.assert_automation_control()

            locator = resolve_locator(
                self.session.page,
                target,
            )

            await self.guard.validate(
                page=self.session.page,
                locator=locator,
                action=action,
            )

            if action == "fill":
                if value is None:
                    raise ValueError("Fill value is required")

                await locator.fill(value, timeout=5000)

            elif action == "click":
                await locator.click(timeout=5000)

            else:
                raise ValueError(
                    f"Unsupported action: {action}"
                )

    async def human_action(
        self,
        operator_id: str,
        action: str,
        target: LocatorSpec,
        value: str | None = None,
    ):
        async with self._action_lock:
            self.session.assert_human_control(
                operator_id
            )

            locator = resolve_locator(
                self.session.page,
                target,
            )

            await self.guard.validate(
                page=self.session.page,
                locator=locator,
                action=action,
            )

            if action == "fill":
                if value is None:
                    raise ValueError("Fill value is required")

                await locator.fill(value, timeout=5000)

            elif action == "click":
                await locator.click(timeout=5000)

            else:
                raise ValueError(
                    f"Unsupported action: {action}"
                )
