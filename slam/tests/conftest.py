import pytest
from ..alarm_item import AlarmItem
from ..alarm_tree_model import AlarmItemsTreeModel
from typing import Dict

""" Various fixtures that can be used for any unit test """


class MockKafkaProducer:
    """A mock of a kafka producer that just stores the values it would have sent"""

    def __init__(self):
        self.topic = None
        self.key = None
        self.values = {}

    def send(self, topic: str, key: str, value: Dict):
        """Instead of sending anything, just store each parameter to inspect for correctness"""
        self.topic = topic
        self.key = key
        self.values = value


@pytest.fixture(scope="function")
def alarm_item():
    return AlarmItem("TEST:PV:ONE", path="/ROOT/SECTOR_ONE/TEST:PV:ONE")


@pytest.fixture(scope="function")
def tree_model():
    """Return an empty tree model for testing"""
    return AlarmItemsTreeModel()


@pytest.fixture(scope="function")
def mock_kafka_producer():
    return MockKafkaProducer()
