# -*- coding: utf-8 -*-
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from zvt import init_log
from zvt.contract.api import get_entities
from zvt.domain import *
from zvt.informer.informer import EmailInformer

logger = logging.getLogger(__name__)

sched = BackgroundScheduler()


@sched.scheduled_job('cron', hour=6, minute=0)
def record_stock():
    while True:
        email_action = EmailInformer()

        try:
            Stock.record_data(provider='joinquant', sleeping_time=1)
            StockTradeDay.record_data(provider='joinquant', sleeping_time=1)
            # email_action.send_message("5533061@qq.com", 'joinquant record stock finished', '')
            break
        except Exception as e:
            msg = f'joinquant record stock:{e}'
            logger.exception(msg)

            # email_action.send_message("5533061@qq.com", 'joinquant record stock error', msg)
            time.sleep(60 * 5)


@sched.scheduled_job('cron', hour=15, minute=20)
def record_kdata():
    while True:
        email_action = EmailInformer()

        try:
            # 日线前复权和后复权数据
            # Stock1dKdata.record_data(provider='joinquant', sleeping_time=0)
            Stock1dHfqKdata.record_data(provider='joinquant', sleeping_time=0, day_data=True)
            # StockMoneyFlow.record_data(provider='joinquant', sleeping_time=0)
            # IndexMoneyFlow.record_data(provider='joinquant', sleeping_time=0)
            # email_action.send_message("5533061@qq.com", 'joinquant record kdata finished', '')
            break
        except Exception as e:
            msg = f'joinquant record kdata:{e}'
            logger.exception(msg)

            # email_action.send_message("5533061@qq.com", 'joinquant record kdata error', msg)
            time.sleep(60 * 5)


if __name__ == '__main__':
    init_log('joinquant_kdata_runner.log')
    record_kdata()

    # items = get_entities(entity_type='stock', provider='joinquant')
    # entity_ids = items['entity_id'].to_list()
    #
    # try:
    #     Stock1dKdata.record_data(provider='joinquant', entity_ids=entity_ids[4172:], sleeping_time=0.5)
    # except Exception as e:
    #     logger.exception('report_tm error:{}'.format(e))
    sched.start()

    sched._thread.join()
