# AI-Trading-Bot
Intelligent Cryptocurrency Trading System (V16.4) powered by DeepSeek AI and CCXT. Supports Spot/Swap modes, real-time risk control, and PySide6 GUI.
🤖 AI-Trading-Bot V16.4基于 DeepSeek AI 决策与 CCXT 框架的量化交易系统。本系统集成了实时行情监控、AI 逻辑分析、自动化风控保护以及友好的 PySide6 交互界面。✨ 核心功能🧠 AI 智能决策：集成 DeepSeek-V3 模型，根据 RSI、MACD、MA 等多维度指标自动生成买卖建议。🔄 双模热切换：支持 现货 (Spot) 与 USDT本位合约 (Swap) 实时切换，无需重启程序。🛡️ 严苛风控：内置最大回撤保护逻辑，当回撤超过阈值（如 $15\%$）时自动拦截交易。支持动态计算止损位。设有卖出后冷却期，防止过度交易。⚡ 实时监控：基于多线程技术，实现秒级价格同步与账户资产校验。🚨 紧急功能：一键“紧急平仓”按钮，3秒延迟确认，确保资金安全。🛠️ 技术栈语言: Python 3.10+交易引擎: CCXT (对接 OKX 交易所)AI 接口: OpenAI SDK (DeepSeek API)GUI 框架: PySide6 (Qt for Python)🚀 快速开始安装依赖:Bashpip install ccxt openai PySide6 loguru
配置密钥: 启动程序后，配置向导会自动引导您创建 secrets.json。运行:Bashpython main.py
📈 风控逻辑说明系统通过以下公式监控当前账户风险：$$Drawdown = \frac{Initial\_Capital - Current\_Total\_Asset}{Initial\_Capital}$$若 $Drawdown > Max\_Drawdown\_Threshold$，系统将强制停止买入权限。⚠️ 免责声明投资有风险，入市需谨慎。 本项目仅供技术交流与学习使用。作者不对使用本软件造成的任何经济损失负责。请在实盘前务必在模拟盘进行充分测试。
