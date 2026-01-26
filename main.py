# -*- coding: utf-8 -*-
"""
main.py - 程序启动入口
AI Trading System V17.2
负责组装各模块并启动 QApplication
"""

import sys

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from config import SCRIPT_DIR, SECRETS_FILE, DATA_FILE, ConfigManager
from ui import ConfigWizard, CryptoAIExpert


def main():
    """主程序入口"""

    # 启动时打印路径信息
    print("=" * 50)
    print("AI Trading System V17.2 (模块化重构版)")
    print("=" * 50)
    print(f"脚本目录: {SCRIPT_DIR}")
    print(f"配置文件: {SECRETS_FILE}")
    print(f"数据文件: {DATA_FILE}")
    print("=" * 50)

    app = QApplication(sys.argv)

    # 检查配置文件
    if not ConfigManager.config_exists():
        print("[V16.0] 配置文件不存在或无效，启动配置向导...")
        wizard = ConfigWizard()
        if wizard.exec() != QDialog.Accepted:
            print("用户取消配置，程序退出")
            sys.exit(0)

    # 加载配置
    config = ConfigManager.load_config()

    # 验证配置
    if not config.get("deepseek_api_key") or not config.get("exchange_api_key"):
        QMessageBox.critical(None, "错误", f"配置无效，请删除以下文件重新配置:\n{SECRETS_FILE}")
        sys.exit(1)

    # 启动主窗口
    win = CryptoAIExpert(config)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
