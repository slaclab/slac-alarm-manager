import argparse
import sys

from qtpy.QtWidgets import QApplication
from slam import AlarmHandlerMainWindow


def main():
    parser = argparse.ArgumentParser(description="SLAC Alarm Manager")
    # TODO: Take a list of topics (not currently supported by the applicaiton)
    parser.add_argument('--topic', help='Kafka alarm topic to listen to')
    
    app_args = parser.parse_args()

    app = QApplication([])
    main_window = AlarmHandlerMainWindow(app_args.topic)
    main_window.resize(1035, 600)
    main_window.setWindowTitle('SLAC Alarm Manager')
    main_window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
