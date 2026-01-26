# -*- coding: utf-8 -*-
"""
config.py - 全局配置模块
存放所有常量配置、ConfigManager类
不依赖其他项目模块
"""

import os
import json

# ================= 路径配置 =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE = os.path.join(SCRIPT_DIR, "secrets.json")
DATA_FILE = os.path.join(SCRIPT_DIR, "trading_account.json")
LOG_DIR = SCRIPT_DIR

# ================= 交易配置 =================
DEFAULT_SYMBOL = "BTC/USDT"
TIMEFRAME = '5m'
SLIPPAGE_TOLERANCE = 0.005
COOLING_OFF_MINUTES = 30

# 预设交易对列表
SUPPORTED_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT"
]

# 交易模式常量
TRADING_MODE_SPOT = "spot"
TRADING_MODE_SWAP = "swap"

# ================= 代理设置 =================
PROXIES = {
    'http': 'http://127.0.0.1:7897',
    'https': 'http://127.0.0.1:7897'
}


# ================= 配置管理器 =================
class ConfigManager:
    """配置管理器 - V16.0 增强版"""

    @staticmethod
    def load_config():
        """加载配置，返回配置字典"""
        config = {
            "deepseek_api_key": None,
            "exchange_api_key": None,
            "exchange_secret": None,
            "exchange_passphrase": None,
            "max_drawdown": 0.15,
            "symbol": DEFAULT_SYMBOL,
            "trading_mode": TRADING_MODE_SPOT,
            "leverage": 1
        }

        if os.path.exists(SECRETS_FILE):
            try:
                with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config["deepseek_api_key"] = data.get("deepseek_api_key")
                    config["exchange_api_key"] = data.get("exchange_api_key")
                    config["exchange_secret"] = data.get("exchange_secret")
                    config["exchange_passphrase"] = data.get("exchange_passphrase")
                    config["max_drawdown"] = data.get("max_drawdown", 0.15)
                    config["symbol"] = data.get("symbol", DEFAULT_SYMBOL)
                    config["trading_mode"] = data.get("trading_mode", TRADING_MODE_SPOT)
                    config["leverage"] = data.get("leverage", 1)
                    return config
            except Exception as e:
                print(f"[V16.0] 配置加载警告: {e}")
                pass

        # 回退到环境变量
        config["deepseek_api_key"] = os.getenv("DEEPSEEK_API_KEY")
        config["exchange_api_key"] = os.getenv("EXCHANGE_API_KEY")
        config["exchange_secret"] = os.getenv("EXCHANGE_SECRET_KEY")
        config["exchange_passphrase"] = os.getenv("EXCHANGE_PASSPHRASE")

        return config

    @staticmethod
    def save_config(config):
        """保存配置到 secrets.json"""
        try:
            with open(SECRETS_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"[V16.0] 配置已保存到: {SECRETS_FILE}")
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    @staticmethod
    def update_trading_params(symbol, trading_mode, leverage):
        """仅更新交易参数（热切换后调用）"""
        try:
            config = ConfigManager.load_config()
            config["symbol"] = symbol
            config["trading_mode"] = trading_mode
            config["leverage"] = leverage
            return ConfigManager.save_config(config)
        except Exception as e:
            print(f"更新交易参数失败: {e}")
            return False

    @staticmethod
    def config_exists():
        """检查配置文件是否存在且有效"""
        if not os.path.exists(SECRETS_FILE):
            print(f"[V16.0] 配置文件不存在: {SECRETS_FILE}")
            return False
        try:
            with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                required = ["deepseek_api_key", "exchange_api_key", "exchange_secret"]
                return all(data.get(k) for k in required)
        except Exception:
            return False
