import getpass
import socket
from .alarm_item import AlarmItem
from kafka.producer import KafkaProducer
from qtpy.QtCore import QDateTime, QObject
from qtpy.QtWidgets import (QCheckBox, QDateTimeEdit, QDialog, QHBoxLayout, QHeaderView, QLabel,
                            QLineEdit, QPushButton, QSpinBox, QTableWidget, QVBoxLayout)
from typing import Optional


class AlarmConfigurationWidget(QDialog):
    """
    The AlarmConfigurationWidget is a pop-up dialog allowing the user to specify various configuration options
    for each alarm. Double clicking on an alarm item in either the tree or table model will create this dialog.

    Parameters
    ----------
    parent : QObject
        The parent of this widget.
    alarm_item : AlarmItem
        The alarm item to have its configuration updated
    kafka_producer : KafkaProducer
        The producer for sending state and command updates to the kafka cluster
    topic : str
        The kafka topic to send update messages to
    parent : QObject, optional
        The parent of this widget
    """

    def __init__(self, alarm_item: AlarmItem, kafka_producer: KafkaProducer,
                 topic: str, parent: Optional[QObject] = None):
        super().__init__(parent=parent)
        self.alarm_item = alarm_item
        self.kafka_producer = kafka_producer
        self.topic = topic

        self.resize(700, 800)

        self.layout = QVBoxLayout()

        self.path_value_label = QLabel(alarm_item.path)
        self.description_label = QLabel('Description:')
        self.description_box = QLineEdit(alarm_item.description or '')

        self.behavior_label = QLabel('Behavior:')
        self.enabled_checkbox = QCheckBox('Enabled')
        self.latch_checkbox = QCheckBox('Latched')
        self.annunciate_checkbox = QCheckBox('Annunciate')

        self.disable_date_label = QLabel('Disable Until:')
        self.minimum_datetime = QDateTime.currentDateTime().addDays(-1)
        self.datetime_widget = QDateTimeEdit(self.minimum_datetime)
        self.datetime_widget.setMinimumDateTime(self.minimum_datetime)
        self.datetime_widget.setSpecialValueText(' ')
        self.datetime_widget.setCalendarPopup(True)

        self.datetime_widget.dateTimeChanged.connect(self.uncheck_enabled_box)
        self.enabled_checkbox.stateChanged.connect(self.clear_datetime_widget)

        self.delay_label = QLabel('Alarm Delay (sec)')
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 1000000)
        self.delay_spinbox.setFixedWidth(100)

        self.filter_label = QLabel('Enabling Filter:')
        self.filter_edit = QLineEdit(alarm_item.alarm_filter or '')

        self.guidance_label = QLabel('Guidance:')
        self.displays_label = QLabel('Display:')
        self.commands_label = QLabel('Commands:')

        self.guidance_table = QTableWidget(10, 2)
        self.guidance_table.verticalHeader().setVisible(False)
        self.guidance_table.setHorizontalHeaderLabels(['Title', 'Detail'])
        self.guidance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.guidance_table.setAlternatingRowColors(True)
        for i in range(10):
            for j in range(10):
                self.guidance_table.setCellWidget(i, j, QLineEdit())

        self.displays_table = QTableWidget(10, 2)
        self.displays_table.verticalHeader().setVisible(False)
        self.displays_table.setHorizontalHeaderLabels(['Title', 'Detail'])
        self.displays_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.displays_table.setAlternatingRowColors(True)
        for i in range(10):
            for j in range(10):
                self.displays_table.setCellWidget(i, j, QLineEdit())

        self.commands_table = QTableWidget(10, 2)
        self.commands_table.verticalHeader().setVisible(False)
        self.commands_table.setHorizontalHeaderLabels(['Title', 'Detail'])
        self.commands_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.commands_table.setAlternatingRowColors(True)
        for i in range(10):
            for j in range(10):
                self.commands_table.setCellWidget(i, j, QLineEdit())

        if alarm_item.guidance is not None:
            for index, guidance_item in enumerate(alarm_item.guidance):
                self.guidance_table.cellWidget(index, 0).setText(guidance_item['title'])
                self.guidance_table.cellWidget(index, 1).setText(guidance_item['details'])
        if alarm_item.displays is not None:
            for index, display_item in enumerate(alarm_item.displays):
                self.displays_table.cellWidget(index, 0).setText(display_item['title'])
                self.displays_table.cellWidget(index, 1).setText(display_item['details'])
        if alarm_item.commands is not None:
            for index, command_item in enumerate(alarm_item.commands):
                self.commands_table.cellWidget(index, 0).setText(command_item['title'])
                self.commands_table.cellWidget(index, 1).setText(command_item['details'])

        self.layout.addWidget(self.path_value_label)
        if alarm_item.is_leaf():
            self.description_layout = QHBoxLayout()
            self.description_layout.addWidget(self.description_label)
            self.description_layout.addWidget(self.description_box)
            self.layout.addLayout(self.description_layout)
            self.behavior_layout = QHBoxLayout()
            self.behavior_layout.addWidget(self.behavior_label)
            if type(self.alarm_item.enabled) is bool:
                self.enabled_checkbox.setChecked(self.alarm_item.enabled)
            elif self.alarm_item.enabled and type(self.alarm_item.enabled) is str:
                self.enabled_checkbox.setChecked(False)  # Any string here means a disable timeout has been set
            self.behavior_layout.addWidget(self.enabled_checkbox)
            self.latch_checkbox.setChecked(self.alarm_item.latching)
            self.behavior_layout.addWidget(self.latch_checkbox)
            self.annunciate_checkbox.setChecked(self.alarm_item.annunciating)
            self.behavior_layout.addWidget(self.annunciate_checkbox)
            self.layout.addLayout(self.behavior_layout)
            self.disable_layout = QHBoxLayout()
            self.disable_layout.addWidget(self.disable_date_label)
            self.disable_layout.addWidget(self.datetime_widget)
            if self.alarm_item.enabled and type(self.alarm_item.enabled) == str:
                self.datetime_widget.setDateTime(
                    QDateTime.fromString(alarm_item.enabled[:19], 'yyyy-MM-ddThh:mm:ss'))
            self.layout.addLayout(self.disable_layout)
            self.delay_layout = QHBoxLayout()
            self.delay_layout.addWidget(self.delay_label)
            if self.alarm_item.delay:
                self.delay_spinbox.setValue(self.alarm_item.delay)
            self.delay_layout.addWidget(self.delay_spinbox)
            self.layout.addLayout(self.delay_layout)
            self.filter_layout = QHBoxLayout()
            self.filter_layout.addWidget(self.filter_label)
            self.filter_layout.addWidget(self.filter_edit)
            self.layout.addLayout(self.filter_layout)
        self.layout.addWidget(self.guidance_label)
        self.layout.addWidget(self.guidance_table)
        self.layout.addWidget(self.displays_label)
        self.layout.addWidget(self.displays_table)
        self.layout.addWidget(self.commands_label)
        self.layout.addWidget(self.commands_table)

        self.cancel_button = QPushButton('Cancel')
        self.ok_button = QPushButton('OK')
        self.cancel_button.clicked.connect(self.close_window)
        self.ok_button.clicked.connect(self.save_configuration)
        self.ok_button.setDefault(True)

        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.cancel_button)
        self.button_layout.addWidget(self.ok_button)

        self.setLayout(self.layout)
        self.layout.addLayout(self.button_layout)

    def save_configuration(self):
        """ Saves the input the user entered into the widget by sending it to the kafka config queue """
        guidance = []
        displays = []
        commands = []
        username = getpass.getuser()
        hostname = socket.gethostname()

        for row in range(self.guidance_table.rowCount()):
            title = self.guidance_table.cellWidget(row, 0).text()
            detail = self.guidance_table.cellWidget(row, 1).text()
            if title or detail:
                guidance.append({'title': title, 'details': detail})

        for row in range(self.displays_table.rowCount()):
            title = self.displays_table.cellWidget(row, 0).text()
            detail = self.displays_table.cellWidget(row, 1).text()
            if title or detail:
                displays.append({'title': title, 'details': detail})

        for row in range(self.commands_table.rowCount()):
            title = self.commands_table.cellWidget(row, 0).text()
            detail = self.commands_table.cellWidget(row, 1).text()
            if title or detail:
                commands.append({'title': title, 'details': detail})

        if self.alarm_item.is_leaf():
            values_to_send = {'user': username, 'host': hostname, 'description': self.description_box.text(),
                              'enabled': self.alarm_item.enabled, 'latching': self.alarm_item.latching,
                              'annunciating': self.alarm_item.annunciating, 'guidance': guidance, 'displays': displays,
                              'commands': commands}
            if self.datetime_widget.dateTime() != self.minimum_datetime and not self.enabled_checkbox.isChecked():
                values_to_send['enabled'] = self.datetime_widget.dateTime().toString('yyyy-MM-ddThh:mm:ss')
            elif self.alarm_item.enabled != self.enabled_checkbox.isChecked():
                values_to_send['enabled'] = self.enabled_checkbox.isChecked()
            if self.alarm_item.latching != self.latch_checkbox.isChecked():
                values_to_send['latching'] = self.enabled_checkbox.isChecked()
            if self.alarm_item.annunciating != self.annunciate_checkbox.isChecked():
                values_to_send['annunciating'] = self.annunciate_checkbox.isChecked()
            if self.delay_spinbox.value() != 0:
                values_to_send['delay'] = self.delay_spinbox.value()
            if self.filter_edit.text():
                values_to_send['filter'] = self.filter_edit.text()

            self.kafka_producer.send(self.topic,
                                     key=f'config:{self.alarm_item.path}',
                                     value=values_to_send)
        else:
            self.kafka_producer.send(self.topic,
                                     key=f'config:{self.alarm_item.path}',
                                     value={'user': username, 'host': hostname, 'guidance': guidance,
                                            'displays': displays, 'commands': commands})

        self.close()

    def uncheck_enabled_box(self):
        """ A simple slot for unchecking the enabled checkbox when the date time widget is set  """
        if self.datetime_widget.dateTime() != self.minimum_datetime:
            self.enabled_checkbox.setChecked(False)

    def clear_datetime_widget(self, checkbox_state: int):
        """ A simple slot for clearing out the datetime widget if the enabled checkbox is checked """
        if checkbox_state != 0:
            self.datetime_widget.setDateTime(self.minimum_datetime)

    def close_window(self):
        self.close()
