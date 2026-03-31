import pandas as pd
import numpy as np
from typing import Tuple, Optional


def calculate_rsi_series(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSIの全時系列を計算（Wilder法）"""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_rsi(closes: pd.Series, period: int = 14) -> float:
    """RSI最新値を返す"""
    if len(closes) < period + 1:
        return 50.0
    return float(calculate_rsi_series(closes, period).iloc[-1])


def calculate_macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD, シグナル線, ヒストグラムを返す"""
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_moving_averages(closes: pd.Series) -> dict:
    """MA25, MA75, MA200を計算。データ不足はNoneを返す"""
    mas = {}
    for period in [25, 75, 200]:
        if len(closes) >= period:
            mas[f"MA{period}"] = closes.rolling(window=period).mean()
        else:
            mas[f"MA{period}"] = None
    return mas


def get_trend(closes: pd.Series) -> str:
    """MA25/MA75を用いてトレンドを判定"""
    if len(closes) < 25:
        return "不明"

    current = closes.iloc[-1]
    ma25 = closes.rolling(window=25).mean().iloc[-1]

    if len(closes) >= 75:
        ma75 = closes.rolling(window=75).mean().iloc[-1]
        if current > ma25 and ma25 > ma75:
            return "↑ 上昇"
        elif current < ma25 and ma25 < ma75:
            return "↓ 下降"
        elif current > ma25:
            return "↗ やや上昇"
        else:
            return "↘ やや下降"
    else:
        return "↑ 上昇" if current > ma25 else "↓ 下降"


def get_rsi_status(rsi: float) -> str:
    if rsi >= 70:
        return "買われすぎ"
    elif rsi <= 30:
        return "売られすぎ"
    return "中立"


def get_macd_signal(macd_line: pd.Series, signal_line: pd.Series) -> str:
    """直近のMACDシグナルを返す"""
    if len(macd_line) < 2:
        return "不明"

    prev_macd, curr_macd = macd_line.iloc[-2], macd_line.iloc[-1]
    prev_sig, curr_sig = signal_line.iloc[-2], signal_line.iloc[-1]

    if prev_macd <= prev_sig and curr_macd > curr_sig:
        return "ゴールデンクロス"
    elif prev_macd >= prev_sig and curr_macd < curr_sig:
        return "デッドクロス"
    elif curr_macd > curr_sig:
        return "上昇トレンド"
    return "下降トレンド"
