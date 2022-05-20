from collections import OrderedDict
from qtpy.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QVariant
from qtpy.QtGui import QBrush
from typing import Optional
from .alarm_item import AlarmItem


class AlarmItemsTableModel(QAbstractTableModel):
    """
    The AlarmItemsTableModel is a QAbstractTableModel based representation of alarm data. Can be used for both
    active and acknowledged alarms.

    Parameters
    ----------
    parent : QObject, optional
        The parent of the table model.
    """

    def __init__(self, parent: Optional[QObject] = None):
        super(QAbstractTableModel, self).__init__(parent=parent)
        self.alarm_items = OrderedDict()  # Key (str) to data
        self.column_names = ('PV', 'Alarm Severity', 'Alarm Status', 'Time', 'Alarm Value', 'PV Severity', 'PV Status')

    def rowCount(self, parent) -> int:
        """ Return the row count of the table """
        if parent is not None and parent.isValid():
            return 0
        return len(self.alarm_items)

    def columnCount(self, parent) -> int:
        """ Return the column count of the table """
        if parent is not None and parent.isValid():
            return 0
        return len(self.column_names)

    def data(self, index: QModelIndex, role: int):
        """ Return the data for the associated role. Currently only supporting DisplayRole and BackgroundRole. """
        if not index.isValid():
            return QVariant()

        if role != Qt.DisplayRole and role != Qt.BackgroundRole:
            return QVariant()

        column_name = self.column_names[index.column()]
        alarm_item = list(self.alarm_items.items())[index.row()][1]

        if role == Qt.DisplayRole:
            return self.getData(column_name, alarm_item)
        elif role == Qt.BackgroundRole:
            if alarm_item.alarm_severity == 'OK':
                return QBrush(Qt.green)
            elif alarm_item.alarm_severity == 'UNDEFINED':
                return QBrush(Qt.darkMagenta)
            elif alarm_item.alarm_severity == 'MAJOR':
                return QBrush(Qt.red)
            elif alarm_item.alarm_severity == 'MINOR':
                return QBrush(Qt.yellow)

    def getData(self, column_name: str, alarm_item: AlarmItem):
        """ Get the data from the input alarm item based on the column name """
        if column_name == 'PV':
            return alarm_item.name
        elif column_name == 'Alarm Severity':
            return alarm_item.alarm_severity
        elif column_name == 'Alarm Status':
            return alarm_item.alarm_status
        elif column_name == 'Time':
            return str(alarm_item.alarm_time)
        elif column_name == 'Alarm Value':
            return alarm_item.alarm_value
        elif column_name == 'PV Severity':
            return alarm_item.pv_severity
        elif column_name == 'PV Status':
            return alarm_item.pv_status

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return super(AlarmItemsTableModel, self).headerData(section, orientation, role)

        return str(self.column_names[section])

    def append(self, alarm_item: AlarmItem) -> None:
        """ Appends a row to this table with data as given by the input alarm item """
        if alarm_item.alarm_severity == 'OK':
            return  # Don't want to add unnecessary items to the table
        if alarm_item.name in self.alarm_items:
            print(f'ERROR: Attempting to append a row to the alarm table which is already there: {alarm_item.name}')
            return
        self.beginInsertRows(QModelIndex(), len(self.alarm_items), len(self.alarm_items))
        self.alarm_items[alarm_item.name] = alarm_item
        self.endInsertRows()
        self.layoutChanged.emit()

    def remove_row(self, alarm_name: str):
        """ Removes the row associated with the input name from this table """
        if alarm_name not in self.alarm_items:
            # print(f'ERROR: Attempting to remove a row from the alarm table when that PV is not present: {alarm_name}')
            return
        index_to_remove = list(self.alarm_items.keys()).index(alarm_name)
        self.beginRemoveRows(QModelIndex(), index_to_remove, index_to_remove)
        del self.alarm_items[alarm_name]
        self.endRemoveRows()
        self.layoutChanged.emit()

    def sort(self, col: int, order=Qt.AscendingOrder):
        """ Sort the table by the input column """
        self.layoutAboutToBeChanged.emit()
        # TODO: Clean this up
        if col == 0:
            sort_key = lambda x: x[1].name
        elif col == 1:
            sort_key = lambda x: x[1].alarm_severity
        elif col == 2:
            sort_key = lambda x: x[1].alarm_status
        elif col == 3:
            sort_key = lambda x: x[1].alarm_time
        elif col == 4:
            sort_key = lambda x: x[1].alarm_value
        elif col == 5:
            sort_key = lambda x: x[1].pv_severity
        elif col == 6:
            sort_key = lambda x: x[1].pv_status
        else:
            print(f'ERROR: Cannot sort by column: {col}')
        self.alarm_items = OrderedDict(
            sorted(self.alarm_items.items(), key=sort_key, reverse=order == Qt.DescendingOrder))
        self.layoutChanged.emit()

    def update_row(self, name: str, path: str, severity: str, status: str, time,
                   value: str, pv_severity: str, pv_status: str):
        """ Update a row in the alarm table based on the input name. If that name does not yet exist, a row will
            be created for it. If it does exist, update the values of the row accordingly. """

        if name not in self.alarm_items:
            # This item does not yet exist in the table, so create it and return
            self.append(AlarmItem(name=name, path=path, alarm_severity=severity, alarm_status=status, alarm_time=time,
                                  alarm_value=value, pv_severity=pv_severity, pv_status=pv_status))
            return

        # Otherwise update the row with the newly received data
        item_to_update = self.alarm_items[name]
        item_to_update.alarm_severity = severity
        item_to_update.alarm_status = status
        item_to_update.alarm_time = time
        item_to_update.alarm_value = value
        item_to_update.pv_severity = pv_severity
        item_to_update.pv_status = pv_status
        self.layoutChanged.emit()
