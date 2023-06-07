import os
import sys

from dsa_api import DSAClient

__all__ = ['dsa_client', 'DSA_CONFIG']

DSA_HTTP = os.getenv('DSA_HTTP', 'http://localhost:8000')
DSA_AUTH = os.getenv('DSA_AUTH')
DSA_CONFIG = os.getenv('DSA_CONFIG')

if len(sys.argv) >= 2:
    DSA_CONFIG = sys.argv[1]

dsa_client = DSAClient(DSA_HTTP, DSA_AUTH)
