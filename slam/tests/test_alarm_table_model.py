from ..alarm_item import AlarmItem, AlarmSeverity
from ..alarm_table_model import AlarmItemsTableModel
from datetime import datetime
import pytest


@pytest.fixture(scope='function')
def alarm_table():
    """ Return an empty alarm table for testing """
    return AlarmItemsTableModel()


def test_row_count(alarm_table, alarm_item):
    """ Verify the row count returns the number expected """
    assert alarm_table.rowCount(None) == 0
    alarm_table.alarm_items['ALARM:ONE'] = alarm_item
    assert alarm_table.rowCount(None) == 1
    alarm_table.alarm_items['ALARM:TWO'] = alarm_item
    assert alarm_table.rowCount(None) == 2


def test_column_count(alarm_table):
    """ Verify the column count is as expected """
    assert alarm_table.columnCount(None) == len(alarm_table.column_names)


def test_get_data(alarm_table):
    """ Ensure we return the correct attribute of the input AlarmItem as a string based on the column requested """
    alarm_item = AlarmItem('PV:NAME', alarm_severity=AlarmSeverity.MAJOR, alarm_status='enabled',
                           alarm_time=datetime.fromisoformat('2022-01-02 00:10:00'), alarm_value='FAULT',
                           pv_severity=AlarmSeverity.MINOR, pv_status='enabled')

    assert alarm_table.getData('PV', alarm_item) == 'PV:NAME'
    assert alarm_table.getData('Latched Severity', alarm_item) == 'MAJOR'
    assert alarm_table.getData('Latched Status', alarm_item) == 'enabled'
    assert alarm_table.getData('Time', alarm_item) == '2022-01-02 00:10:00'
    assert alarm_table.getData('Alarm Value', alarm_item) == 'FAULT'
    assert alarm_table.getData('Current Severity', alarm_item) == 'MINOR'
    assert alarm_table.getData('Current Status', alarm_item) == 'enabled'


def test_append(alarm_table):
    """ Append an item to the table and confirm it was added correctly """
    alarm_item_ok = AlarmItem('TEST:PV:ONE', path='/root/TEST:PV:ONE', alarm_severity=AlarmSeverity.OK)
    alarm_item_major = AlarmItem('TEST:PV:TWO', path='/root/TEST:PV:TWO', alarm_severity=AlarmSeverity.MAJOR)
    alarm_item_acknowledged = AlarmItem('TEST:PV:ACK', path='/root/TEST:PV:ACK', alarm_severity=AlarmSeverity.MINOR_ACK)

    # If an alarm has a normal OK severity, it should not be added to the table, so this append will be rejected
    alarm_table.append(alarm_item_ok)
    assert len(alarm_table.alarm_items) == 0

    # This alarm has a severity of MAJOR, so it gets added
    alarm_table.append(alarm_item_major)
    assert len(alarm_table.alarm_items) == 1

    # Acknowledged alarms should also be added to the table
    alarm_table.append(alarm_item_acknowledged)
    assert len(alarm_table.alarm_items) == 2


def test_remove_row(alarm_table):
    """ Now verify that removing rows that have been appended works as expected """
    alarm_item_major = AlarmItem('TEST:PV:MAJOR', path='/root/TEST:PV:TWO', alarm_severity=AlarmSeverity.MAJOR)
    alarm_item_acknowledged = AlarmItem('TEST:PV:ACK', path='/root/TEST:PV:ACK', alarm_severity=AlarmSeverity.MINOR_ACK)

    alarm_table.append(alarm_item_major)
    alarm_table.append(alarm_item_acknowledged)
    assert len(alarm_table.alarm_items) == 2

    # Remove the unacknowledged alarm, confirm there is only one item remaining and it is the acknowledged one
    alarm_table.remove_row('TEST:PV:MAJOR')
    assert len(alarm_table.alarm_items) == 1
    assert 'TEST:PV:ACK' in alarm_table.alarm_items

    # Remove the acknowledged alarm, confirm that there are no items remaining in the table
    alarm_table.remove_row('TEST:PV:ACK')
    assert len(alarm_table.alarm_items) == 0


