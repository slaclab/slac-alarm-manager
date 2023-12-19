import enum
import getpass
import socket
from functools import partial
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
from epics import PV
from typing import Callable, List
from .alarm_table_model import AlarmItemsTableModel
from .alarm_tree_model import AlarmItemsTreeModel
from .permissions import UserAction, can_take_action
from math import isnan


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
        annunciate: bool = False,
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
        self.display_thresholds_menu = QMenu("Display Alarm Thresholds")
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
        self.alarm_context_menu.addMenu(self.display_thresholds_menu)
        self.display_thresholds_menu.aboutToShow.connect(self.handleThresholdDisplay)

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

    def handleThresholdDisplay(self):
        indices = self.get_selected_indices()
        alarm_item = None
        hihi = high = low = lolo = -1

        # If multiple alarm-items selected, just display thresholds for 1st item.
        # (or don't display anything if 1st item is undefined/invalid).
        # This follows how the "Draw Plot" option handles multiple selected items.
        if len(indices) > 0:
            index = indices[0]
            alarm_item = list(self.alarmModel.alarm_items.items())[index.row()][1]
        else:
            return

        # If not a leaf its an invalid 'cainfo' call which could stall things for a while.
        if not alarm_item.is_leaf():
            # Don't display any of the threshold-display actions if selected non-leaf
            self.display_thresholds_menu.clear()
            return

        # Avoid calling 'cainfo' on undefined alarm since causes the call to stall for a bit.
        # Also we don't want thresholds from an undefined alarm anyway.
        if alarm_item.is_undefined_or_invalid():
            # Don't display any of the threshold-display actions if alarm-item undefined
            self.display_thresholds_menu.clear()
            return

        if alarm_item.pv_object is None:
            alarm_item.pv_object = PV(alarm_item.name)
            # Update the values only when user requests them in right-click menu
            alarm_item.pv_object.clear_auto_monitor()

        alarm_item_metadata = alarm_item.pv_object.get_ctrlvars()

        # Getting data can fail for some PV's, good metadata will always have a key for all 4 limits (nan if not set),
        # in this case don't display any threshold sub-menus
        if (
            alarm_item_metadata is not None
            and len(alarm_item_metadata) > 0
            and "upper_alarm_limit" not in alarm_item_metadata
        ):
            self.display_thresholds_menu.clear()
            return

        # threshold values are not always set, just display "None" if so
        # upper_alarm_limit here is same as calling caget for pv's '.HIHI'
        hihi = alarm_item_metadata["upper_alarm_limit"]
        lolo = alarm_item_metadata["lower_alarm_limit"]
        high = alarm_item_metadata["upper_warning_limit"]
        low = alarm_item_metadata["lower_warning_limit"]

        # we display threshold values as 4 items in a drop-down menu
        self.hihi_action = QAction("HIHI: " + str(hihi)) if not isnan(hihi) else QAction("HIHI: Not set")
        self.high_action = QAction("HIGH: " + str(high)) if not isnan(high) else QAction("HIGH: Not set")
        self.low_action = QAction("LOW: " + str(low)) if not isnan(low) else QAction("LOW: Not set")
        self.lolo_action = QAction("LOLO: " + str(lolo)) if not isnan(lolo) else QAction("LOLO: Not set")
        self.display_thresholds_menu.addAction(self.hihi_action)
        self.display_thresholds_menu.addAction(self.high_action)
        self.display_thresholds_menu.addAction(self.low_action)
        self.display_thresholds_menu.addAction(self.lolo_action)

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
