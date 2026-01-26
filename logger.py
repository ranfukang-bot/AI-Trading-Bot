# -*- coding: utf-8 -*-
"""
logger.py - 日志模块
存放日志初始化逻辑
依赖: config.py
"""

import os
import logging
from config import LOG_DIR


def setup_loggers():
    """初始化日志系统，返回 trade_logger 和 error_logger"""

    # 交易日志
    trade_logger = logging.getLogger('trade')
    trade_logger.setLevel(logging.INFO)
    trade_logger.handlers.clear()
    trade_log_path = os.path.join(LOG_DIR, 'trade_history.log')
    trade_handler = logging.FileHandler(trade_log_path, encoding='utf-8')
    trade_handler.setFormatter(logging.Formatter('%(message)s'))
    trade_logger.addHandler(trade_handler)

    # 错误日志
    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)
    error_logger.handlers.clear()
    error_log_path = os.path.join(LOG_DIR, 'system_error.log')
    error_handler = logging.FileHandler(error_log_path, encoding='utf-8')
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    error_logger.addHandler(error_handler)

    return trade_logger, error_logger


# 初始化全局日志实例
trade_logger, error_logger = setup_loggers()
