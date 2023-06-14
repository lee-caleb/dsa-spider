#!/bin/env python3
# coding: utf-8
import json
import time
from typing import List

import feedparser

from spider import Finds, rss
from settings import dsa_client

CONFIG = {
    'name': '匈牙利国家数据保护和信息自由局 - 英语',
    'type': 'html',
    'link': 'https://www.naih.hu/news',
    'selector_list': '#jm-maincontent > div > div.items-row > div > div > div > h2 > a',
    'selector_page': '#jm-maincontent > div > div'
}


def find_list(config: dict):
    if not config.get('name'):
        raise FileNotFoundError("config 中没有发现名称")

    if config.get('type') == 'rss':
        titles: List[dict] = rss(config)
    else:
        titles: List[dict] = Finds(config).titles()

    i = 0
    for title in titles:
        i += 1
        print(i, json.dumps(title, indent=2, ensure_ascii=False))


def find_page(config, page_link):
    """找到内容"""
    text = Finds(config).get_text(page_link)
    print('text', text)


if __name__ == '__main__':
    link = "https://www.naih.hu/news/537-notice-of-the-publication-obligation-on-the-central-information-public-data-registry-online-platform-and-the-transparency-procedure"
    # find_list(CONFIG)
    find_page(CONFIG, link)
