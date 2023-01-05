from setuptools import setup
from pathlib import Path

curr_dir = Path(__file__).parent
long_description = (curr_dir/'README.md').read_text()

setup(
    name='slac-alarm-manager',
    version='1.1.0',
    description='Python interface for managing alarms',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='SLAC National Accelerator Laboratory',
    url='https://github.com/slaclab/slac-alarm-manager',
    packages=['slam', 'slam_launcher', 'pydm_alarm_plugin'],
    install_requires=['kafka-python', 'pydm', 'qtpy'],
    entry_points={
        'console_scripts': ['slam=slam_launcher.main:main'],
        'pydm.data_plugin': ['pydm_alarm_plugin=pydm_alarm_plugin.alarm_plugin:AlarmPlugin']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
    ]
)
