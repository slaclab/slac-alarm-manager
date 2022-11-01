import pytest
from unittest import mock
from pydm import PyDMChannel
from pydm.widgets.base import PyDMWidget

from pydm_alarm_plugin.alarm_plugin import AlarmPlugin, Connection


@mock.patch('kafka.consumer.fetcher.ConsumerRecord', autospec=True)
@pytest.mark.parametrize('severity_from_kafka, signal_to_send', [
    ('OK', PyDMWidget.ALARM_NONE),
    ('MINOR', PyDMWidget.ALARM_MINOR),
    ('MAJOR', PyDMWidget.ALARM_MAJOR),
    ('INVALID', PyDMWidget.ALARM_INVALID),
    ('UNDEFINED', PyDMWidget.ALARM_DISCONNECTED)
])
def test_process_message(mock_record, severity_from_kafka, signal_to_send):
    """
    The alarm data plugin maintains a list of connections for receiving updates to alarm severities. This tests
    that when a new message from kafka arrives that a connection is listening for, the plugin will notify
    that connection to emit the correct signal.

    Parameters
    ----------
    mock_record : ConsumerRecord
        A mock up of a message that will be received by the kafka consumer
    severity_from_kafka : str
        The new alarm severity received from kafka
    signal_to_send : int
        The severity value that PyDM is expecting to receive
    """

    # Setup the alarm plugin and an associated connection
    alarm_plugin = AlarmPlugin()
    alarm_plugin.kafka_topics = ['test_topic']
    alarm_plugin.alarm_severities = {}
    alarm_channel = PyDMChannel()
    alarm_connection = Connection(alarm_channel, 'pva://TEST:ADDRESS')

    # Setup a way for verifying the signals emitted
    received_values = []

    def receive_signal(value_received: object):
        """ A simple slot for receiving all our test signals and storing the values to ensure they are as expected """
        received_values.append(value_received)
    alarm_connection.new_severity_signal.connect(receive_signal)

    # Create the mock record to receive from kafka
    mock_record.key = 'state:/top_level_summary/component_summary/motors'
    mock_record.value = {'message': 'state_alarm', 'severity': severity_from_kafka}

    # At first no signals should be sent because no connections have been established with the plugin
    alarm_plugin.process_message(mock_record)
    assert len(received_values) == 0

    # Now add a connection, and verify the signal is emitted as expected
    alarm_plugin.connections['motors'] = alarm_connection
    alarm_plugin.process_message(mock_record)
    assert len(received_values) == 1
    assert received_values[0] == signal_to_send
