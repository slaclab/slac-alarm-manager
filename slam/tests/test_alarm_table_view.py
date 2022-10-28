from ..alarm_item import AlarmItem, AlarmSeverity
from ..alarm_table_view import AlarmTableType, AlarmTableViewWidget
from qtpy.QtCore import QEvent, QItemSelectionModel, QModelIndex
from qtpy.QtWidgets import QTableView
import pytest


@pytest.fixture(scope='function')
def active_alarm_table_view(tree_model, mock_kafka_producer):
    """ Return an empty alarm table view for testing """
    return AlarmTableViewWidget(tree_model, mock_kafka_producer, 'TEST_TOPIC', AlarmTableType.ACTIVE, lambda x: x)

@pytest.fixture(scope='function')
def acknowledged_alarm_table_view(tree_model, mock_kafka_producer):
    """ Return an empty alarm table view for testing """
    return AlarmTableViewWidget(tree_model, mock_kafka_producer, 'TEST_TOPIC', AlarmTableType.ACKNOWLEDGED, lambda x: x)


def test_create_and_show(qtbot, active_alarm_table_view):
    """ A simple check that the alarm table view will init and show without any errors """
    qtbot.addWidget(active_alarm_table_view)
    with qtbot.waitExposed(active_alarm_table_view):
        active_alarm_table_view.show()


def test_update_counter_label(alarm_item, active_alarm_table_view, acknowledged_alarm_table_view):
    """ Verify alarm item counts are updated accurately """
    # Add one active alarm and update the counts. Should be 1 for active and 0 for acknowledged
    active_alarm_table_view.alarmModel.append(alarm_item)
    active_alarm_table_view.update_counter_label()
    assert active_alarm_table_view.alarm_count_label.text() == 'Active Alarms: 1'

    # Now add an acknowledged alarm. Counts should now be 1 for both
    acknowledged_alarm_table_view.alarmModel.append(alarm_item)
    assert acknowledged_alarm_table_view.alarm_count_label.text() == 'Acknowledged Alarms: 1'


def test_context_menu_create_and_show(qtbot, active_alarm_table_view):
    """ Quick check to confirm that both context menus on this view init and show without any errors """
    qtbot.addWidget(active_alarm_table_view)
    active_alarm_table_view.alarm_context_menu_event(ev=QEvent(QEvent.Type.ContextMenu))
    with qtbot.waitExposed(active_alarm_table_view.alarm_context_menu):
        active_alarm_table_view.alarm_context_menu.show()


def test_send_acknowledgement(qtbot, monkeypatch, active_alarm_table_view, mock_kafka_producer):
    """ Test that when a user acknowledges an alarm, the message send to kafka is as expected """
    qtbot.addWidget(active_alarm_table_view)
    # Create an alarm with a severity of major
    alarm_item = AlarmItem('TEST:PV', path='/path/to/TEST:PV', alarm_severity=AlarmSeverity.MAJOR)
    active_alarm_table_view.alarmModel.append(alarm_item)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(QItemSelectionModel, 'selectedRows', lambda x: indices)
    monkeypatch.setattr(model_index, 'row', lambda: 0)

    # Send the acknowledgement, and verify the message we are sending to kafka looks the way we want it to
    active_alarm_table_view.send_acknowledgement()
    # Setting the correct topic, path, and acknowledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == 'TEST_TOPICCommand'
    assert mock_kafka_producer.key == 'command:/path/to/TEST:PV'
    assert 'command' in mock_kafka_producer.values
    assert mock_kafka_producer.values['command'] == 'acknowledge'


def test_send_unacknowledgement(qtbot, monkeypatch, acknowledged_alarm_table_view, mock_kafka_producer):
    """ Similar to the send acknowledgment test, except we now deal with the unacknowledge action and table """
    qtbot.addWidget(acknowledged_alarm_table_view)
    # Create an alarm that has been acknowledged
    alarm_item = AlarmItem('TEST:PV', path='/path/to/TEST:PV', alarm_severity=AlarmSeverity.MAJOR_ACK)
    acknowledged_alarm_table_view.alarmModel.append(alarm_item)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(QItemSelectionModel, 'selectedRows', lambda x: indices)
    monkeypatch.setattr(model_index, 'row', lambda: 0)

    # Send the unacknowledgement, and verify the message we are sending to kafka looks the way we want it to
    acknowledged_alarm_table_view.send_unacknowledgement()
    # Setting the correct topic, path, and acknoledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == 'TEST_TOPICCommand'
    assert mock_kafka_producer.key == 'command:/path/to/TEST:PV'
    assert 'command' in mock_kafka_producer.values
    assert mock_kafka_producer.values['command'] == 'unacknowledge'
