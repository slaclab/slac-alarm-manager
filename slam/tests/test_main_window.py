from ..kafka_reader import KafkaReader
from ..main_window import AlarmHandlerMainWindow
from kafka.producer import KafkaProducer
from qtpy.QtCore import QThread
import pytest


@pytest.fixture(scope='function')
def main_window(monkeypatch, mock_kafka_producer):
    """ Create an instance of the main window of this application for testing """
    monkeypatch.setattr(KafkaProducer, '__init__', lambda *args, **kwargs: None)
    monkeypatch.setattr(KafkaReader, '__init__', lambda *args, **kwargs: None)
    monkeypatch.setattr(KafkaReader, 'moveToThread', lambda *args: None)
    monkeypatch.setattr(QThread, 'start', lambda *args: None)

    main_window = AlarmHandlerMainWindow('TEST_TOPIC')
    return main_window


def test_create_and_show(qtbot, main_window):
    """ Ensure the main window of the application inits and shows without any errors """
    qtbot.addWidget(main_window)
    with qtbot.waitExposed(main_window):
        main_window.show()


def test_create_and_show_plot(qtbot, main_window):
    """ Ensure a plot can be created and shown correctly without errors """
    main_window.create_plot_widget()
    with qtbot.waitExposed(main_window):
        main_window.show()
