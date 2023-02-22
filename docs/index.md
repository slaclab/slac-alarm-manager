# SLAC Alarm Manager

The SLAC Alarm Manager contains two main ways of interfacing with the [NALMS](https://slaclab.github.io/nalms/) alarm
system. There is a standalone python application for viewing and interacting with alarms described in greater
detail [here](alarm_manager.md). And a [PyDM data plugin](pydm.md) that will allow for building displays containing
summary alarms.

## Installation

The easiest installation method is using pip to install from PyPI into a virtual environment:

`pip install slac-alarm-manager`

It can also be installed from source using pip from the repository here: https://github.com/slaclab/slac-alarm-manager
