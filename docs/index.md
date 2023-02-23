# SLAC Alarm Manager

The [SLAC Alarm Manager](https://github.com/slaclab/slac-alarm-manager) is a python package providing an interface to the [NALMS alarm system](https://slaclab.github.io/nalms/).
It contains two main ways of interacting with NALMS. There is a standalone python application for 
viewing and interacting with alarms described in greater detail [here](alarm_manager.md). And 
a [PyDM data plugin](pydm.md) that will allow for building PyDM displays containing summary alarms.

## Installation

The easiest installation method is using pip to install from PyPI into a virtual environment:

`pip install slac-alarm-manager`

It can also be installed from source using pip from the repository here: https://github.com/slaclab/slac-alarm-manager

## Setting up Alarm Configurations

The alarm hierarchies displayed in this system are defined using xml files. As an example, we can look at this file:

https://github.com/pcdshub/pcds-nalms/blob/master/XML/KFE/GMDXGMD.xml

The top level config name, `nalms-kfe-GMDXGMD`, represents the system being monitored. It will also be referred to
as the alarm topic or kafka topic in the rest of this documentation. A component is a way of grouping PVs together
in whatever way makes sense. For more information about the valid options for each pv, please see the description
of these at the NALMS documentation here: https://slaclab.github.io/nalms/configuration/.
