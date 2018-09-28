#!/usr/bin/env python3
"""Load CSV file data and push to InfluxDB."""
import argparse
import csv
import sys

from metrics.helpers import util


def _parse_value_type(value_type):
    if value_type == 'float':
        return float
    elif value_type == 'int':
        return int
    elif value_type == 'str':
        return str
    else:
        raise ValueError('Unknown value_type: ', value_type)


def csv2influx(csv_filename, measurement, use_tags=None, value_type=None):
    """
    Push CSV data to InfluxDB.

    @param csv_filename: csv filename to load into InfluxDB
    @param measurement: measurement name to use for data
    @param use_tags: use these columns as tags, not value keys
    @param value_type: cast value columns to this type
    """
    data = []

    value_type = _parse_value_type(value_type or 'int')

    with open(csv_filename) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            date = row.pop('date')

            try:
                tags = {k: row.pop(k) for k in use_tags} if use_tags else {}
                fields = {k: value_type(v) if v else 0
                          for k, v in dict(row).items()}
            except TypeError:
                print('Unknown value (not an int) on this row:')
                print(row)
                sys.exit(1)

            entry = {
                "measurement": measurement,
                "fields": fields,
                "tags": tags,
                "time": date
            }
            data.append(entry)

    util.influxdb_insert(data)
    print('wrote {} datapoints'.format(len(data)))


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('csv',
                        help='csv file to inject into influxdb')
    PARSER.add_argument('--measurement', required=True,
                        help='Name of measurement')
    PARSER.add_argument('--value-type', default='int',
                        help='Type of value column (float, int or str)')
    PARSER.add_argument('--tag', default=None, action='append',
                        help='Use a csv column as tag. '
                             'Can be specified multiple times')
    PARSER.add_argument('--database',
                        help='')

    ARGS = PARSER.parse_args()

    csv2influx(ARGS.csv, ARGS.measurement, ARGS.tag, ARGS.value_type)
