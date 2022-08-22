# AlarmPlugin

The `AlarmPlugin` class is a `PyDMPlugin` with support for reading alarm information from the NALMS kafka cluster.
It uses an entry point in order to be discoverable by `PyDM` such that installing this package into an environment which 
contains `PyDM` will allow it to be used. See here for more information: https://slaclab.github.io/pydm/data_plugins/external_plugins.html

In order to connect to kafka correctly, two environment variable must be specified. `PYDM_KAFKA_ALARM_TOPIC` must be
set to the kafka topic to consume messages from. And `PYDM_KAFKA_BOOTSTRAP_SERVERS` must be set to the correct url for
connecting to the kafka cluster. If either of these is not set, the connection to the cluster will not be made and
no messages will be read.

To use this plugin with PyDM displays, the new protocol `nalms://` has been created. Any widget which specifies a
channel starting with `nalms://` will be routed to the `AlarmPlugin`, and any updates to the alarm severity of the
channel being monitored will be sent back to the widget.
