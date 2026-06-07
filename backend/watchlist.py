"""
自选股管理模块 - 使用 JSON 文件持久化存储
"""

import json
import os
from pathlib import Path
from typing import List, Dict
import fastapi
from fastapi import HTTPException

# 自选股存储文件路径
WATCHLIST_FILE = Path(__file__).parent.parent / "data" / "watchlist.json"

# 股票名称映射（从 main.py 复制，避免循环导入）
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


def _ensure_data_dir() -> None:
    """确保数据目录存在"""
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)


def _read_watchlist() -> List[str]:
    """读取自选股列表"""
    _ensure_data_dir()
    if not WATCHLIST_FILE.exists():
        return []
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("symbols", [])
    except (json.JSONDecodeError, KeyError):
        return []


def _write_watchlist(symbols: List[str]) -> None:
    """写入自选股列表"""
    _ensure_data_dir()
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump({"symbols": symbols}, f, ensure_ascii=False, indent=2)


def get_watchlist() -> List[str]:
    """获取自选股列表"""
    return _read_watchlist()


def add_to_watchlist(symbol: str) -> bool:
    """添加股票到自选股

    返回: True=新增成功, False=已存在
    """
    symbol = symbol.upper().strip()
    symbols = _read_watchlist()
    if symbol in symbols:
        return False
    symbols.append(symbol)
    _write_watchlist(symbols)
    return True


def remove_from_watchlist(symbol: str) -> bool:
    """从自选股移除股票

    返回: True=移除成功, False=不存在
    """
    symbol = symbol.upper().strip()
    symbols = _read_watchlist()
    if symbol not in symbols:
        return False
    symbols.remove(symbol)
    _write_watchlist(symbols)
    return True


def is_in_watchlist(symbol: str) -> bool:
    """检查股票是否在自选股中"""
    return symbol.upper().strip() in _read_watchlist()


def get_watchlist_with_names() -> List[Dict[str, str]]:
    """获取带名称的自选股列表"""
    symbols = _read_watchlist()
    return [
        {"symbol": s, "name": STOCK_NAMES.get(s, s)}
        for s in symbols
    ]
