# coding: utf-8
import json
import logging
import re
import time
import zipfile
from hashlib import md5
from pathlib import Path

import requests
from requests import Response

from common import local_time

logger = logging.getLogger('dsa.spider.dsa-client')
__all__ = ['DSAClient']


class DSAClient(requests.Session):
    class Cache:
        ACTIVE_CONFIG = None
        LOG_ID = None
        EXIT_STATUS = 'Success'
        COUNT_NEW_PAGE = 0
        COUNT_UPDATE_TEXT = 0
        NOT_FOUND_TEXT_IDS = []

    def __init__(self, base_url='', auth=None):
        super().__init__()

        self.base_url = base_url
        self.headers.update({'User-Agent': 'dsa-spider/0.1'})
        if auth:
            self.headers.update({'Auth': auth})

    def request(self, method, url, *args, **kwargs):
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

    def active_config(self, retry=0, force_config=None):
        """活跃的配置"""
        if self.Cache.ACTIVE_CONFIG is not None:
            logger.info('DSA Active Config From Cache. name: %s', self.Cache.ACTIVE_CONFIG.get('name'))
            return self.Cache.ACTIVE_CONFIG

        _resp: Response = self.get(f'/apis/config/{force_config}/' if force_config else '/apis/config/unlocked')

        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            self.Cache.ACTIVE_CONFIG = _resp.json()['data']
            logger.info('Saved ACTIVE_CONFIG to Cache. name: %s', self.Cache.ACTIVE_CONFIG['name'])
            return self.Cache.ACTIVE_CONFIG
        elif _resp.status_code == 406 and _resp.json()['status'] == 406:
            logger.warning('All Config in server is locked. This process will be stop.')
            exit()
        else:
            text = _resp.text
            logger.warning(
                'Get Active config Error HTTP_CODE(%d), %s',
                _resp.status_code,
                re.findall(r'<title>(.*?)</title>', text) or text
            )
            time.sleep(3)
            if retry <= 3:
                logger.info('Retry to get active config, times: %d', retry + 1)
                return self.active_config(retry=retry + 1)
            else:
                logger.error('Cannot access a config from server.')
                raise

    def heartbeat(self):
        param = {'config_id': self.Cache.ACTIVE_CONFIG['id']}
        logger.info('send a heartbeat to server.')
        _resp = self.get('/apis/config/heartbeat', params=param)
        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            return True
        return

    def page_create(self, body: dict):
        body['page_id'] = md5(f'{body["source"]}{body["title"]}{body["link"]}'.encode()).hexdigest()
        logger.info('Create a Page to Server, %s, %s', body['page_id'], body['title'])
        _resp = self.post(f'/apis/page/{body["page_id"]}/', json=body)
        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            logger.info('Page [%s] is created at Server. ID: %s', body["title"], body['page_id'])
            self.Cache.COUNT_NEW_PAGE += 1
            return body['page_id']
        logger.warning(f'create page [%s] is Error, %s', body["title"], _resp.json()['message'])
        return None

    def page_update(self, body: dict):
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
        logger.warning('')
        return self.delete(f'/apis/page/{page_id}/')

    def page_no_text(self, retry=0):
        """没有正文的page
        page_id, link
        """
        config_id = self.Cache.ACTIVE_CONFIG['id']
        _resp = self.get('/apis/pages/no_text/', params=dict(config_id=config_id))

        if _resp.status_code == 200 and _resp.json()['status'] == 200:
            return _resp.json()['data']

        else:
            text = _resp.text
            logger.warning('Get no text pages Error HTTP_CODE(%d), %s', _resp.status_code,
                           re.findall(r'<title>(.*?)</title>', text) or text
                           )
            time.sleep(3)
            if retry <= 3:
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
            not_found_text_page_ids=self.Cache.NOT_FOUND_TEXT_IDS,
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
        elif isinstance(self.Cache.EXIT_STATUS, Exception):
            data['status'] = 'Error'
            data['comments'] = str(self.Cache.EXIT_STATUS)
        else:
            data['status'] = 'Error'
            data['comments'] = str(self.Cache.EXIT_STATUS)
        logger.info('Upload Status <<< %s', json.dumps(data, indent=2, ensure_ascii=False))
        _resp = self.put(f'/apis/log/{self.Cache.LOG_ID}', json=data)
