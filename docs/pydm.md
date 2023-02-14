# PyDM Support

PyDM is a python based framework for building interfaces for control systems described in more details [here](https://slaclab.github.io/pydm/)
PyDM is able to read in data from multiple sources via data plugins, allowing a standard way for UI widgets
to receive and display data.

One such data plugin is included with the slac-alarm-manager package. An associated [entrypoint](https://pypi.org/project/entrypoints/)
will cause PyDM to automatically discover this data plugin and allow the user to build displays that include
data from the alarm system.

## Summary Alarm

Since PyDM already includes built-in support for fetching and displaying the alarm status of individual PVs, the 
main benefit of this new plugin is for the display of summary alarms.

## Creating a Sample Display