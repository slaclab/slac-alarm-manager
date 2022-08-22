from setuptools import setup

setup(
    name='slac-alarm-manager',
    version='0.1.0',
    description='Python interface for managing alarms',
    url='https://github.com/slaclab/slac-alarm-manager',
    packages=['slam', 'slam_launcher', 'pydm_alarm_plugin'],
    install_requires=['kafka-python', 'pydm', 'qtpy'],
    entry_points={
        'console_scripts': ['slam=slam_launcher.main:main'],
        'pydm.data_plugin': ['pydm_alarm_plugin=pydm_alarm_plugin.alarm_plugin:AlarmPlugin']
    },
)
