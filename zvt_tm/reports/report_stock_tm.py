# -*- coding: utf-8 -*-
import logging
import time
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from zvt import init_log
from zvt.contract import IntervalLevel
from zvt.contract.api import get_entities
from zvt.domain import Stock, StockTradeDay, Stock1dKdata, StockValuation, Block, BlockStock
from zvt.factors.target_selector import TargetSelector
from zvt.utils.pd_utils import pd_is_not_null
from zvt.utils.time_utils import now_pd_timestamp, to_pd_timestamp
from zvt_crypto import Coin

from zvt_tm.factors.block_selector import BlockSelector
from zvt_tm.factors.tm_factor import TMFactor
from zvt_tm.informer.discord_informer import DiscordInformer

logger = logging.getLogger(__name__)

sched = BackgroundScheduler()


@sched.scheduled_job('cron', hour=19, minute=0, day_of_week='mon-fri')
def report_tm():
    while True:
        error_count = 0
        discord_informer = DiscordInformer()

        try:
            # 抓取k线数据
            # StockTradeDay.record_data(provider='baostock', sleeping_time=2)
            # Stock1dKdata.record_data(provider='baostock', sleeping_time=1.5)

            latest_day: StockTradeDay = StockTradeDay.query_data(order=StockTradeDay.timestamp.desc(), limit=1,provider='joinquant',
                                                                 return_type='domain')
            if latest_day:
                target_date = latest_day[0].timestamp
            else:
                target_date = now_pd_timestamp()

            start_date = target_date - timedelta(60)

            # 计算
            my_selector = TargetSelector(entity_schema=Stock, provider='joinquant',
                                         start_timestamp=start_date, end_timestamp=target_date)
            # add the factors
            tm_factor = TMFactor(entity_schema=Stock, provider='joinquant',
                                 start_timestamp=start_date,
                                 end_timestamp=target_date)

            my_selector.add_filter_factor(tm_factor)

            my_selector.run()

            long_targets = my_selector.get_open_long_targets(timestamp=target_date)

            logger.info(long_targets)

            msg = 'no targets'

            # 过滤亏损股
            # check StockValuation data
            pe_date = target_date - timedelta(10)
            if StockValuation.query_data(start_timestamp=pe_date, limit=1, return_type='domain'):
                positive_df = StockValuation.query_data(provider='joinquant', entity_ids=long_targets,
                                                        start_timestamp=pe_date,
                                                        filters=[StockValuation.pe > 0],
                                                        columns=['entity_id'])
                bad_stocks = set(long_targets) - set(positive_df['entity_id'].tolist())
                if bad_stocks:
                    stocks = get_entities(provider='joinquant', entity_schema=Stock, entity_ids=bad_stocks,
                                          return_type='domain')
                    info = [f'{stock.name}({stock.code})' for stock in stocks]
                    msg = '亏损股:' + ' '.join(info) + '\n'

                long_stocks = set(positive_df['entity_id'].tolist())

                if long_stocks:
                    # use block to filter
                    block_selector = BlockSelector(start_timestamp='2020-01-01', long_threshold=0.8)
                    block_selector.run()
                    long_blocks = block_selector.get_open_long_targets(timestamp=target_date)
                    if long_blocks:
                        blocks = Block.query_data(provider='sina', entity_ids=long_blocks,
                                                               return_type='domain')

                        info = [f'{block.name}({block.code})' for block in blocks]
                        msg = ' '.join(info) + '\n'

                        block_stocks = BlockStock.query_data(provider='sina',  filters=[
                                                                                   BlockStock.stock_id.in_(long_stocks)],
                                                                               entity_ids=long_blocks, return_type='domain')

                        block_map_stocks = {}
                        for block_stock in block_stocks:
                            stocks = block_map_stocks.get(block_stock.name)
                            if not stocks:
                                stocks = []
                                block_map_stocks[block_stock.name] = stocks
                            stocks.append(f'{block_stock.stock_name}({block_stock.stock_code})')

                        for block in block_map_stocks:
                            stocks = block_map_stocks[block]
                            stock_msg = ' '.join(stocks)
                            msg = msg + f'{block}:\n' + stock_msg + '\n'

            discord_informer.send_message(f'{target_date} TM选股结果 {msg}')

            break
        except Exception as e:
            logger.exception('report_tm error:{}'.format(e))
            time.sleep(60 * 3)
            error_count = error_count + 1
            if error_count == 10:
                discord_informer.send_message(f'report_tm error',
                                              'report_tm error:{}'.format(e))


def get_turning_point(df, timestamp):
    if pd_is_not_null(df):
        if timestamp in df.index:
            df['difference'] = df.groupby('entity_id')['timestamp'].diff().fillna(0)
            df = df[df['difference'] > timedelta(days=1)]
            target_df = df.loc[[to_pd_timestamp(timestamp)], :]
            return target_df['entity_id'].tolist()
    return []


if __name__ == '__main__':
    init_log('repot_crypto_tm.log')
    report_tm()

    sched.start()

    sched._thread.join()
