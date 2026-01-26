# -*- coding: utf-8 -*-
"""
ui.py - 用户界面模块
存放配置向导、弹窗类和主窗口类
依赖: config.py, logger.py, signals.py, risk.py, exchange.py
"""

import time
import json
import threading
from datetime import datetime

import ccxt
from openai import OpenAI

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QWidget, QFrame, QHBoxLayout,
    QTextEdit, QDialog, QLineEdit, QPushButton, QFormLayout, QMessageBox,
    QSpinBox, QDoubleSpinBox, QGridLayout, QSizePolicy, QComboBox,
    QRadioButton, QButtonGroup, QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor

from config import (
    DEFAULT_SYMBOL, SUPPORTED_SYMBOLS, SECRETS_FILE,
    TRADING_MODE_SPOT, TRADING_MODE_SWAP, TIMEFRAME, COOLING_OFF_MINUTES,
    ConfigManager
)
from logger import trade_logger, error_logger
from signals import TradingSignals
from risk import RiskController
from exchange import RealExchange


# ================= 配置向导对话框 =================
class ConfigWizard(QDialog):
    """首次配置向导 - V16.0 精简版（只配置 API）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("首次配置向导 - V16.4")
        self.setFixedSize(520, 480)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1f2e, stop:1 #0d1117);
                color: #e6edf3;
            }
            QLabel {
                color: #e6edf3;
                font-size: 13px;
            }
            QLineEdit, QSpinBox {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px 12px;
                color: #e6edf3;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #58a6ff;
            }
            QPushButton {
                background: #238636;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2ea043;
            }
            QPushButton:pressed {
                background: #1a7f37;
            }
            QGroupBox {
                color: #58a6ff;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #30363d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(30, 25, 30, 25)

        # 标题
        title = QLabel("AI Trading System V16.3")
        title.setFont(QFont("微软雅黑", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #58a6ff; margin-bottom: 5px;")
        layout.addWidget(title)

        subtitle = QLabel("请配置您的 API 密钥（交易参数在主界面设置）")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8b949e; font-size: 12px; margin-bottom: 15px;")
        layout.addWidget(subtitle)

        # API 配置区
        api_group = QGroupBox("API 配置")
        api_layout = QFormLayout(api_group)
        api_layout.setSpacing(10)

        self.deepseek_input = QLineEdit()
        self.deepseek_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxx")
        self.deepseek_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("DeepSeek API Key:", self.deepseek_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("您的 OKX API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("交易所 API Key:", self.api_key_input)

        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("您的 OKX Secret Key")
        self.secret_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("交易所 Secret:", self.secret_input)

        self.passphrase_input = QLineEdit()
        self.passphrase_input.setPlaceholderText("您的 OKX Passphrase")
        self.passphrase_input.setEchoMode(QLineEdit.Password)
        api_layout.addRow("交易所 Passphrase:", self.passphrase_input)

        layout.addWidget(api_group)

        # 风控配置区
        risk_group = QGroupBox("风控配置")
        risk_layout = QFormLayout(risk_group)
        risk_layout.setSpacing(10)

        drawdown_widget = QWidget()
        drawdown_layout = QHBoxLayout(drawdown_widget)
        drawdown_layout.setContentsMargins(0, 0, 0, 0)

        self.drawdown_input = QSpinBox()
        self.drawdown_input.setRange(5, 50)
        self.drawdown_input.setValue(15)
        self.drawdown_input.setSuffix(" %")
        self.drawdown_input.setFixedWidth(100)
        drawdown_layout.addWidget(self.drawdown_input)

        drawdown_hint = QLabel("(基于初始本金计算)")
        drawdown_hint.setStyleSheet("color: #8b949e; font-size: 11px; margin-left: 10px;")
        drawdown_layout.addWidget(drawdown_hint)
        drawdown_layout.addStretch()
        risk_layout.addRow("最大回撤阈值:", drawdown_widget)

        layout.addWidget(risk_group)

        # 提示信息
        info_label = QLabel("提示: 交易对、模式、杠杆将在主界面实时设置")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: #f0883e; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info_label)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("保存并启动")
        self.save_btn.setFixedWidth(150)
        self.save_btn.clicked.connect(self.save_and_start)
        btn_layout.addWidget(self.save_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 路径提示
        path_hint = QLabel(f"配置文件: {SECRETS_FILE}")
        path_hint.setAlignment(Qt.AlignCenter)
        path_hint.setStyleSheet("color: #6e7681; font-size: 10px; margin-top: 10px;")
        layout.addWidget(path_hint)

    def save_and_start(self):
        if not self.deepseek_input.text().strip():
            QMessageBox.warning(self, "提示", "请输入 DeepSeek API Key")
            return
        if not self.api_key_input.text().strip():
            QMessageBox.warning(self, "提示", "请输入交易所 API Key")
            return
        if not self.secret_input.text().strip():
            QMessageBox.warning(self, "提示", "请输入交易所 Secret")
            return

        config = {
            "deepseek_api_key": self.deepseek_input.text().strip(),
            "exchange_api_key": self.api_key_input.text().strip(),
            "exchange_secret": self.secret_input.text().strip(),
            "exchange_passphrase": self.passphrase_input.text().strip(),
            "max_drawdown": self.drawdown_input.value() / 100.0,
            "symbol": DEFAULT_SYMBOL,
            "trading_mode": TRADING_MODE_SPOT,
            "leverage": 1
        }

        if ConfigManager.save_config(config):
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "配置保存失败，请检查文件权限")


# ================= 紧急平仓确认对话框 =================
class PanicConfirmDialog(QDialog):
    """紧急平仓确认对话框（3秒延迟）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("紧急平仓确认")
        self.setFixedSize(400, 200)
        self.setStyleSheet("""
            QDialog {
                background: #1a1f2e;
                color: #e6edf3;
            }
            QLabel {
                color: #e6edf3;
            }
        """)

        self.countdown = 3
        self.init_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        warning = QLabel("紧急平仓警告")
        warning.setFont(QFont("微软雅黑", 16, QFont.Bold))
        warning.setAlignment(Qt.AlignCenter)
        warning.setStyleSheet("color: #f85149;")
        layout.addWidget(warning)

        desc = QLabel("此操作将:\n- 停止 AI 交易线程\n- 以市价卖出所有持仓\n- 清空本地状态文件")
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(desc)

        btn_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 10px 25px;
                color: #e6edf3;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #30363d;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton(f"确认平仓 ({self.countdown}s)")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background: #6e4040;
                border: none;
                border-radius: 6px;
                padding: 10px 25px;
                color: #8b949e;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:enabled {
                background: #da3633;
                color: white;
            }
            QPushButton:enabled:hover {
                background: #f85149;
            }
        """)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

    def update_countdown(self):
        self.countdown -= 1
        if self.countdown <= 0:
            self.timer.stop()
            self.confirm_btn.setText("确认平仓")
            self.confirm_btn.setEnabled(True)
        else:
            self.confirm_btn.setText(f"确认平仓 ({self.countdown}s)")


# ================= 主窗口 =================
class CryptoAIExpert(QMainWindow):
    """主窗口 - AI 交易系统界面"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.account_lock = threading.Lock()
        self.trade_lock = threading.Lock()

        self.exchange = RealExchange(config)
        max_dd = config.get("max_drawdown", 0.15)
        self.risk_controller = RiskController(max_drawdown=max_dd)

        # 从配置获取交易参数
        self.symbol = config.get("symbol", DEFAULT_SYMBOL)
        self.trading_mode = config.get("trading_mode", TRADING_MODE_SPOT)
        self.leverage = config.get("leverage", 1)

        # 状态变量
        self.balance = 0.0
        self.position = 0.0
        self.entry_price = 0.0
        self.current_price = 0.0
        self.last_price = 0.0
        self.position_open_time = None
        self.peak_balance = 0.0
        self.initial_capital = 0.0
        self.last_sell_ts = 0

        self.running = True
        self.last_sync_time = 0
        self.init_ui()
        self.sync_account()

        self.signals = TradingSignals()
        self.signals.update_price.connect(self.refresh_price_style)
        self.signals.update_ai.connect(self.refresh_ai_ui)
        self.signals.update_account.connect(self.refresh_account_ui)
        self.signals.update_status.connect(self.refresh_status_ui)
        self.signals.update_log.connect(self.append_log)
        self.signals.update_risk.connect(self.refresh_risk_ui)
        self.signals.reconnect_result.connect(self.on_reconnect_result)

        # 启动线程
        self.price_thread = threading.Thread(target=self.price_monitor_loop, daemon=True)
        self.ai_thread = threading.Thread(target=self.ai_cruise_loop, daemon=True)
        self.price_thread.start()
        self.ai_thread.start()

    def closeEvent(self, event):
        self.running = False
        event.accept()

    def sync_account(self):
        acct = self.exchange.get_account()
        with self.account_lock:
            self.balance = acct["balance"]
            self.position = acct["position"]
            self.entry_price = acct["entry_price"]
            self.peak_balance = acct["peak_balance"]
            self.initial_capital = acct.get("initial_capital", 0.0)
            self.position_open_time = acct["position_open_time"]
            self.last_sell_ts = acct["last_trade_time"]

            if self.current_price > 0:
                total = self.balance + self.position * self.current_price
                self.exchange.update_peak_balance(total, self.position)

    def get_total_asset(self):
        with self.account_lock:
            return self.balance + self.position * self.current_price

    def can_make_decision(self):
        if self.current_price <= 0:
            return False

        if time.time() - self.last_sell_ts < COOLING_OFF_MINUTES * 60:
            return False

        with self.account_lock:
            total_val = self.balance + (self.position * self.current_price)
            if total_val < 10:
                return False
        return True

    def calculate_pnl_percent(self, current, entry):
        if entry <= 0:
            return 0.0
        return ((current - entry) / entry) * 100

    def init_ui(self):
        mode_text = f"{self.leverage}x合约" if self.trading_mode == TRADING_MODE_SWAP else "现货"
        self.setWindowTitle(f"AI Trading V16.4 - {self.symbol} [{mode_text}]")
        self.setFixedSize(720, 920)

        cv = QWidget()
        self.setCentralWidget(cv)

        cv.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e2330, stop:0.5 #161b22, stop:1 #0d1117);
                color: #e6edf3;
            }
        """)

        main_layout = QVBoxLayout(cv)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 15, 20, 15)

        # 顶部状态栏
        top_card = QFrame()
        top_card.setStyleSheet("""
            QFrame {
                background: rgba(33, 38, 45, 0.9);
                border-radius: 12px;
                border: 1px solid #30363d;
            }
        """)
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(15, 10, 15, 10)

        status_widget = QWidget()
        st_layout = QHBoxLayout(status_widget)
        st_layout.setContentsMargins(0, 0, 0, 0)
        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Arial", 14))
        self.status_text = QLabel("启动中...")
        self.status_text.setStyleSheet("color: #8b949e; font-size: 12px;")
        st_layout.addWidget(self.status_dot)
        st_layout.addWidget(self.status_text)
        top_layout.addWidget(status_widget)

        self.asset_label = QLabel("资产同步中...")
        self.asset_label.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: bold;")
        top_layout.addWidget(self.asset_label, 1)

        self.panic_btn = QPushButton("紧急平仓")
        self.panic_btn.setStyleSheet("""
            QPushButton {
                background: #da3633;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #f85149;
            }
            QPushButton:pressed {
                background: #b62324;
            }
        """)
        self.panic_btn.clicked.connect(self.trigger_panic_sell)
        top_layout.addWidget(self.panic_btn)

        main_layout.addWidget(top_card)

        # 实战控制栏
        control_card = QFrame()
        control_card.setStyleSheet("""
            QFrame {
                background: rgba(33, 38, 45, 0.95);
                border-radius: 10px;
                border: 1px solid #388bfd;
            }
        """)
        control_layout = QHBoxLayout(control_card)
        control_layout.setContentsMargins(15, 10, 15, 10)
        control_layout.setSpacing(15)

        ctrl_icon = QLabel("⚙️")
        ctrl_icon.setFont(QFont("Arial", 14))
        control_layout.addWidget(ctrl_icon)

        ctrl_title = QLabel("实战控制")
        ctrl_title.setStyleSheet("color: #58a6ff; font-size: 12px; font-weight: bold;")
        control_layout.addWidget(ctrl_title)

        symbol_label = QLabel("交易对:")
        symbol_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        control_layout.addWidget(symbol_label)

        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(SUPPORTED_SYMBOLS)
        self.symbol_combo.setCurrentText(self.symbol)
        self.symbol_combo.setStyleSheet("""
            QComboBox {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px 10px;
                color: #e6edf3;
                font-size: 12px;
                min-width: 100px;
            }
            QComboBox:hover {
                border: 1px solid #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #8b949e;
            }
            QComboBox QAbstractItemView {
                background: #21262d;
                border: 1px solid #30363d;
                selection-background-color: #388bfd;
                color: #e6edf3;
            }
        """)
        control_layout.addWidget(self.symbol_combo)

        mode_label = QLabel("模式:")
        mode_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        control_layout.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["现货 Spot", "合约 Swap"])
        self.mode_combo.setCurrentIndex(0 if self.trading_mode == TRADING_MODE_SPOT else 1)
        self.mode_combo.setStyleSheet("""
            QComboBox {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px 10px;
                color: #e6edf3;
                font-size: 12px;
                min-width: 90px;
            }
            QComboBox:hover {
                border: 1px solid #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #8b949e;
            }
            QComboBox QAbstractItemView {
                background: #21262d;
                border: 1px solid #30363d;
                selection-background-color: #388bfd;
                color: #e6edf3;
            }
        """)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        control_layout.addWidget(self.mode_combo)

        leverage_label = QLabel("杠杆:")
        leverage_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        control_layout.addWidget(leverage_label)

        self.leverage_spin = QSpinBox()
        self.leverage_spin.setRange(1, 125)
        self.leverage_spin.setValue(self.leverage)
        self.leverage_spin.setSuffix("x")
        self.leverage_spin.setEnabled(self.trading_mode == TRADING_MODE_SWAP)
        self.leverage_spin.setStyleSheet("""
            QSpinBox {
                background: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px 8px;
                color: #e6edf3;
                font-size: 12px;
                min-width: 60px;
            }
            QSpinBox:hover {
                border: 1px solid #58a6ff;
            }
            QSpinBox:disabled {
                background: #161b22;
                color: #6e7681;
                border: 1px solid #21262d;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background: #30363d;
                border: none;
                width: 16px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #388bfd;
            }
        """)
        control_layout.addWidget(self.leverage_spin)

        control_layout.addStretch()

        self.apply_btn = QPushButton("应用设置")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #238636;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2ea043;
            }
            QPushButton:pressed {
                background: #1a7f37;
            }
            QPushButton:disabled {
                background: #21262d;
                color: #6e7681;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_trading_settings)
        control_layout.addWidget(self.apply_btn)

        main_layout.addWidget(control_card)

        # 风控状态栏
        risk_card = QFrame()
        risk_card.setStyleSheet("""
            QFrame {
                background: rgba(33, 38, 45, 0.9);
                border-radius: 8px;
                border: 1px solid #30363d;
            }
        """)
        risk_layout = QHBoxLayout(risk_card)
        risk_layout.setContentsMargins(15, 8, 15, 8)

        risk_icon = QLabel("🛡️")
        risk_icon.setFont(QFont("Arial", 14))
        risk_layout.addWidget(risk_icon)

        self.risk_status_label = QLabel("风控状态: 正常")
        self.risk_status_label.setStyleSheet("color: #3fb950; font-size: 12px; font-weight: bold;")
        risk_layout.addWidget(self.risk_status_label)

        risk_layout.addStretch()

        self.drawdown_label = QLabel("当前回撤: 0.0%")
        self.drawdown_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        risk_layout.addWidget(self.drawdown_label)

        self.risk_base_label = QLabel("(基于初始本金)")
        self.risk_base_label.setStyleSheet("color: #6e7681; font-size: 11px; margin-left: 5px;")
        risk_layout.addWidget(self.risk_base_label)

        main_layout.addWidget(risk_card)

        # 中部区域
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(12)

        # 左侧卡片：价格 + 盈亏
        left_card = QFrame()
        left_card.setStyleSheet("""
            QFrame {
                background: rgba(33, 38, 45, 0.9);
                border-radius: 12px;
                border: 1px solid #30363d;
            }
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(20, 25, 20, 25)
        left_layout.setSpacing(15)

        price_title = QLabel("当前价格")
        price_title.setStyleSheet("color: #8b949e; font-size: 12px;")
        price_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(price_title)

        self.price_label = QLabel("$0.00")
        self.price_label.setFont(QFont("Consolas", 42, QFont.Bold))
        self.price_label.setAlignment(Qt.AlignCenter)
        self.price_label.setStyleSheet("color: #e6edf3;")
        left_layout.addWidget(self.price_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #30363d;")
        sep.setFixedHeight(1)
        left_layout.addWidget(sep)

        pnl_title = QLabel("持仓盈亏")
        pnl_title.setStyleSheet("color: #8b949e; font-size: 12px;")
        pnl_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(pnl_title)

        self.pnl_label = QLabel("+0.00%")
        self.pnl_label.setAlignment(Qt.AlignCenter)
        self.pnl_label.setFont(QFont("微软雅黑", 28, QFont.Bold))
        self.pnl_label.setStyleSheet("color: #8b949e;")
        left_layout.addWidget(self.pnl_label)

        left_layout.addStretch()
        middle_layout.addWidget(left_card, 1)

        # 右侧卡片：AI 建议
        right_card = QFrame()
        right_card.setStyleSheet("""
            QFrame {
                background: rgba(33, 38, 45, 0.9);
                border-radius: 12px;
                border: 1px solid #30363d;
            }
        """)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(12)

        ai_title = QLabel("🤖 AI 交易建议")
        ai_title.setStyleSheet("color: #58a6ff; font-size: 14px; font-weight: bold;")
        right_layout.addWidget(ai_title)

        self.ai_advise = QLabel("分析中...")
        self.ai_advise.setFont(QFont("微软雅黑", 24, QFont.Bold))
        self.ai_advise.setStyleSheet("color: #e6edf3;")
        right_layout.addWidget(self.ai_advise)

        self.ai_confidence = QLabel("信心: --")
        self.ai_confidence.setStyleSheet("color: #8b949e; font-size: 13px;")
        right_layout.addWidget(self.ai_confidence)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: #30363d;")
        sep2.setFixedHeight(1)
        right_layout.addWidget(sep2)

        reason_title = QLabel("分析理由")
        reason_title.setStyleSheet("color: #8b949e; font-size: 11px;")
        right_layout.addWidget(reason_title)

        self.ai_reason = QLabel("等待数据...")
        self.ai_reason.setWordWrap(True)
        self.ai_reason.setStyleSheet("color: #c9d1d9; font-size: 12px; line-height: 1.5;")
        right_layout.addWidget(self.ai_reason)

        self.indicator_label = QLabel("RSI: -- | MACD: --")
        self.indicator_label.setStyleSheet("""
            color: #8b949e;
            background: rgba(22, 27, 34, 0.8);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 11px;
        """)
        right_layout.addWidget(self.indicator_label)

        right_layout.addStretch()
        middle_layout.addWidget(right_card, 1)

        main_layout.addLayout(middle_layout, 1)

        # 底部日志
        log_card = QFrame()
        log_card.setStyleSheet("""
            QFrame {
                background: rgba(22, 27, 34, 0.9);
                border-radius: 12px;
                border: 1px solid #30363d;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(15, 12, 15, 12)
        log_layout.setSpacing(8)

        log_title = QLabel("📋 系统日志")
        log_title.setStyleSheet("color: #58a6ff; font-size: 12px; font-weight: bold;")
        log_layout.addWidget(log_title)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFixedHeight(140)
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #010409;
                color: #7d8590;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: 1px solid #21262d;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        log_layout.addWidget(self.log_display)

        main_layout.addWidget(log_card)

    def on_mode_changed(self, index):
        """模式切换时联动杠杆控件"""
        is_swap = (index == 1)
        self.leverage_spin.setEnabled(is_swap)
        if not is_swap:
            self.leverage_spin.setValue(1)
        elif self.leverage_spin.value() == 1:
            self.leverage_spin.setValue(3)

    def apply_trading_settings(self):
        """应用交易设置 - 触发热切换"""
        new_symbol = self.symbol_combo.currentText()
        new_mode = TRADING_MODE_SWAP if self.mode_combo.currentIndex() == 1 else TRADING_MODE_SPOT
        new_leverage = self.leverage_spin.value() if new_mode == TRADING_MODE_SWAP else 1

        if (new_symbol == self.symbol and
            new_mode == self.trading_mode and
            new_leverage == self.leverage):
            self.log("设置未改变，无需应用")
            return

        self.apply_btn.setEnabled(False)
        self.apply_btn.setText("切换中...")

        def do_reconnect():
            success, msg = self.exchange.reconnect(
                new_symbol, new_mode, new_leverage,
                log_callback=lambda m: self.signals.update_log.emit(m)
            )
            self.signals.reconnect_result.emit(success, msg)

        threading.Thread(target=do_reconnect, daemon=True).start()

    def on_reconnect_result(self, success, message):
        """热切换结果回调"""
        self.apply_btn.setEnabled(True)
        self.apply_btn.setText("应用设置")

        if success:
            self.symbol = self.exchange.symbol
            self.trading_mode = self.exchange.trading_mode
            self.leverage = self.exchange.leverage

            mode_text = f"{self.leverage}x合约" if self.trading_mode == TRADING_MODE_SWAP else "现货"
            self.setWindowTitle(f"AI Trading V16.4 - {self.symbol} [{mode_text}]")

            self.sync_account()
            self.log(f"成功: {message}")
        else:
            self.symbol_combo.setCurrentText(self.symbol)
            self.mode_combo.setCurrentIndex(0 if self.trading_mode == TRADING_MODE_SPOT else 1)
            self.leverage_spin.setValue(self.leverage)
            self.log(f"失败: {message}")

    def log(self, text):
        self.signals.update_log.emit(str(text))
        print(text)

    def append_log(self, text):
        self.log_display.append(f"<span style='color:#58a6ff;'>[{datetime.now().strftime('%H:%M:%S')}]</span> {text}")
        self.log_display.moveCursor(QTextCursor.End)

    def trigger_panic_sell(self):
        """触发紧急平仓"""
        dialog = PanicConfirmDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.execute_panic_sell()

    def execute_panic_sell(self):
        """执行紧急平仓"""
        self.log("执行紧急平仓...")

        self.running = False

        with self.account_lock:
            position = self.position

        if position > 0.0001:
            order_id = self.exchange.place_market_order("sell", position)
            if order_id:
                self.log(f"紧急平仓成功 (ID: {order_id[-8:]})")
            else:
                self.log("紧急平仓失败")
        else:
            self.log("无持仓可平")

        self.exchange.clear_local_state()
        self.log("本地状态已清空")

        self.sync_account()
        self.panic_btn.setEnabled(False)
        self.panic_btn.setText("已平仓")

    def price_monitor_loop(self):
        """价格监控循环"""
        while self.running:
            try:
                if not self.exchange.is_safe_to_fetch():
                    time.sleep(0.5)
                    continue

                trading_symbol = self.exchange.get_trading_symbol()
                ticker = self.exchange.exchange.fetch_ticker(trading_symbol)
                price = float(ticker['last'])

                with self.account_lock:
                    color = "#3fb950" if price > self.last_price else "#f85149" if price < self.last_price else "#e6edf3"
                    self.last_price = self.current_price = price

                if time.time() - self.last_sync_time > 10:
                    self.sync_account()
                    self.last_sync_time = time.time()

                if price > 0 and self.balance >= 0 and self.exchange.initial_capital <= 0:
                    with self.account_lock:
                        total = self.balance + self.position * price
                        if total > 0:
                            self.exchange.set_initial_capital(total)

                emit_data = None
                with self.account_lock:
                    pnl = 0.0
                    current_asset = self.balance + self.position * price
                    if self.position > 0.0001 and self.entry_price > 0:
                        pnl = self.calculate_pnl_percent(price, self.entry_price)
                    emit_data = (self.balance, self.position, current_asset, pnl, self.initial_capital, color)

                    risk_ok, risk_msg, drawdown = self.risk_controller.check_risk(current_asset, self.initial_capital)

                self.signals.update_price.emit(price, emit_data[5])
                self.signals.update_account.emit(emit_data[0], emit_data[1], emit_data[2], emit_data[3], emit_data[4])
                self.signals.update_status.emit(True)
                self.signals.update_risk.emit(risk_msg, drawdown)

            except ccxt.NetworkError:
                self.signals.update_status.emit(False)
            except Exception as e:
                if "NoneType" not in str(e):
                    print(f"Monitor Error: {e}")
                self.signals.update_status.emit(False)

            time.sleep(2)

    def fetch_klines(self):
        try:
            trading_symbol = self.exchange.get_trading_symbol()
            ohlcv = self.exchange.exchange.fetch_ohlcv(trading_symbol, TIMEFRAME, limit=200)
            return [float(x[4]) for x in ohlcv]
        except Exception as e:
            error_logger.error(f"Kline Error: {e}")
            return []

    def _calculate_rsi_wilder(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [abs(d) if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_macd(self, prices, fast=12, slow=26, signal=9):
        def calculate_ema_series(data, p):
            if not data:
                return []
            k = 2 / (p + 1)
            ema = [data[0]]
            for price in data[1:]:
                ema.append(price * k + ema[-1] * (1 - k))
            return ema
        if len(prices) < slow + signal:
            return 0, 0, 0
        ema_fast = calculate_ema_series(prices, fast)
        ema_slow = calculate_ema_series(prices, slow)
        dif_series = [f - s for f, s in zip(ema_fast, ema_slow)]
        dea_series = calculate_ema_series(dif_series, signal)
        macd_series = [(dif - dea) * 2 for dif, dea in zip(dif_series, dea_series)]
        return dif_series[-1], dea_series[-1], macd_series[-1]

    def calculate_indicators(self, closes):
        try:
            if len(closes) < 50:
                return None
            rsi = self._calculate_rsi_wilder(closes)
            dif, dea, macd = self._calculate_macd(closes)
            ma5 = sum(closes[-5:]) / 5
            ma20 = sum(closes[-20:]) / 20
            ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else ma20

            std = (sum((c - ma20)**2 for c in closes[-20:]) / 20) ** 0.5
            volatility = (std / ma20 * 100) if ma20 > 0 else 0

            trend_score = 0
            if ma5 > ma20 > ma50:
                trend_score += 40
            if closes[-1] > ma5:
                trend_score += 20
            if macd > 0:
                trend_score += 20
            if 30 < rsi < 70:
                trend_score += 20

            return {
                "ma5": ma5, "ma20": ma20, "ma50": ma50,
                "rsi": rsi, "dif": dif, "dea": dea, "macd": macd,
                "trend_score": trend_score, "volatility": volatility
            }
        except Exception as e:
            return None

    def generate_ai_prompt(self, indicators, position_desc):
        leverage_info = f"杠杆: {self.leverage}x" if self.trading_mode == TRADING_MODE_SWAP else "现货交易"
        prompt = f"""【资产】{self.symbol}
【交易模式】{leverage_info}
【市场数据】
价格: ${self.current_price:,.2f}
趋势分: {indicators['trend_score']}/100
RSI: {indicators['rsi']:.1f}
MACD: {indicators['macd']:.2f}

【状态】
{position_desc}

【任务】
1. action: buy/sell/hold
2. position: 建议仓位(%)
3. reason: 简短理由
4. confidence: 0-100

返回JSON。"""
        return prompt

    def should_sell(self, indicators, ai_action):
        with self.account_lock:
            if self.position <= 0.0001:
                return False, "无持仓"

            if ai_action == "sell":
                return True, "AI建议卖出"

            if self.position_open_time:
                try:
                    holding_hours = (datetime.now() - self.position_open_time).total_seconds() / 3600
                    if holding_hours >= 12:
                        return True, f"时间止损({holding_hours:.1f}h)"
                except:
                    pass

            if indicators['trend_score'] < 25 and indicators['macd'] < 0:
                return True, "趋势崩坏"

            return False, "持有"

    def execute_trade(self, action, indicators, ai_data):
        if not self.trade_lock.acquire(blocking=False):
            return

        try:
            with self.account_lock:
                current_price = self.current_price
                current_total = self.balance + self.position * current_price
                local_initial = self.initial_capital
                local_position = self.position

            allowed, risk_reason = self.risk_controller.check_trade_permission(
                current_total, local_initial, action
            )

            if not allowed:
                self.log(f"风控拦截({action}): {risk_reason}")
                return

            should_sell_flag, sell_reason = self.should_sell(indicators, action)

            if should_sell_flag and local_position > 0.0001:
                self.log(f"执行卖出: {sell_reason}")
                order_id = self.exchange.place_limit_order_with_stop("sell", local_position, current_price)
                if order_id:
                    self.log(f"卖出挂单成功 (ID: {order_id[-4:]})")
                    self.sync_account()
                else:
                    self.log("卖出下单失败")
                return

            if action == "buy" and self.balance > 10:
                if time.time() - self.last_sell_ts < COOLING_OFF_MINUTES * 60:
                    self.log("处于卖出冷却期，跳过买入")
                    return

                if local_position * current_price > 10:
                    return

                suggested_ratio = ai_data.get("position", 50) / 100
                final_ratio = max(0.2, min(0.95, suggested_ratio))

                if self.trading_mode == TRADING_MODE_SWAP:
                    effective_buying_power = self.balance * self.leverage
                    buy_amount = effective_buying_power * final_ratio
                    self.log(f"合约购买力: ${self.balance:.1f} x {self.leverage}倍杠杆 = ${effective_buying_power:.1f}")
                else:
                    buy_amount = self.balance * final_ratio

                buy_qty = buy_amount / current_price

                self.log(f"执行买入: ${buy_amount:.1f} ({final_ratio*100:.0f}% 仓位)")

                stop_loss = self.risk_controller.calculate_stop_loss(current_price)

                order_id = self.exchange.place_limit_order_with_stop("buy", buy_qty, current_price, stop_loss_price=stop_loss)

                if order_id:
                    self.log(f"买入挂单成功 (ID: {order_id[-4:]})")
                    trade_logger.info(f"BUY: {current_price} SL: {stop_loss}")
                    time.sleep(1)
                    self.sync_account()
                else:
                    self.log("买入下单失败")

        except Exception as e:
            error_logger.error(f"Trade Execution Error: {e}")
            self.log(f"交易异常: {e}")
        finally:
            self.trade_lock.release()

    def ai_cruise_loop(self):
        """AI 巡航循环"""
        try:
            deepseek_key = self.config.get("deepseek_api_key")
            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            self.log("AI 引擎就绪")
        except Exception:
            return

        while self.running:
            try:
                if not self.exchange.is_safe_to_fetch():
                    time.sleep(1)
                    continue

                if not self.can_make_decision():
                    for _ in range(10):
                        if not self.running:
                            return
                        time.sleep(1)
                    continue

                closes = self.fetch_klines()
                indicators = self.calculate_indicators(closes)

                if not indicators:
                    time.sleep(10)
                    continue

                with self.account_lock:
                    base_coin = self.symbol.split('/')[0]
                    pos_desc = f"持仓 {self.position:.6f} {base_coin}" if self.position > 0.0001 else "当前空仓"

                prompt = self.generate_ai_prompt(indicators, pos_desc)
                self.log(f"AI 思考中... (RSI:{indicators['rsi']:.1f})")

                response = client.chat.completions.create(
                    model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.1
                )
                content = response.choices[0].message.content.strip()

                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                ai_data = json.loads(content)

                action = ai_data.get("action", "hold")
                reason = ai_data.get("reason", "N/A")
                conf = ai_data.get("confidence", 50)

                self.log(f"AI建议: {action} ({reason})")
                self.signals.update_ai.emit(action, reason, conf, datetime.now().strftime("%H:%M"), indicators)

                if action in ["buy", "sell"]:
                    self.execute_trade(action, indicators, ai_data)

                for _ in range(180):
                    if not self.running:
                        return
                    time.sleep(1)

            except Exception as e:
                if "NoneType" not in str(e):
                    error_logger.error(f"AI Loop: {e}")
                    self.log("AI 轮询暂歇")
                time.sleep(30)

    def refresh_price_style(self, p, c):
        self.price_label.setText(f"${p:,.2f}")
        self.price_label.setStyleSheet(f"color: {c};")

    def refresh_status_ui(self, ok):
        self.status_dot.setStyleSheet(f"color: {'#3fb950' if ok else '#f85149'};")
        self.status_text.setText("API正常" if ok else "API断连")

    def refresh_ai_ui(self, adv, reason, conf, ts, ind):
        action_text = {"buy": "买入", "sell": "卖出", "hold": "持有"}.get(adv, adv)
        self.ai_advise.setText(f"建议: {action_text.upper()}")
        color = "#3fb950" if adv == 'buy' else "#f85149" if adv == 'sell' else "#e6edf3"
        self.ai_advise.setStyleSheet(f"color: {color};")
        self.ai_confidence.setText(f"信心度: {conf}%  |  更新: {ts}")
        self.ai_reason.setText(reason)
        self.indicator_label.setText(f"RSI: {ind['rsi']:.1f}  |  MACD: {ind['macd']:.2f}  |  趋势分: {ind['trend_score']}/100")

    def refresh_account_ui(self, bal, pos, total, pnl, initial_cap):
        base_coin = self.symbol.split('/')[0]
        quote_coin = self.symbol.split('/')[1]
        self.asset_label.setText(f"{quote_coin}: {bal:,.2f}  |  {base_coin}: {pos:.6f}  |  总值: ${total:,.2f}")

        pnl_color = "#3fb950" if pnl > 0 else "#f85149" if pnl < 0 else "#8b949e"
        self.pnl_label.setText(f"{pnl:+.2f}%")
        self.pnl_label.setStyleSheet(f"color: {pnl_color};")

        if initial_cap > 0:
            total_return = ((total - initial_cap) / initial_cap) * 100
            sign = "+" if total_return >= 0 else ""
            mode_text = f"{self.leverage}x合约" if self.trading_mode == TRADING_MODE_SWAP else "现货"
            self.setWindowTitle(f"AI Trading V16.4 - {self.symbol} [{mode_text}] | 累计收益: {sign}{total_return:.2f}%")

    def refresh_risk_ui(self, risk_msg, drawdown):
        """刷新风控状态显示"""
        drawdown_pct = drawdown * 100

        if drawdown_pct <= 0:
            status_color = "#3fb950"
            status_text = "风控状态: 正常"
        elif drawdown_pct < self.risk_controller.max_drawdown * 100 * 0.5:
            status_color = "#3fb950"
            status_text = "风控状态: 正常"
        elif drawdown_pct < self.risk_controller.max_drawdown * 100 * 0.8:
            status_color = "#f0883e"
            status_text = "风控状态: 警戒"
        else:
            status_color = "#f85149"
            status_text = "风控状态: 危险"

        self.risk_status_label.setText(status_text)
        self.risk_status_label.setStyleSheet(f"color: {status_color}; font-size: 12px; font-weight: bold;")

        self.drawdown_label.setText(f"当前回撤: {drawdown_pct:.1f}% / {self.risk_controller.max_drawdown*100:.0f}%")

        if drawdown_pct > self.risk_controller.max_drawdown * 100:
            self.drawdown_label.setStyleSheet("color: #f85149; font-size: 12px; font-weight: bold;")
        else:
            self.drawdown_label.setStyleSheet("color: #8b949e; font-size: 12px;")
