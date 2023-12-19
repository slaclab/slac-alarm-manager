import getpass
import socket
import logging
from functools import partial
from kafka.producer import KafkaProducer
from pydm.display import load_file
from qtpy.QtCore import QModelIndex, QPoint, Qt, Signal
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QAbstractItemView, QAction, QApplication, QMenu, QTreeView, QVBoxLayout, QWidget
from typing import Callable, Dict, Optional
from .alarm_configuration_widget import AlarmConfigurationWidget
from .alarm_item import AlarmItem, AlarmSeverity
from .alarm_tree_model import AlarmItemsTreeModel
from .permissions import UserAction, can_take_action
from math import isnan
from epics import PV

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        kafka_producer: KafkaProducer,
        topic: str,
        plot_slot: Callable,
        enable_all_topic: bool = False,
        annunciate: bool = False,
    ):
        super().__init__()

        self.kafka_producer = kafka_producer
        self.topic = topic
        self.plot_slot = plot_slot
        self.plot_signal.connect(self.plot_slot)
        self.clipboard = QApplication.clipboard()
        self.annunciate = annunciate

        self.setFont(QFont("Arial", 12))
        self.layout = QVBoxLayout(self)

        self.treeModel = AlarmItemsTreeModel(annunciate, enable_all_topic)
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
        self.acknowledge_action = QAction("Acknowledge")
        self.unacknowledge_action = QAction("Unacknowledge")
        self.copy_action = QAction("Copy PV To Clipboard")
        self.plot_action = QAction("Draw Plot")
        self.enable_action = QAction("Enable")
        self.disable_action = QAction("Disable")
        self.guidance_menu = QMenu("Guidance")
        self.display_thresholds_menu = QMenu("Display Alarm Thresholds")
        self.display_actions = []
        self.guidance_objects = []

        self.acknowledge_action.triggered.connect(partial(self.send_action, True, None))
        self.unacknowledge_action.triggered.connect(partial(self.send_action, False, None))
        self.plot_action.triggered.connect(self.plot_pv)
        self.copy_action.triggered.connect(self.copy_to_clipboard)
        self.enable_action.triggered.connect(partial(self.send_action, None, True))
        self.disable_action.triggered.connect(partial(self.send_action, None, False))

        self.tree_view.setModel(self.treeModel)

        self.layout.addWidget(self.tree_view)

    def handleThresholdDisplay(self):
        indices = self.tree_view.selectedIndexes()
        index = indices[0]
        alarm_item = self.treeModel.getItem(index)
        hihi = high = low = lolo = -1

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

        # Make pv_object if first time item's threshold is requested
        if alarm_item.pv_object is None:
            # Update the values only when user requests them in right-click menu
            alarm_item.pv_object = PV(alarm_item.name, auto_monitor=False)

        # Do a get call we can quickly timeout, so if PV not-connected don't
        # need to wait for slower get_ctrlvars() call.
        # 0.1 is small arbitrary value, can be made larger if timing-out for
        # actually connected PVs.
        if alarm_item.pv_object.get(timeout=0.1) is None:
            return
        alarm_item_metadata = alarm_item.pv_object.get_ctrlvars()

        # Getting data can fail for some PV's, good metadata will always have a key for all 4 limits (nan if not set),
        # in this case don't display any threshold sub-menus
        if alarm_item_metadata is None:
            logger.warn(f"Can't connect to PV: {alarm_item.name}")
            self.display_thresholds_menu.clear()
            return
        elif len(alarm_item_metadata) > 0 and "upper_alarm_limit" not in alarm_item_metadata:
            logger.warn(f"No threshold data for PV: {alarm_item.name}")
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

    def tree_menu(self, pos: QPoint) -> None:
        """Creates and displays the context menu to be displayed upon right clicking on an alarm item"""
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            if alarm_item.is_leaf():
                self.context_menu = QMenu(self)
                if alarm_item.alarm_severity in (
                    AlarmSeverity.MINOR,
                    AlarmSeverity.MAJOR,
                    AlarmSeverity.INVALID,
                    AlarmSeverity.UNDEFINED,
                ):
                    self.context_menu.addAction(self.acknowledge_action)
                elif alarm_item.alarm_severity in (
                    AlarmSeverity.MINOR_ACK,
                    AlarmSeverity.MAJOR_ACK,
                    AlarmSeverity.INVALID_ACK,
                    AlarmSeverity.UNDEFINED_ACK,
                ):
                    self.context_menu.addAction(self.unacknowledge_action)
                self.context_menu.addAction(self.copy_action)
                self.context_menu.addAction(self.plot_action)
            else:  # Parent Node
                leaf_nodes = self.treeModel.get_all_leaf_nodes(alarm_item)
                add_acknowledge_action = False
                add_unacknowledge_action = False
                for leaf in leaf_nodes:
                    if leaf.alarm_severity is not None and leaf.alarm_severity in (
                        AlarmSeverity.MINOR,
                        AlarmSeverity.MAJOR,
                        AlarmSeverity.INVALID,
                        AlarmSeverity.UNDEFINED,
                    ):
                        # As long as one item needs acknowledging we will display the acknowledge action
                        add_acknowledge_action = True
                        break
                    elif leaf.alarm_severity is not None and leaf.alarm_severity in (
                        AlarmSeverity.MINOR_ACK,
                        AlarmSeverity.MAJOR_ACK,
                        AlarmSeverity.INVALID_ACK,
                        AlarmSeverity.UNDEFINED_ACK,
                    ):
                        add_unacknowledge_action = True
                self.context_menu = QMenu(self)
                if add_acknowledge_action:  # This always should take precedence over unacknowledge
                    self.context_menu.addAction(self.acknowledge_action)
                elif add_unacknowledge_action:
                    self.context_menu.addAction(self.unacknowledge_action)
            self.context_menu.addAction(self.enable_action)
            self.context_menu.addAction(self.disable_action)
            self.context_menu.addMenu(self.guidance_menu)
            self.context_menu.addMenu(self.display_thresholds_menu)
            self.display_thresholds_menu.aboutToShow.connect(self.handleThresholdDisplay)

            # Make the entires from the config-page appear when alarm in tree is right-clicked
            indices = self.tree_view.selectedIndexes()
            alarm_item = self.treeModel.getItem(indices[0])

            self.guidance_objects.clear()
            has_guidance = False
            if alarm_item.guidance is not None:
                guidance_count = 0
                for index, guidance_item in enumerate(alarm_item.guidance):
                    has_guidance = True
                    guidance_count += 1

                    curr_title = guidance_item["title"]
                    # sometimes people don't add titles to their guidance notes
                    if curr_title == "":
                        curr_title = "Guidance #" + str(guidance_count)
                    curr_details = guidance_item["details"]

                    title_menu = QMenu(curr_title)
                    self.detail_action = QAction(curr_details)
                    self.guidance_menu.addMenu(title_menu)
                    title_menu.addAction(self.detail_action)

                    self.guidance_objects.append(title_menu)
                    self.guidance_objects.append(self.detail_action)

            self.guidance_menu.menuAction().setVisible(has_guidance)

            self.display_actions.clear()
            if alarm_item.displays:
                for display in alarm_item.displays:
                    display_action = QAction(display["title"])
                    display_action.triggered.connect(partial(self.launch_pydm_display, display["details"]))
                    self.context_menu.addAction(display_action)
                    self.display_actions.append(display_action)
            self.context_menu.popup(self.mapToGlobal(pos))

    def create_alarm_configuration_widget(self, index: QModelIndex) -> None:
        """Create and display the alarm configuration widget for the alarm item with the input index"""
        alarm_item = self.treeModel.getItem(index)
        alarm_config_window = AlarmConfigurationWidget(
            alarm_item=alarm_item,
            kafka_producer=self.kafka_producer,
            topic=self.topic,
            parent=self,
            annunciate=self.annunciate,
        )
        alarm_config_window.show()

    def copy_to_clipboard(self) -> None:
        """Copy the selected PV to the user's clipboard"""
        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            index = indices[0]
            alarm_item = self.treeModel.getItem(index)
            self.clipboard.setText(alarm_item.name, mode=self.clipboard.Selection)
            self.clipboard.setText(alarm_item.name, mode=self.clipboard.Clipboard)

    def plot_pv(self) -> None:
        """Send off the signal for plotting a PV"""
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

    @staticmethod
    def create_config_values_for_action(
        alarm_item: AlarmItem, enabled: Optional[bool] = None, acknowledged: Optional[bool] = None
    ) -> Dict[str, any]:
        """Return a dict to send to kafka changing the enabled and/or acknowledged status of the alarm"""
        values_to_send = dict()
        values_to_send["user"] = getpass.getuser()
        values_to_send["hostname"] = socket.gethostname()
        if enabled is not None:
            values_to_send.update(alarm_item.to_config_dict())
            values_to_send["enabled"] = enabled
        if acknowledged is not None:
            if acknowledged:
                values_to_send["command"] = "acknowledge"
            else:
                values_to_send["command"] = "unacknowledge"
        return values_to_send

    def send_action(self, acknowledged: Optional[bool] = None, enabled: Optional[bool] = None) -> None:
        """Send the appropriate message to kafka to take an enable or acknowledgement related action"""
        # Verify if the user can actually take the requested action and just return if there's nothing to do
        if acknowledged is not None and not can_take_action(UserAction.ACKNOWLEDGE, log_warning=True):
            acknowledged = None
        if enabled is not None and not can_take_action(UserAction.ENABLE, log_warning=True):
            enabled = None
        if acknowledged is None and enabled is None:
            return

        indices = self.tree_view.selectedIndexes()
        if len(indices) > 0:
            alarms_to_modify = []
            alarm_item = self.treeModel.getItem(indices[0])
            alarms_to_modify.append(alarm_item)
            if not alarm_item.is_leaf():
                alarms_to_modify.extend(self.treeModel.get_all_leaf_nodes(alarm_item))
            for alarm in alarms_to_modify:
                for alarm_path in self.treeModel.added_paths[alarm.name]:
                    values_to_send = self.create_config_values_for_action(alarm, enabled, acknowledged)
                    if enabled is not None and enabled != alarm.is_enabled():
                        # Changes to enabled status go to the regular topic

                        # "" topic string means this is 'All' topic tree-vew and doesn't its own valid kafka topic,
                        # so grab the destination topic from the alarm's path.
                        curr_topic = self.topic
                        if curr_topic == "":
                            curr_topic = alarm_path.split("/")[1]
                        self.kafka_producer.send(curr_topic, key=f"config:{alarm_path}", value=values_to_send)
                    if acknowledged is not None and acknowledged != alarm.is_acknowledged():
                        # Changes to acknowledgement status go to the command topic.
                        # Similar to the enabled-status above, grab the destination topic from the alarm's path.
                        curr_topic = self.topic
                        if curr_topic == "":
                            curr_topic = alarm_path.split("/")[1]
                        self.kafka_producer.send(
                            curr_topic + "Command", key=f"command:{alarm_path}", value=values_to_send
                        )
