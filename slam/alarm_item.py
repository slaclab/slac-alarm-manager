from __future__ import annotations
from qtpy.QtCore import QObject


class AlarmItem(QObject):
    """
    An AlarmItem represents the alarm status of a PV, along with all associated data.

    Parameters
    ----------
    name : str
        The name of the PV this alarm is associated with.
    path : str
        The path to the alarm within its configured hierarchy. For example: Accelerator/Line 1/Voltage 2
    alarm_severity : str
        The current severity level of the alarm itself. May be higher than the PV if latching is enabled.
    alarm_status : str
        The current status of the alarm itself.
    alarm_time : datetime
        The date and time this alarm was raised.
    alarm_value : str
        The current value of this alarm
    pv_severity : str
        The current severity level of the PV this alarm is associated with.
    pv_status : str
        The current status of the PV this alarm is associated with.
    description : str
        Additional description of this alarm specified by an end-user in a configuration file
    guidance : str
        Any guidance on how to handle this alarm that would be helpful to a user viewing this alarm.
    displays : str
        Any displays this alarm is associated with
    commands : str
        Any commands that should be run in response to this alarm
    enabled : object
        Whether or not this alarm is enabled. A bool in the simple case, a str here will also mean
        disabled, with the str being the date-time it should automatically re-enable.
    delay : int
        The amount of time in seconds a PV must be in an alarm state before raising the alarm
        If not set, alarm is raised immediately.
    alarm_filter : str
        An expression that allows an alarm to enable based on a different PV
    """
    def __init__(self, name, path=None, alarm_severity=None, alarm_status=None, alarm_time=None,
                 alarm_value=None, pv_severity=None, pv_status=None, description=None,
                 guidance=None, displays=None, commands=None, enabled=True, latching=False, annunciating=False,
                 delay=None, alarm_filter=None):
        super().__init__()
        self.name = name
        self.path = path
        self.child_items = []
        self.parent_item = None
        self.alarm_severity = alarm_severity
        self.alarm_status = alarm_status
        self.alarm_time = alarm_time
        self.alarm_value = alarm_value
        self.pv_severity = pv_severity
        self.pv_status = pv_status
        self.description = description
        self.guidance = guidance
        self.displays = displays
        self.commands = commands
        if enabled is None:  # Protect against setting it explicitly to None
            enabled = True
        if latching is None:
            latching = False
        if annunciating is None:
            annunciating = False
        self.enabled = enabled
        self.latching = latching
        self.annunciating = annunciating
        self.delay = delay
        self.alarm_filter = alarm_filter

    def is_leaf(self) -> bool:
        """ Return whether or not this alarm is associated with a leaf node in its configured hierarchy """
        return len(self.child_items) == 0

    def is_enabled(self) -> bool:
        """ A convenience method for checking the enabled state of the alarm """
        if type(self.enabled) is bool:
            return self.enabled
        elif type(self.enabled) is str:
            if self.enabled:
                return False  # A non-empty string means a bypass until date has been set, so it is disabled
            else:
                return True
        else:
            print('ERROR: Enabled status for alarm: {self.path} is set to a bad value: {self.enabled}')

    def append_child(self, item: AlarmItem) -> None:
        """ Add the input item as a child node for this alarm item """
        self.child_items.append(item)

    def assign_parent(self, parent: AlarmItem) -> None:
        """ Sets the input item as the parent of this alarm item """
        self.parent_item = parent

    def child(self, row: int) -> AlarmItem:
        """ Returns the child item at the input row, or None if nothing exists there """
        if row < 0 or row >= len(self.child_items):
            return None
        return self.child_items[row]

    def child_count(self) -> int:
        """ Return the number of children this item has """
        return len(self.child_items)

    def row(self) -> int:
        """ Return the row of this item relative to its parent, or zero if it has no parent """
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0

    def column_count(self) -> int:
        """ Return the column count of this item """
        return 1

    def parent_item(self) -> AlarmItem:
        """ Return the parent of this item, or None if one doesn't exist """
        return self.parent_item

    def __str__(self) -> str:
        return f'PV: {self.name} Alarm Severity: {self.alarm_severity} Alarm States: {self.alarm_status} ' \
               f'Alarm Time: {self.alarm_time} Alarm Value: {self.alarm_value} PV Severity: {self.pv_severity} ' \
               f'PV Status: {self.pv_status} Guidance: {self.guidance} Displays: {self.displays} Commands: {self.commands}' \
               f'Enabled: {self.enabled}'
