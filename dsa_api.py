# coding: utf-8
import json
import logging
import re
import time
import zipfile
from hashlib import md5
from pathlib import Path
from typing import Union

import requests

from common import local_time

logger = logging.getLogger('dsa.spider.dsa-client')
__all__ = ['DSAClient']


class ActiveConfigNotFoundError(FileNotFoundError):
    pass


class DSAClient(requests.Session):
    """DSA Controller API 封装"""

    class Cache:
        LOG_ID = None
        EXIT_STATUS = 'Success'
        COUNT_NEW_PAGE = 0
        COUNT_UPDATE_TEXT = 0
        NOT_FOUND_TEXT_IDS = []

    def __init__(self, base_url='', auth=None):
        super().__init__()

        self.base_url = base_url
        self.headers.update({'User-Agent': 'dsa-spider/0.1'})
        self.params: dict = {}
        if auth:
            self.headers.update({'Auth': auth})

    def request(self, method, url, *args, **kwargs):
        """重写 Session.request，
        1. 将URI拼接为完整的URL，发起调用；
        2. 打印一些额外的日志；
        """
        _url = self.base_url + url
        logger.debug('Join a New URL,[%s] %s', method, _url)

        _resp = super().request(method, _url, *args, **kwargs)
        if '<!DOCTYPE html>' in _resp.text:
            Path(
                f'logs/{method}_{url.replace("/", "_").replace(":", "")}.html'
            ).write_text(_resp.text)
            logger.warning('[%s] %s return a HTML , it will be saved at logs', method, url)
        else:
            logger.debug('[%s] %s >>> %s', method, url, _resp.text)
        return _resp

    def client_get(self, url, *args, retry=0, **kwargs
                   ) -> Union[str, dict, list, int, type(None)]:
        """附带判定和重试的get请求，返回一个API的REST Ful API 中data内容， 否则返回None
        """

        _resp = self.get(url, *args, **kwargs)

        if _resp.status_code == 200:
            _resp_json = _resp.json()
            # 尴尬的是_resp_json有可能是一个列表而不是一个字典
            return _resp_json.get('date') if isinstance(_resp_json, dict) else _resp_json
        elif _resp.status_code == 406 and _resp.json()['status'] == 406:
            return None
        else:
            text = _resp.text
            logger.warning(
                'Get %s Error HTTP_CODE(%d), %s',
                url,
                _resp.status_code,
                re.findall(r'<title>(.*?)</title>', text) or text
            )
            time.sleep(3)
            if retry <= 3:
                logger.info('Retry to get active config, times: %d', retry + 1)
                return self.client_get(url, *args, retry=retry + 1, **kwargs)
            else:
                logger.error('Cannot access a %s from server.', url)
                return None

    _active_config = None

    def active_config(self, force_config=None):
        """从 Controller 获取到指定的配置，并缓存"""
        logger.info(f'{type(self._active_config)} - {self._active_config}')
        if self._active_config is not None and self._active_config:
            logger.info('DSA Active Config From Cache. name: %s', self._active_config.get('name'))
            return self._active_config

        # 如果指定 force_config 则获取一个指定配置，否则获取一个最不活跃的配置
        _resp: dict = self.client_get(f'/apis/config/{force_config}/' if force_config else '/apis/config/unlocked')

        if isinstance(_resp, dict) and _resp.get('name') is not None:
            self._active_config = _resp
            if self._active_config.get('name'):
                self.params.setdefault('source', self._active_config.get('name', ''))  # 添加请求默认参数 source
                self.params.setdefault('config_id', self._active_config.get('id', -1))  # 添加请求默认参数 config_id
            return _resp
        else:
            logger.error('Cannot access a config from server. _resp: %s', _resp)
            raise ActiveConfigNotFoundError()

    _page_ids = None

    @property
    def page_ids(self) -> set:
        """返回获取active Config 的Page ID，并缓存"""
        if isinstance(self._page_ids, set):
            return self._page_ids

        _resp = self.client_get(f'/apis/pages/id')
        self._page_ids = set(_resp or set())
        return self.page_ids

    _page_links = None

    @property
    def page_links(self) -> set:
        """返回active config 的 Page_link, 并缓存"""
        if isinstance(self._page_links, set):
            return self._page_links

        _resp = self.client_get('/apis/pages/link')
        self._page_links = set(_resp or set())
        return self.page_links

    def force_update_ips_from_pages(self):
        """从Page中更新IPS links"""
        logger.warning('正在从pages接口更新_page_ids, page_links')
        pages = self.client_get('/apis/pages')
        self._page_ids = {i['page_id'] for i in pages}
        self._page_links = {i['link'] for i in pages}

    def heartbeat(self):
        """向Controller发送一个心跳，表明当前配置活跃"""
        param = {'config_id': self._active_config['id']}
        logger.info('send a heartbeat to server.')
        _resp = self.get('/apis/config/heartbeat', params=param)
        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            return True
        return

    def page_create(self, body: dict):
        """向 Controller 创建一个新的page"""
        body['page_id'] = md5(f'{body["source"]}{body["title"]}{body["link"]}'.encode()).hexdigest()
        logger.info('Create a Page to Server, %s, %s', body['page_id'], body['title'])

        if body['page_id'] in self.page_ids:  # 判断page_id 是否重复
            logger.warning('duplication page_id %s, skip.', body['page_id'])
            return

        if body['link'] in self.page_links:  # 判定 page_link 是否重重
            logger.warning('duplication Page Link %s, skip.', body['link'])
            return

        _resp = self.post(f'/apis/page/{body["page_id"]}/', json=body)
        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            logger.info('Page [%s] is created at Server. ID: %s', body["title"], body['page_id'])
            self.Cache.COUNT_NEW_PAGE += 1
            return body['page_id']
        logger.warning(f'create page [%s] is Error, %s', body["title"], _resp.json()['message'])
        return None

    def page_update(self, body: dict):
        """更新Page text 到 Controller"""
        if not body.get('page_id'):
            logger.warning('Cannot Find a Page in body.\n'
                           'We will Create a page_id for this body, '
                           'but it may be do not at server.'
                           )
            body['page_id'] = md5(f'{body["source"]}{body["title"]}{body["link"]}'.encode()).hexdigest()

        _resp = self.put(f'/apis/page/{body["page_id"]}/', json=body)
        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            logger.info('Page %s of text is updated at Server. Len(%s)', body["page_id"], len(body['text']))
            self.Cache.COUNT_UPDATE_TEXT += 1
            return _resp.json()
        return

    def page_del(self, page_id):
        """删除一个配置 TODO 未实现"""
        logger.warning('')
        return self.delete(f'/apis/page/{page_id}/')

    def page_no_text(self, retry=0):
        """没有正文的page
        page_id, link
        """
        config_id = self._active_config['id']
        return self.client_get('/apis/pages/no_text/', params=dict(config_id=config_id)) or []

    def log_start(self):
        """记录日志开始"""
        body = {
            'source': self._active_config['name'],
            'status': 'Running',
            'start_time': local_time()
        }
        _resp = self.post('/apis/log/create', json=body)

        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            self.Cache.LOG_ID = _resp.json()['id']
        else:
            logger.error('Cannot Create log at Server, %s', _resp.json()['message'])

    def upload_logs(self):
        """上传日志"""
        with zipfile.ZipFile(f'log_{self.Cache.LOG_ID}.zip', 'w', compresslevel=9) as zz:
            for f in Path('logs').iterdir():
                zz.write(f)

            zz.fp.seek(0)
            _resp = self.post(f'/apis/log/{self.Cache.LOG_ID}/upload', data=zz.fp.read())

        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            return

    def at_exit(self):
        """将被注册到退出函数中的事件。"""
        logger.info('Client on Exit.')
        data = dict(
            end_time=local_time(),
            num_new_page=self.Cache.COUNT_NEW_PAGE,
            num_update_text=self.Cache.COUNT_UPDATE_TEXT,
            not_found_text_pages=self.Cache.NOT_FOUND_TEXT_IDS,
            status=self.Cache.EXIT_STATUS,
        )
        self.upload_logs()
        self.upload_status(data)

    def upload_status(self, data: dict):
        """上传状态"""
        logger.info('Update Logs.')
        data['id'] = self.Cache.LOG_ID
        if self.Cache.EXIT_STATUS == 'Success':
            data['status'] = 'Success'
        elif isinstance(self.Cache.EXIT_STATUS, Exception):  # TODO 如果出现了异常，应该返回堆栈信息
            data['status'] = 'Error'
            data['comments'] = str(self.Cache.EXIT_STATUS)[:510]
        else:
            data['status'] = 'Error'
            data['comments'] = str(self.Cache.EXIT_STATUS)[:510]
        logger.info('Upload Status <<< %s', json.dumps(data, indent=2, ensure_ascii=False))
        _resp = self.put(f'/apis/log/{self.Cache.LOG_ID}', json=data)