@pytest.mark.parametrize('column, expected_order', [(0, ('PV:MAJOR', 'PV:MINOR', 'PV:UNDEFINED')),
                                                    (1, ('PV:MINOR', 'PV:MAJOR', 'PV:UNDEFINED')),
                                                    (2, ('PV:MAJOR', 'PV:MINOR', 'PV:UNDEFINED')),
                                                    (3, ('PV:UNDEFINED', 'PV:MINOR', 'PV:MAJOR')),
                                                    (4, ('PV:MINOR', 'PV:MAJOR', 'PV:UNDEFINED')),
                                                    (5, ('PV:MINOR', 'PV:MAJOR', 'PV:UNDEFINED')),
                                                    (6, ('PV:MAJOR', 'PV:MINOR', 'PV:UNDEFINED'))])
def test_sort(alarm_table, column, expected_order):
    """ Test that the order of alarm items in the table is correct when sorting on every column """
    alarm_item_major = AlarmItem('PV:MAJOR', alarm_severity=AlarmSeverity.MAJOR, alarm_status='enabled',
                                 alarm_time=datetime.fromisoformat('2022-01-05 00:10:00'), alarm_value='FAULT',
                                 pv_severity=AlarmSeverity.MAJOR, pv_status='enabled')
    alarm_item_minor = AlarmItem('PV:MINOR', alarm_severity=AlarmSeverity.MINOR, alarm_status='enabled',
                                 alarm_time=datetime.fromisoformat('2022-01-04 00:10:00'), alarm_value='1.0',
                                 pv_severity=AlarmSeverity.MINOR, pv_status='enabled')
    alarm_item_undefined = AlarmItem('PV:UNDEFINED', alarm_severity=AlarmSeverity.UNDEFINED, alarm_status='unknown',
                                     alarm_time=datetime.fromisoformat('2022-01-03 00:10:00'), alarm_value='UNK',
                                     pv_severity=AlarmSeverity.UNDEFINED, pv_status='unknown')

    alarm_table.append(alarm_item_major)
    alarm_table.append(alarm_item_minor)
    alarm_table.append(alarm_item_undefined)

    alarm_table.sort(col=column)
    sorted_items = list(alarm_table.alarm_items.items())
    assert sorted_items[0][0] == expected_order[0]
    assert sorted_items[1][0] == expected_order[1]
    assert sorted_items[2][0] == expected_order[2]


def test_update_row(alarm_table):
    """ Verify updating a row that doesn't exist adds it, and updating an existing row modified it as expected """
    # Updates to alarm items that don't yet exist will result in them being added
    alarm_table.update_row('PV ONE', '/path/to/PV:ONE', AlarmSeverity.MINOR,
                           'enabled', datetime.now, 'MINOR FAULT', AlarmSeverity.MINOR, 'enabled')
    assert len(alarm_table.alarm_items) == 1
    alarm_table.update_row('PV TWO', '/path/to/PV:TWO', AlarmSeverity.UNDEFINED,
                           'enabled', datetime.now, 'UND', AlarmSeverity.UNDEFINED, 'enabled')
    assert len(alarm_table.alarm_items) == 2

    # Now modify the first alarm we added. Verify that no new row was added, and the update happened as expected
    alarm_table.update_row('PV ONE', '/path/to/PV:ONE', AlarmSeverity.MAJOR,
                           'enabled', datetime.now, 'MAJOR FAULT', AlarmSeverity.MAJOR, 'enabled')
    assert len(alarm_table.alarm_items) == 2

    updated_item = alarm_table.alarm_items['PV ONE']
    assert updated_item.alarm_severity == AlarmSeverity.MAJOR
    assert updated_item.pv_severity == AlarmSeverity.MAJOR
    assert updated_item.alarm_value == 'MAJOR FAULT'
