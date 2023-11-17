# 初始化加载
from pathlib import Path
import sys

WORK_ROOT = Path(__file__).parent.parent

sys.path.append(str(WORK_ROOT))

from settings import dsa_client

__all__ = ['dsa_client']
