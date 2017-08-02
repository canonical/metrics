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

## How to Remove Metrics

If a metric is no longer useful or required there are two steps that need
to occur to remove it from Prometheus:

1. First, the metric needs to be deleted from the pushgateway so no new data
is scraped from the Prometheus server.

A user can use the web interface of the pushgateway to delete a job. Navigate
to the IP address and port of the pushgateway (e.g. http://PUSHGATEWAY_IP:9091)
and press the red "Delete Group" button on the left of the group that needs to
be deleted.

To delete via a CLI, run the following against the Pushgateway IP address and
job name:

```
curl -X DELETE http://PUSHGATEWAY_IP:9091/metrics/job/JOBNAME
```

For example, to delete on the localhost the job called "bug_totals":

```
curl -X DELETE http://127.0.0.1:9091/metrics/job/bug_totals
```

2. Now the metric needs to be deleted from Prometheus itself. To do this run
the following:

```
curl -g -X DELETE 'http://PROMETHEUS_IP:9090/api/v1/series?match[]=METRICNAME'
```

For example, to delete on the localhost the metric called 'bug_totals':

```
curl -g -X DELETE 'http://127.0.0.1/9090/api/v1/series?match[]=bug_totals'
```

If the metric was sucessfully deleted a message such as a following will
be returned:

```
{"status":"success","data":{"numDeleted":1}}
```

If however, an attempt is made to delete a non-existant metric the numDeleted
value will be 0.
