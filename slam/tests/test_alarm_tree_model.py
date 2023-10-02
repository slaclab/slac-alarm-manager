from ..alarm_item import AlarmItem, AlarmSeverity
from operator import attrgetter
import sys
from io import StringIO


def test_clear(tree_model, alarm_item):
    """A quick check that clear is removing data as expected."""
    tree_model.nodes.append(alarm_item)
    tree_model.added_paths["node"] = ["/path/to/the/node"]
    tree_model.root_item = alarm_item

    tree_model.clear()

    assert len(tree_model.nodes) == 0
    assert len(tree_model.added_paths) == 0
    assert tree_model.root_item.name == ""


def test_column_count(tree_model, alarm_item):
    """Check that columnCount() returns the expected number"""
    assert tree_model.columnCount() == 1  # No multiple columns for a tree


def test_row_count(tree_model, alarm_item):
    """Check that rowCount() returns the correct number (the count of children for the tree case)"""
    tree_model.root_item.append_child(alarm_item)
    alarm_item_major = AlarmItem("ALARM:MAJOR", alarm_severity=AlarmSeverity.MAJOR)
    tree_model.root_item.append_child(alarm_item_major)
    assert tree_model.rowCount() == 2


def test_get_all_leaf_nodes(tree_model, alarm_item):
    """Confirm that all leaf nodes of a parent item are returned"""
    # Create a hierarchy of alarms to test with
    parent_one = AlarmItem("parent_1")
    leaf_one = AlarmItem("leaf_1")
    leaf_two = AlarmItem("leaf_2")
    parent_two = AlarmItem("parent_2")
    leaf_three = AlarmItem("leaf_3")
    leaf_four = AlarmItem("leaf_4")
    alarm_item.append_child(parent_one)
    alarm_item.append_child(leaf_one)
    parent_one.append_child(leaf_two)
    parent_one.append_child(parent_two)
    parent_two.append_child(leaf_three)
    parent_two.append_child(leaf_four)

    leaf_nodes = tree_model.get_all_leaf_nodes(alarm_item)
    leaf_nodes.sort(key=attrgetter("name"))
    assert len(leaf_nodes) == 4
    assert leaf_nodes[0].name == "leaf_1"
    assert leaf_nodes[1].name == "leaf_2"
    assert leaf_nodes[2].name == "leaf_3"
    assert leaf_nodes[3].name == "leaf_4"


def test_update_item(tree_model):
    """Test making an update to an item that has already been placed in the alarm tree"""
    alarm_item = AlarmItem(
        "TEST:PV",
        path="/path/to/TEST:PV",
        alarm_severity=AlarmSeverity.OK,
        alarm_status="OK",
        pv_severity=AlarmSeverity.OK,
    )

    tree_model.update_item(
        "TEST:PV", "/path/to/TEST:PV", AlarmSeverity.MINOR, "alarm", None, "FAULT", AlarmSeverity.MINOR, "alarm_status"
    )
    assert len(tree_model.nodes) == 0  # This update should have done nothing, this node has not yet been added

    tree_model.nodes.append(alarm_item)
    tree_model.added_paths["TEST:PV"] = ["/path/to/TEST:PV"]

    tree_model.update_item(
        "TEST:PV", "/path/to/TEST:PV", AlarmSeverity.MINOR, "alarm", None, "FAULT", AlarmSeverity.MINOR, "alarm_status"
    )

    # Verify the update applied successfully
    assert tree_model.nodes[0].name == "TEST:PV"
    assert tree_model.nodes[0].alarm_severity == AlarmSeverity.MINOR
    assert tree_model.nodes[0].alarm_status == "alarm"
    assert tree_model.nodes[0].alarm_value == "FAULT"
    assert tree_model.nodes[0].pv_severity == AlarmSeverity.MINOR
    assert tree_model.nodes[0].pv_status == "alarm_status"

    # Send a disable update message, verify the alarm gets marked filtered
    tree_model.update_item(
        "TEST:PV",
        "/path/to/TEST:PV",
        AlarmSeverity.MINOR,
        "Disabled",
        None,
        "FAULT",
        AlarmSeverity.MINOR,
        "alarm_status",
    )
    assert tree_model.nodes[0].filtered

    # And then send a message re-enabling the alarm and verify it is marked enabled again
    tree_model.update_item(
        "TEST:PV", "/path/to/TEST:PV", AlarmSeverity.MINOR, "OK", None, "FAULT", AlarmSeverity.MINOR, "alarm_status"
    )
    assert not tree_model.nodes[0].filtered


