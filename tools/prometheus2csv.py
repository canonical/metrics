#!/usr/bin/env python3
"""Query Prometheus for a particular metric and optionally specific labels."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
import sys

import requests

from metrics.helpers import util


def print_result(date, value):
    """
    Print the results in CSV format.

    @param date: Date from Prometheus to convert to rfc3339 date
    @param value: Values to print out
    """
    # convert unix timestamp to rfc3339 (YYYY-MM-DDTHH:MM:SS)
    rfc3339 = datetime.fromtimestamp(date).isoformat('T') + 'Z'
    print('%s,%s' % (rfc3339, value))


def print_simple(results, metric):
    """
    Print single dimentional result.

    @param results: results returned by query
    @param metric: metric name
    """
    print('date,%s' % (metric))
    for data in results[0]['values']:
        print_result(data[0], data[1])


def print_multi_result(results, label):
    """
    Print result with multiple dimentions due to labels.

    @param results: results returned by query
    @param label: specific label to look for in results
    """
    headers = []
    data = defaultdict(defaultdict)
    for result in results:
        try:
            header = result['metric'][label]
        except KeyError:
            print('cannot find label \'%s\' choose from:' % label)
            print(', '.join(results[0]['metric'].keys()))
            sys.exit(1)

        if header not in headers:
            headers.append(header)
        for value in result['values']:
            data[value[0]][header] = value[1]

    print('date,%s' % ','.join(headers))
    for date, values in data.items():
        results = ['%s' % date]
        for header in headers:
            try:
                results.append(values[header])
            except KeyError:
                # use an empty string rather than 0
                results.append('')
                pretty_date = datetime.fromtimestamp(date).strftime('%Y-%m-%d')
        print(','.join(results))


def print_with_labels(results, labels):
    """
    Print timeseries values, adding labels as extra csv columns.

    :param results: Prometheus result collection
    :param labels: a list of metric names to extract into columns
    :return: None
    """
    print('date,value,%s' % ','.join(labels))
    for result in results:
        metric = result.get('metric', {})
        for date, value in result.get('values', []):
            print_result(date,
                         ','.join([value] + [metric.get(L) for L in labels]))


def query_prometheus(url, params):
    """
    Query Prometheus for data.

    @param url: URL to query against (e.g. http://IP:PORT/api/v1/query_range)
    @param params: dictionary of parameters
    """
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print('%s %s: %s' % (response.status_code, response.reason,
                             response.text))
        sys.exit(1)

    results = response.json()['data']['result']

    if not results:
        print('no result')
        sys.exit(1)

    return results


def runner(metric, label, days, step, attach_labels=None):
    """
    Query Prometheus for specific metric print out csv output.

    @param metric: name of metric to get
    @param label_key: use specified label key instead of metric name
    @param days: number of days to get data for
    @param step: time step in results
    @param attach_labels: extract metrics with their label values
    """
    server_address = util.get_prometheus_ip()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(days))

    url = '%s/api/v1/query_range' % server_address

    if label:
        query = metric
    else:
        query = 'avg(%s)' % metric

    if attach_labels:
        query += ' by ({})'.format(','.join(attach_labels))

    params = {
        'query': query,
        'start': start_date.strftime('%Y-%m-%dT%H:00:00Z'),
        'end': end_date.strftime('%Y-%m-%dT%H:00:00Z'),
        'step': step,
    }

    results = query_prometheus(url, params)

    if len(results) == 1:
        print_simple(results, metric)
    elif label:
        print_multi_result(results, label)
    elif attach_labels:
        print_with_labels(results, attach_labels)

    else:
        print('multi-dimentional results, please specify a label from:')
        print(', '.join(results[0]['metric'].keys()))
        print('result data:')
        print(results[0]['metric'])
        sys.exit(1)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('metric',
                        help='metric to lookup in Prometheus')
    PARSER.add_argument('--label',
                        help='specific label to use as header')
    PARSER.add_argument('--days', default=180,
                        help='How many days of data to get')
    PARSER.add_argument('--step', default='1h',
                        help='Interval of results')
    PARSER.add_argument('--attach-label', default=None, action='append',
                        help='Include a label into the output. '
                             'Can be specified multiple times. '
                             'Metric value column will be called "value". '
                             'Does not work with --label')

    ARGS = PARSER.parse_args()

    runner(ARGS.metric, ARGS.label, ARGS.days, ARGS.step, ARGS.attach_label)
