# coding: utf8
"""
1. 锁的必要性，应当确立
    1. 锁实现的位置 --
2. 当前Spider只响应一个配置文件中的内容。
3. 独立的客户端类，无需重构。
4. 客户端类日志打印需要优化，在Info中，答应数量而不是响应的全文

"""

import asyncio


class Spider:

    def __init__(self):
        pass
