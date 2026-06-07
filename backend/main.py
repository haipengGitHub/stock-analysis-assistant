"""
股票分析助手 - FastAPI 后端服务
提供股票数据获取、技术指标分析和趋势预测功能
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import pandas_ta_classic  # noqa: F401 — 注册 DataFrame.ta 扩展
import numpy as np
from datetime import timedelta
import time
import warnings

from market_data import fetch_stock_history
from watchlist import get_watchlist_with_names, add_to_watchlist, remove_from_watchlist, is_in_watchlist

warnings.filterwarnings('ignore')

app = FastAPI(title="股票分析助手 API", version="1.0.0")

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="../frontend/static"), name="static")
templates = Jinja2Templates(directory="../frontend/templates")

# 行情缓存：减少重复请求外部数据源
_HISTORY_CACHE: Dict[str, Tuple[float, pd.DataFrame]] = {}
CACHE_TTL_SECONDS = 300

PERIOD_DAYS = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
}

STOCK_NAMES = {
    "AAPL": "Apple Inc.",
    "GOOGL": "Alphabet Inc.",
    "MSFT": "Microsoft Corporation",
    "AMZN": "Amazon.com Inc.",
    "TSLA": "Tesla Inc.",
    "META": "Meta Platforms Inc.",
    "NVDA": "NVIDIA Corporation",
    "600519.SS": "贵州茅台",
    "000001.SZ": "平安银行",
    "600036.SH": "招商银行",
    "BABA": "阿里巴巴",
    "JD": "京东",
    "PDD": "拼多多",
    "NTES": "网易",
}


# 数据模型
class StockData(BaseModel):
    symbol: str
    name: str
    current_price: float
    change: float
    change_percent: float
    high_52w: float
    low_52w: float
    volume: int
    market_cap: Optional[str] = None


class TechnicalIndicator(BaseModel):
    name: str
    value: float
    signal: str  # 'buy', 'sell', 'neutral'


class TrendPrediction(BaseModel):
    trend: str  # 'bullish', 'bearish', 'neutral'
    confidence: float  # 0-100
    target_price: Optional[float]
    reason: List[str]


class StockAnalysis(BaseModel):
    stock: StockData
    indicators: List[TechnicalIndicator]
    prediction: TrendPrediction
    chart_data: Dict[str, Any]


def format_number(num: float) -> str:
    """格式化大数字"""
    if num >= 1e12:
        return f"{num/1e12:.2f}T"
    elif num >= 1e9:
        return f"{num/1e9:.2f}B"
    elif num >= 1e6:
        return f"{num/1e6:.2f}M"
    elif num >= 1e3:
        return f"{num/1e3:.2f}K"
    return str(num)


def _is_rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "too many requests" in msg or "rate limit" in msg


def _raise_for_market_error(exc: Exception, symbol: str) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    msg = str(exc).lower()
    if _is_rate_limited(exc) or "yfratelimit" in msg:
        raise HTTPException(
            status_code=503,
            detail="行情源请求过于频繁，请稍后再试（约 1–5 分钟）",
        )
    if "expecting value" in msg or "no price data" in msg:
        raise HTTPException(
            status_code=503,
            detail="无法从 Yahoo 获取行情（网络或限流），已尝试备用源仍失败，请稍后重试",
        )
    raise HTTPException(
        status_code=500,
        detail=f"获取 {symbol} 行情失败: {exc}",
    )


def _fetch_period_for(period: str) -> str:
    """单次拉取足够长的历史，图表再按 period 截取"""
    return "2y" if period == "2y" else "1y"


def _slice_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    days = PERIOD_DAYS.get(period, 90)
    cutoff = df.index.max() - timedelta(days=days)
    return df[df.index >= cutoff]


def fetch_history(symbol: str, period: str) -> pd.DataFrame:
    """拉取历史行情（AkShare 优先，yfinance 备用，带内存缓存）"""
    fetch_period = _fetch_period_for(period)
    cache_key = f"{symbol.upper()}:{fetch_period}"
    now = time.time()

    cached = _HISTORY_CACHE.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL_SECONDS:
        return cached[1].copy()

    try:
        df = fetch_stock_history(symbol, fetch_period)
    except Exception as e:
        _raise_for_market_error(e, symbol)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"找不到股票 {symbol}")

    _HISTORY_CACHE[cache_key] = (now, df.copy())
    return df


def stock_info_from_df(symbol: str, df: pd.DataFrame) -> Dict[str, Any]:
    """从行情 DataFrame 推导基本信息（不调用 ticker.info）"""
    if len(df) < 2:
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 数据不足")

    current_price = float(df["Close"].iloc[-1])
    prev_price = float(df["Close"].iloc[-2])
    change = current_price - prev_price
    change_percent = (change / prev_price) * 100 if prev_price else 0.0

    year_window = df.tail(min(252, len(df)))
    high_52w = float(year_window["High"].max())
    low_52w = float(year_window["Low"].min())

    sym = symbol.upper()
    return {
        "symbol": sym,
        "name": STOCK_NAMES.get(sym, sym),
        "current_price": round(current_price, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "volume": int(df["Volume"].iloc[-1]),
        "market_cap": None,
    }


def calculate_technical_indicators_from_df(df: pd.DataFrame) -> List[Dict]:
    """基于已有行情计算技术指标"""
    if df.empty or len(df) < 50:
        return []

    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work = work.reset_index()
        date_col = "Date" if "Date" in work.columns else work.columns[0]
        work[date_col] = pd.to_datetime(work[date_col])
        work = work.set_index(date_col)

    indicators = []

    rsi = work.ta.rsi(length=14)
    if rsi is not None and not rsi.empty:
        rsi_value = float(rsi.iloc[-1])
        signal = "neutral"
        if rsi_value < 30:
            signal = "buy"
        elif rsi_value > 70:
            signal = "sell"
        indicators.append({
            "name": "RSI (14)",
            "value": round(rsi_value, 2),
            "signal": signal,
        })

    macd_df = work.ta.macd(fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        macd = macd_df.iloc[-1]
        macd_line = float(macd["MACD_12_26_9"])
        signal_line = float(macd["MACDs_12_26_9"])
        signal = "neutral"
        if macd_line > signal_line and macd_line > 0:
            signal = "buy"
        elif macd_line < signal_line and macd_line < 0:
            signal = "sell"
        indicators.append({
            "name": "MACD",
            "value": round(macd_line, 4),
            "signal": signal,
        })

    bb = work.ta.bbands(length=20, std=2)
    if bb is not None and not bb.empty:
        current_price = float(work["Close"].iloc[-1])
        lower_band = float(bb["BBL_20_2.0"].iloc[-1])
        upper_band = float(bb["BBU_20_2.0"].iloc[-1])
        signal = "neutral"
        if current_price < lower_band:
            signal = "buy"
        elif current_price > upper_band:
            signal = "sell"
        band_width = upper_band - lower_band
        position = (
            round((current_price - lower_band) / band_width * 100, 2)
            if band_width > 0
            else 50.0
        )
        indicators.append({
            "name": "布林带位置",
            "value": position,
            "signal": signal,
        })

    ma_20 = work["Close"].rolling(window=20).mean().iloc[-1]
    ma_50 = work["Close"].rolling(window=50).mean().iloc[-1]
    current_price = float(work["Close"].iloc[-1])

    ma_signal = "neutral"
    if current_price > ma_20 > ma_50:
        ma_signal = "buy"
    elif current_price < ma_20 < ma_50:
        ma_signal = "sell"

    indicators.append({
        "name": "均线趋势",
        "value": round(current_price, 2),
        "signal": ma_signal,
    })

    return indicators


def predict_trend_from_df(df: pd.DataFrame, indicators: List[Dict]) -> Dict:
    """基于指标与行情预测趋势（不再额外请求 Yahoo）"""
    buy_signals = sum(1 for i in indicators if i["signal"] == "buy")
    sell_signals = sum(1 for i in indicators if i["signal"] == "sell")
    neutral_signals = len(indicators) - buy_signals - sell_signals

    total = len(indicators)
    if total == 0:
        return {
            "trend": "neutral",
            "confidence": 0,
            "target_price": None,
            "reason": ["数据不足，无法分析"],
        }

    if buy_signals > sell_signals and buy_signals > neutral_signals:
        trend = "bullish"
        confidence = round((buy_signals / total) * 100, 1)
    elif sell_signals > buy_signals and sell_signals > neutral_signals:
        trend = "bearish"
        confidence = round((sell_signals / total) * 100, 1)
    else:
        trend = "neutral"
        confidence = 50.0

    reasons = []
    for ind in indicators:
        if ind["signal"] == "buy":
            reasons.append(f"{ind['name']} 发出买入信号")
        elif ind["signal"] == "sell":
            reasons.append(f"{ind['name']} 发出卖出信号")

    target_price = None
    if len(df) > 20:
        current_price = float(df["Close"].iloc[-1])
        volatility = float(df["Close"].pct_change().std() * np.sqrt(252))

        if trend == "bullish":
            target_price = round(current_price * (1 + volatility * 0.5), 2)
        elif trend == "bearish":
            target_price = round(current_price * (1 - volatility * 0.5), 2)
        else:
            target_price = round(current_price, 2)

    return {
        "trend": trend,
        "confidence": confidence,
        "target_price": target_price,
        "reason": reasons if reasons else ["指标信号不明确"],
    }


def chart_data_from_df(df: pd.DataFrame) -> Dict[str, Any]:
    """从行情 DataFrame 生成图表数据"""
    if df.empty:
        return {}

    out = df.reset_index()
    date_col = "Date" if "Date" in out.columns else out.columns[0]
    out[date_col] = pd.to_datetime(out[date_col]).dt.strftime("%Y-%m-%d")

    return {
        "dates": out[date_col].tolist(),
        "open": out["Open"].tolist(),
        "high": out["High"].tolist(),
        "low": out["Low"].tolist(),
        "close": out["Close"].tolist(),
        "volume": out["Volume"].tolist(),
    }


# API 路由
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """主页"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/stock/{symbol}", response_model=StockAnalysis)
async def analyze_stock(
    symbol: str,
    period: str = Query("3mo", description="数据周期: 1mo, 3mo, 6mo, 1y, 2y"),
):
    """
    分析股票

    - **symbol**: 股票代码 (如: AAPL, TSLA, 600519.SS)
    - **period**: 数据周期
    """
    symbol = symbol.upper().strip()
    if period not in PERIOD_DAYS:
        raise HTTPException(status_code=400, detail=f"不支持的周期: {period}")

    try:
        full_df = fetch_history(symbol, period)
        chart_df = _slice_by_period(full_df, period)

        stock_info = stock_info_from_df(symbol, full_df)
        indicators_data = calculate_technical_indicators_from_df(full_df)
        prediction_data = predict_trend_from_df(chart_df, indicators_data)
        chart_data = chart_data_from_df(chart_df)
    except HTTPException:
        raise
    except Exception as e:
        _raise_for_market_error(e, symbol)

    return StockAnalysis(
        stock=StockData(**stock_info),
        indicators=[TechnicalIndicator(**i) for i in indicators_data],
        prediction=TrendPrediction(**prediction_data),
        chart_data=chart_data,
    )


