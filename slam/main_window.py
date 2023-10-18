import json
import logging
from datetime import datetime
from kafka.consumer.fetcher import ConsumerRecord
from kafka import KafkaProducer
from pydm.widgets import PyDMArchiverTimePlot
from qtpy.QtCore import Qt, QThread, QTimer, Signal, Slot
from qtpy.QtWidgets import QAction, QApplication, QComboBox, QLabel, QMainWindow, QSplitter, QVBoxLayout, QWidget
from typing import List, Optional
from .alarm_item import AlarmSeverity
from .alarm_table_view import AlarmTableType, AlarmTableViewWidget
from .alarm_tree_view import AlarmTreeViewWidget
from .archive_search import ArchiveSearchWidget
from .kafka_reader import KafkaReader
from .alarm_item import AlarmItem

logger = logging.getLogger(__name__)


class AlarmHandlerMainWindow(QMainWindow):
    """
    The AlarmHandlerMainWindow is the main top-level widget for displaying and interacting with alarms.

    Parameters
    ----------

    topics : List[str]
        The kafka topics to listen to
    bootstrap_servers : List[str]
        A list containing one or more urls for kafka bootstrap servers
    """

    alarm_update_signal = Signal(str, str, str, AlarmSeverity, str, datetime, str, AlarmSeverity, str)

    def __init__(self, topics: List[str], bootstrap_servers: List[str]):
        super().__init__()

        self.kafka_producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode("utf-8"),
            key_serializer=lambda x: x.encode("utf-8"),
        )
        self.topics = topics
        self.descriptions = dict()  # Map from alarm path to description

        self.clipboard = QApplication.clipboard()

        self.main_menu = self.menuBar()
        self.file_menu = self.main_menu.addMenu("File")
        self.applications_menu = self.main_menu.addMenu("Tools")
        self.exit_action = QAction("Exit")
        self.exit_action.triggered.connect(self.exit_application)
        self.file_menu.addAction(self.exit_action)
        self.archiver_search_action = QAction("Archiver Search")
        self.archiver_search_action.triggered.connect(self.create_archiver_search_widget)
        self.empty_plot_action = QAction("Time Plot")
        self.empty_plot_action.triggered.connect(self.create_plot_widget)
        self.applications_menu.addAction(self.archiver_search_action)
        self.applications_menu.addAction(self.empty_plot_action)

        # A combo box for choosing which alarm tree/table to display
        self.alarm_select_combo_box = QComboBox(self)
        self.alarm_select_combo_box.setFixedSize(120, 30)

        self.alarm_select_combo_box.currentTextChanged.connect(self.change_display)
        self.current_alarm_config = topics[0]

        self.alarm_trees = dict()
        self.all_alarms_tree = AlarmTreeViewWidget(self.kafka_producer, "", self.plot_pv)
        self.all_alarms_tree.topics = topics
        self.alarm_trees['All'] = self.all_alarms_tree

        self.active_alarm_tables = dict()
        self.all_active_alarms_table = AlarmTableViewWidget(
            self.all_alarms_tree.treeModel, self.kafka_producer, "", AlarmTableType.ACTIVE, self.plot_pv
            )
        self.all_active_alarms_table.topics = topics
        self.active_alarm_tables['All'] = self.all_active_alarms_table
        
        self.acknowledged_alarm_tables = dict()
        self.all_acknowledged_alarms_table = AlarmTableViewWidget(
            self.all_alarms_tree.treeModel, self.kafka_producer, "", AlarmTableType.ACKNOWLEDGED, self.plot_pv
            )
        self.all_acknowledged_alarms_table.topics = topics
        self.acknowledged_alarm_tables['All'] = self.all_acknowledged_alarms_table

        self.last_received_update_time = {}  # Mapping from alarm config name to last kafka message received for it

        # Create a separate tree and table widget for each alarm configuration we are monitoring
        for topic in topics:
            self.last_received_update_time[topic] = datetime.now()
            self.alarm_select_combo_box.addItem(topic)
            self.alarm_trees[topic] = AlarmTreeViewWidget(self.kafka_producer, topic, self.plot_pv)
            self.active_alarm_tables[topic] = AlarmTableViewWidget(
                self.alarm_trees[topic].treeModel, self.kafka_producer, topic, AlarmTableType.ACTIVE, self.plot_pv
            )
            self.acknowledged_alarm_tables[topic] = AlarmTableViewWidget(
                self.alarm_trees[topic].treeModel, self.kafka_producer, topic, AlarmTableType.ACKNOWLEDGED, self.plot_pv
            )

            # Sync the column widths in the active and acknowledged tables, resizing a column will effect both tables.
            # Managing the width of tables is done with their headers (QHeaderViews).
            self.acknowledged_alarm_tables[topic].alarmView.horizontalHeader().sectionResized.connect(
                lambda logicalIndex, oldSize, newSize: self.active_alarm_tables[topic]
                .alarmView.horizontalHeader()
                .resizeSection(logicalIndex, newSize)
            )

            self.active_alarm_tables[topic].alarmView.horizontalHeader().sectionResized.connect(
                lambda logicalIndex, oldSize, newSize: self.acknowledged_alarm_tables[topic]
                .alarmView.horizontalHeader()
                .resizeSection(logicalIndex, newSize)
            )
        if len(topics) > 1:
            self.alarm_select_combo_box.addItem("All")

        self.alarm_update_signal.connect(self.update_tree)
        self.alarm_update_signal.connect(self.update_table)

        self.server_status_timer = QTimer()  # Periodically checks to ensure connection to the alarm server is active
        self.server_status_timer.timeout.connect(self.check_server_status)
        self.server_status_timer.start(3000)
        self.alarm_server_connected = True
        self.alarm_server_disconnected_banner = QLabel("WARNING: No connection to alarm server, data may be stale")
        self.alarm_server_disconnected_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alarm_server_disconnected_banner.setStyleSheet("background-color: red")
        self.alarm_server_disconnected_banner.setMaximumHeight(40)
        self.alarm_server_disconnected_banner.hide()

        self.kafka_reader = KafkaReader(topics, bootstrap_servers, self.process_message)
        self.processing_thread = QThread()
        self.kafka_reader.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.kafka_reader.run)
        self.processing_thread.start()

        self.axis_count = 0
        self.widget = QWidget()
        self.setCentralWidget(self.widget)
        self.horizontal_splitter = QSplitter(self)

        # The active and acknowledged alarm tables will appear in their own right-hand vertical split
        self.vertical_splitter = QSplitter(self)
        self.vertical_splitter.setOrientation(Qt.Orientation.Vertical)
        self.vertical_splitter.addWidget(self.active_alarm_tables[topics[1]])
        self.vertical_splitter.addWidget(self.acknowledged_alarm_tables[topics[0]])
        self.horizontal_splitter.addWidget(self.alarm_trees[topics[0]])
        self.horizontal_splitter.addWidget(self.vertical_splitter)

        # Adjust the relative sizes between widgets
        self.horizontal_splitter.setStretchFactor(0, 2)
        self.horizontal_splitter.setStretchFactor(1, 5)
        self.vertical_splitter.setStretchFactor(0, 3)
        self.vertical_splitter.setStretchFactor(1, 2)

        self.alarm_selector_layout = QVBoxLayout()
        self.widget.setLayout(self.alarm_selector_layout)
        self.alarm_selector_layout.addWidget(self.alarm_server_disconnected_banner)
        self.alarm_selector_layout.addWidget(self.alarm_select_combo_box)
        self.alarm_selector_layout.addWidget(self.horizontal_splitter)

    def update_tree(self, alarm_config_name: str, *args) -> None:
        """
         A slot for updating an alarm tree

        Parameters
        ----------
        alarm_config_name : str
            The name associated with the tree to update
        """
        self.alarm_trees[alarm_config_name].treeModel.update_item(*args)
        self.alarm_trees['All'].treeModel.update_item(*args)

    def update_table(
        self,
        alarm_config_name: str,
        name: str,
        path: str,
        severity: AlarmSeverity,
        status: str,
        time,
        value: str,
        pv_severity: AlarmSeverity,
        pv_status: str,
    ) -> None:
        """
        A slot for updating an alarm table
        """
        '''
        print ("Alarm config name: ", alarm_config_name)
        if alarm_config_name == "LCLS":
            self.active_alarm_tables[alarm_config_name].alarmModel.append(AlarmItem("NOLAN"))
            self.active_alarm_tables['LCLS'].alarmModel.append(self.active_alarm_tables['CRYO'].alarmModel.alarm_items.items()[1])
            #print (self.active_alarm_tables['CRYO'].alarmModel.alarm_items.items())
            #for _, currAlarmItem in self.active_alarm_tables['CRYO'].alarmModel.alarm_items.items():
                #print ("Appending curr alarm item: ", currAlarmItem)
                #self.active_alarm_tables['LCLS'].alarmModel.append(currAlarmItem)
        '''
        if status == "Disabled":
            self.active_alarm_tables[alarm_config_name].alarmModel.remove_row(name)
            self.acknowledged_alarm_tables[alarm_config_name].alarmModel.remove_row(name)

            self.active_alarm_tables['All'].alarmModel.remove_row(name)
            self.acknowledged_alarm_tables['All'].alarmModel.remove_row(name)
        elif severity in (
            AlarmSeverity.INVALID_ACK,
            AlarmSeverity.MAJOR_ACK,
            AlarmSeverity.MINOR_ACK,
            AlarmSeverity.UNDEFINED_ACK,
        ):
            self.active_alarm_tables[alarm_config_name].alarmModel.remove_row(name)
            self.acknowledged_alarm_tables[alarm_config_name].alarmModel.update_row(
                name, path, severity, status, time, value, pv_severity, pv_status, self.descriptions.get(path, "")
            )

            self.active_alarm_tables['All'].alarmModel.remove_row(name)
            self.acknowledged_alarm_tables['All'].alarmModel.update_row(
                name, path, severity, status, time, value, pv_severity, pv_status, self.descriptions.get(path, "")
            )
        elif severity == AlarmSeverity.OK:
            self.active_alarm_tables[alarm_config_name].alarmModel.remove_row(name)
            self.acknowledged_alarm_tables[alarm_config_name].alarmModel.remove_row(name)

            self.active_alarm_tables['All'].alarmModel.remove_row(name)
            self.acknowledged_alarm_tables['All'].alarmModel.remove_row(name)
        else:
            if name in self.acknowledged_alarm_tables[alarm_config_name].alarmModel.alarm_items:
                self.acknowledged_alarm_tables[alarm_config_name].alarmModel.remove_row(name)
                
                self.acknowledged_alarm_tables['All'].alarmModel.remove_row(name)
            self.active_alarm_tables[alarm_config_name].alarmModel.update_row(
                name, path, severity, status, time, value, pv_severity, pv_status, self.descriptions.get(path, "")
            )
            self.active_alarm_tables['All'].alarmModel.update_row(
                name, path, severity, status, time, value, pv_severity, pv_status, self.descriptions.get(path, "")
            )

    def change_display(self, alarm_config_name: str) -> None:
        """
        Changes the current tree/table being displayed in the UI

        Parameters
        ----------
        alarm_config_name : str
            The name associated with the tree and table to be displayed
        """
        alarm_tree_to_swap = None
        active_alarm_table_to_swap = None
        ack_alarm_table_to_swap = None
        
        if alarm_config_name not in self.alarm_trees and alarm_config_name != "All":
            return
        elif alarm_config_name == "All":
            alarm_tree_to_swap = self.all_alarms_tree
            active_alarm_table_to_swap = self.all_active_alarms_table
            ack_alarm_table_to_swap = self.all_acknowledged_alarms_table
        else: 
            alarm_tree_to_swap = self.alarm_trees[alarm_config_name]
            active_alarm_table_to_swap = self.active_alarm_tables[alarm_config_name]
            ack_alarm_table_to_swap = self.acknowledged_alarm_tables[alarm_config_name]
        
        self.horizontal_splitter.replaceWidget(0, alarm_tree_to_swap)
        self.vertical_splitter.replaceWidget(0, active_alarm_table_to_swap)
        self.vertical_splitter.replaceWidget(1, ack_alarm_table_to_swap)
        self.current_alarm_config = alarm_config_name

    def process_message(self, message: ConsumerRecord):
        """
        Process a message received from kafka and update the display widgets accordingly

        Parameters
        ----------
        message : ConsumerRecord
            A message received from the kafka queue indicating a change made to the topic we are listening to
        """
        key = message.key
        values = message.value
        if key.startswith("config"):  # [7:] because config:
            logger.debug(f"Processing CONFIG message with key: {message.key} and values: {message.value}")
            alarm_config_name = key.split("/")[1]
            #print ("!! alarm config name: ", alarm_config_name)
            if values is not None:
                # Start from 7: to read past the 'config:' part of the key
                #print ("XX@#@: ", message.key[7:])
                self.alarm_trees[alarm_config_name].treeModel.update_model(message.key[7:], values)
                self.alarm_trees['All'].treeModel.update_model(message.key[7:], values)
                if "description" in values:
                    self.descriptions[message.key[7:]] = values.get("description")
            else:  # A null message indicates this item should be removed from the tree
                self.alarm_trees[alarm_config_name].treeModel.remove_item(message.key[7:])
                self.active_alarm_tables[alarm_config_name].alarmModel.remove_row(message.key[7:].split("/")[-1])
                self.acknowledged_alarm_tables[alarm_config_name].alarmModel.remove_row(message.key[7:].split("/")[-1])

                self.alarm_trees['All'].treeModel.remove_item(message.key[7:])
                self.active_alarm_tables['All'].alarmModel.remove_row(message.key[7:].split("/")[-1])
                self.acknowledged_alarm_tables['All'].alarmModel.remove_row(message.key[7:].split("/")[-1])
        elif key.startswith("command"):
            pass  # Nothing for us to do
        elif key.startswith("state"):
            pv = message.key.split("/")[-1]
            alarm_config_name = key.split("/")[1]
            self.last_received_update_time[alarm_config_name] = datetime.now()
            self.last_received_update_time['All'] = datetime.now()
            logger.debug(f"Processing STATE message with key: {message.key} and values: {message.value}")
            if values is None:
                self.active_alarm_tables[alarm_config_name].alarmModel.remove_row(message.key[6:].split("/")[-1])
                self.acknowledged_alarm_tables[alarm_config_name].alarmModel.remove_row(message.key[6:].split("/")[-1])

                self.active_alarm_tables['All'].alarmModel.remove_row(message.key[6:].split("/")[-1])
                self.acknowledged_alarm_tables['All'].alarmModel.remove_row(message.key[6:].split("/")[-1])
                return
            if len(values) <= 2:
                return  # This is the heartbeat message which doesn't get recorded
            time = ""
            if "time" in values:
                time = datetime.fromtimestamp(values["time"]["seconds"])
            self.alarm_update_signal.emit(
                alarm_config_name,
                pv,
                message.key[6:],
                AlarmSeverity(values["severity"]),
                values["message"],
                time,
                values["value"],
                AlarmSeverity(values["current_severity"]),
                values["current_message"],
            )

    def check_server_status(self):
        """Ensure that our client is still receiving alarm updates, display a warning if not"""
        if (datetime.now() - self.last_received_update_time[self.current_alarm_config]).seconds > 25:
            # The alarm server will always send a heartbeat message confirming it is still up
            # every 10 seconds even if no alarm has changed its status
            self.alarm_server_connected = False
            self.alarm_server_disconnected_banner.show()
        elif not self.alarm_server_connected:
            self.alarm_server_connected = True
            self.alarm_server_disconnected_banner.hide()

    def create_archiver_search_widget(self):
        """Create and show the widget for sending search requests to archiver appliance"""
        if not hasattr(self, "search_widget"):
            self.search_widget = ArchiveSearchWidget()
        self.search_widget.show()

    def create_plot_widget(self, pv: Optional[str] = None):
        """
        Create a widget for display a PyDMArchiverTimePlot of a PV

        Parameters
        ----------
        pv : str, optional
            The name of the pv to plot. If not specified, then the plot will start out empty.
        """
        plot = PyDMArchiverTimePlot()
        plot.setTimeSpan(300)
        if pv:
            plot.addYChannel(y_channel=f"ca://{pv}", name=pv, yAxisName=f"Axis {self.axis_count}", useArchiveData=True)
            self.axis_count += 1

        def drag_enter_event(ev):
            ev.accept()

        def drag_move_event(ev):
            ev.accept()

        def drop_event(ev):
            ev.accept()
            if ev.mimeData().text():
                pv = ev.mimeData().text()
                plot.addYChannel(
                    y_channel=f"ca://{pv}", name=pv, yAxisName=f"Axis {self.axis_count}", useArchiveData=True
                )
                self.axis_count += 1

        plot.setAcceptDrops(True)
        plot.dragEnterEvent = drag_enter_event
        plot.dragMoveEvent = drag_move_event
        plot.dropEvent = drop_event
        plot.axis_count = 0
        plot.show()

    @Slot(str)
    def plot_pv(self, pv: Optional[str] = None):
        """Create a plot and associate it with the input PV if present"""
        self.create_plot_widget(pv)

    def exit_application(self):
        """Close out the entire application"""
        self.close()
