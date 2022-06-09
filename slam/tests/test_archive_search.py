from ..archive_search import ArchiveResultsTableModel, ArchiveSearchWidget
from qtpy.QtCore import Qt
from qtpy.QtNetwork import QNetworkReply
import pytest


@pytest.fixture(scope='function')
def archive_results_table():
    """ Return an ArchiveResultsTableModel with an empty list of results """
    return ArchiveResultsTableModel()


@pytest.fixture(scope='function')
def archive_search_widget():
    """ Return an ArchiveSearchWidget with an empty list of results """
    return ArchiveSearchWidget()


class MockNetworkReply:
    """ A mock of a reply made from the archiver appliance. """

    @staticmethod
    def readAll():
        return b'PV:1 PV:2 PV:3'

    @staticmethod
    def error():
        return QNetworkReply.NoError

    @staticmethod
    def deleteLater():
        pass


@pytest.fixture(scope='function')
def mock_network_reply():
    return MockNetworkReply


def test_row_count(archive_results_table):
    """ Confirm that checking the row count is returning the correct number """
    assert archive_results_table.rowCount(None) == 0
    archive_results_table.results_list.extend(['PV:1', 'PV:2', 'PV3'])
    assert archive_results_table.rowCount(None) == 3


def test_column_count(archive_results_table):
    """ Confirm that checking the column count is returning the correct number """
    assert archive_results_table.columnCount(None) == len(archive_results_table.column_names)


def test_append(archive_results_table):
    """ Verify that single PV names are appended to the results table correctly """
    archive_results_table.append('PV:1')
    assert len(archive_results_table.results_list) == 1
    assert archive_results_table.results_list[0] == 'PV:1'

    archive_results_table.append('PV:2')
    assert len(archive_results_table.results_list) == 2
    assert archive_results_table.results_list[0] == 'PV:1'
    assert archive_results_table.results_list[1] == 'PV:2'


def test_replace_rows(archive_results_table):
    """ Test that setting all rows of the table at once works as expected """
    archive_results_table.replace_rows(['PV:1'])
    assert len(archive_results_table.results_list) == 1
    assert archive_results_table.results_list[0] == 'PV:1'

    archive_results_table.replace_rows(['PV:2', 'PV:3', 'PV:4'])
    assert len(archive_results_table.results_list) == 3
    assert archive_results_table.results_list == ['PV:2', 'PV:3', 'PV:4']


def test_clear(archive_results_table):
    """ Test that the clear function removes all rows from the table """
    archive_results_table.replace_rows(['PV:2', 'PV:3', 'PV:4'])
    archive_results_table.clear()
    assert len(archive_results_table.results_list) == 0


def test_sort(archive_results_table):
    """ Test that sorting the results table by name works correctly """
    archive_results_table.replace_rows(['B:PV', 'A:PV', 'D:PV', 'C:PV'])
    archive_results_table.sort(col=0)
    assert archive_results_table.results_list == ['A:PV', 'B:PV', 'C:PV', 'D:PV']
    archive_results_table.sort(col=0, order=Qt.DescendingOrder)
    assert archive_results_table.results_list == ['D:PV', 'C:PV', 'B:PV', 'A:PV']


def test_create_and_show(qtbot, archive_search_widget):
    """ Verify that the widget for displaying the table inits and shows correctly """
    qtbot.addWidget(archive_search_widget)
    with qtbot.waitExposed(archive_search_widget):
        archive_search_widget.show()


def test_populate_results_list(qtbot, archive_search_widget, mock_network_reply):
    """ Test that the response received from archiver is places into the table correctly """
    qtbot.addWidget(archive_search_widget)
    archive_search_widget.populate_results_list(mock_network_reply)
    assert archive_search_widget.results_table_model.results_list == ['PV:1', 'PV:2', 'PV:3']
