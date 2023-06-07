import time
import logging

from selenium.webdriver.common.by import By
import jieba.analyse as ana
import feedparser

from chrome import chrome
from settings import dsa_client

logger = logging.getLogger('dsa.spider.runner')


def secure_filename(s: str) -> str:
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

    def __init__(self, config):
        self.config = config
        self.news = config['link']
        self.selector_page_list = config.get('selector_list')
        self.selector_page_text = config.get('selector_page')
        self.browser = chrome(incognito=True, pic=False)

    def titles(self) -> list:
        """获取标题列表"""
        self.browser.get(self.news)
        self.browser.implicitly_wait(10)
        elements = self.browser.find_elements(By.CSS_SELECTOR, self.selector_page_list)
        return [(ele.text, ele.get_attribute('href')) for ele in elements]

    def get_text(self, url):
        if not self.selector_page_text:
            logger.warning(f'{self.config.get("name")} 没有配置 selector_text 属性跳过 ...')
            return
        self.browser.get(url)
        self.browser.implicitly_wait(10)
        # lens = open(f'cache/{secure_filename(title)}.png', 'wb').write(
        #     self.browser.get_screenshot_as_png())  # screenshot
        return '\n'.join(
            [ele.text for ele in self.browser.find_elements(
                By.CSS_SELECTOR, self.selector_page_text)
             ]
        )


def create(config):
    """"""
    if not config.get('name'):
        raise FileNotFoundError("config 中没有发现名称")

    if config.get('type') == 'rss':
        titles = [(entry['title'], entry['link']) for entry in
                  feedparser.parse(config['link'])['entries']]
    else:
        titles = Finds(config).titles()

    try:
        for title, link in titles:
            dsa_client.page_create({
                'source': config['name'],
                'title': title,
                'link': link,
                'update_time': time.strftime('%Y-%m-%d %H:%M:%S %z')
            })
    except Exception as _e:
        logger.warning(_e)
        # TODO Next Page


def load_text(config):
    """加载正文"""
    for item in dsa_client.page_no_text():
        item: dict  # page_id, link

        text = Finds(config).get_text(item['link'])

        if has_chinese(text):
            _k = ana.tfidf(text, 10)
        else:
            _k = []  # TODO English
        logger.info('Uploading page text: %s', item['page_id'])
        dsa_client.page_update(
            {'page_id': item['page_id'],
             'keywords': _k,
             'text': text,
             }
        )
