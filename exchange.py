# -*- coding: utf-8 -*-
"""
exchange.py - 交易所交互模块
存放 RealExchange 类
依赖: config.py, logger.py
"""

import sys
import os
import json
import time
import threading
from datetime import datetime

import ccxt

from config import (
    PROXIES, DATA_FILE, DEFAULT_SYMBOL,
    TRADING_MODE_SPOT, TRADING_MODE_SWAP,
    SLIPPAGE_TOLERANCE, ConfigManager
)
from logger import error_logger


class RealExchange:
    """实盘交易所交互类 - V17.2 热切换增强版"""

    def __init__(self, config):
        self.lock = threading.Lock()
        self.config = config

        # 热切换状态标志
        self.is_reconnecting = False
        self.reconnect_lock = threading.Lock()

        api_key = config.get("exchange_api_key")
        secret = config.get("exchange_secret")
        passphrase = config.get("exchange_passphrase")

        # 交易参数
        self.symbol = config.get("symbol", DEFAULT_SYMBOL)
        self.trading_mode = config.get("trading_mode", TRADING_MODE_SPOT)
        self.leverage = config.get("leverage", 1)

        if not api_key or not secret:
            error_logger.error("未找到 API Key")
            print("错误: API Key 配置无效")
            sys.exit(1)

        # 创建交易所实例
        self.exchange = self._create_exchange_instance(api_key, secret, passphrase)

        try:
            mode_text = "合约(Swap)" if self.trading_mode == TRADING_MODE_SWAP else "现货(Spot)"
            print(f"正在连接交易所 ({self.symbol} - {mode_text})...")
            self.exchange.load_markets()
            print("交易所连接成功")

            if self.trading_mode == TRADING_MODE_SWAP and self.leverage > 1:
                self._set_leverage()

        except Exception as e:
            error_logger.error(f"交易所连接失败: {e}")
            print(f"交易所连接失败: {e}")
            sys.exit(1)

        self.entry_price = 0.0
        self.peak_balance = 0.0
        self.initial_capital = 0.0
        self.position_open_time = None
        self.last_trade_time = 0

        self._load_and_calibrate_data()

    def _create_exchange_instance(self, api_key, secret, passphrase):
        """创建 ccxt 实例（用于初始化和重连）"""
        exchange_config = {
            'apiKey': api_key,
            'secret': secret,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {'defaultType': self.trading_mode}
        }

        if PROXIES:
            exchange_config['proxies'] = PROXIES

        return ccxt.okx(exchange_config)

    def get_trading_symbol(self):
        """获取正确格式的交易对符号

        OKX 交易所格式:
        - 现货: BTC/USDT
        - 合约: BTC/USDT:USDT (USDT本位永续合约)
        """
        if self.trading_mode == TRADING_MODE_SWAP:
            if ':' not in self.symbol:
                return f"{self.symbol}:USDT"
            return self.symbol
        else:
            if ':' in self.symbol:
                return self.symbol.split(':')[0]
            return self.symbol

    def reconnect(self, new_symbol, new_mode, new_leverage, log_callback=None):
        """
        热切换核心方法 - 安全地切换交易连接
        返回: (success: bool, message: str)
        """
        def _log(msg):
            if log_callback:
                log_callback(msg)
            print(msg)

        with self.reconnect_lock:
            if self.is_reconnecting:
                return False, "重连进行中，请稍候"
            self.is_reconnecting = True

        _log(f"开始切换: {new_symbol} / {'合约' if new_mode == TRADING_MODE_SWAP else '现货'} / {new_leverage}x")

        try:
            with self.lock:
                old_exchange = self.exchange
                old_symbol = self.symbol
                old_mode = self.trading_mode
                old_leverage = self.leverage

                try:
                    self.symbol = new_symbol
                    self.trading_mode = new_mode
                    self.leverage = new_leverage

                    api_key = self.config.get("exchange_api_key")
                    secret = self.config.get("exchange_secret")
                    passphrase = self.config.get("exchange_passphrase")

                    self.exchange = self._create_exchange_instance(api_key, secret, passphrase)

                    _log("正在加载市场数据...")
                    self.exchange.load_markets()

                    if self.trading_mode == TRADING_MODE_SWAP and self.leverage > 1:
                        self._set_leverage()
                        _log(f"杠杆已设置: {self.leverage}x")

                    _log("验证连接...")
                    self.exchange.fetch_balance()

                    ConfigManager.update_trading_params(new_symbol, new_mode, new_leverage)
                    _log(f"切换成功: {new_symbol}")

                    return True, f"切换成功: {new_symbol}"

                except Exception as e:
                    _log(f"切换失败，正在恢复...")
                    self.exchange = old_exchange
                    self.symbol = old_symbol
                    self.trading_mode = old_mode
                    self.leverage = old_leverage
                    error_logger.error(f"热切换失败: {e}")
                    return False, f"切换失败: {str(e)}"

        finally:
            with self.reconnect_lock:
                self.is_reconnecting = False
            _log("切换流程完成")

    def is_safe_to_fetch(self):
        """检查是否可以安全拉取数据"""
        with self.reconnect_lock:
            return not self.is_reconnecting

    def _set_leverage(self):
        """设置合约杠杆倍数"""
        try:
            trading_symbol = self.get_trading_symbol()
            self.exchange.set_leverage(self.leverage, trading_symbol, params={'mgnMode': 'cross'})
            print(f"杠杆设置成功: {self.leverage}x ({trading_symbol})")
        except Exception as e:
            print(f"杠杆设置警告: {e}")
            error_logger.error(f"杠杆设置失败: {e}")

    def _load_and_calibrate_data(self):
        """加载本地数据并校准"""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    self.entry_price = float(data.get("entry_price", 0.0))
                    self.peak_balance = float(data.get("peak_balance", 0.0))
                    self.initial_capital = float(data.get("initial_capital", 0.0))
                    t_str = data.get("position_open_time")
                    self.position_open_time = datetime.fromisoformat(t_str) if t_str else None
            except Exception:
                pass

        try:
            balance = self.exchange.fetch_balance()
            symbol_base = self.symbol.split('/')[0]

            if self.trading_mode == TRADING_MODE_SWAP:
                try:
                    trading_symbol = self.get_trading_symbol()
                    positions = self.exchange.fetch_positions([trading_symbol])
                    qty = 0.0
                    for pos in positions:
                        if pos['symbol'] == trading_symbol:
                            contracts = float(pos.get('contracts', 0) or 0)
                            contract_size = float(pos.get('contractSize', 1) or 1)
                            qty = contracts * contract_size
                            break
                except Exception:
                    qty = 0.0
            else:
                qty = float(balance.get(symbol_base, {}).get('total', 0.0))

            if qty > 0.0001:
                if self.entry_price <= 0:
                    print("检测到持仓但丢失入场价，正在从交易所历史恢复...")
                    trading_symbol = self.get_trading_symbol()
                    trades = self.exchange.fetch_my_trades(trading_symbol, limit=1)
                    if trades:
                        self.entry_price = trades[0]['price']
                        self.position_open_time = datetime.fromtimestamp(trades[0]['timestamp']/1000)
                        print(f"已恢复入场价: ${self.entry_price}")
            else:
                self.entry_price = 0.0
                self.position_open_time = None

        except Exception as e:
            error_logger.error(f"启动校准失败: {e}")

    def _save_local_data(self):
        """保存本地数据"""
        try:
            data = {
                "entry_price": self.entry_price,
                "peak_balance": self.peak_balance,
                "initial_capital": self.initial_capital,
                "position_open_time": self.position_open_time.isoformat() if self.position_open_time else None
            }
            with open(DATA_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            error_logger.error(f"本地数据保存失败: {e}")

    def set_initial_capital(self, capital):
        """设置初始本金"""
        with self.lock:
            if self.initial_capital <= 0:
                self.initial_capital = capital
                if self.peak_balance <= 0:
                    self.peak_balance = capital
                self._save_local_data()
                print(f"初始本金锁定: ${capital:,.2f}")

    def get_account(self):
        """获取账户信息"""
        with self.lock:
            try:
                balance_info = self.exchange.fetch_balance()
                base_coin = self.symbol.split('/')[0]
                quote_coin = self.symbol.split('/')[1]

                usdt_balance = float(balance_info.get(quote_coin, {}).get('free', 0.0))

                if self.trading_mode == TRADING_MODE_SWAP:
                    try:
                        trading_symbol = self.get_trading_symbol()
                        positions = self.exchange.fetch_positions([trading_symbol])
                        position_qty = 0.0
                        for pos in positions:
                            if pos['symbol'] == trading_symbol:
                                contracts = float(pos.get('contracts', 0) or 0)
                                contract_size = float(pos.get('contractSize', 1) or 1)
                                position_qty = contracts * contract_size
                                break
                    except Exception as e:
                        print(f"获取合约持仓失败: {e}")
                        position_qty = 0.0
                else:
                    position_qty = float(balance_info.get(base_coin, {}).get('total', 0.0))

                return {
                    "balance": usdt_balance,
                    "position": position_qty,
                    "entry_price": self.entry_price,
                    "peak_balance": self.peak_balance,
                    "initial_capital": self.initial_capital,
                    "position_open_time": self.position_open_time,
                    "last_trade_time": self.last_trade_time
                }
            except ccxt.NetworkError:
                return {"balance": 0.0, "position": 0.0, "entry_price": 0.0,
                        "peak_balance": 0.0, "initial_capital": 0.0,
                        "position_open_time": None, "last_trade_time": 0}
            except Exception as e:
                error_logger.error(f"获取账户失败: {e}")
                return {"balance": 0.0, "position": 0.0, "entry_price": 0.0,
                        "peak_balance": 0.0, "initial_capital": 0.0,
                        "position_open_time": None, "last_trade_time": 0}

    def place_limit_order_with_stop(self, side, quantity, current_market_price, stop_loss_price=None):
        """发送限价单，并自动附带止损

        [V17.2 修复] OKX 单向持仓模式 (Net Mode) 专用
        1. 止损方向问题: 单向模式下 posSide 必须为 'net'，且需指定 tpSlSide 告知止损方向
        2. 数量单位问题: 合约模式下需要将币数转换为张数 (quantity / contractSize)
        """
        with self.lock:
            try:
                trading_symbol = self.get_trading_symbol()

                if side == 'buy':
                    price_raw = current_market_price * (1 + SLIPPAGE_TOLERANCE)
                else:
                    price_raw = current_market_price * (1 - SLIPPAGE_TOLERANCE)

                # [V17.2 修复] 合约模式下需要将币数转换为张数
                if self.trading_mode == TRADING_MODE_SWAP:
                    market = self.exchange.market(trading_symbol)
                    contract_size = float(market.get('contractSize', 1) or 1)

                    # OKX USDT本位合约: contractSize 通常是 USD 面值 (如 100 表示每张 100 USD)
                    # 计算公式: 张数 = (币数 × 当前价格) / 面值(USD)
                    contracts = int((quantity * current_market_price) / contract_size)
                    if contracts <= 0:
                        print(f"计算张数为0: quantity={quantity:.8f} 币, price={current_market_price}, contractSize={contract_size} USD")
                        print(f"   计算过程: ({quantity:.8f} × {current_market_price}) / {contract_size} = {(quantity * current_market_price) / contract_size:.2f}")
                        return None
                    amount = contracts
                    print(f"单位换算: {quantity:.6f} 币 × ${current_market_price:,.2f} / {contract_size} USD = {contracts} 张")
                else:
                    amount = self.exchange.amount_to_precision(trading_symbol, quantity)

                price = self.exchange.price_to_precision(trading_symbol, price_raw)

                params = {}

                if self.trading_mode == TRADING_MODE_SWAP:
                    # 单向持仓模式 (Net Mode) 专用逻辑
                    pos_side = 'net'

                    if side == 'buy' and stop_loss_price:
                        sl_price_str = self.exchange.price_to_precision(trading_symbol, stop_loss_price)
                        params = {
                            'tdMode': 'cross',
                            'posSide': pos_side,
                            'slTriggerPx': sl_price_str,
                            'slOrdPx': '-1',
                            'tpSlSide': 'sell'
                        }
                        print(f"准备下单(合约-单向模式): {side} {amount}张 @ {price}")
                        print(f"   posSide=net, tpSlSide=sell, 止损触发价={sl_price_str}")
                    elif side == 'sell' and stop_loss_price:
                        sl_price_str = self.exchange.price_to_precision(trading_symbol, stop_loss_price)
                        params = {
                            'tdMode': 'cross',
                            'posSide': pos_side,
                            'slTriggerPx': sl_price_str,
                            'slOrdPx': '-1',
                            'tpSlSide': 'buy'
                        }
                        print(f"准备下单(合约-单向模式): {side} {amount}张 @ {price}")
                        print(f"   posSide=net, tpSlSide=buy, 止损触发价={sl_price_str}")
                    else:
                        params = {
                            'tdMode': 'cross',
                            'posSide': pos_side
                        }
                        print(f"准备下单(合约-单向模式): {side} {amount}张 @ {price}, posSide=net")
                else:
                    params = {'tdMode': 'cash'}
                    print(f"准备下单(现货): {side} {amount} @ {price}")

                order = self.exchange.create_order(
                    symbol=trading_symbol,
                    type='limit',
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )

                order_id = order['id']
                print(f"下单成功: order_id={order_id}")

                if side == 'buy':
                    self.entry_price = float(price)
                    self.position_open_time = datetime.now()
                elif side == 'sell':
                    if float(amount) > 0:
                        self.entry_price = 0.0
                        self.position_open_time = None
                        self.last_trade_time = time.time()

                self._save_local_data()
                return order_id

            except Exception as e:
                error_logger.error(f"下单失败: {e}")
                print(f"下单异常: {e}")
                import traceback
                traceback.print_exc()
                return None

    def place_market_order(self, side, quantity):
        """市价单（用于紧急平仓）

        [V17.2 修复] OKX 单向持仓模式 (Net Mode) 专用
        1. posSide 必须为 'net'
        2. 合约模式下需要将币数转换为张数: 张数 = (币数 × 价格) / 面值
        """
        with self.lock:
            try:
                trading_symbol = self.get_trading_symbol()

                if self.trading_mode == TRADING_MODE_SWAP:
                    ticker = self.exchange.fetch_ticker(trading_symbol)
                    current_price = float(ticker['last'])

                    market = self.exchange.market(trading_symbol)
                    contract_size = float(market.get('contractSize', 1) or 1)

                    contracts = int((quantity * current_price) / contract_size)
                    if contracts <= 0:
                        print(f"计算张数为0: quantity={quantity:.8f} 币, price={current_price}, contractSize={contract_size} USD")
                        return None
                    amount = contracts
                    print(f"单位换算: {quantity:.6f} 币 × ${current_price:,.2f} / {contract_size} USD = {contracts} 张")
                else:
                    amount = self.exchange.amount_to_precision(trading_symbol, quantity)

                print(f"紧急市价单: {side} {amount}")

                params = {}
                if self.trading_mode == TRADING_MODE_SWAP:
                    params = {
                        'tdMode': 'cross',
                        'posSide': 'net'
                    }
                    print(f"紧急市价单(合约-单向模式): {side} {amount}张, posSide=net")

                order = self.exchange.create_order(
                    symbol=trading_symbol,
                    type='market',
                    side=side,
                    amount=amount,
                    params=params
                )

                order_id = order['id']
                print(f"市价单成功: order_id={order_id}")

                if side == 'sell':
                    self.entry_price = 0.0
                    self.position_open_time = None
                    self.last_trade_time = time.time()

                self._save_local_data()
                return order_id

            except Exception as e:
                error_logger.error(f"市价单失败: {e}")
                print(f"市价单异常: {e}")
                import traceback
                traceback.print_exc()
                return None

    def update_peak_balance(self, current_total_asset, current_position):
        """更新峰值余额 - 只在空仓时更新"""
        with self.lock:
            if current_position <= 0.0001:
                if current_total_asset > self.peak_balance:
                    old_peak = self.peak_balance
                    self.peak_balance = current_total_asset
                    self._save_local_data()
                    if old_peak > 0:
                        increase_pct = (current_total_asset - old_peak) / old_peak * 100
                        if increase_pct >= 0.1:
                            print(f"峰值更新(空仓锁定): ${current_total_asset:,.2f} (+{increase_pct:.2f}%)")
                    else:
                        print(f"峰值初始化: ${current_total_asset:,.2f}")

    def clear_local_state(self):
        """清空本地状态文件"""
        with self.lock:
            self.entry_price = 0.0
            self.position_open_time = None
            if os.path.exists(DATA_FILE):
                try:
                    os.remove(DATA_FILE)
                except Exception:
                    pass
