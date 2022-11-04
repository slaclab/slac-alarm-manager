import logging
import os
from kafka.consumer.fetcher import ConsumerRecord
from pydm.data_plugins.plugin import PyDMPlugin, PyDMConnection
from pydm.utilities import is_qt_designer, remove_protocol
from pydm.widgets.base import PyDMWidget
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import QObject, QThread
from slam.alarm_item import AlarmSeverity
from slam.kafka_reader import KafkaReader
from typing import Optional


logger = logging.getLogger(__name__)
kafka_logger = logging.getLogger('kafka')
kafka_logger.setLevel('WARNING')  # Anything less results in too much noise


class Connection(PyDMConnection):
    """
    A PyDMConnection for sending alarm severity signals to all listeners which have been registered with it.
    """
    def __init__(self, channel: PyDMChannel, address: str, protocol: Optional[str] = None,
                 parent: Optional[QObject] = None):
        super().__init__(channel, address, protocol, parent)
        self.add_listener(channel)
        self.current_severity = AlarmSeverity.OK

    def send_alarm_data(self, severity: AlarmSeverity):
        """
        Sends the updated alarm severity to all listeners of this connection.

        Parameters
        ----------
        severity : AlarmSeverity
            The updated severity which will be emitted as the new_severity_signal
        """
        if severity is AlarmSeverity.OK:
            self.new_severity_signal.emit(PyDMWidget.ALARM_NONE)
        elif severity is AlarmSeverity.MINOR:
            self.new_severity_signal.emit(PyDMWidget.ALARM_MINOR)
        elif severity is AlarmSeverity.MAJOR:
            self.new_severity_signal.emit(PyDMWidget.ALARM_MAJOR)
        elif severity is AlarmSeverity.INVALID:
            self.new_severity_signal.emit(PyDMWidget.ALARM_INVALID)
        elif severity is AlarmSeverity.UNDEFINED:
            self.new_severity_signal.emit(PyDMWidget.ALARM_DISCONNECTED)
        elif severity is AlarmSeverity.MINOR_ACK and self.current_severity <= AlarmSeverity.MINOR:
            self.new_severity_signal.emit(PyDMWidget.ALARM_NONE)
        elif severity is AlarmSeverity.MAJOR_ACK and self.current_severity <= AlarmSeverity.MAJOR:
            self.new_severity_signal.emit(PyDMWidget.ALARM_NONE)
        elif severity is AlarmSeverity.INVALID_ACK and self.current_severity <= AlarmSeverity.INVALID:
            self.new_severity_signal.emit(PyDMWidget.ALARM_NONE)
        elif severity is AlarmSeverity.UNDEFINED_ACK and self.current_severity <= AlarmSeverity.UNDEFINED:
            self.new_severity_signal.emit(PyDMWidget.ALARM_NONE)

        self.current_severity = severity


class AlarmPlugin(PyDMPlugin):
    """
    Manages the data flow between the kafka queue for alarm data and the PyDM display widgets. Currently this is
    read-only as no write actions can be taken from PyDM widgets for now.
    """
    protocol = "nalms"
    connection_class = Connection

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kafka_topics = os.getenv('PYDM_KAFKA_ALARM_TOPICS')
        kafka_bootstrap_servers = os.getenv('PYDM_KAFKA_BOOTSTRAP_SERVERS')
        if not kafka_topics:
            logger.debug('Could not initialize alarm data plugin, at least one topic must be specified in the '
                         'PYDM_KAFKA_ALARM_TOPICS environment variable')
            return
        if not kafka_bootstrap_servers:
            logger.debug('Could not initialize alarm data plugin, kafka bootstrap server location must be '
                         'specified in the PYDM_KAFKA_BOOTSTRAP_SERVERS environment variable')
            return

        self.alarm_severities = dict()  # Mapping from alarm name to current alarm severity
        self.kafka_reader = KafkaReader(kafka_topics.split(','),
                                        kafka_bootstrap_servers.split(','),
                                        self.process_message)
        self.kafka_topics = kafka_topics
        self.processing_thread = QThread()
        self.kafka_reader.moveToThread(self.processing_thread)
        self.processing_thread.started.connect(self.kafka_reader.run)
        self.processing_thread.start()

    def add_connection(self, channel: PyDMChannel):
        """
        Add the input channel to the set of channels this data plugin is connected with. Will send the current
        alarm value to the channel upon connecting, and continue to send alarm updates to the channel for as long
        as it remains connected.

        Parameters
        ----------
        channel : PyDMChannel
            The channel to establish a connection with
        """
        if is_qt_designer():
            return

        super(AlarmPlugin, self).add_connection(channel)
        alarm_name = remove_protocol(channel.address)
        self.connections[alarm_name].connected = True
        if alarm_name in self.alarm_severities:
            self.connections[alarm_name].send_alarm_data(self.alarm_severities[alarm_name])

    def process_message(self, message: ConsumerRecord):
        """
        Process a message received from kafka and send the alarm severity to any channels listening for updates to the
        key of the message received.

        Parameters
        ----------
        message : ConsumerRecord
            A message received from the kafka queue indicating a new message for the topic we are listening to
        """
        if message.key.startswith('state') and message.value is not None and 'severity' in message.value:
            # Start from [6:] to skip over the "state:" part of the key.
            # An example key could look something like: state:/top-level-system/sub-system/sub-component/PV:NAME
            alarm_path = message.key[6:]
            alarm_name = alarm_path.split('/')[-1]
            if alarm_name not in self.kafka_topics:
                current_severity = AlarmSeverity(message.value['severity'])
                self.alarm_severities[alarm_name] = current_severity
                if alarm_name in self.connections:
                    self.connections[alarm_name].send_alarm_data(current_severity)
