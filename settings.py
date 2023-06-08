import os
import sys
import logging

from dsa_api import DSAClient

logger = logging.getLogger('dsa.spider.settings')

__all__ = ['dsa_client', 'DSA_CONFIG']

DSA_HTTP = os.getenv('IN_DSA_HTTP') or os.getenv('ENV_DSA_HTTP') or 'http://localhost:8000'
DSA_AUTH = os.getenv('IN_DSA_AUTH') or os.getenv('ENV_DSA_AUTH') or ''
DSA_CONFIG = os.getenv('DSA_CONFIG')
DSA_DEBUG = os.getenv('DSA_DEBUG', '') == 'true'

logger.info(f'Load Env Settings: \n{DSA_HTTP=} \n{DSA_AUTH=} \n{DSA_CONFIG=} \n{DSA_DEBUG=}')

if len(sys.argv) >= 2:
    DSA_CONFIG = sys.argv[1]

dsa_client = DSAClient(DSA_HTTP, DSA_AUTH)
