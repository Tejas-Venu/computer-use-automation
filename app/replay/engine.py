
import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.artifacts.schema import CapabilityArtifact
from app.discovery.completion import verify_savings_balance
from app.handoff.controller import SharedBrowserController
from app.handoff.intervention import InterventionManager
from app.handoff.session import (
    BrowserSession,
    SessionOwnershipError,
)
from app.replay.checkpoints import CheckpointFailed, verify_checkpoint
from app.replay.evidence import ReplayEvidence
from app.replay.locators import resolve_locator
from app.replay.outcomes import detect_business_outcome
from app.replay.waits import (
    BusinessOutcomeDetected,
    LocatorTimeoutError,
    wait_for_control,
)
from app.safety.navigation import install_navigation_guard
from app.safety.policy import PolicyViolation, SafetyPolicy
from app.surface.browser import BrowserSurface


ARTIFACT_PATH = "artifacts/banking.get_savings_balance.v1.json"
TARGET_URL = "http://mock-bank:8000"
INTERVENTION_TIMEOUT = 120.0


def load_artifact(path: str) -> CapabilityArtifact:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return CapabilityArtifact.model_validate(data)


def resolve_value(template: str, inputs: dict) -> str:
    match = re.fullmatch(r"\{\{(\w+)\}\}", template)

    if not match:
        raise ValueError("Unsupported parameter template")

    parameter = match.group(1)

    if parameter not in inputs:
        raise ValueError(f"Missing parameter: {parameter}")

    return str(inputs[parameter])


