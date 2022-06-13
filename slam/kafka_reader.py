import json
from kafka import KafkaConsumer
from kafka.consumer.fetcher import ConsumerRecord
from qtpy.QtCore import QObject, Signal
from typing import Callable


class KafkaReader(QObject):
    """
    KafkaReader is a simple class for reading message from kafka topics and sending them to the main qt thread.

    Parameters
    ----------
    topic_name : str
        The name of the topic to subscribe to. Will also subscribe to the command topic as well
    new_message_slot : Callable
        The slot function that each message will end up at
    """

    new_message_signal = Signal(ConsumerRecord)  # Emitted for every new message received

    def __init__(self, topic_name: str, new_message_slot: Callable):
        self.topic_name = topic_name
        self.main_consumer = KafkaConsumer(topic_name,
                                           f'{topic_name}Command',
                                           bootstrap_servers=['localhost:9092'],
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
