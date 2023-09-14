from ..alarm_item import AlarmItem, AlarmSeverity
from ..alarm_tree_view import AlarmTreeViewWidget
from qtpy.QtCore import QModelIndex, QPoint
from qtpy.QtWidgets import QTreeView
import pytest


@pytest.fixture(scope="function")
def alarm_tree_view(mock_kafka_producer):
    """Return an empty alarm tree view for testing"""
    return AlarmTreeViewWidget(mock_kafka_producer, "TEST_TOPIC", lambda x: x)


def test_create_and_show(qtbot, alarm_tree_view):
    """A simple check that the alarm tree view will init and show without any errors"""
    qtbot.addWidget(alarm_tree_view)
    with qtbot.waitExposed(alarm_tree_view):
        alarm_tree_view.show()


def test_tree_menu(qtbot, monkeypatch, alarm_tree_view):
    """Verify that the right click context menu is created and displayed without errors"""
    qtbot.addWidget(alarm_tree_view)
    alarm_tree_view.show()

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    leaf_item = AlarmItem("PV:NAME", "/path/to/PV:NAME", AlarmSeverity.OK)
    monkeypatch.setattr(QTreeView, "selectedIndexes", lambda x: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, "getItem", lambda x: leaf_item)

    qtbot.addWidget(alarm_tree_view.context_menu)
    alarm_tree_view.tree_menu(QPoint())
    with qtbot.waitExposed(alarm_tree_view.context_menu):
        alarm_tree_view.context_menu.show()

    # Check that creating a menu from a non-leaf node works too
    parent_item = AlarmItem("PV:GROUP:NAME", "/path/to/PV:GROUP:NAME", AlarmSeverity.OK)
    parent_item.append_child(leaf_item)
    monkeypatch.setattr(alarm_tree_view.treeModel, "getItem", lambda x: parent_item)

    alarm_tree_view.tree_menu(QPoint())
    with qtbot.waitExposed(alarm_tree_view.context_menu):
        alarm_tree_view.context_menu.show()


@pytest.mark.parametrize("acknowledged", [False, True])
def test_acknowledge_action(qtbot, monkeypatch, alarm_tree_view, mock_kafka_producer, acknowledged):
    """Test that when a user acks or un-acks an alarm from the tree, the message sent to kafka is correct"""
    qtbot.addWidget(alarm_tree_view)
    # Create an alarm with an acknowledged state opposite to what we want to set
    if acknowledged:
        alarm_item = AlarmItem("TEST:PV", path="/path/to/TEST:PV", alarm_severity=AlarmSeverity.MAJOR)
    else:
        alarm_item = AlarmItem("TEST:PV", path="/path/to/TEST:PV", alarm_severity=AlarmSeverity.MAJOR_ACK)

    # Monkeypatch some qt methods to return our alarm as the selected index
    model_index = QModelIndex()
    indices = [model_index]
    monkeypatch.setattr(alarm_tree_view.tree_view, "selectedIndexes", lambda: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, "getItem", lambda x: alarm_item)
    alarm_tree_view.treeModel.added_paths["TEST:PV"] = ["/path/to/TEST:PV"]

    alarm_tree_view.send_action(acknowledged=acknowledged)
    # Setting the correct topic, path, and acknowledgement command is all we need to acknowledge an alarm
    assert mock_kafka_producer.topic == "TEST_TOPICCommand"
    assert mock_kafka_producer.key == "command:/path/to/TEST:PV"
    assert "command" in mock_kafka_producer.values
    if acknowledged:
        assert mock_kafka_producer.values["command"] == "acknowledge"
    else:
        assert mock_kafka_producer.values["command"] == "unacknowledge"


@pytest.mark.parametrize("enabled", [False, True])
def test_enable_disable_action(qtbot, monkeypatch, alarm_item, alarm_tree_view, mock_kafka_producer, enabled):
    """Test that when a user enables or disables an alarm from the tree, the message sent to kafka is correct"""
    qtbot.addWidget(alarm_tree_view)
    model_index = QModelIndex()
    indices = [model_index]
    alarm_item.description = "Test Alarm"
    alarm_item.enabled = not enabled  # Set it to the opposite of the action we want to take
    monkeypatch.setattr(alarm_tree_view.tree_view, "selectedIndexes", lambda: indices)
    monkeypatch.setattr(alarm_tree_view.treeModel, "getItem", lambda x: alarm_item)
    alarm_tree_view.treeModel.added_paths["TEST:PV:ONE"] = ["/ROOT/SECTOR_ONE/TEST:PV:ONE"]

    alarm_tree_view.send_action(enabled=enabled)
    assert mock_kafka_producer.topic == "TEST_TOPIC"
    assert mock_kafka_producer.key == "config:/ROOT/SECTOR_ONE/TEST:PV:ONE"
    assert mock_kafka_producer.values["description"] == "Test Alarm"
    assert mock_kafka_producer.values["enabled"] == enabled
    assert not mock_kafka_producer.values["latching"]
