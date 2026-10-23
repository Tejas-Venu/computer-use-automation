
from app.artifacts.schema import CapabilityArtifact


def detect_business_outcome(
    page_text: str,
    artifact: CapabilityArtifact,
) -> str | None:
    """
    Detect expected business outcomes declared
    in the capability artifact.
    """

    for outcome_name, config in artifact.expected_outcomes.items():
        if config.get("type") != "business_outcome":
            continue

        message = config.get("message")

        if message and message.casefold() in page_text.casefold():
            return outcome_name

    return None
