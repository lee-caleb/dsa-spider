import os
import logging
import time
from hashlib import md5

import requests
from requests import Response

logger = logging.getLogger('dsa-spider.dsa-client')
__all__ = ['DSAClient']


class DSAClient(requests.Session):
    class Cache:
        ACTIVE_CONFIG = None
        LOG_ID = None

    def __init__(self, base_url='', auth=None):
        super().__init__()

        self.base_url = base_url
        self.headers.update({'User-Agent': 'dsa-spider/0.1'})
        if auth:
            self.headers.update({'Auth': auth})

    def request(self, method, url, *args, **kwargs):
        url = self.base_url + url
        logger.debug('更新URL, %s', url)
        super().request(method, url, *args, **kwargs)

    def active_config(self, retry=0, force_config=None):
        """活跃的配置"""
        if self.Cache.ACTIVE_CONFIG is not None:
            logger.info('DSA Active Config From Cache.')
            return self.Cache.ACTIVE_CONFIG

        _resp = self.get(f'/apis/config/{force_config}/' if force_config else '/apis/config/unlocked')

        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            self.Cache.ACTIVE_CONFIG = _resp.json()['data']
            logger.info('Saved ACTIVE_CONFIG to Cache.')
            return self.Cache.ACTIVE_CONFIG
        else:
            logger.warning('Get Active config Error HTTP_CODE(%d), %s', _resp.status_code, _resp.text)
            time.sleep(3)
            if retry >= 3:
                logger.info('Retry to get active config, times: %d', retry + 1)
                return self.active_config(retry=retry + 1)
            else:
                logger.error('Cannot access a config from server.')
                raise

    def heartbeat(self):
        param = {'name': self.Cache.ACTIVE_CONFIG['id']}
        logger.info('send a heartbeat to server.')
        return self.get('/apis/config/heartbeat', params=param).json()

    def page_create(self, body: dict):
        body['page_id'] = md5(f'{body["source"]}{body["title"]}{body["link"]}'.encode()).hexdigest()
        logger.info('Create a Page to Server, %s, %s', body['page_id'], body['title'])
        return self.post(f'/apis/page/{body["page_id"]}/', json=body)

    def page_update(self, body: dict):
        if not body.get('page_id'):
            logger.warning('Cannot Find a Page in body.\n'
                           'We will Create a page_id for this body, '
                           'but it may be do not at server.'
                           )
            body['page_id'] = md5(f'{body["source"]}{body["title"]}{body["link"]}'.encode()).hexdigest()
        return self.put(f'/apis/page/{body["page_id"]}/', json=body).json()

    def page_del(self, page_id):
        logger.warning('')
        return self.delete(f'/apis/page/{page_id}/')

    def page_no_text(self, retry=0):
        """没有正文的page
        page_id, link
        """
        config_id = self.Cache.ACTIVE_CONFIG['id']
        _resp = self.get('/apis/pages/no_text', params=dict(config_id=config_id))

        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            return _resp.json()['data']

        else:
            logger.warning('Get no text pages Error HTTP_CODE(%d), %s', _resp.status_code, _resp.text)
            time.sleep(3)
            if retry >= 3:
                logger.info('Retry to get no text pages, times: %d', retry + 1)
                return self.page_no_text(retry=retry + 1)
            else:
                logger.error('Cannot get pages from server.')
                raise

    def log_start(self):
        """记录日志开始"""
        body = {
            'source': self.Cache.ACTIVE_CONFIG['name'],
            'status': 'Running',
            'start_time': int(time.time())
        }
        self.post('/apis/log/', json=body).json()

    def upload_logs(self, logs_file=None):
        """上传日志"""

    def at_exit(self):
        """将被注册到退出函数中的事件。"""
        logger.info('Client on Exit.')
        self.upload_status('success')

    def upload_status(self, status):
        """上传状态"""
