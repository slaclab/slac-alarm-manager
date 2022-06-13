from ..kafka_reader import KafkaReader
from ..main_window import AlarmHandlerMainWindow
from kafka.producer import KafkaProducer
from qtpy.QtCore import QThread
import pytest


def test_create_and_show(monkeypatch, qtbot, mock_kafka_producer):
    """ Ensure the main window of the application inits and shows without any errors """
    monkeypatch.setattr(KafkaProducer, '__init__', lambda *args, **kwargs: None)
    monkeypatch.setattr(KafkaReader, '__init__', lambda *args, **kwargs: None)
    monkeypatch.setattr(KafkaReader, 'moveToThread', lambda *args: None)
    monkeypatch.setattr(QThread, 'start', lambda *args: None)

    main_window = AlarmHandlerMainWindow('TEST_TOPIC')
    qtbot.addWidget(main_window)
    with qtbot.waitExposed(main_window):
        main_window.show()
