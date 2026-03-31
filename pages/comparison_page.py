import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from services.stock_data import (
    JP_TICKERS, US_TICKERS, TICKER_NAMES, get_comparison_data,
)
from services.technical import (
    calculate_rsi_series, calculate_macd,
)

COLORS = ["#FF9500", "#34C759", "#FF4B4B", "#5856D6"]
BG = "#0E1117"
GRID = "#2D2D2D"

PERIOD_OPTIONS = {"1ヶ月": "1mo", "3ヶ月": "3mo", "6ヶ月": "6mo", "1年": "1y"}


def show_comparison():
    st.markdown("# 📊 銘柄比較")
    st.caption("最大4銘柄を比較できます。")

    # 市場・銘柄選択
    col_m, col_p = st.columns([2, 2])
    with col_m:
        market = st.selectbox(
            "市場",
            ["JP", "US"],
            format_func=lambda x: "🇯🇵 日本株" if x == "JP" else "🇺🇸 米国株",
            key="cmp_market",
        )
    with col_p:
        period_label = st.radio(
            "期間", list(PERIOD_OPTIONS.keys()), index=1, horizontal=True, key="cmp_period"
        )

    all_tickers = JP_TICKERS if market == "JP" else US_TICKERS
    ticker_labels = {t: f"{t}  {TICKER_NAMES.get(t, '')}" for t in all_tickers}

    selected = st.multiselect(
        "比較銘柄を選択（最大4銘柄）",
        options=all_tickers,
        format_func=lambda t: ticker_labels[t],
        max_selections=4,
        default=all_tickers[:2],
        key="cmp_tickers",
    )

    if len(selected) < 2:
        st.info("2銘柄以上を選択してください。")
        return

    period = PERIOD_OPTIONS[period_label]

    with st.spinner("データ取得中..."):
        data = get_comparison_data(tuple(selected), period=period)

    valid = [t for t in selected if t in data and not data[t].empty]
    if len(valid) < 2:
        st.error("有効なデータが2銘柄以上取得できませんでした。")
        return

    # --- 正規化価格チャート ---
    st.markdown("---")
    st.markdown("### 📈 価格推移（基準日=100 に正規化）")

    fig_price = go.Figure()
    for i, ticker in enumerate(valid):
        closes = data[ticker]["Close"].dropna()
        if closes.empty:
            continue
        normalized = closes / closes.iloc[0] * 100
        name = TICKER_NAMES.get(ticker, ticker)
        fig_price.add_trace(go.Scatter(
            x=closes.index, y=normalized,
            mode="lines", name=f"{ticker} ({name})",
            line=dict(color=COLORS[i % len(COLORS)], width=2),
        ))

    fig_price.add_hline(y=100, line_dash="dot", line_color="#666", opacity=0.6)
    _apply_dark_layout(fig_price, height=380)
    st.plotly_chart(fig_price, use_container_width=True)

    # --- RSI比較 ---
    st.markdown("### 📉 RSI 比較")

    fig_rsi = go.Figure()
    for i, ticker in enumerate(valid):
        closes = data[ticker]["Close"].dropna()
        if len(closes) < 15:
            continue
        rsi = calculate_rsi_series(closes)
        name = TICKER_NAMES.get(ticker, ticker)
        fig_rsi.add_trace(go.Scatter(
            x=closes.index, y=rsi,
            mode="lines", name=f"{ticker} ({name})",
            line=dict(color=COLORS[i % len(COLORS)], width=2),
        ))

    fig_rsi.add_hline(y=70, line_dash="dot", line_color="#FF4B4B", opacity=0.5)
    fig_rsi.add_hline(y=50, line_dash="dot", line_color="#666", opacity=0.3)
    fig_rsi.add_hline(y=30, line_dash="dot", line_color="#4B9EFF", opacity=0.5)
    fig_rsi.add_hrect(y0=70, y1=100, fillcolor="#FF4B4B", opacity=0.04)
    fig_rsi.add_hrect(y0=0, y1=30, fillcolor="#4B9EFF", opacity=0.04)
    _apply_dark_layout(fig_rsi, height=280)
    fig_rsi.update_yaxes(range=[0, 100])
    st.plotly_chart(fig_rsi, use_container_width=True)

    # --- MACD比較 ---
    st.markdown("### 📊 MACD 比較")

    fig_macd = make_subplots(
        rows=len(valid), cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=[
            f"{t} ({TICKER_NAMES.get(t, '')})" for t in valid
        ],
    )
    for i, ticker in enumerate(valid):
        closes = data[ticker]["Close"].dropna()
        if len(closes) < 26:
            continue
        macd_line, signal_line, histogram = calculate_macd(closes)
        color = COLORS[i % len(COLORS)]
        row = i + 1

        bar_colors = ["#FF4B4B" if v >= 0 else "#4B9EFF" for v in histogram]
        fig_macd.add_trace(
            go.Bar(x=closes.index, y=histogram, name=f"Hist {ticker}",
                   marker_color=bar_colors, opacity=0.5, showlegend=False),
            row=row, col=1,
        )
        fig_macd.add_trace(
            go.Scatter(x=closes.index, y=macd_line, mode="lines",
                       name=f"MACD {ticker}", line=dict(color=color, width=1.5)),
            row=row, col=1,
        )
        fig_macd.add_trace(
            go.Scatter(x=closes.index, y=signal_line, mode="lines",
                       name=f"Signal {ticker}", line=dict(color="#AF52DE", width=1.5, dash="dot")),
            row=row, col=1,
        )

    _apply_dark_layout(fig_macd, height=220 * len(valid))
    st.plotly_chart(fig_macd, use_container_width=True)

    # --- 指標サマリーテーブル ---
    st.markdown("### 📋 指標サマリー")
    from services.technical import calculate_rsi, get_trend, get_rsi_status, get_macd_signal

    rows = []
    for ticker in valid:
        closes = data[ticker]["Close"].dropna()
        if len(closes) < 2:
            continue
        current = closes.iloc[-1]
        prev = closes.iloc[-2]
        change = (current - prev) / prev * 100
        rsi = calculate_rsi(closes)
        macd_l, sig_l, _ = calculate_macd(closes)
        rows.append({
            "ティッカー": ticker,
            "銘柄名": TICKER_NAMES.get(ticker, ticker),
            "現在値": f"{current:,.2f}",
            "前日比": f"{change:+.2f}%",
            "RSI": f"{rsi:.1f}",
            "RSI判定": get_rsi_status(rsi),
            "トレンド": get_trend(closes),
            "MACD": get_macd_signal(macd_l, sig_l),
        })

    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _apply_dark_layout(fig: go.Figure, height: int = 400):
    fig.update_layout(
        height=height,
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        font=dict(color="white", size=11),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_rangeslider_visible=False,
    )
    for axis in fig.layout:
        if axis.startswith("xaxis") or axis.startswith("yaxis"):
            fig.layout[axis].update(gridcolor=GRID, showgrid=True)
