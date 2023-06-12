import os
import sys
from pathlib import Path

import dotenv

from dsa_api import DSAClient

dotenv.load_dotenv(Path(__file__).parent.joinpath('.env'))

__all__ = ['dsa_client', 'DSA_CONFIG', 'DSA_HTTP']

DSA_HTTP = os.getenv('IN_DSA_HTTP') or os.getenv('ENV_DSA_HTTP') or os.getenv('DSA_HTTP') or 'http://localhost:8000'
DSA_AUTH = os.getenv('IN_DSA_AUTH') or os.getenv('ENV_DSA_AUTH') or os.getenv('DSA_AUTH') or ''
DSA_CONFIG = os.getenv('DSA_CONFIG')
DSA_DEBUG = os.getenv('DSA_DEBUG', '') == 'true'

if len(sys.argv) >= 2:
    DSA_CONFIG = sys.argv[1]

dsa_client = DSAClient(DSA_HTTP, DSA_AUTH)
dsa_client.active_config(force_config=DSA_CONFIG)
