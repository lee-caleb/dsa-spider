#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@File Name  : __main__.py
@Author     : LeeCQ
@Date-Time  : 2023/6/6 11:28
"""

import atexit
import logging
import threading
import time
import json
from logging.config import dictConfig
from pathlib import Path

from settings import dsa_client, DSA_DEBUG, DSA_AUTH, DSA_HTTP, DSA_CONFIG
from dsa_api import ActiveConfigNotFoundError
from spider import create, load_text

logger = logging.getLogger('dsa.spider.__main__')


def filter_maker(level__lte, ex_names):
    """日志过滤器"""
    level__lte = getattr(logging, level__lte)

    def _filter(record):
        record: logging.LogRecord
        if record.name in ex_names and record.levelno <= level__lte:
            return False
        return True

    return _filter


def init():
    """初始化"""
    config = dsa_client.active_config(force_config=DSA_CONFIG)
    if config.get('id') is None:
        raise

    def heartbeats():
        while True:
            dsa_client.heartbeat()
            time.sleep(120)

    dsa_client.log_start()
    atexit.register(dsa_client.at_exit)  # 注册退出函数
    threading.Thread(target=heartbeats, daemon=True).start()  # 开启心跳守护线程
    print(config['name'], file=open('last_config_name', 'w', encoding='utf8'))
    return config


def main():
    """main pages"""
    config = init()
    # 爬取主页页面
    # logger.info('===== Load Text ======')
    # load_text(config)
    logger.info('===== Load List ======')
    create(config)
    logger.info('===== Load Text ======')
    load_text(config)


if __name__ == "__main__":
    for i in Path(__file__).parent.joinpath('logs').iterdir():
        i.unlink()

    dictConfig(json.loads(open('logger_settings.json', 'r', encoding='utf8').read()))
    logger.info(f'Load Env Settings: \n{DSA_HTTP=} \n{DSA_AUTH=} \n{DSA_CONFIG=} \n{DSA_DEBUG=}')
    try:
        main()
        dsa_client.Cache.EXIT_STATUS = 'Success'
        _exit_code = 0
    except ActiveConfigNotFoundError:
        _exit_code = 119
    except Exception as _e:
        dsa_client.Cache.EXIT_STATUS = _e
        logger.error('Has a Error in running, %s', _e, exc_info=_e)
        _exit_code = 1
        raise _e
    finally:
        logger.info(
            'News Update: \n'
            'Created New Page: %d\n'
            'Update Page\'s Text: %d',
            dsa_client.Cache.COUNT_NEW_PAGE,
            dsa_client.Cache.COUNT_UPDATE_TEXT,
        )

    exit(_exit_code)
