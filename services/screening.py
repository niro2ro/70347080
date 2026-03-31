"""
screening.py
戦略別（短期 / 中期 / 長期）スコアリングによる株スクリーニングエンジン

設計方針
 - yf.download による一括取得（ループ内 API 呼び出し禁止）
 - ベクトル演算（pandas / numpy）で高速処理
 - NaN・データ不足・APIエラーに強い設計
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from services.stock_data import JP_TICKERS, US_TICKERS, TICKER_NAMES


# ═══════════════════════════════════════════════════════════════════
#  定数
# ═══════════════════════════════════════════════════════════════════

MIN_DATA_ROWS   = 75        # 最低必要データ数（MA75 計算のため）
MIN_PRICE       = 300       # ノイズ除去：最低株価
MIN_VOLUME      = 100_000   # ノイズ除去：最低出来高
MIN_SCORE       = 5         # 抽出最低スコア
TOP_N           = 20        # 返却銘柄数上限


# ═══════════════════════════════════════════════════════════════════
#  メイン関数（Streamlit キャッシュ付き）
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_stock_screening(market: str = "JP", mode: str = "swing") -> list:
    """
    戦略別スコアリングによる株スクリーニング

    Parameters
    ----------
    market : "JP" | "US"
    mode   : "day"（短期）| "swing"（中期）| "long"（長期）

    Returns
    -------
    list of dict  スコア降順・上位 TOP_N 件
        {ticker, name, price, change_pct, volume_ratio, rsi, trend, score, risk}
    """
    tickers      = JP_TICKERS if market == "JP" else US_TICKERS
    tickers_dict = {t: TICKER_NAMES.get(t, t) for t in tickers}

    # ── データ一括取得 ─────────────────────────────────────────────
    raw = _download(tickers)
    if raw is None or raw.empty:
        return []

    # ── 銘柄ごとに指標を抽出してリスト化 ──────────────────────────
    records = []
    for ticker in tickers:
        rec = _extract_metrics(ticker, tickers_dict, raw)
        if rec is not None:
            records.append(rec)

    if not records:
        return []

    df = pd.DataFrame(records)

    # ── 相対評価（パーセンタイルランク） ──────────────────────────
    df = _add_percentile_ranks(df)

    # ── 戦略スコアリング → フィルタリング → ソート ────────────────
    df = _apply_score(df, mode)
    df = df[df["score"] >= MIN_SCORE]

    if df.empty:
        return []

    df = df.sort_values(["score", "volume_rank"], ascending=False)

    # ── 出力整形 ──────────────────────────────────────────────────
    output_cols = ["ticker", "name", "price", "change_pct",
                   "volume_ratio", "rsi", "trend", "score", "risk"]
    return df.head(TOP_N)[output_cols].to_dict("records")


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：データ取得
# ═══════════════════════════════════════════════════════════════════

def _download(tickers: list) -> pd.DataFrame | None:
    """yfinance から 200 日分を一括ダウンロード"""
    try:
        raw = yf.download(
            tickers,
            period="200d",
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            threads=True,
            progress=False,
        )
        raw.sort_index(inplace=True)
        return raw
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：1 銘柄の指標抽出
# ═══════════════════════════════════════════════════════════════════

def _extract_metrics(ticker: str, tickers_dict: dict, raw: pd.DataFrame) -> dict | None:
    """
    1 銘柄分の全指標をスカラー値として抽出する。
    エラーやデータ不足の場合は None を返してスキップ。
    """
    try:
        # ── OHLCV 取得（MultiIndex 対応）──────────────────────────
        if isinstance(raw.columns, pd.MultiIndex):
            closes  = raw[ticker]["Close"].dropna()
            volumes = raw[ticker]["Volume"].dropna()
        else:
            closes  = raw["Close"].dropna()
            volumes = raw["Volume"].dropna()

        # ── データ数チェック ──────────────────────────────────────
        if len(closes) < MIN_DATA_ROWS or len(volumes) < 20:
            return None

        # ── ノイズ除去フィルター ──────────────────────────────────
        price    = float(closes.iloc[-1])
        vol_last = float(volumes.iloc[-1])
        if price <= MIN_PRICE or vol_last <= MIN_VOLUME:
            return None

        # ── 価格変化率 ────────────────────────────────────────────
        change_pct = (closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100

        # ── 出来高指標 ────────────────────────────────────────────
        vol_mean20  = volumes.iloc[-20:].mean()
        volume_ratio = vol_last / vol_mean20 if vol_mean20 > 0 else 1.0
        volume_trend = bool(volumes.iloc[-5:].mean() > volumes.iloc[-20:].mean())

        # ── RSI(14) Wilder法 ──────────────────────────────────────
        rsi_series = _calc_rsi(closes, period=14)
        rsi        = float(rsi_series.iloc[-1])
        rsi_slope  = float(rsi_series.diff(3).iloc[-1])   # 3 日傾き

        # ── 移動平均 ──────────────────────────────────────────────
        ma25_series = closes.rolling(25).mean()
        ma75_series = closes.rolling(75).mean()
        ma25        = float(ma25_series.iloc[-1])
        ma75        = float(ma75_series.iloc[-1])
        ma25_slope  = float(ma25_series.diff(5).iloc[-1])  # 5 日傾き

        # ── NaN チェック（MA 計算失敗時） ──────────────────────────
        if np.isnan(ma25) or np.isnan(ma75):
            return None

        # ── トレンド強度 ──────────────────────────────────────────
        trend_strength = (ma25 - ma75) / ma75 if ma75 != 0 else 0.0

        # ── 価格乖離率（MA25 比）─────────────────────────────────
        ma_gap = (price - ma25) / ma25 * 100 if ma25 != 0 else 0.0

        # ── トレンド分類 ──────────────────────────────────────────
        trend = _classify_trend(trend_strength)

        # ── リスク指標 ────────────────────────────────────────────
        returns    = closes.pct_change().dropna()
        volatility = float(returns.std())
        drawdown   = float((closes / closes.cummax() - 1).min())
        risk       = abs(drawdown) * volatility

        return {
            "ticker":         ticker,
            "name":           tickers_dict.get(ticker, ticker),
            "price":          price,
            "change_pct":     float(change_pct),
            "volume_ratio":   float(volume_ratio),
            "volume_trend":   volume_trend,
            "rsi":            rsi,
            "rsi_slope":      rsi_slope,
            "ma25_slope":     ma25_slope,
            "ma_gap":         ma_gap,
            "trend_strength": trend_strength,
            "trend":          trend,
            "volatility":     volatility,
            "drawdown":       drawdown,
            "risk":           risk,
        }

    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：RSI（Wilder 法）
# ═══════════════════════════════════════════════════════════════════

def _calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI 全時系列を Wilder 法（ewm com=period-1）で計算"""
    delta    = closes.diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：トレンド分類
