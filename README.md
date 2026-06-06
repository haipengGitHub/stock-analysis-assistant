# 📈 股票分析助手

一个功能完整的股票分析 Web 应用，提供实时行情获取、技术指标分析和趋势预测功能。

## ✨ 功能特性

- **实时行情数据** - 获取股票实时价格、涨跌幅、成交量等基本信息
- **技术指标分析** - 自动计算 RSI、MACD、布林带、移动平均线等常用技术指标
- **AI 趋势预测** - 基于技术指标综合分析，给出趋势预测和目标价位
- **交互式图表** - 使用 ECharts 展示 K 线图、均线和成交量
- **智能搜索** - 支持股票代码搜索和热门股票推荐

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python + FastAPI |
| 数据源 | AkShare（主）/ Yahoo Finance（备） |
| 技术分析 | pandas-ta |
| 前端 | HTML + JavaScript + ECharts |
| 机器学习 | scikit-learn |

## 📦 安装运行

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

> 行情默认经 **AkShare** 拉取（国内网络更稳定）；若失败会自动回退 **yfinance**。
```

### 2. 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动

### 3. 访问应用

在浏览器中打开 `http://localhost:8000` 即可使用

## 📋 使用说明

### 支持的股票代码

- **美股**: AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN, META 等
- **A股**: 600519.SS (贵州茅台), 000001.SZ (平安银行), 600036.SH (招商银行) 等
- **中概股**: BABA (阿里巴巴), JD (京东), PDD (拼多多) 等

### 技术指标说明

| 指标 | 说明 | 买入信号 | 卖出信号 |
|------|------|----------|----------|
| RSI (14) | 相对强弱指标 | < 30 超卖 | > 70 超买 |
| MACD | 指数平滑移动平均线 | 上穿信号线 | 下穿信号线 |
| 布林带 | 价格波动范围 | 价格低于下轨 | 价格高于上轨 |
| 均线趋势 | 移动平均线组合 | 价格 > MA20 > MA50 | 价格 < MA20 < MA50 |

### API 接口

#### 获取股票分析

```
GET /api/stock/{symbol}?period={period}
```

参数:
- `symbol`: 股票代码 (如 AAPL)
- `period`: 数据周期 (1mo, 3mo, 6mo, 1y, 2y)

#### 搜索股票

```
GET /api/search/{query}
```

#### 热门股票

```
GET /api/suggestions
```

## ⚠️ 免责声明

本工具仅用于学习和研究目的，不构成任何投资建议。股票投资有风险，入市需谨慎。

## 📄 许可证

MIT License
