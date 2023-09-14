from ..alarm_item import AlarmItem, AlarmSeverity
from ..alarm_tree_view import AlarmTreeViewWidget
import time
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

        # Add a dummy guidance entry
    indices = alarm_tree_view.tree_view.selectedIndexes()
    alarm_item = alarm_tree_view.treeModel.getItem(indices[0])
    alarm_item.guidance =[{"title":"Don't call anybody", "details": "Read the manual"}, {"title":"Call Somebody", "details": "bash run_display.sh"}]

    qtbot.addWidget(alarm_tree_view.context_menu)
    alarm_tree_view.tree_menu(QPoint())
    with qtbot.waitExposed(alarm_tree_view.context_menu):
        alarm_tree_view.context_menu.show()
    
    # Verify that guidance info is displayed correctly in the context menu
    assert (alarm_tree_view.guidance_menu.title() == "Guidance")
    for i in range(len(alarm_tree_view.guidance_menu.actions())):

        curr_guidance_title = alarm_tree_view.guidance_menu.actions()[i]
        curr_title = curr_guidance_title.iconText()
        # curr_guidance_title is a QAction, so need to first access its menu and then can access its sub-actions
        curr_details = curr_guidance_title.menu().actions()[0].iconText() # always only 1 sub-action here, for details of guidance entry

        assert (curr_title == alarm_item.guidance[i]["title"]) 
        assert (curr_details == alarm_item.guidance[i]["details"])

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