# ═══════════════════════════════════════════════════════════════════

def _classify_trend(ts: float) -> str:
    """trend_strength の値からトレンド文字列を返す"""
    if ts > 0.02:
        return "強い上昇"
    elif ts > 0:
        return "やや上昇"
    elif ts < -0.02:
        return "強い下降"
    else:
        return "やや下降"


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：パーセンタイルランク付け
# ═══════════════════════════════════════════════════════════════════

def _add_percentile_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """rsi_rank / volume_rank / change_rank を全銘柄相対評価で追加"""
    df = df.copy()
    df["rsi_rank"]    = df["rsi"].rank(pct=True)
    df["volume_rank"] = df["volume_ratio"].rank(pct=True)
    df["change_rank"] = df["change_pct"].rank(pct=True)
    return df


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：戦略スコアリング
# ═══════════════════════════════════════════════════════════════════

def _apply_score(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """
    mode に応じてリスクフィルタリングとスコアを計算して返す

    ── 短期（day）  ── max 8 点
        出来高急増 +3 / 上昇率高い +2 / RSI 上昇傾向 +1
        上昇トレンド +1 / 出来高増加トレンド +1
        risk < 0.6

    ── 中期（swing）── max 8 点
        RSI 低位 +2 / MA25 上昇傾向 +2 / トレンド強 +2
        出来高中 +1 / MA25 乖離小 +1
        risk < 0.4

    ── 長期（long） ── max 9 点
        トレンド強い上昇 +3 / 低ボラ +2 / ドローダウン小 +2
        MA25 上昇 +1 / RSI 中立 +1
        risk < 0.3
    """
    df = df.copy()

    if mode == "day":
        df = df[df["risk"] < 0.6]
        df["score"] = (
              (df["volume_rank"]   > 0.8 ).astype(int) * 3
            + (df["change_rank"]   > 0.7 ).astype(int) * 2
            + (df["rsi_slope"]     > 0   ).astype(int) * 1
            + (df["trend_strength"]> 0   ).astype(int) * 1
            + df["volume_trend"].astype(int)            * 1
        )

    elif mode == "swing":
        df = df[df["risk"] < 0.4]
        df["score"] = (
              (df["rsi_rank"]      < 0.4 ).astype(int) * 2
            + (df["ma25_slope"]    > 0   ).astype(int) * 2
            + (df["trend_strength"]> 0.01).astype(int) * 2
            + (df["volume_rank"]   > 0.5 ).astype(int) * 1
            + (df["ma_gap"]        < 5   ).astype(int) * 1
        )

    elif mode == "long":
        df = df[df["risk"] < 0.3]
        df["score"] = (
              (df["trend_strength"] > 0.03).astype(int) * 3
            + (df["volatility"]     < 0.03).astype(int) * 2
            + (df["drawdown"]       > -0.2).astype(int) * 2
            + (df["ma25_slope"]     > 0   ).astype(int) * 1
            + ((df["rsi_rank"] >= 0.4) & (df["rsi_rank"] <= 0.6)).astype(int) * 1
        )

    else:
        df["score"] = 0

    return df
