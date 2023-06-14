# coding: utf8
import sys
import logging
from typing import List

from selenium.webdriver.common.by import By
import jieba.analyse as ana
import feedparser

from chrome import chrome
from settings import dsa_client

logger = logging.getLogger('dsa.spider.runner')


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


class Finds:
    linux_config = dict(pic=False, headless=True, use_gpu=False)
    windows_config = dict(pic=False, )

    def __init__(self, config):
        self.config = config
        self.news = config['link']
        self.selector_page_list = config.get('selector_list', )
        self.selector_page_text = config.get('selector_page', )
        self.browser = chrome(**(self.windows_config if sys.platform == 'win32' else self.linux_config))

    def titles(self) -> List[dict]:
        """获取标题列表"""
        self.browser.get(self.news)
        self.browser.implicitly_wait(10)

        # 一个适配器，这样 model.Config.selector_list 支持 str 和 list
        if isinstance(self.selector_page_list, str):
            page_lists = [self.selector_page_list, ]
        else:
            page_lists = self.selector_page_list

        # 遍历 model.Config.selector_list 的全部值，并将内容整合到一起
        elements = [ele for page_list in page_lists
                    for ele in self.browser.find_elements(By.CSS_SELECTOR, page_list)
                    ]

        return [{'title': ele.text, 'link': ele.get_attribute('href')} for ele in elements]

    def get_text(self, url) -> str:
        """从页面中检索内容，通过 config 中配置的CSS选择器。"""
        if not self.selector_page_text:
            logger.warning(f'{self.config.get("name")} 没有配置 selector_text 属性跳过 ...')
            return ''
        self.browser.get(url)
        self.browser.implicitly_wait(10)

        # 一个适配器，这样 model.Config.selector_page 支持 str 和 list 支持 str 和 list
        if isinstance(self.selector_page_text, str):
            page_texts = [self.selector_page_text, ]
        else:
            page_texts = self.selector_page_text

        # 遍历 model.Config.selector_page 的全部值，并将内容整合到一起
        elements = [ele for page_text in page_texts
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
