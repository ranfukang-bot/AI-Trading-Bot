# -*- coding: utf-8 -*-
"""
signals.py - Qt信号模块
存放 PySide6 的 Signal 定义
不依赖其他项目模块
"""

from PySide6.QtCore import Signal, QObject


class TradingSignals(QObject):
    """交易系统信号类"""

    # 价格更新信号 (价格, 颜色)
    update_price = Signal(float, str)

    # AI建议更新信号 (action, reason, confidence, timestamp, indicators)
    update_ai = Signal(str, str, int, str, dict)

    # 账户更新信号 (balance, position, total_asset, pnl, initial_capital)
    update_account = Signal(float, float, float, float, float)

    # 状态更新信号 (is_connected)
    update_status = Signal(bool)

    # 日志更新信号 (message)
    update_log = Signal(str)

    # 风控更新信号 (risk_msg, drawdown)
    update_risk = Signal(str, float)

    # 热切换结果信号 (success, message)
    reconnect_result = Signal(bool, str)
