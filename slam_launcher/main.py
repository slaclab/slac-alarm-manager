import argparse
import logging
import sys

from qtpy.QtWidgets import QApplication
from slam import AlarmHandlerMainWindow


def main():
    parser = argparse.ArgumentParser(description="SLAC Alarm Manager")
    parser.add_argument('--topic', help='Kafka alarm topic to listen to')
    parser.add_argument('--bootstrap-servers',
                        default='localhost:9092',
                        help='Comma separated list of urls for one or more kafka boostrap servers')
    parser.add_argument('--log', default='warning', help='Logging level. debug, info, warning, error, critical')

    app_args = parser.parse_args()

    logging.basicConfig(level=app_args.log.upper())

    kafka_boostrap_servers = app_args.bootstrap_servers.split(',')

    app = QApplication([])
    main_window = AlarmHandlerMainWindow(app_args.topic, kafka_boostrap_servers)
    main_window.resize(1035, 600)
    main_window.setWindowTitle('SLAC Alarm Manager')
    main_window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
