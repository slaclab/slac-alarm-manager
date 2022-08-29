[![CI Status](https://github.com/slaclab/slac-alarm-manager/actions/workflows/build-and-test.yml/badge.svg?branch=main)](https://github.com/slaclab/slac-alarm-manager/actions/workflows/build-and-test.yml)

## SLAC Alarm Manger

A user interface for monitoring and managing alarms written in Python. It is a frontend display for [NALMS](https://github.com/slaclab/nalms) and
requires a running NALMS deployment to interact with. Specifically it will consume messages from the kafka queue in order to put 
together the alarm tree hierarchy, and then continue to read updates to alarm severity in order to display them in the tree
and table views.

In addition to displaying data, this interface will allow users to take actions on alarms such as acknowledgments and enabling/disabling
specific alarms. These actions will be written into the kafka queue so that if multiple users have multiple copies of this
application running, each user will receive any commands run by each other user.


## Requirements

* Python 3.6+
* pydm
* kafka-python
* qtpy
* A Qt Python wrapper

Most requirements are listed in the `requirements.txt` file, but the qt wrapper is not allowing flexibility in the choice.

## Installation

This package can be installed from PyPI using the command `pip install slac-alarm-manager`.

Alternatively, it may also be installed from source by cloning the code from the repository, and running
`pip install .` from the top level slam directory. `pip install -e .` may also be used for to allow for easier development
on the project.

## Running Tests

In order to run all of the tests included with this project, a few additional test-only requirements must be installed
as included in `dev-requirements.txt`. This test suite will also be run as part of every pull request, and whenever
a new commit is made to main.
