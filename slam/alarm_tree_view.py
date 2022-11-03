import getpass
import socket
from functools import partial
from kafka.producer import KafkaProducer
from pydm.display import load_file
from qtpy.QtCore import QModelIndex, QPoint, Qt, Signal
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QAbstractItemView, QAction, QApplication, QMenu, QTreeView, QVBoxLayout, QWidget
from typing import Callable
from .alarm_configuration_widget import AlarmConfigurationWidget
from .alarm_item import AlarmSeverity
from .alarm_tree_model import AlarmItemsTreeModel


class AlarmTreeViewWidget(QWidget):
    """
    The TreeViewWidget is a collection of everything needed to display and interact with the alarm tree.

    Parameters
    ----------
    kafka_producer : KafkaProducer
        The producer for sending state and command updates to the kafka cluster

    topic : str
        The kafka topic to write update messages to

    plot_slot : Callable
        The function to invoke for plotting a PV
    """

    plot_signal = Signal(str)

    def __init__(self, kafka_producer: KafkaProducer, topic: str, plot_slot: Callable):
        super().__init__()

        self.kafka_producer = kafka_producer
        self.topic = topic
        self.plot_slot = plot_slot
        self.plot_signal.connect(self.plot_slot)
        self.clipboard = QApplication.clipboard()

        self.setFont(QFont('Arial', 12))
        self.layout = QVBoxLayout(self)
        self.treeModel = AlarmItemsTreeModel()
        self.tree_view = QTreeView(self)
        self.tree_view.setProperty("showDropIndicator", False)
        self.tree_view.setDragDropOverwriteMode(False)
        self.tree_view.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tree_view.setSortingEnabled(False)
        self.tree_view.setExpandsOnDoubleClick(False)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.setHeaderHidden(True)
        self.tree_view.customContextMenuRequested.connect(self.tree_menu)

        self.tree_view.doubleClicked.connect(self.create_alarm_configuration_widget)

        self.context_menu = QMenu(self)
        self.acknowledge_action = QAction('Acknowledge')
        self.unacknowledge_action = QAction('Unacknowledge')
        self.copy_action = QAction('Copy PV To Clipboard')
        self.plot_action = QAction('Draw Plot')
        self.enable_action = QAction('Enable')
        self.disable_action = QAction('Disable')

        self.acknowledge_action.triggered.connect(self.send_acknowledgement)
        self.unacknowledge_action.triggered.connect(self.send_unacknowledgement)
        self.plot_action.triggered.connect(self.plot_pv)
        self.copy_action.triggered.connect(self.copy_to_clipboard)
        self.enable_action.triggered.connect(self.enable_alarm)
        self.disable_action.triggered.connect(self.disable_alarm)

        self.tree_view.setModel(self.treeModel)

        self.layout.addWidget(self.tree_view)

    def tree_menu(self, pos: QPoint) -> None:
        """ Creates and displays the context menu to be displayed upon right clicking on an alarm item """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            if alarm_item.is_leaf():
                self.context_menu = QMenu(self)
                if alarm_item.alarm_severity in (AlarmSeverity.MINOR, AlarmSeverity.MAJOR,
                                                 AlarmSeverity.INVALID, AlarmSeverity.UNDEFINED):
                    self.context_menu.addAction(self.acknowledge_action)
                elif alarm_item.alarm_severity in (AlarmSeverity.MINOR_ACK, AlarmSeverity.MAJOR_ACK,
                                                   AlarmSeverity.INVALID_ACK, AlarmSeverity.UNDEFINED_ACK):
                    self.context_menu.addAction(self.unacknowledge_action)
                self.context_menu.addAction(self.copy_action)
                self.context_menu.addAction(self.plot_action)
            else:  # Parent Node
                leaf_nodes = self.treeModel.get_all_leaf_nodes(alarm_item)
                add_acknowledge_action = False
                add_unacknowledge_action = False
                for leaf in leaf_nodes:
                    if leaf.alarm_severity is not None and leaf.alarm_severity in (
                            AlarmSeverity.MINOR, AlarmSeverity.MAJOR, AlarmSeverity.INVALID, AlarmSeverity.UNDEFINED):
                        # As long as one item needs acknowledging we will display the acknowledge action
                        add_acknowledge_action = True
                        break
                    elif leaf.alarm_severity is not None and leaf.alarm_severity in (
                            AlarmSeverity.MINOR_ACK, AlarmSeverity.MAJOR_ACK,
                            AlarmSeverity.INVALID_ACK, AlarmSeverity.UNDEFINED_ACK):
                        add_unacknowledge_action = True
                self.context_menu = QMenu(self)
                if add_acknowledge_action:  # This always should take precedence over unacknowledge
                    self.context_menu.addAction(self.acknowledge_action)
                elif add_unacknowledge_action:
                    self.context_menu.addAction(self.unacknowledge_action)
            self.context_menu.addAction(self.enable_action)
            self.context_menu.addAction(self.disable_action)
            if alarm_item.displays:
                for display in alarm_item.displays:
                    display_action = QAction(display['title'])
                    display_action.triggered.connect(partial(self.launch_pydm_display, display['details']))
                    self.context_menu.addAction(display_action)
            self.context_menu.popup(self.mapToGlobal(pos))

    def create_alarm_configuration_widget(self, index: QModelIndex) -> None:
        """ Create and display the alarm configuration widget for the alarm item with the input index """
        alarm_item = self.treeModel.getItem(index)
        alarm_config_window = AlarmConfigurationWidget(alarm_item=alarm_item, kafka_producer=self.kafka_producer,
                                                       topic=self.topic, parent=self)
        alarm_config_window.show()

    def copy_to_clipboard(self) -> None:
        """ Copy the selected PV to the user's clipboard """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            self.clipboard.setText(alarm_item.name, mode=self.clipboard.Selection)
            self.clipboard.setText(alarm_item.name, mode=self.clipboard.Clipboard)

    def plot_pv(self) -> None:
        """ Send off the signal for plotting a PV """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            self.plot_signal.emit(alarm_item.name)

    @staticmethod
    def launch_pydm_display(file_path: str) -> None:
        """
        Launch a PyDM display associated with an alarm

        Parameters
        ----------
        file_path : str
            The path to the pydm file to display
        """
        load_file(file_path)

    def send_acknowledgement(self) -> None:
        """ Send the acknowledge action by sending it to the command topic in the kafka cluster """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            username = getpass.getuser()
            hostname = socket.gethostname()
            if alarm_item.is_leaf():
                for alarm_path in self.treeModel.added_paths[alarm_item.name]:
                    self.kafka_producer.send(self.topic + 'Command',
                                             key=f'command:{alarm_path}',
                                             value={'user': username, 'host': hostname, 'command': 'acknowledge'})
            else:
                all_leaf_nodes = self.treeModel.get_all_leaf_nodes(alarm_item)
                for leaf in all_leaf_nodes:
                    if leaf.is_in_active_alarm_state():
                        for alarm_path in self.treeModel.added_paths[leaf.name]:
                            self.kafka_producer.send(self.topic + 'Command',
                                                     key=f'command:{alarm_path}',
                                                     value={'user': username, 'host': hostname, 'command': 'acknowledge'})

    def send_unacknowledgement(self) -> None:
        """ Send the un-acknowledge action by sending it to the command topic in the kafka cluster """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            username = getpass.getuser()
            hostname = socket.gethostname()
            if alarm_item.is_leaf():
                for alarm_path in self.treeModel.added_paths[alarm_item.name]:
                    self.kafka_producer.send(self.topic + 'Command',
                                             key=f'command:{alarm_path}',
                                             value={'user': username, 'host': hostname, 'command': 'unacknowledge'})
            else:
                all_leaf_nodes = self.treeModel.get_all_leaf_nodes(alarm_item)
                for leaf in all_leaf_nodes:
                    if not leaf.is_in_active_alarm_state():
                        for alarm_path in self.treeModel.added_paths[leaf.name]:
                            self.kafka_producer.send(self.topic + 'Command',
                                                     key=f'command:{alarm_path}',
                                                     value={'user': username, 'host': hostname, 'command': 'unacknowledge'})

    def enable_alarm(self) -> None:
        """ Enable the selected alarm. If the selected item is a parent node, enable all its children """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            username = getpass.getuser()
            hostname = socket.gethostname()
            if alarm_item.is_leaf() and not alarm_item.is_enabled():
                for alarm_path in self.treeModel.added_paths[alarm_item.name]:
                    self.kafka_producer.send(self.topic,
                                             key=f'config:{alarm_path}',
                                             value={'user': username, 'host': hostname,
                                                    'description': alarm_item.description, 'enabled': True,
                                                    'latching': alarm_item.latching,
                                                    'annunciating': alarm_item.annunciating})
            elif not alarm_item.is_leaf():
                all_leaf_nodes = self.treeModel.get_all_leaf_nodes(alarm_item)
                for leaf in all_leaf_nodes:
                    if not leaf.is_enabled():
                        for alarm_path in self.treeModel.added_paths[leaf.name]:
                            self.kafka_producer.send(self.topic,
                                                     key=f'config:{alarm_path}',
                                                     value={'user': username, 'host': hostname,
                                                            'description': leaf.description, 'enabled': True,
                                                            'latching': leaf.latching, 'annunciating': leaf.annunciating})

    def disable_alarm(self) -> None:
        """ Disable the selected alarm. If the selected item is a parent node, disable all its children """
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            username = getpass.getuser()
            hostname = socket.gethostname()
            if alarm_item.is_leaf() and alarm_item.is_enabled():
                for alarm_path in self.treeModel.added_paths[alarm_item.name]:
                    self.kafka_producer.send(self.topic,
                                             key=f'config:{alarm_path}',
                                             value={'user': username, 'host': hostname,
                                                    'description': alarm_item.description, 'enabled': False,
                                                    'latching': alarm_item.latching,
                                                    'annunciating': alarm_item.annunciating})
            elif not alarm_item.is_leaf():
                all_leaf_nodes = self.treeModel.get_all_leaf_nodes(alarm_item)
                for leaf in all_leaf_nodes:
                    if leaf.is_enabled():
                        for alarm_path in self.treeModel.added_paths[leaf.name]:
                            self.kafka_producer.send(self.topic,
                                                     key=f'config:{alarm_path}',
                                                     value={'user': username, 'host': hostname,
                                                            'description': leaf.description, 'enabled': False,
                                                            'latching': leaf.latching, 'annunciating': leaf.annunciating})
