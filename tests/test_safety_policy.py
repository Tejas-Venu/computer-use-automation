
import pytest

from app.safety.policy import (
    PolicyViolation,
    SafetyPolicy,
)


@pytest.fixture
def policy():
    return SafetyPolicy()


def test_allowed_homepage(policy):
    policy.validate_url(
        "http://mock-bank:8000/"
    )


def test_allowed_search(policy):
    policy.validate_url(
        "http://mock-bank:8000/search"
    )


def test_allowed_member_details(policy):
    policy.validate_url(
        "http://mock-bank:8000/members/12345"
    )


def test_external_domain_blocked(policy):
    with pytest.raises(PolicyViolation):
        policy.validate_url(
            "https://example.com"
        )


def test_unapproved_route_blocked(policy):
    with pytest.raises(PolicyViolation):
        policy.validate_url(
            "http://mock-bank:8000/admin/delete"
        )


def test_allowed_fill_action(policy):
    policy.validate_action("fill")


def test_transfer_blocked(policy):
    with pytest.raises(PolicyViolation):
        policy.validate_action(
            action="click",
            target_name="Transfer Funds",
        )


def test_delete_blocked(policy):
    with pytest.raises(PolicyViolation):
        policy.validate_action(
            action="click",
            target_name="Delete Account",
        )


def test_unknown_action_blocked(policy):
    with pytest.raises(PolicyViolation):
        policy.validate_action(
            action="execute_script"
        )
