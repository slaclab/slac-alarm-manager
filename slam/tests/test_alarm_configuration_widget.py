from ..alarm_configuration_widget import AlarmConfigurationWidget
import pytest


def test_create_and_show(qtbot, alarm_item, mock_kafka_producer):
    """A simple check that the configuration window will init and show without any errors"""
    alarm_config_widget = AlarmConfigurationWidget(
        alarm_item=alarm_item, kafka_producer=mock_kafka_producer, topic="TEST"
    )

    qtbot.addWidget(alarm_config_widget)

    with qtbot.waitExposed(alarm_config_widget):
        alarm_config_widget.show()

    # Also simple test for it the presence of enabled-filter text disables the "Enabled" check-box
    assert not alarm_config_widget.filter_edit.text() and alarm_config_widget.enabled_checkbox.isEnabled()

    alarm_config_widget.filter_edit.setText("Test filter")
    assert not alarm_config_widget.enabled_checkbox.isEnabled()

    alarm_config_widget.filter_edit.setText("")
    assert alarm_config_widget.enabled_checkbox.isEnabled()


@pytest.mark.parametrize("enabled, latching, annunciating", [(False, False, False), (True, True, True)])
def test_save_configuration(qtbot, alarm_item, mock_kafka_producer, enabled, latching, annunciating):
    """Verify that the information saved in the configuration widget is sent to the kafka cluster correctly"""
    alarm_config_widget = AlarmConfigurationWidget(
        alarm_item=alarm_item, kafka_producer=mock_kafka_producer, topic="TEST"
    )
    qtbot.addWidget(alarm_config_widget)

    # Simulate the user typing in several suggestions for how to handle this particular alarm
    alarm_config_widget.enabled_checkbox.setChecked(enabled)
    alarm_config_widget.latch_checkbox.setChecked(latching)
    alarm_config_widget.annunciate_checkbox.setChecked(annunciating)

    alarm_config_widget.guidance_table.cellWidget(0, 0).setText("Call")
    alarm_config_widget.guidance_table.cellWidget(0, 1).setText("Somebody")
    alarm_config_widget.guidance_table.cellWidget(1, 0).setText("Read")
    alarm_config_widget.guidance_table.cellWidget(1, 1).setText("the manual")

    alarm_config_widget.displays_table.cellWidget(0, 0).setText("RF Display")

    alarm_config_widget.commands_table.cellWidget(0, 0).setText("How to run display")
    alarm_config_widget.commands_table.cellWidget(0, 1).setText("bash run_display.sh")

    # Save all the values entered into the form
    alarm_config_widget.save_configuration()

    assert mock_kafka_producer.topic == "TEST"
    assert mock_kafka_producer.key == "config:/ROOT/SECTOR_ONE/TEST:PV:ONE"
    values_sent = mock_kafka_producer.values

    # Verify the user input was read from the check boxes and tables and sent to kafka in the form it expects
    assert values_sent["enabled"] == enabled
    assert values_sent["latching"] == latching
    assert values_sent["annunciating"] == annunciating
    assert values_sent["guidance"][0]["title"] == "Call"
    assert values_sent["guidance"][0]["details"] == "Somebody"
    assert values_sent["guidance"][1]["title"] == "Read"
    assert values_sent["guidance"][1]["details"] == "the manual"
    assert values_sent["displays"][0]["title"] == "RF Display"
    assert values_sent["displays"][0]["details"] == ""
    assert values_sent["commands"][0]["title"] == "How to run display"
    assert values_sent["commands"][0]["details"] == "bash run_display.sh"
