# Metrics

[![Build Status](https://travis-ci.org/canonical-server/metrics.svg?branch=master)](https://travis-ci.org/canonical-server/metrics)


Scripts used to generate metrics for the Server and Foundations Teams.

## Setting Up a Local Environment for Testing

To test your metrics which will push data into a prometheus gateway you should setup a local prometheus pushgateway and prometheus server. Both of these are available as juju charms.

```
juju deploy cs:prometheus-pushgateway
juju deploy cs:prometheus
juju add-relation prometheus:target prometheus-pushgateway
```

To be able to run metrics you'll need to install python3-prometheus-client. With your local testing environment setup you can now push data into it, start with a known good script like foundations_proposed_migration.

```
METRICS_PROMETHEUS=$(juju status --format json | jq -r '.applications["prometheus-pushgateway"].units[]["public-address"]'):9091 python3 -m metrics.foundations_proposed_migration
```

You can then check on the metric by using the prometheus server, http://$PROMETHEUS_IP:9090, and inputing the metric name in the input text box e.g. foundations_proposed_migration.

## How to Run

Scripts should be run as follows:

```
python3 -m metrics.merges
python3 -m metrics.package cloud-init
```
