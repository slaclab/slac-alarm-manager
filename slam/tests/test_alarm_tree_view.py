from ..alarm_item import AlarmItem, AlarmSeverity
from ..alarm_tree_view import AlarmTreeViewWidget
from qtpy.QtCore import QEvent, QModelIndex, QPoint
from qtpy.QtWidgets import QTableView
import pytest


@pytest.fixture(scope='function')
def alarm_tree_view(mock_kafka_producer):
    """ Return an empty alarm tree view for testing """
    return AlarmTreeViewWidget(mock_kafka_producer, 'TEST_TOPIC', lambda x: x)


def test_create_and_show(qtbot, alarm_tree_view):
    """ A simple check that the alarm tree view will init and show without any errors """
    qtbot.addWidget(alarm_tree_view)
    with qtbot.waitExposed(alarm_tree_view):
        alarm_tree_view.show()


def test_tree_menu(qtbot, monkeypatch, alarm_tree_view):
    """ Verify that the right click context menu is created and displayed without errors """
    qtbot.addWidget(alarm_tree_view)
    alarm_tree_view.show()

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    leaf_item = AlarmItem('PV:NAME', '/path/to/PV:NAME', AlarmSeverity.OK)
    monkeypatch.setattr(QTableView, 'selectedIndexes', lambda x: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, 'getItem', lambda x: leaf_item)

    alarm_tree_view.tree_menu(QPoint())

    # Check that creating a menu from a non-leaf node works too
    parent_item = AlarmItem('PV:GROUP:NAME', '/path/to/PV:GROUP:NAME', AlarmSeverity.OK)
    parent_item.append_child(leaf_item)
    monkeypatch.setattr(alarm_tree_view.treeModel, 'getItem', lambda x: parent_item)

    alarm_tree_view.tree_menu(QPoint())


def test_send_acknowledgement(qtbot, monkeypatch, alarm_tree_view, mock_kafka_producer):
    """ Test that when a user acknowledges an alarm from the tree, the message sent to kafka is correct """
    qtbot.addWidget(alarm_tree_view)
    # Create an alarm with a severity of major
    alarm_item = AlarmItem('TEST:PV', path='/path/to/TEST:PV', alarm_severity=AlarmSeverity.MAJOR)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(alarm_tree_view.tree_view, 'selectedIndexes', lambda: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, 'getItem', lambda x: alarm_item)

    alarm_tree_view.send_acknowledgement()
    # Setting the correct topic, path, and acknowledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == 'TEST_TOPICCommand'
    assert mock_kafka_producer.key == 'command:/path/to/TEST:PV'
    assert 'command' in mock_kafka_producer.values
    assert mock_kafka_producer.values['command'] == 'acknowledge'


def test_send_unacknowledgement(qtbot, monkeypatch, alarm_tree_view, mock_kafka_producer):
    """ Test than when a user unacknowledges an alarm from the tree, the message sent to kafka is correct """
    qtbot.addWidget(alarm_tree_view)
    # Create an alarm with a severity of major ack
    alarm_item = AlarmItem('TEST:PV', path='/path/to/TEST:PV', alarm_severity=AlarmSeverity.MAJOR_ACK)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(alarm_tree_view.tree_view, 'selectedIndexes', lambda: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, 'getItem', lambda x: alarm_item)

    alarm_tree_view.send_unacknowledgement()
    # Setting the correct topic, path, and acknowledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == 'TEST_TOPICCommand'
    assert mock_kafka_producer.key == 'command:/path/to/TEST:PV'
    assert 'command' in mock_kafka_producer.values
    assert mock_kafka_producer.values['command'] == 'unacknowledge'


def test_enable_alarm(qtbot, monkeypatch, alarm_item, alarm_tree_view, mock_kafka_producer):
    """ Test that when a user enables an alarm from the tree, the message sent to kafka is correct """
    qtbot.addWidget(alarm_tree_view)
    model_index = QModelIndex()
    indices = [model_index]
    alarm_item.description = 'Test Alarm'
    alarm_item.enabled = False  # Disable the alarm so we can enable it later
    monkeypatch.setattr(alarm_tree_view.tree_view, 'selectedIndexes', lambda: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, 'getItem', lambda x: alarm_item)

    alarm_tree_view.enable_alarm()
    assert mock_kafka_producer.topic == 'TEST_TOPIC'
    assert mock_kafka_producer.key == 'config:/ROOT/SECTOR_ONE/TEST:PV:ONE'
    assert mock_kafka_producer.values['description'] == 'Test Alarm'
    assert mock_kafka_producer.values['enabled']
    assert not mock_kafka_producer.values['latching']


def test_disable_alarm(qtbot, monkeypatch, alarm_item, alarm_tree_view, mock_kafka_producer):
    """ Test that when a user disables an alarm from the tree, the message sent to kafka is correct """
    qtbot.addWidget(alarm_tree_view)
    model_index = QModelIndex()
    indices = [model_index]
    alarm_item.description = 'Test Alarm'
    monkeypatch.setattr(alarm_tree_view.tree_view, 'selectedIndexes', lambda: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, 'getItem', lambda x: alarm_item)

    alarm_tree_view.disable_alarm()
    assert mock_kafka_producer.topic == 'TEST_TOPIC'
    assert mock_kafka_producer.key == 'config:/ROOT/SECTOR_ONE/TEST:PV:ONE'
    assert mock_kafka_producer.values['description'] == 'Test Alarm'
    assert not mock_kafka_producer.values['enabled']
    assert not mock_kafka_producer.values['latching']
