
from app.artifacts.schema import (
    ActionStep,
    CapabilityArtifact,
    LocatorSpec,
    OutputSpec,
    ParameterSpec,
)


def test_capability_schema():
    artifact = CapabilityArtifact(
        capability_id="banking.get_savings_balance",
        capability_version="1.0.0",
        description="Retrieve a member's savings balance",
        target_app="mock-bank",
        inputs={
            "member_id": ParameterSpec(
                type="string",
                description="Member identifier",
            )
        },
        outputs={
            "savings_balance": OutputSpec(
                type="number",
                description="Savings account balance",
                source_step="extract_balance",
            )
        },
        steps=[
            ActionStep(
                step_id="enter_member_id",
                action="fill",
                target=LocatorSpec(
                    strategy="attribute",
                    tag="input",
                    attribute="name",
                    value="member_id",
                ),
                value="{{member_id}}",
            )
        ],
        success_condition={
            "type": "text_visible",
            "value": "Member Details",
        },
    )

    assert artifact.schema_version == "1.0"
    assert artifact.capability_id == "banking.get_savings_balance"
    assert artifact.steps[0].value == "{{member_id}}"

    print(artifact.model_dump_json(indent=2))
