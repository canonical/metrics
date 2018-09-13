import json
from typing import List, Optional
from urllib.parse import urljoin

from simplestreams.contentsource import UrlContentSource
from simplestreams.filters import ItemFilter as SSFilter
from simplestreams.generate_simplestreams import FileNamer
from simplestreams.util import products_exdata

UBUNTU_CLOUD_IMAGES_BASE_URL = 'http://cloud-images.ubuntu.com'
UBUNTU_CLOUD_IMAGE_INDEXES = ['releases', 'daily',
                              'minimal/releases', 'minimal/daily']

PEDIGREE_STREAM_PROPERTIES = ['cloudname', 'datatype', 'index_path']
'''simplestream index entry properties to include into product items'''


class ProductsContentSource(UrlContentSource):
    def __init__(self, url, mirrors=None, url_reader=None, stream_info=None):
        super().__init__(url, mirrors, url_reader)
        self.info = stream_info or {}

    def _extend_item_info(self, item):
        for prop in PEDIGREE_STREAM_PROPERTIES:
            val = self.info.get(prop)
            if val:
                item[prop] = val
        return item

    def get_product_items(self, filter: Optional[SSFilter] = None):
        filter = filter or AndFilter()

        contents = super().read()
        super().close()
        stream = json.loads(contents)
        assert stream.get('format') == 'products:1.0', \
            'simplestreams product stream is of supported version'

        for product_name, product in stream.get('products', {}).items():
            for version_name, version in product.get('versions', {}).items():
                for item_name, item in version.get('items', {}).items():

                    pedigree = (product_name, version_name, item_name)
                    item = products_exdata(stream, pedigree)
                    item = self._extend_item_info(item)

                    if filter.matches(item):
                        yield item

    def __str__(self):
        return '<{}({})>'.format(type(self).__name__, self.url)


STREAM_READERS = {'products:1.0': ProductsContentSource}


class IndexContentSource(UrlContentSource):
    def __init__(self, base_url, entry_readers=STREAM_READERS, info=None):
        base_url = base_url.rstrip('/') + '/'
        known_idx_path = FileNamer.get_index_path()
        super().__init__(urljoin(base_url, known_idx_path))
        self.base_url = base_url
        self.entry_readers = entry_readers
        self.info = info or {}

    def get_product_streams(self, filter: Optional[SSFilter] = None):
        filter = filter or AndFilter()

        contents = super().read()
        super().close()
        index = json.loads(contents)

        assert index.get('format') == 'index:1.0', \
            'simplestreams index is of supported version'

        for cloud, info in index['index'].items():
            assert info['format'] in self.entry_readers, \
                'stream format is known'

            info.update(self.info)  # copying index properties onto stream

            if filter.matches(info):
                stream_reader_cls = self.entry_readers[info['format']]
                stream = stream_reader_cls(
                    urljoin(self.base_url, info['path']),
                    stream_info=info
                )
                yield stream

    def __str__(self):
        return '<{}({})>'.format(type(self).__name__, self.url)


class UbuntuCloudImages:
    indexes: List[IndexContentSource] = None

    def __init__(self, base_url=UBUNTU_CLOUD_IMAGES_BASE_URL,
                 index_paths=UBUNTU_CLOUD_IMAGE_INDEXES):
        self.indexes = []
        for index in index_paths:
            self.indexes.append(
                IndexContentSource(
                    urljoin(base_url, index),
                    info={'index_path': index}
                )
            )

    def get_product_streams(self, filter=None):
        for index in self.indexes:
            yield from index.get_product_streams(filter)

    def get_product_items(self, stream_filter=None, item_filter=None):
        for stream in self.get_product_streams(stream_filter):
            yield from stream.get_product_items(item_filter)


class ItemFilter(SSFilter):
    def __or__(self, other):
        return OrFilter(self, other)

    def __and__(self, other):
        return AndFilter(self, other)

    def __neg__(self):
        return NotFilter(self)


def ifilter(expr, noneval=""):
    return ItemFilter(expr, noneval)


class LogicFilter(ItemFilter):
    operation = lambda v: bool(v)
    symbol = 'bool'

    def __init__(self, *filters, noneval=""):
        self.filters = [ItemFilter(f, noneval)
                        if isinstance(f, str) else f for f in filters]

    def __str__(self):
        return (self.symbol+'({})').format(
            ','.join([str(f) for f in self.filters])
        )

    def __repr__(self):
        return self.__str__()

    def matches(self, item):
        op = self.operation
        filters_eval = [f.matches(item) for f in self.filters]
        return op(filters_eval)


class OrFilter(LogicFilter):
    operation = any
    symbol = 'any'


class AndFilter(LogicFilter):
    operation = all
    symbol = 'all'


class NotFilter(LogicFilter):
    operation = lambda _, v: all([not x for x in v])
    symbol = '!'

