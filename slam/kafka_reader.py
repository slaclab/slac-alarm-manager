import json
from kafka import KafkaConsumer
from kafka.consumer.fetcher import ConsumerRecord
from qtpy.QtCore import QObject, Signal
from typing import Callable, List


class KafkaReader(QObject):
    """
    KafkaReader is a simple class for reading message from kafka topics and sending them to the main qt thread.

    Parameters
    ----------
    topics : List[str]
        A list of topics representing the alarm configs to listen to
    bootstrap_servers : List[str]
        A list containing one or more urls for kafka bootstrap servers
    new_message_slot : Callable
        The slot function that each message will end up at
    """

    new_message_signal = Signal(ConsumerRecord)  # Emitted for every new message received

    def __init__(self, topics: List[str], bootstrap_servers: List[str], new_message_slot: Callable):
        self.topics = topics
        self.main_consumer = KafkaConsumer(*topics,
                                           bootstrap_servers=bootstrap_servers,
                                           auto_offset_reset='earliest',
                                           enable_auto_commit=False,
                                           key_deserializer=lambda x: x.decode('utf-8'),
                                           value_deserializer=self.value_decode)

        super(KafkaReader, self).__init__()
        self.new_message_slot = new_message_slot
        self.new_message_signal.connect(self.new_message_slot)

    def value_decode(self, x):
        if x is not None:
            return json.loads(x.decode('utf-8'))
        return None

    def run(self):
        for message in self.main_consumer:
            self.new_message_signal.emit(message)
