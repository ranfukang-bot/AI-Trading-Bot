# -*- coding: utf-8 -*-
"""
risk.py - 风险控制模块
存放 RiskController 类
不依赖其他项目模块
"""

import threading


class RiskController:
    """风险控制器"""

    def __init__(self, max_drawdown=0.15, max_single_loss=0.05):
        self.max_drawdown = max_drawdown
        self.max_single_loss = max_single_loss
        self.lock = threading.Lock()

    def check_trade_permission(self, current_total_asset, initial_capital, action="buy"):
        """检查交易权限"""
        with self.lock:
            if action == "sell":
                return True, "卖出操作允许"

            if initial_capital <= 0:
                return True, "初始状态"

            drawdown = (initial_capital - current_total_asset) / initial_capital

            if drawdown > self.max_drawdown:
                return False, f"触发最大回撤限制 ({drawdown*100:.1f}% > {self.max_drawdown*100:.0f}%)"

            return True, "风控通过"

    def check_risk(self, current_total_asset, initial_capital):
        """检查风险状态"""
        with self.lock:
            if initial_capital <= 0:
                return True, "风控通过(初始状态)", 0.0

            drawdown = (initial_capital - current_total_asset) / initial_capital
            drawdown = max(0, drawdown)

            if drawdown > self.max_drawdown:
                return False, f"触发最大回撤限制 ({drawdown*100:.1f}%)", drawdown

            return True, "风控通过", drawdown

    def calculate_stop_loss(self, entry_price):
        """计算止损价格"""
        return entry_price * (1 - self.max_single_loss)

    def calculate_take_profit(self, entry_price, risk_reward_ratio=2.0):
        """计算止盈价格"""
        return entry_price * (1 + self.max_single_loss * risk_reward_ratio)
