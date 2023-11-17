# coding: utf8
import json
import sys
import logging
from typing import List

from selenium.webdriver.common.by import By
import jieba.analyse as ana
import feedparser

from chrome import chrome as f_chrome
from settings import dsa_client

logger = logging.getLogger('dsa.spider.runner')

linux_config = dict(pic=False, headless=True, use_gpu=False)
windows_config = dict(pic=False, )
CHROME = f_chrome(**(windows_config if sys.platform == 'win32' else linux_config))

def secure_filename(s: str) -> str:
    """返回一个转换后的安全的文件名称"""
    unsafe_chars = '/\\><:\'"!@#•$%^&*()\n|.'
    for _c in unsafe_chars:
        s = s.replace(_c, '_')
    return s[:20]


def has_chinese(s: str, threshold=1) -> bool:
    """一个str中是否有中文"""
    _ec = 0
    for _c in s:
        if '\u4e00' <= _c <= '\u9fa5':
            if _ec < threshold - 1:
                _ec += 1
            else:
                return True
    return False


def load_selector(selector_value: str) -> list[str]:
    """一个适配器，这样 model.Config.selector_list 支持 str 和 list"""
    if isinstance(selector_value, List):
        return selector_value
    try:
        return json.loads(selector_value)
    except (json.JSONDecodeError, TypeError) as _e:
        if selector_value:
            return [selector_value, ]
        return []


class Finds:


    def __init__(self, config):
        self.config = config
        self.news = config['link']
        self.selector_page_list = load_selector(config.get('selector_list') or '[]')  # selector_list可能的值是 None 和 空字符串
        self.selector_page_text = load_selector(config.get('selector_page') or '[]')  # 同上
        self.browser = CHROME

    def titles(self) -> List[dict]:
        """获取标题列表"""
        self.browser.get(self.news)
        self.browser.implicitly_wait(10)

        # 遍历 model.Config.selector_list 的全部值，并将内容整合到一起
        elements = [ele for page_list in self.selector_page_list
                    for ele in self.browser.find_elements(By.CSS_SELECTOR, page_list)
                    ]

        return [{'title': ele.text, 'link': ele.get_attribute('href')} for ele in elements]

    def get_text(self, url) -> str:
        """从页面中检索内容，通过 config 中配置的CSS选择器。"""
        if not self.selector_page_text:
            logger.warning(f'{self.config.get("name")} 没有配置 selector_text 属性跳过 ...')
            return ''
        for page_text in self.selector_page_text:
            if not isinstance(page_text, str):
                logger.warning(f'{self.config.get("name")} 的 selector_text 中的每一项必须是一个str, \n'
                               f'但是得到 {type(page_text)}, ({page_text = }) ')
                return ''
        self.browser.get(url)
        self.browser.implicitly_wait(30)

        # 遍历 model.Config.selector_page 的全部值，并将内容整合到一起
        elements = [ele for page_text in self.selector_page_text
                    for ele in self.browser.find_elements(By.CSS_SELECTOR, page_text)
                    ]

        return '\n'.join(ele.text for ele in elements)


def rss(config) -> List[dict]:
    """RSS 配置"""
    return [{'title': p['title'],
             'description': p.get('description'),
             'link': p.get('link'),
             'page_time': p.get('pubDate')
             } for p in feedparser.parse(config['link'])['entries']]


def create(config):
    """向服务器推送新的文章标题和文章链接"""
    if not config.get('name'):
        raise FileNotFoundError("config 中没有发现名称")

    if config.get('type') == 'rss':
        titles = rss(config)
    else:
        titles = Finds(config).titles()

    try:
        for title in titles:
            title['source'] = config['name']

            dsa_client.page_create(
                title
            )
    except Exception as _e:
        logger.warning(_e)
        # TODO Next Page


def load_text(config):
    """从controller中获取当前配置中没有text的配置信息，"""
    for item in dsa_client.page_no_text():
        item: dict  # 拥有2个key的dict: page_id, link

        text = Finds(config).get_text(item['link'])

        if has_chinese(text):
            _k = ana.tfidf(text, 10)
        else:
            _k = []  # TODO English
        logger.info('Uploading page text: %s', item['page_id'])
        if text != '':
            dsa_client.page_update(
                {'page_id': item['page_id'],
                 'keywords': _k,
                 'text': text,
                 }
            )
        else:
            dsa_client.Cache.NOT_FOUND_TEXT_IDS.append(item['page_id'])
            logger.error('Not Found Text in this Page. link: %s', item['link'])
