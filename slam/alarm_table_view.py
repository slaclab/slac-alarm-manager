import enum
import getpass
import socket
from kafka.producer import KafkaProducer
from qtpy.QtCore import QEvent, QSortFilterProxyModel, Qt, Signal
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (QAbstractItemView, QAction, QApplication, QHBoxLayout, QHeaderView, QLabel,
                            QLineEdit, QMenu, QPushButton, QTableView, QVBoxLayout, QWidget)
from typing import Callable
from .alarm_table_model import AlarmItemsTableModel
from .alarm_tree_model import AlarmItemsTreeModel


class AlarmTableType(str, enum.Enum):
    """
    An enum for the type of alarms this table is displaying.
    """
    ACTIVE = 'ACTIVE'
    ACKNOWLEDGED = 'ACKNOWLEDGED'


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
    table_type: AlarmTableType
        The type of alarms this table is displaying (active or acknowledged)
    plot_slot : callable
        The function to invoke for plotting a PV
    """
    plot_signal = Signal(str)

    def __init__(self, tree_model: AlarmItemsTreeModel, kafka_producer: KafkaProducer,
                 topic: str, table_type: AlarmTableType, plot_slot: Callable):
        super().__init__()
        self.resize(1035, 600)

        self.tree_model = tree_model  # We still need the tree hierarchy when dealing with acks at non leaf nodes
        self.kafka_producer = kafka_producer
        self.topic = topic
        self.table_type = table_type
        self.plot_slot = plot_slot
        self.plot_signal.connect(self.plot_slot)
        self.clipboard = QApplication.clipboard()

        self.layout = QVBoxLayout(self)
        self.alarm_count_label = QLabel('Active Alarms: 0')
        self.alarmView = QTableView(self)

        self.alarmModel = AlarmItemsTableModel()

        # Using a proxy model allows for filtering based on a search bar
        self.alarm_proxy_model = QSortFilterProxyModel()
        self.alarm_proxy_model.setFilterKeyColumn(-1)
        self.alarm_proxy_model.setSourceModel(self.alarmModel)

        self.alarmView.setModel(self.alarmModel)

        # The table for alarms which are currently active
        self.alarmView.setProperty("showDropIndicator", False)
        self.alarmView.setDragDropOverwriteMode(False)
        self.alarmView.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.alarmView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.alarmView.setCornerButtonEnabled(False)
        self.alarmView.setSortingEnabled(True)
        self.alarmView.verticalHeader().setVisible(False)
        self.alarmView.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        for i in range(len(self.alarmModel.column_names)):
            self.alarmView.horizontalHeader().resizeSection(i, 150)
        self.alarmView.horizontalHeader().setStretchLastSection(True)
        self.alarmView.horizontalHeader().setSectionsMovable(True)

        # The actions which may be taken on an alarm
        self.alarm_context_menu = QMenu(self)
        self.acknowledge_action = QAction('Acknowledge')
        self.unacknowledge_action = QAction('Unacknowledge')
        self.copy_action = QAction('Copy PV To Clipboard')
        self.plot_action = QAction('Draw Plot')
        self.acknowledge_action.triggered.connect(self.send_acknowledgement)
        self.unacknowledge_action.triggered.connect(self.send_unacknowledgement)
        self.plot_action.triggered.connect(self.plot_pv)
        self.copy_action.triggered.connect(self.copy_alarm_name_to_clipboard)

        if self.table_type is AlarmTableType.ACTIVE:
            self.alarm_context_menu.addAction(self.acknowledge_action)
        if self.table_type is AlarmTableType.ACKNOWLEDGED:
            self.alarm_context_menu.addAction(self.unacknowledge_action)

        self.alarm_context_menu.addAction(self.copy_action)
        self.alarm_context_menu.addAction(self.plot_action)

        self.alarmView.contextMenuEvent = self.alarm_context_menu_event

        # For filtering the alarm table
        self.alarm_filter_bar = QLineEdit()
        self.alarm_filter_bar.setMaximumSize(415, 30)
        self.filter_button = QPushButton('Filter')
        self.filter_button.setMaximumSize(120, 30)
        self.filter_button.pressed.connect(self.filter_table)
        self.filter_active_label = QLabel('Filter Active: ')
        self.filter_active_label.setStyleSheet('background-color: orange')
        self.filter_active_label.hide()
        self.first_filter = True

        self.layout.addWidget(self.alarm_count_label)
        self.search_layout = QHBoxLayout()
        self.search_layout.addWidget(self.alarm_filter_bar)
        self.search_layout.addWidget(self.filter_button)
        self.search_layout.setAlignment(Qt.AlignLeft)
        self.layout.addLayout(self.search_layout)
        self.layout.addWidget(self.filter_active_label)
        self.layout.addWidget(self.alarmView)

        self.alarmModel.rowsInserted.connect(self.update_counter_label)
        self.alarmModel.rowsRemoved.connect(self.update_counter_label)

    def filter_table(self) -> None:
        """ Filter the table based on the text typed into the filter bar """
        if self.first_filter:
            # By delaying setting the proxy model until an actual filter request, performance is improved by a lot
            # when first loading data into the table
            self.first_filter = False
            self.alarmView.setModel(self.alarm_proxy_model)
        self.alarm_proxy_model.setFilterFixedString(self.alarm_filter_bar.text())
        if self.alarm_filter_bar.text():
            self.filter_active_label.setText(f'Filter Active: {self.alarm_filter_bar.text()}')
            self.filter_active_label.show()
        else:
            self.filter_active_label.hide()

    def update_counter_label(self) -> None:
        """ Update the labels displaying the count of active and acknowledged alarms """
        if self.table_type is AlarmTableType.ACTIVE:
            self.alarm_count_label.setText(f'Active Alarms: {len(self.alarmModel.alarm_items)}')
        else:
            self.alarm_count_label.setText(f'Acknowledged Alarms: {len(self.alarmModel.alarm_items)}')

    def alarm_context_menu_event(self, ev: QEvent) -> None:
        """ Display the right-click context menu for items in the active alarms table """
        self.alarm_context_menu.popup(QCursor.pos())

    def plot_pv(self) -> None:
        """ Send off the signal for plotting a PV """
        indices = self.alarmView.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
            self.plot_signal.emit(alarm_item.name)

    def copy_alarm_name_to_clipboard(self) -> None:
        """ Copy the selected PV to the user's clipboard """
        indices = self.alarmView.selectionModel().selectedRows()
        if len(indices) > 0:
            copy_text = ''
            for index in indices:
                alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
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
                for alarm_path in self.tree_model.added_paths[alarm_item.name]:
                    self.kafka_producer.send(self.topic + 'Command',
                                             key=f'command:{alarm_path}',
                                             value={'user': username, 'host': hostname, 'command': 'acknowledge'})

    def send_unacknowledgement(self) -> None:
        """ Send the un-acknowledge action by sending it to the command topic in the kafka cluster """
        indices = self.alarmView.selectionModel().selectedRows()
        if len(indices) > 0:
            for index in indices:
                alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
                username = getpass.getuser()
                hostname = socket.gethostname()
                for alarm_path in self.tree_model.added_paths[alarm_item.name]:
                    self.kafka_producer.send(self.topic + 'Command',
                                             key=f'command:{alarm_path}',
                                             value={'user': username, 'host': hostname, 'command': 'unacknowledge'})
