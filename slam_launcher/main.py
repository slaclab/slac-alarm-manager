import argparse
import logging
import sys

from qtpy.QtWidgets import QApplication
from slam import AlarmHandlerMainWindow, permissions


def main():
    parser = argparse.ArgumentParser(description="SLAC Alarm Manager")
    parser.add_argument("--topics", help="Comma separated list of kafka alarm topics to listen to")
    parser.add_argument(
        "--bootstrap-servers",
        default="localhost:9092",
        help="Comma separated list of urls for one or more kafka boostrap servers",
    )
    parser.add_argument("--user-permissions", default="admin", help="One of read-only, operator, admin")
    parser.add_argument("--log", default="warning", help="Logging level. debug, info, warning, error, critical")

    app_args = parser.parse_args()

    logging.basicConfig(level=app_args.log.upper())

    permissions.set_user_permission(permissions.UserPermission(app_args.user_permissions))

    topics = app_args.topics.split(",")
    kafka_boostrap_servers = app_args.bootstrap_servers.split(",")

    app = QApplication([])
    main_window = AlarmHandlerMainWindow(topics, kafka_boostrap_servers)
    main_window.resize(1536, 864)
    main_window.setWindowTitle("SLAC Alarm Manager")
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
