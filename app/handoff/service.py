
import asyncio
import logging
import re

from app.handoff.controller import SharedBrowserController
from app.handoff.intervention import InterventionManager
from app.handoff.session import BrowserSession, SessionState
from app.replay.engine import run_replay
from app.safety.navigation import install_navigation_guard
from app.safety.policy import SafetyPolicy
from app.surface.browser import BrowserSurface


logger = logging.getLogger(__name__)


class OperatorService:
    def __init__(self):
        self.surface = None
        self.session = None
        self.manager = None
        self.controller = None
        self.replay_task = None
        self.result = None

        self.policy = SafetyPolicy()
        self._start_lock = asyncio.Lock()

    async def start(
        self,
        member_id: str,
        demo_intervention: bool = False,
    ):
        if not re.fullmatch(r"[0-9]{1,20}", member_id):
            raise ValueError("Invalid member ID")

        async with self._start_lock:
            if self.replay_task and not self.replay_task.done():
                raise RuntimeError(
                    "An automation run is already active"
                )

            if self.surface is not None:
                await self.surface.close()
                self.surface = None

            self.session = None
            self.manager = None
            self.controller = None
            self.result = None

            surface = BrowserSurface()

            try:
                await surface.start()

                await install_navigation_guard(
                    surface.context,
                    self.policy,
                )

                await surface.navigate(
                    "http://mock-bank:8000"
                )

                session = BrowserSession(surface.page)
                manager = InterventionManager(session)

                controller = SharedBrowserController(
                    session=session,
                    policy=self.policy,
                )

            except Exception:
                await surface.close()
                raise

            self.surface = surface
            self.session = session
            self.manager = manager
            self.controller = controller

            logger.info(
                "Starting managed replay: demo=%s",
                demo_intervention,
            )

            self.replay_task = asyncio.create_task(
                self._execute(
                    member_id=member_id,
                    demo_intervention=demo_intervention,
                )
            )

            return self.session.snapshot()

    async def _execute(
        self,
        member_id: str,
        demo_intervention: bool,
    ):
        try:
            result = await run_replay(
                member_id=member_id,
                session=self.session,
                intervention_manager=self.manager,
                demo_intervention=demo_intervention,
            )

            self.result = result

            if result["status"] == "failure":
                await self.session.fail()

            elif result["status"] == "business_outcome":
                # A business outcome is a terminal run result.
                # The session is no longer executing actions.
                if self.session.state == SessionState.RUNNING:
                    await self.session.complete()

            return result

        except asyncio.CancelledError:
            if self.session is not None:
                await self.session.fail()
            raise

        except Exception:
            logger.exception(
                "Managed replay encountered an unexpected error"
            )

            self.result = {
                "status": "failure",
                "error": {
                    "type": "operator_service_error",
                    "message": "Automation execution failed",
                    "recoverable": False,
                },
            }

            if self.session is not None:
                await self.session.fail()

            return self.result

    def status(self):
        if self.session is None:
            return {
                "state": "idle",
                "result": None,
                "interventions": [],
            }

        interventions = [
            {
                "intervention_id": request.intervention_id,
                "step_id": request.step_id,
                "reason": request.reason,
                "status": request.status.value,
                "operator_id": request.operator_id,
            }
            for request in self.manager.list_requests()
        ]

        return {
            **self.session.snapshot(),
            "browser_url": self.session.page.url,
            "result": self.result,
            "interventions": interventions,
        }

    async def screenshot(self) -> bytes:
        if self.session is None:
            raise RuntimeError("No active session")

        return await self.session.page.screenshot(
            type="png",
            full_page=False,
        )

    async def stop(self):
        async with self._start_lock:
            if self.replay_task and not self.replay_task.done():
                self.replay_task.cancel()

                try:
                    await self.replay_task
                except asyncio.CancelledError:
                    pass

            if self.surface is not None:
                await self.surface.close()

            self.surface = None
            self.session = None
            self.manager = None
            self.controller = None
            self.replay_task = None
            self.result = None
