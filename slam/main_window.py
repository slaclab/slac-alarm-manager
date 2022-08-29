import json
import logging
from datetime import datetime
from kafka.consumer.fetcher import ConsumerRecord
from kafka import KafkaProducer
from pydm.widgets import PyDMArchiverTimePlot
from qtpy.QtCore import QThread, Signal, Slot
from qtpy.QtWidgets import QAction, QApplication, QMainWindow, QTabWidget
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

    topic : str
        The kafka topic to listen to
    bootstrap_servers : List[str]
        A list containing one or more urls for kafka bootstrap servers
    """

    alarm_update_signal = Signal(str, str, AlarmSeverity, str, datetime, str, AlarmSeverity, str)

    def __init__(self, topic: str, bootstrap_servers: List[str]):
        super().__init__()

        self.kafka_producer = KafkaProducer(bootstrap_servers=bootstrap_servers,
                                            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                                            key_serializer=lambda x: x.encode('utf-8'))
        self.topic = topic
        self.clipboard = QApplication.clipboard()

        self.main_menu = self.menuBar()
        self.file_menu = self.main_menu.addMenu('File')
        self.applications_menu = self.main_menu.addMenu('Applications')
        self.exit_action = QAction('Exit')
        self.exit_action.triggered.connect(self.exit_application)
        self.file_menu.addAction(self.exit_action)
        self.show_alarm_table_action = QAction('Alarm Table')
        self.show_alarm_table_action.triggered.connect(self.display_alarm_table_widget)
        self.archiver_search_action = QAction('Archiver Search')
        self.archiver_search_action.triggered.connect(self.create_archiver_search_widget)
        self.empty_plot_action = QAction('Time Plot')
        self.empty_plot_action.triggered.connect(self.create_plot_widget)
        self.applications_menu.addAction(self.show_alarm_table_action)
        self.applications_menu.addAction(self.archiver_search_action)
        self.applications_menu.addAction(self.empty_plot_action)

        self.tab_widget = QTabWidget()

        self.tree_view_widget = AlarmTreeViewWidget(self.kafka_producer, self.topic, self.plot_pv)
        self.tab_widget.addTab(self.tree_view_widget, 'Alarm Tree')

        self.table_view_widget = AlarmTableViewWidget(self.tree_view_widget.treeModel, self.kafka_producer,
                                                      self.topic, self.plot_pv)
        self.table_view_widget.hide()

        self.alarm_update_signal.connect(self.table_view_widget.update_tables)
        self.alarm_update_signal.connect(self.tree_view_widget.treeModel.update_item)

        self.kafka_reader = KafkaReader(topic, bootstrap_servers, self.process_message)
        self.processing_thread = QThread()
        self.kafka_reader.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.kafka_reader.run)
        self.processing_thread.start()

        self.axis_count = 0
        self.setCentralWidget(self.tab_widget)

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
            if values is not None:
                # Start from 7: to read past the 'config:' part of the key
                self.tree_view_widget.treeModel.update_model(message.key[7:], values)
            else:  # A null message indicates this item should be removed from the tree
                self.tree_view_widget.treeModel.remove_item(message.key[7:])
        elif key.startswith('command'):
            pass  # Nothing for us to do
        elif values is not None and (len(values) <= 2):
            pass
        elif key.startswith('state') and values is not None:
            pv = message.key.split('/')[-1]
            logger.debug(f'Processing STATE message with key: {message.key} and values: {message.value}')
            time = ''
            if 'time' in values:
                time = datetime.fromtimestamp(values['time']['seconds'])
            self.alarm_update_signal.emit(pv, message.key[6:], AlarmSeverity(values['severity']), values['message'],
                                          time, values['value'], AlarmSeverity(values['current_severity']),
                                          values['current_message'])

    def display_alarm_table_widget(self):
        """ Show the alarm table """
        self.table_view_widget.show()

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
