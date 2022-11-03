from ..alarm_item import AlarmItem, AlarmSeverity
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush
import pytest


def test_is_leaf():
    """ Check that an alarm item with no children is considered a leaf """
    alarm_root = AlarmItem('PV:GROUP')
    assert alarm_root.is_leaf()

    child_node = AlarmItem('TEST:PV')
    alarm_root.append_child(child_node)

    assert not alarm_root.is_leaf()


@pytest.mark.parametrize('alarm_severity, expected_state',
                         [(AlarmSeverity.MINOR, True),
                          (AlarmSeverity.MAJOR, True),
                          (AlarmSeverity.INVALID, True),
                          (AlarmSeverity.UNDEFINED, True),
                          (AlarmSeverity.MINOR_ACK, False),
                          (AlarmSeverity.MAJOR_ACK, False),
                          (AlarmSeverity.INVALID_ACK, False),
                          (AlarmSeverity.UNDEFINED_ACK, False)])
def test_is_in_activate_alarm_state(alarm_severity, expected_state):
    """ Confirm that the alarm item correctly reports whether or not it is in an active alarm state """
    alarm_item = AlarmItem('TEST:PV')
    alarm_item.alarm_severity = alarm_severity
    assert alarm_item.is_in_active_alarm_state() == expected_state


def test_is_enabled():
    """ Verify the various methods of indicating an alarm item is enabled work properly """
    alarm_item = AlarmItem('TEST:PV')
    assert alarm_item.is_enabled()  # Should be set to True by default

    alarm_item.enabled = False
    assert not alarm_item.is_enabled()

    alarm_item.enabled = '06/03/2022 15:00:00'  # Simulate a bypass until date
    assert not alarm_item.is_enabled()


def test_assign_parent():
    """ Confirm that assigning a parent to an alarm item happens properly """
    alarm_item = AlarmItem('TEST:PV')
    parent_item = AlarmItem('GROUP:NAME')

    alarm_item.assign_parent(parent_item)
    assert alarm_item.parent_item == parent_item


def test_child():
    """ Check that returning an item's children by index works as expected """
    alarm_item = AlarmItem('TEST:PV')
    child_one = AlarmItem('CHILD:PV:ONE')
    child_two = AlarmItem('CHILD:PV:TWO')

    assert alarm_item.child_count() == 0
    alarm_item.append_child(child_one)
    assert alarm_item.child_count() == 1
    alarm_item.append_child(child_two)
    assert alarm_item.child_count() == 2

    assert alarm_item.child(0).name == 'CHILD:PV:ONE'
    assert alarm_item.child(1).name == 'CHILD:PV:TWO'
    assert alarm_item.child(2) is None


@pytest.mark.parametrize('enabled, severity, expected_color',
                         [(False, AlarmSeverity.MAJOR, QBrush(Qt.gray)),
                          (True, AlarmSeverity.OK, QBrush(Qt.darkGreen)),
                          (True, AlarmSeverity.UNDEFINED, QBrush(Qt.magenta)),
                          (True, AlarmSeverity.MAJOR, QBrush(Qt.red)),
                          (True, AlarmSeverity.MINOR, QBrush(Qt.darkYellow)),
                          (True, AlarmSeverity.MAJOR_ACK, QBrush(Qt.darkRed)),
                          (True, AlarmSeverity.MINOR_ACK, QBrush(Qt.darkGray)),
                          (True, AlarmSeverity.UNDEFINED_ACK, QBrush(Qt.darkMagenta)),
                          (True, AlarmSeverity.INVALID, QBrush(Qt.magenta)),
                          (True, AlarmSeverity.INVALID_ACK, QBrush(Qt.darkMagenta))])
def test_display_color(enabled, severity, expected_color):
    """ Verify that the color the alarm is to be drawn in is returned correctly """
    alarm_item = AlarmItem('TEST:PV')
    alarm_item.enabled = enabled
    alarm_item.alarm_severity = severity
    assert alarm_item.display_color(severity) == expected_color
