# -*- coding: utf-8 -*-
import json

import ccxt

from zvt import zvt_env, zvt_config
from zvt_crypto.settings import COIN_EXCHANGES


class CCXTAccount(object):
    exchange_cache = {}
    exchanges = COIN_EXCHANGES
    exchange_conf = {}

    @classmethod
    def init(cls):
        for exchange in cls.exchanges:
            import pkg_resources

            resource_package = 'zvt_crypto'
            resource_path = 'accounts/{}.json'.format(exchange)
            config_file = pkg_resources.resource_filename(resource_package, resource_path)

            with open(config_file) as f:
                cls.exchange_conf[exchange] = json.load(f)

    @classmethod
    def get_tick_limit(cls, exchange):
        return cls.exchange_conf[exchange]['tick_limit']

    @classmethod
    def get_kdata_limit(cls, exchange):
        return cls.exchange_conf[exchange]['kdata_limit']

    @classmethod
    def get_safe_sleeping_time(cls, exchange):
        return cls.exchange_conf[exchange]['safe_sleeping_time']

    @classmethod
    def get_ccxt_exchange(cls, exchange_str) -> ccxt.Exchange:
        if cls.exchange_cache.get(exchange_str):
            return cls.exchange_cache[exchange_str]

        exchange = eval("ccxt.{}()".format(exchange_str))
        exchange.apiKey = cls.exchange_conf[exchange_str]['apiKey']
        exchange.secret = cls.exchange_conf[exchange_str]['secret']
        # set to your proxies if need
        exchange.proxies = {'http': zvt_config['http_proxy'], 'https': zvt_config['https_proxy']}
        cls.exchange_cache[exchange_str] = exchange
        return exchange
