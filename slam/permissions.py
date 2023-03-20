import enum
import logging
from functools import total_ordering

""" 
A file for dealing with permissions for actions that users are allowed to take. This file is intentionally
as simple as possible at the moment since there is currently no notion of individual user accounts for using this
application. Permissions are set on application startup.
"""

logger = logging.getLogger(__name__)


@total_ordering
class UserPermission(enum.Enum):
    """
    An enum for the values that an alarm severity can take on. Not inheriting from str so permission
    based comparisons can be done.
    """
    READ_ONLY = 'read-only'
    OPERATOR = 'operator'
    ADMIN = 'admin'

    def __lt__(self, other):
        """ The order in which they are defined is in order of increasing ability to take action """
        if self.__class__ is other.__class__:
            values = [e for e in UserPermission]
            return values.index(self) < values.index(other)
        return NotImplemented


class UserAction(enum.Enum):
    """ An enum for the actions available to the user """
    ACKNOWLEDGE = 'acknowledge'
    ENABLE = 'enable'
    UPDATE_CONFIG = 'update-config'


__user_permission = UserPermission.ADMIN


def can_take_action(action: UserAction, log_warning=False) -> bool:
    """ Return True if the user can take the input action, False otherwise """
    if action is UserAction.ACKNOWLEDGE and __user_permission == UserPermission.READ_ONLY:
        if log_warning:
            logger.warning(' Cannot take acknowledge action, permissions are currently set to read-only')
        return False
    elif action is UserAction.ENABLE and __user_permission < UserPermission.ADMIN:
        if log_warning:
            logger.warning(f' Cannot take enable/disable action, requires alarm admin permissions, '
                           f'currently set to {__user_permission.value}')
        return False
    elif action is UserAction.UPDATE_CONFIG and __user_permission < UserPermission.ADMIN:
        if log_warning:
            logger.warning(f' Cannot update config, requires alarm admin permissions, '
                           f'currently set to: {__user_permission.value}')
        return False
    return True


def set_user_permission(permission: UserPermission) -> None:
    """ Set the permission determining what the user is allowed to do """
    global __user_permission
    __user_permission = permission
