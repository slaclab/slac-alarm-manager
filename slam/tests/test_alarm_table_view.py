from ..alarm_item import AlarmItem, AlarmSeverity
from ..alarm_table_view import AlarmTableViewWidget
from qtpy.QtCore import QEvent, QModelIndex
from qtpy.QtWidgets import QTableView
import pytest


@pytest.fixture(scope='function')
def alarm_table_view(tree_model, mock_kafka_producer):
    """ Return an empty alarm table view for testing """
    return AlarmTableViewWidget(tree_model, mock_kafka_producer, 'TEST_TOPIC', lambda x: x)


def test_create_and_show(qtbot, alarm_table_view):
    """ A simple check that the alarm table view will init and show without any errors """
    qtbot.addWidget(alarm_table_view)
    with qtbot.waitExposed(alarm_table_view):
        alarm_table_view.show()


def test_update_counter_label(alarm_item, alarm_table_view):
    """ Verify alarm item counts are updated accurately """
    # Add one active alarm and update the counts. Should be 1 for active and 0 for acknowledged
    alarm_table_view.alarmModel.append(alarm_item)
    alarm_table_view.update_counter_label()
    assert alarm_table_view.active_alarms_label.text() == 'Active Alarms: 1'
    assert alarm_table_view.acknowledged_alarms_label.text() == 'Acknowledged Alarms: 0'

    # Now add an acknowledged alarm. Counts should now be 1 for both
    alarm_table_view.acknowledgedAlarmsModel.append(alarm_item)
    assert alarm_table_view.active_alarms_label.text() == 'Active Alarms: 1'
    assert alarm_table_view.acknowledged_alarms_label.text() == 'Acknowledged Alarms: 1'


def test_context_menu_create_and_show(qtbot, alarm_table_view):
    """ Quick check to confirm that both context menus on this view init and show without any errors """
    qtbot.addWidget(alarm_table_view)
    alarm_table_view.active_alarm_context_menu_event(ev=QEvent(QEvent.Type.ContextMenu))
    with qtbot.waitExposed(alarm_table_view.active_context_menu):
        alarm_table_view.active_context_menu.show()

    alarm_table_view.acknowledged_alarm_context_menu_event(ev=QEvent(QEvent.Type.ContextMenu))
    with qtbot.waitExposed(alarm_table_view.acknowledged_context_menu):
        alarm_table_view.acknowledged_context_menu.show()


def test_send_acknowledgement(qtbot, monkeypatch, alarm_table_view, mock_kafka_producer):
    """ Test that when a user acknowledges an alarm, the message send to kafka is as expected """
    qtbot.addWidget(alarm_table_view)
    # Create an alarm with a severity of major
    alarm_item = AlarmItem('TEST:PV', path='/path/to/TEST:PV', alarm_severity=AlarmSeverity.MAJOR)
    alarm_table_view.alarmModel.append(alarm_item)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(QTableView, 'selectedIndexes', lambda x: indices)
    monkeypatch.setattr(model_index, 'row', lambda: 0)

    # Send the acknowledgement, and verify the message we are sending to kafka looks the way we want it to
    alarm_table_view.send_acknowledgement()
    # Setting the correct topic, path, and acknoledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == 'TEST_TOPICCommand'
    assert mock_kafka_producer.key == 'command:/path/to/TEST:PV'
    assert 'command' in mock_kafka_producer.values
    assert mock_kafka_producer.values['command'] == 'acknowledge'


def test_send_unacknowledgement(qtbot, monkeypatch, alarm_table_view, mock_kafka_producer):
    """ Similar to the send acknowledgment test, except we now deal with the unacknowledge action and table """
    qtbot.addWidget(alarm_table_view)
    # Create an alarm that has been acknowledged
    alarm_item = AlarmItem('TEST:PV', path='/path/to/TEST:PV', alarm_severity=AlarmSeverity.MAJOR_ACK)
    alarm_table_view.acknowledgedAlarmsModel.append(alarm_item)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(QTableView, 'selectedIndexes', lambda x: indices)
    monkeypatch.setattr(model_index, 'row', lambda: 0)

    # Send the unacknowledgement, and verify the message we are sending to kafka looks the way we want it to
    alarm_table_view.send_unacknowledgement()
    # Setting the correct topic, path, and acknoledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == 'TEST_TOPICCommand'
    assert mock_kafka_producer.key == 'command:/path/to/TEST:PV'
    assert 'command' in mock_kafka_producer.values
    assert mock_kafka_producer.values['command'] == 'unacknowledge'


def test_update_tables(qtbot, alarm_table_view):
    """ Test the various updates that can happen to the alarm table view """
    qtbot.addWidget(alarm_table_view)

    # First let's add both an active and an acknowledge alarm so we have some test data to work with
    active_alarm = AlarmItem('ACTIVE:ALARM', path='/path/to/ACTIVE:ALARM', alarm_severity=AlarmSeverity.MAJOR)
    acknowledged_alarm = AlarmItem('ACK:ALARM', path='/path/to/ACK:ALARM', alarm_severity=AlarmSeverity.MINOR_ACK)
    alarm_table_view.alarmModel.append(active_alarm)
    alarm_table_view.acknowledgedAlarmsModel.append(acknowledged_alarm)

    # Start with sending a "disabled" update for the active alarm. This means the user has disabled this
    # alarm and it should no longer be monitored.
    alarm_table_view.update_tables('ACTIVE:ALARM', '', AlarmSeverity.MAJOR, 'Disabled',
                                   None, '', AlarmSeverity.MAJOR, '')
    assert len(alarm_table_view.alarmModel.alarm_items) == 0  # Remove as expected
    assert len(alarm_table_view.acknowledgedAlarmsModel.alarm_items) == 1  # Unaffected

    # Now put it back, and simulate a user acknowledging the alarm
    alarm_table_view.alarmModel.append(active_alarm)
    # The MAJOR_ACK indicates an acknowledgment action
    alarm_table_view.update_tables('ACTIVE:ALARM', '', AlarmSeverity.MAJOR_ACK, '', None, '', AlarmSeverity.MAJOR, '')
    assert len(alarm_table_view.alarmModel.alarm_items) == 0  # Again the active alarm was removed
    assert len(alarm_table_view.acknowledgedAlarmsModel.alarm_items) == 2  # But this time added to acknowledged alarms

    # Now simulate the alarm returning to an OK state, this should clear the alarm since it is both acknowledged and OK
    alarm_table_view.update_tables('ACTIVE:ALARM', '', AlarmSeverity.OK, '', None, '', AlarmSeverity.OK, '')
    assert len(alarm_table_view.alarmModel.alarm_items) == 0  # This should not have changed
    assert len(alarm_table_view.acknowledgedAlarmsModel.alarm_items) == 1  # But this should have cleared one alarm now

    # And finally update the severity of the acknowledged alarm. This change of state will set it back to being active
    alarm_table_view.update_tables('ACK:ALARM', '', AlarmSeverity.MAJOR, '', None, '', AlarmSeverity.MAJOR, '')
    assert len(alarm_table_view.alarmModel.alarm_items) == 1  # This alarm is now activate again
    assert len(alarm_table_view.acknowledgedAlarmsModel.alarm_items) == 0  # And it was moved out of this table