@app.get("/api/search/{query}")
async def search_stocks(query: str):
    """
    搜索股票 (简化版，返回常见股票)

    - **query**: 搜索关键词
    """
    query = query.upper()
    results = []

    for sym, name in STOCK_NAMES.items():
        if query in sym or query in name.upper():
            results.append({"symbol": sym, "name": name})

    return {"results": results[:10]}


@app.get("/api/suggestions")
async def get_suggestions():
    """获取热门股票建议"""
    suggestions = [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "TSLA", "name": "Tesla Inc."},
        {"symbol": "NVDA", "name": "NVIDIA Corporation"},
        {"symbol": "600519.SS", "name": "贵州茅台"},
        {"symbol": "BABA", "name": "阿里巴巴"},
    ]
    return {"suggestions": suggestions}


# 自选股相关接口
@app.get("/api/watchlist")
async def get_watchlist_api():
    """获取自选股列表"""
    return {"watchlist": get_watchlist_with_names()}


@app.post("/api/watchlist/{symbol}")
async def add_to_watchlist_api(symbol: str):
    """添加股票到自选股"""
    added = add_to_watchlist(symbol)
    if not added:
        raise HTTPException(status_code=400, detail=f"股票 {symbol} 已在自选中")
    return {"message": "已添加到自选", "symbol": symbol.upper()}


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist_api(symbol: str):
    """从自选股移除股票"""
    removed = remove_from_watchlist(symbol)
    if not removed:
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 不在自选中")
    return {"message": "已从自选移除", "symbol": symbol.upper()}


@app.get("/api/watchlist/check/{symbol}")
async def check_watchlist(symbol: str):
    """检查股票是否在自选中"""
    return {"in_watchlist": is_in_watchlist(symbol)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
