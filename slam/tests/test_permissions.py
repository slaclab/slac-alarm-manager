import pytest
from ..permissions import UserAction, UserPermission, can_take_action, set_user_permission


@pytest.mark.parametrize(
    "user_permission, user_action, expected_result",
    [
        (UserPermission.READ_ONLY, UserAction.ACKNOWLEDGE, False),
        (UserPermission.READ_ONLY, UserAction.ENABLE, False),
        (UserPermission.READ_ONLY, UserAction.UPDATE_CONFIG, False),
        (UserPermission.OPERATOR, UserAction.ACKNOWLEDGE, True),
        (UserPermission.OPERATOR, UserAction.ENABLE, False),
        (UserPermission.OPERATOR, UserAction.UPDATE_CONFIG, False),
        (UserPermission.ADMIN, UserAction.ACKNOWLEDGE, True),
        (UserPermission.ADMIN, UserAction.ENABLE, True),
        (UserPermission.ADMIN, UserAction.UPDATE_CONFIG, True),
    ],
)
def test_can_take_action(user_permission, user_action, expected_result):
    """A simple test for ensuring that all pairs of user action/user permission are handled properly"""
    set_user_permission(user_permission)
    action_allowed = can_take_action(user_action)
    assert action_allowed == expected_result
