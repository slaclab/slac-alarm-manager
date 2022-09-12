import json
import logging
from datetime import datetime
from kafka.consumer.fetcher import ConsumerRecord
from kafka import KafkaProducer
from pydm.widgets import PyDMArchiverTimePlot
from qtpy.QtCore import Qt, QThread, Signal, Slot
from qtpy.QtWidgets import QAction, QApplication, QComboBox, QMainWindow, QSplitter, QTabWidget, QVBoxLayout, QWidget
from typing import List, Optional
from .alarm_item import AlarmSeverity
from .alarm_table_view import AlarmTableViewWidget
from .alarm_tree_view import AlarmTreeViewWidget
from .archive_search import ArchiveSearchWidget
from .kafka_reader import KafkaReader

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

        self.kafka_producer = KafkaProducer(bootstrap_servers=bootstrap_servers,
                                            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                                            key_serializer=lambda x: x.encode('utf-8'))
        self.topics = topics
        self.clipboard = QApplication.clipboard()

        self.main_menu = self.menuBar()
        self.file_menu = self.main_menu.addMenu('File')
        self.applications_menu = self.main_menu.addMenu('Applications')
        self.exit_action = QAction('Exit')
        self.exit_action.triggered.connect(self.exit_application)
        self.file_menu.addAction(self.exit_action)
        self.archiver_search_action = QAction('Archiver Search')
        self.archiver_search_action.triggered.connect(self.create_archiver_search_widget)
        self.empty_plot_action = QAction('Time Plot')
        self.empty_plot_action.triggered.connect(self.create_plot_widget)
        self.applications_menu.addAction(self.archiver_search_action)
        self.applications_menu.addAction(self.empty_plot_action)

        # A combo box for choosing which alarm tree/table to display
        self.alarm_select_combo_box = QComboBox(self)
        self.alarm_select_combo_box.setFixedSize(120, 30)
        self.alarm_select_combo_box.currentTextChanged.connect(self.change_display)
        self.current_alarm_config = topics[0]
        self.horizontal_splitter = QSplitter(self)

        self.alarm_trees = dict()
        self.alarm_tables = dict()

        # Create a separate tree and table widget for each alarm configuration we are monitoring
        for topic in topics:
            self.alarm_select_combo_box.addItem(topic)
            self.alarm_trees[topic] = AlarmTreeViewWidget(self.kafka_producer, topic, self.plot_pv)
            self.alarm_tables[topic] = AlarmTableViewWidget(self.alarm_trees[topic].treeModel, self.kafka_producer,
                                                            topic, self.plot_pv)

        self.alarm_update_signal.connect(self.update_tree)
        self.alarm_update_signal.connect(self.update_table)

        self.kafka_reader = KafkaReader(topics, bootstrap_servers, self.process_message)
        self.processing_thread = QThread()
        self.kafka_reader.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.kafka_reader.run)
        self.processing_thread.start()

        self.axis_count = 0
        self.widget = QWidget()
        self.setCentralWidget(self.widget)
        self.horizontal_splitter.addWidget(self.alarm_trees[topics[0]])
        self.horizontal_splitter.addWidget(self.alarm_tables[topics[0]])
        self.alarm_selector_layout = QVBoxLayout()
        self.widget.setLayout(self.alarm_selector_layout)
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

    def update_table(self, alarm_config_name: str, *args) -> None:
        """
        A slot for updating an alarm table

        Parameters
        ----------
        alarm_config_name : str
            The name associated with the table to update
        """
        self.alarm_tables[alarm_config_name].update_tables(*args)

    def change_display(self, alarm_config_name: str) -> None:
        """
        Changes the current tree/table being displayed in the UI

        Parameters
        ----------
        alarm_config_name : str
            The name associated with the tree and table to be displayed
        """
        if alarm_config_name not in self.alarm_trees:
            return
        self.horizontal_splitter.replaceWidget(0, self.alarm_trees[alarm_config_name])
        self.horizontal_splitter.replaceWidget(1, self.alarm_tables[alarm_config_name])
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
        if key.startswith('config'):  # [7:] because config:
            logger.debug(f'Processing CONFIG message with key: {message.key} and values: {message.value}')
            alarm_config_name = key.split('/')[1]
            if values is not None:
                # Start from 7: to read past the 'config:' part of the key
                self.alarm_trees[alarm_config_name].treeModel.update_model(message.key[7:], values)
            else:  # A null message indicates this item should be removed from the tree
                self.alarm_trees[alarm_config_name].treeModel.remove_item(message.key[7:])
                self.alarm_tables[alarm_config_name].alarmModel.remove_row(message.key[7:].split('/')[-1])
                self.alarm_tables[alarm_config_name].acknowledgedAlarmsModel.remove_row(message.key[7:].split('/')[-1])
        elif key.startswith('command'):
            pass  # Nothing for us to do
        elif values is not None and (len(values) <= 2):
            pass
        elif key.startswith('state') and values is not None:
            pv = message.key.split('/')[-1]
            alarm_config_name = key.split('/')[1]
            logger.debug(f'Processing STATE message with key: {message.key} and values: {message.value}')
            time = ''
            if 'time' in values:
                time = datetime.fromtimestamp(values['time']['seconds'])
            self.alarm_update_signal.emit(alarm_config_name, pv, message.key[6:], AlarmSeverity(values['severity']),
                                          values['message'], time, values['value'],
                                          AlarmSeverity(values['current_severity']), values['current_message'])

    def create_archiver_search_widget(self):
        """ Create and show the widget for sending search requests to archiver appliance """
        if not hasattr(self, 'search_widget'):
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
            plot.addYChannel(y_channel=f'ca://{pv}', name=pv, yAxisName=f'Axis {self.axis_count}', useArchiveData=True)
            self.axis_count += 1

        def drag_enter_event(ev):
            ev.accept()

        def drag_move_event(ev):
            ev.accept()

        def drop_event(ev):
            ev.accept()
            if ev.mimeData().text():
                pv = ev.mimeData().text()
                plot.addYChannel(y_channel=f'ca://{pv}', name=pv, yAxisName=f'Axis {self.axis_count}',
                                 useArchiveData=True)
                self.axis_count += 1

        plot.setAcceptDrops(True)
        plot.dragEnterEvent = drag_enter_event
        plot.dragMoveEvent = drag_move_event
        plot.dropEvent = drop_event
        plot.axis_count = 0
        plot.show()

    @Slot(str)
    def plot_pv(self, pv: Optional[str] = None):
        """ Create a plot and associate it with the input PV if present """
        self.create_plot_widget(pv)

    def exit_application(self):
        """ Close out the entire application """
        self.close()
