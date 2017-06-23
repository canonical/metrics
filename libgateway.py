"""Wrapper around Prometheus Gateway library"""
import sys
import urllib

from prometheus_client import push_to_gateway

INSTANCE = 'ubuntu-server'
PROMETHEUS_IP = '10.245.168.18:9091'


def push2gateway(pkg, registry):
    """Wrapper around push_to_gateway."""
    try:
        push_to_gateway(PROMETHEUS_IP,
                        job=pkg,
                        grouping_key={'instance': INSTANCE},
                        registry=registry)
    except urllib.error.URLError:
        print('Could not connect to push gateway!')
        sys.exit(1)
