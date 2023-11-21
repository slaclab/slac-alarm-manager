import enum
import getpass
import socket
from functools import partial
from epics import cainfo, PV
from kafka.producer import KafkaProducer
from qtpy.QtCore import QEvent, QModelIndex, QSortFilterProxyModel, Qt, Signal
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAction,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from typing import Callable, List
from .alarm_table_model import AlarmItemsTableModel
from .alarm_tree_model import AlarmItemsTreeModel
from .permissions import UserAction, can_take_action
import re

class AlarmTableType(str, enum.Enum):
    """
    An enum for the type of alarms this table is displaying.
    """

    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"


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

    def __init__(
        self,
        tree_model: AlarmItemsTreeModel,
        kafka_producer: KafkaProducer,
        topic: str,
        table_type: AlarmTableType,
        plot_slot: Callable,
    ):
        super().__init__()
        self.resize(1035, 600)

        self.tree_model = tree_model  # We still need the tree hierarchy when dealing with acks at non leaf nodes
        self.kafka_producer = kafka_producer
        self.topic = topic
        self.table_type = table_type
        self.plot_slot = plot_slot
        self.plot_signal.connect(self.plot_slot)
        self.clipboard = QApplication.clipboard()

        self.alarmModel = AlarmItemsTableModel()

        self.layout = QVBoxLayout(self)
        self.alarm_count_label = QLabel("Active Alarms: 0")
        self.alarmView = QTableView(self)
        self.update_counter_label()

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
        self.acknowledge_action = QAction("Acknowledge")
        self.unacknowledge_action = QAction("Unacknowledge")
        self.copy_action = QAction("Copy PV To Clipboard")
        self.plot_action = QAction("Draw Plot")
        self.display_threshholds_menu = QMenu("Display Alarm Thresholds")

        self.acknowledge_action.triggered.connect(partial(self.send_acknowledge_action, True))
        self.unacknowledge_action.triggered.connect(partial(self.send_acknowledge_action, False))
        self.plot_action.triggered.connect(self.plot_pv)
        self.copy_action.triggered.connect(self.copy_alarm_name_to_clipboard)

        if self.table_type is AlarmTableType.ACTIVE:
            self.alarm_context_menu.addAction(self.acknowledge_action)
        if self.table_type is AlarmTableType.ACKNOWLEDGED:
            self.alarm_context_menu.addAction(self.unacknowledge_action)

        self.alarm_context_menu.addAction(self.copy_action)
        self.alarm_context_menu.addAction(self.plot_action)
        self.alarm_context_menu.addMenu(self.display_threshholds_menu)
        self.display_threshholds_menu.aboutToShow.connect(self.handleThresholdDisplay)

        self.alarmView.contextMenuEvent = self.alarm_context_menu_event

        # For filtering the alarm table
        self.alarm_filter_bar = QLineEdit()
        self.alarm_filter_bar.setMaximumSize(415, 30)
        self.filter_button = QPushButton("Filter")
        self.filter_button.setMaximumSize(120, 30)
        self.filter_button.pressed.connect(self.filter_table)
        self.filter_active_label = QLabel("Filter Active: ")
        self.filter_active_label.setStyleSheet("background-color: orange")
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

        self.alarmModel.layoutChanged.connect(self.update_counter_label)
        self.display_threshholds_menu.aboutToShow.connect(self.handleThresholdDisplay)

    def handleThresholdDisplay(self):
        indices = self.get_selected_indices()
        index = indices[0]
        alarm_item = None 
        if len(indices) > 0:
            alarm_item = list(self.alarmModel.alarm_items.items())[indices[0].row()][1]

        info = None
        hihi = high = low = lolo = "None"

        # Avoid calling "cainfo" on undefined alarm since causes the call to stall for a bit.
        # Also we don't want thresholds from an undefined alarm anyway.
        if alarm_item.is_undefined_or_invalid():
            self.display_threshholds_menu.clear()
            return

        info = cainfo(alarm_item.name, False) # False arg is so call returns string
        print (info)

        if info != None:
            """
            "cainfo" just returns string, so need regex to extract values,
            the following is example of values in the string:

             upper_alarm_limit   = 130.0
             lower_alarm_limit   = 90.0
             upper_warning_limit = 125.0
             lower_warning_limit = 90.0

            """
            upper_alarm_limit_pattern = re.compile(r'upper_alarm_limit\s*=\s*([\d.]+)')
            lower_alarm_limit_pattern = re.compile(r'lower_alarm_limit\s*=\s*([\d.]+)')
            upper_warning_limit_pattern = re.compile(r'upper_warning_limit\s*=\s*([\d.]+)')
            lower_warning_limit_pattern = re.compile(r'lower_warning_limit\s*=\s*([\d.]+)')

            hihi_search_result = upper_alarm_limit_pattern.search(info)
            # threshold values are not always set 
            hihi = hihi_search_result.group(1) if hihi_search_result else "None"
            
            high_search_result = lower_alarm_limit_pattern.search(info)
            high = high_search_result.group(1) if high_search_result else "None"

            low_search_result = upper_warning_limit_pattern.search(info)
            low = low_search_result.group(1) if low_search_result else "None"

            lolo_search_result = lower_warning_limit_pattern.search(info)
            lolo = lolo_search_result.group(1) if lolo_search_result else "None"


        self.hihi_action = QAction("HIHI: " + hihi)
        self.high_action = QAction("HIGH: " + high)
        self.low_action = QAction("LOW: " + low)
        self.lolo_action = QAction("LOLO: " + lolo)
        self.display_threshholds_menu.addAction(self.hihi_action)
        self.display_threshholds_menu.addAction(self.high_action)
        self.display_threshholds_menu.addAction(self.low_action)
        self.display_threshholds_menu.addAction(self.lolo_action)

    def filter_table(self) -> None:
        """Filter the table based on the text typed into the filter bar"""
        if self.first_filter:
            # By delaying setting the proxy model until an actual filter request, performance is improved by a lot
            # when first loading data into the table
            self.first_filter = False
            self.alarmView.setModel(self.alarm_proxy_model)
        self.alarm_proxy_model.setFilterFixedString(self.alarm_filter_bar.text())
        if self.alarm_filter_bar.text():
            self.filter_active_label.setText(f"Filter Active: {self.alarm_filter_bar.text()}")
            self.filter_active_label.show()
        else:
            self.filter_active_label.hide()

    def update_counter_label(self) -> None:
        """Update the labels displaying the count of active and acknowledged alarms"""
        if self.table_type is AlarmTableType.ACTIVE:
            self.alarm_count_label.setText(f"Active Alarms: {len(self.alarmModel.alarm_items)}")
        else:
            self.alarm_count_label.setText(f"Acknowledged Alarms: {len(self.alarmModel.alarm_items)}")

    def alarm_context_menu_event(self, ev: QEvent) -> None:
        """Display the right-click context menu for items in the active alarms table"""
        indices = self.get_selected_indices()
        if len(indices) > 0:
            alarm_item = list(self.alarmModel.alarm_items.items())[indices[0].row()][1]
        #print ("!!alarm_item path: ", alarm_item.name)
        #print ("!!!vals: ", vals)
        self.alarm_context_menu.popup(QCursor.pos())

    def get_selected_indices(self) -> List[QModelIndex]:
        """Return the indices which have been selected by the user, applying a mapping if a filter has been applied"""
        indices = self.alarmView.selectionModel().selectedRows()
        if self.filter_active_label.isVisible():
            indices = [self.alarm_proxy_model.mapToSource(proxy_index) for proxy_index in indices]
        return indices

    def plot_pv(self) -> None:
        """Send off the signal for plotting a PV"""
        indices = self.get_selected_indices()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
            self.plot_signal.emit(alarm_item.name)

    def copy_alarm_name_to_clipboard(self) -> None:
        """Copy the selected PV to the user's clipboard"""
        indices = self.get_selected_indices()
        if len(indices) > 0:
            copy_text = ""
            for index in indices:
                alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
                copy_text += alarm_item.name + " "
            self.clipboard.setText(copy_text[:-1], mode=self.clipboard.Selection)
            self.clipboard.setText(copy_text[:-1], mode=self.clipboard.Clipboard)

    def send_acknowledge_action(self, acknowledged: bool) -> None:
        """Send the input action by sending it to the command topic in the kafka cluster"""
        if not can_take_action(UserAction.ACKNOWLEDGE, log_warning=True):
            return

        indices = self.get_selected_indices()
        if len(indices) > 0:
            for index in indices:
                alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
                username = getpass.getuser()
                hostname = socket.gethostname()
                if alarm_item.name not in self.tree_model.added_paths:
                    # Alarm is no longer valid, send a None value to delete it from kafka.
                    # Empty topic string means this is 'All' topic tree-vew and doesn't have a valid kafka topic,
                    # so grab the destination topic from the alarm's path.
                    curr_topic = self.topic
                    if curr_topic == "":
                        curr_topic = self.tree_model.added_paths[alarm_item.name][0].split("/")[1]
                    self.kafka_producer.send(curr_topic, key=f"state:{alarm_item.path}", value=None)
                else:
                    command_to_send = "acknowledge" if acknowledged else "unacknowledge"
                    for alarm_path in self.tree_model.added_paths[alarm_item.name]:
                        # Similar to not-valid state above, grab the destination topic from the alarm's path.
                        curr_topic = self.topic
                        if curr_topic == "":
                            curr_topic = alarm_path.split("/")[1]
                        self.kafka_producer.send(
                            curr_topic + "Command",
                            key=f"command:{alarm_path}",
                            value={"user": username, "host": hostname, "command": command_to_send},
                        )
        self.alarmView.selectionModel().reset()
