# Metrics

[![Build Status](https://travis-ci.org/CanonicalLtd/metrics.svg?branch=master)](https://travis-ci.org/CanonicalLtd/metrics)

Scripts used to generate metrics for the Server and Foundations Teams.

## How to Run

### Invocation
Scripts should be run as follows:

```
python3 -m metrics.merges
python3 -m metrics.package cloud-init
```

## Development
All new developments are expected to meet the following conditions:

  * Run under Python 3, unless library requirements force Python 2 usage
  * Follow the structure and functionality of other existing metrics
    * This means the usage of argparse
    * Including a --dryrun option to test the metric without pushing data
    * In `if __name__ == '__main__':` function:
      * Handles arguments of argparse
      * Calls `collect` function with arguments
    * A `collect` function
      * Calls other functions to handle collecting data
      * Prints out results
      * Pushes data to gateway
  * Utilize a unique metric job name when pushing to Prometheus
      * Names should be prefaced with team name when applicable (e.g. 'server_metric')
  * Usage of noqa and pylint-ignore should be justified and limited to as few places as possible
  * Create the required merge request for the [jenkins-job](https://github.com/canonical-server/jenkins-jobs) project to collect the metrics
  * Manual verification of the results by the developer is expected. The merge reviewers will do a best effort if the data is easily accessible. 

## Testing
Testing can come in two forms: first, via tox that is used to lint the code and second, via local testing via juju. Both are detailed below.

### tox
[tox](https://tox.readthedocs.io/en/latest/) is a Python virtualenv tool used to ease Python testing. The configuration of tox occurs in the tox.ini file in the root of the project directory.

Running tox is as simple as installing tox (`apt install tox`) and invoking it. Here are some common use-cases:

```
# Run default tox configs
$ tox
# Get a list of all test enviornments
$ tox -l
# Run single environment
$ tox -e pylint
# Clear tox cache and run
$ tox -r
```

If adding new requirements to requirements.txt it is generally a good idea to clear the cache and rerun. We avoid doing this on every run only to save time.

The metric's tox.ini file dictates that by default these three tests should always run:

#### pycodestyle
`pycodestyle`, formerly known as `pep8`, is a tool to check your Python code against some of the style conventions in [PEP 8](https://www.python.org/dev/peps/pep-0008/). This check exists to make sure the code looks consistent and meets the generally accepted conventions.

#### pydocstyle
`pydocstyle` is a static analysis tool  for checking compliance with Python docstring conventions mainly [PEP 257](https://www.python.org/dev/peps/pep-0257/). This ensures that documentation of the metrics follows a consistent look and feel while meeting generally accepted conventions.

#### pylint
The most complex and difficult of the lint tests, `pylint` is a Python source code analyzer which looks for programming errors, helps to enforce a coding standard, completes complexity checking, and sniffs for some code smells.

There does exist a `.pylintrc` file to help configure pylint. Certain errors are marked as ignored here due to their either incorrect showing or common error we wish to ignore. Similarly modules that pylint has a hard time recognizing or are dynamically created during usage are marked as ignored. Ignoring errors and modules should be used only as a last resort and justified as such.

### Setting Up a Local Environment for Testing
To test your metrics you should setup a local Influx DB server. It is available as a juju charm.

```
juju deploy cs:influxdb
```

You'll need to create a database in Influx DB to which the scripts can write data.

```
juju ssh influxdb/0
influx
CREATE DATABASE foundations
```

To be able to run metrics you'll need to install python3-influxdb. With your local testing environment setup you can now push data into it, start with a known good script like docker_hub_images.

```
INFLUXDB_HOSTNAME=$(juju status --format json | jq -r '.applications["influxdb"].units[]["public-address"]') INFLUXDB_PORT=8086 INFLUXDB_USERNAME='' INFLUXDB_PASSWORD='' INFLUXDB_DATABASE=foundations python3 -m metrics.docker_hub_images
```

You can then check on the metric by using influx on the Influx DB server.

```
SELECT * FROM docker_hub_images WHERE suite = 'bionic'
```

## Remove Metrics from Prometheus and pushgateway
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

If however, an attempt is made to delete a non-existent metric the numDeleted value will be 0.
