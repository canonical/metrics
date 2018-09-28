"""Simplestream filtering helper.

Copyright 2018 Canonical Ltd.
Aleksandr Bogdanov <aleksandr.bogdanov@canonical.com>
"""

import json
from typing import List, Optional
from urllib.parse import urljoin
import logging

from simplestreams.contentsource import UrlContentSource
from simplestreams.filters import ItemFilter as SSFilter
from simplestreams.generate_simplestreams import FileNamer
from simplestreams.util import products_exdata, expand_tree

logger = logging.getLogger(__name__)

UBUNTU_CLOUD_IMAGES_BASE_URL = 'http://cloud-images.ubuntu.com'
UBUNTU_CLOUD_IMAGE_INDEXES = ['releases', 'daily',
                              'minimal/releases', 'minimal/daily']

PEDIGREE_STREAM_PROPERTIES = ['cloudname', 'datatype', 'index_path']
'''simplestream index entry properties to include into product items'''


class ProductsContentSource(UrlContentSource):
    """A UrlContentSource that can work with ubuntu-shaped image feeds."""

    def __init__(self, url, mirrors=None, url_reader=None, stream_info=None):
        """Construct the class."""
        super().__init__(url, mirrors, url_reader)
        self.info = stream_info or {}

    def _extend_item_info(self, item):
        for prop in PEDIGREE_STREAM_PROPERTIES:
            val = self.info.get(prop)
            if val:
                item[prop] = val
        return item

    def get_product_items(self, itemfilter: Optional[SSFilter] = None):
        """
        Parse products from this ContentSource, matching the filter.

        :param itemfilter: simplestreams.filters.ItemFilter
        """
        itemfilter = itemfilter or AndFilter()  # empty AndFilter is true

        logger.debug('Fetching %s', self)

        contents = super().read()
        super().close()
        stream = json.loads(contents)
        assert stream.get('format') == 'products:1.0', \
            'simplestreams product stream is of supported version'

        expand_tree(stream)

        for product_name, product in stream.get('products', {}).items():
            for version_name, version in product.get('versions', {}).items():
                for item_name, item in version.get('items', {}).items():

                    pedigree = (product_name, version_name, item_name)
                    item = products_exdata(stream, pedigree)
                    item = self._extend_item_info(item)

                    if itemfilter.matches(item):
                        yield item

    def __str__(self):
        """Return str(self)."""
        return '<{}({})>'.format(type(self).__name__, self.url)


STREAM_READERS = {'products:1.0': ProductsContentSource}


class IndexContentSource(UrlContentSource):
    """A UrlContentSource that can work with ubuntu-shaped stream indices."""

    def __init__(self, base_url, entry_readers=STREAM_READERS, info=None):
        """Construct the class."""
        base_url = base_url.rstrip('/') + '/'
        known_idx_path = FileNamer.get_index_path()
        super().__init__(urljoin(base_url, known_idx_path))
        self.base_url = base_url
        self.entry_readers = entry_readers
        self.info = info or {}

    def get_product_streams(self, itemfilter: Optional[SSFilter] = None):
        """
        Parse streams from this ContentSource, matching the filter.

        :param itemfilter: simplestreams.filters.ItemFilter
        """
        itemfilter = itemfilter or AndFilter()

        logger.debug('Fetching %s', self)

        contents = super().read()
        super().close()
        index = json.loads(contents)

        assert index.get('format') == 'index:1.0', \
            'simplestreams index is of supported version'

        for info in index['index'].values():
            assert info['format'] in self.entry_readers, \
                'stream format is known'

            info.update(self.info)  # copying index properties onto stream

            if itemfilter.matches(info):
                stream_reader_cls = self.entry_readers[info['format']]
                stream = stream_reader_cls(
                    urljoin(self.base_url, info['path']),
                    stream_info=info
                )
                yield stream

    def __str__(self):
        """Return str(self)."""
        return '<{}({})>'.format(type(self).__name__, self.url)


class UbuntuCloudImages:
    """Aggregates all the image indices on cloud-images.ubuntu.com."""

    indexes: List[IndexContentSource] = None

    def __init__(self, base_url=UBUNTU_CLOUD_IMAGES_BASE_URL,
                 index_paths=UBUNTU_CLOUD_IMAGE_INDEXES):
        """Construct the class."""
        self.indexes = []
        for index in index_paths:
            self.indexes.append(
                IndexContentSource(
                    urljoin(base_url, index),
                    info={'index_path': index}
                )
            )

    def get_product_streams(self, stream_filter=None):
        """Aggregate get_product_streams of all the sub-indexes in Ubuntu."""
        for index in self.indexes:
            yield from index.get_product_streams(stream_filter)

    def get_product_items(self, stream_filter=None, item_filter=None):
        """Aggregate get_product_items of all streams of all sub-indexes."""
        for stream in self.get_product_streams(stream_filter):
            yield from stream.get_product_items(item_filter)


class ItemFilter(SSFilter):
    """Item filtering helper for syntax sugar."""

    def __or__(self, other):
        """Provide syntactic sugar."""
        return OrFilter(self, other)

    def __and__(self, other):
        """Provide syntactic sugar."""
        return AndFilter(self, other)

    def __neg__(self):
        """Provide syntactic sugar."""
        return NotFilter(self)


def ifilter(expr, noneval=""):
    """Item filtering helper for syntax sugar."""
    return ItemFilter(expr, noneval)


class LogicFilter(ItemFilter):
    """Item filtering helper for syntax sugar."""

    operation = bool
    symbol = 'bool'

    def __init__(self, *filters, noneval=""):
        """Construct the class."""
        self.filters = [ItemFilter(f, noneval)
                        if isinstance(f, str) else f for f in filters]

    def __str__(self):
        """Return str(self)."""
        return (self.symbol+'({})').format(
            ','.join([str(f) for f in self.filters])
        )

    def matches(self, item):
        """Check if the item dict passes the current filter collection."""
        filters_eval = [f.matches(item) for f in self.filters]
        retval = self.operation(filters_eval)
        return retval

    def non_matching_recursive_filters(self, item):
        """
        Provide debug info on "why this logic filter does not pass my item".

        :return: offending filters generator
        """
        if isinstance(self, OrFilter):  # at least one should match
            if not self.matches(item):  # if none of them match, yield'em all
                yield from self.filters

        else:
            for itemfilter in self.filters:
                if isinstance(itemfilter, LogicFilter):
                    yield from itemfilter.non_matching_recursive_filters(item)
                else:
                    if not itemfilter.matches(item):
                        yield itemfilter


class OrFilter(LogicFilter):
    """Item filtering helper for syntax sugar."""

    operation = any
    symbol = 'any'


class AndFilter(LogicFilter):
    """Item filtering helper for syntax sugar."""

    operation = all
    symbol = 'all'


class NotFilter(LogicFilter):
    """Item filtering helper for syntax sugar."""

    symbol = '!'

    @staticmethod
    def operation(value):
        """Inverse the filter."""
        return all([not x for x in value])
