from collections import OrderedDict
from qtpy.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QVariant
from typing import Optional
from .alarm_item import AlarmItem, AlarmSeverity
import logging

logger = logging.getLogger(__name__)


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
        self.column_names = ('PV', 'Latched Severity', 'Latched Status', 'Description', 'Time', 'Alarm Value',
                             'Current Severity', 'Current Status')
        self.column_to_attr = {0: 'name', 1: 'alarm_severity', 2: 'alarm_status', 3: 'description', 4: 'alarm_time',
                               5: 'alarm_value', 6: 'pv_severity', 7: 'pv_status'}

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

        if role != Qt.DisplayRole and role != Qt.TextColorRole:
            return QVariant()

        column_name = self.column_names[index.column()]
        alarm_item = list(self.alarm_items.items())[index.row()][1]

        if role == Qt.DisplayRole:
            return self.getData(column_name, alarm_item)
        elif role == Qt.TextColorRole:
            if column_name == 'Latched Severity':
                return alarm_item.display_color(alarm_item.alarm_severity)
            if column_name == 'Current Severity':
                return alarm_item.display_color(alarm_item.pv_severity)

    def getData(self, column_name: str, alarm_item: AlarmItem):
        """ Get the data from the input alarm item based on the column name """
        if column_name == 'PV':
            return alarm_item.name
        elif column_name == 'Latched Severity':
            return alarm_item.alarm_severity.value
        elif column_name == 'Latched Status':
            return alarm_item.alarm_status
        elif column_name == 'Description':
            return alarm_item.description
        elif column_name == 'Time':
            return str(alarm_item.alarm_time)
        elif column_name == 'Alarm Value':
            return alarm_item.alarm_value
        elif column_name == 'Current Severity':
            return alarm_item.pv_severity.value
        elif column_name == 'Current Status':
            return alarm_item.pv_status

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return super(AlarmItemsTableModel, self).headerData(section, orientation, role)

        return str(self.column_names[section])

    def append(self, alarm_item: AlarmItem) -> None:
        """ Appends a row to this table with data as given by the input alarm item """
        if alarm_item.alarm_severity == AlarmSeverity.OK:
            return  # Don't want to add unnecessary items to the table
        if alarm_item.name in self.alarm_items:
            logger.warning(f'Attempting to append a row to the alarm table which is already there: {alarm_item.name}')
            return
        self.beginInsertRows(QModelIndex(), len(self.alarm_items), len(self.alarm_items))
        self.alarm_items[alarm_item.name] = alarm_item
        self.endInsertRows()
        self.layoutChanged.emit()

    def remove_row(self, alarm_name: str):
        """ Removes the row associated with the input name from this table """
        if alarm_name not in self.alarm_items:
            return
        index_to_remove = list(self.alarm_items.keys()).index(alarm_name)
        self.beginRemoveRows(QModelIndex(), index_to_remove, index_to_remove)
        del self.alarm_items[alarm_name]
        self.endRemoveRows()
        self.layoutChanged.emit()

    def sort(self, col: int, order=Qt.AscendingOrder):
        """ Sort the table by the input column """
        self.layoutAboutToBeChanged.emit()
        self.alarm_items = OrderedDict(sorted(self.alarm_items.items(),
                                              key=lambda alarm_item: getattr(alarm_item[1], self.column_to_attr[col]),
                                              reverse=order == Qt.DescendingOrder))
        self.layoutChanged.emit()

    def update_row(self, name: str, path: str, severity: AlarmSeverity, status: str, time,
                   value: str, pv_severity: AlarmSeverity, pv_status: str, description: str):
        """ Update a row in the alarm table based on the input name. If that name does not yet exist, a row will
            be created for it. If it does exist, update the values of the row accordingly. """

        if name not in self.alarm_items:
            # This item does not yet exist in the table, so create it and return
            self.append(AlarmItem(name=name, path=path, alarm_severity=severity, alarm_status=status,
                                  alarm_time=time, alarm_value=value, pv_severity=pv_severity,
                                  pv_status=pv_status, description=description))
            return

        # Otherwise update the row with the newly received data
        self.layoutAboutToBeChanged.emit()
        item_to_update = self.alarm_items[name]
        item_to_update.alarm_severity = severity
        item_to_update.alarm_status = status
        item_to_update.alarm_time = time
        item_to_update.alarm_value = value
        item_to_update.pv_severity = pv_severity
        item_to_update.pv_status = pv_status
        self.layoutChanged.emit()
