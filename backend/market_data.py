"""
行情数据获取：优先 AkShare（国内网络更稳定），失败时回退 yfinance。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Literal, Tuple

import pandas as pd

Market = Literal["us", "cn"]


def parse_symbol(symbol: str) -> Tuple[Market, str]:
    """解析市场类型与代码（供 AkShare 使用）"""
    raw = symbol.upper().strip()
    for suffix in (".SS", ".SH", ".SZ"):
        if raw.endswith(suffix):
            return "cn", raw[: -len(suffix)]
    return "us", raw


def _normalize_us(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.set_index("date").sort_index()
    out = out.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    return out[["Open", "High", "Low", "Close", "Volume"]]


def _normalize_cn(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["日期"] = pd.to_datetime(out["日期"])
    out = out.set_index("日期").sort_index()
    out = out.rename(
        columns={
            "开盘": "Open",
            "收盘": "Close",
            "最高": "High",
            "最低": "Low",
            "成交量": "Volume",
        }
    )
    return out[["Open", "High", "Low", "Close", "Volume"]]


def _fetch_akshare_us(symbol: str) -> pd.DataFrame:
    import akshare as ak

    df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
    if df is None or df.empty:
        raise ValueError("AkShare 未返回美股数据")
    return _normalize_us(df)


def _fetch_akshare_cn(code: str) -> pd.DataFrame:
    import akshare as ak

    start = (datetime.now() - timedelta(days=800)).strftime("%Y%m%d")
    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start,
        adjust="qfq",
    )
    if df is None or df.empty:
        raise ValueError("AkShare 未返回 A 股数据")
    return _normalize_cn(df)


def _fetch_yfinance(symbol: str, fetch_period: str) -> pd.DataFrame:
    import yfinance as yf

    try:
        from yfinance.exceptions import YFRateLimitError
    except ImportError:
        YFRateLimitError = Exception  # type: ignore

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            df = yf.download(
                symbol,
                period=fetch_period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                if "Date" in df.columns:
                    df = df.set_index("Date")
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                df = df.sort_index()
                cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
                return df[cols]
        except YFRateLimitError as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            last_err = e
            if "429" in str(e).lower() or "too many" in str(e).lower():
                time.sleep(2 * (attempt + 1))
                continue
            raise

    if last_err:
        raise last_err
    raise ValueError("yfinance 未返回数据")


def fetch_stock_history(symbol: str, fetch_period: str = "1y") -> pd.DataFrame:
    """
    拉取日线行情。优先 AkShare，失败再试 yfinance。
    fetch_period 仅用于 yfinance 回退（1y / 2y）。
    """
    market, code = parse_symbol(symbol)
    errors: list[str] = []

    for attempt in range(2):
        try:
            if market == "us":
                return _fetch_akshare_us(code)
            return _fetch_akshare_cn(code)
        except Exception as e:
            errors.append(f"AkShare: {e}")
            if attempt == 0:
                time.sleep(1)

    try:
        yf_symbol = symbol.upper().strip()
        return _fetch_yfinance(yf_symbol, fetch_period)
    except Exception as e:
        errors.append(f"yfinance: {e}")

    raise RuntimeError("；".join(errors))
