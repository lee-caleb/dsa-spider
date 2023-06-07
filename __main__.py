#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
@File Name  : __main__.py
@Author     : LeeCQ
@Date-Time  : 2023/6/6 11:28
"""
import os
import sys
import atexit
import logging
import threading
import time

from settings import dsa_client

from spider import create, load_text

logger = logging.getLogger('dsa-spider.__main__')


def init():
    """初始化"""
    config = dsa_client.active_config()
    if config.get('id') is None:
        raise

    def heartbeats():
        while True:
            dsa_client.heartbeat()
            time.sleep(120)

    atexit.register(dsa_client.at_exit())  # 注册退出函数
    threading.Thread(target=heartbeats, daemon=True).start()  # 开启心跳守护线程
    return config


def main():
    """main pages"""
    config = init()
    # 爬取主页页面
    create(config)
    load_text(config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
