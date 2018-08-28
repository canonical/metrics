#!/usr/bin/env python3
"""Load CSV file data and push to InfluxDB."""
import argparse
import csv
import sys

from metrics.helpers import util


def csv2influx(csv_filename, measurement):
    """
    Push CSV data to InfluxDB.

    @param csv_filename: csv filename to load into InfluxDB
    @param measurement: measurement name to use for data
    """
    data = []
    with open(csv_filename) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            date = row.pop('date')

            try:
                fields = {k:int(v) if v else 0 for k, v in dict(row).items()}
            except TypeError:
                print('Unknown value (not an int) on this row:')
                print(row)
                sys.exit(1)

            entry = {
                "measurement": measurement,
                "fields": fields,
                "time": date
            }
            data.append(entry)

    util.influxdb_insert(data)


if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()
    PARSER.add_argument('csv',
                        help='csv file to inject into influxdb')
    PARSER.add_argument('--measurement', required=True,
                        help='Name of measurement')
    PARSER.add_argument('--database',
                        help='')

    ARGS = PARSER.parse_args()

    csv2influx(ARGS.csv, ARGS.measurement)
