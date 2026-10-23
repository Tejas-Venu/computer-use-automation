
import json
from pathlib import Path
from app.artifacts.schema import CheckpointSpec
from app.artifacts.schema import (
    ActionStep,
    CapabilityArtifact,
    ExtractionSpec,
    LocatorSpec,
    OutputSpec,
    ParameterSpec,
)


def generate_capability(
    discovery_path: str,
    member_id: str,
    output_path: str,
) -> CapabilityArtifact:
    discovery = json.loads(
        Path(discovery_path).read_text()
    )

    if discovery.get("status") != "success":
        raise ValueError("Discovery must be successful")

    recorded_steps = discovery["steps"]

    expected_actions = [
        "fill",
        "click",
        "click",
        "extract",
    ]

    actual_actions = [
        step["action"]["action"]
        for step in recorded_steps
    ]

    if actual_actions != expected_actions:
        raise ValueError(
            f"Unexpected discovery sequence: {actual_actions}"
        )

    if discovery["outputs"]["member_id"] != member_id:
        raise ValueError("Discovery member ID mismatch")

    step_ids = [
        "enter_member_id",
        "submit_search",
        "open_details",
        "extract_balance",
    ]

    steps = []

    checkpoints = {
        "enter_member_id": CheckpointSpec(
            type="input_value",
            expected="{{member_id}}",
            target=LocatorSpec(
                strategy="attribute",
                tag="input",
                attribute="name",
                value="member_id",
            ),
        ),
        "submit_search": CheckpointSpec(
            type="url_path",
            expected="/search",
        ),
        "open_details": CheckpointSpec(
            type="text_visible",
            expected="Member Details",
        ),
    }

    for index, recorded in enumerate(recorded_steps):
        action_type = recorded["action"]["action"]

        if action_type in ("fill", "click"):
            locator_data = recorded.get("locator")

            if not locator_data:
                raise ValueError(
                    f"Missing locator at step {index + 1}"
                )

            target = LocatorSpec.model_validate(
                locator_data
            )

            value = None

            if action_type == "fill":
                recorded_value = recorded["action"]["value"]

                if recorded_value != member_id:
                    raise ValueError(
                        "Unexpected fill value"
                    )

                value = "{{member_id}}"

            steps.append(
                ActionStep(
                    step_id=step_ids[index],
                    action=action_type,
                    target=target,
                    value=value,
                    checkpoint=checkpoints.get(step_ids[index]),
                )
            )

        elif action_type == "extract":
            steps.append(
                ActionStep(
                    step_id=step_ids[index],
                    action="extract",
                    extraction=ExtractionSpec(
                        source="visible_text",
                        pattern=(
                            r"Savings Balance:\s*"
                            r"\$([\d,]+(?:\.\d{2})?)"
                        ),
                    ),
                )
            )

    artifact = CapabilityArtifact(
        capability_id="banking.get_savings_balance",
        capability_version="1.0.0",
        description=(
            "Look up a member and retrieve their "
            "current savings balance"
        ),
        target_app="mock-bank",
        inputs={
            "member_id": ParameterSpec(
                type="string",
                required=True,
                description="Member identifier",
            )
        },
        outputs={
            "member_id": OutputSpec(
                type="string",
                description="Verified member identifier",
            ),
            "savings_balance": OutputSpec(
                type="string",
                description="Savings balance in USD",
                source_step="extract_balance",
            ),
            "currency": OutputSpec(
                type="string",
                description="Currency code",
            ),
        },
        steps=steps,
        success_condition={
            "type": "member_balance_verified",
            "member_id_parameter": "member_id",
        },
        expected_outcomes={
            "member_not_found": {
                "type": "business_outcome",
                "message": "Member not found",
            }
        },
    )

    destination = Path(output_path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    destination.write_text(
        artifact.model_dump_json(indent=2)
    )

    return artifact


if __name__ == "__main__":
    artifact = generate_capability(
        discovery_path="evidence/discovery/run.json",
        member_id="12345",
        output_path=(
            "artifacts/"
            "banking.get_savings_balance.v1.json"
        ),
    )

    print("Capability generated successfully!")
    print("Capability:", artifact.capability_id)
    print("Version:", artifact.capability_version)
    print("Steps:", len(artifact.steps))
