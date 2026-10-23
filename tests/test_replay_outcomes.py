
from app.artifacts.schema import CapabilityArtifact
from app.replay.engine import load_artifact
from app.replay.outcomes import detect_business_outcome


def test_member_not_found():
    artifact = load_artifact(
        "artifacts/banking.get_savings_balance.v1.json"
    )

    result = detect_business_outcome(
        "Bank Administration Portal\nMember not found",
        artifact,
    )

    assert result == "member_not_found"


def test_member_found():
    artifact = load_artifact(
        "artifacts/banking.get_savings_balance.v1.json"
    )

    result = detect_business_outcome(
        "Search Results\nMember: Alex Morgan\nOpen Details",
        artifact,
    )

    assert result is None


def test_unrelated_error():
    artifact = load_artifact(
        "artifacts/banking.get_savings_balance.v1.json"
    )

    result = detect_business_outcome(
        "Permission denied",
        artifact,
    )

    assert result is None