async def run_replay(
    member_id: str,
    artifact_path: str = ARTIFACT_PATH,
    session: BrowserSession | None = None,
    intervention_manager: InterventionManager | None = None,
    intervention_timeout: float = INTERVENTION_TIMEOUT,
    demo_intervention: bool = False,
) -> dict:
    """
    Deterministic capability replay.

    Standalone:
        Owns and closes its browser.

    Managed:
        Uses an existing Playwright page.
        Supports human intervention.

    Demo:
        Pauses before Search.
        Operator clicks Search.
        Replay verifies the checkpoint and continues.
    """

    if not re.fullmatch(r"[0-9]{1,20}", member_id):
        raise ValueError("Invalid member ID")

    artifact = load_artifact(artifact_path)

    if artifact.capability_id != "banking.get_savings_balance":
        raise ValueError("Unexpected capability ID")

    if (session is None) != (intervention_manager is None):
        raise ValueError(
            "Managed replay requires session and intervention manager"
        )

    managed = session is not None

    if demo_intervention and not managed:
        raise ValueError(
            "Demo intervention requires managed replay"
        )

    if managed:
        if intervention_manager.session is not session:
            raise ValueError("Intervention manager mismatch")

        session.assert_automation_control()

        surface = None
        page = session.page
        context = page.context
    else:
        surface = BrowserSurface()
        page = None
        context = None

    inputs = {"member_id": member_id}
    policy = SafetyPolicy()
    evidence = ReplayEvidence()

    current_step = None
    browser_session = None

    evidence.record(
        event_type="replay_started",
        details={
            "capability_id": artifact.capability_id,
            "capability_version": artifact.capability_version,
            "managed": managed,
            "demo_intervention": demo_intervention,
        },
    )

    async def finish_business_outcome(outcome: str) -> dict:
        result = {
            "status": "business_outcome",
            "capability_id": artifact.capability_id,
            "outcome": outcome,
            "outputs": {},
        }

        evidence.record(
            event_type="business_outcome",
            step=current_step,
            details={"outcome": outcome},
        )

        evidence.save(result)

        if managed:
            await session.complete()

        return result

    async def finish_failure(
        error_type: str,
        recoverable: bool = False,
    ) -> dict:
        result = {
            "status": "failure",
            "capability_id": artifact.capability_id,
            "step": current_step,
            "error": {
                "type": error_type,
                "message": "Replay execution failed",
                "recoverable": recoverable,
            },
        }

        evidence.record(
            event_type="step_failed",
            step=current_step,
            details={
                "error_type": error_type,
                "recoverable": recoverable,
            },
        )

        if page is not None:
            try:
                await evidence.capture_failure(page)

                evidence.record(
                    event_type="failure_screenshot_saved",
                    step=current_step,
                )
            except Exception:
                evidence.record(
                    event_type="screenshot_unavailable",
                    step=current_step,
                )

        evidence.save(result)

        if managed:
            await session.fail()

        return result

    async def request_human_intervention(reason: str) -> None:
        if not managed:
            raise RuntimeError(
                "Human handoff requires managed replay"
            )

        request = await intervention_manager.create(
            capability_id=artifact.capability_id,
            step_id=current_step,
            reason=reason,
        )

        evidence.record(
            event_type="intervention_requested",
            step=current_step,
            details={
                "intervention_id": request.intervention_id,
                "reason_category": reason,
            },
        )

        try:
            await asyncio.wait_for(
                session.wait_for_resume(),
                timeout=intervention_timeout,
            )
        except asyncio.TimeoutError:
            evidence.record(
                event_type="intervention_timeout",
                step=current_step,
            )
            raise

        await session.resume_automation()
        policy.validate_url(page.url)

        evidence.record(
            event_type="automation_resumed",
            step=current_step,
        )

    async def checkpoint_passed(step, timeout_ms=1000) -> bool:
        if step.checkpoint is None:
            return False

        try:
            await verify_checkpoint(
                page=page,
                checkpoint=step.checkpoint,
                inputs=inputs,
                timeout_ms=timeout_ms,
            )
            return True
        except CheckpointFailed:
            return False

    try:
        if not managed:
            await surface.start()

            page = surface.page
            context = surface.context

            await install_navigation_guard(context, policy)

            policy.validate_url(TARGET_URL)
            await surface.navigate(TARGET_URL)

        else:
            policy.validate_url(page.url)

            await install_navigation_guard(
                context,
                policy,
            )

        browser_session = (
            session if managed else BrowserSession(page)
        )

        controller = SharedBrowserController(
            session=browser_session,
            policy=policy,
        )

        for step in artifact.steps:
            current_step = step.step_id
            browser_session.current_step = current_step

            print(f"Executing: {current_step}", flush=True)

            evidence.record(
                event_type="step_started",
                step=current_step,
                details={"action": step.action},
            )

            intervention_attempted = False
            operator_action_required = False

            # Demo mode: pause BEFORE clicking Search.
            if (
                demo_intervention
                and current_step == "submit_search"
            ):
                intervention_attempted = True
                operator_action_required = True

                print(
                    "[DEMO] Waiting for operator at submit_search",
                    flush=True,
                )

                try:
                    await request_human_intervention(
                        "demo_manual_search_required"
                    )
                except asyncio.TimeoutError:
                    return await finish_failure(
                        "intervention_timeout"
                    )

            while True:
                try:
                    browser_session.assert_automation_control()
                    policy.validate_url(page.url)

                    # If human already completed Search,
                    # verify checkpoint and skip duplicate click.
                    if (
                        intervention_attempted
                        and current_step == "submit_search"
                        and step.checkpoint is not None
                    ):
                        if await checkpoint_passed(step):
                            evidence.record(
                                event_type="step_completed_by_operator",
                                step=current_step,
                                details={
                                    "checkpoint": "passed",
                                },
                            )
                            break

                        if operator_action_required:
                            return await finish_failure(
                                "operator_action_incomplete"
                            )

                    page_text = await page.locator(
                        "body"
                    ).inner_text()

                    outcome = detect_business_outcome(
                        page_text=page_text,
                        artifact=artifact,
                    )

                    if outcome is not None:
                        return await finish_business_outcome(
                            outcome
                        )

                    if step.action in ("fill", "click"):
                        if step.target is None:
                            raise ValueError(
                                "Missing step locator"
                            )

                        locator = resolve_locator(
                            page,
                            step.target,
                        )

                        await wait_for_control(
                            page=page,
                            locator=locator,
                            artifact=artifact,
                            timeout=5.0,
                        )

                        value = None

                        if step.action == "fill":
                            if step.value is None:
                                raise ValueError(
                                    "Missing fill value"
                                )

                            value = resolve_value(
                                step.value,
                                inputs,
                            )

                        await controller.automation_action(
                            action=step.action,
                            target=step.target,
                            value=value,
                        )

                        if step.checkpoint is not None:
                            await verify_checkpoint(
                                page=page,
                                checkpoint=step.checkpoint,
                                inputs=inputs,
                                timeout_ms=5000,
                            )

                        evidence.record(
                            event_type="step_completed",
                            step=current_step,
                            details={
                                "action": step.action,
                                "checkpoint": (
                                    "passed"
                                    if step.checkpoint is not None
                                    else "not_configured"
                                ),
                            },
                        )

                        break

                    elif step.action == "extract":
                        if step.extraction is None:
                            raise ValueError(
                                "Missing extraction specification"
                            )

                        page_text = await page.locator(
                            "body"
                        ).inner_text()

                        match = re.search(
                            step.extraction.pattern,
                            page_text,
                        )

                        if match is None:
                            raise RuntimeError(
                                "Savings balance extraction failed"
                            )

                        extracted_balance = (
                            match.group(
                                step.extraction.group
                            ).replace(",", "")
                        )

                        outputs = verify_savings_balance(
                            page_text=page_text,
                            member_id=member_id,
                        )

                        if outputs is None:
                            raise RuntimeError(
                                "Member or balance verification failed"
                            )

                        if (
                            outputs["savings_balance"]
                            != extracted_balance
                        ):
                            raise RuntimeError(
                                "Balance verification mismatch"
                            )

                        evidence.record(
                            event_type="step_completed",
                            step=current_step,
                            details={
                                "action": "extract",
                                "checkpoint": "passed",
                            },
                        )

                        result = {
                            "status": "success",
                            "capability_id": artifact.capability_id,
                            "outputs": outputs,
                        }

                        evidence.record(
                            event_type="replay_completed",
                            step=current_step,
                            details={"status": "success"},
                        )

                        evidence.save(result)

                        if managed:
                            await session.complete()

                        return result

                    else:
                        raise ValueError(
                            f"Unsupported action: {step.action}"
                        )

                except BusinessOutcomeDetected as exc:
                    return await finish_business_outcome(
                        exc.outcome
                    )

                except PolicyViolation:
                    return await finish_failure(
                        "policy_violation"
                    )

                except (
                    LocatorTimeoutError,
                    CheckpointFailed,
                    PlaywrightTimeoutError,
                ) as exc:
                    if isinstance(exc, LocatorTimeoutError):
                        error_type = "locator_timeout"
                    elif isinstance(exc, CheckpointFailed):
                        error_type = "checkpoint_failed"
                    else:
                        error_type = "playwright_timeout"

                    if not managed or intervention_attempted:
                        return await finish_failure(
                            error_type,
                            recoverable=True,
                        )

                    intervention_attempted = True

                    try:
                        await request_human_intervention(
                            "recoverable_ui_failure"
                        )
                    except asyncio.TimeoutError:
                        return await finish_failure(
                            "intervention_timeout"
                        )

                    # Retry once after intervention.
                    continue

        return await finish_failure(
            "success_condition_not_met"
        )

    except PolicyViolation:
        return await finish_failure(
            "policy_violation"
        )

    except SessionOwnershipError:
        return await finish_failure(
            "session_ownership_error"
        )

    except Exception as exc:
        return await finish_failure(
            type(exc).__name__
        )

    finally:
        if surface is not None:
            await surface.close()


if __name__ == "__main__":
    member_id = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "12345"
    )

    result = asyncio.run(run_replay(member_id))

    print("\nREPLAY RESULT:")
    print(json.dumps(result, indent=2))