def test_update_model(tree_model):
    """Make some updates to the entire tree model itself and verify they are applied as expected"""
    tree_model.update_model("/path/to/PV:ONE", {})
    tree_model.update_model("/path/to/PV:TWO", {"description": "A Test PV", "enabled": False, "delay": 10})

    assert tree_model.nodes[0].name == "PV:ONE"
    assert tree_model.nodes[0].enabled

    # The two parent nodes of PV:ONE and PV:TWO
    assert tree_model.nodes[1].name == "to"
    assert tree_model.nodes[2].name == "path"

    assert tree_model.nodes[3].name == "PV:TWO"
    assert tree_model.nodes[3].description == "A Test PV"
    assert not tree_model.nodes[3].enabled
    assert tree_model.nodes[3].delay == 10

    # Now do an update to an existing node
    tree_model.update_model("/path/to/PV:TWO", {"enabled": True})
    assert tree_model.nodes[3].enabled


def test_remove_item(tree_model):
    """Delete an item from the tree, and verify it is deleted as expected"""
    # This should not do anything except log an error
    tree_model.remove_item("/does/not/exist")

    # Now add an item to actually be removed
    alarm_item = AlarmItem("TEST:PV", "/to/be/removed/TEST:PV", AlarmSeverity.OK)
    alarm_item_two = AlarmItem("OTHER:PV", "/other/pv/OTHER:PV", AlarmSeverity.OK)
    tree_model.nodes.append(alarm_item)
    tree_model.nodes.append(alarm_item_two)
    tree_model.added_paths["TEST:PV"] = ["/to/be/removed/TEST:PV"]
    tree_model.added_paths["OTHER:PV"] = ["/other/pv/OTHER:PV"]

    assert len(tree_model.nodes) == 2

    tree_model.remove_item("/to/be/removed/TEST:PV")
    tree_model.remove_item("/other/pv/OTHER:PV")

    assert len(tree_model.nodes) == 0
    assert len(tree_model.added_paths) == 0


def test_annunciation(tree_model):
    """Test making an update to an item that has already been placed in the alarm tree"""
    alarm_item = AlarmItem(
        "TEST:PV",
        path="/path/to/TEST:PV",
        alarm_severity=AlarmSeverity.OK,
        alarm_status="OK",
        pv_severity=AlarmSeverity.OK,
        annunciating=True,
    )

    tree_model.nodes.append(alarm_item)
    tree_model.added_paths["TEST:PV"] = ["/path/to/TEST:PV"]

    stdout_buffer = StringIO()
    # redirect stdout to buffer
    sys.stdout = stdout_buffer

    tree_model.update_item(
        "TEST:PV",
        "/path/to/TEST:PV",
        AlarmSeverity.MINOR,
        "STATE_ALARM",
        None,
        "FAULT",
        AlarmSeverity.MINOR,
        "alarm_status",
    )

    # restore original stdout stream
    sys.stdout = sys.__stdout__

    captured_output = stdout_buffer.getvalue()
    assert captured_output == "\x07\n"

    # Verify the update applied successfully
    assert tree_model.nodes[0].name == "TEST:PV"
    assert tree_model.nodes[0].alarm_severity == AlarmSeverity.MINOR
    assert tree_model.nodes[0].alarm_status == "alarm" or tree_model.nodes[0].alarm_status == "STATE_ALARM"
    assert tree_model.nodes[0].alarm_value == "FAULT"
    assert tree_model.nodes[0].pv_severity == AlarmSeverity.MINOR
    assert tree_model.nodes[0].pv_status == "alarm_status"

    # Send a disable update message, verify the alarm gets marked filtered
    tree_model.update_item(
        "TEST:PV",
        "/path/to/TEST:PV",
        AlarmSeverity.MINOR,
        "Disabled",
        None,
        "FAULT",
        AlarmSeverity.MINOR,
        "alarm_status",
    )
    assert tree_model.nodes[0].filtered

    # And then send a message re-enabling the alarm and verify it is marked enabled again
    tree_model.update_item(
        "TEST:PV", "/path/to/TEST:PV", AlarmSeverity.MINOR, "OK", None, "FAULT", AlarmSeverity.MINOR, "alarm_status"
    )
    assert not tree_model.nodes[0].filtered
