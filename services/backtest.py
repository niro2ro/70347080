"""
backtest.py
スクリーニングロジックの有効性を検証するバックテストエンジン

設計方針：
 ① 一括ダウンロード（ループ内 API 呼び出し禁止）
 ② 指標を事前ベクトル計算してから日次ループ（高速化）
 ③ expanding 計算で未来データ使用を厳密に禁止
 ④ NaN・データ不足・APIエラーに強い設計
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from services.stock_data import JP_TICKERS, US_TICKERS, TICKER_NAMES
from services.screening import _calc_rsi, _classify_trend, _apply_score, _add_percentile_ranks


# ═══════════════════════════════════════════════════════════════════
#  定数
# ═══════════════════════════════════════════════════════════════════

BACKTEST_START = "2022-01-01"
BACKTEST_END   = "2024-12-31"
MIN_DATA_ROWS  = 75        # ループ開始までの最低データ数
MIN_PRICE      = 300       # ノイズ除去：最低株価
MIN_VOLUME     = 100_000   # ノイズ除去：最低出来高
MIN_SCORE      = 5         # スクリーニング通過最低スコア
MAX_POSITIONS  = 5         # 1日あたり最大保有銘柄数

HOLDING_DAYS: dict = {
    "day":   1,
    "swing": 5,
    "long":  20,
}


# ═══════════════════════════════════════════════════════════════════
#  メイン関数
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def run_backtest(market: str = "JP", mode: str = "swing") -> dict:
    """
    バックテスト実行

    Parameters
    ----------
    market : "JP" | "US"
    mode   : "day"（短期）| "swing"（中期）| "long"（長期）

    Returns
    -------
    dict
        {mode, market, total_trades, win_rate, avg_return,
         max_loss, std, sharpe, equity_curve, trades_df}
    """
    tickers      = JP_TICKERS if market == "JP" else US_TICKERS
    tickers_dict = {t: TICKER_NAMES.get(t, t) for t in tickers}
    holding_days = HOLDING_DAYS.get(mode, 5)

    # ── ① 一括ダウンロード ────────────────────────────────────────
    raw = _download_historical(tickers)
    if raw is None or raw.empty:
        return {"error": "データ取得に失敗しました"}

    all_dates = raw.index

    # ── ② 全銘柄・全日付の指標を事前ベクトル計算 ─────────────────
    #     未来データ漏洩防止のため expanding 集計を使用
    indicators = _precompute_indicators(raw, tickers)
    if not indicators:
        return {"error": "指標の事前計算に失敗しました"}

    # ── ③ 日次ループ（その日までのデータのみで判断）──────────────
    trades = []

    for i, date in enumerate(all_dates):

        # 最低データ数（MA75 計算分）に達するまでスキップ
        if i < MIN_DATA_ROWS:
            continue

        # holding_days 後の売却日が存在しない場合はスキップ
        future_idx = i + holding_days
        if future_idx >= len(all_dates):
            continue
        sell_date = all_dates[future_idx]

        # ── その日の横断面レコードを生成 ──────────────────────────
        records = []
        for ticker, ind in indicators.items():
            rec = _record_at(ticker, tickers_dict, ind, date)
            if rec is not None:
                records.append(rec)

        if len(records) < 3:   # 銘柄数が少なすぎる日はスキップ
            continue

        df_day = pd.DataFrame(records)

        # ── 相対評価（パーセンタイルランク）──────────────────────
        df_day = _add_percentile_ranks(df_day)

        # ── 戦略スコアリング + フィルタリング ──────────────────────
        df_day = _apply_score(df_day, mode)
        df_day = df_day[df_day["score"] >= MIN_SCORE]

        if df_day.empty:
            continue

        df_day = df_day.sort_values(["score", "volume_rank"], ascending=False)
        selected = df_day.head(MAX_POSITIONS)

        # ── ④ 選定銘柄のリターンを計算 ────────────────────────────
        for _, row in selected.iterrows():
            ticker = row["ticker"]
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    buy_price  = float(raw.at[date,      (ticker, "Close")])
                    sell_price = float(raw.at[sell_date, (ticker, "Close")])
                else:
                    buy_price  = float(raw.at[date,  "Close"])
                    sell_price = float(raw.at[sell_date, "Close"])

                if np.isnan(buy_price) or np.isnan(sell_price) or buy_price == 0:
                    continue

                return_pct = (sell_price - buy_price) / buy_price * 100

                trades.append({
                    "date":       date,
                    "ticker":     ticker,
                    "name":       row.get("name", ticker),
                    "buy_price":  round(buy_price, 2),
                    "sell_price": round(sell_price, 2),
                    "return_pct": round(return_pct, 4),
                    "score":      int(row["score"]),
                    "win":        return_pct > 0,
                })

            except Exception:
                continue

    # ── ⑤ 評価指標を集計して返却 ──────────────────────────────────
    return _aggregate_metrics(trades, mode, market)


# ═══════════════════════════════════════════════════════════════════
#  複数モードを一括実行
# ═══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def run_all_modes(market: str = "JP") -> dict:
    """全3モードのバックテストを実行して比較 DataFrame も返す"""
    results = {}
    for mode in ("day", "swing", "long"):
        results[mode] = run_backtest(market=market, mode=mode)

    # 比較用サマリー DataFrame
    rows = []
    for mode, res in results.items():
        if "error" in res:
            continue
        rows.append({
            "モード":         {"day": "⚡短期", "swing": "📊中期", "long": "🏔長期"}[mode],
            "総トレード数":   res.get("total_trades", 0),
            "勝率 (%)":      round(res.get("win_rate", 0) * 100, 1),
            "平均リターン (%)": round(res.get("avg_return", 0), 3),
            "最大損失 (%)":   round(res.get("max_loss", 0), 3),
            "標準偏差":       round(res.get("std", 0), 4),
            "シャープレシオ": round(res.get("sharpe", 0), 3),
        })

    summary_df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return {"results": results, "summary": summary_df}


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：データ取得
# ═══════════════════════════════════════════════════════════════════

def _download_historical(tickers: list) -> pd.DataFrame | None:
    """2022-01-01 ～ 2024-12-31 を一括ダウンロード"""
    try:
        raw = yf.download(
            tickers,
            start=BACKTEST_START,
            end=BACKTEST_END,
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
#  内部ヘルパー：全指標の事前ベクトル計算
# ═══════════════════════════════════════════════════════════════════

def _precompute_indicators(raw: pd.DataFrame, tickers: list) -> dict:
    """
    各銘柄の指標シリーズを事前ベクトル計算して辞書で返す。
    expanding 集計を用いて未来データ漏洩を防止。

    Returns
    -------
    dict  {ticker: {indicator_name: pd.Series, ...}}
    """
    indicators = {}

    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                closes  = raw[ticker]["Close"]
                volumes = raw[ticker]["Volume"]
            else:
                closes  = raw["Close"]
                volumes = raw["Volume"]

            closes  = closes.dropna()
            volumes = volumes.dropna()

            if len(closes) < MIN_DATA_ROWS:
                continue

            returns = closes.pct_change()

            # ── 価格変化率 ─────────────────────────────────────────
            change_pct = returns * 100

            # ── 出来高指標 ─────────────────────────────────────────
            vol_ma20   = volumes.rolling(20, min_periods=1).mean()
            vol_ratio  = volumes / vol_ma20.replace(0, np.nan)
            vol_trend  = volumes.rolling(5,  min_periods=1).mean() > vol_ma20

            # ── RSI(14) Wilder法 ───────────────────────────────────
            rsi_series = _calc_rsi(closes, period=14)
            rsi_slope  = rsi_series.diff(3)

            # ── 移動平均 ───────────────────────────────────────────
            ma25       = closes.rolling(25, min_periods=25).mean()
            ma75       = closes.rolling(75, min_periods=75).mean()
            ma25_slope = ma25.diff(5)

            # ── トレンド強度 ───────────────────────────────────────
            trend_strength = (ma25 - ma75) / ma75.replace(0, np.nan)

            # ── 価格乖離率 ─────────────────────────────────────────
            ma_gap = (closes - ma25) / ma25.replace(0, np.nan) * 100

            # ── ボラティリティ（expanding std：未来データ不使用）───
            volatility = returns.expanding(min_periods=30).std()

            # ── ドローダウン（expanding max：未来データ不使用）─────
            expanding_max  = closes.expanding().max()
            drawdown_daily = closes / expanding_max - 1
            drawdown       = drawdown_daily.expanding().min()   # 最大ドローダウン（各日現在まで）

            # ── リスク指標 ─────────────────────────────────────────
            risk = abs(drawdown) * volatility

            indicators[ticker] = {
                "closes":          closes,
                "volumes":         volumes,
                "change_pct":      change_pct,
                "vol_ratio":       vol_ratio,
                "vol_trend":       vol_trend,
                "rsi":             rsi_series,
                "rsi_slope":       rsi_slope,
                "ma25_slope":      ma25_slope,
                "trend_strength":  trend_strength,
                "ma_gap":          ma_gap,
                "volatility":      volatility,
                "drawdown":        drawdown,
                "risk":            risk,
            }

        except Exception:
            continue

    return indicators


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：特定日付の横断面レコード生成
# ═══════════════════════════════════════════════════════════════════

def _record_at(ticker: str, tickers_dict: dict,
               ind: dict, date) -> dict | None:
    """
    事前計算済み指標シリーズから、指定日付のスカラー値を取り出してレコードを返す。
    フィルター条件を満たさない、または NaN の場合は None を返す。
    """
    try:
        def _get(series: pd.Series, default=np.nan):
            val = series.get(date, default)
            return float(val) if not pd.isna(val) else np.nan

        price      = _get(ind["closes"])
        vol_last   = _get(ind["volumes"])
        change_pct = _get(ind["change_pct"])
        vol_ratio  = _get(ind["vol_ratio"])
        rsi        = _get(ind["rsi"])
        rsi_slope  = _get(ind["rsi_slope"])
        ma25_slope = _get(ind["ma25_slope"])
        ts         = _get(ind["trend_strength"])
        ma_gap     = _get(ind["ma_gap"])
        volatility = _get(ind["volatility"])
        drawdown   = _get(ind["drawdown"])
        risk       = _get(ind["risk"])

        # vol_trend は bool Series
        vt_val     = ind["vol_trend"].get(date, False)
        vol_trend  = bool(vt_val) if not pd.isna(vt_val) else False

        # NaN チェック（必須指標）
        if any(np.isnan(v) for v in [price, vol_last, change_pct, vol_ratio,
                                      rsi, ts, risk]):
            return None

        # ── ノイズ除去フィルター ───────────────────────────────────
        if price <= MIN_PRICE or vol_last <= MIN_VOLUME:
            return None

        trend = _classify_trend(ts)

        return {
            "ticker":         ticker,
            "name":           tickers_dict.get(ticker, ticker),
            "price":          price,
            "change_pct":     change_pct,
            "volume_ratio":   vol_ratio,
            "volume_trend":   vol_trend,
            "rsi":            rsi,
            "rsi_slope":      rsi_slope if not np.isnan(rsi_slope) else 0.0,
            "ma25_slope":     ma25_slope if not np.isnan(ma25_slope) else 0.0,
            "ma_gap":         ma_gap if not np.isnan(ma_gap) else 0.0,
            "trend_strength": ts,
            "trend":          trend,
            "volatility":     volatility if not np.isnan(volatility) else 0.05,
            "drawdown":       drawdown if not np.isnan(drawdown) else -0.1,
            "risk":           risk,
        }

    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  内部ヘルパー：評価指標の集計
# ═══════════════════════════════════════════════════════════════════

def _aggregate_metrics(trades: list, mode: str, market: str) -> dict:
    """トレードリストから評価指標を計算して返す"""

    base = {"mode": mode, "market": market, "total_trades": 0}

    if not trades:
        return {**base, "error": "該当トレードなし（スコア基準を満たす銘柄が存在しなかった）"}

    df_t   = pd.DataFrame(trades)
    rets   = df_t["return_pct"]

    total_trades = len(rets)
    win_count    = int(df_t["win"].sum())
    win_rate     = win_count / total_trades if total_trades > 0 else 0.0
    avg_return   = float(rets.mean())
    max_loss     = float(rets.min())
    std          = float(rets.std())
    sharpe       = avg_return / std if std != 0 else 0.0

    # 累積リターン（equity curve）
    equity_curve = (1 + rets / 100).cumprod().reset_index(drop=True)

    return {
        "mode":          mode,
        "market":        market,
        "total_trades":  total_trades,
        "win_count":     win_count,
        "win_rate":      win_rate,
        "avg_return":    avg_return,
        "max_loss":      max_loss,
        "std":           std,
        "sharpe":        sharpe,
        "equity_curve":  equity_curve,
        "trades_df":     df_t,
    }
