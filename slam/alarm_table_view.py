import functools
import getpass
import socket
from kafka.producer import KafkaProducer
from qtpy.QtCore import QEvent, QSortFilterProxyModel, Signal
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (QAbstractItemView, QAction, QApplication, QHBoxLayout, QHeaderView, QLabel,
                            QLineEdit, QMenu, QPushButton, QTableView, QVBoxLayout, QWidget)
from typing import Callable
from .alarm_item import AlarmSeverity
from .alarm_table_model import AlarmItemsTableModel
from .alarm_tree_model import AlarmItemsTreeModel


class AlarmTableViewWidget(QWidget):
    """
    The AlarmTableViewWidget is a collection of everything needed to display and interact with an alarm table.

    Parameters
    ----------
    tree_model : AlarmItemsTreeModel
        The model containing the tree configuration of all the monitored alarms
    kafka_producer : KafkaProducer
        The producer for sending state and command updates to the kafka cluster
    topic : str
        The kafka topic to send update messages to
    plot_slot : callable
        The function to invoke for plotting a PV
    """
    plot_signal = Signal(str)

    def __init__(self, tree_model: AlarmItemsTreeModel, kafka_producer: KafkaProducer, topic: str, plot_slot: Callable):
        super().__init__()
        self.resize(1035, 600)

        self.tree_model = tree_model  # We still need the tree hierarchy when dealing with acks at non leaf nodes
        self.kafka_producer = kafka_producer
        self.topic = topic
        self.plot_slot = plot_slot
        self.plot_signal.connect(self.plot_slot)
        self.clipboard = QApplication.clipboard()

        self.layout = QVBoxLayout(self)
        self.active_alarms_label = QLabel('Active Alarms: 0')
        self.acknowledged_alarms_label = QLabel('Acknowledged Alarms: 0')
        self.alarmView = QTableView(self)
        self.acknowledgedAlarmsView = QTableView(self)

        self.alarmModel = AlarmItemsTableModel()
        self.acknowledgedAlarmsModel = AlarmItemsTableModel()

        # Using a proxy model allows for filtering based on a search bar
        self.alarm_proxy_model = QSortFilterProxyModel()
        self.alarm_proxy_model.setFilterKeyColumn(-1)
        self.alarm_proxy_model.setSourceModel(self.alarmModel)

        self.alarmView.setModel(self.alarmModel)
        self.acknowledgedAlarmsView.setModel(self.acknowledgedAlarmsModel)

        # The table for alarms which are currently active
        self.alarmView.setProperty("showDropIndicator", False)
        self.alarmView.setDragDropOverwriteMode(False)
        self.alarmView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.alarmView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.alarmView.setCornerButtonEnabled(False)
        self.alarmView.setSortingEnabled(True)
        self.alarmView.verticalHeader().setVisible(False)
        self.alarmView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.alarmView.horizontalHeader().setSectionsMovable(True)

        # The table for alarms which have been acknowledged
        self.acknowledgedAlarmsView.setProperty("showDropIndicator", False)
        self.acknowledgedAlarmsView.setDragDropOverwriteMode(False)
        self.acknowledgedAlarmsView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.acknowledgedAlarmsView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.acknowledgedAlarmsView.setCornerButtonEnabled(False)
        self.acknowledgedAlarmsView.setSortingEnabled(True)
        self.acknowledgedAlarmsView.verticalHeader().setVisible(False)
        self.acknowledgedAlarmsView.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.acknowledgedAlarmsView.horizontalHeader().setSectionsMovable(True)

        # The actions which may be taken on an alarm
        self.active_context_menu = QMenu(self)
        self.acknowledged_context_menu = QMenu(self)
        self.acknowledge_action = QAction('Acknowledge')
        self.unacknowledge_action = QAction('Unacknowledge')
        self.active_copy_action = QAction('Copy PV To Clipboard')
        self.acknowledged_copy_action = QAction('Copy PV To Clipboard')
        self.plot_action = QAction('Draw Plot')
        self.acknowledge_action.triggered.connect(self.send_acknowledgement)
        self.unacknowledge_action.triggered.connect(self.send_unacknowledgement)
        self.plot_action.triggered.connect(self.plot_pv)
        self.active_copy_action.triggered.connect(self.copy_active_alarm_to_clipboard)
        self.acknowledged_copy_action.triggered.connect(self.copy_acknowledged_alarm_to_clipboard)

        self.active_context_menu.addAction(self.acknowledge_action)
        self.active_context_menu.addAction(self.active_copy_action)
        self.active_context_menu.addAction(self.plot_action)
        self.acknowledged_context_menu.addAction(self.unacknowledge_action)
        self.acknowledged_context_menu.addAction(self.acknowledged_copy_action)
        self.acknowledged_context_menu.addAction(self.plot_action)

        self.alarmView.contextMenuEvent = self.active_alarm_context_menu_event
        self.acknowledgedAlarmsView.contextMenuEvent = self.acknowledged_alarm_context_menu_event

        # For filtering the alarm table
        self.active_alarm_search_bar = QLineEdit()
        self.filter_button = QPushButton('Filter')
        self.filter_button.pressed.connect(self.filter_table)
        self.filter_active_label = QLabel('Filter Active: ')
        self.filter_active_label.setStyleSheet('background-color: orange')
        self.filter_active_label.hide()
        self.first_filter = True

        self.layout.addWidget(self.active_alarms_label)
        self.search_layout = QHBoxLayout()
        self.search_layout.addWidget(self.active_alarm_search_bar)
        self.search_layout.addWidget(self.filter_button)
        self.layout.addLayout(self.search_layout)
        self.layout.addWidget(self.filter_active_label)
        self.layout.addWidget(self.alarmView)
        self.layout.addWidget(self.acknowledged_alarms_label)
        self.layout.addWidget(self.acknowledgedAlarmsView)

        self.alarmModel.rowsInserted.connect(self.update_counter_label)
        self.alarmModel.rowsRemoved.connect(self.update_counter_label)
        self.acknowledgedAlarmsModel.rowsInserted.connect(self.update_counter_label)
        self.acknowledgedAlarmsModel.rowsRemoved.connect(self.update_counter_label)

    def filter_table(self) -> None:
        """ Filter the table based on the text typed into the filter bar """
        if self.first_filter:
            # By delaying setting the proxy model until an actual filter request, performance is improved by a lot
            # when first loading data into the table
            self.first_filter = False
            self.alarmView.setModel(self.alarm_proxy_model)
        self.alarm_proxy_model.setFilterFixedString(self.active_alarm_search_bar.text())
        if self.active_alarm_search_bar.text():
            self.filter_active_label.setText(f'Filter Active: {self.active_alarm_search_bar.text()}')
            self.filter_active_label.show()
        else:
            self.filter_active_label.hide()

    def update_counter_label(self) -> None:
        """ Update the labels displaying the count of active and acknowledged alarms """
        self.active_alarms_label.setText(f'Active Alarms: {len(self.alarmModel.alarm_items)}')
        self.acknowledged_alarms_label.setText(f'Acknowledged Alarms: {len(self.acknowledgedAlarmsModel.alarm_items)}')

    def active_alarm_context_menu_event(self, ev: QEvent) -> None:
        """ Display the right-click context menu for items in the active alarms table """
        self.active_context_menu.popup(QCursor.pos())

    def acknowledged_alarm_context_menu_event(self, ev: QEvent) -> None:
        """ Display the right-click context menu for items in the acknowledged alarms table """
        self.acknowledged_context_menu.popup(QCursor.pos())

    def plot_pv(self) -> None:
        """ Send off the signal for plotting a PV """
        indices = self.alarmView.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
            self.plot_signal.emit(alarm_item.name)

    def copy_active_alarm_to_clipboard(self) -> None:
        """ Copy the selected PV to the user's clipboard """
        indices = self.alarmView.selectionModel().selectedRows()
        if len(indices) > 0:
            copy_text = ''
            for index in indices:
                alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
                copy_text += alarm_item.name + ' '
            self.clipboard.setText(copy_text[:-1], mode=self.clipboard.Selection)
            self.clipboard.setText(copy_text[:-1], mode=self.clipboard.Clipboard)

    def copy_acknowledged_alarm_to_clipboard(self) -> None:
        """ Copy the selected PV to the user's clipboard """
        indices = self.acknowledgedAlarmsView.selectionModel().selectedRows()
        if len(indices) > 0:
            copy_text = ''
            for index in indices:
                alarm_item = list(self.acknowledgedAlarmsModel.alarm_items.items())[index.row()][1]
                copy_text += alarm_item.name + ' '
            self.clipboard.setText(copy_text[:-1], mode=self.clipboard.Selection)
            self.clipboard.setText(copy_text[:-1], mode=self.clipboard.Clipboard)

    def send_acknowledgement(self) -> None:
        """ Send the acknowledge action by sending it to the command topic in the kafka cluster """
        indices = self.alarmView.selectionModel().selectedRows()
        if len(indices) > 0:
            for index in indices:
                alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
                username = getpass.getuser()
                hostname = socket.gethostname()
                self.kafka_producer.send(self.topic + 'Command',
                                         key=f'command:{alarm_item.path}',
                                         value={'user': username, 'host': hostname, 'command': 'acknowledge'})

    def send_unacknowledgement(self) -> None:
        """ Send the un-acknowledge action by sending it to the command topic in the kafka cluster """
        indices = self.acknowledgedAlarmsView.selectedIndexes()
        if len(indices) > 0:
            for index in indices:
                alarm_item = list(self.acknowledgedAlarmsModel.alarm_items.items())[index.row()][1]
                username = getpass.getuser()
                hostname = socket.gethostname()
                self.kafka_producer.send(self.topic + 'Command',
                                         key=f'command:{alarm_item.path}',
                                         value={'user': username, 'host': hostname, 'command': 'unacknowledge'})

    def update_tables(self, name: str, path: str, severity: AlarmSeverity, status: str, time,
                      value: str, pv_severity: AlarmSeverity, pv_status: str) -> None:
        """ Update both the active and acknowledged alarm tables when a new alarm state message is received """
        if status == 'Disabled':
            self.alarmModel.remove_row(name)
            self.acknowledgedAlarmsModel.remove_row(name)
        elif severity in (AlarmSeverity.INVALID_ACK, AlarmSeverity.MAJOR_ACK,
                          AlarmSeverity.MINOR_ACK, AlarmSeverity.UNDEFINED_ACK):
            if name in self.alarmModel.alarm_items:
                self.alarmModel.remove_row(name)
            self.acknowledgedAlarmsModel.update_row(name, path, severity, status, time, value, pv_severity, pv_status)
        elif severity == AlarmSeverity.OK:
            self.alarmModel.remove_row(name)
            self.acknowledgedAlarmsModel.remove_row(name)
        else:
            if name in self.acknowledgedAlarmsModel.alarm_items:
                self.acknowledgedAlarmsModel.remove_row(name)
            self.alarmModel.update_row(name, path, severity, status, time, value, pv_severity, pv_status)
