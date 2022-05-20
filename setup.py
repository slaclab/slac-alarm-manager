from setuptools import setup

setup(
    name='slac-alarm-manager',
    version='0.1.0',
    description='Python interface for managing alarms',
    url='https://github.com/jbellister-slac/slam',
    packages=['slam', 'slam_launcher'],
    install_requires=['kafka-python', 'qtpy'],
    entry_points={'console_scripts': ['slam=slam_launcher.main:main']},
)
