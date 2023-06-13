import time


def local_time():
    """返回当前时间的标准字符串格式"""
    return time.strftime('%Y-%m-%d %H:%M:%S %z')