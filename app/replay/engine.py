
import asyncio
from email import policy
import json
import re
import sys
from app.safety.policy import PolicyViolation
from pathlib import Path
from app.safety.navigation import install_navigation_guard
from app.artifacts.schema import CapabilityArtifact
from app.discovery.completion import verify_savings_balance
from app.replay.checkpoints import verify_checkpoint
from app.replay.evidence import ReplayEvidence
from app.replay.locators import resolve_locator
from app.replay.outcomes import detect_business_outcome
from app.replay.waits import (
    BusinessOutcomeDetected,
    LocatorTimeoutError,
    wait_for_control,
)
from app.surface.browser import BrowserSurface
from app.safety.policy import SafetyPolicy
from app.safety.guard import ActionGuard


ARTIFACT_PATH = (
    "artifacts/banking.get_savings_balance.v1.json"
)

TARGET_URL = "http://mock-bank:8000"


def load_artifact(path: str) -> CapabilityArtifact:
    """
    Load and validate the saved capability artifact.
    """
    data = json.loads(
        Path(path).read_text(encoding="utf-8")
    )

    return CapabilityArtifact.model_validate(data)


def resolve_value(template: str, inputs: dict) -> str:
    """
    Replace a parameter placeholder with its
    corresponding runtime input.
    """
    match = re.fullmatch(
        r"\{\{(\w+)\}\}",
        template,
    )

    if not match:
        raise ValueError(
            "Unsupported parameter template"
        )

    parameter = match.group(1)

    if parameter not in inputs:
        raise ValueError(
            f"Missing parameter: {parameter}"
        )

    return str(inputs[parameter])


async def run_replay(
    member_id: str,
    artifact_path: str = ARTIFACT_PATH,
) -> dict:
    """
    Execute a saved banking capability without
    invoking an LLM.

    Results:
    - success
    - business_outcome
    - failure
    """

    if not re.fullmatch(r"[0-9]{1,20}", member_id):
        raise ValueError(
            "Invalid member ID. Expected 1-20 digits."
        )

    artifact = load_artifact(artifact_path)

    if artifact.capability_id != "banking.get_savings_balance":
        raise ValueError("Unexpected capability ID")

    inputs = {
        "member_id": member_id,
    }

    surface = BrowserSurface()
    current_step = None
    policy = SafetyPolicy()
    guard = ActionGuard(policy)
    # Create a unique evidence recorder for this run.
    evidence = ReplayEvidence()

    evidence.record(
        event_type="replay_started",
        details={
            "capability_id": artifact.capability_id,
            "capability_version": artifact.capability_version,
        },
    )

    def complete_business_outcome(outcome: str) -> dict:
        """
        Save and return a known business outcome.
        """
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

        return result

    async def complete_failure(
        error_type: str,
        recoverable: bool,
    ) -> dict:
        """
        Save sanitized failure evidence and
        capture a mock-app screenshot.
        """
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

        if surface.page is not None:
            try:
                await evidence.capture_failure(
                    surface.page
                )

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

        return result

    try:
        await surface.start()
        policy.validate_url(TARGET_URL)
        await install_navigation_guard(
            context=surface.context,
            policy=policy,
        )
        await surface.navigate(TARGET_URL)

        for step in artifact.steps:
            current_step = step.step_id

            print(f"Executing: {current_step}")

            evidence.record(
                event_type="step_started",
                step=current_step,
                details={
                    "action": step.action,
                },
            )

            # Inspect the current UI state.
            observation = await surface.observe()

            # Detect expected business outcomes before
            # attempting the next action.
            outcome = detect_business_outcome(
                page_text=observation["visible_text"],
                artifact=artifact,
            )

            if outcome is not None:
                return complete_business_outcome(outcome)

            # Execute interactive actions.
            if step.action in ("fill", "click"):

                if step.target is None:
                    raise ValueError(
                        f"Missing locator: {current_step}"
                    )

                locator = resolve_locator(
                    surface.page,
                    step.target,
                )

                # Wait for exactly one visible control.
                # Detect business outcomes during the wait.
                await wait_for_control(
                    page=surface.page,
                    locator=locator,
                    artifact=artifact,
                    timeout=5.0,
                )

                await guard.validate(
                    page=surface.page,
                    locator=locator,
                    action=step.action,
                )

                if step.action == "fill":

                    if step.value is None:
                        raise ValueError(
                            f"Missing fill value: {current_step}"
                        )

                    value = resolve_value(
                        template=step.value,
                        inputs=inputs,
                    )

                    await locator.fill(
                        value,
                        timeout=5000,
                    )

                elif step.action == "click":

                    await locator.click(
                        timeout=5000,
                    )

                # Verify the checkpoint after execution.
                if step.checkpoint is not None:
                    await verify_checkpoint(
                        page=surface.page,
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

            # Extract and verify requested information.
            elif step.action == "extract":

                if step.extraction is None:
                    raise ValueError(
                        "Missing extraction specification"
                    )

                page_text = await surface.page.locator(
                    "body"
                ).inner_text()

                outcome = detect_business_outcome(
                    page_text=page_text,
                    artifact=artifact,
                )

                if outcome is not None:
                    return complete_business_outcome(outcome)

                # Apply the extraction rule from the artifact.
                match = re.search(
                    step.extraction.pattern,
                    page_text,
                )

                if match is None:
                    raise RuntimeError(
                        "Savings balance extraction failed"
                    )

                extracted_balance = (
                    match.group(step.extraction.group)
                    .replace(",", "")
                )

                # Verify the balance belongs to the
                # requested member.
                outputs = verify_savings_balance(
                    page_text=page_text,
                    member_id=member_id,
                )

                if outputs is None:
                    raise RuntimeError(
                        "Member ID or balance verification failed"
                    )

                if (
                    outputs["savings_balance"]
                    != extracted_balance
                ):
                    raise RuntimeError(
                        "Extracted balance verification mismatch"
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
                    details={
                        "status": "success",
                    },
                )

                evidence.save(result)

                return result

            else:
                raise ValueError(
                    f"Unsupported action: {step.action}"
                )

        raise RuntimeError(
            "Replay ended without satisfying "
            "the success condition"
        )

    except PolicyViolation:
        return await complete_failure(
            error_type="policy_violation",
            recoverable=False,
        )

    except BusinessOutcomeDetected as exc:
        return complete_business_outcome(exc.outcome)

    except LocatorTimeoutError:
        return await complete_failure(
            error_type="locator_timeout",
            recoverable=True,
        )

    except Exception as exc:
        blocked_requests = getattr(
            surface.context,
            "_blocked_requests",
            [],
        ) if getattr(surface, "context", None) else []

        if blocked_requests:
            return await complete_failure(
                error_type="policy_violation",
                recoverable=False,
            )

        return await complete_failure(
            error_type=type(exc).__name__,
            recoverable=False,
        )

    finally:
        await surface.close()


if __name__ == "__main__":
    member_id = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "12345"
    )

    result = asyncio.run(
        run_replay(member_id)
    )

    print("\nREPLAY RESULT:")
    print(json.dumps(result, indent=2))
