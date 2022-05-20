import json
import sys
from datetime import datetime
from kafka.consumer.fetcher import ConsumerRecord
from kafka import KafkaProducer
from pydm.widgets import PyDMArchiverTimePlot
from qtpy.QtCore import QThread, Signal, Slot
from qtpy.QtWidgets import QAction, QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
from typing import Optional
from .alarm_table_view import AlarmTableViewWidget
from .alarm_tree_view import AlarmTreeViewWidget
from .archive_search import ArchiveSearchWidget
from .kafka_reader import KafkaReader


class AlarmHandlerMainWindow(QMainWindow):
    """ 
    The AlarmHandlerMainWindow is the main top-level widget for displaying and interacting with alarms. 
    
    Parameters
    ----------

    topic : str
        The kafka topic to listen to (TODO: Convert to a list)
    """

    alarm_update_signal = Signal(str, str, str, str, datetime, str, str, str)

    def __init__(self, topic: str):
        super().__init__()

        self.kafka_producer = KafkaProducer(bootstrap_servers=['localhost:9092'],
                                            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                                            key_serializer=lambda x: x.encode('utf-8'))
        self.topic = topic
        self.clipboard = QApplication.clipboard()

        self.layout = QVBoxLayout(self)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_widget.setLayout(self.layout)

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
        # self.setCentralWidget(self.tab_widget)
        self.layout.addWidget(self.tab_widget)

        self.tree_view_widget = AlarmTreeViewWidget(self.kafka_producer, self.topic, self.plot_pv)
        #        self.layout.addWidget(self.tree_view_widget)
        self.tab_widget.addTab(self.tree_view_widget, 'Alarm Tree')

        self.table_view_widget = AlarmTableViewWidget(self.tree_view_widget.treeModel, self.kafka_producer,
                                                      self.topic, self.plot_pv)
        self.table_view_widget.hide()
        # self.tab_widget.addTab(self.table_view_widget, 'Alarm Table')

        self.alarm_update_signal.connect(self.table_view_widget.update_tables)
        self.alarm_update_signal.connect(self.tree_view_widget.treeModel.update_item)

        self.plots = []

        self.kafka_reader = KafkaReader(topic, self.process_message)
        self.processing_thread = QThread()
        self.kafka_reader.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.kafka_reader.run)
        self.processing_thread.start()

        self.axis_count = 0

    # Processing CONFIG message with key: config:/CRYO/CRYO/Global/Auxilaries and Utilities/Analyzers/CANL:CP12:3801:ALM and values: {'user': 'r\oot', 'host': 'b4f2a0844c4e', 'description': 'CANL:CP12:3801:ALM', 'enabled': False, 'latching': False, 'annunciating': False, 'guidance': \[{'title': 'Super', 'details': 'Quiet'}]}
    # Processing STATE message with key: state:/CRYO/CRYO/Global/Auxilaries and Utilities/Analyzers/CANL:CP12:3801:ALM and values: {'severity': \'OK', 'message': 'Disabled', 'value': '', 'time': {'seconds': 1646335579, 'nano': 701864000}, 'current_severity': 'OK', 'current_message': \'OK'}
    def process_message(self, message: ConsumerRecord):
        """ Process a message received from kafka """
        key = message.key
        values = message.value
        if key.startswith('config'):  # [7:] because config:
            #            print(f'Processing CONFIG message with key: {message.key} and values: {message.value}')
            if values is not None:
                self.tree_view_widget.treeModel.update_model(message.key[7:], values)
            else:  # A null message indicates this item should be removed from the tree
                self.tree_view_widget.treeModel.remove_an_item(message.key[7:])
        elif key.startswith('command'):
            pass  # Nothing to do
        elif values is not None and (len(values) <= 2):
            pass
        elif key.startswith('state') and values is not None:
            pv = message.key.split('/')[-1]
            # print(f'STATE message key is: {message.key} and our slice is: {message.key[6:]}')
            # [6:] because state:
            time = ''
            if 'time' in values:
                time = datetime.fromtimestamp(values['time']['seconds'])
            self.alarm_update_signal.emit(pv, message.key[6:], values['severity'], values['message'], time,
                                          values['value'], values['current_severity'], values['current_message'])

    def display_alarm_table_widget(self):
        self.table_view_widget.show()

    def create_archiver_search_widget(self):
        if not hasattr(self, 'search_widget'):
            self.search_widget = ArchiveSearchWidget()
        self.search_widget.show()

    def create_plot_widget(self, pv: Optional[str] = None):
        plot = PyDMArchiverTimePlot()
        plot.removeAxis('left')
        plot.setTimeSpan(300)
        if pv:
            plot.addYChannel(y_channel=f'ca://{pv}', name=pv, yAxisName=f'Axis {self.axis_count}', useArchiveData=True)
            self.axis_count += 1

        plot.setAcceptDrops(True)
        plot.dragEnterEvent = self.drag_enter_event
        plot.dragMoveEvent = self.drag_move_event

        def dropper(ev):
            ev.accept()
            if ev.mimeData().text():
                pv = ev.mimeData().text()
                plot.addYChannel(y_channel=f'ca://{pv}', name=pv, yAxisName=f'Axis {self.axis_count}',
                                 useArchiveData=True)
                self.axis_count += 1

        plot.dropEvent = dropper
        plot.axis_count = 0
        self.plots.append(plot)
        plot.show()

    def exit_application(self):
        self.close()

    def drag_enter_event(self, ev):  # TODO: Move this
        ev.accept()

    def drag_move_event(self, ev):
        ev.accept()

    def drop_event(self, ev):  # TODO: Move this
        ev.accept()
        if ev.mimeData().text():
            pv = ev.mimeData().text()
            self.addYChannel(y_channel=f'ca://{pv}', name=pv, yAxisName=f'Axis {self.axis_count}', useArchiveData=True)
            self.axis_count += 1

    @Slot(str)
    def plot_pv(self, pv: Optional[str] = None):
        self.create_plot_widget(pv)


if __name__ == "__main__":
    app = QApplication([])

    widget = AlarmHandlerMainWindow()
    widget.resize(1035, 600)
    widget.setWindowTitle('SLAC Alarm Manager')
    widget.show()

    sys.exit(app.exec())
