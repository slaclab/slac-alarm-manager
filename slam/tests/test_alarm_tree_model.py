from ..alarm_item import AlarmItem, AlarmSeverity


def test_clear(tree_model, alarm_item):
    """ A quick check that clear is removing data as expected. """
    tree_model.nodes.append(alarm_item)
    tree_model.added_paths.add('/path/to/the/node')
    tree_model.root_item = alarm_item

    tree_model.clear()

    assert len(tree_model.nodes) == 0
    assert len(tree_model.added_paths) == 0
    assert tree_model.root_item.name == ''


def test_column_count(tree_model, alarm_item):
    """ Check that columnCount() returns the expected number """
    assert tree_model.columnCount() == 1  # No multiple columns for a tree


def test_row_count(tree_model, alarm_item):
    """ Check that rowCount() returns the correct number (the count of children for the tree case) """
    tree_model.root_item.append_child(alarm_item)
    alarm_item_major = AlarmItem('ALARM:MAJOR', alarm_severity=AlarmSeverity.MAJOR)
    tree_model.root_item.append_child(alarm_item_major)
    assert tree_model.rowCount() == 2


def test_get_all_leaf_nodes(alarm_item):
    """ Confirm that all leaf nodes of a parent item are returned """
    pass
