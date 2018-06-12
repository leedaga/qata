#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This is a skeleton file that can serve as a starting point for a Python
console script. To run this script uncomment the following line in the
entry_points section in setup.py:

    [console_scripts]
    fibonacci = qata.skeleton:run

Then run `python setup.py install` which will install the command `fibonacci`
inside your current environment.
Besides console scripts, the header (i.e. until _logger...) of this file can
also be used as template for Python modules.

Note: This skeleton file can be safely removed if not needed!
"""
from __future__ import division, print_function, absolute_import

import argparse
import sys
import logging

import pymongo
from pytdx.exhq import TdxExHq_API
from pytdx.params import TDXParams
from datetime import datetime, time, timedelta
from functools import partial
from qata import __version__
sys.excepthook = sys.__excepthook__

__author__ = "hardywu"
__copyright__ = "hardywu"
__license__ = "mit"

QSIZE = 500
_logger = logging.getLogger(__name__)

def parse_record(ticker, record):
    bar = record.copy()
    bar['datetime'] = datetime.strptime(bar['datetime'], '%Y-%m-%d %H:%M')
    bar['ticker'] = ticker
    for key in ['year', 'month', 'day', 'hour', 'minute', 'price']:
        bar.pop(key, None)
    bar['oi'] = bar.pop('position', None)
    bar['volume'] = bar.pop('trade', None)
    bar['turnover'] = bar.pop('amount', None)
    return bar

def update_futures(args):
    """Update Future 1min data in MongoDB

    Args:
    Returns:
    """
    client = pymongo.MongoClient(args.mongo_uri, serverSelectionTimeoutMS=1000)
    client.server_info()
    min1_db = client['avaloron']
    col = min1_db['future_china_1min']
    api = TdxExHq_API(heartbeat=True, multithread=True)
    api.connect('61.152.107.141', 7727)
    num = api.get_instrument_count()
    insts = [api.get_instrument_info(i, QSIZE) for i in range(0, num, QSIZE)]
    insts = [x for i in insts for x in i]
    ex = ['中金所期货', '上海期货', '大连商品', '郑州商品']
    markets = [t['market'] for t in api.get_markets() if t['name'] in ex]
    ensure_fut = lambda t: (t['market'] in markets) and (t['code'][-2] != 'L')
    futures =  [t for t in insts if ensure_fut(t)]
    for future in futures:
        qeury = col.find({"ticker": future['code']})
        qeury = qeury.sort('datetime', pymongo.DESCENDING)
        qeury = qeury.limit(1)
        last_one = list(qeury)

        if len(last_one) > 0:
            last_date = last_one[-1]['datetime'] + timedelta(minutes=1)
        else:
            last_date = datetime.now() - timedelta(days=365)
        end_date = datetime.now().date()
        end_date = datetime.combine(end_date - timedelta(days=1), time(15,0))
        _start_date = end_date
        _bars = []
        _pos = 0
        while _start_date > last_date:
            _res = api.get_instrument_bars(TDXParams.KLINE_TYPE_1MIN,
                future['market'],
                future['code'],
                _pos,
                QSIZE)
            try:
                _bars += _res
            except TypeError:
               continue
            _pos += QSIZE
            if len(_res) > 0:
                _start_date = _res[0]['datetime']
                _start_date = datetime.strptime(_start_date, '%Y-%m-%d %H:%M')
            else:
                break
        if len(_bars) == 0:
            continue
        parser = partial(parse_record, future['code'])
        data = list(map(parser, _bars))
        data.sort(key=lambda x: x['datetime'])
        _s = lambda x: x['datetime'] >= last_date and x['datetime'] <= end_date
        data = list(filter(_s, data))
        col.insert_many(data) if len(data) > 0 else 0

        _logger.info(future['code'])
    api.disconnect()

def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="Data Maintainance Tool for Quantitative Investment")
    parser.add_argument(
        '--version',
        action='version',
        version='qata {ver}'.format(ver=__version__))
    parser.add_argument(
        '-v',
        '--verbose',
        dest="loglevel",
        help="set loglevel to INFO",
        action='store_const',
        const=logging.INFO)
    parser.add_argument(
        '-vv',
        '--very-verbose',
        dest="loglevel",
        help="set loglevel to DEBUG",
        action='store_const',
        const=logging.DEBUG)
    parser.set_defaults(loglevel=logging.INFO)
    subparsers = parser.add_subparsers()
    parser_future = subparsers.add_parser('futures')
    parser_future.add_argument(
        '-d',
        '--mongo',
        dest='mongo_uri',
        help="set MongoDB uri",
        action='store',
        default='localhost:27017')
    parser_future.set_defaults(func=update_futures)
    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")


def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    _logger.debug("Starting crazy calculations...")
    args.func(args)
    _logger.info("Script ends here")


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
