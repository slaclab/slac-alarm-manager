from ..alarm_table_view import AlarmTableViewWidget


def test_create_and_show(qtbot, alarm_item, tree_model, mock_kafka_producer):
    """ A simple check that the alarm table view will init and show without any errors """
    alarm_table = AlarmTableViewWidget(tree_model, mock_kafka_producer, 'TEST_TOPIC', lambda x: x)
    qtbot.addWidget(alarm_table)
    with qtbot.waitExposed(alarm_table):
        alarm_table.show()
